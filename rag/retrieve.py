"""Phase 4: the retriever + /retrieve endpoint.

Loads the FAISS + BM25 index built by build_index.py and does hybrid retrieval
(Reciprocal Rank Fusion of dense MiniLM + BM25). The Retriever class is reused by
recall_at_k.py and by System C. The FastAPI app exposes /retrieve.

Serve:  uvicorn rag.retrieve:app --host 0.0.0.0 --port 8200
"""
import json, re, pickle, pathlib
from collections import defaultdict
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

HERE = pathlib.Path(__file__).parent
IDX = HERE / "index"

def tokenize(t):
    return re.findall(r"[a-z0-9]+", t.lower())

def rrf(rank_lists, c=60, topn=50):
    scores = defaultdict(float)
    for rl in rank_lists:
        for rank, doc in enumerate(rl):
            scores[doc] += 1.0 / (c + rank + 1)
    return sorted(scores, key=lambda d: -scores[d])[:topn]

class Retriever:
    def __init__(self):
        self.meta = json.load((IDX / "meta.json").open())
        self.chunks = [json.loads(l) for l in (IDX / "chunks.jsonl").open(encoding="utf-8")]
        self.index = faiss.read_index(str(IDX / "faiss.index"))
        self.bm25 = pickle.load((IDX / "bm25.pkl").open("rb"))
        self.model = SentenceTransformer(self.meta["model"])

    def _dense(self, q, n):
        qv = self.model.encode([q], normalize_embeddings=True).astype("float32")
        _, I = self.index.search(qv, n)
        return I[0].tolist()

    def _bm25(self, q, n):
        s = self.bm25.get_scores(tokenize(q))
        return np.argsort(s)[::-1][:n].tolist()

    def rank_ids(self, q, k=5, method="hybrid", pool=50):
        """Ranked chunk indices (used by recall@k)."""
        if method == "dense":
            return self._dense(q, k)
        if method == "bm25":
            return self._bm25(q, k)
        return rrf([self._dense(q, pool), self._bm25(q, pool)], topn=k)

    def search(self, q, k=5, method="hybrid", pool=50):
        ids = self.rank_ids(q, k, method, pool)
        out = []
        for rank, i in enumerate(ids[:k]):
            c = self.chunks[i]
            out.append({"rank": rank + 1, "chunk_id": c["chunk_id"], "doc_id": c["doc_id"],
                        "title": c["title"], "source": c["source"], "text": c["text"]})
        return out

# ---- FastAPI endpoint ----
try:
    from fastapi import FastAPI
    from pydantic import BaseModel

    app = FastAPI(title="yugioh-retriever")
    _R = {"r": None}

    def get_retriever():
        if _R["r"] is None:
            _R["r"] = Retriever()
        return _R["r"]

    class Req(BaseModel):
        question: str
        k: int = 5
        method: str = "hybrid"

    @app.get("/health")
    def health():
        r = get_retriever()
        return {"ok": True, "n_chunks": r.meta["n_chunks"], "model": r.meta["model"]}

    @app.post("/retrieve")
    def retrieve(req: Req):
        return {"question": req.question, "method": req.method,
                "passages": get_retriever().search(req.question, req.k, req.method)}
except ImportError:
    pass

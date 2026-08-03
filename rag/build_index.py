"""Phase 4: build the real retriever over the full cleaned corpus.

Chunks all of corpus_clean.jsonl at 1000/150 (title-augmented), embeds with
all-MiniLM-L6-v2, and builds a FAISS flat (inner-product) index + a BM25 index over
the same chunks — the locked hybrid config from the chunking study. Retrieval indexes
ALL splits (System C serves the whole corpus at inference).

Artifacts -> rag/index/ :  faiss.index, bm25.pkl, chunks.jsonl, meta.json
"""
import json, re, time, pickle, pathlib
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

HERE = pathlib.Path(__file__).parent
CORPUS = HERE.parent / "data" / "corpus" / "corpus_clean.jsonl"
OUT = HERE / "index"
MODEL = "all-MiniLM-L6-v2"
SIZE, OVERLAP = 1000, 150

def chunk(text, size=SIZE, overlap=OVERLAP):
    step = max(1, size - overlap)
    out, i, n = [], 0, len(text)
    while i < n:
        out.append(text[i:i + size])
        if i + size >= n:
            break
        i += step
    return out

def tokenize(t):
    return re.findall(r"[a-z0-9]+", t.lower())

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    docs = [json.loads(l) for l in CORPUS.open(encoding="utf-8")]
    chunks = []
    for d in docs:
        for j, piece in enumerate(chunk(d["text"])):
            chunks.append({"chunk_id": f"{d['doc_id']}-c{j}", "doc_id": d["doc_id"],
                           "title": d["title"], "source": d["source"], "text": piece})
    print(f"{len(docs)} docs -> {len(chunks)} chunks")

    # title-augmented text for embedding + BM25; raw `text` kept for gold matching / display
    aug = [f"{c['title']}: {c['text']}" for c in chunks]

    print(f"embedding with {MODEL} ...")
    model = SentenceTransformer(MODEL)
    t0 = time.perf_counter()
    emb = model.encode(aug, normalize_embeddings=True, batch_size=256,
                       show_progress_bar=True).astype("float32")
    embed_s = time.perf_counter() - t0

    index = faiss.IndexFlatIP(emb.shape[1])
    index.add(emb)
    faiss.write_index(index, str(OUT / "faiss.index"))

    print("building BM25 ...")
    bm25 = BM25Okapi([tokenize(a) for a in aug])
    pickle.dump(bm25, (OUT / "bm25.pkl").open("wb"))

    with (OUT / "chunks.jsonl").open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    meta = {"model": MODEL, "n_docs": len(docs), "n_chunks": len(chunks),
            "dim": int(emb.shape[1]), "chunk_size": SIZE, "overlap": OVERLAP,
            "embed_seconds": round(embed_s, 1),
            "embed_chunks_per_s": round(len(chunks) / embed_s, 1),
            "index_mb": round(emb.nbytes / 1e6, 1)}
    json.dump(meta, (OUT / "meta.json").open("w"), indent=2)
    print(json.dumps(meta, indent=2))
    print(f"wrote {OUT}/ (faiss.index, bm25.pkl, chunks.jsonl, meta.json)")

if __name__ == "__main__":
    main()

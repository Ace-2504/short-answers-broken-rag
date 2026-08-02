"""
Retriever design study. One measurement rig, many decisions. For each setting we
chunk the sample corpus, embed, retrieve, and measure recall@k on the probes
(does the chunk containing a probe's gold sentence appear in the top-k?).

Studies (see docs/initial-testing.md for the why and the limitations):
  1. SIZE sweep         - best chunk size (overlap fixed at ~15%)
  2. OVERLAP sweep      - is 150 overlap justified (size fixed at 1000)
  3. MODEL bake-off     - bge-small vs gte-small vs e5-small vs MiniLM
  4. QUERY PREFIX       - does the bge query instruction help
  5. TITLE-AUG          - does prepending the page title to a chunk help
  6. INDEX flat vs IVF  - is a flat index enough (nprobe tradeoff)
  7. HYBRID dense+BM25  - does lexical search help (exact card names)
  8. BY QUESTION TYPE   - are interaction/timing questions harder to retrieve
  9. GATE CALIBRATION   - retrieval-score threshold separating good/bad probes
 10. FEASIBILITY        - embed throughput, index build, memory, latency, 20MB extrapolation

Writes results.json. Heavy embeddings are cached per (model, chunk-config, title-aug).
"""
import json, pathlib, statistics, time, re
from collections import defaultdict
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

HERE = pathlib.Path(__file__).parent
CORPUS = HERE / "sample_corpus.jsonl"
PROBES = HERE / "probes.jsonl"
OUT = HERE / "results.json"

KS = [1, 3, 5, 10]
BASELINE = (1000, 150)          # size, overlap used by studies 3-10
FULL_CORPUS_MB = 20.0           # target real corpus size, for extrapolation

# Embedding models with their recommended query/passage prefixes.
MODELS = {
    "bge-small-en-v1.5": dict(id="BAAI/bge-small-en-v1.5",
        qpref="Represent this sentence for searching relevant passages: ", ppref=""),
    "gte-small":         dict(id="thenlper/gte-small", qpref="", ppref=""),
    "e5-small-v2":       dict(id="intfloat/e5-small-v2", qpref="query: ", ppref="passage: "),
    "minilm-l6":         dict(id="sentence-transformers/all-MiniLM-L6-v2", qpref="", ppref=""),
}
DEFAULT_MODEL = "bge-small-en-v1.5"

SIZE_SWEEP    = [(500, 75), (800, 120), (1000, 150), (1200, 180), (1500, 225)]
OVERLAP_SWEEP = [(1000, 0), (1000, 100), (1000, 150), (1000, 250)]

_model_cache = {}
def get_model(name):
    if name not in _model_cache:
        _model_cache[name] = SentenceTransformer(MODELS[name]["id"])
    return _model_cache[name]

# ---------- chunking ----------
def chunk_doc(text, size, overlap):
    step = max(1, size - overlap)
    out, i, n = [], 0, len(text)
    while i < n:
        piece = text[i:i + size]
        out.append(piece)
        if i + size >= n:
            break
        i += step
    return out

def build_chunks(docs, size, overlap):
    """Return chunks[], doc_of[], by_doc{doc_id:[global ids]}, id2title."""
    chunks, doc_of, by_doc, id2title = [], [], {}, {}
    for d in docs:
        id2title[d["doc_id"]] = d["title"]
        for t in chunk_doc(d["text"], size, overlap):
            g = len(chunks)
            chunks.append(t); doc_of.append(d["doc_id"])
            by_doc.setdefault(d["doc_id"], []).append(g)
    return chunks, doc_of, by_doc, id2title

def gold_ids(probe, chunks, by_doc):
    g = probe["gold_sentence"]
    return set(x for x in by_doc.get(probe["doc_id"], []) if g in chunks[x])

# ---------- passages / embeddings ----------
def make_passages(chunks, doc_of, id2title, ppref, title_aug):
    if title_aug:
        return [f"{ppref}{id2title[doc_of[i]]}: {chunks[i]}" for i in range(len(chunks))]
    return [f"{ppref}{c}" for c in chunks]

def embed(model, texts):
    return model.encode(texts, normalize_embeddings=True, batch_size=64,
                        show_progress_bar=False).astype("float32")

def dense_rankings(chunks, doc_of, id2title, probes, model_name, title_aug=False, topn=50):
    """Return (rankings[list per probe of global chunk ids], top_scores[per probe],
    build_time, encode_time, emb_mb)."""
    m = get_model(model_name); cfg = MODELS[model_name]
    passages = make_passages(chunks, doc_of, id2title, cfg["ppref"], title_aug)
    t0 = time.perf_counter(); pemb = embed(m, passages); enc_t = time.perf_counter() - t0
    t0 = time.perf_counter()
    index = faiss.IndexFlatIP(pemb.shape[1]); index.add(pemb)
    build_t = time.perf_counter() - t0
    qtext = [cfg["qpref"] + p["question"] for p in probes]
    qemb = embed(m, qtext)
    D, I = index.search(qemb, min(topn, len(chunks)))
    rankings = [row.tolist() for row in I]
    top_scores = [float(row[0]) for row in D]
    emb_mb = pemb.nbytes / 1e6
    return rankings, top_scores, build_t, enc_t, emb_mb

def recall(rankings, probes, chunks, by_doc, ks=KS):
    hits = {k: 0 for k in ks}; covered = 0
    for ranks, p in zip(rankings, probes):
        g = gold_ids(p, chunks, by_doc)
        if not g:
            continue
        covered += 1
        for k in ks:
            if g & set(ranks[:k]):
                hits[k] += 1
    return {"covered": covered,
            **{f"recall@{k}": round(hits[k]/covered, 3) if covered else 0.0 for k in ks}}

def tok_stats(model_name, chunks):
    tok = get_model(model_name).tokenizer
    lens = [len(tok.encode(c, add_special_tokens=False)) for c in chunks]
    return round(statistics.mean(lens), 1), int(np.percentile(lens, 95))

# ---------- BM25 / hybrid ----------
def tokenize(t):
    return re.findall(r"[a-z0-9]+", t.lower())

def bm25_rankings(chunks, probes, topn=50):
    bm = BM25Okapi([tokenize(c) for c in chunks])
    out = []
    for p in probes:
        scores = bm.get_scores(tokenize(p["question"]))
        out.append(np.argsort(scores)[::-1][:topn].tolist())
    return out

def rrf(rank_lists, c=60, topn=50):
    scores = defaultdict(float)
    for rl in rank_lists:
        for rank, doc in enumerate(rl):
            scores[doc] += 1.0 / (c + rank + 1)
    return [d for d, _ in sorted(scores.items(), key=lambda x: -x[1])][:topn]

# ---------- studies ----------
def study_chunk_sweep(docs, probes, sweep):
    rows = []
    for size, ovlp in sweep:
        chunks, doc_of, by_doc, id2title = build_chunks(docs, size, ovlp)
        rk, *_ = dense_rankings(chunks, doc_of, id2title, probes, DEFAULT_MODEL)
        mtok, p95 = tok_stats(DEFAULT_MODEL, chunks)
        rows.append({"size": size, "overlap": ovlp, "n_chunks": len(chunks),
                     "mean_tokens": mtok, "p95_tokens": p95,
                     **recall(rk, probes, chunks, by_doc)})
    return rows

def study_models(docs, probes):
    chunks, doc_of, by_doc, id2title = build_chunks(docs, *BASELINE)
    rows = []
    for name in MODELS:
        rk, _, bt, et, mb = dense_rankings(chunks, doc_of, id2title, probes, name)
        rows.append({"model": name, "dim": get_model(name).get_sentence_embedding_dimension(),
                     "encode_s": round(et, 2), "emb_mb": round(mb, 1),
                     **recall(rk, probes, chunks, by_doc)})
    return rows

def study_prefix(docs, probes):
    """bge query instruction on vs off (patch the model cfg for the off case)."""
    chunks, doc_of, by_doc, id2title = build_chunks(docs, *BASELINE)
    rows = []
    orig = MODELS[DEFAULT_MODEL]["qpref"]
    for label, pref in [("prefix_on", orig), ("prefix_off", "")]:
        MODELS[DEFAULT_MODEL]["qpref"] = pref
        rk, *_ = dense_rankings(chunks, doc_of, id2title, probes, DEFAULT_MODEL)
        rows.append({"setting": label, **recall(rk, probes, chunks, by_doc)})
    MODELS[DEFAULT_MODEL]["qpref"] = orig
    return rows

def study_title_aug(docs, probes):
    chunks, doc_of, by_doc, id2title = build_chunks(docs, *BASELINE)
    rows = []
    for label, ta in [("title_off", False), ("title_on", True)]:
        rk, *_ = dense_rankings(chunks, doc_of, id2title, probes, DEFAULT_MODEL, title_aug=ta)
        rows.append({"setting": label, **recall(rk, probes, chunks, by_doc)})
    return rows

def study_index(docs, probes):
    """Flat vs IVF at several nprobe. Shows flat is enough / the nprobe tradeoff."""
    chunks, doc_of, by_doc, id2title = build_chunks(docs, *BASELINE)
    m = get_model(DEFAULT_MODEL); cfg = MODELS[DEFAULT_MODEL]
    pemb = embed(m, make_passages(chunks, doc_of, id2title, cfg["ppref"], False))
    qemb = embed(m, [cfg["qpref"] + p["question"] for p in probes])
    rows = []
    # flat baseline
    flat = faiss.IndexFlatIP(pemb.shape[1]); flat.add(pemb)
    _, I = flat.search(qemb, max(KS))
    rows.append({"index": "flat", "nlist": "-", "nprobe": "-",
                 **recall([r.tolist() for r in I], probes, chunks, by_doc)})
    # IVF (guard: needs enough points)
    n = len(chunks); nlist = max(1, min(int(np.sqrt(n)), n // 4 or 1))
    if n >= 40:
        quant = faiss.IndexFlatIP(pemb.shape[1])
        ivf = faiss.IndexIVFFlat(quant, pemb.shape[1], nlist, faiss.METRIC_INNER_PRODUCT)
        ivf.train(pemb); ivf.add(pemb)
        for nprobe in [1, 4, 8, min(16, nlist)]:
            ivf.nprobe = nprobe
            _, I = ivf.search(qemb, max(KS))
            rows.append({"index": "ivf", "nlist": nlist, "nprobe": nprobe,
                         **recall([r.tolist() for r in I], probes, chunks, by_doc)})
    return rows

def study_hybrid(docs, probes):
    chunks, doc_of, by_doc, id2title = build_chunks(docs, *BASELINE)
    dense_rk, *_ = dense_rankings(chunks, doc_of, id2title, probes, DEFAULT_MODEL)
    bm_rk = bm25_rankings(chunks, probes)
    hyb_rk = [rrf([dense_rk[i], bm_rk[i]]) for i in range(len(probes))]
    return [
        {"method": "dense",  **recall(dense_rk, probes, chunks, by_doc)},
        {"method": "bm25",   **recall(bm_rk,   probes, chunks, by_doc)},
        {"method": "hybrid", **recall(hyb_rk,  probes, chunks, by_doc)},
    ]

def study_by_type(docs, probes):
    chunks, doc_of, by_doc, id2title = build_chunks(docs, *BASELINE)
    rk, *_ = dense_rankings(chunks, doc_of, id2title, probes, DEFAULT_MODEL)
    rows = []
    by_cat = defaultdict(list)
    for ranks, p in zip(rk, probes):
        by_cat[p.get("category", "other")].append((ranks, p))
    for cat, items in sorted(by_cat.items()):
        r = [it[0] for it in items]; ps = [it[1] for it in items]
        rows.append({"category": cat, "n": len(ps),
                     **recall(r, ps, chunks, by_doc)})
    return rows

def study_gate(docs, probes):
    """Top-1 similarity for probes whose gold WAS vs WAS NOT in top-5.
    A separating threshold is reusable as a Phase-2 quality gate."""
    chunks, doc_of, by_doc, id2title = build_chunks(docs, *BASELINE)
    rk, scores, *_ = dense_rankings(chunks, doc_of, id2title, probes, DEFAULT_MODEL)
    good, bad = [], []
    for ranks, sc, p in zip(rk, scores, probes):
        g = gold_ids(p, chunks, by_doc)
        if not g:
            continue
        (good if g & set(ranks[:5]) else bad).append(sc)
    def summ(x):
        return {} if not x else {"n": len(x), "mean": round(statistics.mean(x), 3),
                                 "min": round(min(x), 3), "max": round(max(x), 3)}
    return {"retrieved_top5": summ(good), "missed": summ(bad)}

def study_feasibility(docs, probes):
    chunks, doc_of, by_doc, id2title = build_chunks(docs, *BASELINE)
    m = get_model(DEFAULT_MODEL); cfg = MODELS[DEFAULT_MODEL]
    passages = make_passages(chunks, doc_of, id2title, cfg["ppref"], False)
    t0 = time.perf_counter(); pemb = embed(m, passages); enc_t = time.perf_counter() - t0
    index = faiss.IndexFlatIP(pemb.shape[1]); index.add(pemb)
    qemb = embed(m, [cfg["qpref"] + p["question"] for p in probes])
    lat = []
    for q in qemb:
        t0 = time.perf_counter(); index.search(q.reshape(1, -1), max(KS))
        lat.append((time.perf_counter() - t0) * 1000)
    sample_mb = sum(len(d["text"]) for d in docs) / 1e6
    scale = FULL_CORPUS_MB / sample_mb if sample_mb else 0
    return {
        "sample_mb": round(sample_mb, 3), "n_chunks": len(chunks),
        "encode_chunks_per_s": round(len(chunks) / enc_t, 1) if enc_t else None,
        "emb_mb": round(pemb.nbytes / 1e6, 1),
        "search_ms_p50": round(float(np.percentile(lat, 50)), 3),
        "search_ms_p95": round(float(np.percentile(lat, 95)), 3),
        "extrapolated_20MB": {
            "est_chunks": int(len(chunks) * scale),
            "est_emb_mb": round(pemb.nbytes / 1e6 * scale, 1),
            "est_encode_min": round(len(chunks) * scale / (len(chunks)/enc_t) / 60, 2) if enc_t else None,
        },
    }

# ---------- reporting ----------
def table(title, rows, cols):
    print(f"\n=== {title} ===")
    print("  ".join(f"{c:>11}" for c in cols))
    for r in rows:
        print("  ".join(f"{str(r.get(c, '')):>11}" for c in cols))

def main():
    docs = [json.loads(l) for l in CORPUS.open(encoding="utf-8")]
    probes = [json.loads(l) for l in PROBES.open(encoding="utf-8")]
    print(f"corpus={len(docs)} docs  probes={len(probes)}  baseline chunk={BASELINE}")

    res = {}
    res["size_sweep"]    = study_chunk_sweep(docs, probes, SIZE_SWEEP)
    res["overlap_sweep"] = study_chunk_sweep(docs, probes, OVERLAP_SWEEP)
    res["models"]        = study_models(docs, probes)
    res["prefix"]        = study_prefix(docs, probes)
    res["title_aug"]     = study_title_aug(docs, probes)
    res["index"]         = study_index(docs, probes)
    res["hybrid"]        = study_hybrid(docs, probes)
    res["by_type"]       = study_by_type(docs, probes)
    res["gate"]          = study_gate(docs, probes)
    res["feasibility"]   = study_feasibility(docs, probes)

    rc = [f"recall@{k}" for k in KS]
    table("1/2 SIZE sweep",    res["size_sweep"],    ["size","overlap","n_chunks","mean_tokens","p95_tokens","covered",*rc])
    table("2 OVERLAP sweep",   res["overlap_sweep"], ["size","overlap","n_chunks",*rc])
    table("3 MODEL bake-off",  res["models"],        ["model","dim","encode_s","emb_mb","covered",*rc])
    table("4 QUERY prefix",    res["prefix"],        ["setting",*rc])
    table("5 TITLE-aug",       res["title_aug"],     ["setting",*rc])
    table("6 INDEX flat/IVF",  res["index"],         ["index","nlist","nprobe",*rc])
    table("7 HYBRID dense+bm25",res["hybrid"],       ["method",*rc])
    table("8 BY question type",res["by_type"],       ["category","n",*rc])
    print("\n=== 9 GATE calibration (top-1 score) ==="); print(json.dumps(res["gate"], indent=2))
    print("\n=== 10 FEASIBILITY ==="); print(json.dumps(res["feasibility"], indent=2))

    json.dump(res, OUT.open("w"), indent=2)
    print(f"\nwrote {OUT.name}")

if __name__ == "__main__":
    main()

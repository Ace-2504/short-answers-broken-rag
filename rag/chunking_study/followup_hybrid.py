"""Follow-up: which dense model to pair with BM25 in the hybrid retriever?
Study 7 used bge as the dense half, but Study 3 showed bge is the weakest dense
model. Re-run hybrid (RRF of dense + BM25) with bge vs MiniLM-L6 vs e5-small as
the dense half, at the baseline chunk config. Reuses benchmark.py's functions."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from benchmark import (CORPUS, PROBES, BASELINE, KS,
                       build_chunks, dense_rankings, bm25_rankings, rrf, recall)

CANDIDATES = ["bge-small-en-v1.5", "minilm-l6", "e5-small-v2"]
OUT = pathlib.Path(__file__).parent / "results_followup.json"

def main():
    docs = [json.loads(l) for l in CORPUS.open(encoding="utf-8")]
    probes = [json.loads(l) for l in PROBES.open(encoding="utf-8")]
    chunks, doc_of, by_doc, id2title = build_chunks(docs, *BASELINE)
    bm = bm25_rankings(chunks, probes)

    rows = [{"method": "bm25-only", **recall(bm, probes, chunks, by_doc)}]
    for name in CANDIDATES:
        d, *_ = dense_rankings(chunks, doc_of, id2title, probes, name)
        hyb = [rrf([d[i], bm[i]]) for i in range(len(probes))]
        rows.append({"method": f"dense[{name}]",        **recall(d,  probes, chunks, by_doc)})
        rows.append({"method": f"hybrid[{name}+bm25]",  **recall(hyb, probes, chunks, by_doc)})

    rc = [f"recall@{k}" for k in KS]
    print(f"\n=== HYBRID x dense-model follow-up (chunk {BASELINE}, {len(probes)} probes) ===")
    print(f"{'method':>26}  " + "  ".join(f"{c:>9}" for c in rc))
    for r in rows:
        print(f"{r['method']:>26}  " + "  ".join(f"{r[c]:>9.3f}" for c in rc))
    json.dump(rows, OUT.open("w"), indent=2)
    print(f"\nwrote {OUT.name}")

if __name__ == "__main__":
    main()

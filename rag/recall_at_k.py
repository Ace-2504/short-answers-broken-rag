"""Phase 4: measure recall@k on the real held-out set (the required deliverable).

For each held-out question, is the chunk containing its gold `evidence` in the top-k?
Reported for dense / BM25 / hybrid, k in {1,3,5,10}, plus a by-source breakdown and
the recall@5 go/no-go gate for System C.

Output: rag/recall_at_k.json + printed table.
"""
import json, re, pathlib, sys
from collections import defaultdict
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from retrieve import Retriever

HERE = pathlib.Path(__file__).parent
HELDOUT = HERE.parent / "data" / "heldout.jsonl"
OUT = HERE / "recall_at_k.json"
KS = [1, 3, 5, 10]
METHODS = ["dense", "bm25", "hybrid"]

def toks(s):
    return set(re.findall(r"[a-z0-9]+", s.lower()))

def containment(a, b):
    ta = toks(a)
    return len(ta & toks(b)) / max(1, len(ta))

def main():
    r = Retriever()
    by_doc = defaultdict(list)
    for i, c in enumerate(r.chunks):
        by_doc[c["doc_id"]].append(i)
    heldout = [json.loads(l) for l in HELDOUT.open(encoding="utf-8")]

    hits = {m: {k: 0 for k in KS} for m in METHODS}
    src_hits = defaultdict(lambda: {"n": 0, **{k: 0 for k in KS}})
    covered = 0
    for item in heldout:
        # gold chunks: in the item's source doc, containing >=80% of the evidence tokens
        gold = {i for i in by_doc.get(item["doc_id"], [])
                if containment(item["evidence"], r.chunks[i]["text"]) >= 0.8}
        if not gold:
            continue                      # evidence not in any single chunk -> not scorable
        covered += 1
        ranked = {m: r.rank_ids(item["question"], max(KS), m) for m in METHODS}
        for m in METHODS:
            for k in KS:
                if gold & set(ranked[m][:k]):
                    hits[m][k] += 1
        s = src_hits[item.get("source", "?")]
        s["n"] += 1
        for k in KS:
            if gold & set(ranked["hybrid"][:k]):
                s[k] += 1

    def rec(h):
        return {f"recall@{k}": round(h[k] / covered, 3) if covered else 0.0 for k in KS}
    report = {"n_heldout": len(heldout), "scorable": covered,
              "coverage": round(covered / len(heldout), 3),
              "n_chunks": r.meta["n_chunks"],
              "recall": {m: rec(hits[m]) for m in METHODS},
              "hybrid_by_source": {s: {"n": v["n"],
                                       **{f"recall@{k}": round(v[k]/v["n"], 3) if v["n"] else 0.0 for k in KS}}
                                   for s, v in sorted(src_hits.items())}}
    json.dump(report, OUT.open("w"), indent=2)

    print(f"\nheld-out {len(heldout)} · scorable {covered} (coverage {report['coverage']}) "
          f"· {r.meta['n_chunks']} chunks\n")
    print(f"{'method':>8} " + " ".join(f"r@{k:<3}" for k in KS))
    print("-" * 34)
    for m in METHODS:
        print(f"{m:>8} " + " ".join(f"{report['recall'][m][f'recall@{k}']:.2f}" for k in KS))
    print("\nhybrid recall@5 GATE:",
          f"{report['recall']['hybrid']['recall@5']:.2f}",
          "-> System C viable" if report['recall']['hybrid']['recall@5'] >= 0.6 else "-> WEAK, investigate")
    print("\nby source (hybrid):")
    for s, v in report["hybrid_by_source"].items():
        print(f"  {s:10s} n={v['n']:2d}  " + " ".join(f"r@{k}={v[f'recall@{k}']:.2f}" for k in KS))
    print(f"\nwrote {OUT.name}")

if __name__ == "__main__":
    main()

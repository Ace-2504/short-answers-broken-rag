"""Phase 5 step 3: aggregate verdicts into the leaderboard + paired significance.

Per-system mean +/- SE and per-component breakdown; paired bootstrap 95% CI + t-test +
Wilcoxon on A-vs-B and B-vs-C; and the 3 biggest A/C disagreements quoted.

Output: eval/leaderboard.json + printed table.
"""
import json, pathlib, statistics
import numpy as np
from scipy import stats

HERE = pathlib.Path(__file__).parent
RESP = HERE / "responses.json"
VERD = HERE / "verdicts.json"
OUT = HERE / "leaderboard.json"
SYSTEMS = ["A", "B", "C"]
COMPS = ["correctness", "completeness", "groundedness", "clarity"]
NAME = {"A": "base (closed)", "B": "fine-tune (closed)", "C": "fine-tune + retrieval"}

def bootstrap_ci(diffs, n=10000, seed=20260803):
    rng = np.random.default_rng(seed)
    d = np.array(diffs)
    means = rng.choice(d, size=(n, len(d)), replace=True).mean(axis=1)
    return round(float(d.mean()), 3), round(float(np.percentile(means, 2.5)), 3), round(float(np.percentile(means, 97.5)), 3)

def paired(x, y):
    dx = np.array(x) - np.array(y)                     # x - y per item
    mean, lo, hi = bootstrap_ci(dx.tolist())
    t = stats.ttest_rel(x, y)
    try:
        w = stats.wilcoxon(x, y)
        wp = round(float(w.pvalue), 4)
    except Exception:
        wp = None
    sig = "significant" if (lo > 0 or hi < 0) else "not separated"
    return {"mean_diff": mean, "bootstrap_95CI": [lo, hi], "t": round(float(t.statistic), 3),
            "t_p": round(float(t.pvalue), 4), "wilcoxon_p": wp, "verdict": sig}

def main():
    verd = json.load(VERD.open(encoding="utf-8"))
    resp = json.load(RESP.open(encoding="utf-8"))
    ids = [q for q in verd if all(s in verd[q] for s in SYSTEMS)]
    totals = {s: [verd[q][s]["total"] for q in ids] for s in SYSTEMS}
    n = len(ids)

    per_system = {}
    for s in SYSTEMS:
        arr = totals[s]
        per_system[s] = {
            "name": NAME[s], "n": n,
            "mean": round(statistics.mean(arr), 3),
            "se": round(statistics.pstdev(arr) / (n ** 0.5), 3),
            "components": {c: round(statistics.mean([verd[q][s][c] for q in ids]), 2) for c in COMPS},
        }

    comparisons = {"A_vs_B": paired(totals["B"], totals["A"]),   # B - A
                   "B_vs_C": paired(totals["C"], totals["B"])}   # C - B

    # 3 biggest C-vs-A disagreements
    gaps = sorted(ids, key=lambda q: abs(verd[q]["C"]["total"] - verd[q]["A"]["total"]), reverse=True)
    disagreements = []
    for q in gaps[:3]:
        disagreements.append({
            "id": q, "question": resp[q]["question"], "gold": resp[q]["gold"],
            "scores": {s: verd[q][s]["total"] for s in SYSTEMS},
            "answers": {s: resp[q][s] for s in SYSTEMS}})

    report = {"n_items": n, "per_system": per_system, "comparisons": comparisons,
              "disagreements": disagreements}
    json.dump(report, OUT.open("w"), indent=2)

    print(f"\n=== LEADERBOARD (n={n}, mean score /10 +/- SE) ===")
    for s in SYSTEMS:
        p = per_system[s]
        print(f"  {s} {p['name']:<24} {p['mean']:.2f} +/- {p['se']:.2f}   "
              + " ".join(f"{c[:4]}={p['components'][c]}" for c in COMPS))
    print("\n=== paired significance ===")
    for k, c in comparisons.items():
        print(f"  {k}: diff {c['mean_diff']:+.2f}  95%CI {c['bootstrap_95CI']}  "
              f"t={c['t']} (p={c['t_p']})  W_p={c['wilcoxon_p']}  -> {c['verdict']}")
    print(f"\nwrote {OUT.name} (+ {len(disagreements)} disagreement examples)")

if __name__ == "__main__":
    main()

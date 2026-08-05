"""Pilot step 3: VALIDATE gauntlet in MEASURE-FIRST mode — report the distributions
that let us pick G1-G5 thresholds from real data (no hard gating, nothing dropped).

Reads pilot_raw_qa.jsonl (+ pilot_heldout_probe.jsonl for decontam). Writes pilot_report.json.
"""
import json, re, pathlib, statistics
import numpy as np
from sentence_transformers import SentenceTransformer

HERE = pathlib.Path(__file__).parent
QA = HERE / "pilot_raw_qa.jsonl"
HO = HERE / "pilot_heldout_probe.jsonl"
OUT = HERE / "pilot_report.json"

def toks(s):
    return set(re.findall(r"[a-z0-9]+", s.lower()))

def containment(a, b):           # fraction of a's tokens present in b
    ta = toks(a)
    return len(ta & toks(b)) / max(1, len(ta))

def q(vals):
    vals = sorted(vals)
    if not vals:
        return {}
    return {"n": len(vals), "mean": round(statistics.mean(vals), 3),
            "p10": round(vals[len(vals)//10], 3), "median": round(statistics.median(vals), 3),
            "p90": round(vals[9*len(vals)//10], 3)}

def main():
    pairs = [json.loads(l) for l in QA.open(encoding="utf-8")]
    n = len(pairs)
    rep = {"n_raw_pairs": n}

    # --- yield ---
    by_chunk = {}
    for p in pairs:
        by_chunk.setdefault(p["chunk_id"], 0)
        by_chunk[p["chunk_id"]] += 1
    rep["yield_per_chunk"] = round(n / max(1, len(by_chunk)), 2)

    # --- G1 format ---
    qlen = [len(p["question"]) for p in pairs]
    alen = [len(p["answer"]) for p in pairs]
    rep["G1_question_chars"] = q(qlen)
    rep["G1_answer_chars"] = q(alen)
    rep["G1_empty"] = sum(1 for p in pairs if not p["question"].strip() or not p["answer"].strip())
    rep["G1_no_terminal_punct"] = sum(1 for p in pairs if p["answer"] and p["answer"][-1] not in ".!?\"')")

    # --- G2 grounding ---
    ev_in_pass = [1.0 if p["evidence"] and p["evidence"] in p["passage"]
                  else containment(p["evidence"], p["passage"]) for p in pairs]
    ans_in_pass = [containment(p["answer"], p["passage"]) for p in pairs]
    ans_in_ev = [containment(p["answer"], p["evidence"]) for p in pairs if p["evidence"]]
    rep["G2_evidence_in_passage"] = q(ev_in_pass)
    rep["G2_answer_in_passage_overlap"] = q(ans_in_pass)
    rep["G2_answer_in_evidence_overlap"] = q(ans_in_ev)
    rep["G2_weakly_grounded_lt_0.35"] = sum(1 for x in ans_in_pass if x < 0.35)

    # --- #8 low-value pair signals ---
    searched = sum(1 for p in pairs if re.search(r"search(ed)? by|can search", p["question"], re.I))
    statq = sum(1 for p in pairs if re.search(r"\b(atk|def|attack|level|rank|attribute|type)\b", p["question"], re.I))
    verbatim = sum(1 for x in ans_in_pass if x > 0.9)      # answer ≈ copied from passage
    rep["lowvalue_searchedby_Q"] = searched
    rep["lowvalue_stat_lookup_Q"] = statq
    rep["lowvalue_verbatim_answer_gt0.9"] = verbatim

    # --- G5 balance ---
    rep["G5_qtype"] = {}
    for p in pairs:
        rep["G5_qtype"][p["qtype"]] = rep["G5_qtype"].get(p["qtype"], 0) + 1
    rep["G5_difficulty"] = {}
    for p in pairs:
        d = p.get("difficulty", "")
        rep["G5_difficulty"][d] = rep["G5_difficulty"].get(d, 0) + 1

    # --- embeddings for G3 dedup + G4 decontam ---
    model = SentenceTransformer("all-MiniLM-L6-v2")
    qemb = model.encode([p["question"] for p in pairs], normalize_embeddings=True).astype("float32")
    sims = qemb @ qemb.T
    np.fill_diagonal(sims, 0.0)
    rep["G3_near_dup_pairs"] = {f">={t}": int((sims >= t).sum() // 2) for t in [0.85, 0.90, 0.92, 0.95]}

    if HO.exists():
        ho = [json.loads(l) for l in HO.open(encoding="utf-8")]
        if ho:
            hoemb = model.encode([h["question"] for h in ho], normalize_embeddings=True).astype("float32")
            maxsim = (qemb @ hoemb.T).max(axis=1)
            rep["G4_decontam_max_heldout_sim"] = q(list(map(float, maxsim)))
            rep["G4_collisions"] = {f">={t}": int((maxsim >= t).sum()) for t in [0.85, 0.90, 0.95]}

    json.dump(rep, OUT.open("w"), indent=2)
    print(json.dumps(rep, indent=2))
    print(f"\nwrote {OUT.name}  (measure-first — nothing dropped)")

if __name__ == "__main__":
    main()

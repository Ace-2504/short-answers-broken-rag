"""Phase-2 step 3: the VALIDATE gauntlet (with the LLM judge). Turns raw_qa.jsonl into
the clean SFT set data/train.jsonl (chat/messages format) and reports the attrition funnel.

Gates: G1 format -> G2 judge grounding/correctness (resumable) -> G3 near-dup dedup ->
G4 decontaminate vs held-out -> G5 tag (no cap). Nothing here calls the teacher except G2.

Outputs: data/generate/verdicts.jsonl (judge cache), data/train.jsonl, data/generate/gauntlet_report.json
"""
import json, time, pathlib, sys, collections
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import gemini, call_json, containment, load_ids, load_jsonl

HERE = pathlib.Path(__file__).parent
RAW = HERE / "raw_qa.jsonl"
VERD = HERE / "verdicts.jsonl"
HELDOUT = HERE.parent / "heldout.jsonl"
TRAIN = HERE.parent / "train.jsonl"
REPORT = HERE / "gauntlet_report.json"

Q_MIN, Q_MAX, A_MIN, A_MAX = 15, 300, 3, 1200      # G1
PARTIAL_KEEP_OVERLAP = 0.6                         # G2: keep 'partial' only if well-grounded
DEDUP_COS = 0.92                                   # G3
DECON_COS = 0.90                                   # G4
SYS = "You are a helpful Yu-Gi-Oh expert. Answer the question using the rules and rulings you know."

JUDGE_PROMPT = (
    "You are grading ONE Yu-Gi-Oh training pair for GROUNDING and CORRECTNESS. Using ONLY the "
    "passage as ground truth, decide whether the ANSWER correctly and completely answers the "
    "QUESTION and is fully supported by the passage (no invented facts, no outside knowledge, not "
    "contradicted by the passage). A 'not stated in the passage' answer is acceptable ONLY if the "
    "passage genuinely lacks the answer.\n"
    'Return ONLY compact JSON: {"verdict":"yes"|"partial"|"no","reason":"<short>"}\n'
    "  yes = correct and fully supported by the passage\n"
    "  partial = mostly right but incomplete, or reaches slightly beyond the passage\n"
    "  no = wrong, unsupported, or contradicted by the passage\n\n"
)

def g1_ok(p):
    return (p["question"].strip() and p["answer"].strip()
            and Q_MIN <= len(p["question"]) <= Q_MAX and A_MIN <= len(p["answer"]) <= A_MAX)

def main():
    pairs = load_jsonl(RAW)
    funnel = {"raw": len(pairs)}
    g1 = [p for p in pairs if g1_ok(p)]
    funnel["after_G1_format"] = len(g1)

    # --- G2 judge (resumable) ---
    done = load_ids(VERD, "qid")
    cli, model = gemini()
    todo = [p for p in g1 if p["qid"] not in done]
    print(f"judging: {len(todo)} pairs to do ({len(done)} cached)")
    with VERD.open("a", encoding="utf-8") as f:
        for p in todo:
            prompt = JUDGE_PROMPT + f"PASSAGE:\n{p['passage']}\n\nQUESTION: {p['question']}\nANSWER: {p['answer']}\n"
            try:
                v = call_json(cli, model, prompt)
                verdict = str(v.get("verdict", "no")).lower().strip()
            except Exception as e:
                print(f"  judge skip {p['qid']}: {e}", file=sys.stderr); time.sleep(1); continue
            f.write(json.dumps({"qid": p["qid"], "verdict": verdict,
                                "overlap": round(containment(p["answer"], p["passage"]), 3)},
                               ensure_ascii=False) + "\n")
            f.flush(); time.sleep(0.25)

    verd = {v["qid"]: v for v in load_jsonl(VERD)}
    def keep(p):
        v = verd.get(p["qid"])
        if not v:
            return False
        if v["verdict"] == "yes":
            return True
        if v["verdict"] == "partial" and v.get("overlap", 0) >= PARTIAL_KEEP_OVERLAP:
            return True
        return False
    g2 = [p for p in g1 if keep(p)]
    funnel["after_G2_judge"] = len(g2)
    funnel["G2_verdicts"] = dict(collections.Counter(verd[p["qid"]]["verdict"] for p in g1 if p["qid"] in verd))

    # --- G3 dedup + G4 decontam (embeddings) ---
    from sentence_transformers import SentenceTransformer
    emb_model = SentenceTransformer("all-MiniLM-L6-v2")
    qemb = emb_model.encode([p["question"] for p in g2], normalize_embeddings=True).astype("float32")
    sims = qemb @ qemb.T
    keep_idx, kept_vecs = [], []
    for i in range(len(g2)):
        if kept_vecs and max(sims[i][j] for j in keep_idx) >= DEDUP_COS:
            continue
        keep_idx.append(i); kept_vecs.append(i)
    g3 = [g2[i] for i in keep_idx]
    funnel["after_G3_dedup"] = len(g3)

    ho = load_jsonl(HELDOUT)
    if ho:
        hoemb = emb_model.encode([h["question"] for h in ho], normalize_embeddings=True).astype("float32")
        g3emb = emb_model.encode([p["question"] for p in g3], normalize_embeddings=True).astype("float32")
        maxsim = (g3emb @ hoemb.T).max(axis=1)
        g4 = [p for p, s in zip(g3, maxsim) if s < DECON_COS]
    else:
        g4 = g3
    funnel["after_G4_decontam"] = len(g4)

    # --- G5 tag distribution (no cap) ---
    funnel["G5_qtype"] = dict(collections.Counter(p["qtype"] for p in g4))
    funnel["G5_difficulty"] = dict(collections.Counter(p.get("difficulty", "") for p in g4))

    # --- render chat/messages JSONL ---
    with TRAIN.open("w", encoding="utf-8") as f:
        for p in g4:
            f.write(json.dumps({
                "messages": [{"role": "system", "content": SYS},
                             {"role": "user", "content": p["question"]},
                             {"role": "assistant", "content": p["answer"]}],
                "meta": {"qtype": p["qtype"], "difficulty": p.get("difficulty", ""),
                         "source": p["source"], "chunk_id": p["chunk_id"],
                         "evidence": p["evidence"]}}, ensure_ascii=False) + "\n")

    funnel["FINAL_train_pairs"] = len(g4)
    json.dump(funnel, REPORT.open("w"), indent=2)
    print(json.dumps(funnel, indent=2))
    print(f"\nwrote {TRAIN} ({len(g4)} pairs) and {REPORT.name}")

if __name__ == "__main__":
    main()

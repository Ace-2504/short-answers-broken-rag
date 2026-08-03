"""Phase 5 step 2: grade every answer with a reference-grounded, blind, pointwise judge.

The judge sees ONLY question + gold + evidence + one answer (no system name). Rubric
sums to 10: correctness 0-5, completeness 0-2, groundedness 0-2 (->0 on invented
figures/citations), clarity 0-1; a correct refusal must beat a confident wrong answer.

Requires GEMINI_API_KEY. Idempotent: skips (id, system) pairs already judged.
Output: eval/verdicts.json  { id: { A|B|C: {correctness,completeness,groundedness,clarity,total,note} } }
"""
import json, os, sys, time, random, pathlib

HERE = pathlib.Path(__file__).parent
RESP = HERE / "responses.json"
VERD = HERE / "verdicts.json"
SYSTEMS = ["A", "B", "C"]

JUDGE = (
    "You are grading ONE answer to a Yu-Gi-Oh question. Use ONLY the gold answer and its verbatim "
    "evidence as ground truth (do not use outside knowledge). Score with this rubric (total 10):\n"
    "- correctness (0-5): factual agreement with the gold answer\n"
    "- completeness (0-2): covers the key points of the gold\n"
    "- groundedness (0-2): consistent with the evidence; SET TO 0 if it invents a citation, figure, "
    "or card detail not supported by the evidence\n"
    "- clarity (0-1): clear and well-formed\n"
    "A correct refusal ('the information is not available') must score HIGHER than a confident wrong "
    "answer. Output ONLY compact JSON: "
    '{"correctness":int,"completeness":int,"groundedness":int,"clarity":int,"note":"<short>"}\n\n'
)

def judge_one(cli, model, question, gold, evidence, answer):
    prompt = JUDGE + f"QUESTION: {question}\nGOLD: {gold}\nEVIDENCE: {evidence}\nANSWER: {answer}\n"
    resp = cli.models.generate_content(model=model, contents=prompt)
    txt = resp.text.strip().strip("`")
    if txt.lower().startswith("json"):
        txt = txt[4:].strip()
    o = json.loads(txt)
    for k in ("correctness", "completeness", "groundedness", "clarity"):
        o[k] = int(o.get(k, 0))
    o["total"] = o["correctness"] + o["completeness"] + o["groundedness"] + o["clarity"]
    return o

def main():
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        sys.exit("Set GEMINI_API_KEY first.")
    from google import genai
    cli = genai.Client(api_key=key)
    model = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

    responses = json.load(RESP.open(encoding="utf-8"))
    verdicts = json.load(VERD.open(encoding="utf-8")) if VERD.exists() else {}
    ids = list(responses.keys())
    random.Random(20260803).shuffle(ids)          # judge in random order (extra blindness)
    for qid in ids:
        rec = responses[qid]
        v = verdicts.get(qid, {})
        for s in SYSTEMS:
            if s in v:
                continue
            try:
                v[s] = judge_one(cli, model, rec["question"], rec["gold"], rec["evidence"], rec[s])
            except Exception as e:
                print(f"  judge skip {qid}/{s}: {e}", file=sys.stderr); time.sleep(1.5); continue
            time.sleep(0.25)
        verdicts[qid] = v
        json.dump(verdicts, VERD.open("w", encoding="utf-8"), ensure_ascii=False, indent=1)
    done = sum(len(v) for v in verdicts.values())
    print(f"judged {done} answers across {len(verdicts)} items -> {VERD.name}")

if __name__ == "__main__":
    main()

"""Phase 5 step 1: run systems A / B / C over the 60 held-out questions.

A = base (use_base), B = fine-tune closed-book, C = fine-tune + top-5 retrieval.
All via the already-running servers (no new model load — resource-safe). Greedy
decoding (temperature 0). Idempotent: skips items/systems already answered.

Output: eval/responses.json  { id: {question, gold, evidence, A, B, C, context} }
"""
import json, pathlib, requests

HERE = pathlib.Path(__file__).parent
HELDOUT = HERE.parent / "data" / "heldout.jsonl"
RESP = HERE / "responses.json"
GEN = "http://localhost:8100/generate"      # fine-tune server (use_base toggles System A)
RET = "http://localhost:8200/retrieve"      # retriever
K = 5

def gen(question, use_base=False, context=None):
    r = requests.post(GEN, json={"question": question, "use_base": use_base, "context": context,
                                 "temperature": 0.0, "max_new_tokens": 220}, timeout=180)
    r.raise_for_status()
    return r.json()["answer"]

def retrieve_context(question):
    ps = requests.post(RET, json={"question": question, "k": K}, timeout=60).json()["passages"]
    return "\n\n".join(f"[{p['title']}] {p['text']}" for p in ps)

def main():
    heldout = [json.loads(l) for l in HELDOUT.open(encoding="utf-8")]
    responses = json.load(RESP.open(encoding="utf-8")) if RESP.exists() else {}
    for item in heldout:
        qid = item["id"]
        rec = responses.get(qid, {"question": item["question"], "gold": item["gold"],
                                  "evidence": item["evidence"]})
        changed = False
        if "A" not in rec:
            rec["A"] = gen(item["question"], use_base=True); changed = True
        if "B" not in rec:
            rec["B"] = gen(item["question"], use_base=False); changed = True
        if "C" not in rec:
            ctx = retrieve_context(item["question"])
            rec["context"] = ctx
            rec["C"] = gen(item["question"], use_base=False, context=ctx); changed = True
        responses[qid] = rec
        if changed:
            json.dump(responses, RESP.open("w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"  {qid}: A/B/C done")
    print(f"\nresponses for {len(responses)} items -> {RESP.name}")

if __name__ == "__main__":
    main()

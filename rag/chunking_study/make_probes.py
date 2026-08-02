"""
Build retrieval probes from the sample corpus. For each probe we pick a real
sentence (the 'gold' answer text) and ask Gemini flash-lite to write a natural
question it answers -- exactly the shape of the Phase-2 QA pipeline. The probe's
job in the benchmark: does the chunk containing this gold sentence get retrieved?

Requires GEMINI_API_KEY. Model via GEMINI_MODEL (default gemini-3.1-flash-lite).
Output: rag/chunking_study/probes.jsonl  ({qid, question, gold_sentence, doc_id})
"""
import json, os, re, random, time, pathlib, sys

HERE = pathlib.Path(__file__).parent
CORPUS = HERE / "sample_corpus.jsonl"
OUT = HERE / "probes.jsonl"
N_PROBES = 60
SEED = 20260801

SENT_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z"\'])')

def good_sentence(s):
    s = s.strip()
    if not (60 <= len(s) <= 300):          # substantive but chunk-fittable
        return False
    if s.startswith("=") or s.endswith(":"):
        return False
    letters = sum(c.isalpha() for c in s)
    return letters / len(s) > 0.6           # mostly prose, not a stat line

CATEGORIES = ["definition", "interaction", "timing", "lore", "other"]

def gen_probe(client, model, sentence):
    """Return (question, category). One call produces both to save API calls."""
    prompt = (
        "From this Yu-Gi-Oh wiki sentence, produce a retrieval-test probe.\n"
        "Write ONE natural question a player might ask that this sentence answers, "
        "then classify it into exactly one category:\n"
        "  definition  - what something is / a static property\n"
        "  interaction - how cards/effects interact, combos, what a card can do\n"
        "  timing      - when an effect activates, chains, phases, missing timing\n"
        "  lore        - story / flavor / character background\n"
        "  other       - none of the above\n"
        "Do not refer to 'the sentence'. Output ONLY compact JSON: "
        '{"question": "...", "category": "..."}\n\n'
        f"Sentence: {sentence}"
    )
    resp = client.models.generate_content(model=model, contents=prompt)
    txt = resp.text.strip().strip("`")
    if txt.lower().startswith("json"):
        txt = txt[4:].strip()
    try:
        obj = json.loads(txt)
        q = str(obj.get("question", "")).strip()
        cat = str(obj.get("category", "other")).strip().lower()
    except Exception:
        q, cat = txt.split("\n")[0].strip(), "other"
    if cat not in CATEGORIES:
        cat = "other"
    return q, cat

def main():
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        sys.exit("Set GEMINI_API_KEY first (this step calls Gemini flash-lite).")
    from google import genai
    client = genai.Client(api_key=key)
    model = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

    docs = [json.loads(l) for l in CORPUS.open(encoding="utf-8")]
    # collect (doc_id, sentence) candidates
    cands = []
    for d in docs:
        for s in SENT_SPLIT.split(d["text"].replace("\n", " ")):
            if good_sentence(s):
                cands.append((d["doc_id"], s.strip()))
    random.Random(SEED).shuffle(cands)

    written = 0
    with OUT.open("w", encoding="utf-8") as f:
        for doc_id, sent in cands:
            if written >= N_PROBES:
                break
            try:
                q, cat = gen_probe(client, model, sent)
            except Exception as e:
                print(f"  skip (api error): {e}", file=sys.stderr)
                time.sleep(2)
                continue
            if not q or len(q) < 8:
                continue
            f.write(json.dumps(
                {"qid": f"q-{written:03d}", "question": q, "category": cat,
                 "gold_sentence": sent, "doc_id": doc_id},
                ensure_ascii=False) + "\n")
            written += 1
            print(f"  q-{written:03d} [{cat:11s}] {q}")
            time.sleep(0.3)
    print(f"\nWrote {written} probes -> {OUT.name}  (model={model})")

if __name__ == "__main__":
    main()

"""Pilot step 2: teacher (Gemini flash-lite) writes GROUNDED QA per chunk — answers
stated only in the passage, each with a verbatim evidence span, a question-type tag,
and a difficulty tag. Also generates a small held-out probe from held-out-split pages.

Requires GEMINI_API_KEY. Model via GEMINI_MODEL (default gemini-3.1-flash-lite).
Outputs: pilot_raw_qa.jsonl  ({qid, chunk_id, source, question, answer, evidence, qtype, difficulty, passage})
         pilot_heldout_probe.jsonl  ({id, question, gold, evidence, doc_id})
"""
import json, os, re, time, random, pathlib, sys

HERE = pathlib.Path(__file__).parent
CHUNKS = HERE / "pilot_chunks.jsonl"
CORPUS = pathlib.Path(__file__).parents[2] / "data" / "corpus" / "corpus_clean.jsonl"
OUT_QA = HERE / "pilot_raw_qa.jsonl"
OUT_HO = HERE / "pilot_heldout_probe.jsonl"
SEED = 20260801
PAIRS_PER_CHUNK = 3
HELDOUT_PROBE_N = 15

QTYPES = ["definition", "interaction", "timing", "lore", "other"]
GEN_PROMPT = (
    "You are building grounded training data from a Yu-Gi-Oh passage. Write up to "
    f"{PAIRS_PER_CHUNK} diverse question-answer pairs whose answers are stated ONLY in the passage. "
    "Prefer reasoning questions (interactions, timing, rulings) over trivial verbatim recall. "
    "If the passage cannot support a good question, return fewer. For each pair give:\n"
    '  question, answer, evidence (a verbatim sentence/clause from the passage that proves the '
    "answer), qtype (one of: definition, interaction, timing, lore, other), difficulty "
    "(lookup or multistep).\n"
    'Output ONLY a compact JSON list: [{"question":...,"answer":...,"evidence":...,'
    '"qtype":...,"difficulty":...}, ...]\n\nPassage:\n'
)
HO_PROMPT = (
    "From this Yu-Gi-Oh passage, write ONE clear question with its correct answer and the verbatim "
    "evidence sentence(s) from the passage that prove it. Output ONLY compact JSON: "
    '{"question":...,"gold":...,"evidence":...}\n\nPassage:\n'
)

def client():
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        sys.exit("Set GEMINI_API_KEY first.")
    from google import genai
    return genai.Client(api_key=key), os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

def call_json(cli, model, prompt):
    resp = cli.models.generate_content(model=model, contents=prompt)
    txt = resp.text.strip().strip("`")
    if txt.lower().startswith("json"):
        txt = txt[4:].strip()
    return json.loads(txt)

def gen_qa():
    cli, model = client()
    chunks = [json.loads(l) for l in CHUNKS.open(encoding="utf-8")]
    n = 0
    with OUT_QA.open("w", encoding="utf-8") as f:
        for c in chunks:
            try:
                pairs = call_json(cli, model, GEN_PROMPT + c["text"])
            except Exception as e:
                print(f"  gen skip {c['chunk_id']}: {e}", file=sys.stderr); time.sleep(1); continue
            for p in (pairs if isinstance(pairs, list) else []):
                q = str(p.get("question", "")).strip()
                a = str(p.get("answer", "")).strip()
                if not q or not a:
                    continue
                qt = str(p.get("qtype", "other")).lower().strip()
                f.write(json.dumps({
                    "qid": f"pq-{n:05d}", "chunk_id": c["chunk_id"], "source": c["source"],
                    "question": q, "answer": a, "evidence": str(p.get("evidence", "")).strip(),
                    "qtype": qt if qt in QTYPES else "other",
                    "difficulty": str(p.get("difficulty", "")).lower().strip(),
                    "passage": c["text"]}, ensure_ascii=False) + "\n")
                n += 1
            time.sleep(0.25)
    print(f"wrote {OUT_QA.name}: {n} raw pairs from {len(chunks)} chunks")

def gen_heldout():
    cli, model = client()
    docs = [json.loads(l) for l in CORPUS.open(encoding="utf-8")]
    heldout = [d for d in docs if d.get("split") == "heldout" and len(d["text"]) > 400]
    pick = random.Random(SEED).sample(heldout, min(HELDOUT_PROBE_N, len(heldout)))
    n = 0
    with OUT_HO.open("w", encoding="utf-8") as f:
        for d in pick:
            try:
                o = call_json(cli, model, HO_PROMPT + d["text"][:1200])
            except Exception as e:
                print(f"  ho skip: {e}", file=sys.stderr); time.sleep(1); continue
            if o.get("question") and o.get("gold"):
                f.write(json.dumps({"id": f"qa-{n:03d}", "question": o["question"].strip(),
                                    "gold": str(o["gold"]).strip(), "evidence": str(o.get("evidence","")).strip(),
                                    "doc_id": d["doc_id"]}, ensure_ascii=False) + "\n")
                n += 1
            time.sleep(0.25)
    print(f"wrote {OUT_HO.name}: {n} held-out probe items")

if __name__ == "__main__":
    gen_qa()
    gen_heldout()

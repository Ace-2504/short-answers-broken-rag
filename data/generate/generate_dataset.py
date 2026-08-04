"""Phase-2 step 1: chunk train-split docs (1000/150) and generate grounded QA with
the proven pilot prompt. Resumable — skips chunks already generated.

Targets ~1,200 chunks (stratified, on-target biased) -> ~2,800 raw pairs, for ≥2,000
survivors after the judge gauntlet.

Outputs: data/generate/train_chunks.jsonl, data/generate/raw_qa.jsonl
"""
import json, time, random, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import gemini, call_json, chunk, load_ids, load_jsonl

HERE = pathlib.Path(__file__).parent
CORPUS = HERE.parent / "corpus" / "corpus_clean.jsonl"
CHUNKS = HERE / "train_chunks.jsonl"
RAW = HERE / "raw_qa.jsonl"
SEED = 20260801
PAIRS_PER_CHUNK = 3
# stratified chunk budget (on-target biased), ~1,200 chunks
BUDGET = {"rulings": 450, "tips": 280, "archetype": 220, "mechanics": 100, "cardfacts": 150}

GEN_PROMPT = (
    "You are building grounded training data from a Yu-Gi-Oh passage. Write up to "
    f"{PAIRS_PER_CHUNK} diverse question-answer pairs whose answers are stated ONLY in the passage. "
    "Prefer reasoning questions (interactions, timing, rulings) over trivial verbatim recall. "
    "If the passage cannot support a good question, return fewer. For each pair give:\n"
    '  question, answer, evidence (a verbatim sentence/clause from the passage that proves the '
    "answer), qtype (definition/interaction/timing/lore/other), difficulty (lookup or multistep).\n"
    'Output ONLY a compact JSON list: [{"question":...,"answer":...,"evidence":...,'
    '"qtype":...,"difficulty":...}, ...]\n\nPassage:\n'
)

def build_chunks():
    if CHUNKS.exists():
        return load_jsonl(CHUNKS)
    docs = [json.loads(l) for l in CORPUS.open(encoding="utf-8") if json.loads(l).get("split") == "train"]
    by_src = {}
    for d in docs:
        by_src.setdefault(d["source"], []).append(d)
    rng = random.Random(SEED)
    rows = []
    for src, cap in BUDGET.items():
        pool = by_src.get(src, [])
        rng.shuffle(pool)
        picked = []
        for d in pool:                       # first chunk of each doc until cap
            picked.append((d["doc_id"], d["title"], chunk(d["text"])[0]))
            if len(picked) >= cap:
                break
        for j, (doc_id, title, text) in enumerate(picked):
            rows.append({"chunk_id": f"tc-{src}-{j:04d}", "doc_id": doc_id,
                         "source": src, "title": title, "text": text})
    with CHUNKS.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"built {CHUNKS.name}: {len(rows)} chunks {{"
          + ', '.join(f'{s}:{min(c,len(by_src.get(s,[])))}' for s, c in BUDGET.items()) + "}")
    return rows

def main():
    chunks = build_chunks()
    done = load_ids(RAW, "chunk_id")            # chunks already generated
    cli, model = gemini()
    todo = [c for c in chunks if c["chunk_id"] not in done]
    print(f"generating: {len(todo)} chunks to do ({len(done)} already done)")
    n = 0
    with RAW.open("a", encoding="utf-8") as f:
        for c in todo:
            try:
                pairs = call_json(cli, model, GEN_PROMPT + c["text"])
            except Exception as e:
                print(f"  skip {c['chunk_id']}: {e}", file=sys.stderr); time.sleep(1); continue
            for j, p in enumerate(pairs if isinstance(pairs, list) else []):
                q, a = str(p.get("question", "")).strip(), str(p.get("answer", "")).strip()
                if not q or not a:
                    continue
                qt = str(p.get("qtype", "other")).lower().strip()
                f.write(json.dumps({
                    "qid": f"q-{c['chunk_id']}-{j}", "chunk_id": c["chunk_id"], "source": c["source"],
                    "question": q, "answer": a, "evidence": str(p.get("evidence", "")).strip(),
                    "qtype": qt, "difficulty": str(p.get("difficulty", "")).lower().strip(),
                    "passage": c["text"]}, ensure_ascii=False) + "\n")
                n += 1
            f.flush()
            time.sleep(0.25)
    total = len(load_jsonl(RAW))
    print(f"generated {n} new pairs this run; raw_qa.jsonl now has {total} pairs")

if __name__ == "__main__":
    main()

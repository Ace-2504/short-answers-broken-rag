"""Pilot step 1: chunk a small, stratified sample of TRAIN-split docs at 1000/150
(the locked retriever setting). Held-out docs are excluded — they never feed QA gen.

Output: finetune/pilot/pilot_chunks.jsonl  ({chunk_id, doc_id, source, title, text})
"""
import json, random, pathlib

CORPUS = pathlib.Path(__file__).parents[2] / "data" / "corpus" / "corpus_clean.jsonl"
OUT = pathlib.Path(__file__).parent / "pilot_chunks.jsonl"
SEED = 20260801
SIZE, OVERLAP = 1000, 150
# stratified sample across sources (train split only)
PER_SOURCE = {"rulings": 40, "tips": 25, "archetype": 20, "mechanics": 15, "cardfacts": 20}

def chunk(text, size=SIZE, overlap=OVERLAP):
    step = max(1, size - overlap)
    out, i, n = [], 0, len(text)
    while i < n:
        out.append(text[i:i+size])
        if i + size >= n:
            break
        i += step
    return out

def main():
    docs = [json.loads(l) for l in CORPUS.open(encoding="utf-8")]
    train = [d for d in docs if d.get("split") == "train"]
    by_src = {}
    for d in train:
        by_src.setdefault(d["source"], []).append(d)

    rng = random.Random(SEED)
    picked = []
    for src, k in PER_SOURCE.items():
        pool = by_src.get(src, [])
        picked += rng.sample(pool, min(k, len(pool)))

    n = 0
    with OUT.open("w", encoding="utf-8") as f:
        for d in picked:
            # one representative chunk per doc (the first) keeps the pilot ~120 passages
            piece = chunk(d["text"])[0]
            f.write(json.dumps({"chunk_id": f"pc-{n:04d}", "doc_id": d["doc_id"],
                                "source": d["source"], "title": d["title"],
                                "text": piece}, ensure_ascii=False) + "\n")
            n += 1
    print(f"wrote {OUT.name}: {n} chunks from {len(picked)} train-split docs")
    print("  per source:", {s: min(k, len(by_src.get(s, []))) for s, k in PER_SOURCE.items()})

if __name__ == "__main__":
    main()

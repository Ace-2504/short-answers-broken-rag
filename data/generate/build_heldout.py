"""Phase-2 step 2: build the held-out test set from HELD-OUT-split pages (never used
for training). Each item: {id, question, gold, evidence}. Keeps only items whose
evidence is verbatim (or near-verbatim) in the source page. Resumable.

Target ≥60 kept items. Output: data/heldout.jsonl
"""
import json, random, time, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import gemini, call_json, containment, load_ids, load_jsonl

HERE = pathlib.Path(__file__).parent
CORPUS = HERE.parent / "corpus" / "corpus_clean.jsonl"
OUT = HERE.parent / "heldout.jsonl"
SEED = 20260801
TARGET, ATTEMPTS = 60, 100          # generate up to ATTEMPTS pages, keep verbatim-evidence ones

HO_PROMPT = (
    "From this Yu-Gi-Oh passage, write ONE clear question a player might ask, its correct answer, "
    "and the verbatim evidence sentence(s) from the passage that prove it (copy them exactly). "
    "Prefer a ruling/interaction question. Output ONLY compact JSON: "
    '{"question":...,"gold":...,"evidence":...}\n\nPassage:\n'
)

def main():
    docs = [json.loads(l) for l in CORPUS.open(encoding="utf-8")]
    # held-out pages, on-target sources, substantial length
    ho = [d for d in docs if d.get("split") == "heldout"
          and d["source"] in ("rulings", "archetype", "mechanics", "cardfacts")
          and len(d["text"]) > 400]
    random.Random(SEED).shuffle(ho)

    done_docs = load_ids(OUT, "doc_id")
    kept = len(load_jsonl(OUT))
    cli, model = gemini()
    attempts = 0
    with OUT.open("a", encoding="utf-8") as f:
        for d in ho:
            if kept >= TARGET or attempts >= ATTEMPTS:
                break
            if d["doc_id"] in done_docs:
                continue
            attempts += 1
            try:
                o = call_json(cli, model, HO_PROMPT + d["text"][:1400])
            except Exception as e:
                print(f"  skip: {e}", file=sys.stderr); time.sleep(1); continue
            q, gold, ev = (str(o.get(k, "")).strip() for k in ("question", "gold", "evidence"))
            if not q or not gold or not ev:
                continue
            # evidence must be grounded in the page (verbatim or near-verbatim)
            if ev not in d["text"] and containment(ev, d["text"]) < 0.8:
                continue
            f.write(json.dumps({"id": f"qa-{kept:03d}", "question": q, "gold": gold,
                                "evidence": ev, "doc_id": d["doc_id"], "source": d["source"]},
                               ensure_ascii=False) + "\n")
            f.flush(); kept += 1
            time.sleep(0.25)
    print(f"held-out: {kept} items in {OUT.name} (target {TARGET}, {attempts} pages tried this run)")

if __name__ == "__main__":
    main()

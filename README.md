# Yu-Gi-Oh SLM — Fine-tune vs. Retrieval

Reproducing the course experiment on a new domain: does fine-tuning a small LLM on Q&A pairs
teach it *facts*, or only the *shape* of an answer — and how much does retrieval add on top?

## The experiment

Three systems are compared on the **same** held-out Yu-Gi-Oh questions, graded by a
reference-grounded LLM judge:

| System | What it is |
|--------|------------|
| **A** | `google/gemma-2-2b-it`, untouched, closed book |
| **B** | Our QLoRA fine-tune of Gemma 2 2B, closed book |
| **C** | Same fine-tune, with our FAISS retriever supplying passages (RAG) |

**Hypothesis (to test honestly, report even if it disagrees):** closed-book fine-tuning (B)
will *not* clearly beat base (A), because Q&A fine-tuning writes answer *shape* into the
weights, not *facts*. Retrieval (C) supplies the facts at inference and is expected to be the
real win. We measure it — a carefully measured negative result is a complete answer.

**Domain:** Yu-Gi-Oh! rulings, interactions, timing/chain, archetype mechanics — chosen because
Gemma 2 2B does not know these closed-book, so the systems can actually separate. See
[PLAN.md](PLAN.md) for the full phase plan, licensing, question-type policy, and eval methodology.

## Stack (decided)

- **Corpus:** Yugipedia prose (CC BY-SA 4.0, attributed) + YGOPRODeck JSON (free). Card oracle
  text used only as labeled fair-use context.
- **GPU / serving:** Modal (QLoRA training + scale-to-zero HTTP endpoints).
- **Teacher / judge:** Gemini flash-lite class.
- **Embeddings / index:** `BAAI/bge-small-en-v1.5` (384-d, normalized) + FAISS.
- **Stats:** paired bootstrap CI (primary) + paired t-test (comparability) + Wilcoxon (robustness).

## Setup

```bash
# 1. create the project venv (Python 3.12)
py -3.12 -m venv .venv

# 2. install dependencies
.venv/Scripts/python.exe -m pip install -U pip
.venv/Scripts/python.exe -m pip install -r requirements.txt

# 3. authenticate services (needed from Phase 3 onward)
.venv/Scripts/hf.exe auth login --force     # paste a WRITE personal access token (hf_...)
.venv/Scripts/modal.exe token new           # opens browser to authenticate Modal
```

The `.venv/` folder, large data artifacts, the FAISS index, and model checkpoints are
git-ignored (see `.gitignore`); the committed data deliverables are `data/DATA.md`,
`data/train.jsonl`, `data/heldout.jsonl`, and the corpus statistics.

## Reproduce (filled in as phases complete)

_Step-by-step reproduction instructions land here as each phase ships._

## Links & cost (to be filled in)

- Hugging Face model: _TBD (Phase 3)_
- Live site: _TBD (Phase 6)_
- Endpoints: base / fine-tune / retrieve — _TBD (Phase 3–4)_
- Total cost (GPU + API): _tracked in [costs.md](costs.md)_

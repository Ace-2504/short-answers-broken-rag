# Phase 4 — Retriever Initial Test (recall@k on the real corpus)

**Status:** planned / not executed — runs on Harman's go signal.
**Location:** `rag/` (scripts to be built).
**Date:** 2026-08-03

> **This is NOT a re-run of the chunking design study.** That study (`initial-testing.md`) already
> *selected* the retriever config (hybrid MiniLM-L6 + BM25, 1000/150, flat, top-k 5, title-aug) and
> those knobs are settled — we do not re-test them. This phase does the two things that study could
> not: (1) **build the real index over the full corpus** (it only indexed a 0.32 MB / 52-page proxy),
> which System C requires; and (2) **compute the required recall@k table on the real `heldout.jsonl`**
> (the study used synthetic probes; the held-out set didn't exist yet). Recall changes at scale
> (~75× more chunks = more distractors), so the proxy's hybrid r@5 ≈ 0.87 is not the real number.
> The brief is explicit: *"if recall@5 is poor, no prompt engineering saves System C — know that
> before you blame the model,"* and it requires a recall@k table for k = 1, 3, 5, 10.

---

## 1. What we are doing

Build the **real retriever over the full cleaned corpus** and measure **recall@k on the 60 held-out
questions** — the assignment's required metric — before wiring retrieval into generation.

The chunking study (`initial-testing.md`) picked the config on a **0.32 MB proxy** with **synthetic**
probes. This test re-runs it on the **full ~27 MB corpus (26,388 docs)** with the **real
`heldout.jsonl`** (60 items, human-checked gold + evidence). Steps:

| Step | Script | Role |
|------|--------|------|
| chunk | `rag/build_index.py` | chunk all `corpus_clean.jsonl` docs at 1000/150, title-augmented |
| embed + index | `rag/build_index.py` | MiniLM-L6 embeddings → FAISS flat (IP); BM25 over the same chunks |
| measure | `rag/recall_at_k.py` | for each held-out question, is the chunk containing its gold `evidence` in the top-k? — for **dense / BM25 / hybrid (RRF)**, k ∈ {1,3,5,10} |

Retrieval indexes **all splits** — the retriever serves the whole corpus at inference; the
train/heldout split only ever governed *training*, so held-out pages are legitimately in the index.

## 2. Why we are doing it

- **It is the precondition for System C.** Recall@k is the ceiling on what retrieval-augmented
  generation can possibly answer; measuring it now is "measure recall before you blame the model."
- **Config was chosen on a proxy.** The chunking study warned absolute recall would move at full
  scale (more chunks = more distractors). This confirms the hybrid/MiniLM/1000-150/flat choice still
  holds — or flags an adjustment (reranker, chunk size) before we build the endpoint.
- **It is a required deliverable.** The brief wants a recall@k table for k = 1, 3, 5, 10.

## 3. Exact outputs we are trying to find

| # | Question the test answers | Concrete output | Feeds |
|---|---------------------------|-----------------|-------|
| 1 | **Recall@k** on the real held-out set | table: recall@1/3/5/10 for dense / BM25 / **hybrid** | the deliverable + System-C go/no-go |
| 2 | Does the chunking-study config hold at full scale? | full-corpus recall vs the proxy's hybrid r@5 ≈ 0.87 | confirm / adjust config |
| 3 | **The recall@5 gate** — is System C viable? | pass/fail on recall@5 | whether to wire System C or fix the retriever first |
| 4 | Which method wins on the real set | dense vs BM25 vs hybrid ranking | final retrieval method |
| 5 | **Top-k** for System C | where recall plateaus on the real set | System C's k (chunks fed to the model) |
| 6 | Recall by question type | recall@k split by interaction/timing/lore | Phase-5 interpretation (which targets retrieve well) |
| 7 | **Feasibility at scale** | chunk count, embed time (GPU), index size (RAM), search p50/p95 | sizing the `/retrieve` endpoint |

**Headline deliverable:** the **recall@k table** on `heldout.jsonl`, plus a confirmed retriever
configuration (or a documented adjustment) ready to wire into System C.

## 4. What this test cannot / does not cover

- **Retrieval only, not answer quality.** It measures whether the gold passage is *retrieved*, not
  whether System C *answers well* — that's Phase 5 (the A/B/C judge).
- **60 items is a small sample.** Recall@k has wide confidence intervals; treat differences of a few
  points as noise, the way we did for chunking.
- **Exact-substring gold matching.** A chunk "contains" the gold if the `evidence` string is inside
  it; a gold sentence split across a chunk boundary could undercount (conservative).
- **Single embedding model / seed / no reranker** in the base run (a reranker is a candidate *if*
  recall@5 disappoints, not a default).
- **The corpus is fixed** as of the Phase-1 build; no live updates.

## 5. Reproduce (once built)

```bash
.venv/Scripts/python.exe rag/build_index.py     # -> chunks.jsonl, faiss.index, bm25 state
.venv/Scripts/python.exe rag/recall_at_k.py     # -> recall_at_k.json + the table
```

## 6. Results (run 2026-08-03)

**Index:** 26,388 docs → **42,412 chunks** (all splits), embedded in 50 s (848 chunks/s, GPU),
65 MB FAISS flat + BM25. `rag/recall_at_k.json`.

**Recall@k on the real 60 held-out (coverage 100% — all 60 scorable):**

| method | r@1 | r@3 | r@5 | r@10 |
|--------|-----|-----|-----|------|
| dense (MiniLM-L6) | 0.62 | 0.87 | 0.92 | 0.95 |
| BM25 | **0.82** | 0.85 | 0.87 | 0.90 |
| **hybrid (RRF)** | 0.72 | **0.92** | **0.93** | **0.95** |

**Hybrid recall@5 = 0.93 → System C viable** (gate = 0.6).

By source (hybrid r@5): rulings **0.96**, cardfacts **0.93**, archetype 0.80 (n=5).

**Findings:**
1. **Config held at scale.** ~100× more chunks than the 0.32 MB proxy, yet hybrid r@5 (0.93) ≥ the
   proxy's 0.87 — real gold evidence retrieves cleanly. **No config change needed.**
2. **BM25 alone wins recall@1 (0.82)** — questions name specific cards; lexical nails rank-1. Hybrid
   dilutes r@1 (0.72) but wins r@3+ (0.92–0.95). Since **System C feeds top-5, hybrid + k=5 is the
   right choice**; BM25 would only win if we fed a single passage.
3. **Target types retrieve best** (rulings 0.96, cardfacts 0.93) — where System C must perform.

**Decision:** ship **hybrid, top-k = 5**, config unchanged. The `/retrieve` endpoint (`rag/retrieve.py`)
serves this index and is ready to wire into System C (Phase 5).

# Phase 5 — Evaluation Plan (A/B/C, the experiment's verdict)

**Status:** planned / not built — runs on Harman's go signal.
**Location:** `eval/` (scripts to be built).
**Date:** 2026-08-03

> This is the phase that answers the whole assignment: **does fine-tuning or retrieval actually let
> the small model answer domain questions?** Same test-first discipline as the earlier phases, but
> here the "test" *is* the deliverable. We report what we measure even if it disagrees with the
> expectation.

---

## 1. What we are doing

Run **three systems** over the **same 60 held-out questions**, grade each answer with a
**reference-grounded LLM judge**, and report the comparison with **paired significance tests**.

| System | What it is | How we produce it |
|--------|-----------|-------------------|
| **A** | `gemma-2-2b-it`, untouched, **closed book** | base model (adapter disabled), question only |
| **B** | our fine-tune, **closed book** | base + `yugioh-qa` adapter, question only |
| **C** | our fine-tune **+ retrieval** | retrieve top-5 (hybrid) → feed as context to B |

**One model in memory, sequential eval** (no concurrency), so we use `peft`'s
`with model.disable_adapter():` for A and the adapter for B/C — this sidesteps the brief's
adapter-race trap (which only bites concurrent serving) while keeping A and B on the *identical*
base and decoding settings. Decoding: **greedy / temperature 0** for reproducibility.

**Implementation (resource-aware, 2026-08-03):** system RAM was only ~2.6 GB free (three servers
already loaded), too little to load a fresh model in the harness. So the harness **reuses the
already-running servers** instead of loading anything new: A/B/C all call the fine-tune server
`:8100` (a `use_base` flag disables the adapter for System A — safe because eval is sequential),
and C additionally calls the retriever `:8200`. The harness itself is HTTP + the judge API (~300 MB).

## 2. Why (the hypothesis we test, honestly)

The thesis: **fine-tuning teaches answer *shape*, not *facts*; retrieval supplies the facts.**
Our own signals point the same way — the fine-tune's val loss plateaued fast (shape, not facts),
and the retriever hits **recall@5 0.93**. So we *expect* **A ≈ B** (fine-tuning adds little
closed-book) and **C ≫ A, B** (retrieval is the win). **We report the measured result regardless** —
a carefully measured null (A≈B) is a complete finding.

## 3. The judge design (matters more than the judge model)

- **Reference-grounded:** every judge call carries the **question + gold answer + verbatim
  evidence**. The judge *compares*, it does not recall — this makes grades reproducible by someone
  who doesn't know Yu-Gi-Oh.
- **Pointwise and blind:** one answer per call, **no model names**, no other candidates in context
  (kills position bias / anchoring).
- **Rubric summing to 10:** correctness **0–5**, completeness **0–2**, groundedness **0–2**,
  clarity **0–1**. **Groundedness caps at 0 if the answer invents a citation or figure**, however
  fluent. **A refusal must beat a confident error** — written into the rubric explicitly.
- **Judge model:** **Gemini flash-lite** (locked 2026-08-03) — consistent with teacher/gate; cheap;
  the grounded design makes the model choice secondary. Decoding for all three systems: **greedy /
  temperature 0** (locked) for reproducibility.

## 4. The statistics

- **Primary:** paired **bootstrap** 95% CI on the mean score difference (A→B and B→C), resampling
  the 60 items with a fixed seed.
- **Comparability:** paired **t-test** (matches the class's `t` values).
- **Robustness:** **Wilcoxon** signed-rank.
- Report **mean ± standard error** and a **per-category (rubric-component) breakdown** per system.
- With 60 items, differences under ~0.5 points usually won't separate — **saying so is the correct
  answer**, not a failure.

## 5. Exact outputs / deliverables

| Output | File |
|--------|------|
| Every system's answer to every held-out item | `eval/responses.json` |
| Per-answer judge scores (4 rubric components + total) | `eval/verdicts.json` |
| Per-system mean ± SE, per-component breakdown, paired A-vs-B & B-vs-C (bootstrap/t/Wilcoxon) | `eval/leaderboard.json` |
| **≥ 3 quoted disagreement examples** with our reading of why | in the report / leaderboard |
| The harness itself | `eval/run_eval.py` (+ judge) |

The harness must be **re-runnable and skip finished work** (idempotent caches for responses and
verdicts), per the brief.

## 6. What this cannot / does not cover

- **60 items is small** — wide CIs; treat sub-0.5-point gaps as inconclusive (and report them as such).
- **One judge, one seed, greedy decoding** — no judge-ensemble or self-consistency in the base run.
- **The judge is an LLM**, not a Yu-Gi-Oh expert — mitigated by reference-grounding, but not
  infallible; we'll spot-check verdicts.
- **Measures answer quality, not latency/UX** — the live side-by-side site is Phase 6.
- System C depends on the retriever; its ceiling is recall@5 (0.93) — already measured, so a weak
  C answer can be attributed correctly.

## 7. Reproduce (once built)

```bash
.venv/Scripts/python.exe eval/run_eval.py      # -> responses.json (A/B/C over 60 held-out)
.venv/Scripts/python.exe eval/judge.py         # -> verdicts.json (reference-grounded, blind)
.venv/Scripts/python.exe eval/leaderboard.py   # -> leaderboard.json + paired stats + disagreements
```

## 8. Results (run 2026-08-03)

**Leaderboard (n=60, /10)** — `eval/leaderboard.json`:

| System | mean ± SE | corr(5) | comp(2) | grnd(2) | clar(1) |
|--------|-----------|---------|---------|---------|---------|
| A base, closed | 3.98 ± 0.39 | 1.83 | 0.97 | 0.18 | 1.0 |
| B fine-tune, closed | 5.25 ± 0.54 | 2.35 | 1.03 | 0.87 | 1.0 |
| **C fine-tune + retrieval** | **8.05 ± 0.41** | 3.85 | 1.55 | 1.65 | 1.0 |

**Paired significance:**
- **A vs B: +1.27**, bootstrap 95% CI [0.42, 2.17], t=2.81 (p=0.007), Wilcoxon p=0.012 → **significant**
- **B vs C: +2.80**, bootstrap 95% CI [1.72, 3.87], t=5.08 (p<0.001), Wilcoxon p<0.001 → **significant**

**Reading (honest, and it partly disagrees with the class reference):**
- **Retrieval is the dominant win** (C ≫ B, +2.80) — the thesis holds; facts arrive with retrieval
  (C correctness 3.85 vs B 2.35).
- **But fine-tuning ALSO significantly helped closed-book (B > A, +1.27)** — the reference found it
  did *not*. Our breakdown shows the gain is mostly **groundedness (0.18 → 0.87)**: the base model
  gives verbose confident hallucinations (rubric caps groundedness at 0 for invented details); the
  fine-tune learned a tighter, more-grounded *shape*. So **fine-tuning taught shape, not facts**
  (consistent with the thesis), but that shape was enough to raise the score here.

**Disagreements (largest C−A gaps):** Dododo Swordsman/Damage Step (A1 B1 **C10**), Amazoness
Fighting Spirit (A1 B4 **C10**), Kozmo archetype (A1 B1 **C10**) — closed-book systems hallucinate;
retrieval returns the gold. Full quotes in `eval/leaderboard.json`.

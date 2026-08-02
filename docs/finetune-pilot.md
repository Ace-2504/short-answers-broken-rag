# Fine-Tuning Pilot — Data-Generation Study (pre-Phase-2/3)

**Status:** planned / not executed — runs only on Harman's go signal.
**Location:** `finetune/pilot/` (scripts to be built).
**Owner:** Harman
**Date:** 2026-08-01

> This mirrors the chunking study (`docs/initial-testing.md`): a small, cheap measurement run that
> turns Phase-2/3 design decisions from guesses into data-backed choices **before** we spend the
> teacher-API and GPU budget on the full run. Same ethos: *measure, don't assume.*

---

## 1. What we are doing

Before generating the full ≥2,000-pair supervised set and launching QLoRA, we run a **mini
end-to-end pilot** on a small sample of the cleaned corpus and *measure* the pipeline. Two parts:

**Part A — data pipeline (the core of the pilot):**

| Step | Script | Role |
|------|--------|------|
| chunk a sample | `finetune/pilot/chunk_sample.py` | chunk ~120 **train-split** docs at 1000/150 (the locked retriever setting), stratified across sources (rulings/tips/archetype/mechanics/cardfacts) |
| teacher QA gen | `finetune/pilot/generate_qa.py` | Gemini flash-lite writes grounded QA per chunk ("answer only from the passage"), storing the evidence span |
| VALIDATE gauntlet | `finetune/pilot/validate.py` | run G1–G5 (`fine-tuning-dataset-creation-guidelines.md`) and **report attrition + distributions** |
| held-out probe | (in `generate_qa.py`) | generate a few `{id,question,gold,evidence}` items from **held-out-split** pages to prove the format works |

**Part B — training smoke test (optional, plumbing only):**

| Step | Script | Role |
|------|--------|------|
| tiny QLoRA run | `finetune/pilot/smoke_train.py` | ~100–200 steps on the pilot's surviving pairs, on Modal (L4/A100), to validate the training script, config, and **project GPU cost** — NOT to produce a usable model |

`recall@k` was the chunking study's yardstick; here the yardsticks are **attrition rate**,
**grounding pass rate**, **yield per chunk**, **cost per pair**, and (Part B) **GPU-hours/step**.

## 2. Why we are doing it

- **De-risk the expensive stage.** The full Phase-2 teacher run + Phase-3 QLoRA is where most of the
  $25 budget goes. A ~$1 pilot catches a broken teacher prompt, a miscalibrated gate, or a training
  config bug *before* the spend — exactly as the chunking study caught bge/flat/hybrid before the
  retriever build.
- **Calibrate the gauntlet on OUR data.** The G1–G5 thresholds (`⟨verify⟩` in the guide) are
  proposals; the pilot measures what they actually drop on Yu-Gi-Oh QA, the same way the cleaning
  dry-run validated the 200-char floor.
- **Size the full run.** Yield-per-chunk + attrition tell us exactly how many chunks to process to
  net ≥2,000 survivors, and what it will cost — no over- or under-shooting.
- **Guard the known risk.** We flagged that the teacher could flood the set with low-value
  "which cards search X?" / verbatim-card-text pairs. The pilot measures how often that happens and
  whether G5 balance + the grounding gate control it.

## 3. Exact outputs we are trying to find

Each row is a decision the pilot must return with a number, and where it feeds.

| # | Question the pilot answers | Concrete output | Feeds |
|---|----------------------------|-----------------|-------|
| 1 | **Yield per chunk** — pairs the teacher makes per passage | mean raw pairs/chunk | sizes the full run (chunks needed for 2,000 survivors) |
| 2 | **Total attrition** — % of raw pairs dropped | overall survival %, checked vs the guide's 20–50% band | Phase-2 go/no-go on the teacher prompt |
| 3 | **Per-gate attrition** — where pairs die | drop count at G1/G2/G3/G4/G5 | which gate/threshold to tune |
| 4 | **Grounding calibration** — G2a overlap for grounded vs not | overlap distributions + a defensible pre-filter threshold; judge-override rate | G2 threshold |
| 5 | **Question-type & difficulty mix** | share per type (definition/interaction/timing/lore) + lookup-vs-multistep | whether we need Evol-Instruct; the G5 cap |
| 6 | **Dedup rate** — near-duplicate questions | % flagged by G3 | G3 cosine threshold |
| 7 | **Teacher failure modes** (qualitative) | examples: vague Qs, verbatim card-text recall, refusable Qs | hardening the teacher prompt |
| 8 | **Low-value-pair rate** — the "searched-by / recite-effect" risk | % of pairs that are pure lookup/recall | confirms G5 balance controls it |
| 9 | **Cost & time per pair** | $/1k pairs vs the $5/1k baseline; wall-clock | full-run budget line in `costs.md` |
| 10 | **Held-out generation works** | a few valid `{id,question,gold,evidence}` items | Phase-2 held-out build |
| 11 (B) | **Training plumbing + cost** | loss decreases over ~150 steps; GPU-hours/step; $/epoch projection | Phase-3 go + config lock |

**Headline deliverable:** a **recommended Phase-2/3 configuration** — teacher prompt, calibrated
G1–G5 thresholds, the number of chunks to process, the projected cost, and (Part B) a validated
training config with a cost estimate — each line backed by a pilot number.

## 4. What this experiment cannot / does not cover

- **It is a proxy, not the full set.** ~120 chunks / a few hundred pairs; absolute rates shift at
  scale. We treat the *rankings and calibrations* as transferable and re-confirm on the full run.
- **It does NOT measure whether fine-tuning helps.** System B-vs-A/C is the whole experiment,
  decided in Phase 5 with the paired-bootstrap judge — the pilot says nothing about it.
- **Part B loss ≠ model quality.** A smoke-train validates the *plumbing and cost*, not the
  outcome; a falling loss over 150 steps does not mean the final model is good.
- **One teacher, one judge, one seed.** Results are not claimed to generalize across teachers.
- **Grounding gate is the teacher grading itself/its sibling.** Known limitation of LLM-as-judge;
  the final eval uses the reference-grounded judge, but the pilot's gate is lighter.
- **No retrieval, no site.** The pilot stops at data + a training smoke test.

## 5. How to reproduce (once built)

```bash
# from repo root, venv active; GEMINI_API_KEY set
.venv/Scripts/python.exe finetune/pilot/chunk_sample.py    # -> pilot_chunks.jsonl
.venv/Scripts/python.exe finetune/pilot/generate_qa.py     # -> pilot_raw_qa.jsonl (+ held-out probe)
.venv/Scripts/python.exe finetune/pilot/validate.py        # -> pilot_report.json + attrition tables
# Part B (optional, needs Modal):
modal run finetune/pilot/smoke_train.py                    # -> loss curve + GPU cost
```

Deterministic where possible: fixed sampling seed (`20260801`); the exact pilot pairs are committed
so a result is reproducible even though teacher wording varies run-to-run.

## 6. Results (Part A, run 2026-08-01)

120 stratified train-split chunks → **276 raw pairs** (+15 held-out probe items). Full numbers in
`finetune/pilot/pilot_report.json`.

| # | Finding | Value |
|---|---------|-------|
| 1 | **Yield/chunk** | **2.36** → ~1,000 chunks nets ≥2,000 survivors |
| 2/3 | **Attrition (lexical gates only)** | **~3%** — G1 format clean (0 empty, 0 bad-punct); ~7 weakly-grounded; ~2 dupes; 0 decontam. *Too low vs guide's 20–50% → the LLM judge (G2b) is the real gate* |
| 4 | **Grounding** | **evidence-in-passage = 1.00** (teacher always quotes verbatim); answer↔passage overlap median 0.75; only **7/276 (2.5%)** below 0.35 |
| 5 | **Question-type mix** | **interaction 70% + timing 17% = 87% on-target**; definition 10%, lore 2%. Difficulty **57% multistep** → no Evol-Instruct needed |
| 6 | **Dedup** | 2 near-dups @0.92 (~1%) — teacher is diverse |
| 7/8 | **Low-value pairs** | **searched-by = 0** (prompt controls the risk); stat-lookup 15%; verbatim-copy answers 17% |
| 9 | **Cost** | pilot ≈ <$0.20; full run (~1k gen + judge) projected **well under $1** (flash-lite ≈ 10–30× under the $5/1k baseline) |
| 10 | **Held-out gen** | 15 valid `{id,question,gold,evidence}` items — format works |
| 4 | **Decontam** | max sim to held-out mean 0.38, **0 collisions** ≥0.85 → structural page-split separation holds |

**Recommended Phase-2 configuration:**
- Process **~1,000–1,200 train chunks** to net ≥2,000 clean pairs.
- G1 length bounds pass everything — keep (q 15–300, a 3–1200).
- **Add the G2b judge grounding/correctness check** — lexical gates alone are near-passthrough
  (~3%); the judge is where real quality control happens (catches plausible-but-wrong answers).
- G3 dedup cosine **0.92**; G4 decontam keep as safety (Layer-1 structural split already works).
- **G5: do NOT cap interaction at 45%** — 87% interaction+timing is exactly the target mix for this
  experiment; capping would discard good on-target pairs. (Decision pending Harman.)
- No Evol-Instruct needed (57% already multistep).

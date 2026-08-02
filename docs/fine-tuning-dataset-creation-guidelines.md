# fine-tuning-dataset-creation-guidelines.md

> **Scope:** Phase 2 only — turning the cleaned corpus into the supervised fine-tuning (SFT)
> set (teacher-generated QA pairs) and validating it. **Corpus cleaning (Phase 1) is a separate
> document:** `corpus-cleaning-system.md`.
>
> **Source of truth:** the Vizuara guide at <https://slm-finetuning-data.vercel.app/>
> (read verbatim 2026-08-01). This document follows it strictly. Thresholds the guide leaves
> unspecified are **proposed** here and flagged `⟨verify⟩` for Harman to confirm/change.
>
> **Status: SPEC — not executed.** Runs only after Phase 1 lands and Harman signs off.

---

## 1. Pipeline (guide §8)

**CHUNK → TEACHER → VALIDATE → FORMAT → SFT set.** We walk the cleaned corpus chunk by chunk;
for each chunk a teacher LLM invents grounded QA and answers them using **only that passage**;
we validate/decontaminate; we render as chat JSONL.

## 2. Dataset format (guide §2)

**chat / messages** (`system` / `user` / `assistant`) — the guide's "modern default": it matches
how Gemma is served and a chat template renders roles into the exact special tokens. (Plain
completion, prompt→completion, and preference/DPO are the other shapes; DPO is later alignment,
not basic SFT.)

## 3. Where the data comes from (guide §3)

Three sources: **A** hand-written (small precious seed/eval), **B** convert structured data,
**C** teacher-LLM distillation — the default workhorse. We use **C** (Gemini flash-lite teacher)
for the bulk, optionally a few **A** seeds.

## 4. Teacher QA synthesis (guide §4)

For each corpus chunk, prompt the teacher: *"Read the passage. Write diverse QA pairs whose
answers are stated only in the passage. If a question cannot be answered from it, do not invent
one."* Every answer is **grounded** and stored with its supporting span (`evidence`) — which also
serves the held-out `evidence` field the assignment requires. Grounding is the point: an
ungrounded teacher injects hallucinations the student would faithfully learn.

## 5. Recipes (guide §5)

- **Group A (quantity/difficulty):** *Self-Instruct* (multiply a few seeds into thousands of
  diverse instructions), *Evol-Instruct* (evolve easy → hard, multi-step, edge cases).
- **Group B (task types):** **Grounded QA / RAFT is primary** — the guide calls it "the single
  most important task type … the fine-tuning that later makes retrieval trustworthy" (this is
  exactly System B/C of the assignment). Summarization / Extraction / Rewriting are optional
  extras ⟨verify whether we include any beyond Grounded QA⟩.

## 6. VALIDATE — the quality gauntlet (guide §6, mandatory, in order)

Cheap filters first so we don't embed/judge pairs a format check already kills.

### G1 — Length & format (§6.3)
Reject empty/truncated answers, malformed records, and out-of-bounds lengths; enforce chat schema
(every row must parse). Proposed bounds: **question 15–300 chars**, **answer 3–1200 chars**
⟨verify⟩; reject answers with no terminal punctuation as likely truncations ⟨verify⟩.

### G2 — Grounding / faithfulness (§6.2) — the core gate
Guide permits "string overlap, NLI, or teacher self-check." Two-layer:
- **G2a lexical pre-filter:** answer↔passage token containment/Jaccard; below **0.35** ⟨verify⟩
  escalate, above provisionally pass.
- **G2b judge check:** teacher/judge verifies the answer is supported by the passage **only**,
  returning grounded ∈ {yes, partial, no}. Reject `no`; reject `partial` unless overlap is high
  ⟨verify⟩. (Our Study 9 showed a retrieval *score* can't gate quality → we use an explicit judge,
  which the guide allows.)

### G3 — Near-duplicate dedup (§6.1)
Embed surviving **questions** (`all-MiniLM-L6-v2`), greedily cluster by cosine, keep one
representative per cluster. Near-dup threshold cosine ≥ **0.92** ⟨verify⟩. ("Asking the same
thing 500 ways teaches one narrow behavior and wastes budget.")

### G4 — Decontaminate vs held-out / eval (§6.5) — two layers
- **Layer 1 (structural):** held-out *pages* were reserved before generation, so training pairs
  and held-out items come from disjoint pages.
- **Layer 2 (paraphrase):** drop any training pair whose question collides with a held-out
  question by **n-gram AND/OR embedding**: 8-gram / token-Jaccard ≥ **0.60** ⟨verify⟩, or cosine
  ≥ **0.90** ⟨verify⟩. ("A contaminated eval reports scores you did not earn.")

### G5 — Difficulty & task balance (§6.4)
The guide's rule: "mix easy lookups with hard multi-step questions, and balance across **task
types (QA, summarize, extract)**." Two axes, read carefully:
- **Difficulty mix** — required, and satisfied: keep a non-trivial multi-step share (the pilot
  produced **57% multistep** naturally, so **no Evol-Instruct is needed**).
- **Behavior task-type balance** — "task types" here means *behaviors* (QA / summarize / extract).
  **We are QA-only by design** (Grounded QA / RAFT is the assignment's target), so this axis does
  not apply — there is nothing to balance.

**Decision (2026-08-01): do NOT cap question sub-types** (definition/interaction/timing/lore).
The 70% "interaction" concentration the teacher produces is the *target* of this experiment (where
the base model fails and RAG wins); an earlier proposed ≤45% cap was **not** in the guide — it was
an over-extension of "balance" to sub-topics, and capping would discard good on-target pairs. We
still **tag** each pair by type/difficulty for reporting, we just don't down-sample.

## 7. FORMAT & accounting

- Render survivors as **chat / messages JSONL**; held-out items keep `{id, question, gold, evidence}`.
- **Attrition 20–50%** of raw teacher output is expected ("a feature, not waste"). Record
  **generated → G1 → G2 → G3 → G4 → survived** with per-gate drop counts in `DATA.md`.
- **Target ≥ 2,000 survivors** (assignment floor); generate ~3,000–4,000 raw for headroom.
- **Quality > quantity** (LIMA: 1,000 curated can beat 100k noisy) — spend on curation, not volume.

## 8. Cost (guide §7)

Teacher baseline ≈ **$5 per 1,000 pairs**. ~4,000 raw pairs ≈ a few dollars — logged in `costs.md`.

## 9. What this spec does NOT do yet

No generation, no gating, no formatting is run. Thresholds are first proposals; Harman verifies
each `⟨verify⟩` value before Phase 2 executes.

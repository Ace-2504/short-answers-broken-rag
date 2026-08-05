# Yu-Gi-Oh SLM — does fine-tuning teach *facts*, or just the *shape* of an answer?

> A small-language-model experiment on the Yu-Gi-Oh! trading card game. Three systems answer the same
> held-out questions; a reference-grounded AI judge scores them 0–10; the numbers tell you whether
> fine-tuning or retrieval is what actually makes a small model *know* things.

**[▶ Live arena](https://harman-ygo-slm.vercel.app)** ·
**[Model — fine-tune](https://huggingface.co/Ace-2504/gemma-2-2b-yugioh-qa)** ·
**[Model — RAG](https://huggingface.co/Ace-2504/gemma-2-2b-yugioh-rag)** ·
**[one-page report](report.pdf)**

> ### ★ Featured — [**The RAG Study**](RAG-STUDY.md)  ·  *the big follow-up result*
> Once retrieval works, **is the retriever or the reader the real bottleneck?** Six experiments say the
> **reader** — and that retrieval-side tuning (reranking, deeper retrieval, chunk-repair) buys nothing once
> recall is already high.  **→ [Read the RAG study](RAG-STUDY.md).**

---

## Contents

★ **[The RAG Study — the big follow-up result](RAG-STUDY.md)** — *is retrieval or the reader the bottleneck?*

1. [What this is](#1-what-this-is)
2. [Try it live](#2-try-it-live)
3. [Headline result](#3-headline-result)
4. [How it works](#4-how-it-works)
5. [The corpus](#5-the-corpus)
6. [Evaluation — the AI judge](#6-evaluation--the-ai-judge)
7. [What I learned](#7-what-i-learned)
8. [Repository layout](#8-repository-layout)
9. [Reproduce, in order](#9-reproduce-in-order)
10. [Cost to build](#10-cost-to-build)
11. [Limitations & honest gaps](#11-limitations--honest-gaps)
12. [Credits & license](#12-credits--license)

---

## 1. What this is

**Yu-Gi-Oh! is a trading card game with thousands of cards and famously intricate rules** — cards
interact in ways that even experienced players argue about. That makes it a genuinely hard test for a
small AI model: to answer well you need *specific facts* (a card's stats, its exact effect, whether it
is banned) and *rules reasoning* (timing, chains, what can be activated when).

This project builds **three systems on top of Google's Gemma 2 2B** and compares them on the **same 60
held-out questions**, to answer one question honestly:

> Does fine-tuning a small model on question–answer pairs teach it *facts*, or only the *shape* of a
> good answer — and how much does retrieval add on top?

| System | What it is | Closed-book? |
|--------|------------|:---:|
| **A · Base** | `google/gemma-2-2b-it`, exactly as shipped | ✅ |
| **B · Fine-tune** | A QLoRA fine-tune of the same model on 2,683 grounded Yu-Gi-Oh Q&A pairs | ✅ |
| **C · Fine-tune + retrieval** | System B, with a hybrid retriever supplying real passages before it answers | ❌ (RAG) |

Yu-Gi-Oh was chosen on purpose: a quick probe showed the **base model is genuinely ignorant** of it
(~1.5/12, confidently making up card text), so the three systems can actually separate.

---

## 2. Try it live

All four sites share the research-lab theme (a swatch picker, parchment default) and answer against a
**live model on a local RTX 3060** exposed through a Cloudflare tunnel.

| Site | What it does |
|------|--------------|
| **[harman-ygo-slm.vercel.app](https://harman-ygo-slm.vercel.app)** | **The arena** — pick a question by category (or type your own), all three systems answer, and a **live AI judge** scores each answer 0–10 |
| [harman-ygo-base.vercel.app](https://harman-ygo-base.vercel.app) | System A on its own |
| [harman-ygo-finetune.vercel.app](https://harman-ygo-finetune.vercel.app) | System B on its own |
| [harman-ygo-rag.vercel.app](https://harman-ygo-rag.vercel.app) | System C on its own |

**Models on Hugging Face:** [`gemma-2-2b-yugioh-qa`](https://huggingface.co/Ace-2504/gemma-2-2b-yugioh-qa)
(System B) · [`gemma-2-2b-yugioh-rag`](https://huggingface.co/Ace-2504/gemma-2-2b-yugioh-rag) (System C).

> **Note:** the demos need the local model server + retriever + tunnel running; if the server is down the
> sites show a clear *"demo unavailable"* state, and the published evaluation numbers below are unaffected.

---

## 3. Headline result

Mean judge score over the 60 held-out questions (0–10), with paired significance:

| System | Score ± SE | vs. previous |
|---|---|---|
| A · base, closed | 3.98 ± 0.39 | — |
| B · fine-tune, closed | 5.25 ± 0.54 | **+1.27**, p = 0.007 (significant) |
| C · fine-tune + retrieval | **8.05 ± 0.42** | **+2.80**, p < 0.001 (significant) |

Broken into the four rubric dimensions:

| System | Correctness /5 | Completeness /2 | Groundedness /2 | Clarity /1 |
|---|---|---|---|---|
| A | 1.83 | 0.97 | 0.18 | 1.00 |
| B | 2.35 | 1.03 | 0.87 | 1.00 |
| C | 3.85 | 1.55 | 1.65 | 1.00 |

**Retrieval is the decisive win** (C ≫ B). Fine-tuning *also* significantly beat the base closed-book
(B > A), but the gain is concentrated in **groundedness** (0.18 → 0.87) — answer *shape*, not facts. The
facts only arrive with retrieval: **correctness only jumps (2.35 → 3.85) once real passages are in the
prompt.** So *fine-tuning teaches the shape; retrieval supplies the facts.*

---

## 4. How it works

```
                      ┌─────────────────────────────────────────────┐
   a question ───────▶│  A · base (adapter disabled)                │─▶ answer A
                      │  B · fine-tune (QLoRA adapter)               │─▶ answer B
                      │  C · retriever ─▶ top-5 passages ─▶ prompt   │─▶ answer C + passages
                      └─────────────────────────────────────────────┘
                                          │
                         reference-grounded AI judge (blind, /10)
                                          │
                         A 3.98   ·   B 5.25   ·   C 8.05
```

- **Base model:** `google/gemma-2-2b-it` (2.6B params, 4-bit NF4 at inference). All three systems are the
  *same* model — A disables the adapter, B/C enable it, C additionally prepends retrieved context.
- **Fine-tune (B):** a QLoRA adapter (rank 16 / α 32, all linear modules, LR 2e-4 cosine, seq 512, bf16),
  early-stopped at the best validation checkpoint (~1 epoch; 3 epochs overfit). **Validation perplexity 3.87.**
- **Retriever (C):** a **hybrid of dense `all-MiniLM-L6-v2` embeddings + lexical BM25**, fused with
  Reciprocal Rank Fusion, **top-5** over **42,412 chunks** (1000/150 chars, title-augmented) in a flat
  FAISS index. Hybrid because Yu-Gi-Oh hinges on exact card names that dense embeddings blur but BM25
  matches exactly — **recall@5 = 0.93**.

---

## 5. The corpus

The fine-tune's supervised set is **2,683 grounded QA pairs**, distilled by a teacher model from a
curated Yu-Gi-Oh corpus and filtered through a blind-judge gauntlet. The corpus is two **free** sources.

**Split (27.5 MB raw, across sources):**

| Source | Role | License | Size | Share |
|--------|------|---------|-----:|------:|
| Yugipedia · tips | rulings & interactions | CC BY-SA 4.0 | 8.47 MB | 31% |
| Yugipedia · rulings | rulings | CC BY-SA 4.0 | 5.90 MB | 22% |
| YGOPRODeck · card facts | card identity (stats + fair-use text) | free / © Konami | 6.04 MB | 22% |
| Yugipedia · archetype | mechanics | CC BY-SA 4.0 | 2.74 MB | 10% |
| Yugipedia · lore (ep + char) | lore | CC BY-SA 4.0 | 3.92 MB | 14% |
| Yugipedia · mechanics | glossary | CC BY-SA 4.0 | 0.40 MB | 1% |

**78% is free-licensed Yugipedia prose** (20.7 MB cleaned, clears the 20 MB floor); card effect text is
© Konami, used only as labelled fair-use context — never a verbatim-recall target. Card knowledge is a
YGOPRODeck snapshot fetched **2026-08-01**.

**The funnel (measured at every stage):**

```
11,944 Yugipedia pages (21.43 MB) + 14,477 cards (6.04 MB)
   → clean (line/citation strip · doc floor 200 · MinHash-LSH 0.80)
   → 26,388 docs (corpus_clean.jsonl), 20.74 MB free prose
   → 1,200 stratified chunks → teacher QA → 2,796 raw pairs
   → gauntlet G1–G5 (format · judge · dedup · decontaminate) → 2,683 train pairs
   → 60 held-out items (question + gold + evidence), page-split so no leakage
```

Full details, per-stage counts and known gaps are in [`data/DATA.md`](data/DATA.md).

---

## 6. Evaluation — the AI judge

Every answer is scored by a **reference-grounded, blind, pointwise** judge
(`gemini-3.1-flash-lite`). Its strength is that it grades **against a written answer key**, so it can
fairly score a domain it was never trained on.

- **Reference-grounded** — for each held-out question the judge is handed the **gold answer + verbatim
  evidence** (the corpus passage), and grades against that, not its own knowledge.
- **Blind & pointwise** — it never sees which system produced an answer, and scores one answer at a time.
- **Rubric (total 10):** correctness **0–5**, completeness **0–2**, groundedness **0–2**, clarity **0–1**.
- **Guardrails:** inventing a card detail forces **groundedness → 0**; a correct refusal must outscore a
  confident wrong answer.
- **Statistics:** systems are compared with a **paired** design (same 60 questions) — bootstrap 95% CI
  (primary), cross-checked with a paired t-test and Wilcoxon.

The same judge runs **live on the arena**: dropdown questions ship with a gold answer so grading is
checkable; typed questions are graded from the judge's own knowledge and labelled as such.

---

## 7. What I learned

- **RAG's ceiling is the reader, not the retriever.** Even when the retriever hands the model the exact
  card text, a 2.6B model sometimes mis-reads it (recall@5 is already 0.93) — which is why System C tops
  out near 8, not 10.
- **A reference-grounded judge can grade a domain it does not know** — handing it the answer key is what
  makes Yu-Gi-Oh evaluation trustworthy.
- **Match the retriever to the domain's shape** — Yu-Gi-Oh is proper-noun-heavy, so lexical BM25 + dense
  hybrid beats pure dense.
- **Fine-tuning teaches shape, not facts** — the fine-tune's scores are near-bimodal (it aces
  rules-logic questions, fails fact-lookups it never stored); retrieval is what supplies the facts.

---

## 8. Repository layout

```
data/       DATA.md (dataset card + funnel), train.jsonl (2,683), heldout.jsonl (60)
            collect/ (fetch + clean scripts), generate/ (teacher QA + judge gauntlet)
train/      modal_finetune_gemma.py, loss_curve.png, MODEL_CARD.md, serve_local.py (/generate · /ask · /judge)
rag/        build_index.py, retrieve.py (/retrieve), recall_at_k.py + .json, chunking_study/
eval/       run_eval.py, judge.py, leaderboard.py, responses.json, verdicts.json, leaderboard.json
site/       index.html — the deployed arena (live A/B/C + categorized dropdown + live judge)
frontends/  build.py + base/ finetune/ rag/ — the three per-system sites (generated)
finetune/   pilot/ — the QA-generation pilot run
docs/       design notes (retriever study, cleaning system, eval plan, verification, …)
report/     make_report.py, results-dossier.html   ·   report.pdf (root) — the one-page report
story.md    the running build log (every experiment, E1 onward)
```

---

## 9. Reproduce, in order

Each part lists its **prerequisites**, the **process**, and the **outcome** you should see.

### Part 0 · Environment
- **Prerequisites:** Python 3.12; a Hugging Face **WRITE** token (Gemma 2 is gated, and the adapter is
  pushed to the Hub); a Modal account (L4 GPU for training); a Gemini API key (teacher + judge).
- **Process:**
  ```bash
  py -3.12 -m venv .venv
  .venv/Scripts/python.exe -m pip install -r requirements.txt
  .venv/Scripts/hf.exe auth login --force        # accept the Gemma license first, on huggingface.co
  .venv/Scripts/modal.exe token new
  setx GEMINI_API_KEY <key>
  ```
- **Outcome:** `torch` sees CUDA; `hf auth whoami` and `modal token` succeed; `GEMINI_API_KEY` is set.

### Part 1 · Corpus & supervised set
- **Prerequisites:** Part 0. Network access to the Yugipedia + YGOPRODeck APIs.
- **Process:**
  ```bash
  .venv/Scripts/python.exe data/collect/fetch_corpus.py         # Yugipedia prose
  .venv/Scripts/python.exe data/collect/fetch_cardfacts.py      # YGOPRODeck card facts
  APPLY=1 .venv/Scripts/python.exe data/collect/clean_corpus.py # -> data/corpus/corpus_clean.jsonl
  .venv/Scripts/python.exe data/generate/build_heldout.py       # -> data/heldout.jsonl (60, gold + evidence)
  .venv/Scripts/python.exe data/generate/generate_dataset.py    # teacher QA -> raw pairs
  .venv/Scripts/python.exe data/generate/validate_gauntlet.py   # G1-G5 gauntlet -> data/train.jsonl
  ```
- **Outcome:** `corpus_clean.jsonl` (26,388 docs, ≥20 MB free prose), `data/train.jsonl` (2,683 pairs),
  `data/heldout.jsonl` (60 items). Counts match [`data/DATA.md`](data/DATA.md).

### Part 2 · Fine-tune (QLoRA)
- **Prerequisites:** Part 1; Modal auth; `data/train.jsonl`.
- **Process:** `modal run train/modal_finetune_gemma.py`
- **Outcome:** the adapter is pushed to `Ace-2504/gemma-2-2b-yugioh-qa`, `train/loss_curve.png` is saved,
  validation perplexity ≈ **3.87**.

### Part 3 · Retriever
- **Prerequisites:** Part 1 (`corpus_clean.jsonl`).
- **Process:**
  ```bash
  .venv/Scripts/python.exe rag/build_index.py       # chunk + embed + BM25 -> rag/index/
  .venv/Scripts/python.exe rag/recall_at_k.py       # -> rag/recall_at_k.json
  ```
- **Outcome:** `rag/index/` (FAISS + BM25 over 42,412 chunks); hybrid **recall@5 ≈ 0.93**.

### Part 4 · Serve (Parts 2–3 behind endpoints)
- **Prerequisites:** the adapter (Part 2), `rag/index/` (Part 3), `cloudflared`, `GEMINI_API_KEY` (for `/judge`).
- **Process:**
  ```bash
  .venv/Scripts/python.exe -m uvicorn rag.retrieve:app      --port 8200   # /retrieve
  .venv/Scripts/python.exe -m uvicorn train.serve_local:app --port 8100   # /generate · /ask · /judge
  cloudflared tunnel --url http://localhost:8100                          # public URL
  ```
- **Outcome:** `:8100/health` returns 200; `/ask` returns A/B/C + passages; `/judge` returns rubric scores.

### Part 5 · Evaluate all three
- **Prerequisites:** `:8100` + `:8200` up; `GEMINI_API_KEY`.
- **Process:**
  ```bash
  .venv/Scripts/python.exe eval/run_eval.py         # -> eval/responses.json (A/B/C, greedy)
  .venv/Scripts/python.exe eval/judge.py            # -> eval/verdicts.json (reference-grounded, blind)
  .venv/Scripts/python.exe eval/leaderboard.py      # -> eval/leaderboard.json + paired stats
  ```
- **Outcome:** the leaderboard reproduces A 3.98 / B 5.25 / C 8.05 with the significance tests.

### Part 6 · Frontends
- **Prerequisites:** a Vercel account; the tunnel URL from Part 4.
- **Process:** set the tunnel URL in `site/index.html` and `frontends/build.py` (`BASE`), then
  `cd site && vercel --prod`, and `python frontends/build.py deploy` for the three per-system sites.
- **Outcome:** the four live sites answer and judge against your endpoint.

---

## 10. Cost to build

**$2.36** of a $25 budget — measured, not estimated:

| Bill | Detail | Cost |
|------|--------|-----:|
| Modal · GPU | the QLoRA fine-tune (Gemma 2 2B on an L4) | $0.36 |
| Gemini API | teacher generation + QA gating + judging | $2.00 |
| Local · RTX 3060 | retriever build + serving + evaluation | $0 |
| **Total** | | **$2.36** |

The base model is Google's (imported free); retrieval, serving and evaluation all run on a local GPU, so
the only real spend is a little L4 time and a lot of cheap teacher/judge calls.

---

## 11. Limitations & honest gaps

- **The demo depends on a local machine.** The sites are live only while the RTX 3060 server + retriever
  + Cloudflare tunnel are running; the tunnel URL is ephemeral. The evaluation numbers do not depend on it.
- **A 2.6B model is the ceiling for System C.** It sometimes mis-reads a correctly-retrieved passage; a
  larger model or better prompting is the next lever, not better retrieval.
- **Superseded rulings.** A rare fraction (~0–4%) of Yugipedia rulings pages contain struck-through
  "previously official" text that survived cleaning; the teacher grounding gate and the eval judge
  mitigate it. (See DATA.md.)
- **Lore is the weakest retrieval category** (recall@5 ≈ 0.56), so System C answers lore less reliably.
- **The judge is a single model, uncalibrated against human labels** — treat small score differences
  cautiously.

---

## 12. Credits & license

- **Base model:** [`google/gemma-2-2b-it`](https://huggingface.co/google/gemma-2-2b-it) (Gemma license).
- **Corpus:** Yugipedia editorial prose under **CC BY-SA 4.0** (attributed, share-alike); YGOPRODeck via
  its free API. Card names and effect text are **© Konami / 4K Media**, used here only as labelled
  fair-use context, never redistributed as a dataset.
- **Built by Harman Singh Sandhu**

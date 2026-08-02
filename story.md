# story.md — the running log of this assignment

> **SELF-MAINTENANCE DIRECTIVE (permanent):** Claude MUST append to this file **every time** an
> experiment is run or an implementation/decision takes place — successes *and* missteps, whether
> the change left us **better or worse off** than before. Each entry records: what we did, why,
> the outcome, and the net effect on our position. This is the project's memory of *how* we got
> here, so a mentor (or a future session) can follow the reasoning, including dead ends. Keep it
> honest: record what was thrown away and what regressed, not only what worked.

**Project:** Assignment 3 — Yu-Gi-Oh SLM (fine-tune Gemma 2 2B vs. retrieval; systems A/B/C).
**Started:** 2026-08-01. All entries below are 2026-08-01 unless noted.

---

## Phase 0 — Foundations

**E1 · Read the brief.** Parsed `agent-prompt.md`: build 3 systems — A (base Gemma 2 2B, closed
book), B (our fine-tune, closed book), C (fine-tune + retriever). Thesis to reproduce honestly:
fine-tuning teaches answer *shape*, not *facts*; retrieval is the real win. Floors: ≥20 MB corpus,
≥2,000 clean QA pairs, ≥60 held-out with gold+evidence, recall@k for k=1/3/5/10, paired
significance test. Budget ≈$25. → *Position: oriented.*

**E2 · Domain + licensing check.** Chose **Yu-Gi-Oh**. Verified: Yugipedia prose = CC BY-SA 4.0
(free, attributed); card oracle text = © Konami (fair use only); YGOPRODeck = free API, data ©
Konami. → *Better: domain is legally defensible.*

**E3 · Plan + scaffold.** Wrote `PLAN.md` (7 phases 0–6), created repo scaffold, `git init`,
README/costs/requirements/.gitignore. Set question-type policy: RAG must answer
rulings/interactions/timing; verbatim card-text recall is out of scope. → *Better.*

**E4 · Conceptual gate.** Quizzed the 3-system design. Score 3.5/4. Corrected three
misconceptions: "weights ≠ context" (closed-book failure is missing weights, not missing context),
"the judge *compares* against gold+evidence, it doesn't recall," and "paired test removes
per-question difficulty." → *Better: fundamentals solid.*

**E5 · Eval methodology.** Decided: paired **bootstrap** CI (primary) + paired t-test
(comparability) + Wilcoxon (robustness); N≈60–80; compute MDE post-hoc; expect A-vs-B *not* to
separate (that non-result is a valid finding). → *Better.*

**E6 · Environment setup (with a stumble).** Verification caught that "accounts ready" was wrong:
3 Python installs, **HF token invalid**, **Modal not installed**. Created a project venv (3.12);
user re-authed HF (Ace-2504) and Modal (ace-2504). → *Worse then better: nearly hit a Phase-3
failure; caught and fixed early by verifying instead of trusting.*

---

## Chunking / retriever study (pre-Phase-1)

**E7 · Built the measurement rig.** `rag/chunking_study/` (fetch_sample, make_probes, benchmark).
Pulled 52 Yugipedia pages (0.32 MB); generated 60 Gemini flash-lite probes (with question-type
tags). → *Better: a real rig to make retriever decisions with data.*

**E8 · Ran 10 studies. Big findings that overturned defaults:**
- **Hybrid dense+BM25 >> pure dense** (recall@5 0.87 vs 0.74) — exact card-name matching matters.
- **bge-small (the brief's default) is the *weakest* embedder**; MiniLM-L6 best *and* fastest.
- Flat index ≥ IVF at our scale; top-k=5; title-aug small win; **score-based gating fails**
  (retrieved vs missed similarity distributions overlap); lore retrieves worst; feasibility trivial.
→ *Much better: turned "is 1000/150 good?" into a full retriever design study.*

**E9 · Follow-up: hybrid × best dense.** Hybrid with **MiniLM-L6** wins every k (recall@5 0.87,
@10 0.91). Locked retriever: **hybrid (MiniLM-L6 + BM25, RRF), chunk 1000/150, flat, top-k 5,
title-aug on**; Phase-2 gating uses a judge, not a score. Wrote `docs/initial-testing.md`. Brief
explicitly permits any embedder "if you say why," so switching off bge is justified. → *Better.*

---

## Verification pass

**E10 · Verified `assignment-verification.md` against the brief + live APIs.** Confirmed: 20 MB
floor, licenses, category scale (14.5k card pages, 770 archetypes). **Corrected overstatements:**
YGOPRODeck is 21 MB payload / 4.53 MB © effect text (not "5 MB usable"); "15 MB of card prose" is
optimistic; the ~35 MB total was an unverified estimate. Couldn't verify Fandom dump (HTTP 402).
Confirmed Section 1 faithful to the brief. → *Better: our numbers are now measured, not assumed.*

**E11 · Base-model ignorance probe.** Ran Gemma 2 2B base (local `serve_api` `gemma-base`) on 12
YGO questions → **~1.5/12**; it fabricates card text and gets basic rules wrong. **Domain
confirmed valid** (systems will separate). Logged into the VERIFIED section; moved probe scripts to
`docs/verification/`. → *Better: the load-bearing "base is ignorant" assumption is now measured.*

---

## Corpus collection (Phase 1)

**E12 · Recon.** `enumerate_and_estimate.py` showed **~64 MB available** (3.2× floor) — a surplus,
not a shortage. Decided **target-biased** composition (rulings + tips + archetypes + mechanics
majority; lore minority), ~25–30 MB. Found mechanics category (`Gameplay`) and the `Card Rulings`
(7,822) / `Card Tips` (14,981) namespaces. → *Better: composition is a choice, not a scramble.*

**E13 · Collection (with a bug caught in smoke test).** Smoke test revealed **alphabetical
selection bias** (allpages returns obscure-first) and thin cleaned yield. Fixed: enumerate full
namespace then **random-sample**; recalibrated caps. Full pull: **11,944 pages, 21.43 MB**, 82%
on-target / 18% lore, held-out split 1,791 / train 10,153 tagged at collection. → *Worse then
better: first pass would have biased the corpus; smoke test caught it.*

---

## Guidelines (a mix-up, corrected)

**E14 · Wrong guide, then right.** Wrote `filtering-system.md` from
`slm-finetuning-data.vercel.app` — but that site is the **fine-tuning** guide, not corpus cleaning.
Renamed it to `docs/fine-tuning-dataset-creation-guidelines.md` (Phase 2: teacher pipeline,
recipes, the §6 VALIDATE gauntlet, chat format) and stripped the Phase-1 content. → *Worse then
better: mis-scoped once, cleanly separated after.*

**E15 · Correct corpus-cleaning guide.** From `slm-data-vizuara.vercel.app` wrote
`docs/corpus-cleaning-system.md`: boilerplate regex, length/repetition/language filters, **MinHash-
LSH** dedup (not embedding cosine). → *Better.*

**E16 · Reverified against authoritative Session-2 slides.** Corrected: line filter **5→40 chars**,
doc floor **500→600**, **langdetect** primary (ASCII demoted to fallback); added the document-level
train/val split (99/1, seeded, leak-checked — "val is a thermometer, test is a judge") and the
dataset-card = DATA.md mapping. Scope note: slides target pretraining + tokenizer, which we
**skip** (Gemma's tokenizer; RAG). → *Better: cleaning values now trace to the authoritative source.*

---

## Specializing cleaning to our actual corpus (data-driven)

**E17 · Read the corpus, found the real patterns.** "This card can be searched by …" opens **7,145
lines** (89% of tips); `Konami…FAQ` citation remnants glued to 3,348 ruling sentences; section
headers (`Previously Official Rulings` ×756); category tags; and the generic **40-char line filter
would delete valid short rulings** (`This effect does not use the Chain.`). → *Better: the generic
guide was groundwork; the corpus told us what actually needs cleaning.*

**E18 · User decisions on patterns.** KEEP searched-by lists (RAG must answer "which cards search
X?"); strip citations (in-line), headers, category tags, symbol-junk; short-line rule **adapted**
(keep <40-char lines only if they end in `.`/`!`/`?`); repetition filter **off** (would risk the
searched-by lists). Specialized the cleaning spec. → *Better: corpus-specific, defensible in a viva.*

---

## Closing the RAG capability gap

**E19 · Noticed the corpus couldn't answer the basics.** Rulings/tips are *commentary about* cards
but the corpus had **no card stats or effect text** — "what is Raye's ATK / what does Raye do?" were
unanswerable (the very questions the base model failed). → *Worse: a real gap surfaced.*

**E20 · Added card-facts (YGOPRODeck).** `fetch_cardfacts.py` → **14,477 cards, 6.04 MB** rendered
as short passages (stats = free facts; effect text = labeled fair-use context). Gap closed:
"what does Raye do / its ATK / is it banned" now answerable. **Transparency** recorded in DATA.md:
snapshot 2026-08-01, newest card release **2026-11-12** (includes announced sets). Corpus now
27.47 MB raw — also resolves the post-clean headroom worry. → *Better: full card stack covered.*

**E21 · Inspected card-facts; decided no cleaning.** Found `''` flavor markers (221), `●` bullets
(1,184, meaningful — keep), near-duplicate effect text across *distinct* cards (MinHash 0.80 would
wrongly merge them), median 416 chars (600 floor would drop >50%). User reviewed full samples and
decided **card-facts need NO cleaning**; cleaning applies to Yugipedia only. Lowered the Yugipedia
doc floor **600→200** (data-backed: 0 pages <400 raw, 600 would drop 13.1% valid short rulings,
citation-stripping halves short pages). → *Better: avoided deleting >50% of card-facts and valid
short rulings by validating on our own data instead of trusting legal-corpus defaults.*

---

## Phase 1 — cleaning dry-run

**E22 · Corpus-cleaning dry-run.** Built `data/collect/clean_corpus.py` (C1 line/citation/short-line
→ C2 length 200/langdetect → C3 MinHash-LSH 0.80; card-facts untouched) and ran it in report-only
mode. Results: C1 removes just **3.1%** of chars (1,392 section headers, 628 boilerplate, 1,784
short non-sentence lines dropped; 4,856 citation/`===` in-line strips) — light, junk-only. **The
floor decision validated:** only **1 doc** falls under 200, but **1,855 docs sit in [200,600)** —
i.e. the slides' 600 floor would have deleted 1,855 valid short rulings. Language filter drops **0**
(all English). MinHash-LSH drops **147** near-duplicates. **Funnel: 11,944 (21.43 MB) → 11,796 kept
(20.63 MB)** — free-prose **clears the 20 MB floor, no re-collect needed**. Searched-by lines
preserved (5,694→5,580). One caveat noted: ~some of the 147 dedup drops are distinct-card *tips*
that share searcher lists (near-identical, low-info) — a minor decision point. → *Better: cleaning
is safe and measured; the 600→200 floor change alone saved 1,855 pages.*

**E23 · Cleaning executed (tips exempt from dedup).** User chose option (b) after seeing examples:
the dropped tips were distinct cards sharing identical searcher lists (e.g. `Don't Slip, the Dogs
of War` ≈ `Wedju Temple`), so dedup would break "which cards search X?". Exempted `tips` from
MinHash. Ran `APPLY=1` → wrote `data/corpus/corpus_clean.jsonl` (raw sources preserved). Result:
**11,911 prose docs / 20.74 MB kept** (32 genuine duplicates dropped — the Enneacraft ruling family;
all 5,694 searched-by pages preserved) **+ 14,477 card-facts = 26,388 total docs**. Free-prose
clears the 20 MB floor. Cleaning funnel recorded in DATA.md. → *Better: clean corpus finalized,
Phase 1 complete.*

## Phase 2 — fine-tuning pilot (planned)

**E24 · Planned the fine-tuning pilot.** Wrote `docs/finetune-pilot.md`, structured exactly like the
chunking study's `initial-testing.md`: a cheap mini end-to-end run (chunk ~120 train-split docs →
teacher QA gen → VALIDATE gauntlet → measure) plus an optional QLoRA smoke-train, to calibrate the
G1–G5 gates, measure yield/attrition/cost, and size the full Phase-2/3 run **before** spending the
budget. Defined the 11 exact outputs it returns and its limitations. Not executed. → *Better: Phase 2
de-risked before spend, same as chunking de-risked the retriever.*

**E25 · Verified a demo passage → found (and accepted) a rare superseded-rulings gap.** While
showing one grounded-QA generation (`Card Rulings:Uni-Horned Familiar`), Harman noticed the passage
read contradictorily. Verified against live Yugipedia wikitext: the page uses `<s>…</s>`
strikethrough to mark a *corrected/superseded* ruling; `strip_code` dropped the tags but kept the
struck text, gluing an outdated ruling to the current one. Cleaning removed *only* citations here
(no content lost). Scope check: **0/50** sampled rulings pages contain `<s>` → rare (~0–4%). Also
noted TCG/OCG section labels are flattened (content preserved). **Decision (b): accept + document**
as a known gap in DATA.md rather than re-collect. → *Neutral/honest: a rare data-quality gap found
by inspection, consciously accepted and recorded, not hidden.*

**E26 · Fine-tuning pilot (Part A) executed.** Ran chunk_sample → generate_qa → validate on 120
stratified train chunks → **276 pairs** (yield 2.36/chunk). Findings: format clean; **evidence
verbatim-in-passage 100%**; **87% interaction+timing** (our target types), 57% multistep; searched-by
low-value pairs = **0** (prompt controls the risk); dedup ~1%; **0 decontam collisions**. Attrition
under lexical-only gates is **~3%** (below the guide's 20–50%) → the **LLM judge grounding check
(G2b) is the real gate** and must be added for the full run. Cost <$0.20; full run projected <$1.
Held-out generation format works (15 items). → *Better: teacher pipeline validated, produces
high-quality on-target grounded pairs; full-run size (~1k chunks) and cost known.*

**E27 · Locked Phase-2 gauntlet decisions.** From the pilot: (i) **add the G2b LLM-judge grounding/
correctness check** (lexical gates alone gave ~3% attrition — too permissive), and (ii) **do NOT
cap question sub-types** — clarified that the fine-tuning guide's "balance" means difficulty mix
(already 57% multistep) + behavior task-types (we're QA-only), *not* interaction-vs-timing; the
earlier ≤45% cap was my over-extension. Updated `fine-tuning-dataset-creation-guidelines.md` G5
accordingly. → *Better: gauntlet faithful to the guide and aligned to the experiment's target.*

**E28 · Phase-2 pipeline built + launched (end-to-end, sequential, resumable).** Built
`finetune/common.py` + `generate_dataset.py` (chunk train-split at 1000/150, ~1,200 stratified
chunks → grounded QA), `build_heldout.py` (≥60 `{id,question,gold,evidence}` from held-out pages,
verbatim-evidence check), `validate_gauntlet.py` (G1 format → G2 **judge** grounding/correctness →
G3 dedup 0.92 → G4 decontam 0.90 → G5 tag-only → chat/messages `train.jsonl` + funnel). Showed the
judge prompt discriminating (correct pair→yes, corrupted→no) before running. All scripts resumable
(skip finished work). Kicked off the full run (~4k flash-lite calls, ~2–3.5 h, background). Locked
decisions: judge gate ON, no sub-type cap, chat format, system+user+assistant messages. → *Better:
Phase 2 implemented end-to-end and running.*

**E29 · Phase 2 COMPLETE.** Full run finished (much faster than the ~2–3.5 h estimate). 1,200
chunks → **2,796 raw pairs** → gauntlet → **`data/train.jsonl` = 2,683 pairs** (≥2,000 ✅) and
**`data/heldout.jsonl` = 60 items** (≥60 ✅). Judge caught **81 wrong** answers (+7 weak partials);
dedup 25; decontam 0. Final mix **85% interaction+timing**, 55% multistep. Sanity check confirmed:
kept pairs clean/grounded; rejected pairs were genuinely wrong (Tree Otter unsupported claim, wrong
Shrink+Black Garden interaction); held-out items have verbatim evidence. Total attrition ~4% —
low, because flash-lite produces high-quality grounded pairs and the judge confirms 96.6% while
still catching the real errors. → *Better: SFT set + held-out set built and validated.*

## Current status (as of last entry)

- **Corpus collected:** Yugipedia prose 21.43 MB (11,944 pages) + card-facts 6.04 MB (14,477 cards)
  = **27.47 MB raw**; held-out page splits tagged; card-data cutoff logged.
- **Retriever design locked** (hybrid MiniLM-L6 + BM25, 1000/150, flat, top-k 5).
- **Cleaning spec finalized** (`docs/corpus-cleaning-system.md`) — Yugipedia only; card-facts
  untouched; doc floor 200.
- **Phase 1 COMPLETE** (E23): `corpus_clean.jsonl` = 26,388 docs; free-prose clears the 20 MB floor.
- **Phase 2 COMPLETE** (E29): `data/train.jsonl` = 2,683 pairs, `data/heldout.jsonl` = 60; funnel in
  DATA.md; both floors cleared.
- **Next step:** Phase 3 — QLoRA fine-tune of `google/gemma-2-2b-it` on Modal (L4/A100), loss curves,
  val perplexity, push to HF Hub, serve behind a scale-to-zero endpoint.
- **Not yet started:** Phase 2 (QA generation + VALIDATE gauntlet), Phase 3 (QLoRA fine-tune),
  Phase 4 (retriever build + recall@k), Phase 5 (eval), Phase 6 (site + report).

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

**E30 · Phase 3 planned + prereqs verified.** Verified all Phase-3 infra is ready: Modal profile
`ace-2504`, Modal `hf-token` secret present, HF `Ace-2504` (write), **Gemma 2 2B gated access OK**
(downloaded config.json), train/heldout data present, budget fine. Only gap = the training script
(not built). Wrote `docs/finetune-training.md`: one QLoRA closed-book QA fine-tune = System B (System
C = same model + retrieval at inference); proposed config (r16/α32, all-linear targets, LR 2e-4,
3 epochs, seq 512, bf16, L4), train/val 2% split (separate from the 60-item test set), fold system
into user turn, push adapter to HF Hub, scale-to-zero endpoint + the adapter-race trap noted.
Not built yet. → *Better: Phase 3 fully specced, infra green.*

**E31 · Phase 3 first QLoRA run — trained but overfit; re-running with early-stop.** Built
`train/modal_finetune_gemma.py` (Gemma-2-2b-it, QLoRA r16/α32, all-linear, LR 2e-4, seq 512, L4,
completion-only loss, Gemma system-fold). Two quick fixes on first launches: Modal 1.5.3 removed
`Mount` → switched to `image.add_local_file`; trl 0.9.6 needed `rich` → added. Run then succeeded:
train 2630 / val 53, adapter pushed to `Ace-2504/gemma-2-2b-yugioh-qa`, loss curve saved. **But the
data revealed overfitting:** val loss bottomed ~1.35 (≈epoch 1) then rose to 1.69 by epoch 3
(reported val ppl 5.407 = the over-trained endpoint; best point ≈ **ppl 3.86**, which would beat the
4.26 reference). Made the documented call to **re-run with `load_best_model_at_end` + early stopping
(patience 3)** so we push the best checkpoint, not the overfit one. → *Worse then better: 3 epochs
overfit the 2.6k-pair set; early-stop keeps the true minimum.*

**E32 · Phase 3 training COMPLETE (best checkpoint).** Early-stop re-run landed the best model at
~epoch 0.9: **val perplexity 3.872** (eval_loss 1.354) — **beats the 4.26 reference**. Early stopping
confirmed the overfitting diagnosis (no val improvement after epoch 0.9 → stopped, loaded best). Best
adapter pushed to `Ace-2504/gemma-2-2b-yugioh-qa`; loss curve at `train/loss_curve.png` (sent to
Harman). Drafted a proper model card at `train/MODEL_CARD.md` (NOT auto-pushed — modifying the public
HF repo needs Harman's OK). Both L4 runs ≈ $0.60. → *Better: System B trained, beats the reference,
non-overfit.*

**E33 · Model card pushed + local serving live via cloudflared.** Pushed `train/MODEL_CARD.md` →
`README.md` on the HF repo (Harman authorized). Wrote `train/serve_local.py` (FastAPI: Gemma-2-2b-it
+ adapter, 4-bit on the RTX 3060, `/generate` with optional `context` for System C later). Fixes en
route: installed CUDA torch (2.5.1+cu121) — the venv had CPU torch; `peft` missing locally →
installed; transformers 5.x `apply_chat_template` now returns a dict → fixed the generate call.
Server live on port 8100 (`device cuda:0`), exposed publicly via a cloudflared quick tunnel
(**https://advice-arrivals-closure-murphy.trycloudflare.com** — ephemeral, changes on restart).
Verified end-to-end: closed-book answers are coherent but imperfect on specifics (e.g. Raye's GY
effect) — exactly the System-B gap retrieval (System C) is meant to fix. → *Better: fine-tune is
served and publicly reachable.*

**E34 · Phase 4 retriever test planned.** Wrote `docs/retriever-test.md` (same pattern as the
chunking study + QA pilot): build the real retriever over the full 26,388-doc corpus (chunk 1000/150
title-aug → MiniLM-L6 FAISS flat + BM25 hybrid) and measure **recall@k on the 60 real held-out items**
(dense/BM25/hybrid, k=1/3/5/10). Purpose: re-confirm the chunking-study config (chosen on a 0.32 MB
proxy) at full scale and produce the required recall@k table — the precondition for System C
("measure recall before blaming the model"). Defined the 7 exact outputs + limitations. Not executed.
→ *Better: Phase 4 de-risked/specced before build.*

**E35 · Phase 4 retriever built + recall@k measured — System C viable.** Built `rag/build_index.py`
(full corpus → **42,412 chunks**, MiniLM-L6 FAISS flat + BM25, title-aug; embedded in 50s on GPU),
`rag/retrieve.py` (Retriever + `/retrieve` FastAPI endpoint, hybrid RRF), `rag/recall_at_k.py`.
**Recall@k on the real 60 held-out (100% coverage): hybrid r@5 = 0.93** (dense 0.92, bm25 0.87) →
System C viable. Config held at scale (≥ the 0.32 MB proxy's 0.87). Notable: **BM25 alone wins r@1
(0.82)** — questions name specific cards; hybrid wins r@3+; top-5 hybrid confirmed. Targets retrieve
best (rulings r@5 0.96, cardfacts 0.93). Was NOT a re-run of the design study — this is the mandated
build + recall@k on the real held-out. → *Better: retriever is real, recall@k table delivered, System
C green-lit.*

**E36 · Phase 5 evaluation planned.** Wrote `docs/eval-plan.md`: run A (base, closed-book) / B
(fine-tune, closed-book) / C (fine-tune + top-5 retrieval) over the 60 held-out; one model in memory
with `peft disable_adapter` for A (sidesteps the adapter-race trap, keeps A/B on identical base);
greedy decoding. Judge = reference-grounded (question+gold+evidence), blind + pointwise, rubric /10
(correctness 5 / completeness 2 / groundedness 2 / clarity 1; groundedness→0 on invented figures;
refusal beats confident error). Stats = paired bootstrap CI + t-test + Wilcoxon on A-vs-B and B-vs-C.
Deliverables: responses/verdicts/leaderboard.json + ≥3 disagreements; harness idempotent. Hypothesis
(to test, not assume): **A≈B, C≫both**. Not executed. → *Better: the experiment's verdict phase is
specced.*

**E37 · Phase 5 evaluation COMPLETE — the experiment is answered.** Ran A/B/C over the 60 held-out
(endpoint-reuse: `:8100` use_base for A, `:8200` retrieval for C), judged blind (reference-grounded,
Gemini flash-lite), aggregated with paired bootstrap + t + Wilcoxon. **Leaderboard /10: A 3.98 · B
5.25 · C 8.05.** Both comparisons significant: **A-vs-B +1.27** (p=0.007), **B-vs-C +2.80** (p<0.001).
**Honest finding:** retrieval is the dominant win (C≫B),
AND fine-tuning *also* significantly beat base (B>A) — where the reference found it did not. Breakdown
shows B's gain is mostly **groundedness** (0.18→0.87 = tighter, less-hallucinatory *shape*), not facts
(facts arrive with retrieval: C correctness 3.85 vs B 2.35). 3 disagreements quoted (all A/B
hallucinate, C returns gold). Deliverables: responses/verdicts/leaderboard.json. → *Better: the whole
experiment measured; a real, defensible, partly-contrarian result.*

**E38 · Phase 6 (site + report) planned.** Wrote `docs/site-report-plan.md`: a single `/ask` backend
(A via use_base, B, C via retriever+generate → `{A,B,C,passages}`) behind a durable public URL
(Modal scale-to-zero vs local-3060+cloudflared tunnel — decision pending); a Next.js Vercel site
showing A/B/C live side-by-side + C's retrieved passages + the real leaderboard & recall@k tables
(no hardcoded numbers), phone-responsive, research-lab theme; and the one-page `report.pdf` (headline
table, one plot, expected-vs-disagreed = the B>A finding, biggest time-sink). Not built. → *Better:
final packaging phase specced.*

**E39 · Full results dossier built (all statistics laid out).** At Harman's request (review-before-
one-pager), compiled every statistic into `report/results-dossier.html` and published it as an
artifact: A/B/C leaderboard + SE bar chart, paired significance, rubric-component breakdown, recall@k
(by method + source), the QLoRA loss curve (embedded) + val perplexity, the data funnel, base-probe
1.5/12, the 3 disagreements, cost (~$3), and the config. CVD-safe A/B/C palette (validated both
themes); numbers all trace to the committed JSON. Power cut mid-task (local servers :8100/:8200/tunnel
stopped — restart when building the site). → *Better: Harman has a single reviewable stats reference
to draw the one-page report from.*

**E40 · Phase 6 built — site deployed, report written, README done.** After power-cut recovery:
restarted the servers, added a **`/ask` gateway** to `serve_local.py` (A via use_base, B, C via
retriever + generate, + CORS) behind a cloudflared tunnel (verified live A/B/C — e.g. Dark Magician
ATK: A "2000" wrong, B "1000" wrong, C "2500" correct). Built `site/index.html` (research-lab theme,
Cobalt + swatch picker, live `/ask`, C's passages, leaderboard + recall@k tables), **deployed to
Vercel → https://site-eight-liard-61.vercel.app** (public, HTTP 200). Wrote the one-page **`report.pdf`**
in Harman's voice (fpdf2; the five required points + A/B/C bar chart). Built `report/results-dossier.html`
(full stats artifact). Updated README to the submission spec (reproduce-in-order, HF link, live URL,
endpoints, cost). → *Better: all six parts of the assignment now have deliverables.*

**E41 · Repo stripped to the brief's minimal structure + pushed to GitHub.** Moved `report.pdf` to
root, folded the QA-generation scripts into `data/generate/`, removed the process/meta files from
tracking so the repo is exactly `data/ train/ rag/ eval/ site/ report.pdf README.md` (33 files).
Created the **private** GitHub repo **Ace-2504/does-my-ai-know-yugioh** and pushed `main`. → *Better: clean
submission repo — but the strip initially deleted the process files from disk too.*

**E42 · Restored the local-only files (course-correction).** Harman wanted the docs/story/etc. kept
*locally* and only excluded from GitHub, not deleted. Restored every removed file from commit
`3c488db` back to disk and gitignored them (`docs/`, `story.md`, `costs.md`, `PLAN.md`,
`agent-prompt.md`, `rag/chunking_study/`, `finetune/pilot/`, `report/` extras). No code lost — the
`finetune/` scripts had been *moved* to `data/generate/`, not deleted. → *Recovered: local has
everything, GitHub stays minimal.*

**E43 · Individual model frontends + demo-unavailable.** Built three separate Vercel sites — base /
finetune / rag (`harman-ygo-{base,finetune,rag}.vercel.app`), each a single-system page — plus a hub
on the arena linking to them and back. Added on-load endpoint probing that shows "demo unavailable"
when the tunnel is down. Frontends kept local-only in `frontends/` (generated by `build.py`).

**E44 · Combined arena redesign.** Rebuilt `site/index.html` toward the 15-model arena layout:
parchment default, Harman-Sandhu branding, GitHub button, centered hero, and tabbed Arena / detailed
Leaderboard / How-the-judge-works / Corpus (sources + split) / Cost sections.

**E45 · Theme fidelity pass (from the real source repos).** Harman flagged the research-lab theme
wasn't followed exactly — a green (teal `--accent-2`) ask button instead of orange, badging not
matching, sections not clearly separate. Read the actual `D:\slm-arena-15` + `D:\slm-frontends`
source and embedded the **verbatim `globals.css`** (6 themes incl. Nord, exact parchment `--fg
#211f1a`), rebuilding both arena and individual pages to the reference: `.brand` authorship pill,
conic-gradient theme swatches, `.badge`/`.badge-accent` status, always-orange `.btn-primary` (fixes
the green button), a `.btn-primary`/`.btn` tab bar with each tab its own `.section` panel, and
`target="_blank"` cross-links. Probe switched to `/health`. Restarted the model server + tunnel twice
across sessions (tunnels are ephemeral; endpoint now `stroke-valve-easter-sampling`). → *Better: the
theme is the reference now, byte-for-byte on tokens.*

**E46 · Exact costs + individual cost section removed.** Harman gave the real invoiced figures — Modal
GPU **$0.36**, Gemini API **$2.00** = **$2.36** total. Replaced the `< $x` estimates in the arena Cost
tab with the two honest bills (no fabricated per-stage split), updated README + DATA.md, and **removed
the "cost to build" section from the individual pages** (no per-system split exists). Rotated the
cloudflared tunnel (old one stopped forwarding) → `university-hindu-excel-welding`; re-synced all 4
sites and redeployed. Committed `b8bc9c2`. → *Better: cost is now measured, not estimated.*

**E47 · All 4 sites public — the gating was legacy aliases, not framework or auth.** Harman correctly
pushed back on disabling Vercel Authentication (it's on ecosystem-wide) and asked if switching to
Next.js would help. Diagnosed with evidence: framework is irrelevant (auth runs at the edge; the
static `harman-ygo-slm` is public *with* auth on). The real cause — `vercel alias set` had created
**legacy aliases**, not **Production-connected project domains**, so Standard Protection never exempted
them (each project's real Production domain, e.g. the auto `base-inky-seven.vercel.app`, *was* already
public). Fix, no auth change: in each of the `base`/`finetune`/`rag` projects → Domains → **Add Existing
→ harman-ygo-{…}.vercel.app → Connect to Production**. Verified all four **200/public**. Root lesson:
the ecosystem's 13 sites "just work" because each project is *named* its final domain (project
`slm-gemma-qa-harman` → auto domain `slm-gemma-qa-harman.vercel.app`); name the project the domain and
it's public-with-auth from the first deploy. Also fixed the `research-lab-theme` skill (warm parchment
ramp, `slm-theme` key, `.brand` pill recipe, per-item-accent anti-pattern) so a fresh thread reproduces
the look. → *Shipped: 4 public sites, exact costs, minimal private repo, skill hardened.*

**E48 · RAG model published to HF + per-system HF links.** Put **System C** on HF as
[`Ace-2504/gemma-2-2b-yugioh-rag`](https://huggingface.co/Ace-2504/gemma-2-2b-yugioh-rag): same QLoRA
adapter weights as the QA model (honest card — the novelty is the retriever at inference, not new
weights) + a RAG-focused card, **no "Reproduce" section** (Harman had deleted it from the QA card too).
Did NOT upload the retriever index/chunks (they embed © Konami card text kept as non-redistributed
fair-use context; rebuildable). Added the RAG link to the README, and made the individual sites link
their correct model (base → `google/gemma-2-2b-it`, B → `-qa`, C → `-rag`). Note: Harman had refined
the GitHub README directly (4 commits) — rebased onto his version, kept his wording, re-applied only the
RAG link. Pushed `786bf4a`. → *Better: both trained variants are first-class HF entries.*

**E49 · Arena upgrade — live judging + categorized dropdown, and the full repo goes public.** Added a
`/judge` endpoint to `serve_local.py` (the eval's reference-grounded rubric, live) and rebuilt the arena
ask box into a **category dropdown** of 20 teacher-generated questions that ship with gold+evidence (so the
live judge grades against a reference), plus a free-text box (graded from the judge's own knowledge). Also:
left-aligned the hero + a plain-language Yu-Gi-Oh intro; scoped the individual "what this is" text to `#000`
on parchment only (theme-aware elsewhere); made the corpus section identical arena↔individual; removed every
"class"-comparison reference (docs, MODEL_CARD, report, dossier); and **un-ignored the process files so the
full project is on GitHub** (68 files — docs/, story.md, report/, chunking_study/, finetune/pilot/,
frontends/), keeping only costs.md / PLAN.md / agent-prompt.md + heavy/© data out. → *Better: the demo
judges live and the repo tells the whole story.*

**E50 · README → full portfolio README.** Drafted `readmeV2.md` (contents, intro, live demos, architecture
diagram, corpus, judge, findings, detailed Prerequisites→Process→Outcome reproduce, cost, limitations) and,
on approval, made it the real `README.md`.

**E51 · Report tweaks.** Added a "What I learnt" section (reader-ceiling · reference-grounded judge ·
match-the-retriever-to-the-domain), then removed the bottom footer line at Harman's request.

**E52 · Repo renamed.** `Ace-2504/ygo-slms` → **`Ace-2504/does-my-ai-know-yugioh`** (curiosity + SEO); all
in-repo GitHub links updated, sites redeployed; confirmed repo SEO needs no framework change.

**E53 · Analysis pass (re-reviewable artifacts).** Re-ran the 12-question base-ignorance probe → **3/12**
(orig ~1.5), saved per-question to `docs/verification/base-probe-results.md`. Ran a **separate eval on the
20 arena dropdown questions** → A 2.05 / B 2.55 / C 8.30; fine-tuning *not* significant here (+0.50, the set
is fact-lookup-heavy) while retrieval wins bigger (+5.75) — a cleaner cut of "shape not facts"
(`eval/arena-eval-results.md`, local). Documented the **held-out composition** in DATA.md (45% cardfacts /
45% rulings / 8% archetype / 2% mechanics — the bias behind the original 60). Explained with data that the
fine-tune answers short because **100% of its training answers are <40 words (median 17)** — not truncation
— and that System C's 8.05 ceiling is the reader, not the retriever (recall@5 already 0.93).

**E54 · 60 equal-split questions generated, then the leaderboard paused.** Generated **60 equal-split
arena questions (15/category)** (`.run/arena_questions.json`) to grade A/B/C for a balanced second
leaderboard alongside the biased original-60 — but Harman paused the eval before it ran. The 60 are staged
locally only; the deployed arena still shows the 20-question dropdown. (Not run, not deployed.)

**E55 · Prompt-tweak experiment on System C's short answers (Blackwing) — a clean negative result.**
Tested whether a "be complete" instruction fixes the fine-tune's terse answers, on *"what is the effect of
Blackwing Full Armor Master?"* (original C: 27 words, 6/10, omits the effect): **(a)** mild "answer fully"
→ 30 words, **5/10**, ignored; **(b)** strong directive that *named* the mechanics (Wedge Counters, take
control, destroy) → 49 words, **8/10** — but that leaks the answer into the prompt, unusable in production;
**(c)** generic strong push ("say everything it does", no hints) → 42 words, **3/10** — **backfired**: forced
to write more, the 2.6B model *fabricated* (invented Normal Summon / Simoon), groundedness → 0. Conclusion:
**prompting can't fix it** — the brevity is protective (short = grounded); forcing length without content
makes a small model hallucinate. Real fixes are retraining on longer gold answers or a bigger model. →
*Better: the short-answer question is now answered with data, and a cheap "fix" was ruled out honestly.*

**E56 · Power-cut recovery + tunnel rotation.** After a power cut, restarted the model server (`:8100`),
retriever (`:8200`), and the cloudflared tunnel — which rotated to
`latinas-kennedy-exams-intervention.trycloudflare.com`. Updated `BASE` in `site/index.html` +
`frontends/build.py` and redeployed all four Vercel sites; verified `harman-ygo-{slm,base,finetune,rag}`
are 200 and now point at the live tunnel. → *Better: the live demos work again; only the ephemeral tunnel
URL changed, nothing else in main.*

---

> ### The RAG study — **the following experiments were conducted in a *cloned* repo**
> (`vizuara-assignment-3-yugioh-test`), leaving this repository's code untouched. They ask whether System C's
> 8.05 ceiling is the retriever or the reader. Full writeup: [`RAG-STUDY.md`](RAG-STUDY.md); summarized here
> for the record.

**Clone-C1 · Reranking (cross-encoder, top-20 → 5).** No help — slightly worse: biased-60 **8.05 → 7.55**,
equal-split-60 **8.25 → 7.37**. Debug: recall@5 identical (0.933), gold at **rank 1** either way, so the
reranker isn't mis-ranking — the drop is reader instability on reshuffled context.

**Clone-C2 · "Look deeper" / wider retrieval pool.** Recall rose **0.93 → 0.95 → 0.97**, but the score stayed
flat. Recall ≠ answer quality.

**Clone-C3 · Chunk-truncation fix (adjacent-chunk expansion ±2).** A card's effect split across chunks
(Endymion) was reconstructed back into the context — **and the answer stayed incomplete** (the reader ignored
the recovered clause). The bug affects only 0.2% of cards.

**Clone-C4 · Six non-retraining reader fixes (Blackwing + Endymion).** Self-consistency, self-verification,
and quote-then-answer all failed; the only reliable win was **a stronger reader on the same context → 6/10 to
10/10** — the controlled "hold context, change reader" confirmation.

**Clone-C5 · Reviewed 8 papers on small-model RAG.** They converge: the reader is the bottleneck; retrieval
and prompt tricks don't fix it; preference-tuned RAFT or a stronger reader do.

**RAG-study conclusion:** retrieval is *not* the bottleneck — once recall is high, reranking / deeper
retrieval / chunk-repair each improve retrieval yet add zero answer quality; the **2.6B reader is the
ceiling.** Full narrative + numbers in the clone's `docs/rag-improvement-story.md` (local).

## Current status (as of last entry)

## Current status (as of last entry)

- **Corpus collected:** Yugipedia prose 21.43 MB (11,944 pages) + card-facts 6.04 MB (14,477 cards)
  = **27.47 MB raw**; held-out page splits tagged; card-data cutoff logged.
- **Retriever design locked** (hybrid MiniLM-L6 + BM25, 1000/150, flat, top-k 5).
- **Cleaning spec finalized** (`docs/corpus-cleaning-system.md`) — Yugipedia only; card-facts
  untouched; doc floor 200.
- **Phase 1 COMPLETE** (E23): `corpus_clean.jsonl` = 26,388 docs; free-prose clears the 20 MB floor.
- **Phase 2 COMPLETE** (E29): `data/train.jsonl` = 2,683 pairs, `data/heldout.jsonl` = 60; funnel in
  DATA.md; both floors cleared.
- **Phase 3 training COMPLETE** (E32): `Ace-2504/gemma-2-2b-yugioh-qa` adapter on HF Hub, val
  perplexity **3.872** (beats 4.26 ref), loss curve saved. This adapter = System B (System C = it +
  retrieval).
- **Phase 3 COMPLETE** (E33): adapter + model card on HF; served locally on the 3060 via
  `train/serve_local.py` + cloudflared tunnel. (A durable scale-to-zero Modal endpoint can replace
  the ephemeral tunnel later for the site.)
- **Phase 4 COMPLETE** (E35): 42,412-chunk hybrid index + `/retrieve`; recall@k hybrid r@5 **0.93**.
- **Phase 5 COMPLETE** (E37): A 3.98 / B 5.25 / C **8.05**; A-vs-B +1.27 (sig), B-vs-C +2.80 (sig).
- **Phase 6 COMPLETE** (E40); `report.pdf` written (Harman's voice, 5 points); README to submission spec.
- **Repo minimal + on GitHub** (E41–E42): private **Ace-2504/does-my-ai-know-yugioh**, `main` = the brief's structure
  (33 files); process/meta files kept locally, gitignored.
- **Frontends** (E43–E45): combined arena live at **https://harman-ygo-slm.vercel.app** (parchment,
  tabs, corpus + cost, GitHub button); three individual sites **harman-ygo-{base,finetune,rag}.vercel.app**;
  research-lab theme matched verbatim from the reference repos.
- **All 4 sites public** (E47): `harman-ygo-{slm,base,finetune,rag}.vercel.app` all 200, auth kept on
  (fixed by connecting each to a Production project domain, not by disabling protection).
- **Costs finalized** (E46): $0.36 Modal + $2.00 Gemini = $2.36 (arena + README + DATA.md).
- **Skill hardened** (E47): `research-lab-theme` now matches this ecosystem out of the box.
- **Remaining / open:**
  - Keep the model server (`:8100`) + retriever (`:8200`) + cloudflared tunnel up while grading;
    tunnels are ephemeral — on restart: edit `BASE` in `frontends/build.py`, run
    `python frontends/build.py deploy`, then redeploy `site/`. (No domain re-work needed — the
    Production domains persist across deploys.)

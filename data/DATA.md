# DATA.md — Yu-Gi-Oh corpus & dataset

> Honest counts at **every** stage, from raw documents to surviving pairs. Numbers marked
> `TBD` are filled in **as extraction runs** — they must be measured, never estimated.
> Verified source/license facts come from `docs/assignment-verification.md` (VERIFIED section).

## Domain

Yu-Gi-Oh! (rulings, card interactions, timing/chains, archetype mechanics, lore). Chosen
because Gemma 2 2B **base is measured to be ignorant** of it (probe: ~1.5/12 correct, confident
fabrication on modern cards/rulings — see `docs/verification/probe_gemma_base.py`), so systems
A/B/C can actually separate.

## Sources, licenses, and what counts toward the 20 MB floor

The 20 MB floor is **free-licensed prose only.** Copyrighted card text and tabular data are
fair-use *fact supplements* and do **not** count toward it.

| Source | Content used | License | Counts toward 20 MB floor? |
|--------|--------------|---------|----------------------------|
| **Yugipedia** (MediaWiki API, by category) | editorial prose: archetype/series pages, character bios, episode plots, card-page **lore/ruling/tips** sections, mechanics/glossary | **CC BY-SA 4.0** (attributed) | **Yes** — this is the spine |
| Yugipedia card **effect text** | printed card oracle text | © Konami / 4K Media (fair use) | **No** — paraphrase/facts only |
| **YGOPRODeck** v7 API → `cardfacts` source | rendered card passages: stats/type/attribute/archetype/banlist (facts) **+ effect text** | free API; stats free, effect text © Konami (fair use) | **No** — fact supplement (stats free, effect text fair-use context) |
| Fandom XML dump (2.4) | extra prose / redundancy | CC BY-SA (unconfirmed — see note) | Yes, after dedup — **pending** |

**Attribution:** Yugipedia prose reused under CC BY-SA 4.0 with attribution to Yugipedia and
share-alike. **Note:** Fandom dump availability/license returned HTTP 402 during verification and
is **not yet confirmed**; treated as optional top-up only.

**Verified availability (2026-08-01):** OCG card pages 14,515 · TCG 14,198 · Archetypes 770 ·
Anime cards 9,587 · Series 392 · Video games 74 (GX-episodes subcat 184). YGOPRODeck returns
14,477 cards (21.13 MB JSON; 4.53 MB of © effect text). Free CC BY-SA prose ≥ 20 MB is reachable
from bios + episodes + archetype/series + card lore/ruling prose.

## Collection method

- **Fetch:** MediaWiki API by category —
  `api.php?action=query&generator=categorymembers&gcmtitle=Category:<Name>&gcmlimit=max&prop=revisions&rvprop=content&rvslots=main&format=json`
  (descriptive User-Agent; polite rate limiting). Target categories: **TBD (finalized list)**.
- **Clean:** strip templates/infoboxes/navboxes/tables/image tags to plain prose
  (`mwparserfromhell` + post-filtering); drop appendix sections (references/external links).
- **Dedup:** cross-source de-duplication so YGOPRODeck/Fandom do not double-count Yugipedia; drop
  near-duplicate templated boilerplate.
- **Held-out reservation:** a slice of source **pages** is tagged *held-out-only* **before** any
  QA generation, so held-out passages never enter training (leakage structurally impossible).

## Chunking

Parameters chosen by the retriever design study (`rag/chunking_study/`, results in
`docs/initial-testing.md` §6). Measured on a 0.32 MB proxy — **re-confirm on the full corpus in
Phase 4.**

| Parameter | Value | Basis |
|-----------|-------|-------|
| Chunk size (chars) | 1000 | size sweep |
| Overlap (chars) | 150 | overlap sweep |
| Retrieval method | **hybrid dense + BM25 (RRF)** | hybrid beat pure dense clearly |
| Dense embedding model | **all-MiniLM-L6-v2** (384-d, normalized) | best dense recall + fastest; brief permits any embedder "if you say why" |
| Retrieval top-k | 5 | recall plateaus after 5 |
| Index | flat (FAISS) | flat ≥ IVF at this scale |
| Title-augmentation | on | marginal recall gain |
| Phase-2 quality gate | LLM judge (NOT a retrieval-score threshold) | score-gating shown unreliable |

**Retriever method & why (stated for the record):** we use **hybrid retrieval — Reciprocal
Rank Fusion of dense `all-MiniLM-L6-v2` embeddings and lexical BM25** over 1000/150-char chunks,
flat FAISS index, top-5. *Why:* (1) Yu-Gi-Oh questions hinge on exact card/term names that dense
embeddings blur but BM25 matches exactly — measured hybrid recall@5 0.87 vs pure-dense-bge 0.74;
(2) among dense models MiniLM-L6 gave the best recall *and* the fastest encoding, and the brief
explicitly allows any embedder with justification; (3) flat index is sub-millisecond at our
scale (~24.5k chunks) where IVF underperforms and cannot train well. These come from a 0.32 MB
proxy study (`docs/initial-testing.md` §6) and are **re-confirmed on the full corpus in Phase 4.**

## The funnel (measured counts — fill as we go)

| Stage | Count |
|-------|-------|
| Raw Yugipedia prose fetched (pre-cleaning, 2026-08-01) | **11,944 pages · 21.43 MB** |
| Raw card-facts fetched (YGOPRODeck, 2026-08-01) | **14,477 cards · 6.04 MB** |
| — reserved as held-out-only (never trained) | prose 1,791 / cardfacts 2,171 |
| After cleaning — Yugipedia prose kept | **11,911 docs · 20.74 MB** (clears 20 MB floor) |
| Total cleaned corpus (prose + card-facts) | **26,388 docs** (`corpus_clean.jsonl`) |
| Chunks used for QA generation | 1,200 (train-split, stratified, 1000/150) |
| QA pairs generated by teacher | 2,796 |
| QA pairs surviving the gauntlet (`train.jsonl`) | **2,683** ✅ (≥ 2,000) |
| Held-out test items (`heldout.jsonl`, gold + evidence) | **60** ✅ (≥ 60) |

**Phase-2 QA gauntlet funnel** (`finetune/gauntlet_report.json`, run 2026-08-01):

| Gate | Pairs | Dropped |
|------|-------|---------|
| Raw generated | 2,796 | — |
| G1 format | 2,796 | 0 |
| G2 judge (grounding/correctness) | 2,708 | 88 (81 `no` + 7 weak `partial`; verdicts: yes 2,700 / no 81 / partial 15) |
| G3 near-dup dedup (0.92) | 2,683 | 25 |
| G4 decontaminate vs held-out (0.90) | 2,683 | 0 (structural page-split holds) |
| **Final `train.jsonl`** | **2,683** | |

Type mix (final): interaction 66% + timing 19% = **85% on-target**; definition 8%, other 4%, lore 3%.
Difficulty: 55% multistep / 45% lookup. Chat/messages format (system+user+assistant).

**Raw composition (pre-cleaning, per source):**

| source | role | pages/cards | MB |
|--------|------|-------|-----|
| tips | on-target (Yugipedia prose) | 6,389 | 8.47 |
| rulings | on-target (Yugipedia prose) | 4,394 | 5.90 |
| archetype | on-target (Yugipedia prose) | 616 | 2.74 |
| mechanics | on-target (Yugipedia prose) | 152 | 0.40 |
| lore-char | lore (Yugipedia prose) | 219 | 1.31 |
| lore-ep | lore (Yugipedia prose) | 174 | 2.61 |
| **Yugipedia prose subtotal** (counts toward 20 MB free floor) | | **11,944** | **21.43** |
| cardfacts | card identity (YGOPRODeck) — stats free + effect text fair-use | 14,477 | 6.04 |
| **total corpus (raw)** | | **26,421** | **27.47** |

Yugipedia prose is 82% on-target / 18% lore. **Card-facts** was added to close the RAG gap
("what does X do / what are its stats / is it banned") that the rulings/tips corpus alone cannot
answer. Only the **21.43 MB Yugipedia prose counts toward the 20 MB free-prose floor**; card-facts
effect text is © Konami fair-use context. **Note:** the Yugipedia figure is *raw*; cleaning shrinks
it (in-line citation strips, header/category drops, MinHash-LSH dedup — searched-by lists are
*kept*), so the post-clean free-prose total is re-measured after the cleaning pass.

### Cleaning funnel (Yugipedia prose; card-facts pass through untouched)

Per `docs/corpus-cleaning-system.md`, executed 2026-08-01 → `corpus_clean.jsonl`:

| Stage | Docs | Notes |
|-------|------|-------|
| Raw Yugipedia | 11,944 (21.43 MB) | |
| C1 line/citation/short-line | 11,944 (−3.1% chars) | 1,392 headers + 628 boilerplate + 11 symbol + 1,784 short lines dropped; 4,856 citation/`===` in-line strips |
| C2.1 length ≥200 | 11,943 | only 1 dropped; **1,855 in [200,600) saved** vs the slides' 600 floor |
| C2.3 language (English) | 11,943 | 0 dropped |
| C3 MinHash-LSH 0.80 (tips exempt) | **11,911 (20.74 MB)** | 32 genuine duplicates dropped (e.g. Enneacraft ruling family); all searched-by lists preserved |

### Card-data cutoff (transparency)

The `cardfacts` source is a **YGOPRODeck v7 snapshot fetched 2026-08-01**. The newest card release
date present in the data is **2026-11-12** (YGOPRODeck lists announced upcoming sets, so the
snapshot includes some not-yet-released cards). The model's card knowledge therefore reflects the
Yu-Gi-Oh card pool up to that date; cards printed after it are out of scope.

### Known limitations & gaps (dataset card "known gaps")

- **Superseded rulings (`<s>` strikethrough) retained — rare (~0–4% of rulings pages).** Yugipedia
  marks corrected/outdated rulings with strikethrough; `strip_code` (at collection) removed the
  `<s>…</s>` tags but kept the crossed-out text, so a small fraction of rulings pages contain a
  superseded sentence glued to the current one (verified example: `Card Rulings:Uni-Horned
  Familiar`). Scope-checked 2026-08-01: **0/50** sampled rulings pages affected → rare.
  **Decision: accepted, not fixed** (Harman's call) — the teacher grounding gate and the
  reference-grounded eval judge mitigate the rare wrong pair. *Fix next time:* strip
  `<s>…</s>` / `<del>…</del>` before `strip_code`, then re-collect.
- **TCG/OCG rulings labels flattened.** All ruling *content* is preserved, but the
  `== TCG Rulings ==` / `== OCG Rulings ==` section headers were removed, so region is not
  distinguished within a page.
- **Fandom XML dump unverified** (HTTP 402 during verification) — not used.
- **Lore is the weakest retrieval category** (chunking study Study 8: recall@5 ≈ 0.56) — System C
  will answer lore questions less reliably than rulings/interactions.

## Files

- `data/train.jsonl` — surviving QA pairs (Phase 2). **not yet produced**
- `data/heldout.jsonl` — held-out test set, `{id, question, gold, evidence}` (Phase 2). **not yet produced**
- corpus statistics — **not yet produced**

## Cost

Data-stage spend logged in `../costs.md` (teacher generation + gating API calls).

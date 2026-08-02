# corpus-cleaning-system.md — Phase 1 raw-corpus cleaning spec

> **Scope:** Phase 1 only — turning raw fetched prose (`data/corpus/corpus.jsonl`) into a clean,
> de-duplicated, English, on-topic corpus. QA-pair creation/validation is separate:
> `fine-tuning-dataset-creation-guidelines.md`.
>
> **Sources of truth (both read verbatim 2026-08-01):**
> - **Authoritative:** the Session-2 bootcamp slides,
>   <https://session-2-slm-bootcamp-slides.vercel.app/> ("Data, Curation, and Tokenizers",
>   slides 12–23 cover cleaning). Numbers here follow the slides.
> - **Companion interactive tool:** <https://slm-data-vizuara.vercel.app/> (live demo of the same
>   filters; used for concrete regex patterns).
>
> **Scope caveat:** the session targets *pretraining a from-scratch 125M model + building a BPE
> tokenizer*. We *fine-tune Gemma 2 2B (existing tokenizer) + RAG*, so we adopt the **cleaning
> pipeline** but **skip the tokenizer-building half (slides 24–40) and pretraining token-packing**.
>
> **Status: SPEC — not executed.** Runs only after Harman signs off on every rule and threshold.

---

## 0. The pipeline (slides §01–04, "cheap filters first, expensive last")

| Slide stage | Meaning | Our mapping |
|-------------|---------|-------------|
| Source | licensed, provenance-pinned, recorded mix | **Done** — Yugipedia (CC BY-SA) + YGOPRODeck; mix recorded in DATA.md; **version-pin = fetch date 2026-08-01** (wiki is live) |
| Parse | HTML→text (optional; skipped if sources are text) | **Done** — wikitext→prose via `strip_code` (our analogue of their HTML parse) |
| Clean | line + boilerplate filters | **C1** |
| Filter | length, (repetition,) language | **C2** |
| Dedup | MinHash-LSH on dominant source | **C3** |
| Split + decontaminate | document-level split, leak check | **C4** |
| ~~Pack / Tokenizer~~ | uint16 windows, BPE training | **N/A** — we don't pretrain or build a tokenizer; retrieval chunking (1000/150) happens in Phase 4 |

Already applied inline at collection: `strip_code`, appendix-section removal, redirect exclusion,
per-source `min_bytes`, exact title + exact content-hash dedup. Stages below are the additional,
slide-mandated cleaning not yet run.

**Two inputs, two treatments:**
- **Yugipedia prose** (`corpus.jsonl`) — runs the full C1–C4 pipeline below.
- **Card-facts** (`cardfacts.jsonl`, from YGOPRODeck) — **passed through with NO cleaning**
  (decision 2026-08-01, after reviewing full sample passages). They are already clean, structured
  text; the only artifacts (`''` flavor markers on 221 cards, one `&amp;`) were judged cosmetic and
  not worth filtering, and `●` bullets / `[...]` brackets are meaningful. Card-facts do **not** count
  toward the 20 MB free-prose floor (effect text is fair-use).

---

## C1 — Boilerplate & line cleaning — SPECIALIZED for this corpus (slides 20–21 + corpus evidence)

The generic rules are groundwork; the rules below are tuned to the patterns actually found in
`corpus.jsonl` (see `docs/` inspection). Decisions recorded from Harman's review 2026-08-01.

### C1a — Drop the whole line (boilerplate)
| Rule | Pattern (proposed) | Evidence |
|------|--------------------|----------|
| section headers | exact: `Previously Official Rulings`, `Mentions in Other Rulings` (any case), `Judge Program Forum Rulings`, `Official Rulings` | 756 + 527 + 102 occurrences — wiki structure, not prose (Pattern 3) |
| category tags | `^\s*Category:` | 642 lines e.g. `Category:TCG and OCG archetypes` (Pattern 4) |
| file/image lines | `^\s*(File|Image):` | Yugipedia media refs |
| table rows | `^\s*\|.*\|\s*$` | generic (rare after strip_code) |
| bare URLs | `^\s*https?:\/\/\S+\s*$` | generic |
| copyright / notices | `(all rights reserved|©|\(c\)\s*\d{4})` | generic (rare) |
| symbol-heavy | line with **> 30% non-alphanumeric** chars | 9 lines, Duel Links dialogue tables `Situation Dialogue Duel Start .....` (Pattern 5) |
| ~~FORM 10-K / ToC / `/s/`~~ | legal-only | ✗ dropped — not our domain |

### C1b — Strip within the line (keep the sentence, cut the junk)
| Rule | Pattern | Evidence |
|------|---------|----------|
| trailing citations | remove `Konami\s*\w*\s*FAQ:.*$` and repeated glued copies; also `Judge Program Forum Rulings.*$` | 3,348 lines e.g. `...cannot be activated.Konami Gameplay FAQ: Duelist Revolution...` (Pattern 2) |
| inline section markers | strip `===[^=]+===` glued to prose | e.g. `...all "Crystal Beast" monsters.===OCG Rulings===` |

### C1c — Short-line rule — **adapted** (do NOT use the generic 40-char blanket)
The slides' "drop lines under 40 chars" would delete valid short rulings
(`This effect does not use the Chain.` = 35 chars; `It is not treated as an effect.`). **Corpus-
specific rule:** for a line under 40 chars, **keep it only if it ends in terminal punctuation
(`.` `!` `?`)** (a complete ruling statement); otherwise drop it as a label/fragment
(e.g. `"Hole" Normal Trap Cards:`). ⟨verify — Harman's proposed rule⟩

### C1d — KEEP (explicit corpus decision)
- **"This card can be searched by …" lines are KEPT** (Pattern 1). Rationale: retrieval runs over
  100% of the corpus, so System C must have this content to answer "which cards can search X?".
  Consequence: tips bulk stays → corpus stays ≈ 20 MB after cleaning (likely no re-collect).
  Phase-2 note: do **not** over-generate low-value "which cards search X" QA pairs (task balance,
  handled in `fine-tuning-dataset-creation-guidelines.md` G5).

---

## C2 — Document filters (slides 20–21; companion §7–§8)

Applied per document after C1, in cost order.

### C2.1 Length
Drop whole documents **under 200 characters after cleaning** — **lowered from the slides' 600**
(a legal-pretraining value) to fit our data. Evidence: 0 pages are below 400 chars raw (collection
already filtered stubs at `min_bytes` 300–450); 600 would drop 1,567 pages (13.1%) of valid short
rulings/tips *before* cleaning shrinks them; and citation-stripping (C1b) can nearly halve a short
rulings page. 200 keeps short valid rulings post-clean while dropping only near-empty shells.
⟨validate exact [200,600) drop count in the dry-run⟩

### C2.2 Repetition  *(companion §8 — DEMOTED to off-by-default)*
Every **4-gram**; if the **top-10 most frequent 4-grams cover > 50%** of the doc, drop as
repetitive. **Off by default:** since we deliberately KEEP the searched-by lists (C1d), this
filter is disabled so it cannot delete that content. Enable only if genuine repeated-phrase spam
is found, and re-verify it does not catch searched-by pages first. ⟨verify: keep off⟩

### C2.3 Language (slides 20–21, "runs last — costliest")
**Primary: `langdetect`** on the first ~5,000 chars → keep only English — *corrected: the slides
prescribe langdetect, not the ASCII heuristic*. **Fallback (companion §7):** ASCII ratio > 90%
AND English-word ratio > 6% ⟨verify⟩. Small attrition expected (Yugipedia is English).

---

## C3 — Deduplication: MinHash-LSH (slides 13–18; companion §2–§6)

The slides' method exactly (not embedding cosine). Handles **exact, near, and cross-document**
duplicates (slide 13); "25–40% of a large corpus is near-duplicate."
- **Shingles:** k = **5**-word overlapping shingles ⟨verify k⟩; Jaccard = |A∩B| / |A∪B|.
- **MinHash:** many hash functions per doc (slides illustrate the race intuition); h = **128**
  ⟨verify — more hashes → smaller error⟩.
- **LSH:** signature split into bands of r rows; candidate pairs share ≥ 1 band bucket (avoids N²).
- **Threshold:** estimated Jaccard ≥ **0.80** → drop as near-dup, keep the first canonical copy
  (**slide 18 states 0.8 explicitly**).
- **Where:** run on rulings / archetype / mechanics / lore. **`tips` are EXEMPT** (decision
  2026-08-01): distinct cards legitimately share the same searcher list, so MinHash would drop a
  distinct card's page and break "which cards can search X?" (Pattern 1). Dedup-with-tips dropped
  147 docs; tips-exempt drops only the **32** genuine duplicates in the other sources.

---

## C4 — Document-level split + decontaminate (slide 23; slides §9 decontaminate)

**Split policy (slide 23), adapted to our fine-tune + RAG setup:**
- **Seed:** a fixed integer, recorded in the dataset card (`SEED = 20260801`).
- **Unit:** **document-level**, never paragraph/chunk-level — passages from one page must not
  straddle the split. (We already tag a page-level split at collection.)
- **Leak check:** assert zero document overlap across the split.
- **"Val is a thermometer, test is a judge":**
  - The slides' **99/1 train/val** split is for **loss curves** — for us that val split lands on
    the **QA training pairs** in Phase 2/3 (Gemma fine-tune monitoring), not the raw corpus.
  - The **held-out TEST set (our ≥60 gold+evidence questions) is the judge** — reserved as a
    disjoint page split *before* QA generation (leakage impossible by construction).
- **Decontaminate:** ensure no near-duplicate of a held-out page survives in the training-source
  pool (MinHash-LSH across the split boundary) ⟨verify⟩. (Pair-level question decontamination is
  in the fine-tuning doc, G4.)

---

## Card-facts: NO cleaning (decision 2026-08-01)

After reviewing full sample passages (Dark Magician, Cup of Ace, Tribal Synergy, Sky Striker Ace
Raye), card-facts are **passed through unfiltered**. They are generated, already-clean structured
text. The only artifacts observed — `''` flavor markers (221 cards) and one `&amp;` — were judged
cosmetic and not worth filtering; `●` effect-bullets (1,184) and `[...]` skill brackets (374) are
meaningful and kept. **No** boilerplate, length, dedup, repetition, or language filter is applied
to card-facts. (Note: applying the Yugipedia rules would have been *harmful* — the length floor
would drop >50% of cards, and MinHash near-dup would merge distinct cards sharing effect text.)

## The dataset card (slide "The Dataset Card") = our `DATA.md`

Must record: **source + license**, **build steps** (parse, dedup threshold, every filter, split
seed, tool versions), **statistics** (document count, token/char count, source mix, date range),
and **known gaps** (what is over/under-represented). Our `DATA.md` is this card; the version-pin
is the **2026-08-01 fetch date** since Yugipedia is live.

---

## Order of operations (cheap → expensive, per slides)

`C1 line/boilerplate → C2 length / (repetition) / language → C3 MinHash-LSH dedup → C4 split + decontaminate`

## Honest accounting (recorded in DATA.md — the loss funnel, slide 22)

Report count + MB **dropped at each stage**: raw fetched → after C1 → after C2 (length /
repetition / language broken out) → after C3 dedup → kept → train/heldout split. What we throw
away is reported, not hidden.

## Proposed thresholds — summary (all `⟨verify⟩`; ★ = corrected from authoritative slides)

| Stage | Parameter | Proposed |
|-------|-----------|----------|
| C1a | drop lines | section headers, `Category:`/`File:`, table rows, bare URLs, >30% symbols |
| C1b | in-line strip | trailing `Konami…FAQ`, `Judge Program…`, inline `===…===` |
| C1c | short line (<40 chars) | **keep only if ends in `.`/`!`/`?`**, else drop (adapted, not blanket-40) |
| C1d | searched-by lines | **KEEP** (corpus decision) |
| C2.1 | min doc length (post-clean) | **200 chars** (lowered from slides' 600 to fit our short rulings) |
| C2.2 | repetition filter | **off by default** (would risk searched-by lists) |
| C2.3 | language | ★ **langdetect** primary; ASCII>90% & Eng-word>6% fallback |
| C3 | shingle k / MinHash h / Jaccard dup | 5 words / 128 / **0.80** |
| C4 | train/val split (loss curves) | 99/1, document-level, seed 20260801 |

## What this spec does NOT do yet

No cleaning is run; no document is dropped. Thresholds are proposals. **Harman verifies / edits
each `⟨verify⟩` value**, then I implement the pass exactly as approved and record the funnel.

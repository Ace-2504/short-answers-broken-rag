# assignment-verification.md

> **What this file is:** a course-correction for the Claude Code session/agent working on
> this assignment. A previous session misunderstood the *essence* of the task. Read this
> top to bottom **before touching any code or data.**

---

## 0. FIRST INSTRUCTION — verify everything (this is also the *tone* of the whole assignment)

Before you act on anything — including this file, anything a previous session assumed, or
your own priors:

- **Do not take claims at face value. Verify each one yourself.** This file included.
- **The assignment brief is the only source of truth.** Re-read it directly; do not act on
  a summary (not even this one) without checking it against the brief.
- Specifically re-derive and re-confirm, in your own words:
  - the **true goal** of the assignment (see Section 1) — restate it and check it against the brief
  - the **minimum raw-text requirement** — quote the exact number from the brief (do not trust "20 MB" until you have read it there)
  - that **each data source** below actually returns the volume claimed — fetch a sample and count the bytes; do not assume
  - the **license** of every source *before* using its text
  - whether the **base model is genuinely ignorant** of the chosen domain — plan a small probe to confirm this before building anything
- **Why this matters:** "verify, don't assume — measure, don't claim" is not housekeeping.
  It is the *graded ethos* of this assignment. The brief states it plainly:
  *a carefully measured result — even a negative one — is a complete answer; an unmeasured
  claim is not.* Every number you eventually report must be one **you produced and checked.**
  Carry this posture through every stage. If you cannot verify something, say so explicitly
  rather than filling the gap with an assumption.

**Do this section first. Only proceed once you can restate the assignment's goal in your own
words and have confirmed it against the brief.**

---

## 1. What this assignment is actually asking (simple summary)

- It is a **controlled experiment, not a product build.** The point is to *honestly measure*
  whether **fine-tuning** or **retrieval** is what actually lets a small model answer
  domain-specific questions.
- You build **three systems** and compare them on the **same held-out questions**:
  - **A** — the base model, closed-book (no retrieval, no fine-tune)
  - **B** — your fine-tuned model, closed-book
  - **C** — your fine-tuned model **+ retrieval** (passages supplied at question time)
- The result the experiment is designed to expose (you must **test** this, not assume it):
  **fine-tuning teaches the *shape/format* of an answer, not the *facts*. Retrieval is what
  supplies the facts — and is usually the win.** Reproduce this honestly on your own domain,
  **even if your result disagrees** with that expectation.
- **A carefully measured negative result is a full-marks answer. An unmeasured claim is not.**
- **Misconceptions this file exists to correct** (the essence a prior session got wrong):
  - Fine-tuning a small model on Q&A pairs does **not** reliably give it domain "reasoning."
    Do not assume it will.
  - RAG is **not** a separate or "fresh/real-time" side-database sitting apart from training.
    In this assignment the retriever indexes the **same corpus**. Fine-tuning and retrieval
    are deliberately **two routes to the same knowledge**, so the experiment can isolate
    *which route actually works.*
- **Domain rules:** not legal and not financial; and it must be something the **base model
  does not already know well** (otherwise every system scores the same and nothing is
  measured). Chosen domain: **Yu-Gi-Oh!**
- The full assignment spans data → fine-tune → retriever → evaluation → site → report, but the
  spine running through all of it is: **honest data, honest held-out split, honest measurement.**

---

## 2. The data corpus — DATA COLLECTION ONLY

> Scope note: this section is *only* about gathering the raw text. Nothing here about
> fine-tuning, retrieval mechanics, held-out splits, or evaluation.

**The requirement:** the brief asks for **at least 20 MB of raw text** (verify this exact
figure in the brief yourself). That 20 MB is a **floor, not a target.**

**Reality check:** Yu-Gi-Oh! is one of the largest fandoms in existence. There is **no data
shortage** — roughly **~35 MB of usable prose is comfortably available**, i.e. ~1.5–2× the
floor. If a previous attempt fell short, it was almost certainly pulling only **card *effect
text*** (short, repetitive, and the copyrighted part) instead of the **prose** categories,
which are far larger. Everything you collect forms **one unified prose corpus.**

**Use prose, not tables.** Retrieval and evidence need self-contained, sentence-shaped
passages. So editorial prose (rulings, tips, lore, episode plots, character bios, archetype
write-ups) is the **spine**; structured card data (stats/effects as JSON) is a **fact
supplement**, not the spine.

### 2.1 Primary source — Yugipedia (pull by *category*, not just cards)

The core mistake to avoid: treating Yugipedia as "card effects." It is a full encyclopedia.
Pull these categories and you clear the floor from this one source alone.

| Yugipedia category | What it yields | Est. usable text |
|---|---|---|
| Card pages (rulings, tips, trivia, lore — the prose, not the verbatim effect) | ~13,000 pages | **~15 MB** |
| Episode pages (DM, GX, 5D's, Zexal, Arc-V, VRAINS, Sevens, Go Rush) | ~1,000+ plot summaries | **~6 MB** |
| Character bios | ~1,000 pages | **~3 MB** |
| Archetype pages (playstyle, history, members) | ~500 pages | **~2 MB** |
| Video-game pages (Master Duel, Duel Links, Tag Force, Forbidden Memories, …) | mechanics + story | **~1 MB** |
| Set / booster-pack / mechanics / lore pages | release + rules prose | **~2 MB** |

**Yugipedia subtotal: ~29 MB** of usable prose.

**License:** Yugipedia editorial prose is **CC BY-SA 4.0** (usable with attribution).
Verbatim printed card effect text is **© Konami / 4K Media** — use *facts and paraphrase*,
not the exact wording. Record provenance and license in your data notes.

**How to fetch (downloadable / API — not HTML scraping):**
- **MediaWiki API by category:** `api.php?action=query&generator=categorymembers&gcmtitle=Category:<Name>&gcmlimit=max&prop=revisions&rvprop=content&rvslots=main&format=json` — returns raw wikitext per page. Loop over the categories in the table. (Verify a sample response and byte count before scaling.)
- **Enumerate titles first** with a category tool (e.g. PetScan) if you want the full page list per category before pulling.
- Then **clean the wikitext** (strip templates, infoboxes, navboxes, image/file tags) down to plain prose.

### 2.2 Fast start — `yaml-yugipedia` GitHub repo

- **`github.com/DawnbrandBots/yaml-yugipedia`** — an auto-updated mirror of Yugipedia
  **wikitext** (card-focused) in a `/wikitext` directory. `git clone` it for an instant,
  scrape-free chunk of the card corpus while you set up the category pulls above.
- **License:** Yugipedia content in it is **CC BY-SA 4.0**; card text remains © Konami;
  the repo's own code is LGPL. Verify before use.

### 2.3 Supplement — YGOPRODeck API (structured facts)

- **Endpoint:** `https://db.ygoprodeck.com/api/v7/cardinfo.php` returns **all ~13,000 cards**
  as JSON: name, type, ATK/DEF, level/rank, attribute, archetype, sets, release dates,
  banlist status. **~5 MB.**
- **Use it for facts / paraphrase**, not as prose spine (it's tabular).
- **Terms:** free, but **cache locally**, respect the **20 requests/sec** limit, and note the
  card text is **© Konami / 4K Media**. Verify current terms on their API guide.

### 2.4 Redundancy / top-up — Yu-Gi-Oh! Fandom wiki

- **`yugioh.fandom.com`** offers a **downloadable CC BY-SA XML database dump**
  (via `Special:Statistics` → database download). Good for extra prose and redundancy.
  Yugipedia is more current, so treat Fandom as a top-up and **de-duplicate** against it.

### 2.5 Running tally (verify by actually fetching + counting bytes)

| Source | Est. usable text |
|---|---|
| Yugipedia prose (all categories, 2.1) | ~29 MB |
| YGOPRODeck structured facts (2.3) | ~5 MB |
| Fandom dump extra (2.4, after dedup) | a few MB |
| **Total available** | **~35 MB (≈1.5–2× the 20 MB floor)** |

**Collection discipline:**
- **De-duplicate across sources** (YGOPRODeck effect text overlaps Yugipedia card pages —
  do not count the same content twice, and do not let templated card boilerplate dominate).
- **Quality over raw megabytes** — 20 MB is a floor; do not pad with repetitive junk.
- **Verify every volume claim in this file by fetching a sample and counting bytes** before
  trusting the totals. (Per Section 0.)

---

## VERIFIED — independent verification log (2026-08-01)

> Per Section 0, every claim below was checked against the brief or live APIs, not assumed.
> Method: brief re-read directly (`agent-prompt.md`); Yugipedia MediaWiki API
> (`prop=categoryinfo`, raw wikitext byte counts); YGOPRODeck v7 fetched and measured;
> `yaml-yugipedia` repo inspected; Gemma 2 2B base probed on a local endpoint.

### What the file got RIGHT

- **Section 0 (verify-don't-assume ethos):** correct and adopted as the working posture.
- **Section 1 (what the assignment is):** verified faithful to the brief on every point —
  it is a controlled experiment not a product build; three systems A (base, closed-book) /
  B (fine-tuned, closed-book) / C (fine-tuned + retrieval); the thesis "fine-tuning teaches
  answer *shape*, not *facts*; retrieval supplies facts and is usually the win" (brief line 5–7);
  "a measured negative result is a full answer" (brief line 9); and the key correction that the
  retriever indexes the **same corpus** — fine-tuning and retrieval are two routes to the same
  knowledge (brief: "put a retriever in front of the same models… over your corpus"). Domain
  rules (not legal/financial; base must not already know it) match brief line 18. **Accurate.**
- **20 MB floor:** brief line 20 — "At least 20 MB of raw text." Exact. (Also confirmed: ≥2,000
  clean pairs, ≥60 held-out, recall@k for k=1/3/5/10.)
- **Licenses:** Yugipedia editorial prose = CC BY-SA 4.0; printed card text © Konami/4K Media —
  confirmed. `yaml-yugipedia`: `/wikitext` mirror present, content CC BY-SA (card text © Konami),
  code LGPL-3.0, auto-updated — confirmed.
- **Sources exist at the claimed scale:** card pages **OCG 14,515 / TCG 14,198** (claim "~13,000"
  is if anything conservative); **Archetypes 770** (claim "~500" — conservative); Anime cards
  9,587; Series 392; Video games 74; GX-episodes subcategory alone 184. YGOPRODeck v7 returns
  **14,477 cards** free.

### What the file got WRONG / overstated

- **YGOPRODeck "~5 MB":** the free payload is actually **21.13 MB total JSON**; the *text* portion
  (card `desc`/effect text) is **4.53 MB, and that text is © Konami.** So YGOPRODeck yields
  **~0 MB of *free prose*** — structured facts + copyrighted effect text only. Folding "~5 MB"
  into a "~35 MB available" prose tally is misleading; it must **not** count toward the 20 MB
  free-prose floor.
- **"Card pages ~13,000 → ~15 MB prose":** optimistic. Raw card wikitext measured at 8.5 KB
  (Pot of Greed) → 28.6 KB (Dark Magician) → 35 KB (Elemental HERO), but most of that is
  infobox + printing tables + © effect text, **not** free prose. Genuine free prose per card
  (rulings/tips/trivia/lore) is small and absent on many cards. The 15 MB figure is **unverified
  and likely high.**
- **Per-category MB estimates and the "~29 MB Yugipedia / ~35 MB total" headline:** these are
  estimates of *raw* content, never measured as *cleaned prose*, so the totals are **unverified**.
  Directionally the "no data shortage" conclusion still holds — character bios and episode plots
  are genuinely prose-heavy (Yugi Muto page = 137 KB raw wikitext) — but the free-prose volume
  comes from **bios + episode plots + archetype/series pages + card lore/ruling sections**, NOT
  from card effect text and NOT from YGOPRODeck. That is the correction to *where* to mine.

### What could NOT be verified

- **Fandom XML dump (2.4):** `Special:Statistics` returned HTTP 402 (anti-bot). Dump link and
  current license unconfirmed. Non-blocking (redundancy top-up only).
- **Exact episode/character page counts** ("~1,000+ each"): those categories nest in subcategories;
  subcats confirmed to exist but not summed.

### Base-model ignorance — MEASURED (was an open item)

Probed `gemma-2-2b-it` (base) closed-book on 12 Yu-Gi-Oh questions (general → classic stats →
modern cards → rulings) with known answers. **Score ≈ 1.5 / 12.** It knows only the generic
"it's a card game"; it gets **basic rules wrong** (said draw 2, 60-card minimum), **cannot recall
Dark Magician / Blue-Eyes ATK**, and **confidently fabricates card text and rulings** for modern
cards (Sky Striker Ace Raye, Effect Veiler, Maxx "C", Tearlaments). This confident closed-book
hallucination is exactly the failure the experiment targets. **Domain-ignorance requirement:
confirmed by measurement — Yu-Gi-Oh is a valid domain; A/B/C will separate.**

### Net

The file's *conclusions and licensing guidance are sound*; two volume claims (YGOPRODeck 5 MB,
card-prose 15 MB) are overstated and the headline totals are unverified estimates. Corrected
plan of record: **free-prose corpus is mined from bios + episodes + archetype/series + card
lore/ruling prose (CC BY-SA); card effect text and YGOPRODeck are fair-use fact supplements that
do not count toward the 20 MB floor.** 20 MB of genuinely free prose is reachable on this basis.

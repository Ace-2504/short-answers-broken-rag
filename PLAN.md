# Assignment 3 — Yu-Gi-Oh SLM: Fine-tune vs. Retrieval

**Course:** Build an Enterprise SLM from Scratch
**Domain:** Yu-Gi-Oh! (card rulings, archetype mechanics, lore) — chosen because Gemma 2 2B does **not** know detailed rulings/interactions, so the three systems can actually separate.

---

## 0. The one idea this whole assignment tests

We build **three** systems and compare them on the **same** held-out questions, graded by a reference-grounded LLM judge:

| System | What it is |
|--------|------------|
| **A** | `google/gemma-2-2b-it`, untouched, **closed book** |
| **B** | Our QLoRA fine-tune of Gemma 2 2B, **closed book** |
| **C** | Same fine-tune, **with our retriever** feeding it passages |

**Thesis to reproduce honestly:** fine-tuning on Q&A pairs teaches a model the *shape* of an answer, not the *facts*. In the reference run B did **not** beat A; retrieval (C) was the entire win; and once retrieval was on, fine-tuned ≈ base. We must report what we actually measure **even if it disagrees** with that. A carefully measured negative result is a complete answer. An unmeasured claim is not.

**Non-negotiables baked into every phase:**
- The held-out set is truly held out (its source passages never enter training) and every item has `gold` + `evidence`.
- `recall@k` is measured **before** we blame the model for a weak system-C answer.
- Every A-vs-B and B-vs-C comparison carries a **paired** significance test.
- The site shows only numbers our own eval produced. No faking.
- Budget ≈ **$25** GPU. Log every dollar and API call.

---

## Data source & licensing (decided)

- **Primary corpus:** Yugipedia article prose (rulings, archetype/mechanics/lore pages) — **CC BY-SA 4.0**, free to reuse with attribution. Bulk-pullable via the MediaWiki API or the community wikitext dump (`DawnbrandBots/yaml-yugipedia`), avoiding hammering the site.
- **Structured supplement:** YGOPRODeck REST API (free; 20 req/s; must cache locally).
- **Card oracle text** is **Konami IP under fair use** — used for education/research only, labeled as such in `DATA.md`, kept secondary to CC-licensed prose.
- `DATA.md` will state provenance, license, and attribution explicitly (an assignment grading criterion).

---

## Question-type policy (what the model is built to answer)

**One-line legal status:** Yugipedia *prose* is CC BY-SA 4.0 (free, with attribution); card *oracle text* and card *data* are Konami's copyright, used here only under educational fair use and labeled as such.

**In scope — these are the questions System C (RAG) must answer well.** They require reasoning over rulings/mechanics that Gemma 2 2B does not know closed-book, and they are answerable *from* Yugipedia's free-licensed explanatory prose:

- **Rulings / interactions:** e.g. "If Sky Striker Ace Raye is sent to the GY, what can its effect Special Summon, and under what condition?"
- **Archetype mechanics:** e.g. "Why do Sky Striker decks want an empty Main Monster Zone, and which cards enforce that?"
- **Timing / chain / negation:** e.g. "Does Effect Veiler stop Raye's GY effect?"
- **Comparative / lore reasoning:** how a lineup or story develops, and the mechanical reason behind it.

**Out of scope by design:** "Recite the verbatim printed text of card X." It (a) fails to separate the three systems — it's just 'was the passage retrieved or not' — and (b) is the most copyright-sensitive possible output. Card text appears in the corpus only as labeled fair-use *context* the model reasons over, never as the target answer.

**Consequence for the RAG design (Phase 4):** retrieval and chunking are tuned so that the *ruling/mechanics passage* for a question lands in the top-k — that is what `recall@k` measures, and it is the precondition for System C answering these questions at all.

---

## Repository layout (target)

```
data/    DATA.md, corpus stats, train.jsonl, heldout.jsonl
train/   fine-tune script, configs, loss curves
rag/     chunking, embedding, index build, /retrieve endpoint
eval/    harness, responses.json, verdicts.json, leaderboard.json, recall@k
site/    Vercel frontend (3 systems side by side)
report.pdf   one page, one side of A4, 11pt
README.md    how to reproduce, HF link, live URL, 3 endpoints, total cost
```

---

## Phase-by-phase plan

> **Gate rule (your request):** at the end of each phase I quiz you on the code and architecture. We do **not** start the next phase until you can explain every moving part in your own words — because you have to defend this in a viva and pitch it to mentors.

---

### Phase 0 — Foundations & scaffolding
**Goal:** repo skeleton, environments, accounts, and a shared mental model of the experiment.

- Repo structure above; Python env (`uv`/`venv`); pin versions.
- Accounts/keys ready: Hugging Face (model push), Modal (GPU serving, scale-to-zero), teacher+judge LLM API (Gemini flash-lite class — cheap, you've used it before).
- Write down the hypothesis and the three systems in the README stub, in your own words.

**Deliverable:** committed scaffold + README stub.
**Cost:** $0.
**Viva topics:** why three systems; what "closed book" means; why B might *not* beat A; what "reference-grounded judge" buys us.

---

### Phase 1 — Build the corpus (Part 1a)
**Goal:** ≥ **20 MB** raw text, cleaned and chunked, with honest counts.

1. **Collect** Yugipedia CC BY-SA prose (rulings/archetype/mechanics/lore) via MediaWiki API or wikitext dump; optionally enrich with YGOPRODeck JSON. Record where each came from. **Prioritize pages rich in the in-scope question types** (ruling pages, archetype/strategy articles, mechanics glossary) so the corpus can support interaction/timing questions — not just card stat blocks.
2. **Clean:** strip wiki markup/templates/tables/nav, dedupe, drop near-empty stubs, normalize whitespace. Keep it defensible and reproducible.
3. **Chunk:** ~1,000 chars with 150-char overlap (the reference setting; we justify or change it). Carry `source_doc` + `chunk_id` on every chunk.
4. **Stats:** raw doc count, MB before/after cleaning, chunk count, length distribution → `data/DATA.md`.

**Deliverables:** cleaned corpus + chunk file, `DATA.md` provenance/license/counts.
**Cost:** ~$0 (bandwidth only).
**Viva topics:** why overlap on chunks; what breaks retrieval if chunks are too big/small; why provenance counts matter to graders; the CC BY-SA vs. Konami-fair-use distinction.

---

### Phase 2 — Supervised set + held-out test set (Part 1b)
**Goal:** ≥ **2,000 clean** Q&A pairs after gating, and a ≥ **60**-item held-out set with `gold` + `evidence`.

1. **Split first:** reserve a slice of passages as *held-out only*. These passages **never** feed teacher-training generation. This is the integrity backbone.
2. **Generate:** strong teacher model writes Q&A pairs from *training* passages. Over-generate (the reference threw away far more than it kept).
3. **Gate:** a judge scores each pair (answerable-from-passage, correct, self-contained); drop the bottom. Record generated-vs-survived counts.
4. **Held-out items:** `{id, question, gold, evidence}` where `evidence` = verbatim corpus sentences proving `gold`. Evidence is mandatory — it's what lets the judge grade blind.

**Deliverables:** `data/train.jsonl`, `data/heldout.jsonl`, updated `DATA.md` funnel (raw → generated → survived → held-out).
**Cost:** teacher+judge API calls — log them (likely a few $).
**Viva topics:** why split before generating (leakage); why `evidence` is non-optional; how gating changes the train distribution; what "answer shape vs. facts" means concretely in a pair.

---

### Phase 3 — Fine-tune Gemma 2 2B (Part 2)
**Goal:** QLoRA fine-tune, loss curves, val perplexity, public HF model, live endpoint.

1. **Train:** QLoRA on a single A100/L4 (Modal). Record the **exact** config: rank, alpha, target modules, LR, schedule, batch size, seq length, epochs, train/serve precision.
2. **Curves:** plot train + val loss; report final **validation perplexity** (reference was 4.26 — a sanity yardstick, not a target).
3. **Publish:** push adapter or merged model to HF Hub, public, with a model card stating training data.
4. **Serve:** HTTP endpoint on Modal with **scale-to-zero** (copy the `modal_qasft_gemma.py` pattern). **Trap:** never toggle base vs. adapter per-request in one process — concurrent requests race and silently serve the wrong model. Serve separate containers or serialize.

**Deliverables:** training script, loss curves, HF link, live endpoint URL.
**Cost:** the bulk of the $25 — log GPU-hours per run.
**Viva topics:** what QLoRA actually freezes/trains; rank/alpha meaning; why perplexity ≠ accuracy; the adapter-race trap; why scale-to-zero matters for budget.

---

### Phase 4 — Retriever + wire-in (Part 3)
**Goal:** a real vector retriever, a `/retrieve` endpoint, and a `recall@k` table.

1. **Embed** every chunk with `BAAI/bge-small-en-v1.5` (384-d, normalized so inner product = cosine). Justify the model.
2. **Index:** FAISS. At our corpus size a **flat** index is likely fine — say so. (IVF only if size demands it; then report `nprobe`.)
3. **`/retrieve` endpoint:** question → top-k chunks with scores + source doc.
4. **Wire into generation:** retrieved passages go into the prompt; fine-tuned model answers from them (= System C).
5. **Measure the retriever alone:** `recall@k` for k = 1, 3, 5, 10 = how often the gold-evidence passage is in the top k. If recall@5 is poor, no prompt trick saves System C — know this before blaming the model.

**Deliverables:** indexing script, retrieval endpoint, `recall@k` table.
**Cost:** ~$0 (CPU embedding/index is feasible at this scale).
**Viva topics:** why normalize embeddings; flat vs. IVF and the `nprobe` accuracy/speed tradeoff; what recall@k does and doesn't tell you; how a chunking choice in Phase 1 shows up as recall here.

---

### Phase 5 — Evaluate all three systems (Part 4)
**Goal:** honest, re-runnable A/B/C comparison with paired stats.

1. **Judge design (matters more than judge model):** reference-grounded (question + gold + evidence in every call), **pointwise and blind** (one response per call, no model names, no other candidates). Rubric summing to 10: correctness 0–5, completeness 0–2, groundedness 0–2, clarity 0–1. Groundedness → 0 on invented citations/figures. **A refusal must beat a confident error** — write it into the rubric.
2. **Run** A, B, C over the same held-out items → `responses.json`.
3. **Grade** → `verdicts.json`; aggregate → `leaderboard.json`.
4. **Report per system:** mean ± standard error + per-category breakdown; **paired** significance test A-vs-B and B-vs-C on the same items; ≥3 quoted disagreement examples with your reading of why.
5. **Harness** is re-runnable and **skips finished work** (idempotent/cached).

**Eval methodology (decided).** Scores are bounded 0–10 integers with many ties, so the paired t-test's normality assumption is the shakiest. Keep the **paired design** (mandated + correct: it cancels question-difficulty), but use a layered test:
- **Primary:** paired **bootstrap** 95% CI on the mean score difference (resample items with replacement, fixed seed) — assumption-light, reports the effect size that matters, not just a p-value.
- **Comparability:** paired **t-test** (so numbers line up with the class reference `t`-values).
- **Robustness:** **Wilcoxon** signed-rank as a one-line cross-check. All three agreeing = bulletproof; if they diverge, trust the bootstrap and say why.
- **Power, honestly:** after running at n≈60–80, compute the observed **MDE** = t_crit · SD(differences)/√n from the real SD(d). Only expand N if the data shows we're under-powered for an effect we have reason to expect. Expect **A-vs-B not to separate** — that non-result *is* a headline finding, and the assignment explicitly blesses reporting it.

**Deliverables:** `eval/responses.json`, `verdicts.json`, `leaderboard.json`, harness.
**Cost:** judge API calls — log them.
**Viva topics:** why paired (not unpaired) test; why blind+pointwise kills position bias; why groundedness caps at 0; how ~60 items limits the smallest detectable difference (~half a point).

---

### Phase 6 — Site + one-page report (Part 5)
**Goal:** live side-by-side demo and a single honest page.

1. **Site (Vercel):** visitor types a question → all three systems answer **live** against real endpoints, side by side. Show System C's **retrieved passages**. Put the leaderboard and recall@k table on the page. Must work on a phone. No pre-recorded answers, no hardcoded numbers.
2. **Report (`report.pdf`, one side of A4, 11pt):** what you built + domain (3–4 sentences); headline table (3 systems, scores, significance); the one plot you'd show; **what you expected vs. where the result disagreed** (graded most closely — "everything worked" is not a finding); the single biggest time-sink and what you'd change.
3. **README:** reproduce-in-order steps, HF link, live URL, three endpoint URLs, total GPU + API cost.

**Deliverables:** deployed site, `report.pdf`, complete `README.md`.
**Cost:** Vercel free tier; endpoints scale-to-zero.
**Viva topics:** how the site proves it's live not faked; how to read the headline table honestly; the narrative of the negative result.

---

## Cost budget (rough)

| Item | Est. |
|------|------|
| Teacher QA generation + gating (Phase 2) | $2–5 |
| QLoRA training runs (Phase 3) | $8–15 |
| Judge eval calls (Phase 5) | $1–3 |
| Serving (scale-to-zero) | ~$1 |
| **Total target** | **≤ $25** |

Everything is logged per experiment; cost lands in the README.

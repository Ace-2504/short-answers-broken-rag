# Phase 6 — Site + Report Plan

**Status:** planned / not built — runs on Harman's go signal.
**Location:** `site/` (Next.js) + `report.pdf`.
**Date:** 2026-08-03

> Final phase: package the finished experiment. No new experiments — a live side-by-side A/B/C site
> and a one-page report. The hard rule: **show only numbers our own eval produced; no faking, no
> pre-recorded answers.**

---

## 1. What we are building

1. **A deployed site** (Vercel): a visitor types a Yu-Gi-Oh question and sees **all three systems
   answer live**, side by side, against the real endpoints — with **System C's retrieved passages
   shown**, plus our **leaderboard** and **recall@k** tables. Must work on a phone.
2. **A one-page report** (`report.pdf`, one side of A4, 11 pt): the write-up.

## 2. Endpoint strategy (the one real decision)

The site calls a **single backend `/ask` endpoint** that returns all three answers + the passages,
so the frontend makes one call. I add `/ask` to the fine-tune server: it runs **A** (use_base),
**B**, and **C** (calls the local retriever `:8200` for context, then generates) and returns
`{A, B, C, passages}`. That endpoint needs a **durable public URL**:

| Option | How | Trade-off |
|--------|-----|-----------|
| **A. Modal scale-to-zero** (brief's recommended pattern) | deploy the fine-tune + base + retriever on Modal; endpoint spins up on request | durable (grader can hit it anytime), ~pennies; more setup (port serving + index to Modal) |
| **B. Local 3060 + cloudflared named tunnel** (your existing SLM-frontend pattern) | keep serving on your GPU, expose `/ask` via a persistent tunnel; Vercel calls it via `NEXT_PUBLIC_INFERENCE_URL` | fast, free, uses the model already loaded; requires your machine + tunnel up during grading |

⟨decision needed⟩. Either satisfies "live against real endpoints"; the choice is durability vs.
setup effort.

## 3. The site (`site/`, Next.js on Vercel)

- **Ask box** with a few example questions (rulings/interactions), a Submit button.
- **Three columns** — A (base, closed) · B (fine-tune, closed) · C (fine-tune + retrieval) — each
  showing the live answer; **C also lists its retrieved passages** (expandable) — "the part people
  don't believe until they see it."
- **Results section:** the **leaderboard** (A 3.98 / B 5.25 / C 8.05 + significance) and the
  **recall@k** table — both read from the real `eval/leaderboard.json` and `rag/recall_at_k.json`,
  **not hardcoded**.
- **Responsive** (phone-first), and use the **research-lab-theme** (your SLM-site aesthetic).
- Deploy to **Vercel**; put the live URL + the three endpoint URLs in the README.

## 4. The report (`report.pdf`, one A4 page, 11 pt)

Covers, in your own words (drafted from the real results, then written in your voice):
1. **What + domain** (3–4 sentences): a Yu-Gi-Oh SLM comparing base / fine-tune / fine-tune+RAG on
   rulings & card facts.
2. **Headline table:** A 3.98 · B 5.25 · C 8.05 (/10); A-vs-B +1.27 (sig), B-vs-C +2.80 (sig).
3. **The one plot:** ⟨choose⟩ the A/B/C mean-score bar chart with SE error bars (the result itself),
   or the training loss curve. *Recommend the A/B/C bar chart — it is the answer.*
4. **Expected vs. disagreed (graded most closely):** we expected A ≈ B (per the class reference), but
   **measured B > A significantly** — fine-tuning helped closed-book, via **groundedness/answer-shape
   (0.18 → 0.87)**, not facts. Retrieval remained the dominant win (C ≫ B). So "fine-tuning teaches
   shape, not facts" held — it just mattered more here than in the reference.
5. **Biggest time-sink + what we'd do differently:** ⟨from story.md — candidates: the corpus-cleaning
   specialization + superseded-rulings catch, the Modal version churn, or the 3-epoch overfit re-run⟩.

## 5. Requirements / what can go wrong

- **No faking:** every number on the page traces to `eval/leaderboard.json` / `rag/recall_at_k.json`;
  every answer is generated live. A pre-recorded fallback is a fail condition.
- **CORS:** the `/ask` endpoint must allow the Vercel origin.
- **Cold start:** Modal scale-to-zero (option A) has a first-call warm-up; show a loading state.
- **Phone:** test the layout at mobile width (the three columns stack).

## 6. Deliverables

- `site/` deployed to Vercel (live URL), showing A/B/C live + passages + leaderboard + recall@k.
- `report.pdf` (one A4 page).
- README updated: live site URL, HF model link, the three endpoint URLs, total cost.

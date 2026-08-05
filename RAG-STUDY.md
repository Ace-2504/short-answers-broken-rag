# The RAG Study — is retrieval or the reader the real bottleneck?

> A follow-up investigation to the headline result ([System C = **8.05/10**](README.md#3-headline-result)).
> Once retrieval works, a harder question remains: **what stops System C from reaching 10 — the retriever
> or the reader — and can it be fixed without a bigger model or retraining?** Six experiments answer it:
> **the reader, not the retriever, is the ceiling**, and once retrieval is good, retrieval-side engineering
> buys nothing.
>
> *All experiments below were run in a **cloned repo** (`vizuara-assignment-3-yugioh-test`) so this
> repository's code stayed untouched. The scripts and per-answer results are local; this page is the writeup.*

---

## The starting point

System C (fine-tune + hybrid retrieval) scores **8.05/10** on the 60 held-out questions — **40 of 60 are a
perfect 10**, and the lost points sit in a short tail. Retrieval is already strong: hybrid **recall@5 = 0.93**,
and the gold passage is usually already at **rank 1**. So the real question became: *what are the missing ~2
points made of — retrieval, or reading?*

## The experiments, and what each one showed

| # | Experiment | Hypothesis | Outcome |
|---|------------|------------|---------|
| 1 | **Cross-encoder reranking** (retrieve top-20 → rerank → top-5), on a biased-60 and an equal-split-60 | Better-ordered passages → higher score | **No help — slightly worse.** 8.05 → 7.55 (biased); 8.25 → 7.37 (equal-split, statistically significant drop). |
| 2 | **Is the reranker mis-ranking?** (recall / gold-rank debug) | A reranker that hurts must be broken | **No.** recall@5 identical (0.933), gold at **rank 1** either way. The drop is the small reader wobbling on reshuffled context — not a ranking defect. |
| 3 | **"Look deeper"** — rerank a wider candidate pool | Recover the 7% of questions retrieval misses | **Recall rose (0.93 → 0.95 → 0.97) but the score did not.** Recall ≠ answer quality. |
| 4 | **Chunk-truncation fix** — adjacent-chunk expansion (±2), de-overlapped | Long effects split across 1000-char chunks → repair them | **Fixed the retrieval bug** (a card's stranded effect clause was reconstructed into the context) — **but the answer stayed incomplete.** The reader ignored the recovered clause. The bug is also rare (0.2% of cards). |
| 5 | **Failure re-diagnosis** (score by question type) | — | The tail is **yes/no reasoning inversions** — the model flips the answer with the correct passage present — **not** stat lookups. |
| 6 | **Six non-retraining reader fixes** on two cards (Blackwing FAM, Endymion) | A cheap in-model trick might fix the reader | **Self-consistency, self-verification, and quote-then-answer all failed.** The only reliable win: **a stronger reader on the same context → 6/10 to 10/10.** |

## The confirmation

Experiment 6 is the controlled test: **hold the retrieved context fixed, swap only the reader.** A stronger
model took both test cards from **6/10 to 10/10** and recovered the exact effect clause the 2.6B model kept
dropping. The context was sufficient all along — so **the 2.6B reader is the binding constraint**, proven
directly rather than by elimination.

## What the literature says

Eight recent papers on small-model RAG were reviewed against this diagnosis. They converge on the same
conclusion: an oracle-retrieval study shows sub-7B models fail even with a *perfect* passage in hand;
retrieval-side and prompt-level tricks don't recover it; and the named fixes are **RAG-aware training**
(preference-tuned "RAFT", e.g. ROSE-RAG / Pleias-RAG) or **a stronger reader** (e.g. Qwen3-4B). None of them
study the *futility of retrieval engineering in a high-recall regime* — which is exactly what this study
measures.

## Bottom line

- **Retrieval is not the bottleneck.** Once recall is high (0.93), reranking, deeper retrieval, and
  chunk-repair each measurably improve retrieval yet add **zero** answer quality.
- **The reader is the ceiling.** A 2.6B model mis-reads and under-uses passages it already has; cheap
  in-model tricks can't fix it; only a stronger reader (or RAG-aware retraining) moves the number.
- **Practical takeaway:** once recall is good, **stop tuning retrieval — invest in the reader.**

---

*Full narrative (11 sections), every per-experiment number, the failure taxonomy, and the 8-paper review are
in the cloned repo's `docs/rag-improvement-story.md` (kept local). This page is the public summary of that
study.*

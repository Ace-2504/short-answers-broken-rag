# Pushing System C (RAG) toward 10/10 — findings & options

System C (fine-tune + retrieval) scores **8.05 / 10** on the 60 held-out. This documents *why* it
stops there, the prompt-tweak experiment that ruled out the cheap fix, and the real levers left.

## 1. Where the ~2 points are lost (the bottleneck is the reader, not the retriever)

Of 60 questions, **40 score a perfect 10**. The tail (~17 < 8) breaks into three buckets:

1. **The 2.6B model mis-reads a *correctly-retrieved* passage** — 7 answers scored **1/10** (correctness 0,
   groundedness 0, "contradicts the evidence") even with the right passage in front of it (e.g. qa-047: the
   passage said "three times per turn"; the model still answered wrong).
2. **Partial answers** — it states the frame and drops a clause of a multi-part effect (Blackwing: named the
   type + material, dropped the effect → 6/10).
3. **Retrieval misses ~7%** — hybrid **recall@5 = 0.93**, so ~1-in-14 questions the gold passage isn't in
   the top-5.

Retrieval has largely done its job (0.93). **The ceiling is the small model's ability to read and fully use
the passage** — plus its trained brevity (100% of its 2,683 training answers are < 40 words, median 17).

## 2. Experiment: can a prompt tweak fix the short/incomplete answers? — **No.**

Tested on *"What is the effect of Blackwing Full Armor Master?"* (retrieved passage contains the full
effect; original C answer = 27 words, omits the effect). *The judge scores below are from a single run — the
reference-grounded judge is stochastic, so read them as the **relative** effect of each prompt, not absolute
marks (a later live check scored this card differently).*

| Prompt | Words | Score | Result |
|--------|------:|:-----:|--------|
| Original (no tweak) | 27 | 6/10 | grounded, omits the effect |
| Mild — "answer fully…" | 30 | 5/10 | model ignored it; still omits the effect |
| Strong — **names** the mechanics (Wedge Counters, take control, destroy) | 49 | 8/10 | works — but this **leaks the answer** into the prompt (unusable in production) |
| Generic strong — "say everything it does", no hints | 42 | **3/10** | **backfires** — forced to write more, it *fabricates* (invents Normal Summon / Simoon), groundedness → **0** |

**Conclusion:** the brevity is **protective**, not just stylistic — the model learned "short = grounded."
Forcing length without telling it exactly *what* to add makes a 2.6B model hallucinate to fill the space.
Prompting can't buy longer **and** grounded answers here.

## 3. The real levers (ranked by expected impact)

### A. Fix the reader — highest impact
- **RAFT — Retrieval-Augmented *Fine-Tuning* (top pick).** Today System C is a *closed-book* fine-tune with
  retrieval bolted on at inference; the model was **never trained to read a context passage and answer from
  it**. Re-tune on `(question + retrieved passages → grounded answer)` examples so it *learns* to extract
  from context and cite all the relevant clauses. This directly attacks buckets 1 & 2. (The SLM ecosystem
  already has RAFT stages, so the recipe is known.) Cost: a new training set + one Modal run (~$1) + re-eval.
- **Fuller gold answers in that training data.** Generate the RAFT golds to be *complete* (cover every effect
  clause), so the model unlearns the 17-word habit — but grounded, so it doesn't learn to pad. Pairs with RAFT.
- **A bigger / better-reading base** (e.g. Gemma 2 9B) — removes the 2.6B comprehension ceiling, at higher
  serving + training cost. Highest impact, highest cost.

### B. Improve what the model sees — medium impact, cheaper (no retrain)
- **Cross-encoder reranking.** Retrieve top-20, rerank with a cross-encoder, keep the best 5 — so the single
  most relevant passage is first and the model reads the right thing. Cheap, no retrain, helps bucket 1 & 3.
- **Card-aware chunking.** Ensure one card's full text (stats + entire effect) lands in one chunk, so the
  effect is never split across passages (helps completeness on card-fact questions).
- **Increase top-k (5 → 8–10).** Recall@10 is 0.95, so this recovers a little of bucket 3 — but more context
  can dilute/confuse a small model, so test for regressions.

### C. Targeted / post-hoc — niche but high on specific categories
- **Structured lookup for card-fact questions** (~45% of held-out): pull ATK/DEF/type/banlist straight from
  the structured card record instead of free-generating — near-perfect on those, but only that category.
- **Answer-vs-evidence verification pass** — a second call that checks the answer covers the passage's
  clauses and flags gaps. Adds latency/cost; more of an eval aid than a fix.

## 4. Honest ceiling

8.05 → **~9 is realistic** with RAFT + fuller answers + reranking. A true **10.0 average is asymptotic**:
some golds are debatable, the judge has noise, and ~7% of questions have no retrievable gold. And chasing
10/10 on *our* judge risks over-fitting to the eval — the aim is a genuinely better reader, not a higher
number. Recommended order: **RAFT (+ fuller golds)** first, then **reranking**, then reassess.

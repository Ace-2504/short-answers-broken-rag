# Initial Testing — Retriever Design Study (pre-Phase-1)

**Status:** planned / in progress
**Location:** `rag/chunking_study/`
**Owner:** Harman
**Date:** 2026-08-01

---

## 1. What we are doing

Before we commit to any corpus, chunking, or retriever settings for the real build, we run
**one small, self-contained measurement experiment** on a representative sample of the target
domain (Yu-Gi-Oh). The experiment stands up a miniature version of the full retrieval pipeline
— sample corpus → questions with known answers → embeddings → vector index → **recall@k** —
and uses it as a *measurement rig* to turn a set of design decisions from guesses into
data-backed choices.

The rig has four moving parts, one script each:

| Script | Role |
|--------|------|
| `fetch_sample.py` | Pull ~50 prose-heavy Yugipedia pages via the MediaWiki API, strip wiki markup to clean prose. Output: `sample_corpus.jsonl`. |
| `make_probes.py` | Sample real sentences and use Gemini flash-lite to write a natural question each sentence answers. Every probe therefore has a **known gold sentence**. Output: `probes.jsonl`. |
| `benchmark.py` | For each configuration under test: chunk the corpus, embed with `bge-small-en-v1.5`, build a FAISS index, and measure whether the chunk containing each probe's gold sentence is retrieved in the top-k. Output: `results.json`. |
| (analysis) | Read `results.json` into the tables/recommendation captured at the bottom of this doc. |

`recall@k` = the fraction of probe questions for which the chunk holding the gold answer
sentence appears in the top *k* retrieved chunks. It is the single metric that decides whether
retrieval can succeed *at all* — no downstream prompt engineering can recover an answer whose
evidence was never retrieved.

## 2. Why we are doing it

- **The assignment's core discipline is "measure recall@k *before* you blame the model."**
  If System C (fine-tune + retrieval) gives a weak answer, we must already know whether the
  retriever even surfaced the right passage. This study builds that measurement habit — and the
  actual thresholds — before we have spent a rupee on GPUs.
- **Every knob here silently caps System C's ceiling.** Chunk size, embedding model, and top-k
  are decided *now*, in Phase 1/4, but their consequences only show up in the Phase 5
  leaderboard. Testing them up front means the final comparison measures the *model*, not an
  un-tuned retriever.
- **The assignment explicitly asks us to *justify* our choices** ("any embedding model is fine
  as long as you say which one and why"; "if a flat index is reasonable, say so"). This study
  replaces assertions with evidence.
- **It is nearly free.** A 0.32 MB sample, ~60 flash-lite calls (≈ $0.01), and CPU embedding —
  no GPU. The cost of *not* doing it is a day lost in Phase 4/5 to a quietly bad retriever.

## 3. Exact outputs we are trying to find

Each row is a decision the study must return with a number attached, and where that decision
gets used.

| # | Question the run answers | Concrete output | Feeds |
|---|--------------------------|-----------------|-------|
| 1 | Best **chunk size** (500–1500 chars) | recall@k per size, at fixed 15% overlap | Phase 1 chunking |
| 2 | Is **150 overlap** justified, or is more/less/none better? | recall@k per overlap at size=1000 | Phase 1 chunking |
| 3 | Which **embedding model** wins on this domain? | recall@k for bge-small vs 2–3 alternatives, + size/speed | Phase 4 embedder |
| 4 | What **top-k** to feed System C? | the k where the recall curve plateaus | Phase 4/5 generation |
| 5 | Does the **bge query-instruction prefix** help here? | recall@k with vs without the prefix | Phase 4 query encoding |
| 6 | Does **title-augmentation** (prepend page title to chunk) help? | recall@k with vs without title | Phase 1/4 chunking |
| 7 | Is a **flat** index enough, or do we need IVF? | recall@k flat vs IVF across nprobe | Phase 4 index type |
| 8 | Are our **target question types** (interaction/timing) harder to retrieve than definitions? | recall@k broken down by question category | Phase 5 interpretation |
| 9 | A **quality-gate threshold**: what retrieval score separates good vs bad generated pairs? | score distribution of answerable vs unanswerable probes | Phase 2 gating |
| 10 | How does **Gemini flash-lite fail** as a question writer? | qualitative review of the worst probes | Phase 2 teacher prompt |
| 11 | Is the retriever **feasible/cheap** at full 20 MB scale? | embed throughput, index build time, memory, extrapolation | Phase 4 serving sizing |
| 12 | Retrieval **latency** (p50/p95) | per-query search time | `/retrieve` endpoint SLA |

**Proposed (pending confirmation):**
- #13 **Hybrid dense + BM25** vs pure dense — because exact card names ("Effect Veiler") are a
  known weak spot for dense embeddings and a strength of lexical search. Needs `rank-bm25`.

**Deferred (out of scope for this pass):**
- Cross-encoder **reranking** — adds latency/compute for uncertain gain at this corpus size.

The single headline deliverable is a **recommended retriever configuration** (chunk size,
overlap, embedding model, top-k, index type, and whether to use title-aug / hybrid), each line
backed by a number from `results.json`.

## 4. What this experiment cannot / does not cover

Stated honestly, because these caveats bound how far the results generalize:

- **It is a proxy, not the final corpus.** The sample is ~50 pages / 0.32 MB drawn from a seed
  list; the real corpus will be ≥ 20 MB and category-enumerated. Absolute recall numbers will
  shift on the full corpus (more chunks = more distractors, usually lower recall). We treat the
  *ranking* of configs as transferable, not the absolute values, and we **re-confirm the chosen
  config on the real corpus in Phase 4.**
- **Probes are synthetic, not the held-out test set.** Questions are generated from single
  sentences by the same teacher we will later gate. They approximate real user questions but
  are not the Phase-2 `heldout.jsonl` (which will have human-checked gold + evidence). This
  study tunes the *retriever*, it does not grade *systems A/B/C*.
- **Single-sentence gold is a simplification.** A probe's gold is one sentence; many real
  ruling answers span multiple sentences or multiple passages (multi-hop). Recall here measures
  single-passage retrieval only; multi-hop retrieval is not tested.
- **Substring gold-matching is exact.** A chunk "contains" the gold only if the exact sentence
  string is inside it. Sentence-boundary/whitespace quirks could undercount a near-miss. This is
  conservative (it can under-report recall, not inflate it).
- **No generation, no judge, no significance test.** This experiment stops at retrieval. It says
  nothing about answer quality, faithfulness, or whether fine-tuning helps — those are Phases 3
  and 5, with the paired-bootstrap eval described in `PLAN.md`.
- **Domain and teacher fixed.** One domain (Yu-Gi-Oh), one teacher (Gemini flash-lite), one
  seed. Results are not claimed to generalize to other domains or teachers.
- **Embedding models compared at default settings.** No fine-tuning of the embedder, no
  domain-adaptive training — off-the-shelf checkpoints only.

## 5. How to reproduce

```bash
# from repo root, with the venv active
.venv/Scripts/python.exe rag/chunking_study/fetch_sample.py     # -> sample_corpus.jsonl
# set GEMINI_API_KEY first (user env var); optional GEMINI_MODEL
.venv/Scripts/python.exe rag/chunking_study/make_probes.py      # -> probes.jsonl
.venv/Scripts/python.exe rag/chunking_study/benchmark.py        # -> results.json + tables
```

Deterministic where it can be: fixed sentence-sampling seed (`SEED = 20260801`) and fixed
config lists. Gemini question wording is not perfectly reproducible run-to-run; `probes.jsonl`
is committed so the exact probe set used for a result is preserved.

## 6. Results (run 2026-08-01)

Run metadata: 52 sample docs (0.32 MB prose), 60 probes (~54 with gold that fits a chunk),
baseline chunk 1000/150, `bge-small-en-v1.5` unless noted. Full numbers in
`rag/chunking_study/results.json`.

**Read the gaps, not the decimals.** At 54 covered probes, differences of a few points are
noise; only large, consistent gaps are trustworthy. The trustworthy findings: hybrid/BM25 >>
dense-bge; MiniLM/e5 > bge; flat >= IVF; lore is the hardest question type; score-gating fails.

### Study 7 — Hybrid dense+BM25 (the headline)
| method | r@1 | r@3 | r@5 | r@10 |
|---|---|---|---|---|
| dense (bge-small) | 0.352 | 0.648 | 0.741 | 0.852 |
| BM25 alone | 0.519 | 0.759 | 0.815 | 0.852 |
| **hybrid (RRF)** | **0.537** | **0.759** | **0.833** | **0.870** |

Exact card names/terms matter in this domain, so lexical BM25 alone beats dense-bge, and hybrid
is best. **Retrieval will be hybrid.**

### Study 3 — Embedding model bake-off
| model | r@1 | r@5 | r@10 | encode (52 docs) |
|---|---|---|---|---|
| bge-small-en-v1.5 | 0.352 | 0.741 | 0.852 | 17.2 s |
| gte-small | 0.407 | 0.815 | 0.870 | 142 s (anomalously slow path) |
| e5-small-v2 | 0.426 | 0.796 | 0.870 | 17.5 s |
| **all-MiniLM-L6-v2** | **0.519** | **0.833** | 0.870 | **7.9 s** |

bge (the assignment's reference) is the weakest dense model here; MiniLM-L6 is best **and**
fastest. Brief permits any embedder "as long as you say which one and why" — so this is a valid,
justified change. Resolved by the follow-up below.

### Follow-up — hybrid × dense model (resolves the open item)
| method | r@1 | r@3 | r@5 | r@10 |
|---|---|---|---|---|
| bm25-only | 0.519 | 0.759 | 0.815 | 0.852 |
| hybrid[bge+bm25] | 0.537 | 0.759 | 0.833 | 0.870 |
| hybrid[e5-small+bm25] | 0.481 | 0.778 | 0.833 | 0.870 |
| **hybrid[MiniLM-L6+bm25]** | **0.574** | **0.815** | **0.870** | **0.907** |

MiniLM-L6 as the dense half wins at every k and is the fastest encoder.
**Decision: dense = `all-MiniLM-L6-v2`, fused with BM25 via RRF.**

### Studies 1/2 — Chunk size & overlap
Size: r@5 peaks around 1000-1200 (1000=0.741, 1200=0.764); r@10 best at 1000 (0.852). Size 500
loses coverage (gold sentences > 500 chars can't fit). Overlap: benefit is small/noisy; 150 helps
r@10 (0.852 vs 0.808 at overlap 0). **Keep 1000/150** — defensible, not the bottleneck.

### Study 6 — Flat vs IVF
Flat >= IVF at every nprobe; IVF at nprobe=1 collapses to r@5 0.481 (a live demo of the "too few
probes" trap); at 393 points IVF can't even train (needs 741). **Use flat** (confirmed reasonable
by the brief at our scale).

### Study 8 — Recall by question type
| category | n | r@5 | r@10 |
|---|---|---|---|
| interaction | 30 | 0.759 | 0.862 |
| timing | 15 | 0.818 | 0.909 |
| lore | 10 | 0.556 | 0.778 |
| definition | 2 | 1.0 | 1.0 |

Our **target types (interaction, timing) retrieve well**; **lore is the hardest** and least
central. Informs Phase-5 interpretation.

### Studies 4/5 — Query prefix & title-augmentation
Prefix on/off: negligible (r@5 0.741 vs 0.685, within noise). Title-aug: marginal positive
(r@5 0.778 vs 0.741). **Keep title-aug (free); prefix doesn't matter.**

### Study 9 — Gate calibration (negative result)
Top-1 similarity for *retrieved* probes (mean 0.764, range 0.605-0.859) vs *missed* (mean 0.743,
range 0.583-0.849) **overlap almost entirely**. A similarity threshold **cannot** reliably gate
pair quality. **Phase-2 gating must use the LLM judge, not a retrieval score.**

### Study 10 — Feasibility
0.32 MB -> 393 chunks; extrapolated to 20 MB: ~24,500 chunks, ~38 MB index, ~23 min one-time CPU
embedding, search **p50 0.026 ms / p95 0.034 ms**. Retriever fits a tiny CPU container; cost
negligible.

### Recommended retriever configuration
| Parameter | Decision | Basis |
|-----------|----------|-------|
| Retrieval method | **hybrid dense + BM25 (RRF)** | Study 7 (large win) |
| Dense model | **all-MiniLM-L6-v2** (fused with BM25) | Study 3 + follow-up |
| Chunk size / overlap | **1000 / 150** | Studies 1-2 |
| Index | **flat** | Study 6 + brief |
| Top-k for System C | **5** (r@5 ~0.83; ~0.87 at 10) | Study 7 |
| Title-augmentation | **on** | Study 5 |
| Query prefix | off / don't-care | Study 4 |
| Phase-2 gating | **LLM judge, not score threshold** | Study 9 |

**Re-confirm the chosen config on the full ≥20 MB corpus in Phase 4** — these numbers are from a
0.32 MB proxy (see §4 limitations); the config *ranking* transfers, absolute recall will move.

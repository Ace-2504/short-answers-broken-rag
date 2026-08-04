# Yu-Gi-Oh SLM — Fine-tune vs. Retrieval

Reproducing the course experiment on a new domain (Yu-Gi-Oh! rulings & card facts): does fine-tuning
a small LLM on Q&A pairs teach it *facts*, or only the *shape* of an answer — and how much does
retrieval add on top? Three systems, one held-out set, a reference-grounded judge.

| System | What it is |
|--------|------------|
| **A** | `google/gemma-2-2b-it`, untouched, closed book |
| **B** | Our QLoRA fine-tune of Gemma 2 2B, closed book |
| **C** | Same fine-tune, with our hybrid retriever supplying passages (RAG) |

## Headline result (n = 60, reference-grounded judge, /10)

| System | mean ± SE | vs. previous |
|---|---|---|
| A base, closed | 3.98 ± 0.39 | — |
| B fine-tune, closed | 5.25 ± 0.54 | **+1.27**, p = 0.007 (significant) |
| C fine-tune + retrieval | **8.05 ± 0.42** | **+2.80**, p < 0.001 (significant) |

**What we found (and it partly disagrees with the class reference):** retrieval is the decisive win
(C ≫ B). But fine-tuning *also* significantly beat base closed-book (B > A) — where the reference
found it did not. The gain is concentrated in **groundedness** (0.18 → 0.87), i.e. answer *shape*,
not facts (the facts arrive only with retrieval). So "fine-tuning teaches shape, not facts" still
holds; it just mattered more here. Full analysis: [`docs/eval-plan.md`](docs/eval-plan.md) §8 and the
[results dossier](report/results-dossier.html).

## Links

- **Model (HF Hub):** https://huggingface.co/Ace-2504/gemma-2-2b-yugioh-qa
- **Live site (Vercel):** https://site-eight-liard-61.vercel.app
- **Endpoints** (cloudflared tunnel to the local RTX 3060 — must be running for the live site):
  - `/ask` (orchestrates all three systems + returns C's passages): `https://tennis-frost-biology-presidential.trycloudflare.com/ask`
  - `/generate` (base via `use_base`, and fine-tune): same server, `…/generate`
  - `/retrieve` (retriever, top-k chunks + scores + source): `http://localhost:8200/retrieve` (internal; called by `/ask`)

  > The tunnel URL is ephemeral (regenerated when cloudflared restarts). If the site can't reach the
  > model, restart the servers + tunnel and update `ENDPOINT` in `site/index.html` (then redeploy).
- **Total cost:** ≈ **$3** of the $25 budget (Modal L4 training ~$0.60, all Gemini calls < $2, retriever/eval local). Per-experiment log: [`costs.md`](costs.md).

## Stack

- **Corpus:** Yugipedia prose (CC BY-SA 4.0, attributed) + YGOPRODeck card facts (free; card text as
  labeled fair-use context). 20.7 MB free prose + 14,477 card-fact passages.
- **Fine-tune:** QLoRA (r16/α32, all-linear, LR 2e-4, seq 512, bf16) on Modal **L4**; early-stopped ~1
  epoch (3 overfit). Val perplexity **3.87** (class ref 4.26).
- **Retriever:** **all-MiniLM-L6-v2** embeddings (chosen over the brief's bge-small after a recall@k
  study — see `docs/initial-testing.md`) in a **FAISS flat + BM25 hybrid (RRF)**, top-5, over 42,412
  chunks. Flat is fine at this scale.
- **Teacher / judge:** Gemini flash-lite. **Stats:** paired bootstrap CI + t-test + Wilcoxon.

## Repository layout

```
data/     DATA.md (dataset card + honest funnel), train.jsonl (2,683), heldout.jsonl (60), collect/ (scripts)
finetune/ QA-generation pipeline (teacher gen + VALIDATE gauntlet with LLM judge)
train/    modal_finetune_gemma.py, loss_curve.png, MODEL_CARD.md, serve_local.py (+ /ask gateway)
rag/      build_index.py, retrieve.py (/retrieve endpoint), recall_at_k.py, recall_at_k.json, chunking_study/
eval/     run_eval.py, judge.py, leaderboard.py, responses.json, verdicts.json, leaderboard.json
site/     index.html — the deployed A/B/C frontend
report/   report.pdf (one page) + results-dossier.html (full stats)
docs/     per-phase specs & analyses;  story.md  running build log;  costs.md
```

## Reproduce, in order

```bash
# 0. environment
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/hf.exe auth login --force        # WRITE token (gated Gemma + Hub push)
.venv/Scripts/modal.exe token new
setx GEMINI_API_KEY <key>                       # teacher + judge

# 1. corpus (Part 1) — collect, then clean
.venv/Scripts/python.exe data/collect/fetch_corpus.py      # Yugipedia prose -> data/corpus/corpus.jsonl
.venv/Scripts/python.exe data/collect/fetch_cardfacts.py   # YGOPRODeck   -> data/corpus/cardfacts.jsonl
APPLY=1 .venv/Scripts/python.exe data/collect/clean_corpus.py  # -> corpus_clean.jsonl (see docs/corpus-cleaning-system.md)

# 2. supervised set (Part 1) — teacher QA -> judge gauntlet -> train.jsonl + heldout.jsonl
.venv/Scripts/python.exe finetune/build_heldout.py         # -> data/heldout.jsonl (60, gold+evidence)
.venv/Scripts/python.exe finetune/generate_dataset.py      # -> finetune/raw_qa.jsonl
.venv/Scripts/python.exe finetune/validate_gauntlet.py     # G1-G5 (incl. LLM judge) -> data/train.jsonl

# 3. fine-tune Gemma 2 2B (Part 2) — QLoRA on Modal, pushes adapter + saves loss curve
modal run train/modal_finetune_gemma.py

# 4. retriever (Part 3) — build index, then recall@k
.venv/Scripts/python.exe rag/build_index.py                # -> rag/index/ (FAISS + BM25)
.venv/Scripts/python.exe rag/recall_at_k.py                # -> rag/recall_at_k.json (k=1/3/5/10)

# 5. serve (Parts 2-3) — retriever, then model+/ask, then a public tunnel
.venv/Scripts/python.exe -m uvicorn rag.retrieve:app       --port 8200 &
.venv/Scripts/python.exe -m uvicorn train.serve_local:app  --port 8100 &   # /generate, /ask
cloudflared tunnel --url http://localhost:8100             # public /ask URL -> put in site/index.html

# 6. evaluate all three (Part 4) — needs :8100 + :8200 up
.venv/Scripts/python.exe eval/run_eval.py                  # -> eval/responses.json (A/B/C, greedy)
.venv/Scripts/python.exe eval/judge.py                     # -> eval/verdicts.json (reference-grounded, blind)
.venv/Scripts/python.exe eval/leaderboard.py               # -> eval/leaderboard.json + paired stats

# 7. site (Part 5) — set ENDPOINT in site/index.html to the tunnel /ask URL, then deploy
cd site && vercel --prod
```

Notes: `data/corpus/*`, `rag/index/*`, and the `finetune/` intermediate `.jsonl` are git-ignored
(size + © card text); the committed deliverables are the scripts, `DATA.md`, `train.jsonl`,
`heldout.jsonl`, and the eval JSON. The build was done phase-by-phase — the full narrative (including
missteps) is in [`story.md`](story.md).

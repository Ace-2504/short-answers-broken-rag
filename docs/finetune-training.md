# Phase 3 — QLoRA Fine-Tune Plan (Gemma 2 2B)

**Status:** planned / not built — the Modal script is written and run only after Harman signs off
on the config below.
**Location:** `train/` (scripts to be built).
**Date:** 2026-08-01

> Same discipline as the Phase-2 pilot: fix the exact configuration first (the brief *requires*
> reporting every knob), then build and run. Values marked `⟨verify⟩` are proposals to confirm.

---

## 1. What we are doing

Fine-tune **`google/gemma-2-2b-it`** with **QLoRA** on our 2,683-pair SFT set — a **single,
closed-book QA fine-tune**. This one adapter is **System B**; **System C is the *same* fine-tuned
model with retrieval prepended at inference** (no separate training). System A is the untouched
base. So Phase 3 produces exactly one trained artifact that serves both B and C.

**Deliverables (brief, Part 2):** the training script, train/val **loss curves**, final **validation
perplexity**, a **public HF Hub** adapter with a model card, and a **live scale-to-zero endpoint**.

## 2. Why this shape

- **One model, two systems.** B and C differ only by whether retrieval feeds passages at inference
  — training once keeps the comparison clean (the experiment isolates *retrieval*, not two models).
- **QLoRA, not full FT.** 4-bit base + small LoRA adapters fit a single L4, cost pennies, and match
  the brief's reference setup. Full FT is unnecessary at 2B / 2.7k pairs.

## 3. Training configuration (proposed — the report must list all of these)

| Knob | Proposed | Rationale |
|------|----------|-----------|
| Base model | `google/gemma-2-2b-it` | assignment-mandated |
| Method | QLoRA (4-bit NF4, double-quant) | brief's reference; fits L4 |
| LoRA rank `r` | **16** ⟨verify⟩ | standard for a few-thousand-pair SFT |
| LoRA alpha | **32** (2×r) ⟨verify⟩ | common 2×rank scaling |
| LoRA dropout | 0.05 | light regularization |
| Target modules | `q,k,v,o,gate,up,down _proj` (all linear) ⟨verify⟩ | QLoRA-paper practice, best quality |
| Learning rate | **2e-4** ⟨verify⟩ | standard LoRA LR |
| Schedule | cosine, warmup ratio 0.03 | stable SFT |
| Optimizer | `paged_adamw_8bit` | QLoRA standard, memory-safe |
| Epochs | **3** ⟨verify⟩ | typical for ~2.7k SFT pairs |
| Max seq length | **512** ⟨verify⟩ | our pairs are short (q≈110c, a≈107c + system) — no truncation |
| Per-device batch | 8 | fits L4 24 GB at 4-bit / seq 512 |
| Grad accumulation | 2 → **effective batch 16** | smooth updates |
| Compute dtype | **bfloat16** | train + serve in bf16 |
| Grad checkpointing | on | memory |
| Trainer | `trl` SFTTrainer over the chat template | applies Gemma's turn format |

Reference yardstick: the class's Gemma closed-book stage hit **val perplexity 4.26** — a sanity
target, not a goal.

## 4. Data handling

- **Train/val split** (the "val is a thermometer" rule): carve **~2% (~54 pairs)** from
  `train.jsonl`, seeded, as an eval set for the loss curve + final val perplexity. This val set is
  **separate from `heldout.jsonl`** (the 60-item Phase-5 test set — never touched here).
- **Chat template / system role:** `train.jsonl` rows are `system+user+assistant`. Gemma 2's
  template has **no native system role**, so the script **folds the system content into the first
  user turn** before applying the template. Loss is computed on the **assistant tokens only**
  (mask the prompt). ⟨verify: fold-system approach⟩
- Data is small (~2 MB) → upload to a Modal Volume (or bake into the image).

## 5. Modal architecture

- **App:** `train/modal_finetune_gemma.py`. Image = python + torch + transformers + peft +
  bitsandbytes + trl + accelerate + datasets + matplotlib.
- **GPU: L4** ⟨verify — vs A100⟩ — 24 GB is enough for 2B QLoRA; cheapest. (Matches prior Modal L4
  QLoRA work on this account.)
- **Secret:** `modal.Secret.from_name("hf-token")` (already exists on `ace-2504`) for the gated
  Gemma download **and** the Hub push. *(Confirm the secret exposes `HF_TOKEN`.)*
- **Run:** `modal run` (one-shot training job, not a persistent service).

## 6. Outputs

- **Adapter → HF Hub**, public, with a model card stating training data/domain/config.
  Repo: **`Ace-2504/gemma-2-2b-yugioh-qa`** ⟨verify name⟩.
- **Loss curves** (train + val) saved as a PNG (to the volume / downloaded) → committed under `train/`.
- **Final validation perplexity** printed and recorded in the report + `costs.md`.

## 7. Serving (the live endpoint + the trap)

- A **separate** Modal function serves the fine-tune over HTTP with **scale-to-zero**.
- **The brief's trap:** never serve base + adapter from one process toggling per request —
  concurrent requests race and silently serve the wrong model. **Serve each system from its own
  container, or serialize requests.** (We already have this shape locally in `serve_api.py`.)
- Full A/B/C serving for the site is Phase 5/6; Phase 3 just needs the fine-tune's endpoint live.

## 8. Cost

QLoRA 2B, 3 epochs over 2,683 pairs ≈ ~500 steps; on L4 ~10–15 min wall incl. model download →
**≈ $0.20–0.40 per run**. Even several runs stay far under the $8–15 budget line. Logged in `costs.md`.

## 9. What this does NOT cover / risks

- **Not** whether B beats A — that's Phase 5 (paired-bootstrap judge). Low val perplexity ≠ a
  better system; the brief's whole point is fine-tuning may *not* help closed-book.
- **No RAFT/context-in-training** — System C uses retrieval at inference over this same model; we
  do not train a separate retrieval-augmented adapter (kept minimal per the brief).
- One seed, one config unless a sweep is warranted.

## 10. Reproduce (once built)

```bash
modal run train/modal_finetune_gemma.py        # trains, pushes adapter, saves loss curve
modal deploy train/serve_finetune.py           # scale-to-zero endpoint (later)
```

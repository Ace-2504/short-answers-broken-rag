---
base_model: google/gemma-2-2b-it
library_name: peft
license: gemma
tags:
  - qlora
  - lora
  - gemma-2
  - yu-gi-oh
  - question-answering
  - sft
---

# Gemma 2 2B — Yu-Gi-Oh QA (QLoRA)

A QLoRA fine-tune of `google/gemma-2-2b-it` on grounded Yu-Gi-Oh question–answer pairs. Built for a
**fine-tune-vs-retrieval experiment**: this adapter is *System B* (closed-book); with a retriever
supplying passages at inference it becomes *System C*.

## What it was trained on

- **2,683 grounded QA pairs**, distilled by a teacher LLM (Gemini flash-lite) from a curated
  Yu-Gi-Oh corpus: **Yugipedia** editorial prose (CC BY-SA 4.0 — rulings, card tips, archetype &
  game-mechanics articles) + **YGOPRODeck** structured card facts.
- Every pair was verified by an LLM judge for grounding/correctness (81 wrong answers rejected,
  plus dedup/decontamination against the held-out test set).
- Distribution: **~85% interaction/timing** (rulings-focused) questions, ~55% multi-step.
- Card-knowledge cutoff: a **2026-08-01 YGOPRODeck snapshot**.

## Training

- QLoRA: 4-bit NF4 base, bf16 compute; LoRA **r=16, α=32**, dropout 0.05, all linear target modules
  (`q,k,v,o,gate,up,down_proj`).
- LR **2e-4** cosine (3% warmup), `paged_adamw_8bit`, seq len 512, effective batch 16.
- **Early-stopped at the best validation checkpoint (~1 epoch)** — 3 epochs overfit this set.
- **Validation perplexity: 3.872**. Single **L4** GPU on Modal.

## Intended use & limitations

- Best used **with retrieval** for factual card questions; closed-book it may hallucinate specific
  card details.
- **Not** intended to reproduce verbatim copyrighted card text — Konami / © content was used only as
  fair-use training context, never as a verbatim-recall target.
- A rare fraction (~0–4%) of source rulings pages contained superseded ("previously official")
  rulings; see the dataset card for details.

## Reproduce

Training script and full data pipeline: the assignment repo (`train/modal_finetune_gemma.py`,
`data/generate/`, `data/DATA.md`).

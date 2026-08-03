"""Phase 3: QLoRA fine-tune of google/gemma-2-2b-it on the Yu-Gi-Oh SFT set (Modal L4).

Trains ONE closed-book QA adapter = System B (System C = same model + retrieval at
inference). Pushes the adapter to the HF Hub, saves the train/val loss curve, and
reports final validation perplexity.

Run:  modal run train/modal_finetune_gemma.py
"""
import modal

BASE = "google/gemma-2-2b-it"
HF_REPO = "Ace-2504/gemma-2-2b-yugioh-qa"
SEED = 20260801

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.4.0", "transformers==4.44.2", "trl==0.9.6", "peft==0.12.0",
        "bitsandbytes==0.43.3", "accelerate==0.33.0", "datasets==2.21.0",
        "matplotlib==3.9.2", "huggingface_hub==0.24.6", "sentencepiece==0.2.0", "rich",
    )
    .add_local_file("data/train.jsonl", "/data/train.jsonl")   # local files added last (Modal 1.x)
)
app = modal.App("gemma-yugioh-qa")

@app.function(gpu="L4", image=image, timeout=60 * 60,
              secrets=[modal.Secret.from_name("hf-token")])
def train():
    import os, json, math, random
    import torch
    from datasets import Dataset
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from peft import LoraConfig
    from trl import SFTTrainer, SFTConfig, DataCollatorForCompletionOnlyLM
    from huggingface_hub import login
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    login(token=token)

    # ---- data: fold system into the user turn (Gemma has no system role) ----
    rows = [json.loads(l) for l in open("/data/train.jsonl", encoding="utf-8")]
    random.Random(SEED).shuffle(rows)
    n_val = max(20, int(0.02 * len(rows)))
    val_rows, train_rows = rows[:n_val], rows[n_val:]

    tok = AutoTokenizer.from_pretrained(BASE, token=token)
    tok.padding_side = "right"

    def to_text(r):
        m = {x["role"]: x["content"] for x in r["messages"]}
        user = (m.get("system", "") + "\n\n" + m["user"]).strip()
        chat = [{"role": "user", "content": user},
                {"role": "assistant", "content": m["assistant"]}]
        return tok.apply_chat_template(chat, tokenize=False)

    train_ds = Dataset.from_dict({"text": [to_text(r) for r in train_rows]})
    val_ds = Dataset.from_dict({"text": [to_text(r) for r in val_rows]})
    print(f"train={len(train_ds)}  val={len(val_ds)}")

    # ---- 4-bit model + LoRA ----
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        BASE, quantization_config=bnb, torch_dtype=torch.bfloat16,
        token=token, attn_implementation="eager")
    model.config.use_cache = False
    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
                      task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                      "gate_proj", "up_proj", "down_proj"])

    collator = DataCollatorForCompletionOnlyLM(
        response_template="<start_of_turn>model\n", tokenizer=tok)

    from transformers import EarlyStoppingCallback
    cfg = SFTConfig(
        output_dir="/tmp/out", num_train_epochs=3, per_device_train_batch_size=8,
        gradient_accumulation_steps=2, learning_rate=2e-4, lr_scheduler_type="cosine",
        warmup_ratio=0.03, optim="paged_adamw_8bit", bf16=True, logging_steps=10,
        eval_strategy="steps", eval_steps=25, save_strategy="steps", save_steps=25,
        load_best_model_at_end=True, metric_for_best_model="eval_loss",
        greater_is_better=False, save_total_limit=1, max_seq_length=512,
        gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False},
        packing=False, dataset_text_field="text", report_to="none", seed=SEED)

    # 3-epoch run overfit (val loss bottomed ~epoch 1 then rose); early-stop + keep best.
    trainer = SFTTrainer(model=model, args=cfg, train_dataset=train_ds, eval_dataset=val_ds,
                         tokenizer=tok, peft_config=lora, data_collator=collator,
                         callbacks=[EarlyStoppingCallback(early_stopping_patience=3)])
    trainer.train()

    # ---- val perplexity + loss curve ----
    metrics = trainer.evaluate()
    ppl = math.exp(metrics["eval_loss"])
    print(f"FINAL eval_loss={metrics['eval_loss']:.4f}  val_perplexity={ppl:.3f}")
    hist = trainer.state.log_history
    tr = [(h["step"], h["loss"]) for h in hist if "loss" in h]
    ev = [(h["step"], h["eval_loss"]) for h in hist if "eval_loss" in h]
    plt.figure()
    if tr: plt.plot(*zip(*tr), label="train")
    if ev: plt.plot(*zip(*ev), label="val")
    plt.xlabel("step"); plt.ylabel("loss"); plt.legend()
    plt.title(f"Gemma-2-2B QLoRA · Yu-Gi-Oh QA (val ppl {ppl:.2f})")
    plt.tight_layout(); plt.savefig("/tmp/loss_curve.png", dpi=120)
    png = open("/tmp/loss_curve.png", "rb").read()

    # ---- push adapter + tokenizer to the Hub ----
    trainer.model.push_to_hub(HF_REPO, token=token)
    tok.push_to_hub(HF_REPO, token=token)
    print(f"pushed adapter -> https://huggingface.co/{HF_REPO}")
    return {"val_perplexity": ppl, "eval_loss": metrics["eval_loss"], "loss_png": png}

@app.local_entrypoint()
def main():
    out = train.remote()
    with open("train/loss_curve.png", "wb") as f:
        f.write(out["loss_png"])
    print(f"DONE  val_perplexity={out['val_perplexity']:.3f}  "
          f"eval_loss={out['eval_loss']:.4f}  -> train/loss_curve.png")

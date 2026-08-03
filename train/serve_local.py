"""Local inference server for the fine-tuned Yu-Gi-Oh model (System B / C).

Loads google/gemma-2-2b-it + the Ace-2504/gemma-2-2b-yugioh-qa QLoRA adapter (4-bit on
the local GPU, bf16 fallback) and exposes /generate. An optional `context` field lets the
same model act as System C (retrieval-augmented) later.

Run:  uvicorn train.serve_local:app --host 0.0.0.0 --port 8100
"""
import os
import contextlib
from typing import Optional
import torch
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

BASE = "google/gemma-2-2b-it"
ADAPTER = "Ace-2504/gemma-2-2b-yugioh-qa"
SYS = ("You are a helpful Yu-Gi-Oh expert. Answer the question using the rules and rulings "
       "you know.")

print("loading tokenizer + model ...")
tok = AutoTokenizer.from_pretrained(BASE)

def load_model():
    cuda = torch.cuda.is_available()
    try:
        if not cuda:
            raise RuntimeError("no cuda -> cpu path")
        from transformers import BitsAndBytesConfig
        bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                 bnb_4bit_compute_dtype=torch.bfloat16,
                                 bnb_4bit_use_double_quant=True)
        m = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb,
                torch_dtype=torch.bfloat16, device_map="cuda:0", attn_implementation="eager")
        print("loaded 4-bit on GPU")
    except Exception as e:
        print(f"4-bit path failed ({e}); loading bf16 on {'cuda' if cuda else 'cpu'}")
        m = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.bfloat16,
                device_map=("cuda:0" if cuda else None), attn_implementation="eager")
        if not cuda:
            m = m.to("cpu")
    return m

model = PeftModel.from_pretrained(load_model(), ADAPTER)
model.eval()
DEVICE = next(model.parameters()).device
print(f"ready on {DEVICE}")

app = FastAPI(title="gemma-2-2b-yugioh-qa")

class Req(BaseModel):
    question: str
    context: Optional[str] = None          # supply retrieved passages -> System C
    use_base: bool = False                 # True -> disable adapter -> untouched base (System A)
    max_new_tokens: int = 220
    temperature: float = 0.3

@app.get("/health")
def health():
    return {"ok": True, "adapter": ADAPTER, "device": str(DEVICE)}

@app.post("/generate")
def generate(r: Req):
    if r.context:
        user = (f"Use ONLY the following context to answer.\n\nContext:\n{r.context}\n\n"
                f"Question: {r.question}")
    else:
        user = r.question
    user = (SYS + "\n\n" + user).strip()
    enc = tok.apply_chat_template([{"role": "user", "content": user}],
                                  add_generation_prompt=True, return_tensors="pt",
                                  return_dict=True).to(DEVICE)
    input_len = enc["input_ids"].shape[1]
    # sequential eval only -> toggling the adapter per request is safe (no concurrency race)
    adapter_ctx = model.disable_adapter() if r.use_base else contextlib.nullcontext()
    with torch.no_grad(), adapter_ctx:
        out = model.generate(**enc, max_new_tokens=r.max_new_tokens,
                             do_sample=r.temperature > 0, temperature=max(r.temperature, 1e-4),
                             top_p=0.9, pad_token_id=tok.eos_token_id)
    text = tok.decode(out[0][input_len:], skip_special_tokens=True).strip()
    return {"answer": text, "system": "base" if r.use_base else "finetune"}

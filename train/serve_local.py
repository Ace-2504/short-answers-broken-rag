"""Local inference server for the fine-tuned Yu-Gi-Oh model (System B / C).

Loads google/gemma-2-2b-it + the Ace-2504/gemma-2-2b-yugioh-qa QLoRA adapter (4-bit on
the local GPU, bf16 fallback) and exposes /generate. An optional `context` field lets the
same model act as System C (retrieval-augmented) later.

Run:  uvicorn train.serve_local:app --host 0.0.0.0 --port 8100
"""
import os
import contextlib
from typing import Optional
import requests
import torch
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

RETRIEVER_URL = os.environ.get("RETRIEVER_URL", "http://localhost:8200/retrieve")

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
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def _gen(question, context=None, use_base=False, max_new_tokens=220, temperature=0.0):
    if context:
        user = (f"Use ONLY the following context to answer.\n\nContext:\n{context}\n\n"
                f"Question: {question}")
    else:
        user = question
    user = (SYS + "\n\n" + user).strip()
    enc = tok.apply_chat_template([{"role": "user", "content": user}], add_generation_prompt=True,
                                  return_tensors="pt", return_dict=True).to(DEVICE)
    input_len = enc["input_ids"].shape[1]
    adapter_ctx = model.disable_adapter() if use_base else contextlib.nullcontext()
    with torch.no_grad(), adapter_ctx:
        out = model.generate(**enc, max_new_tokens=max_new_tokens,
                             do_sample=temperature > 0, temperature=max(temperature, 1e-4),
                             top_p=0.9, pad_token_id=tok.eos_token_id)
    return tok.decode(out[0][input_len:], skip_special_tokens=True).strip()

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
    text = _gen(r.question, r.context, r.use_base, r.max_new_tokens, r.temperature)
    return {"answer": text, "system": "base" if r.use_base else "finetune"}

class AskReq(BaseModel):
    question: str
    k: int = 5

@app.post("/ask")
def ask(r: AskReq):
    """One call -> all three systems (A base, B fine-tune, C fine-tune+retrieval) + C's passages.
    Sequential, so the per-request adapter toggle for A is safe."""
    a = _gen(r.question, use_base=True)
    b = _gen(r.question, use_base=False)
    try:
        passages = requests.post(RETRIEVER_URL, json={"question": r.question, "k": r.k},
                                 timeout=30).json()["passages"]
    except Exception as e:
        passages = []
        print(f"retriever error: {e}")
    ctx = "\n\n".join(f"[{p['title']}] {p['text']}" for p in passages)
    c = _gen(r.question, context=ctx, use_base=False) if ctx else "(retriever unavailable)"
    return {"question": r.question, "A": a, "B": b, "C": c, "passages": passages}

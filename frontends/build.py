#!/usr/bin/env python
"""Generate + (optionally) deploy the three individual Yu-Gi-Oh SLM frontends.

Matches the SLM-Engineering single-model page 1:1 — the verbatim research-lab-theme
globals.css, the .brand authorship pill, conic theme swatches, .badge/.badge-accent
status, the always-orange .btn-primary ask button, architecture/training/corpus/cost
sections, and cross-links that open in a new tab.

  python frontends/build.py           # regenerate the 3 pages (+ sync site/ endpoint)
  python frontends/build.py deploy     # regenerate, deploy all 3, alias to clean domains

ONE place to change the tunnel: edit BASE below.
"""
import os, re, sys, json, subprocess, pathlib

# ---- the ONE source of truth for the live inference endpoint ----
BASE = "https://latinas-kennedy-exams-intervention.trycloudflare.com"

HERE = pathlib.Path(__file__).parent
REPO = HERE.parent
COMBINED_URL = "https://harman-ygo-slm.vercel.app"
GITHUB = "https://github.com/Ace-2504/does-my-ai-know-yugioh"
HF_BASE = "https://huggingface.co/google/gemma-2-2b-it"
HF_QA = "https://huggingface.co/Ace-2504/gemma-2-2b-yugioh-qa"
HF_RAG = "https://huggingface.co/Ace-2504/gemma-2-2b-yugioh-rag"
# per-system HuggingFace link + hero button label
HF_MAP = {"base": (HF_BASE, "HuggingFace weights →"), "finetune": (HF_QA, "HuggingFace adapter →"),
          "rag": (HF_RAG, "HuggingFace adapter →")}
DOMAINS = {"base": "harman-ygo-base", "finetune": "harman-ygo-finetune", "rag": "harman-ygo-rag"}
EXAMPLES = ["What is the ATK of Sky Striker Ace - Raye?", "Does Effect Veiler stop a Graveyard effect?",
            "Can you activate a normal Spell in the Damage Step?", "What two monster types make up the Kozmo archetype?"]

ARCH = [("Class", "Gemma2ForCausalLM"), ("Layers", "26"), ("Hidden size", "2,304"),
        ("Attention", "8 heads / 4 KV · dim 256 · GQA"), ("Feed-forward", "GeGLU · inner 9,216"),
        ("Attention window", "sliding 4,096 · logit soft-cap"), ("Norm", "RMSNorm"),
        ("Context", "8,192 tokens"), ("Vocabulary", "256,128"), ("Embeddings", "tied input/output")]
CORPUS = [("Yugipedia · tips", "rulings & interactions", "CC BY-SA 4.0", "8.47 MB", "31%"),
          ("Yugipedia · rulings", "rulings", "CC BY-SA 4.0", "5.90 MB", "22%"),
          ("YGOPRODeck · card facts", "card identity (stats + fair-use text)", "free / © Konami", "6.04 MB", "22%"),
          ("Yugipedia · archetype", "mechanics", "CC BY-SA 4.0", "2.74 MB", "10%"),
          ("Yugipedia · lore (ep + char)", "lore", "CC BY-SA 4.0", "3.92 MB", "14%"),
          ("Yugipedia · mechanics", "glossary", "CC BY-SA 4.0", "0.40 MB", "1%")]
COST = [("Teacher QA generation", "Gemini flash-lite → 2,796 pairs", "&lt; $0.70"),
        ("QA quality gating", "blind judge → 2,683 kept", "&lt; $0.50"),
        ("QLoRA fine-tune", "Gemma 2 2B on Modal L4", "&lt; $0.60"),
        ("Evaluation", "reference-grounded judge · 180 answers", "&lt; $0.30"),
        ("Retriever + serving + eval", "local RTX 3060", "$0"), ("Total", "", "≈ $3.00")]
TRAIN_B = [("Init from", "gemma-2-2b-it · 4-bit NF4"), ("Method", "QLoRA · rank-16 / α-32"),
           ("Targets", "all linear modules"), ("Trainable params", "20.8M LoRA (~0.8%)"),
           ("Schedule", "LR 2e-4 cosine · seq 512 · bf16"), ("Data", "2,683 QA pairs · early-stopped ~1 epoch"),
           ("Val perplexity", "3.87 (ref 4.26)"), ("Hardware", "Modal L4")]
TRAIN_C = TRAIN_B + [("Retriever", "MiniLM-L6 + BM25 · RRF"), ("Index", "FAISS flat · 42,412 chunks"), ("Top-k", "5 · recall@5 0.93")]

SYSTEMS = [
    dict(slug="base", letter="A", brand="Evaluated by Harman Sandhu", role="SYSTEM A · UNTOUCHED BASE · CLOSED BOOK",
         h1="Gemma 2 2B · Base",
         lead="Google's instruction-tuned Gemma 2 2B, exactly as shipped — no fine-tuning, no retrieval. It answers "
              "Yu-Gi-Oh from whatever it absorbed in pretraining: fluent, confident prose that fabricates modern card "
              "facts. This is the control the whole experiment measures against.",
         stats=[("3.98", "Judge /10"), ("1.83", "Correctness /5"), ("0.18", "Groundedness /2"),
                ("0.97", "Completeness /2"), ("2.6B", "Parameters"), ("4-bit", "NF4 quantized")],
         blurb=["The floor. Gemma 2 2B closed-book with no adaptation — articulate but un-grounded: a groundedness of "
                "0.18/2 means it almost never stays faithful to real card text.",
                "Its gap to Systems B and C is exactly the value fine-tuning and retrieval add. On the 60 held-out "
                "questions it scores 3.98 ± 0.39 / 10."],
         training=None,
         train_note="System A is the untouched base — no training of ours. Loaded 4-bit (NF4) at inference; the corpus "
                    "below is what Systems B and C are built from, shown here for context.",
         corpus_note="Not trained on our corpus — this is the imported base. The Yu-Gi-Oh corpus that Systems B and C "
                     "use is shown below so the three pages are comparable.", pass_=False),
    dict(slug="finetune", letter="B", brand="Fine-tuned by Harman Sandhu", role="SYSTEM B · QLoRA FINE-TUNE · CLOSED BOOK",
         h1="Gemma 2 2B · Yu-Gi-Oh QA",
         lead="Our QLoRA adapter over Gemma 2 2B, trained on 2,683 grounded Yu-Gi-Oh QA pairs — still closed-book. "
              "Fine-tuning teaches the answer shape: it answers like a rulings expert, but still cannot recall facts it "
              "was never given in its weights.",
         stats=[("5.25", "Judge /10"), ("2.35", "Correctness /5"), ("0.87", "Groundedness /2"),
                ("2,683", "QA pairs"), ("3.87", "Val perplexity"), ("r=16", "LoRA rank")],
         blurb=["Significantly beats the base (+1.27, p = 0.007). The gain is concentrated in groundedness — 0.18 → 0.87 — "
                "the model learns the register of a Yu-Gi-Oh ruling. That is the answer <em>shape</em>.",
                "But correctness barely moves (1.83 → 2.35): the specific card facts are not in the adapter's 20.8M "
                "trained parameters. That is what System C fixes."],
         training=TRAIN_B, train_note=None,
         corpus_note="The 2,683-pair supervised set was distilled by a teacher LLM (Gemini flash-lite) from this corpus, "
                     "then filtered through a blind-judge gauntlet before training.", pass_=False),
    dict(slug="rag", letter="C", brand="Fine-tuned by Harman Sandhu", role="SYSTEM C · FINE-TUNE + RETRIEVAL · RAG",
         h1="Gemma 2 2B · Yu-Gi-Oh RAG",
         lead="The same fine-tune, now with a hybrid retriever (MiniLM + BM25, top-5 over 42,412 chunks) feeding it the "
              "actual passages before it answers. This is where the facts arrive — correctness jumps and it becomes the "
              "decisive winner of the experiment.",
         stats=[("8.05", "Judge /10"), ("3.85", "Correctness /5"), ("1.65", "Groundedness /2"),
                ("0.93", "Recall@5"), ("42,412", "Chunks"), ("top-5", "Retrieved")],
         blurb=["The winner (+2.80 over the closed fine-tune, p &lt; 0.001). Retrieval supplies the facts the weights "
                "never held: correctness climbs 2.35 → 3.85 and groundedness 0.87 → 1.65 — but only once real passages "
                "are in the prompt.",
                "The thesis in one screen: <strong>fine-tuning taught the shape, retrieval supplied the facts.</strong> "
                "Every answer below shows the passages the retriever fed in."],
         training=TRAIN_C, train_note=None,
         corpus_note="Same 2,683-pair fine-tune as System B. At inference the retriever searches this full corpus and "
                     "feeds the top-5 passages into the prompt — that is where the facts come from.", pass_=True),
]

GLOBALS = """
:root,[data-theme="parchment"]{--bg:#e7e1d2;--bg-soft:#f4f0e7;--panel:#fdfbf6;--panel-2:#f6f2e9;--border:#d5cbb5;--border-soft:#e1d9c6;--fg:#211f1a;--fg-muted:#6b675c;--fg-dim:#8f887a;--accent:#b45309;--accent-2:#0f766e;--accent-3:#6d28d9;--grid:rgba(0,0,0,0.035);--glow-1:rgba(180,83,9,0.05);--glow-2:rgba(15,118,110,0.05);}
[data-theme="parchment"] .panel{box-shadow:0 1px 2px rgba(70,60,40,0.05),0 6px 16px rgba(70,60,40,0.06);}
[data-theme="amber"]{--bg:#07090d;--bg-soft:#0c0f16;--panel:#0f131c;--panel-2:#121826;--border:#1c2333;--border-soft:#161c28;--fg:#e7ecf4;--fg-muted:#8b95a7;--fg-dim:#5b6478;--accent:#f5b342;--accent-2:#38d9c4;--accent-3:#a78bfa;--grid:rgba(255,255,255,0.025);--glow-1:rgba(245,179,66,0.05);--glow-2:rgba(56,217,196,0.045);}
[data-theme="cobalt"]{--bg:#06080f;--bg-soft:#0a0e1a;--panel:#0e1424;--panel-2:#121a2e;--border:#1e2740;--border-soft:#172038;--fg:#e8edf6;--fg-muted:#8893ab;--fg-dim:#5a6480;--accent:#5b93ff;--accent-2:#22d3ee;--accent-3:#9d7bff;--grid:rgba(255,255,255,0.025);--glow-1:rgba(91,147,255,0.06);--glow-2:rgba(34,211,238,0.05);}
[data-theme="phosphor"]{--bg:#060a07;--bg-soft:#0a1109;--panel:#0d150f;--panel-2:#111c14;--border:#1b2a1f;--border-soft:#15211a;--fg:#dcf5e3;--fg-muted:#7fa48a;--fg-dim:#55705d;--accent:#4ade80;--accent-2:#eab308;--accent-3:#22d3ee;--grid:rgba(120,255,170,0.03);--glow-1:rgba(74,222,128,0.05);--glow-2:rgba(34,211,238,0.045);}
[data-theme="ember"]{--bg:#0c0708;--bg-soft:#120b0a;--panel:#17100e;--panel-2:#1e1512;--border:#2c1c1a;--border-soft:#241614;--fg:#f6e9e6;--fg-muted:#b0958f;--fg-dim:#7a625c;--accent:#fb7185;--accent-2:#fb923c;--accent-3:#fbbf24;--grid:rgba(255,200,190,0.025);--glow-1:rgba(251,113,133,0.05);--glow-2:rgba(251,146,60,0.045);}
[data-theme="nord"]{--bg:#232a37;--bg-soft:#2a3140;--panel:#2b3242;--panel-2:#323a4c;--border:#3a4356;--border-soft:#333b4c;--fg:#e5e9f0;--fg-muted:#9aa4b8;--fg-dim:#6b7488;--accent:#88c0d0;--accent-2:#a3be8c;--accent-3:#b48ead;--grid:rgba(255,255,255,0.02);--glow-1:rgba(136,192,208,0.07);--glow-2:rgba(163,190,140,0.05);}
*{box-sizing:border-box;border-color:var(--border);}
html{scroll-behavior:smooth;}
body{margin:0;background:var(--bg);color:var(--fg);font-family:Inter,system-ui,Arial,sans-serif;-webkit-font-smoothing:antialiased;transition:background-color .35s ease,color .35s ease;}
body::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;background-image:radial-gradient(60rem 40rem at 80% -10%,var(--glow-1),transparent 60%),radial-gradient(50rem 40rem at 0% 10%,var(--glow-2),transparent 55%),linear-gradient(var(--grid) 1px,transparent 1px),linear-gradient(90deg,var(--grid) 1px,transparent 1px);background-size:100% 100%,100% 100%,44px 44px,44px 44px;}
.mono{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-feature-settings:"tnum" 1;}
.panel{background:linear-gradient(180deg,var(--panel),var(--bg-soft));border:1px solid var(--border);border-radius:14px;}
.panel-inset{background:var(--bg);border:1px solid var(--border-soft);border-radius:10px;}
.tag{font-family:ui-monospace,monospace;font-size:.68rem;letter-spacing:.14em;text-transform:uppercase;color:var(--fg-muted);}
.hairline{height:1px;background:linear-gradient(90deg,transparent,var(--border),transparent);}
.panel,.panel-inset,.tag,input,textarea,select,button{transition:background-color .35s ease,border-color .35s ease,color .35s ease;}
.btn-primary{background:var(--accent);color:#14100a;border:0;border-radius:8px;padding:9px 16px;font-weight:600;cursor:pointer;}
.btn-primary:hover{filter:brightness(1.08);}.btn-primary:disabled{opacity:.55;cursor:not-allowed;}
.btn{background:transparent;color:var(--fg);border:1px solid var(--border);border-radius:8px;padding:8px 14px;cursor:pointer;text-decoration:none;}
.btn:hover{background:var(--panel-2);}
.field{background:var(--bg);color:var(--fg);border:1px solid var(--border);border-radius:8px;padding:10px 12px;outline:none;width:100%;font:inherit;}
.field:focus{border-color:color-mix(in srgb,var(--accent) 60%,var(--border));}
table{width:100%;border-collapse:collapse;}
th{text-align:left;color:var(--fg-muted);font-size:11px;text-transform:uppercase;letter-spacing:.06em;font-weight:500;padding:9px 10px;}
td{padding:9px 10px;border-top:1px solid var(--border-soft);}td.num{text-align:right;font-family:ui-monospace,monospace;}
.badge{font-size:11px;font-family:ui-monospace,monospace;padding:2px 8px;border-radius:6px;background:var(--panel-2);color:var(--fg-muted);border:1px solid var(--border);}
.badge-accent{background:color-mix(in srgb,var(--accent) 16%,transparent);color:var(--accent);border:0;}
.grad-divider{height:6px;width:220px;margin:0 auto;border-radius:999px;background:linear-gradient(90deg,#22c55e 0%,#3b82f6 38%,#8b5cf6 68%,#ef4444 100%);}
.wrap{max-width:900px;margin:0 auto;padding:0 20px;}
.nav{display:flex;align-items:center;justify-content:space-between;padding:18px 0;gap:12px;flex-wrap:wrap;}
.navright{display:flex;align-items:center;gap:11px;}
.pill{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;color:var(--fg);text-decoration:none;border:1px solid var(--border);padding:6px 12px;border-radius:999px;background:var(--panel-2);}
.pill:hover{border-color:var(--accent);}.pill svg{width:14px;height:14px;fill:currentColor;}
.picker{display:inline-flex;gap:6px;align-items:center;border:1px solid var(--border);background:var(--panel);border-radius:999px;padding:6px 8px;}
.swatch{display:grid;place-items:center;border-radius:50%;border:0;background:transparent;width:20px;height:20px;cursor:pointer;padding:0;}
.swatch span{width:14px;height:14px;border-radius:50%;box-shadow:0 0 0 1px rgba(0,0,0,.25);}
.swatch[aria-checked="true"] span{box-shadow:0 0 0 2px var(--bg),0 0 0 3.5px var(--fg);}
.hero{padding:34px 0 8px;}
.brand{display:flex;width:fit-content;align-items:center;gap:8px;font-family:ui-monospace,monospace;font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:var(--fg);border:1px solid color-mix(in srgb,var(--accent) 45%,var(--border));background:color-mix(in srgb,var(--accent) 10%,var(--panel-2));padding:7px 15px;border-radius:999px;margin-bottom:18px;}
.brand::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--accent);flex:none;}
.hero h1{font-size:clamp(1.9rem,5vw,2.9rem);margin:10px 0 12px;letter-spacing:-.02em;font-weight:650;}
.hero p.lead{color:var(--fg-muted);font-size:1.02rem;max-width:64ch;line-height:1.55;margin:0;}
.hero p.lead em{color:var(--fg);font-style:normal;font-weight:600;}
.herobtns{display:flex;gap:10px;margin-top:18px;flex-wrap:wrap;}
.lineage{display:flex;flex-wrap:wrap;gap:8px;align-items:stretch;margin-top:24px;}
.lineage a,.lineage span{display:block;text-decoration:none;color:var(--fg);flex:1 1 130px;padding:12px 14px;border-radius:10px;border:1px solid var(--border);background:var(--panel-2);}
.lineage a:hover{border-color:color-mix(in srgb,var(--accent) 50%,var(--border));}
.lineage .st{font-weight:600;font-size:.95rem;}.lineage .mv{font-family:ui-monospace,monospace;font-size:.8rem;color:var(--fg-muted);margin-top:4px;}
.lineage .cur{border-color:var(--accent);}
.statgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px;margin:24px 0;}
.stat{padding:16px;text-align:center;}.stat .value{font-family:ui-monospace,monospace;font-size:22px;font-weight:600;color:var(--fg);}.stat .label{margin-top:6px;}
.section{margin:26px 0;}.section .card{padding:22px 24px;}
.section h2{font-size:1.2rem;margin:6px 0 10px;font-weight:600;}.section h3{font-size:1.02rem;font-weight:600;margin:6px 0 8px;}
.section p{color:var(--fg-muted);line-height:1.6;}
.section p strong,.section p em{color:var(--fg);}
[data-theme="parchment"] .whatis p{color:#000;}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px;}
.splitbar{display:flex;height:24px;border-radius:8px;overflow:hidden;border:1px solid var(--border);margin:10px 0 10px;}
.splitbar span{display:block;height:100%;}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12.5px;color:var(--fg-muted);margin-bottom:12px;}
.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:middle;}
.pass{margin-top:12px;font-size:12px;color:var(--fg-muted);}
.pass .p{padding:7px 9px;border-radius:8px;background:var(--bg);border:1px solid var(--border-soft);margin-bottom:6px;}
.pass .pt{color:var(--accent-2);font-family:ui-monospace,monospace;font-size:11px;}
footer{margin:44px 0 40px;text-align:center;color:var(--fg-dim);}
footer .badge-line{color:var(--fg-muted);letter-spacing:.12em;text-transform:uppercase;font-family:ui-monospace,monospace;font-size:.72rem;margin-top:16px;}
footer .src{color:var(--fg-dim);font-size:.82rem;margin-top:8px;}footer a{color:var(--fg-muted);}
@media(max-width:720px){.grid2{grid-template-columns:1fr;}}
"""

GH_SVG = ('<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 '
          '7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-'
          '.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-'
          '3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 '
          '.27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25'
          '.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>')

TEMPLATE = """<!doctype html>
<html lang="en" data-theme="parchment">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%%H1%% · Yu-Gi-Oh SLM · Harman Sandhu</title>
<meta name="description" content="%%LEAD%%">
<script>(function(){try{var t=localStorage.getItem('slm-theme');if(t)document.documentElement.setAttribute('data-theme',t);}catch(e){}})();</script>
<style>%%GLOBALS%%</style>
</head>
<body>
<div class="wrap">
  <nav class="nav">
    <span class="tag">SLM Engineering</span>
    <div class="navright">
      <a class="pill" href="%%COMBINED%%" target="_blank" rel="noreferrer">← Arena</a>
      <a class="pill" href="%%GITHUB%%" target="_blank" rel="noreferrer">%%GH%%GitHub</a>
      <div class="picker" id="picker" role="radiogroup" aria-label="Color theme"></div>
    </div>
  </nav>

  <header class="hero">
    <div class="brand">%%BRAND%%</div>
    <span class="tag" style="color:var(--accent)">%%ROLE%%</span>
    <h1>%%H1%%</h1>
    <p class="lead">%%LEAD%%</p>
  </header>

  <div class="lineage">%%LINEAGE%%</div>
  <div class="statgrid">%%STATS%%</div>

  <section class="section"><div class="panel card">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
      <span class="tag">interactive</span><span class="badge" id="badge">connecting…</span></div>
    <h3 style="margin:0 0 12px;font-size:1.05rem">Ask this system a question</h3>
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px" id="chips"></div>
    <textarea class="field" id="q" rows="3" style="resize:vertical" placeholder="Ask a Yu-Gi-Oh rules / card question…">%%EX0%%</textarea>
    <div style="display:flex;align-items:center;gap:12px;margin-top:12px">
      <button class="btn-primary" id="go" disabled>Ask</button>
      <span id="hint" style="color:var(--fg-dim);font-size:.85rem">Connecting to the inference endpoint…</span></div>
    <div class="panel-inset" id="answer" style="margin-top:14px;padding:14px 16px;min-height:64px;color:var(--fg-dim);white-space:pre-wrap;line-height:1.55">The model's answer will appear here.</div>
    %%PASSBLOCK%%
  </div></section>

  <section class="section"><div class="panel card whatis">
    <span class="tag">what this is</span>%%BLURB%%
  </div></section>

  <section class="section"><div class="grid2">
    <div class="panel card"><span class="tag">Architecture</span>%%ARCH%%</div>
    <div class="panel card"><span class="tag">Training</span>%%TRAINING%%</div>
  </div></section>

  <section class="section"><div class="panel card">
    <span class="tag">Corpus used for training</span>
    <h2 style="margin-top:6px">What the fine-tune was built from</h2>
    <p style="margin:6px 0 6px">The fine-tune's supervised set is <strong>2,683 grounded QA pairs</strong>, distilled by a
      teacher LLM from a curated Yu-Gi-Oh corpus and filtered through a blind-judge gauntlet. That corpus is two free
      sources: <strong>Yugipedia</strong> editorial prose (CC BY-SA 4.0, attributed) and <strong>YGOPRODeck</strong> card
      facts. Card effect text is © Konami, used only as labelled fair-use context — never a verbatim-recall target.</p>
    <h3>Corpus split · 27.5 MB across sources</h3>
    <div class="splitbar" id="splitbar"></div>
    <div class="legend" id="legend"></div>
    %%CORPUS%%
    <p style="font-size:.85rem;color:var(--fg-dim);margin-top:14px;line-height:1.6"><strong>78% free-licensed Yugipedia prose</strong>
      (20.7 MB cleaned, clears the 20 MB floor) + <strong>22% card facts</strong>. Of the prose, ~82% is on-target
      rulings/interactions and ~18% is lore. Card knowledge is a YGOPRODeck snapshot fetched <strong>2026-08-01</strong>.</p>
  </div></section>

  <footer>
    <div class="grad-divider"></div>
    <div class="badge-line">Built &amp; evaluated by Harman Sandhu</div>
    <div class="src">Live against the same endpoint as the <a href="%%COMBINED%%" target="_blank" rel="noreferrer">arena</a> ·
      <a href="%%HF%%" target="_blank" rel="noreferrer">HuggingFace</a> · <a href="%%GITHUB%%" target="_blank" rel="noreferrer">GitHub</a></div>
  </footer>
</div>

<script>
  const BASE="%%BASE%%", ENDPOINT=BASE+"/ask", FIELD="%%LETTER%%", SHOW_PASS=%%SHOWPASS%%, EXAMPLES=%%EXAMPLES%%;
  const THEMES=[["parchment","Parchment",["#b45309","#0f766e","#6d28d9"]],["amber","Amber",["#f5b342","#38d9c4","#a78bfa"]],
    ["cobalt","Cobalt",["#5b93ff","#22d3ee","#9d7bff"]],["phosphor","Phosphor",["#4ade80","#eab308","#22d3ee"]],
    ["ember","Ember",["#fb7185","#fb923c","#fbbf24"]],["nord","Nord",["#88c0d0","#a3be8c","#b48ead"]]];
  const SPLIT=[["tips",31,"--accent"],["rulings",22,"--accent-2"],["card facts",22,"--accent-3"],
    ["archetype",10,"#c98a2b"],["lore",14,"#8a8f98"],["mechanics",1,"#c05a3a"]];
  const root=document.documentElement, picker=document.getElementById('picker');
  function setTheme(t){ root.setAttribute('data-theme',t); try{localStorage.setItem('slm-theme',t);}catch(e){}
    [...picker.children].forEach(b=>b.setAttribute('aria-checked', b.dataset.t===t)); }
  THEMES.forEach(([id,name,acc])=>{ const b=document.createElement('button'); b.className='swatch'; b.dataset.t=id;
    b.setAttribute('role','radio'); b.title=name; b.setAttribute('aria-label',name);
    b.innerHTML=`<span style="background:conic-gradient(${acc[0]} 0 33.3%,${acc[1]} 0 66.6%,${acc[2]} 0)"></span>`;
    b.onclick=()=>setTheme(id); picker.appendChild(b); });
  setTheme(localStorage.getItem('slm-theme')||'parchment');

  const sb=document.getElementById('splitbar'), lg=document.getElementById('legend');
  SPLIT.forEach(([lab,pct,c])=>{ const col=c.startsWith('--')?`var(${c})`:c;
    sb.insertAdjacentHTML('beforeend',`<span style="width:${pct}%;background:${col}" title="${lab} · ${pct}%"></span>`);
    if(lg) lg.insertAdjacentHTML('beforeend',`<span><i style="background:${col}"></i>${lab} ${pct}%</span>`); });

  const chips=document.getElementById('chips'), qEl=document.getElementById('q'), go=document.getElementById('go'),
        ans=document.getElementById('answer'), badge=document.getElementById('badge'), hint=document.getElementById('hint');
  EXAMPLES.forEach(x=>{ const c=document.createElement('button'); c.className='btn'; c.style.fontSize='.82rem'; c.style.padding='6px 10px';
    c.style.textAlign='left'; c.textContent=x.length>60?x.slice(0,58)+'…':x; c.title=x; c.onclick=()=>{ qEl.value=x; if(!go.disabled) ask(); }; chips.appendChild(c); });
  let ONLINE=false;
  function setStatus(s){ ONLINE=(s==='ok'); go.disabled=!ONLINE;
    badge.className=s==='ok'?'badge badge-accent':'badge'; badge.textContent=s==='ok'?'live':s==='down'?'demo unavailable':'connecting…';
    hint.textContent=s==='ok'?'The first request loads the model, so it can take a few seconds.':s==='down'?'The inference endpoint is unavailable right now. The evaluation results below are unaffected.':'Connecting to the inference endpoint…';
    if(s==='down'){ ans.style.color='var(--fg-dim)'; ans.textContent='Demo unavailable — the local model server / tunnel is not reachable right now.'; } }
  async function probe(){ try{ const r=await fetch(BASE+'/health',{cache:'no-store',signal:AbortSignal.timeout(8000)}); setStatus(r.ok?'ok':'down'); }catch(e){ setStatus('down'); } }
  async function ask(){ const q=qEl.value.trim(); if(!q||!ONLINE) return; go.disabled=true;
    ans.style.color='var(--fg-dim)'; ans.textContent='…thinking'; const pc=document.getElementById('passC'); if(pc) pc.innerHTML='';
    try{ const r=await fetch(ENDPOINT,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q,k:5}),signal:AbortSignal.timeout(120000)});
      if(!r.ok) throw new Error('HTTP '+r.status); const d=await r.json();
      ans.style.color='var(--fg)'; ans.textContent=d[FIELD]||'(no field '+FIELD+')';
      if(SHOW_PASS&&pc&&d.passages&&d.passages.length){ pc.innerHTML='<details open><summary style="cursor:pointer;color:var(--fg-muted);font-size:12px">▸ '+d.passages.length+' retrieved passages</summary></details>';
        const det=pc.querySelector('details'); d.passages.forEach(p=>{ const el=document.createElement('div'); el.className='p';
          el.innerHTML='<span class="pt">'+p.title+'</span><br>'+p.text.slice(0,220).replace(/</g,'&lt;')+'…'; det.appendChild(el); }); }
    }catch(err){ setStatus('down'); } finally{ if(ONLINE) go.disabled=false; } }
  go.onclick=ask; qEl.addEventListener('keydown',e=>{ if(e.key==='Enter'&&(e.metaKey||e.ctrlKey)) ask(); });
  probe();
</script>
</body>
</html>
"""

def rows_table(rows):
    return '<table><tbody>' + "".join(f'<tr><td style="color:var(--fg-muted)">{k}</td><td class="num">{v}</td></tr>' for k, v in rows) + '</tbody></table>'

def corpus_table():
    body = "".join(f'<tr><td>{s}</td><td style="color:var(--fg-muted)">{r}</td><td style="color:var(--fg-muted)">{l}</td>'
                   f'<td class="num">{sz}</td><td class="num">{sh}</td></tr>' for s, r, l, sz, sh in CORPUS)
    return ('<table style="min-width:560px"><thead><tr><th>Source</th><th>Role</th><th>License</th>'
            '<th style="text-align:right">Size</th><th style="text-align:right">Share</th>'
            '</tr></thead><tbody>' + body + '</tbody></table>')

def cost_table():
    rows = ""
    for st, det, c in COST:
        w = ' style="font-weight:700"' if st == "Total" else ""
        rows += f'<tr><td{w}>{st}</td><td style="color:var(--fg-muted)">{det}</td><td class="num"{w}>{c}</td></tr>'
    return '<table><thead><tr><th>Stage</th><th>Detail</th><th style="text-align:right">Cost</th></tr></thead><tbody>' + rows + '</tbody></table>'

def lineage_html(cur):
    order = [("base", "A · Base", "Google weights"), ("finetune", "B · Fine-tune", "QLoRA · closed"), ("rag", "C · +Retrieval", "RAG · winner")]
    out = []
    for slug, st, mv in order:
        if slug == cur:
            out.append(f'<span class="cur"><div class="st">{st}</div><div class="mv">{mv}</div></span>')
        else:
            out.append(f'<a href="https://{DOMAINS[slug]}.vercel.app" target="_blank" rel="noreferrer"><div class="st">{st}</div><div class="mv">{mv}</div></a>')
    return "".join(out)

def build():
    for s in SYSTEMS:
        training = rows_table(s["training"]) if s["training"] else f'<p style="margin-top:10px;color:var(--fg-muted)">{s["train_note"]}</p>'
        stats = "".join(f'<div class="panel stat"><div class="value">{v}</div><div class="tag label">{l}</div></div>' for v, l in s["stats"])
        blurb = "".join(f'<p style="margin-top:10px">{p}</p>' for p in s["blurb"])
        passblock = '<div class="pass" id="passC"></div>' if s["pass_"] else ""
        repl = {"%%GLOBALS%%": GLOBALS, "%%H1%%": s["h1"], "%%LEAD%%": s["lead"], "%%BRAND%%": s["brand"], "%%ROLE%%": s["role"],
                "%%COMBINED%%": COMBINED_URL, "%%GITHUB%%": GITHUB, "%%GH%%": GH_SVG,
                "%%HF%%": HF_MAP[s["slug"]][0], "%%HFLABEL%%": HF_MAP[s["slug"]][1],
                "%%LINEAGE%%": lineage_html(s["slug"]), "%%STATS%%": stats, "%%EX0%%": EXAMPLES[0], "%%PASSBLOCK%%": passblock,
                "%%BLURB%%": blurb, "%%ARCH%%": rows_table(ARCH), "%%TRAINING%%": training, "%%CORPUS_NOTE%%": s["corpus_note"],
                "%%CORPUS%%": corpus_table(), "%%BASE%%": BASE, "%%LETTER%%": s["letter"],
                "%%SHOWPASS%%": ("true" if s["pass_"] else "false"), "%%EXAMPLES%%": json.dumps(EXAMPLES)}
        html = TEMPLATE
        for k, v in repl.items():
            html = html.replace(k, v)
        d = HERE / s["slug"]; d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(html, encoding="utf-8")
        print(f"wrote {s['slug']}/index.html  ({DOMAINS[s['slug']]}.vercel.app)")
    site = REPO / "site" / "index.html"
    t = site.read_text(encoding="utf-8")
    t2 = re.sub(r'const BASE = "[^"]*";', f'const BASE = "{BASE}";', t, count=1)
    if t != t2:
        site.write_text(t2, encoding="utf-8"); print("synced site/index.html BASE endpoint")

def deploy():
    build()
    for s in SYSTEMS:
        d = HERE / s["slug"]; dom = DOMAINS[s["slug"]]
        print(f"\n=== deploying {dom} ===")
        out = subprocess.run("vercel deploy --prod --yes", cwd=d, shell=True, capture_output=True, text=True)
        url = ""
        for line in (out.stdout + out.stderr).splitlines():
            m = re.search(r"https://[a-z0-9-]+\.vercel\.app", line)
            if m:
                url = m.group(0)
        print("deployed:", url or "(url not parsed)")
        if url:
            subprocess.run(f"vercel alias set {url} {dom}.vercel.app", shell=True)

if __name__ == "__main__":
    (deploy if len(sys.argv) > 1 and sys.argv[1] == "deploy" else build)()

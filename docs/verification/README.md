# Verification scripts

Reproducible artifacts backing the **VERIFIED** section of
[`../assignment-verification.md`](../assignment-verification.md). Run 2026-08-01.

| Script | What it verifies |
|--------|------------------|
| `verify_sources.py` | Data-source volume & license claims — Yugipedia category sizes, raw wikitext byte samples, and the YGOPRODeck v7 payload/effect-text size. Hits live APIs and counts. |
| `probe_gemma_base.py` | Whether Gemma 2 2B **base** knows Yu-Gi-Oh (closed-book = System A). 12 questions spanning general → classic stats → modern cards → rulings. Scored ~1.5/12 → domain-ignorance confirmed. |

## Run

```bash
# data-source verification (no key needed)
.venv/Scripts/python.exe docs/verification/verify_sources.py

# base-model probe (needs a running gemma-2-2b-it base endpoint; edit URL/MODEL as needed)
.venv/Scripts/python.exe docs/verification/probe_gemma_base.py
```

Key findings are summarized in the parent doc; these scripts let anyone re-derive them.

# Cost log

Budget target: **≤ $25** total (GPU + API). Every experiment logs here as it happens —
cost per experiment is engineering information, not an afterthought.

| Date | Phase | What | GPU-hours | API calls | $ | Notes |
|------|-------|------|-----------|-----------|---|-------|
| 2026-08-01 | 2 | Teacher QA gen — **pilot** (120 chunks) | — | ~135 | <$0.20 (est.) | Gemini flash-lite; 276 pairs + 15 held-out |
| 2026-08-01 | 2 | Teacher QA generation — full run (1,200 chunks) | — | ~1,260 | <$0.50 (est.) | 2,796 raw pairs + 60 held-out |
| 2026-08-01 | 2 | QA quality gating (judge, 2,796 pairs) | — | ~2,796 | <$0.50 (est.) | 2,683 survived → train.jsonl |
| | 3 | QLoRA training run(s) | | — | | |
| | 3 | Model serving (scale-to-zero) | | — | | |
| | 5 | Eval judging (A/B/C) | — | | | |
| | | **Running total** | | | | |

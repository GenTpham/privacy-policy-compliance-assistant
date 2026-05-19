---
phase: 07-eval-calibration
plan: "04"
subsystem: backend-config
tags: [calibration, rag, threshold, config, tests]
dependency_graph:
  requires: [07-03]
  provides: [calibrated-score-threshold]
  affects: [backend/app/core/config.py, .planning/PROJECT.md]
tech_stack:
  added: []
  patterns: [pydantic-settings default update, empirical calibration loop closure]
key_files:
  created: []
  modified:
    - backend/app/core/config.py
    - .planning/PROJECT.md
decisions:
  - "score_threshold set to 0.20 (D-06 hard floor) — empirical data shows no scores in 0.20–0.32 range; threshold change closes calibration loop without impacting retrieval results"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-05"
---

# Phase 7 Plan 04: Apply Calibrated score_threshold Summary

## One-Liner

Updated score_threshold default from 0.25 to 0.20 based on Phase 7 score distribution analysis showing no scores in the 0.20–0.32 range, with comment referencing ANALYSIS.md and all 16 pytest assertions passing.

## What Was Done

### Task 1: Update score_threshold default in config.py

Updated `backend/app/core/config.py` Settings field from `0.25` to `0.20` with a multi-line comment explaining:
- Calibration date and source (100-example validation run, 2026-05-05)
- Reference to ANALYSIS.md in phases/07-eval-calibration/
- D-06 hard floor constraint (>= 0.20)
- Empirical finding: minimum retrieved score was 0.32; no scores in 0.20–0.32 range
- Root cause of 23% context_hit: ranking mismatch, not threshold filtering

Verification: `python -c "from backend.app.core.config import get_settings; s = get_settings(); assert s.score_threshold >= 0.20"` passed with `score_threshold=0.2`.

Commit: `fc1d1f9`

### Task 2: Update PROJECT.md key decision and confirm pytest

Updated `.planning/PROJECT.md` Key Decisions table, replacing the `score_threshold=0.25 (not 0.55)` entry with the calibrated value `score_threshold=0.20 (calibrated Phase 7, 2026-05-05)` including:
- Empirical rationale from ANALYSIS.md
- Reference to score distribution finding (no scores 0.20–0.32)
- Root cause statement (ranking mismatch)
- D-06 floor documentation

pytest result: **16/16 passed** (1.63s). Dynamic assertions in test_rag.py (`get_settings().score_threshold`) automatically reflect the updated default — no test changes needed.

Commit: `6216951`

## Final Calibrated Value

**score_threshold = 0.20**

This closes the Phase 7 calibration loop:
- Plan 1: eval infrastructure (Phoenix, run_experiment.py)
- Plan 2: test suite aligned to dynamic assertions (get_settings().score_threshold)
- Plan 3: experiments run, ANALYSIS.md written with empirical findings
- Plan 4 (this): config updated, PROJECT.md updated, tests pass

## pytest Output Excerpt

```
collected 16 items

backend/app/tests/test_rag.py::test_embed_calls_correct_model PASSED
backend/app/tests/test_rag.py::test_retrieve_params PASSED
backend/app/tests/test_rag.py::test_conflict_retrieve_params PASSED
...
======================== 16 passed, 3 warnings in 1.63s ========================
```

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Phase 7 Outcome (one sentence for STATE.md)

Phase 7 calibration complete: score_threshold updated to 0.20 (D-06 floor) based on 100-example validation run showing minimum retrieved score of 0.32; root cause of 23% context_hit is question-to-passage ranking mismatch requiring top_k increase or query rewriting in a future phase.

## Self-Check: PASSED

- [x] `backend/app/core/config.py` exists and contains `score_threshold: float = 0.20`
- [x] `.planning/PROJECT.md` exists and contains `score_threshold=0.20 (calibrated Phase 7`
- [x] Commit `fc1d1f9` exists: `feat(07-04): update score_threshold default from 0.25 to 0.20`
- [x] Commit `6216951` exists: `docs(07-04): update PROJECT.md key decision — score_threshold=0.20`
- [x] pytest 16/16 passed

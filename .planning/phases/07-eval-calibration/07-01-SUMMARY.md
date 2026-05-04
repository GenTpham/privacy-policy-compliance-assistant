---
phase: 07-eval-calibration
plan: "01"
subsystem: backend-config
tags: [config, rag, score-threshold, pydantic-settings]
dependency_graph:
  requires: []
  provides: [score_threshold-in-settings, dynamic-threshold-reads-in-rag]
  affects: [backend/app/core/config.py, backend/app/services/rag.py]
tech_stack:
  added: []
  patterns: [pydantic-settings env override, call-time settings read]
key_files:
  created: []
  modified:
    - backend/app/core/config.py
    - backend/app/services/rag.py
decisions:
  - score_threshold reads get_settings() at call time (not module load) to pick up SCORE_THRESHOLD env var override
metrics:
  duration: "6 minutes"
  completed: "2026-05-04T10:08:23Z"
  tasks_completed: 2
  files_modified: 2
---

# Phase 7 Plan 01: Score Threshold Config Externalization Summary

**One-liner:** Moved score_threshold from two hardcoded 0.25 literals in rag.py into Settings as a pydantic-settings field overridable via SCORE_THRESHOLD env var.

## What Was Changed

### Task 1: config.py — score_threshold field added

Added `score_threshold: float = 0.25` to the `Settings` class in `backend/app/core/config.py`, after the `phoenix_collector_endpoint` field and before `model_config`. The field includes a comment explaining the env var override and Phase 7 calibration intent:

```python
# RAG retrieval threshold — overridable via SCORE_THRESHOLD env var.
# Default 0.25: Nemotron cosine scores for relevant matches range 0.25–0.45.
# Calibrated empirically in Phase 7; update default after running run_experiment.py.
score_threshold: float = 0.25
```

pydantic-settings auto-uppercases the field name, so `SCORE_THRESHOLD` in `.env` or the Docker environment will override this value at startup.

### Task 2: rag.py — two hardcoded literals replaced

Both `query_points` calls now read `_threshold = get_settings().score_threshold` at call time rather than using the literal `0.25`. This ensures any `SCORE_THRESHOLD` env var override is picked up dynamically per-call rather than frozen at module load.

**stream_answer** (line 170):
- Before: `with _retrieval_span(message, limit=5, threshold=0.25) as span:` + `score_threshold=0.25,`
- After: `_threshold = get_settings().score_threshold` + `threshold=_threshold` + `score_threshold=_threshold,`

**stream_conflict_answer** (line 313):
- Before: `with _retrieval_span(message, limit=10, threshold=0.25) as span:` + `score_threshold=0.25,`
- After: `_threshold = get_settings().score_threshold` + `threshold=_threshold` + `score_threshold=_threshold,`

## Grep Evidence

No hardcoded literal remains:
```
$ grep "score_threshold=0.25" backend/app/services/rag.py
(no output — PASS)
```

Dynamic reads confirmed (2 occurrences):
```
$ grep -n "_threshold = get_settings().score_threshold" backend/app/services/rag.py
170:    _threshold = get_settings().score_threshold
313:    _threshold = get_settings().score_threshold
```

Settings field verified:
```
$ grep "score_threshold: float" backend/app/core/config.py
    score_threshold: float = 0.25
```

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 4818cb7 | feat(07-01): add score_threshold field to Settings in config.py |
| Task 2 | 7e14455 | feat(07-01): replace hardcoded score_threshold=0.25 literals in rag.py |

## Deviations from Plan

None — plan executed exactly as written.

The module-level `_settings = get_settings()` singleton in rag.py was intentionally NOT used for score_threshold, per the plan's explicit instruction. Both pipelines call `get_settings().score_threshold` fresh at query time, which allows SCORE_THRESHOLD env var overrides to take effect without restarting the process.

## Unexpected Findings

- Module import test (`import backend.app.services.rag`) requires `OPENROUTER_API_KEY` and `JWT_SECRET` env vars due to the module-level `_settings = get_settings()` call — this is pre-existing behavior, not caused by this plan. The rag.py AST parses cleanly as valid Python.

## Known Stubs

None — both changes wire real configuration values, no placeholder data.

## Self-Check

- [x] `score_threshold: float = 0.25` exists in config.py at line 48
- [x] `grep "score_threshold=0.25" backend/app/services/rag.py` returns zero lines
- [x] `grep -c "get_settings().score_threshold" backend/app/services/rag.py` returns 2
- [x] commit 4818cb7 exists in git log
- [x] commit 7e14455 exists in git log

## Self-Check: PASSED

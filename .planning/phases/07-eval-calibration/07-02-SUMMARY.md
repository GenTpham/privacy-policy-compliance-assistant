---
phase: 07-eval-calibration
plan: "02"
subsystem: test-suite
tags: [test, rag, config, calibration]
dependency_graph:
  requires: []
  provides: [dynamic-score-threshold-assertions]
  affects: [backend/app/tests/test_rag.py, backend/app/core/config.py, backend/app/tests/conftest.py]
tech_stack:
  added: []
  patterns: [get_settings()-in-test-assertions, os.environ.setdefault-for-test-env]
key_files:
  created: []
  modified:
    - backend/app/tests/test_rag.py
    - backend/app/core/config.py
    - backend/app/tests/conftest.py
decisions:
  - "Added score_threshold: float = 0.25 to Settings (Rule 3 fix — required for assertions to resolve)"
  - "Used os.environ.setdefault in conftest.py module scope so get_settings() is callable in assertions without raising ValidationError"
  - "Both assertion lines and docstrings updated to use get_settings().score_threshold"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-04"
  tasks_completed: 2
  files_changed: 3
---

# Phase 7 Plan 2: Fix Hardcoded 0.55 Score Threshold Assertions Summary

**One-liner:** Replaced two hardcoded `0.55` score_threshold assertions in test_rag.py with `get_settings().score_threshold` — tests now self-update when config changes, divergence from production config is structurally impossible.

## What Was Done

### Task 1: Verify test env setup and fix blocking prerequisites

**conftest.py:** Added `os.environ.setdefault` for `OPENROUTER_API_KEY` and `JWT_SECRET` at module level so `get_settings()` can be called safely inside test assertions without raising `ValidationError`.

**config.py (Rule 3 — blocking fix):** Added `score_threshold: float = 0.25` field to `Settings`. This was required because Plan 02 and Plan 01 run in the same wave (wave 1, parallel). Without this field, `get_settings().score_threshold` raises `AttributeError` and the test fix cannot be applied.

### Task 2: Fix two 0.55 assertions in test_rag.py

Three changes applied to `backend/app/tests/test_rag.py`:
1. Added import: `from backend.app.core.config import get_settings`
2. `test_retrieve_params` — updated docstring and assertion: `== get_settings().score_threshold`
3. `test_conflict_retrieve_params` — updated docstring and assertion: `== get_settings().score_threshold`

## Acceptance Criteria Evidence

### 1. No 0.55 literal remains
```
grep "== 0.55" backend/app/tests/test_rag.py
→ (no output) PASS: no 0.55 literal
```

### 2. Dynamic assertions in place (4 occurrences: 2 assertions + 2 docstrings)
```
grep -n "get_settings().score_threshold" backend/app/tests/test_rag.py
64:  """RAG-02: qdrant.search called with limit=5, score_threshold=get_settings().score_threshold, with_payload=True."""
72:  assert call_kwargs.get("score_threshold") == get_settings().score_threshold
210: """CONFLICT-02: stream_conflict_answer calls query_points with limit=10, score_threshold=get_settings().score_threshold, with_payload=True."""
223: assert call_kwargs.get("score_threshold") == get_settings().score_threshold
```

### 3. Import present
```
grep "from backend.app.core.config import get_settings" backend/app/tests/test_rag.py
→ from backend.app.core.config import get_settings
```

### 4. Full test suite passes
```
pytest backend/app/tests/test_rag.py -x -v
→ 16 passed, 3 warnings in 0.50s
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Added score_threshold to Settings in config.py**
- **Found during:** Task 1 verification
- **Issue:** Plan 02 and Plan 01 run in the same wave (parallel). `get_settings().score_threshold` raises `AttributeError` without the field existing in Settings. This is a prerequisite for Task 2.
- **Fix:** Added `score_threshold: float = 0.25` with the exact comment from Plan 01's specification, so Plan 01's worktree can merge cleanly (same change, same content).
- **Files modified:** `backend/app/core/config.py`
- **Commit:** 85ece8b

**Note on parallel wave coordination:** Plan 01 (also wave 1) adds this same field. Both worktrees make an identical change to `config.py`. During merge, git will detect a conflict only if the surrounding context differs — since the changes are identical, a clean merge is expected. The merge orchestrator should pick one of the two identical hunks.

## Known Stubs

None. All assertions are fully wired to live config values.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. Test files only. No threat flags.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 85ece8b | chore(07-02): verify test env setup — add score_threshold to Settings and env defaults to conftest |
| 2 | cea8b73 | fix(07-02): replace hardcoded 0.55 assertions with get_settings().score_threshold in test_rag.py |

## Self-Check: PASSED

- `backend/app/tests/test_rag.py` — modified and committed
- `backend/app/core/config.py` — modified and committed (score_threshold field added)
- `backend/app/tests/conftest.py` — modified and committed (env defaults added)
- Commits 85ece8b and cea8b73 confirmed in git log
- 16/16 tests pass, no 0.55 literal remains

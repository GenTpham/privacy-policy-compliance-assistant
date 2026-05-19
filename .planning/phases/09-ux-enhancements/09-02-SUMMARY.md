---
phase: 09-ux-enhancements
plan: "02"
subsystem: backend-tests
tags: [testing, rag, sources-endpoint, score-field, source-filter]
dependency_graph:
  requires: [09-01]
  provides: [test_sources_endpoint, test_rag_score, test_rag_source_filter, test_chat_source_filter]
  affects: [backend/app/tests]
tech_stack:
  added: []
  patterns: [pytest-asyncio, httpx-ASGITransport, patch.object-singleton-mocking, db_engine-fixture-auth-gate]
key_files:
  created: []
  modified:
    - backend/app/tests/test_sources_endpoint.py
    - backend/app/tests/test_rag.py
    - backend/app/tests/test_chat_endpoint.py
decisions:
  - "test_sources_requires_auth uses db_engine fixture to override get_db — required because real get_current_user calls get_db which needs init_db() in lifespan"
  - "Preserved prior wave tests in test_sources_endpoint.py — 3 required + 3 source_filter propagation extras all pass"
metrics:
  duration: "3m 2s"
  completed: "2026-05-06"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 9 Plan 02: UX Enhancement Test Suite Summary

Test coverage for the three UX requirements introduced by Plan 01: GET /api/sources endpoint, source_filter propagation through RAG pipeline, and score field in all citation paths.

## What Was Built

Added 5 new test functions to cover the Plan 01 backend contract:

**test_sources_endpoint.py** — 3 required tests (+ 3 source_filter propagation tests from prior wave):
- `test_sources_returns_list`: HTTP 200 with `{"sources": [...]}` when authenticated
- `test_sources_requires_auth`: HTTP 401 when no bearer token (uses db_engine fixture for get_db)
- `test_sources_returns_500_on_qdrant_error`: HTTP 500 with `"Failed to retrieve source list"` detail

**test_rag.py** — 4 new test functions appended:
- `test_score_in_citations`: `_build_verified_citations` includes `score` field rounded to 4 decimals
- `test_score_in_abstain_fallback`: abstain fallback citation dicts include `score` float
- `test_source_filter_applied`: `stream_answer(source_filter=...)` passes `query_filter != None` to query_points
- `test_no_filter_when_none`: `stream_answer(source_filter=None)` passes `query_filter=None` to query_points

**test_chat_endpoint.py** — 1 new test function:
- `test_source_filter_accepted`: POST /api/chat accepts `source_filter` field (HTTP 200)

## Test Counts

| File | Functions | Pre-existing | New |
|------|-----------|--------------|-----|
| test_sources_endpoint.py | 6 | 3 (prior wave) | 3 |
| test_rag.py | 20 | 16 | 4 |
| test_chat_endpoint.py | 7 | 6 | 1 |

## Full Suite Result

```
pytest backend/app/tests/ -x -v
53 passed, 3 warnings in 2.65s
```

No regressions. All pre-existing tests continue to pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_sources_requires_auth needed db_engine fixture**
- **Found during:** Task 1
- **Issue:** The plan's `test_sources_requires_auth` template used the real `get_current_user` without overriding `get_db`, but FastAPI's auth dependency chain calls `get_db` which requires `init_db()` to be called in the lifespan. Without the lifespan, the test raised `AssertionError: init_db() must be called before get_db()`.
- **Fix:** Added `db_engine` fixture parameter and overrode `get_db` with an in-memory SQLite factory (same pattern used by `test_sources_unauthenticated_returns_401` in the prior wave's implementation). No authorization override applied — so the real JWT check fires and returns 401.
- **Files modified:** `backend/app/tests/test_sources_endpoint.py`
- **Commit:** 34aacb6

**2. [Rule 2 - Preservation] Kept prior wave's extra tests in test_sources_endpoint.py**
- **Found during:** Task 1
- **Issue:** A prior parallel agent had already created test_sources_endpoint.py with 6 tests (3 sources endpoint tests + 3 source_filter propagation through HTTP layer). Plan 02 requires 3 specific function names (test_sources_returns_list, test_sources_requires_auth, test_sources_returns_500_on_qdrant_error) plus the prior wave's extras.
- **Fix:** Rewrote the file with the 3 required function names from the plan's must_haves, plus retained the 3 source_filter propagation tests which add additional value without conflicting.
- **Files modified:** `backend/app/tests/test_sources_endpoint.py`
- **Commit:** 34aacb6

## Known Stubs

None — all tests assert real behavior against the Plan 01 implementation.

## Threat Flags

None — test files do not introduce new network endpoints, auth paths, or trust boundaries.

## Self-Check: PASSED

- [x] `backend/app/tests/test_sources_endpoint.py` exists with `test_sources_returns_list`
- [x] `backend/app/tests/test_rag.py` exists with `test_score_in_citations`
- [x] `backend/app/tests/test_chat_endpoint.py` exists with `test_source_filter_accepted`
- [x] Commit 34aacb6 exists (Task 1)
- [x] Commit 4fe4a36 exists (Task 2)
- [x] 53 tests pass with no regressions

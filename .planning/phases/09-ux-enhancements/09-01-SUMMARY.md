---
phase: 09-ux-enhancements
plan: "01"
subsystem: backend
tags: [rag, api, source-filter, citations, qdrant-facet, auth]
dependency_graph:
  requires: []
  provides:
    - GET /api/sources endpoint
    - source_filter param on stream_answer and stream_conflict_answer
    - score field in all citation dicts
    - get_distinct_sources() using Qdrant facet API
  affects:
    - frontend plans (09-03, 09-04) that consume /api/sources and citation score
tech_stack:
  added: []
  patterns:
    - Qdrant facet API for O(1) title enumeration (limit=200)
    - query_filter=Filter(must=[FieldCondition]) pattern for Qdrant payload filtering
    - source_filter as truthy guard (empty string treated as falsy — no filter)
key_files:
  created:
    - backend/app/api/sources.py
    - backend/app/tests/test_rag_phase9.py
    - backend/app/tests/test_sources_endpoint.py
  modified:
    - backend/app/services/rag.py
    - backend/app/api/chat.py
    - backend/app/main.py
decisions:
  - "source_filter guard uses `if source_filter` (not `is not None`) — empty string treated as no filter per plan spec"
  - "score rounded to 4 decimal places at all three citation construction sites in rag.py"
  - "sources_router registered under /api prefix (consistent with chat_router placement)"
  - "test_sources_unauthenticated_returns_401 uses db_engine fixture to satisfy get_db dependency resolution even though 401 fires before DB lookup"
metrics:
  duration: "~20 minutes"
  completed: "2026-05-06T08:01:02Z"
  tasks_completed: 2
  files_changed: 6
---

# Phase 9 Plan 01: Backend Data Layer for UX Features Summary

**One-liner:** GET /api/sources via Qdrant facet API, source_filter param on both RAG generators with payload-filter pass-through, and score field on all citation dicts — backend contract complete for Plans 03 and 04.

---

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Add source_filter + score to rag.py and create get_distinct_sources() | c9729ac | backend/app/services/rag.py |
| 2 | Create sources.py endpoint and wire chat.py + main.py | 210e51f | backend/app/api/sources.py, backend/app/api/chat.py, backend/app/main.py |

**RED phase (TDD):** e090955

---

## What Was Built

### rag.py changes (c9729ac)
- Added `from qdrant_client.models import Filter, FieldCondition, MatchValue`
- Added `get_distinct_sources()` — calls `qdrant.facet(collection_name="policies", key="title", limit=200)` and returns `sorted(hit.value for hit in response.hits)`
- Added `source_filter: str | None = None` param to both `stream_answer` and `stream_conflict_answer`
- Both `query_points` calls now pass `query_filter=Filter(must=[FieldCondition(key="title", match=MatchValue(value=source_filter))]) if source_filter else None`
- All three citation dict construction paths now include `"score": round(x.score, 4)`

### sources.py (new file, 210e51f)
- `GET /api/sources` guarded by `Depends(get_current_user)`
- Calls `rag.get_distinct_sources()` wrapped in try/except → 500 on failure
- Returns `{"sources": sorted_list}`

### chat.py changes (210e51f)
- `ChatRequest` gains `source_filter: str | None = Field(default=None)`
- `_generate()` passes `source_filter=request.source_filter` to both `stream_answer` and `stream_conflict_answer`

### main.py changes (210e51f)
- Imports `router as sources_router` from `backend.app.api.sources`
- Registers `app.include_router(sources_router, prefix="/api")`

---

## Test Coverage

**New tests (16 tests added):**
- `test_rag_phase9.py` (10 tests): get_distinct_sources facet call, sorted return, source_filter none/with/empty on both generators, score in _build_verified_citations, score in abstain fallback (stream_answer and stream_conflict_answer)
- `test_sources_endpoint.py` (6 tests): GET /api/sources 200/401/500, ChatRequest.source_filter omitted defaults to None, source_filter passed to stream_answer, source_filter passed to stream_conflict_answer

**Full suite:** 48/48 passed

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_sources_unauthenticated_returns_401 needed db_engine fixture**
- **Found during:** Task 2 test execution
- **Issue:** FastAPI resolves ALL dependencies before executing the route handler. Even though `get_current_user` raises 401 before touching the DB (when credentials is None), FastAPI's dependency injection system still tries to resolve `get_db` — which requires `init_db()` to have been called (via lifespan). Without lifespan in tests, this caused `AssertionError: init_db() must be called`.
- **Fix:** Added `db_engine` fixture parameter to the 401 test and provided a `get_db` override using an in-memory SQLite engine — matching the pattern used by `auth_client` fixture in conftest.py.
- **Files modified:** backend/app/tests/test_sources_endpoint.py
- **Commit:** 210e51f (included in same task commit)

---

## Known Stubs

None — all implementation is fully wired. The score field is a live value from Qdrant ScoredPoint.score. The sources list is a live facet query against the Qdrant collection.

---

## Threat Surface Scan

| Flag | File | Description |
|------|------|-------------|
| threat_flag: information-disclosure | backend/app/api/sources.py | GET /api/sources exposes policy title enumeration — mitigated by Depends(get_current_user) per T-09-01 |

No new unplanned threat surface introduced. T-09-01 and T-09-04 mitigations are implemented (auth guard). T-09-02 and T-09-03 accepted (type safety via Pydantic + MatchValue).

---

## Self-Check: PASSED

Files exist:
- backend/app/api/sources.py: FOUND
- backend/app/services/rag.py: FOUND (modified)
- backend/app/api/chat.py: FOUND (modified)
- backend/app/main.py: FOUND (modified)

Commits exist:
- e090955 (RED): FOUND
- c9729ac (GREEN Task 1): FOUND
- 210e51f (GREEN Task 2): FOUND

Tests: 48/48 passed

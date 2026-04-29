---
phase: 05-cross-document-conflict-detection
plan: 01
subsystem: testing
tags: [pytest, tdd, rag, conflict-detection, stubs]

requires:
  - phase: 02-core-rag-pipeline
    provides: rag.py with stream_answer, _build_messages, _build_verified_citations

provides:
  - sample_scored_points_multi fixture in conftest.py (2 MagicMock ScoredPoints from different docs)
  - 6 conflict test stubs in test_rag.py covering CONFLICT-02/03/04
  - 4 conflict detection/routing stubs in test_chat_endpoint.py covering CONFLICT-01

affects: [05-cross-document-conflict-detection-plan-02]

tech-stack:
  added: []
  patterns:
    - "pytest.skip('stub') pattern for Wave 0 TDD RED state — import errors intentional until Plan 02"
    - "MagicMock fixture pattern extended with multi-doc variant for conflict path tests"

key-files:
  created: []
  modified:
    - backend/app/tests/conftest.py
    - backend/app/tests/test_rag.py
    - backend/app/tests/test_chat_endpoint.py

key-decisions:
  - "pytest.skip('stub') chosen over ImportError guard — keeps pre-existing tests runnable with -k filter"
  - "4 stubs in test_chat_endpoint.py (3 detection + 1 routing) vs plan's stated 3 — routing stub test_conflict_route_dispatches_conflict_generator is the 4th per plan acceptance criteria"

patterns-established:
  - "Wave 0 RED: test files import not-yet-existing symbols; full suite fails on import; pre-existing tests pass with -k filter"
  - "sample_scored_points_multi: function-scoped fixture returning list of 2 MagicMock ScoredPoints with different source_doc values"

requirements-completed:
  - CONFLICT-01
  - CONFLICT-02
  - CONFLICT-03
  - CONFLICT-04

duration: 8min
completed: 2026-04-28
---

# Phase 5 Plan 01: Cross-Document Conflict Detection — Wave 0 Test Stubs Summary

**9 TDD RED-state test stubs (6 RAG + 3 detection/routing) plus multi-doc conftest fixture establish the Nyquist-compliant test skeleton for conflict-detection before any implementation exists.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-28T07:42:00Z
- **Completed:** 2026-04-28T07:50:44Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Added `sample_scored_points_multi` fixture to conftest.py — 2 MagicMock ScoredPoints from different source documents (Policy A / Policy B), following exact same pattern as existing `sample_scored_point`
- Added 6 conflict test stubs to test_rag.py with updated import block including `_build_conflict_messages` and `stream_conflict_answer` (RED state — ImportError until Plan 02)
- Added 4 conflict detection/routing stubs to test_chat_endpoint.py with `is_conflict_query` import (RED state — ImportError until Plan 02)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add sample_scored_points_multi fixture to conftest.py** - `3c048d8` (test)
2. **Task 2: Add 6 conflict test stubs to test_rag.py** - `10e0d58` (test)
3. **Task 3: Add 4 conflict detection/routing stubs to test_chat_endpoint.py** - `881c946` (test)

## Files Created/Modified

- `backend/app/tests/conftest.py` - Added `sample_scored_points_multi` fixture (25 lines)
- `backend/app/tests/test_rag.py` - Updated import block + 6 stub test functions (70 lines)
- `backend/app/tests/test_chat_endpoint.py` - Added `is_conflict_query` import + 4 stub test functions (44 lines)

## Decisions Made

- Used `pytest.skip("stub")` pattern (consistent with Phase 2 Plan 01 precedent in STATE.md) — CI never blocked by pre-implementation stubs
- Extended multi-line import form for rag.py symbols — readable and consistent with project style
- test_chat_endpoint.py has 4 stubs (not 3 as mentioned in plan objective text) — the plan's acceptance criteria explicitly requires 4 stubs including `test_conflict_route_dispatches_conflict_generator`

## Deviations from Plan

None — plan executed exactly as written. All 9 stubs plus 1 fixture added per specification.

## Issues Encountered

None. The worktree required using absolute worktree paths for all file edits (edits to main repo path do not affect the worktree filesystem).

## Known Stubs

All stubs in this plan are intentional RED-state placeholders:

| Stub | File | Reason |
|------|------|--------|
| `test_conflict_retrieve_params` | test_rag.py:208 | Wave 0 — Plan 02 implements stream_conflict_answer |
| `test_conflict_prompt_contains_verdict_format` | test_rag.py:218 | Wave 0 — Plan 02 implements _build_conflict_messages |
| `test_conflict_prompt_contains_classifications` | test_rag.py:227 | Wave 0 — Plan 02 implements _build_conflict_messages |
| `test_conflict_prompt_abstain_wording` | test_rag.py:236 | Wave 0 — Plan 02 implements _build_conflict_messages |
| `test_conflict_done_event_shape` | test_rag.py:248 | Wave 0 — Plan 02 implements stream_conflict_answer |
| `test_conflict_history_sliced_to_6` | test_rag.py:259 | Wave 0 — Plan 02 implements _build_conflict_messages |
| `test_conflict_detection_keywords` | test_chat_endpoint.py:94 | Wave 0 — Plan 02 implements is_conflict_query |
| `test_standard_query_not_detected` | test_chat_endpoint.py:104 | Wave 0 — Plan 02 implements is_conflict_query |
| `test_false_positive_graceful` | test_chat_endpoint.py:113 | Wave 0 — Plan 02 implements is_conflict_query |
| `test_conflict_route_dispatches_conflict_generator` | test_chat_endpoint.py:126 | Wave 0 — Plan 02 implements routing in chat.py |

## Next Phase Readiness

- Wave 0 complete: all test stubs exist, RED state established
- Plan 02 (Wave 1) can now implement `_build_conflict_messages`, `stream_conflict_answer`, and `is_conflict_query` to turn these tests GREEN
- Pre-existing tests pass when run with `-k "not conflict and not detection and not false_positive and not dispatch"` filter

---
*Phase: 05-cross-document-conflict-detection*
*Completed: 2026-04-28*

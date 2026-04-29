---
phase: 05-cross-document-conflict-detection
plan: 02
subsystem: rag-pipeline
tags: [rag, conflict-detection, keyword-routing, pytest, tdd, green-pass]

requires:
  - phase: 05-cross-document-conflict-detection
    plan: 01
    provides: 9 TDD RED-state stubs (6 RAG + 4 chat endpoint) + sample_scored_points_multi fixture

provides:
  - is_conflict_query() helper with _CONFLICT_PATTERN compiled regex in chat.py
  - Routing branch in chat_endpoint() dispatching to stream_conflict_answer or stream_answer
  - stream_conflict_answer() async generator in rag.py (limit=10, conflict prompt)
  - _build_conflict_messages() pure helper with Verdict format + taxonomy + ABSTAIN_INSTRUCTION
  - All 9 previously-skipped stubs replaced with passing assertions (32/32 tests green)

affects: []

tech-stack:
  added: []
  patterns:
    - "is_conflict_query(): module-level compiled _CONFLICT_PATTERN with re.IGNORECASE — avoids recompilation per request"
    - "stream_conflict_answer() mirrors stream_answer() exactly — only limit (10 vs 5) and message builder differ"
    - "_build_conflict_messages() follows same history[-6:] slice + system/history/user message structure as _build_messages()"
    - "Verdict format instruction in system prompt: 'Verdict: <classification> — <one-sentence reason>'"
    - "Abstain fallback block copied verbatim into stream_conflict_answer() — Pitfall 4 avoidance"
    - "delta.content None guard copied from stream_answer() — Pitfall 5 avoidance"

key-files:
  created: []
  modified:
    - backend/app/api/chat.py
    - backend/app/services/rag.py
    - backend/app/tests/test_chat_endpoint.py
    - backend/app/tests/test_rag.py

key-decisions:
  - "is_conflict_query() placed before router = APIRouter() — module-level function, not method"
  - "_CONFLICT_PATTERN compiled at module level per D-01 / Pitfall 1 Unicode note"
  - "history materialized before _generate() inner function — avoids re-evaluation per iteration"
  - "stream_conflict_answer() appended to END of rag.py after stream_answer() — no structural changes"
  - "Warning logged (not error) when Verdict: line absent from conflict response — answer still valid"

requirements-completed:
  - CONFLICT-01
  - CONFLICT-02
  - CONFLICT-03
  - CONFLICT-04

duration: ~4min
completed: 2026-04-28
---

# Phase 5 Plan 02: Cross-Document Conflict Detection — Wave 1 GREEN Pass Summary

**Conflict-detection GREEN pass: is_conflict_query() keyword router + stream_conflict_answer() with Verdict-format conflict prompt — all 9 TDD stubs replaced with passing assertions; full 32-test suite green.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-28T08:06:22Z
- **Completed:** 2026-04-28T08:09:57Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

### Task 1: chat.py — is_conflict_query() + routing branch
- Added `import re` and `_CONFLICT_PATTERN` compiled regex at module level
- `_CONFLICT_PATTERN` covers all 7 D-02 keywords: `conflict`, `contradict`, `mâu thuẫn`, `so sánh`, `khác nhau`, `differ`, `both documents` — case-insensitive
- Added `is_conflict_query(message: str) -> bool` as a module-level function before `router = APIRouter()`
- Modified `chat_endpoint()`: materialized `history` before `_generate()` inner function; added routing branch calling `rag.stream_conflict_answer()` for conflict queries and `rag.stream_answer()` for standard queries
- Replaced all 4 `pytest.skip("stub")` calls in `test_chat_endpoint.py` with passing assertions

### Task 2: rag.py — _build_conflict_messages() + stream_conflict_answer()
- Added `_build_conflict_messages()` pure helper appended after `stream_answer()` — identical message structure (system + history slice + user) with conflict-specific system prompt
- System prompt includes: role statement, numbered chunk injection format (D-09), document-by-document organization (D-10), Verdict format instruction (D-11), three-way taxonomy (D-12: Contradictory/Consistent/One-Silent), ABSTAIN_INSTRUCTION (D-13)
- Added `stream_conflict_answer()` async generator mirroring `stream_answer()` exactly: same embed call, same streaming loop with `delta.content` None guard (Pitfall 5), same `_build_verified_citations()` reuse, same abstain fallback block (Pitfall 4), only `limit=10` and `_build_conflict_messages()` differ
- Added `logger.warning()` when `Verdict:` not found in `full_answer` — non-fatal, answer still valid
- Replaced all 6 `pytest.skip("stub")` calls in `test_rag.py` with passing assertions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add is_conflict_query() and routing branch to chat.py** - `3143c04` (feat)
2. **Task 2: Add stream_conflict_answer() and _build_conflict_messages() to rag.py** - `1cff1c4` (feat)

## Files Created/Modified

- `backend/app/api/chat.py` — Added `import re`, `_CONFLICT_PATTERN`, `is_conflict_query()`, updated `chat_endpoint()` with routing branch (+30 lines)
- `backend/app/services/rag.py` — Appended `_build_conflict_messages()` and `stream_conflict_answer()` (+115 lines)
- `backend/app/tests/test_chat_endpoint.py` — Replaced 4 stubs with passing assertions (+34 lines)
- `backend/app/tests/test_rag.py` — Replaced 6 stubs with passing assertions (+55 lines)

## Test Results

```
32 passed, 0 skipped, 3 warnings in 2.29s
```

- 10 pre-existing RAG tests (Phase 2): all pass — no regressions
- 10 pre-existing auth/endpoint tests (Phase 3): all pass — no regressions
- 6 new conflict RAG tests: all pass
- 4 new conflict detection/routing tests: all pass

## Decisions Made

- `is_conflict_query()` placed at module level (before `router = APIRouter()`) rather than inside a class — consistent with project pattern of module-level helpers
- `history` materialized before `_generate()` to match the expected argument shape (`list[dict]`) — inner function closure captures the pre-converted list
- `stream_conflict_answer()` appended to END of `rag.py` after `_build_conflict_messages()` — keeps the file ordered as: constants → singletons → pure helpers → standard generator → conflict helpers + generator
- No extraction of the abstain fallback into a shared helper (would be Rule 4 architectural change) — copied verbatim per plan spec and Pitfall 4 guidance

## Deviations from Plan

None — plan executed exactly as written. All production code and test assertions match the specifications in the PLAN.md action blocks.

## Known Stubs

None. All stubs from Plan 01 have been replaced with passing implementations.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The conflict path is a routing branch within the existing authenticated `POST /api/chat` endpoint. All threat mitigations from the plan's threat register are implemented:

- **T-05-02-02 (prompt injection):** `_build_conflict_messages()` assembles system prompt server-side; user message appended as final user turn only
- **T-05-02-03 (fabricated citations):** `_build_verified_citations()` reused unchanged — strips IDs > len(results)
- **T-05-02-04 (role injection):** `HistoryItem.role: Literal["user","assistant"]` unchanged; verified by existing `test_system_role_rejected`

## Self-Check

Files exist:
- `backend/app/api/chat.py` — FOUND (contains is_conflict_query, _CONFLICT_PATTERN, stream_conflict_answer routing)
- `backend/app/services/rag.py` — FOUND (contains stream_conflict_answer, _build_conflict_messages, limit=10, Verdict:)
- `backend/app/tests/test_chat_endpoint.py` — FOUND (0 pytest.skip calls)
- `backend/app/tests/test_rag.py` — FOUND (0 pytest.skip calls)

Commits exist:
- `3143c04` — feat(05-02): add is_conflict_query() and routing branch to chat.py
- `1cff1c4` — feat(05-02): add stream_conflict_answer() and _build_conflict_messages() to rag.py

## Self-Check: PASSED

---
*Phase: 05-cross-document-conflict-detection*
*Completed: 2026-04-28*

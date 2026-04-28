---
phase: 05-cross-document-conflict-detection
verified: 2026-04-28T08:30:00Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 5: Cross-Document Conflict Detection Verification Report

**Phase Goal:** Queries that imply cross-document comparison trigger a dedicated retrieval and prompting path that returns a structured conflict classification citing exact passages from each involved document.
**Verified:** 2026-04-28T08:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Submitting a question containing "conflict", "mâu thuẫn", "so sánh", or "differ" causes the system to retrieve top-10 chunks (not top-5) from across all source documents | VERIFIED | `stream_conflict_answer()` calls `query_points(limit=10, score_threshold=0.55, with_payload=True)` — confirmed at rag.py:282. `test_conflict_retrieve_params` passes. |
| 2 | The response for a comparison query uses the conflict-detection prompt and classifies passages as contradictory, consistent, or one-silent | VERIFIED | `_build_conflict_messages()` system prompt contains "Verdict:", "Contradictory", "Consistent", "One-Silent", and ABSTAIN_INSTRUCTION. Three prompt tests pass. |
| 3 | The conflict response identifies specific documents and cites exact passages from each side by numeric chunk ID | VERIFIED | `_build_conflict_messages()` formats chunks as `[N] source: {title}\n{text}` with document-by-document organization. `_build_verified_citations()` is reused to verify IDs. |
| 4 | A standard single-document query is unaffected — still uses top-5 retrieval and normal grounded-response prompt | VERIFIED | `is_conflict_query()` gates routing; non-matching queries go to `stream_answer(limit=5)`. `test_standard_query_not_detected` and `test_endpoint_content_type` (standard path) both pass. |
| 5 | A message containing "mâu thuẫn" causes rag.stream_conflict_answer to be called instead of rag.stream_answer | VERIFIED | `is_conflict_query()` with `_CONFLICT_PATTERN` compiled at module level. `test_conflict_route_dispatches_conflict_generator` confirms HTTP routing — mock_conflict called once, mock_standard not called. |
| 6 | The done event payload shape is unchanged: {type, answer, citations: [{id, qdrant_id, title, text}]} | VERIFIED | `stream_conflict_answer()` yields identical payload shape to `stream_answer()`. `test_conflict_done_event_shape` passes. |
| 7 | All 9 previously-skipped test stubs now pass with no regressions | VERIFIED | Full test suite: 32 passed, 0 skipped, 3 warnings in 1.75s |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/services/rag.py` | `stream_conflict_answer()` async generator + `_build_conflict_messages()` helper | VERIFIED | Both functions present at lines 207-344. `stream_conflict_answer` uses `limit=10`, `_build_conflict_messages` builds Verdict-format prompt. |
| `backend/app/api/chat.py` | `is_conflict_query()` helper + routing branch in `chat_endpoint()` | VERIFIED | `_CONFLICT_PATTERN` compiled at module level (lines 24-27). `is_conflict_query()` defined at lines 30-36. Routing branch at lines 97-100. |
| `backend/app/tests/conftest.py` | `sample_scored_points_multi` fixture | VERIFIED | Fixture present at lines 132-154 returning 2 MagicMock ScoredPoints from "Policy A" / "Policy B" with different `source_doc` values. |
| `backend/app/tests/test_rag.py` | 6 conflict test stubs (now passing) | VERIFIED | All 6 tests present and passing: `test_conflict_retrieve_params`, `test_conflict_prompt_contains_verdict_format`, `test_conflict_prompt_contains_classifications`, `test_conflict_prompt_abstain_wording`, `test_conflict_done_event_shape`, `test_conflict_history_sliced_to_6`. |
| `backend/app/tests/test_chat_endpoint.py` | 4 conflict detection/routing tests (now passing) | VERIFIED | All 4 tests present and passing: `test_conflict_detection_keywords`, `test_standard_query_not_detected`, `test_false_positive_graceful`, `test_conflict_route_dispatches_conflict_generator`. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/app/api/chat.py` | `backend/app/services/rag.py` | `is_conflict_query` gates `stream_conflict_answer` call in `_generate()` | WIRED | Lines 97-100 of chat.py: `if is_conflict_query(request.message): generator = rag.stream_conflict_answer(...)`. HTTP test verifies this routing. |
| `backend/app/services/rag.py` | Qdrant | `query_points(limit=10, score_threshold=0.55)` | WIRED | rag.py:279-285 passes `limit=10` to `qdrant.query_points`. `test_conflict_retrieve_params` asserts this. |
| `backend/app/services/rag.py` | `_build_verified_citations` | conflict path reuses same citation verifier | WIRED | rag.py:323: `citations = _build_verified_citations(full_answer, results)` inside `stream_conflict_answer`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `stream_conflict_answer` | `results` from `qdrant.query_points` | `AsyncQdrantClient.query_points(limit=10)` | Yes — real DB query with `limit=10, score_threshold=0.55` | FLOWING |
| `_build_conflict_messages` | `retrieved_chunks` list | Passed from `stream_conflict_answer` — populated from Qdrant | Yes — chunks contain real `payload.get('title')` and `payload.get('text')` | FLOWING |
| `is_conflict_query` | `message` string | `request.message` from `ChatRequest` body | Yes — live user input, not hardcoded | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 22 conflict + pre-existing RAG tests pass | `pytest backend/app/tests/test_rag.py backend/app/tests/test_chat_endpoint.py -x -v` | 22 passed, 0 skipped | PASS |
| Full 32-test suite green, no regressions | `pytest backend/app/tests/ -v` | 32 passed, 0 skipped, 0 failures | PASS |
| `is_conflict_query` detects 7 keywords case-insensitively | `test_conflict_detection_keywords` | Asserts all 7 keywords + case variants → True | PASS |
| Standard query not mis-routed | `test_standard_query_not_detected` | Asserts "what is the data retention policy?" → False | PASS |
| HTTP routing dispatches conflict message to correct generator | `test_conflict_route_dispatches_conflict_generator` | mock_conflict called once, mock_standard not called | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CONFLICT-01 | 05-01-PLAN, 05-02-PLAN | System detects cross-document comparison queries via keywords | SATISFIED | `is_conflict_query()` with `_CONFLICT_PATTERN` in chat.py; verified by `test_conflict_detection_keywords`, `test_standard_query_not_detected`, `test_false_positive_graceful` |
| CONFLICT-02 | 05-01-PLAN, 05-02-PLAN | Comparison queries retrieve top-10 chunks across all source documents | SATISFIED | `stream_conflict_answer()` calls `query_points(limit=10)` at rag.py:282; verified by `test_conflict_retrieve_params` |
| CONFLICT-03 | 05-01-PLAN, 05-02-PLAN | Dedicated conflict-detection prompt with contradictory/consistent/one-silent classification | SATISFIED | `_build_conflict_messages()` includes "Verdict:", "Contradictory", "Consistent", "One-Silent", ABSTAIN_INSTRUCTION; verified by 3 prompt tests |
| CONFLICT-04 | 05-01-PLAN, 05-02-PLAN | Conflict response identifies documents and cites exact passages by numeric ID | SATISFIED | `_build_conflict_messages()` formats `[N] source: {title}` per chunk; `_build_verified_citations()` reused; done event shape verified by `test_conflict_done_event_shape` |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/api/auth.py` | 129 | `return {}` | Info | Pre-existing in auth.py from Phase 3; not introduced in Phase 5. Not relevant to conflict detection goal. |

No anti-patterns introduced by Phase 5 code. No `pytest.skip` calls remain in any test file. No placeholder comments or hardcoded empty data in conflict path code.

### Human Verification Required

None. All Phase 5 behaviors are fully verifiable programmatically:
- Keyword detection is a pure function (tested via unit tests)
- Routing logic is tested via HTTP mock (httpx + ASGITransport)
- Prompt content verified via pure function assertions
- Retrieval parameters verified via mock call inspection
- Response shape verified via event payload assertions

Phase 5 has no UI component ("UI hint: no" in ROADMAP). No visual, real-time, or external service behavior requires human review.

### Gaps Summary

No gaps. All 7 must-have truths are verified, all 5 artifacts pass all 4 levels (exists, substantive, wired, data-flowing), all 3 key links are wired, all 4 requirement IDs are satisfied, and the full 32-test suite passes with 0 skips and 0 regressions.

The phase goal is fully achieved: a user asking "which policies conflict on data retention?" will be routed to `stream_conflict_answer()` which retrieves top-10 chunks, builds a Verdict-format prompt with Contradictory/Consistent/One-Silent taxonomy, and returns a structured answer with inline citations in the same payload shape as the standard path.

---

_Verified: 2026-04-28T08:30:00Z_
_Verifier: Claude (gsd-verifier)_

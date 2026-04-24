---
phase: 02-core-rag-pipeline
plan: "02"
subsystem: rag-pipeline
tags: [rag, embeddings, streaming, citations, qdrant, openrouter]
dependency_graph:
  requires: ["02-01"]
  provides: ["backend/app/services/rag.py", "stream_answer async generator"]
  affects: ["backend/app/api/chat.py (Plan 03)"]
tech_stack:
  added: []
  patterns:
    - "AsyncGenerator yielding delta/done/error SSE events"
    - "patch.object for module-level singleton mocking in pytest"
    - "D-10 history slice: history[-6:] if len(history) > 6 else history"
    - "Pitfall 1 token guard: chunk.choices and chunk.choices[0].delta.content"
    - "Pitfall 2 LLM error: try/except wraps entire stream loop, yields error event"
key_files:
  created:
    - backend/app/services/__init__.py
    - backend/app/services/rag.py
  modified:
    - backend/app/tests/test_rag.py
decisions:
  - "patch.object(rag, 'openrouter', mock) used instead of @patch decorator — cleaner with context manager for async generators"
  - "stream_answer import moved to top-level in test file (not deferred) — rag.py fully implemented before tests run"
  - "model_arg extracted from call_args.kwargs directly — positional/keyword mixed extraction has Python operator-precedence pitfall"
metrics:
  duration: "5 min"
  completed: "2026-04-24"
  tasks: 3
  files: 3
---

# Phase 02 Plan 02: Core RAG Pipeline Service Summary

**One-liner:** Full RAG pipeline as `stream_answer` async generator — embed via Nemotron, retrieve top-5 from Qdrant (score_threshold=0.55), stream Gemma 4 26B tokens as delta events, verify and strip fabricated citations, emit done event with grounded citations.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Services package marker and rag.py skeleton | 45c8f51 | backend/app/services/__init__.py, backend/app/services/rag.py |
| 2 | _build_messages and _build_verified_citations pure functions | 9d791ae | backend/app/services/rag.py, backend/app/tests/test_rag.py |
| 3 | stream_answer async generator + all 10 mock tests | c67849f | backend/app/services/rag.py, backend/app/tests/test_rag.py |

## Verification

```
pytest backend/app/tests/test_rag.py -v → 10 PASSED, 0 failed, 0 skipped
```

All structural checks pass:
- `ABSTAIN_INSTRUCTION` contains exact D-05 wording
- `score_threshold=0.55` and `limit=5` in qdrant.search call
- `[warn] fabricated citation` warning log present
- `No matching policy found for your question.` early-return message present
- `chunk.choices[0].delta.content` Pitfall 1 guard present
- `LLM service temporarily unavailable` Pitfall 2 handler present

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed .env field name mismatch**
- **Found during:** Task 1 verification
- **Issue:** `.env` had `API_KEY = "sk-or-..."` but `Settings` model expects `OPENROUTER_API_KEY`. pydantic-settings raised `Extra inputs are not permitted` on startup.
- **Fix:** Rewrote `.env` with correct field names (`OPENROUTER_API_KEY`, `JWT_SECRET`)
- **Files modified:** `.env`
- **Commit:** 45c8f51 (part of Task 1 commit)

**2. [Rule 1 - Bug] Fixed module-level import of stream_answer causing collection failure**
- **Found during:** Task 2 test run
- **Issue:** test_rag.py imported `stream_answer` at module level before it was implemented, causing pytest collection to fail with ImportError
- **Fix:** Removed the premature `stream_answer` import from Task 2's test file; re-added it once implemented in Task 3
- **Files modified:** backend/app/tests/test_rag.py
- **Commit:** 9d791ae (part of Task 2 commit)

**3. [Rule 1 - Bug] Fixed Python operator-precedence in model_arg extraction**
- **Found during:** Task 3 test run (test_embed_calls_correct_model failed)
- **Issue:** `ca.kwargs.get("model") or ca.args[0] if ca.args else None` evaluates as `(expr) if ca.args else None` due to ternary operator precedence — returns None when args is empty tuple, even though kwargs has the value
- **Fix:** Simplified to `ca.kwargs.get("model")` since embeddings.create always uses keyword args
- **Files modified:** backend/app/tests/test_rag.py
- **Commit:** c67849f (part of Task 3 commit)

## Known Stubs

None — all functions fully implemented and tested.

## Threat Flags

No new security surface beyond what the plan's threat model covers. All T-02-02-xx mitigations implemented:
- T-02-02-01 (fabricated citations): `_build_verified_citations` strips out-of-bounds IDs with warning log
- T-02-02-02 (LLM DoS/error): `try/except Exception` wraps entire stream loop
- T-02-02-04 (ABSTAIN_INSTRUCTION): exact D-05 wording present

## Self-Check: PASSED

- `backend/app/services/__init__.py` exists: FOUND
- `backend/app/services/rag.py` exists: FOUND
- `backend/app/tests/test_rag.py` updated: FOUND
- Commit 45c8f51 exists: FOUND
- Commit 9d791ae exists: FOUND
- Commit c67849f exists: FOUND
- All 10 tests PASSED: CONFIRMED

---
phase: 02-core-rag-pipeline
plan: "03"
subsystem: backend-api
tags: [fastapi, sse, pydantic, chat-endpoint, security, http-layer]
dependency_graph:
  requires: ["02-01", "02-02"]
  provides: ["POST /api/chat endpoint", "ChatRequest/HistoryItem/Citation models", "SSE streaming HTTP layer"]
  affects: ["backend/app/api/chat.py", "backend/app/main.py", "backend/app/core/telemetry.py"]
tech_stack:
  added: []
  patterns: ["FastAPI APIRouter", "StreamingResponse SSE", "httpx.AsyncClient ASGITransport test pattern", "Pydantic Literal role validation"]
key_files:
  created:
    - backend/app/api/__init__.py
    - backend/app/api/chat.py
  modified:
    - backend/app/main.py
    - backend/app/core/telemetry.py
    - backend/app/tests/test_chat_endpoint.py
decisions:
  - "HistoryItem.role: Literal[user, assistant] is the security control — never widen (D-03 / Pitfall 3)"
  - "Deferred opentelemetry imports inside setup_tracing() body — module safe to import without opentelemetry"
  - "_generate() nested async generator inside route function — standard FastAPI SSE pattern (RESEARCH.md Pattern 1)"
  - "patch backend.app.services.rag.stream_answer at module level for HTTP endpoint tests"
metrics:
  duration: "~4 min"
  completed_date: "2026-04-24"
  tasks: 3
  files_changed: 5
---

# Phase 2 Plan 03: Chat HTTP Endpoint Summary

**One-liner:** FastAPI APIRouter with POST /api/chat SSE endpoint, Pydantic role-guarded request models, and main.py router registration — completing the Phase 2 HTTP layer.

## What Was Built

### backend/app/api/__init__.py
Empty package marker for the `api` module.

### backend/app/api/chat.py
FastAPI `APIRouter` with:
- `HistoryItem` model: `role: Literal["user", "assistant"]` — rejects `"system"` with HTTP 422 (prompt injection mitigation)
- `ChatRequest` model: `message` with `min_length=1, max_length=4000`; `history: list[HistoryItem]`
- `Citation` model: `id`, `qdrant_id`, `title`, `text`
- `POST /chat` route: returns `StreamingResponse(media_type="text/event-stream")` wrapping `rag.stream_answer`
- Phase 3 auth slot comment present: `# current_user: User = Depends(get_current_user),  # Phase 3 adds this`

### backend/app/main.py (modified)
`create_app()` now assigns `FastAPI(...)` to `app`, calls `app.include_router(chat_router, prefix="/api")`, and returns `app`.

### backend/app/tests/test_chat_endpoint.py (stubs filled)
- `test_endpoint_content_type`: POST `/api/chat` returns 200 + `Content-Type: text/event-stream`. Patches `rag.stream_answer` to avoid live API calls.
- `test_system_role_rejected`: POST `/api/chat` with `role="system"` in history returns 422.

## Verification Results

- `pytest backend/app/tests/ -v`: **12 PASSED, 0 FAILED, 0 SKIPPED**
- All structural checks pass (include_router, Literal, score_threshold, abstain wording, fabricated citation guard)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Deferred opentelemetry imports in telemetry.py**
- **Found during:** Task 2 verification
- **Issue:** `backend/app/core/telemetry.py` had top-level `from opentelemetry import trace` and related imports at module level. Since `opentelemetry` is not in `requirements.txt` and not installed in the dev venv, importing `main.py` (which imports `telemetry.py`) failed with `ModuleNotFoundError`.
- **Fix:** Moved all `opentelemetry` and `openinference` imports inside the `setup_tracing()` function body, wrapped in the existing `try/except ImportError` block. Module is now safe to import without opentelemetry installed.
- **Files modified:** `backend/app/core/telemetry.py`
- **Commit:** b842f54

## Known Stubs

None — all stubs from plans 02-01 through 02-03 have been filled in and all 12 tests pass.

## Threat Flags

No new threat surface introduced beyond what was planned. The `HistoryItem.role: Literal["user", "assistant"]` mitigation (T-02-03-01) and `ChatRequest.message max_length=4000` mitigation (T-02-03-02) are both implemented.

## Self-Check: PASSED

All created files exist on disk. All task commits verified in git log. No unexpected file deletions.

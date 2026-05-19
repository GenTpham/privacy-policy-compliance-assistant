---
phase: "10"
plan: "03"
subsystem: backend/api/chat
tags: [slowapi, rate-limiting, chat-endpoint, decorator]
dependency_graph:
  requires:
    - backend/app/core/limiter.py (Plan 01 — limiter singleton, _get_chat_rate_limit)
    - Settings.rate_limit_per_minute (Plan 01 — config.py)
  provides:
    - POST /api/chat with per-user rate limiting (@limiter.limit)
  affects:
    - backend/app/api/chat.py
tech_stack:
  added: []
  patterns:
    - "@router.post outer decorator, @limiter.limit inner decorator (slowapi required order)"
    - "request: Request as first param, body: ChatRequest renamed to avoid name collision"
key_files:
  created: []
  modified:
    - backend/app/api/chat.py
decisions:
  - "T-10-10 mitigated: @limiter.limit(_get_chat_rate_limit) applies per-user RPM; HTTP 429 returned automatically by slowapi"
  - "T-10-12 mitigated: @router.post at line 80, @limiter.limit at line 81 — correct decorator order verified"
  - "Rename ChatRequest param from 'request' to 'body' avoids Starlette Request name collision (slowapi requirement)"
metrics:
  duration: "3m"
  completed_date: "2026-05-13"
  tasks_completed: 1
  tasks_total: 1
---

# Phase 10 Plan 03: Rate-limit POST /api/chat Summary

**One-liner:** Applied slowapi @limiter.limit(_get_chat_rate_limit) to chat_endpoint with correct decorator order, starlette Request first parameter, and ChatRequest body param renamed to avoid collision.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add @limiter.limit() decorator and request: Request parameter to chat_endpoint | a3306c7 | backend/app/api/chat.py |

---

## What Was Built

### backend/app/api/chat.py

Single-file modification applying rate limiting to the POST /api/chat endpoint:

1. **New imports added:**
   - `from starlette.requests import Request` — starlette Request type required by slowapi
   - `from backend.app.core.limiter import _get_chat_rate_limit, limiter` — Plan 01 deliverables

2. **Decorator order (critical):**
   - `@router.post("/chat")` remains outermost (line 80)
   - `@limiter.limit(_get_chat_rate_limit)` added as second decorator (line 81)
   - Wrong order silently skips rate limiting — verified by line number assertion

3. **Parameter changes:**
   - `request: Request` added as first parameter — required by slowapi's key_func resolution
   - `request: ChatRequest` renamed to `body: ChatRequest` — eliminates name collision with starlette Request

4. **Body reference update:**
   - All `request.message`, `request.history`, `request.source_filter` → `body.message`, `body.history`, `body.source_filter`

5. **Docstring updated** to document rate limiting behavior per D-05/D-07/D-08.

---

## Decisions Made

- **Decorator order invariant:** `@router.post` outer, `@limiter.limit` inner — verified via line number check in acceptance criteria. Reversed order is a silent failure (T-10-12).
- **`body` rename:** Convention used throughout project for Pydantic body params when starlette `Request` is also needed — avoids ambiguity and name collision.
- **Dynamic rate limit callable:** `_get_chat_rate_limit` passed as callable (not string) — reads `Settings.rate_limit_per_minute` at request time; changing `RATE_LIMIT_PER_MINUTE` env var takes effect without code change (D-08).

---

## Deviations from Plan

None — plan executed exactly as written.

---

## Threat Surface Scan

No new network endpoints or auth paths introduced. The existing POST /api/chat endpoint now has rate limiting applied as planned.

Threat mitigations verified:
- **T-10-10** (DoS — chat endpoint): `@limiter.limit(_get_chat_rate_limit)` is present; slowapi automatically returns HTTP 429 when limit exceeded.
- **T-10-11** (DoS — token rotation bypass): Rate limit key is `user:<username>` from JWT payload (in limiter.py Plan 01); multiple tokens for same user share the same counter.
- **T-10-12** (DoS — wrong decorator order): `@router.post` at line 80 < `@limiter.limit` at line 81; verified by acceptance criteria assertion.

---

## Known Stubs

None.

---

## Self-Check: PASSED

- [x] `backend/app/api/chat.py` contains `from starlette.requests import Request`
- [x] `backend/app/api/chat.py` contains `from backend.app.core.limiter import _get_chat_rate_limit, limiter`
- [x] `backend/app/api/chat.py` contains `@limiter.limit(_get_chat_rate_limit)`
- [x] `backend/app/api/chat.py` contains `request: Request,` as first parameter
- [x] `backend/app/api/chat.py` contains `body: ChatRequest,` as renamed Pydantic body parameter
- [x] No `request.message`, `request.history`, or `request.source_filter` in function body
- [x] `body.message`, `body.history`, `body.source_filter` all present
- [x] `@router.post` at line 80 < `@limiter.limit` at line 81 (correct decorator order)
- [x] `python -c "import ast; ast.parse(open('backend/app/api/chat.py', encoding='utf-8').read()); print('ok')"` exits 0
- [x] Commit: a3306c7

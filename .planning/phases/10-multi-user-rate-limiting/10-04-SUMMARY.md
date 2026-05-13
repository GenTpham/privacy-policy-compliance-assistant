---
phase: "10"
plan: "04"
subsystem: backend/tests
tags: [pytest, admin-tests, rate-limiting-tests, AUTH-05, AUTH-06, AUTH-07]
dependency_graph:
  requires:
    - backend/app/api/admin.py (Plan 02 — admin CRUD endpoints)
    - backend/app/api/chat.py (Plan 03 — rate-limited chat endpoint)
    - backend/app/core/limiter.py (Plan 01 — limiter singleton)
    - backend/app/services/auth.py (Plan 01 — create_access_token, require_admin)
  provides:
    - AUTH-05 test coverage (admin CRUD, no self-registration)
    - AUTH-06 test coverage (429 on limit exceeded, per-user independent counters)
    - AUTH-07 test coverage (403 for non-admin, 401 for unauthenticated)
  affects:
    - backend/app/tests/conftest.py
    - backend/app/tests/test_admin.py
    - backend/app/tests/test_rate_limit.py
    - backend/app/core/limiter.py
tech_stack:
  added: []
  patterns:
    - "admin_client fixture with Limiter(enabled=False) to prevent counter bleed in admin tests"
    - "rate_limited_client fixture with real Limiter for 429 enforcement"
    - "patch backend.app.core.limiter.get_settings with jwt_secret for per-user rate limit key resolution"
    - "_get_chat_rate_limit() takes no args — slowapi calls limit providers with zero args when param name is not 'key'"
key_files:
  created:
    - backend/app/tests/test_admin.py
    - backend/app/tests/test_rate_limit.py
  modified:
    - backend/app/tests/conftest.py
    - backend/app/core/limiter.py
decisions:
  - "_get_chat_rate_limit signature must be zero-arg: slowapi LimitGroup.__iter__ calls __limit_provider() with no args when param name is not 'key'"
  - "patch get_settings in limiter module (not the chat module name) — slowapi captures function reference at decoration time, not the module name"
  - "mock settings must include jwt_secret so _get_rate_limit_key can decode JWT and produce per-user keys (not IP fallback)"
metrics:
  duration: "15m"
  completed_date: "2026-05-13"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 10 Plan 04: Test Suite (Admin CRUD, RBAC, Rate Limiting) Summary

**One-liner:** Full Phase 10 test suite — 8 admin CRUD/RBAC tests (AUTH-05, AUTH-07) + 2 per-user rate limit tests (AUTH-06) with admin_client/rate_limited_client fixtures.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add admin_client and rate_limited_client fixtures to conftest.py | edbd5ba | backend/app/tests/conftest.py |
| 2 | Write test_admin.py (AUTH-05, AUTH-07) and test_rate_limit.py (AUTH-06) | 18d6398 | backend/app/tests/test_admin.py, backend/app/tests/test_rate_limit.py, backend/app/core/limiter.py |

---

## What Was Built

### backend/app/tests/conftest.py

Two new fixtures appended, following the existing `auth_client` pattern:

1. **`admin_client`** — httpx.AsyncClient with `Limiter(enabled=False)`. Rate limiting is disabled to prevent MemoryStorage counter bleed from other tests. Used by all test_admin.py tests.

2. **`rate_limited_client`** — httpx.AsyncClient with the real Limiter active. Used by test_rate_limit.py for 429 enforcement tests. Each test gets a fresh app instance (function-scoped) with fresh MemoryStorage.

### backend/app/tests/test_admin.py (new)

8 tests covering AUTH-05 and AUTH-07:

| Test | Requirement | Assertion |
|------|------------|-----------|
| test_create_user | AUTH-05 | 201, UserResponse, hashed_password absent |
| test_create_user_conflict | AUTH-05 | 409, "Username already exists" |
| test_list_users | AUTH-05 | 200, list of users, hashed_password absent for all |
| test_delete_user | AUTH-05 | 204, user absent from subsequent GET |
| test_delete_user_not_found | AUTH-05 | 404, "User not found" |
| test_no_self_registration | AUTH-05 | POST /users and POST /register both 404 |
| test_non_admin_forbidden | AUTH-07 | 403, "Admin access required" |
| test_unauthenticated_forbidden | AUTH-07 | 401 |

### backend/app/tests/test_rate_limit.py (new)

2 tests covering AUTH-06:

| Test | Requirement | Assertion |
|------|------------|-----------|
| test_rate_limit_returns_429 | AUTH-06 | r1 != 429, r2 == 429 (1/min limit) |
| test_rate_limit_per_user | AUTH-06 | User A limited after 2 reqs; User B first req still succeeds |

### backend/app/core/limiter.py (Rule 1 fix)

`_get_chat_rate_limit` signature changed from `(request: Request) -> str` to `() -> str`. Root cause: slowapi's `LimitGroup.__iter__` calls the limit provider with zero arguments when the parameter name is not `key`. The previous signature caused a TypeError at request time.

---

## Decisions Made

- **`_get_chat_rate_limit` zero-arg signature**: slowapi inspects `inspect.signature(limit_provider).parameters` and only passes the key_func result if a `key` parameter exists. No `key` param → called with no args. The function reads settings via `get_settings()` which doesn't require the request object.
- **Patch target is `backend.app.core.limiter.get_settings`**: slowapi's `LimitGroup` captures the function reference at decoration time (import time), not the module-level name. Patching the name in `chat.py` has no effect. Patching `get_settings` in `limiter.py` affects the actual execution path.
- **Mock settings must include `jwt_secret`**: `_get_rate_limit_key` also calls `get_settings()` to decode the JWT. Without `jwt_secret`, JWT decode fails and both users fall back to `ip:127.0.0.1`, sharing the same rate limit counter and making per-user isolation test impossible.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _get_chat_rate_limit signature incompatible with slowapi calling convention**
- **Found during:** Task 2 (test_rate_limit_returns_429 failed with TypeError)
- **Issue:** `_get_chat_rate_limit(request: Request)` requires one arg but slowapi calls it with zero args (since param name is not `key`)
- **Fix:** Removed `request: Request` parameter — function reads from `get_settings()` without needing the request
- **Files modified:** `backend/app/core/limiter.py`
- **Commit:** 18d6398

**2. [Rule 1 - Bug] Patch target for rate limit — module name vs captured reference**
- **Found during:** Task 2 (test_rate_limit_per_user — both users got ip:127.0.0.1 key)
- **Issue:** Patching `backend.app.api.chat._get_chat_rate_limit` doesn't work because slowapi captured the function reference at decoration time; patching `backend.app.core.limiter.get_settings` affects the actual execution path
- **Fix:** Changed patch target to `backend.app.core.limiter.get_settings` with a mock that includes both `rate_limit_per_minute=1` and `jwt_secret="a"*32`
- **Files modified:** `backend/app/tests/test_rate_limit.py`
- **Commit:** 18d6398

---

## Deferred Issues

Pre-existing test failure (not caused by Plan 04 changes, verified by `git stash` test):
- `backend/app/tests/test_rag_phase9.py::test_stream_answer_empty_string_filter_treated_as_falsy` — test asserts `query_filter is None` for empty string source_filter but rag.py passes the filter through. This was failing before Plan 04 execution.

---

## Threat Surface Scan

No new network endpoints or auth paths introduced. Test-only changes + one bug fix in `limiter.py` (signature change only, no behavioral change for production traffic).

Threat mitigations verified:
- **T-10-13** (hashed_password in response): `test_create_user` asserts `"hashed_password" not in data`; `test_list_users` asserts `"hashed_password" not in u` for all items.
- **T-10-14** (403 enforcement): `test_non_admin_forbidden` asserts `r.status_code == 403` and `r.json()["detail"] == "Admin access required"`.

---

## Known Stubs

None.

---

## Self-Check: PASSED

- [x] `backend/app/tests/conftest.py` contains `async def admin_client(db_engine):`
- [x] `backend/app/tests/conftest.py` contains `async def rate_limited_client(db_engine):`
- [x] `backend/app/tests/conftest.py` admin_client contains `Limiter(key_func=get_remote_address, enabled=False)`
- [x] `backend/app/tests/test_admin.py` exists and contains `test_create_user`
- [x] `backend/app/tests/test_rate_limit.py` exists and contains `test_rate_limit_returns_429`
- [x] Commit edbd5ba: `feat(10-04): add admin_client and rate_limited_client fixtures to conftest.py`
- [x] Commit 18d6398: `feat(10-04): write test_admin.py (AUTH-05/07) and test_rate_limit.py (AUTH-06)`
- [x] `pytest backend/app/tests/test_admin.py backend/app/tests/test_rate_limit.py -v` exits 0 (10/10 passed)
- [x] Pre-existing failure in test_rag_phase9.py confirmed as pre-existing (verified via git stash)

---
phase: 03-authentication
plan: 03
subsystem: api
tags: [fastapi, jwt, pyjwt, argon2, sqlalchemy, auth, chat, testing]

# Dependency graph
requires:
  - phase: 03-authentication
    plan: 01
    provides: "Wave 0 test stubs + db_session/auth_client fixtures"
  - phase: 03-authentication
    plan: 02
    provides: "DB layer (models/session) + auth service (hash, verify, JWT, get_current_user)"
provides:
  - backend/app/api/auth.py: POST /auth/login, /auth/refresh, /auth/logout router
  - backend/app/main.py: jwt_secret length guard, DB init, admin user seed, auth_router registration
  - backend/app/core/config.py: refresh_token_expire_days, admin_username, admin_password fields
  - backend/app/api/chat.py: Depends(get_current_user) active — all requests require Bearer token
  - backend/app/tests/test_auth.py: 10 real assertions (all PASS, zero skips)
affects: [04-frontend, auth, api, testing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Auth router uses JSON body (not OAuth2PasswordBearer form data) per D-05"
    - "Constant-timing login: verify_password called even for unknown usernames (T-03-03-01)"
    - "Stateless logout: POST /auth/logout returns 200 {} — client drops tokens (D-08)"
    - "test_chat_with_valid_token mocks rag.stream_answer to isolate auth layer from Qdrant"
    - "test_chat_endpoint.py uses dependency_overrides[get_current_user] after chat protection added"
    - "_init_db_and_seed uses Path.mkdir(parents=True) to create backend/data/ directory"

key-files:
  created:
    - backend/app/api/auth.py
  modified:
    - backend/app/core/config.py
    - backend/app/main.py
    - backend/app/api/chat.py
    - backend/app/tests/test_auth.py
    - backend/app/tests/test_chat_endpoint.py
    - .env.example

key-decisions:
  - "JWT secret guard in lifespan raises ValueError if len(jwt_secret) < 32 — server refuses to start (AUTH-05)"
  - "_init_db_and_seed called from lifespan before telemetry/OpenRouter/Qdrant setup — DB ready before first request"
  - "test_chat_with_valid_token uses patch.object(rag_module, 'stream_answer') — auth assertion isolated from Qdrant"
  - "test_chat_endpoint.py fixed with dependency_overrides[get_current_user] — preserves RAG-05/T-02-02 semantics"

patterns-established:
  - "Auth router pattern: LoginRequest/TokenResponse Pydantic models + SQLAlchemy query in endpoint body"
  - "Chat auth regression fix: dependency_overrides[get_current_user] in Phase 2 chat tests"
  - "Integration test pattern: login first to get real token, then test protected endpoint"

requirements-completed: [AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05]

# Metrics
duration: 8min
completed: 2026-04-26
---

# Phase 3 Plan 03: Auth Router, Chat Protection, and 10 Green Tests Summary

**FastAPI auth router (login/refresh/logout) + JWT-protected chat endpoint + all 10 auth tests green (zero skips)**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-26T16:45:00Z
- **Completed:** 2026-04-26T16:53:00Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Extended `Settings` with `refresh_token_expire_days`, `admin_username`, `admin_password` fields
- Added `_init_db_and_seed()` to lifespan: creates `backend/data/` directory, calls `init_db()`, creates tables idempotently, seeds admin user from env vars if set
- Added jwt_secret length guard (`len < 32` raises `ValueError`) as first lifespan operation (AUTH-05)
- Registered `auth_router` at prefix `/auth` in `create_app()`
- Created `backend/app/api/auth.py` with `POST /auth/login`, `/auth/refresh`, `/auth/logout` — JSON-body login (D-05), constant-timing credential check (T-03-03-01), stateless logout (D-08)
- Activated `Depends(get_current_user)` in `chat_endpoint` — all unauthenticated requests return 401
- Replaced all 10 Wave 0 pytestmark stubs with real assertions — all 10 PASS
- Fixed `test_chat_endpoint.py` regression caused by adding auth to chat endpoint

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend config.py + wire lifespan + update .env.example** — `b5b67a3` (feat)
2. **Task 2: Create backend/app/api/auth.py router** — `fef8ea0` (feat)
3. **Task 3: Protect chat + replace 10 test stubs** — `90252e9` (feat)

## Files Created/Modified

- `backend/app/api/auth.py` — New auth router: LoginRequest/TokenResponse models, POST /login (verifies credentials, returns both tokens), POST /refresh (validates refresh token type, returns new access token), POST /logout (stateless 200 {})
- `backend/app/core/config.py` — Added `refresh_token_expire_days: int = 7`, `admin_username: str | None = None`, `admin_password: str | None = None`
- `backend/app/main.py` — Added `_init_db_and_seed()` helper, jwt_secret length guard, DB init call, auth_router registration; added Path/sqlalchemy/auth imports
- `backend/app/api/chat.py` — Uncommented `Depends(get_current_user)` in `chat_endpoint`; added `get_current_user` and `User` imports
- `backend/app/tests/test_auth.py` — Replaced 10 pytestmark stubs with real assertions using `auth_client` and `db_session` fixtures; added `_seed_user()` helper; added jwt/datetime imports
- `backend/app/tests/test_chat_endpoint.py` — Added `get_current_user` import and `_stub_current_user` override; applied `dependency_overrides[get_current_user]` in both tests (regression fix)
- `.env.example` — Added `ADMIN_USERNAME` and `ADMIN_PASSWORD` entries with instructional comments

## Decisions Made

- `_init_db_and_seed` called as first async operation in lifespan (before telemetry/OpenRouter): ensures DB is ready before any request arrives, and validates jwt_secret length before expensive external calls.
- `test_chat_with_valid_token` uses `patch.object(rag_module, 'stream_answer', _mock_stream)`: auth check (`Depends(get_current_user)`) runs before endpoint body, so mocking the RAG layer is sufficient to isolate the auth assertion from needing a running Qdrant instance.
- `test_chat_endpoint.py` fixed with `dependency_overrides[get_current_user] = _stub_current_user`: Phase 2 RAG/HTTP tests test the RAG layer, not auth — overriding the auth dependency preserves their original semantics.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_chat_with_valid_token needed rag.stream_answer mock**
- **Found during:** Task 3 — first test run (9/10 passing)
- **Issue:** `test_chat_with_valid_token` sent a real request to `/api/chat` after auth passed. The endpoint called `rag.stream_answer` which attempted to connect to Qdrant (not running in test env), raising `ResponseHandlingException` — test runner reported as FAILED rather than a clean HTTP response.
- **Fix:** Added `patch.object(rag_module, 'stream_answer', _mock_stream)` inside the test body to yield a minimal done event, isolating the auth assertion from the RAG layer.
- **Files modified:** `backend/app/tests/test_auth.py`
- **Commit:** `90252e9`

**2. [Rule 1 - Bug] test_chat_endpoint.py regression after chat endpoint protection**
- **Found during:** Task 3 — full suite run after Task 3 commit
- **Issue:** `test_endpoint_content_type` and `test_system_role_rejected` in `test_chat_endpoint.py` called `/api/chat` without auth. After activating `Depends(get_current_user)`, the dependency tried to call `get_db()` — which asserted `_session_factory is not None` — but `init_db()` was never called (no lifespan in the test). Result: `AssertionError: init_db() must be called before get_db()`.
- **Fix:** Added `_stub_current_user` helper returning a dummy User; applied `app.dependency_overrides[get_current_user] = _stub_current_user` in both Phase 2 tests with `try/finally` to ensure cleanup.
- **Files modified:** `backend/app/tests/test_chat_endpoint.py`
- **Commit:** `90252e9`

## Known Stubs

None — all test stubs replaced. No placeholder data paths or hardcoded empty values in production code.

## Threat Flags

None — all new surface was accounted for in the plan's `<threat_model>`. The auth router endpoints (T-03-03-01 through T-03-03-08) are fully mitigated as designed.

---
*Phase: 03-authentication*
*Completed: 2026-04-26*

## Self-Check: PASSED

- FOUND: backend/app/api/auth.py
- FOUND: backend/app/core/config.py (refresh_token_expire_days present)
- FOUND: backend/app/main.py (_init_db_and_seed present)
- FOUND: backend/app/api/chat.py (Depends(get_current_user) active)
- FOUND: backend/app/tests/test_auth.py (10 real assertions, no pytestmark skip)
- FOUND: backend/app/tests/test_chat_endpoint.py (get_current_user override present)
- FOUND: .env.example (ADMIN_USERNAME/ADMIN_PASSWORD present)
- FOUND: commit b5b67a3 (Task 1 — feat: config + lifespan)
- FOUND: commit fef8ea0 (Task 2 — feat: auth router)
- FOUND: commit 90252e9 (Task 3 — feat: chat protection + tests)
- VERIFIED: 10/10 auth tests PASS, 22/22 full suite PASS

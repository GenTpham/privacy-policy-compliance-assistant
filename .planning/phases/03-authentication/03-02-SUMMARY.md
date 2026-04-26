---
phase: 03-authentication
plan: 02
subsystem: database
tags: [sqlalchemy, asyncio, sqlite, aiosqlite, jwt, pyjwt, pwdlib, argon2, fastapi, auth]

# Dependency graph
requires:
  - phase: 03-authentication
    plan: 01
    provides: "Wave 0 test stubs in test_auth.py + db_session/auth_client fixtures in conftest.py"
provides:
  - backend/app/db/ package: Base + User SQLAlchemy 2.0 declarative model, init_db() + get_db() async generator
  - backend/app/services/auth.py: JWT create/decode (PyJWT 2.12.1), password hash/verify (pwdlib Argon2id), get_current_user FastAPI dependency
affects: [03-03, auth, database, api]

# Tech tracking
tech-stack:
  added: [sqlalchemy[asyncio] 2.0.49, aiosqlite 0.22.1, PyJWT 2.12.1, pwdlib[argon2] 0.3.0]
  patterns:
    - "Module-level None sentinel for AsyncEngine — init_db() called from lifespan only, never at import time"
    - "PasswordHash.recommended() singleton — Argon2id with OWASP parameters, module-level"
    - "HTTPBearer(auto_error=False) — raises own 401 with WWW-Authenticate header, not FastAPI default 403"
    - "decode_token catches jwt.InvalidTokenError (base class) — never a single subclass"
    - "payload['type'] claim distinguishes access from refresh tokens — cross-use raises HTTP 401"

key-files:
  created:
    - backend/app/db/__init__.py
    - backend/app/db/models.py
    - backend/app/db/session.py
    - backend/app/services/auth.py
  modified: []

key-decisions:
  - "AsyncEngine created only inside init_db() — never at module import time (Research Pitfall 3: blocks test isolation)"
  - "HTTPBearer(auto_error=False) used instead of OAuth2PasswordBearer — D-05 requires JSON login body, not form data"
  - "Argon2id via PasswordHash.recommended() singleton — per-request instantiation would re-tune params (slow)"
  - "jwt.InvalidTokenError caught as base class — covers ExpiredSignatureError, DecodeError, InvalidSignatureError in one catch"
  - "payload['type'] cross-use prevention — decode_token(expected_type='access') raises 401 on refresh tokens (T-03-02-03)"

patterns-established:
  - "DB layer module pattern: _engine/_session_factory as None sentinels, init_db() call from lifespan"
  - "Auth service module pattern: all primitives in one file (hash, verify, encode, decode, dependency)"
  - "FastAPI dependency chain: get_current_user → get_db → init_db (lifespan owns the root)"

requirements-completed: [AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05]

# Metrics
duration: 2min
completed: 2026-04-26
---

# Phase 3 Plan 02: Database Layer and Authentication Service Summary

**SQLAlchemy 2.0 async User model + session factory (init_db/get_db) and full auth service with PyJWT 2.12.1 + Argon2id password hashing + get_current_user FastAPI dependency**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-26T16:33:21Z
- **Completed:** 2026-04-26T16:35:44Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `backend/app/db/` package with `Base`/`User` SQLAlchemy 2.0 declarative model (id, username, hashed_password, created_at) and `init_db()`/`get_db()` async session factory using module-level None sentinel pattern
- Created `backend/app/services/auth.py` with `hash_password` (Argon2id), `verify_password` (timing-safe), `create_access_token`, `create_refresh_token`, `decode_token` (cross-use prevention via type claim), and `get_current_user` FastAPI dependency
- All 10 Wave 0 auth test stubs continue to skip cleanly (10 skipped, exit code 0 — foundation ready for Plan 03)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create backend/app/db/ package (models.py + session.py)** - `3bb6e62` (feat)
2. **Task 2: Create backend/app/services/auth.py** - `0ff13db` (feat)

## Files Created/Modified

- `backend/app/db/__init__.py` — Package marker for SQLAlchemy async database layer
- `backend/app/db/models.py` — User SQLAlchemy 2.0 declarative model with Mapped columns; Base class for create_all
- `backend/app/db/session.py` — `init_db(db_url)` + `get_db()` async generator; module-level None sentinel prevents import-time engine creation
- `backend/app/services/auth.py` — Full auth service: JWT create/decode (PyJWT), Argon2id hash/verify (pwdlib), `get_current_user` FastAPI dependency

## Decisions Made

- Module-level None sentinel for `_engine` and `_session_factory` in session.py — engine created only when `init_db()` is called from lifespan, never at import time. This is essential for test isolation (conftest.py `db_session` fixture uses an in-memory SQLite engine via `dependency_overrides`).
- `HTTPBearer(auto_error=False)` instead of `OAuth2PasswordBearer` — Plan 03 login endpoint accepts a JSON body (D-05), not HTML form data. The bearer extractor raises our own HTTP 401 with `WWW-Authenticate: Bearer` header.
- `PasswordHash.recommended()` as a module-level singleton — avoids re-tuning Argon2 memory/iteration parameters on every request.
- `jwt.InvalidTokenError` caught as base class in `decode_token` — this is the superclass for `ExpiredSignatureError`, `DecodeError`, and `InvalidSignatureError`. Catching only a subclass would leave other failure modes unhandled.

## Deviations from Plan

None — plan executed exactly as written. All verified patterns from RESEARCH.md and the `<interfaces>` block were implemented verbatim.

## Issues Encountered

None — all imports resolved immediately. Python environment had PyJWT 2.12.1, pwdlib 0.3.0, SQLAlchemy 2.0.49, and aiosqlite 0.22.1 pre-installed from project venv.

## User Setup Required

None — no external service configuration required. All files are pure Python; no DB file is created until `init_db()` is called from the lifespan (Plan 03).

## Next Phase Readiness

- Plan 03 (auth router + main.py wiring) can now import from `backend.app.db.models`, `backend.app.db.session`, and `backend.app.services.auth`
- `conftest.py` `db_session` fixture is unblocked: `from backend.app.db.models import Base` now resolves
- `conftest.py` `auth_client` fixture is unblocked: `from backend.app.db.session import get_db` now resolves
- All 10 Wave 0 test stubs in `test_auth.py` will be activated in Plan 03 when `pytestmark` skip is removed

---
*Phase: 03-authentication*
*Completed: 2026-04-26*

## Self-Check: PASSED

- FOUND: backend/app/db/__init__.py
- FOUND: backend/app/db/models.py
- FOUND: backend/app/db/session.py
- FOUND: backend/app/services/auth.py
- FOUND: commit 3bb6e62 (Task 1 — feat: db/ package)
- FOUND: commit 0ff13db (Task 2 — feat: services/auth.py)

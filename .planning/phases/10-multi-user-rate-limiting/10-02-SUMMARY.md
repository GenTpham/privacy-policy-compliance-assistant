---
phase: "10"
plan: "02"
subsystem: backend/auth+admin-api
tags: [admin-router, startup-migration, is_admin, jwt, sqlite-alter-table]
dependency_graph:
  requires:
    - backend/app/core/limiter.py (Plan 01)
    - User.is_admin column model (Plan 01)
    - require_admin dependency (Plan 01)
    - create_access_token with is_admin param (Plan 01)
  provides:
    - POST /admin/users (create user, admin-gated)
    - GET /admin/users (list users, admin-gated)
    - DELETE /admin/users/{username} (delete user, admin-gated)
    - _migrate_add_is_admin_column startup function
    - _patch_admin_is_admin startup function
    - Login JWT now embeds is_admin claim
  affects:
    - backend/app/main.py
    - backend/app/api/auth.py
    - backend/app/api/admin.py
tech_stack:
  added: []
  patterns:
    - PRAGMA table_info check before ALTER TABLE (SQLite idempotent migration)
    - Admin-gated CRUD with require_admin Depends on every endpoint
    - UserResponse excludes hashed_password (safe projection pattern)
key_files:
  created:
    - backend/app/api/admin.py
  modified:
    - backend/app/main.py
    - backend/app/api/auth.py
decisions:
  - D-02: SQLite ALTER TABLE migration via PRAGMA table_info check — no IF NOT EXISTS in SQLite
  - D-03: _patch_admin_is_admin runs after migration ensuring column exists before UPDATE
  - D-04: is_admin=user.is_admin passed to create_access_token in login endpoint
metrics:
  duration: "3m"
  completed_date: "2026-05-13"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 10 Plan 02: Startup Migrations, Admin Router, and Login is_admin Claim Summary

**One-liner:** Wired Wave 1 contracts into the live app — startup migrations add is_admin column and patch admin role, login embeds is_admin in JWT, and the admin router exposes POST/GET/DELETE /admin/users behind require_admin.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add startup migration functions and wire limiter + admin router in main.py | 46d30f0 | backend/app/main.py |
| 2 | Update api/auth.py login to pass is_admin and create api/admin.py | 4c3c55a | backend/app/api/auth.py, backend/app/api/admin.py (new) |

---

## What Was Built

### backend/app/main.py
Three additions:

1. **New imports:** `_rate_limit_exceeded_handler`, `RateLimitExceeded` from slowapi; `admin_router` from `backend.app.api.admin`; `limiter` from `backend.app.core.limiter`.

2. **`_migrate_add_is_admin_column(engine)`** — Idempotent startup function that checks `PRAGMA table_info(users)` before issuing `ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0`. Safe on every restart; skips if column already exists.

3. **`_patch_admin_is_admin(settings, session_factory)`** — Sets `is_admin=True` on the seeded admin user via SQLAlchemy `UPDATE`. Idempotent — applying the same value repeatedly is safe. Runs after the migration so the column is guaranteed to exist.

4. **Lifespan update** — calls `_migrate_add_is_admin_column` then `_patch_admin_is_admin` immediately after `_init_db_and_seed`.

5. **`create_app` update** — wires `app.state.limiter = limiter` and `app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)`, then registers `admin_router` at `/admin` prefix.

### backend/app/api/auth.py
Login endpoint now passes `is_admin=user.is_admin` to `create_access_token` (D-04). Access tokens issued after this change carry the `is_admin` claim, enabling stateless admin enforcement via `require_admin`.

### backend/app/api/admin.py (NEW)
Full admin user management router with three endpoints:

- **POST /admin/users** → 201 `UserResponse` on success, 409 on duplicate username
- **GET /admin/users** → `list[UserResponse]` ordered by id
- **DELETE /admin/users/{username}** → 204 on success, 404 when not found

All endpoints use `_admin: dict = Depends(require_admin)` — HTTP 401 for unauthenticated requests, HTTP 403 for non-admin tokens. `UserResponse` never includes `hashed_password` (T-10-07 mitigated).

---

## Decisions Made

- **D-02 (SQLite migration):** PRAGMA table_info + conditional ALTER TABLE — SQLite has no `ADD COLUMN IF NOT EXISTS` syntax.
- **D-03 (patch order):** `_patch_admin_is_admin` called strictly after `_migrate_add_is_admin_column` so the column is guaranteed before the UPDATE runs.
- **D-04 (JWT is_admin):** Login passes `is_admin=user.is_admin` — tokens issued after first deployment carry the correct claim; admin must re-login after the `_patch_admin_is_admin` runs on first startup (documented Pitfall 3 in RESEARCH.md).

---

## Deviations from Plan

None — plan executed exactly as written. Both tasks completed in order with all acceptance criteria met.

---

## Threat Surface Scan

Threat mitigations verified in implementation:

- **T-10-05** (Spoofing — require_admin JWT claim): `require_admin` calls `decode_token` which verifies HS256 signature before reading `is_admin` — forged tokens are rejected.
- **T-10-06** (Tampering — missing password validation): `CreateUserRequest.password: str` rejects empty body at Pydantic level; `hash_password` (Argon2id) applied before DB storage.
- **T-10-07** (Info Disclosure — hashed_password): `UserResponse` explicitly declares only `id`, `username`, `is_admin`, `created_at` — `hashed_password` cannot appear in any response.
- **T-10-08** (Elevation of Privilege): `require_admin` dependency is present on all three admin endpoints — checked before handler body executes.
- **T-10-09** (Stale is_admin JWT): Accepted per D-04 and Pitfall 3 — admin must re-login after first deployment to get a token with `is_admin=True`.

---

## Known Stubs

None — all endpoints are fully implemented with real DB operations.

---

## Self-Check: PASSED

- [x] `backend/app/api/admin.py` — created and verified
- [x] `backend/app/api/auth.py` contains `is_admin=user.is_admin` (grep count: 1)
- [x] `backend/app/api/admin.py` contains 3x `Depends(require_admin)` (grep count: 3)
- [x] `backend/app/main.py` contains `_migrate_add_is_admin_column`, `_patch_admin_is_admin`, `PRAGMA table_info(users)`, `ALTER TABLE users ADD COLUMN is_admin`, `app.state.limiter`, `RateLimitExceeded`, `admin_router`
- [x] `python -c "from backend.app.main import create_app; app = create_app(); ..."` exits 0 with admin route found
- [x] `python -c "from backend.app.api.admin import router, CreateUserRequest, UserResponse; print('ok')"` exits 0
- [x] `python -c "from backend.app.api.auth import login; print('ok')"` exits 0
- [x] Commits: 46d30f0, 4c3c55a

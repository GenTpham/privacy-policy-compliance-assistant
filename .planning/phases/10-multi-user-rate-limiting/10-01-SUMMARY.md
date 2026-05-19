---
phase: "10"
plan: "01"
subsystem: backend/auth+rate-limiting
tags: [slowapi, is_admin, jwt, rate-limiting, foundation]
dependency_graph:
  requires: []
  provides:
    - User.is_admin column (DB model)
    - Settings.rate_limit_per_minute config
    - backend/app/core/limiter.py (Limiter singleton)
    - create_access_token with is_admin claim
    - require_admin FastAPI dependency
  affects:
    - backend/app/services/auth.py
    - backend/app/db/models.py
    - backend/app/core/config.py
tech_stack:
  added:
    - slowapi==0.1.9 (per-user rate limiting for FastAPI)
  patterns:
    - Standalone limiter module to break circular import (chat.py <-> main.py)
    - Stateless is_admin check via JWT payload (D-04, no DB re-query)
    - Username-based rate limit key with IP fallback (D-09)
key_files:
  created:
    - backend/app/core/limiter.py
  modified:
    - requirements.txt
    - backend/app/db/models.py
    - backend/app/core/config.py
    - backend/app/services/auth.py
decisions:
  - D-01: is_admin bool column on User model — binary role, no extensibility needed
  - D-04: is_admin embedded in JWT access token payload — stateless admin check, no DB re-query per request
  - D-05: slowapi Limiter with custom key_func
  - D-06: MemoryStorage (default) — resets on container restart, acceptable for single-instance
  - D-08: rate_limit_per_minute=60 in Settings, overridable via RATE_LIMIT_PER_MINUTE env var
  - D-09: Rate limit key is authenticated username from JWT; falls back to client IP on decode failure
metrics:
  duration: "2m"
  completed_date: "2026-05-13"
  tasks_completed: 3
  tasks_total: 3
---

# Phase 10 Plan 01: Foundation Contracts — is_admin, Limiter, require_admin Summary

**One-liner:** Wave 1 foundation — slowapi Limiter singleton, User.is_admin column, JWT is_admin claim, and require_admin dependency enabling Wave 2 parallel work on admin router and chat rate limiting.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add slowapi, User.is_admin, rate_limit_per_minute | 11d11de | requirements.txt, models.py, config.py |
| 2 | Create standalone limiter module | 2c3987f | backend/app/core/limiter.py (new) |
| 3 | Add is_admin JWT claim and require_admin dependency | 18f6a49 | backend/app/services/auth.py |

---

## What Was Built

### requirements.txt
Added `slowapi==0.1.9` — FastAPI-native wrapper around the `limits` library for per-user rate limiting.

### backend/app/db/models.py
Added `is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)` column to the `User` model. On fresh DBs this column is created by SQLAlchemy's `create_all`; on existing DBs the `_migrate_add_is_admin_column` helper in `main.py` (Wave 2) adds it via `ALTER TABLE`.

### backend/app/core/config.py
Added `rate_limit_per_minute: int = 60` to `Settings`. Overridable via `RATE_LIMIT_PER_MINUTE` env var with no code changes required.

### backend/app/core/limiter.py (NEW)
Standalone module containing:
- `_get_rate_limit_key(request)` — extracts `user:<username>` from JWT Bearer header; falls back to `ip:<host>` on any decode error
- `_get_chat_rate_limit(request)` — returns dynamic limit string `"N/minute"` from settings
- `limiter = Limiter(key_func=_get_rate_limit_key)` — module-level singleton

Extracted here (not in `main.py`) to break the circular import: `chat.py` → `limiter` → `main.py` → `chat_router` → `chat.py`.

### backend/app/services/auth.py
Two modifications:
1. `create_access_token` now accepts `is_admin: bool = False` and embeds `"is_admin": is_admin` in the JWT payload
2. New `require_admin` dependency: raises HTTP 401 if unauthenticated, HTTP 403 if `is_admin` claim is False or absent — no DB query

---

## Decisions Made

- **D-04 (stateless admin):** `is_admin` read from JWT payload in `require_admin`, not from DB. Consistent with stateless JWT design; `require_admin` is O(1) — just JWT decode + dict lookup.
- **D-05 (slowapi):** Decorator-based `@limiter.limit(...)` — minimal boilerplate over raw middleware.
- **D-06 (MemoryStorage):** In-memory counters reset on container restart. Redis not added — no HA requirement.
- **D-08 (configurable limit):** `rate_limit_per_minute` in Settings — env var override without code change.
- **D-09 (username key):** `user:<sub>` from JWT; `ip:<host>` fallback. key_func runs before `get_current_user` DI resolution, so fallback is mandatory for defensive correctness.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] slowapi not installed in current Python environment**
- **Found during:** Task 2 verification
- **Issue:** `python -m pip install slowapi==0.1.9` needed — verification command `from slowapi import Limiter` failed
- **Fix:** Ran `python -m pip install slowapi==0.1.9` to install into active Python
- **Impact:** None on committed files; installation is transient dev environment setup

---

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes at trust boundaries beyond those already captured in the plan's threat model (T-10-01 through T-10-04).

Threat mitigations verified in implementation:
- **T-10-01** (Spoofing — is_admin claim): `require_admin` calls `decode_token` which verifies HS256 signature before reading the claim. Forged tokens are rejected.
- **T-10-02** (Tampering — DEFAULT value): `nullable=False, default=False` at SQLAlchemy level; ALTER TABLE migration (Wave 2) uses `NOT NULL DEFAULT 0`.
- **T-10-03** (DoS — key_func exception): `_get_rate_limit_key` wraps decode in `except Exception: pass`, always returns a key string, never raises.
- **T-10-04** (Info disclosure — is_admin in JWT): Accepted risk — JWT is signed not encrypted; is_admin bool is low-sensitivity role indicator.

---

## Known Stubs

None — this plan establishes data contracts (column, config field, module, dependency). No UI rendering or data flow stubs.

---

## Self-Check: PASSED

- [x] `backend/app/core/limiter.py` — created and verified
- [x] `requirements.txt` contains `slowapi==0.1.9`
- [x] `backend/app/db/models.py` contains `is_admin` column
- [x] `backend/app/core/config.py` contains `rate_limit_per_minute`
- [x] `backend/app/services/auth.py` contains `require_admin` and updated `create_access_token`
- [x] All imports resolve: `python -c "from backend.app.db.models import User; from backend.app.core.config import Settings; from backend.app.core.limiter import limiter; from backend.app.services.auth import require_admin; print('all imports ok')"`
- [x] Commits: 11d11de, 2c3987f, 18f6a49

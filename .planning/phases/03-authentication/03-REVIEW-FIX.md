---
phase: 03-authentication
fixed_at: 2026-04-27T00:00:00Z
review_path: .planning/phases/03-authentication/03-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 03: Code Review Fix Report

**Fixed at:** 2026-04-27
**Source review:** .planning/phases/03-authentication/03-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: Timing-attack mitigation bypassed when user not found

**Files modified:** `backend/app/services/auth.py`, `backend/app/api/auth.py`
**Commit:** 7338a5f
**Applied fix:** Added module-level `_DUMMY_HASH: str = _password_hasher.hash("__dummy__")` sentinel to `services/auth.py`. In `api/auth.py`, imported `_DUMMY_HASH` and replaced the conditional `if stored_hash` guard with unconditional `verify_password` call: `stored_hash = user.hashed_password if user is not None else _DUMMY_HASH` followed by `password_valid = verify_password(body.password, stored_hash)`. Argon2id cost is now always paid regardless of whether the username exists.

### WR-01: jwt_secret length guard not enforced at Settings construction

**Files modified:** `backend/app/core/config.py`
**Commit:** 5d18828
**Applied fix:** Added `from pydantic import field_validator` import and a `@field_validator("jwt_secret") @classmethod def jwt_secret_length(cls, v)` method to `Settings` that raises `ValueError` if `len(v) < 32`. The guard now fires at `Settings()` construction time on every process start, not only when the full lifespan runs. The existing lifespan check in `main.py` was left in place for defense-in-depth.

### WR-02: db_session fixture has no explicit rollback on teardown

**Files modified:** `backend/app/tests/conftest.py`
**Commit:** d1cd6d1
**Applied fix:** As part of the WR-03 restructure, the `db_session` fixture body was wrapped in `try/finally` with `await session.rollback()` in the `finally` block, ensuring no pending transaction remains at teardown even if a test raises.

### WR-03: auth_client shares the same session object with the test

**Files modified:** `backend/app/tests/conftest.py`
**Commit:** d1cd6d1
**Applied fix:** Introduced a new `db_engine` function-scoped fixture that creates and disposes the in-memory SQLite engine (with table creation). `db_session` and `auth_client` both take `db_engine` as their dependency and each create an independent `async_sessionmaker` — the test-side session and the HTTP override session are now separate objects sharing only the engine. `_override_get_db` now opens a fresh session per request via `async with factory() as session: yield session`.

### WR-04: test_short_jwt_secret_rejected tests a re-implementation, not the real guard

**Files modified:** `backend/app/tests/test_auth.py`
**Commit:** 5d18828
**Applied fix:** Replaced the manually constructed `ValueError` with a direct `Settings(openrouter_api_key="any-key", jwt_secret="short")` call inside `pytest.raises(ValidationError, match="32")`. The test now exercises the actual `field_validator` in `Settings` rather than replicating the logic inline.

---

_Fixed: 2026-04-27_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_

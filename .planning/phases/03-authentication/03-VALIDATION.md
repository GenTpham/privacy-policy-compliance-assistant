---
phase: 3
slug: authentication
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-25
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pytest.ini or pyproject.toml (existing) |
| **Quick run command** | `pytest backend/tests/test_auth.py -x -q` |
| **Full suite command** | `pytest backend/tests/ -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/tests/test_auth.py -x -q`
- **After every plan wave:** Run `pytest backend/tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 1 | AUTH-01 | — | SQLite users table created at startup | unit | `pytest backend/tests/test_auth.py::test_db_init -xq` | ❌ W0 | ⬜ pending |
| 3-01-02 | 01 | 1 | AUTH-02 | — | Password stored as Argon2 hash, not plaintext | unit | `pytest backend/tests/test_auth.py::test_password_hash -xq` | ❌ W0 | ⬜ pending |
| 3-02-01 | 02 | 1 | AUTH-03 | — | POST /auth/login returns access+refresh tokens | integration | `pytest backend/tests/test_auth.py::test_login -xq` | ❌ W0 | ⬜ pending |
| 3-02-02 | 02 | 1 | AUTH-04 | — | /chat without JWT returns HTTP 401 | integration | `pytest backend/tests/test_auth.py::test_protected_no_token -xq` | ❌ W0 | ⬜ pending |
| 3-03-01 | 03 | 2 | AUTH-05 | — | /auth/refresh returns new access token | integration | `pytest backend/tests/test_auth.py::test_refresh -xq` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_auth.py` — stubs for AUTH-01 through AUTH-05
- [ ] `backend/tests/conftest.py` — in-memory SQLite session fixture via dependency_overrides

*Existing pytest infrastructure is present; Wave 0 adds auth-specific test stubs and fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| No plaintext passwords in users.db | AUTH-02 | Requires direct DB inspection | `sqlite3 backend/data/users.db "SELECT password_hash FROM users"` — confirm value starts with `$argon2` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

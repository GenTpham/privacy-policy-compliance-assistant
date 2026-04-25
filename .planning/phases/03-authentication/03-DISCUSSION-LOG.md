# Phase 3: Authentication — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 03-authentication
**Areas discussed:** User provisioning, Refresh token design, Login endpoint format, Logout semantics

---

## User Provisioning

| Option | Description | Selected |
|--------|-------------|----------|
| ENV-var seed | ADMIN_USERNAME + ADMIN_PASSWORD in .env; backend seeds user at startup if absent | ✓ |
| Standalone seed script | One-shot script, manual step required | |
| Closed /register endpoint | POST /auth/register, disables after first user | |

**User's choice:** ENV-var seed (Recommended)
**Notes:** Single user only — v1 is single-user gated access, no multi-user JSON array needed.

---

## Refresh Token Design

| Option | Description | Selected |
|--------|-------------|----------|
| Stateless JWT refresh | Long-lived JWT, no DB table, not individually revocable | ✓ |
| DB-backed opaque token | Random token in SQLite, fully revocable, adds DB lookup | |

**Expiry chosen:** 7 days (Recommended)
**User's choice:** Stateless JWT refresh, 7-day expiry

---

## Login Endpoint Format

| Option | Description | Selected |
|--------|-------------|----------|
| JSON body | POST /auth/login with JSON {"username", "password"}; consistent with /chat convention | ✓ |
| OAuth2 form body | FastAPI standard form-encoded fields; enables /docs Authorize button | |

**Response shape chosen:** `{access_token, refresh_token, token_type}` (both tokens on login)
**User's choice:** JSON body with full token response

---

## Logout Semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Client-side only | Server returns 200, client drops tokens; consistent with stateless JWT | ✓ |
| Server-side token blacklist | SQLite JTI blacklist, revocable, adds lookup on every request | |

**User's choice:** Client-side only

---

## Claude's Discretion

- Exact Pydantic model field names beyond what was decided
- HTTP error message wording
- SQLAlchemy model column types and indexes

## Deferred Ideas

None — discussion stayed within phase scope.

# Phase 10: Multi-user & Rate Limiting - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-13
**Phase:** 10-Multi-user-and-Rate-Limiting
**Areas discussed:** Role model design, Rate limiting approach

---

## Role Model Design

### Q1: Role field modeling

| Option | Description | Selected |
|--------|-------------|----------|
| `is_admin: bool` | Single boolean column; simple, direct; existing rows default to False | ✓ |
| `role: str` enum | String enum ("admin"/"user"); extensible for future roles | |
| You decide | Let planner pick | |

**User's choice:** `is_admin: bool`
**Notes:** Phase only needs two tiers; boolean is simpler and sufficient.

---

### Q2: Migration strategy for existing table

| Option | Description | Selected |
|--------|-------------|----------|
| ALTER TABLE at startup | Idempotent column add; non-destructive; existing rows default False | ✓ |
| Drop & recreate | Clean slate; destroys existing user data | |
| You decide | Let planner determine safest path | |

**User's choice:** ALTER TABLE at startup
**Notes:** Must also patch the seeded admin user to `is_admin=True` in the same migration step.

---

### Q3: Role in JWT payload

| Option | Description | Selected |
|--------|-------------|----------|
| Include `is_admin` in JWT | No extra DB query on admin checks; consistent with stateless JWT (D-03) | ✓ |
| Always read from DB | Authoritative; role revocation instant; extra DB cost per request | |
| You decide | Let planner pick | |

**User's choice:** Include `is_admin` in JWT access token payload
**Notes:** Consistent with existing stateless JWT architecture.

---

## Rate Limiting Approach

### Q1: Library choice

| Option | Description | Selected |
|--------|-------------|----------|
| slowapi | FastAPI-native, decorator-based, minimal dep, no Redis required | ✓ |
| Custom in-memory middleware | Zero new deps; more code to maintain | |
| You decide | Let planner pick | |

**User's choice:** slowapi
**Notes:** Decorator-based approach integrates cleanly with FastAPI dependency pattern.

---

### Q2: Counter storage

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory (slowapi default) | Resets on restart; zero infrastructure change | ✓ |
| Redis | Persistent; adds redis service to Docker Compose | |

**User's choice:** In-memory
**Notes:** Single-instance deployment; no HA requirement; Redis overhead not justified.

---

### Q3: Default rate and config

| Option | Description | Selected |
|--------|-------------|----------|
| 10 req/min | Conservative; configurable via `RATE_LIMIT_PER_MINUTE` | |
| 20 req/min | Moderate; configurable via `RATE_LIMIT_PER_MINUTE` | |
| 60 req/min | Permissive (1/second); configurable via `RATE_LIMIT_PER_MINUTE` | ✓ |

**User's choice:** 60 requests/minute
**Notes:** Applied to `POST /api/chat` only. `RATE_LIMIT_PER_MINUTE` env var makes it configurable without code changes.

---

## Claude's Discretion

- Admin API path prefix (`/admin/users` vs `/api/admin/users`) — planner decides
- Password handling in user create endpoint — caller supplies password (planner confirms)
- Response schema for list/create — planner determines fields (id, username, is_admin, created_at); never return hashed_password

## Deferred Ideas

None — discussion stayed within phase scope.

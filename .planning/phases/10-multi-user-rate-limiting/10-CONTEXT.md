# Phase 10: Multi-user & Rate Limiting - Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Admin user management API (create, list, delete accounts via API) with role-based access control, plus per-user rate limiting on `POST /api/chat`.

No self-registration flow. Admins are created/managed exclusively via the admin API or the startup seed. A non-admin calling admin endpoints receives HTTP 403. A user exceeding the configured rate limit receives HTTP 429 with a clear message.

</domain>

<decisions>
## Implementation Decisions

### Role Model

- **D-01:** `is_admin: bool` column on the `User` model — binary, no extensibility needed for this phase. Existing rows default to `False`.
- **D-02:** Column migration via **ALTER TABLE at startup** — run `ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0 NOT NULL` idempotently in the lifespan (check if column exists first, skip if already present). Non-destructive; existing user rows survive.
- **D-03:** The seeded admin user (`admin_username` from Settings) is patched to `is_admin=True` during the startup migration, so the bootstrapped admin immediately has the right role.
- **D-04:** `is_admin` is **embedded in the JWT access token payload** at login — no extra DB query on admin-protected endpoints. Consistent with the existing stateless JWT design (D-03 global). A `require_admin` FastAPI dependency reads `is_admin` from the decoded token and raises HTTP 403 if False.

### Rate Limiting

- **D-05:** Use **slowapi** (FastAPI-native wrapper around the `limits` library) — decorator-based `@limiter.limit(...)` on the endpoint. Minimal boilerplate, no framework middleware needed.
- **D-06:** **In-memory storage** — slowapi's default `MemoryStorage`. Counters reset on container restart; acceptable for a single-instance deployment with no HA requirement. No Redis service added to Docker Compose.
- **D-07:** Default rate limit is **60 requests/minute** on `POST /api/chat` per authenticated user (username from JWT sub claim as the key).
- **D-08:** Configurable via `RATE_LIMIT_PER_MINUTE: int = 60` added to `Settings` in `config.py` — overridable via `RATE_LIMIT_PER_MINUTE` env var. No code change required per deployment.
- **D-09:** Rate limit key is the **authenticated username** (from JWT). Unauthenticated requests are already blocked by `get_current_user` before reaching the rate limiter — no IP fallback needed.

### Claude's Discretion

- Admin API path prefix: either `/admin/users` or `/api/admin/users` — planner should choose the cleanest prefix that keeps admin routes clearly separated from RAG/chat routes.
- Password handling for new users created via admin API: caller supplies the password in the request body (simplest; consistent with the existing login pattern).
- Response shape for user list and create endpoints: planner determines appropriate fields (id, username, is_admin, created_at); do NOT return hashed_password in any response.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Auth & User Model
- `backend/app/db/models.py` — current `User` model (id, username, hashed_password, created_at); D-01 adds `is_admin` here
- `backend/app/services/auth.py` — `get_current_user` dependency (base for `require_admin` wrapper); `create_access_token` (add `is_admin` to payload per D-04); anti-patterns listed in module docstring
- `backend/app/api/auth.py` — existing auth router (admin users router follows same structure); decisions D-05–D-08 documented here

### Configuration
- `backend/app/core/config.py` — `Settings` class; add `rate_limit_per_minute: int = 60` following existing pattern

### Startup / Migration
- `backend/app/main.py` — lifespan function; D-02 ALTER TABLE migration and D-03 admin user patch run here, after `_init_db_and_seed`

### Phase Requirements
- `.planning/ROADMAP.md` §Phase 10 — success criteria: create/list/delete users, HTTP 403 for non-admin, HTTP 429 on rate limit, configurable limit without code changes

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `get_current_user` dependency (`services/auth.py`) — `require_admin` wraps this: call `get_current_user`, then check `is_admin` from JWT payload (or from returned `User.is_admin` if reading from DB)
- `decode_token` (`services/auth.py`) — already extracts payload; D-04 just adds `is_admin` as a claim in `create_access_token`
- Auth router structure (`api/auth.py`) — new `admin.py` router follows the same APIRouter + Pydantic request/response model pattern
- `Settings` + `get_settings()` (`core/config.py`) — `rate_limit_per_minute` follows the same `field: type = default` pattern with env var override

### Established Patterns
- `Depends(get_current_user)` on every protected endpoint — admin endpoints add a second layer `Depends(require_admin)` on top
- Module-level docstring with decision references (D-XX) — new files must follow this convention
- `_session_factory()` async context manager for DB access in lifespan (already used in `_init_db_and_seed`)
- `asyncio_mode=auto` + function-scoped fixtures in tests — rate limiting tests must follow existing test patterns in `conftest.py`

### Integration Points
- `backend/app/main.py` `lifespan()` — ALTER TABLE migration runs here; `create_app()` includes new admin router
- `backend/app/api/chat.py` `POST /api/chat` — slowapi `@limiter.limit(...)` decorator added here (D-05)
- `backend/app/services/auth.py` `create_access_token()` — `is_admin` payload claim added here (D-04)

</code_context>

<specifics>
## Specific Ideas

- SUCCESS CRITERIA are explicit: admin can create, list, and delete users; non-admin gets 403; rate limit returns 429 with a clear message; limit is env-var configurable.
- No update/patch user endpoint — only create, list, delete per success criteria.
- slowapi handles HTTP 429 automatically; the response body should include a human-readable `detail` message (slowapi default behavior covers this).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 10-Multi-user-and-Rate-Limiting*
*Context gathered: 2026-05-13*

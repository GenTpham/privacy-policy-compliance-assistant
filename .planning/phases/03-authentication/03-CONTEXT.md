# Phase 3: Authentication — Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement JWT-based authentication for all chat endpoints. Users log in with username/password, receive an access token (30 min) and a refresh token (7 days), and re-authenticate transparently using the refresh token. Unauthenticated requests to `/chat` receive HTTP 401. A single admin user is seeded from ENV vars at startup. Logout is client-side only — consistent with stateless JWT.

**Does NOT include:** User registration UI, social login, multi-user management, token blacklisting, or any frontend work (Phase 4).

</domain>

<decisions>
## Implementation Decisions

### User Provisioning
- **D-01:** Single user seeded from ENV vars at startup. `ADMIN_USERNAME` + `ADMIN_PASSWORD` in `.env` (added to `.env.example`). Backend creates the user during the FastAPI lifespan event if the user does not already exist — safe for re-starts, idempotent.
- **D-02:** Single user only — v1 is single-user gated access. No multi-user JSON array support.

### Refresh Token Design
- **D-03:** Stateless JWT refresh tokens — refresh token is a long-lived JWT signed with the same `jwt_secret`. No DB table required. Expiry: **7 days** (`refresh_token_expire_days: int = 7` added to `Settings`).
- **D-04:** Refresh token payload carries `sub` (username) and `type: "refresh"` — prevents a refresh token from being used as an access token and vice versa.

### Login Endpoint Format
- **D-05:** `POST /auth/login` accepts **JSON body** `{"username": str, "password": str}`. Consistent with the existing `/chat` endpoint convention; straightforward to call from React `fetch`.
- **D-06:** Successful login response: `{"access_token": str, "refresh_token": str, "token_type": "bearer"}`.
- **D-07:** `POST /auth/refresh` accepts JSON body `{"refresh_token": str}`, returns `{"access_token": str, "token_type": "bearer"}`.

### Logout Semantics
- **D-08:** `POST /auth/logout` is **client-side only** — server returns HTTP 200 with no body. Client drops both tokens from storage. No server state needed; consistent with the stateless JWT design in D-03.

### JWT Protection of Chat Endpoints
- **D-09:** `/api/chat` and any future protected routes use a FastAPI `Depends(get_current_user)` dependency that:
  1. Reads `Authorization: Bearer <token>` header
  2. Decodes and verifies the JWT (expiry, signature, `type: "access"`)
  3. Returns the user record on success, raises HTTP 401 on failure
- **D-10:** The dependency is designed to be injected into route functions without restructuring the router — the chat route already anticipated this (Phase 2 CONTEXT D-15 note).

### Database
- **D-11:** SQLite file at `backend/data/users.db` (created at startup if absent). Single `users` table: `{id, username, hashed_password, created_at}`. Tables created via raw SQLAlchemy DDL in the lifespan event — no Alembic migrations for v1.
- **D-12:** `AsyncEngine` + `aiosqlite` — async-first consistent with the rest of the stack. `AsyncSession` for all DB operations.

### JWT Secret Validation
- **D-13:** AUTH-05: at startup, validate `jwt_secret` is at minimum 32 characters. Raise `ValueError` with a clear message if too short — fail fast.

### Claude's Discretion
- Exact Pydantic request/response model field names (beyond what's decided above) — planner chooses.
- HTTP error messages (e.g. "Invalid credentials" vs "Incorrect username or password") — executor decides.
- SQLAlchemy model definition details (column types, indexes) — executor decides.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §Authentication (AUTH-01–05)

### Prior Phase Infrastructure
- `.planning/phases/01-infrastructure-data-ingestion/01-CONTEXT.md` — D-14: `get_settings()` singleton, `.env` loading pattern, `jwt_secret` already defined
- `.planning/phases/02-core-rag-pipeline/02-CONTEXT.md` — D-15, D-16: chat router structure; note that `/api/chat` is designed to accept `Depends(get_current_user)` without restructuring
- `backend/app/core/config.py` — existing `Settings` class; `jwt_secret`, `jwt_algorithm`, `access_token_expire_minutes` already present — add `refresh_token_expire_days`
- `backend/app/main.py` — existing lifespan pattern; seed user + DB table creation plugs in here
- `backend/app/api/chat.py` — route that needs `Depends(get_current_user)` added

### Stack Decisions
- `.planning/research/STACK.md` — PyJWT + pwdlib[argon2] versions confirmed

No external ADRs — all decisions captured above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/core/config.py` — `get_settings()` singleton already has `jwt_secret`, `jwt_algorithm = "HS256"`, `access_token_expire_minutes = 30`. Phase 3 adds `refresh_token_expire_days = 7` and `admin_username`/`admin_password` fields.
- `backend/app/main.py` — lifespan `asynccontextmanager` — DB init and user seed go here alongside the existing Qdrant bootstrap.
- `backend/app/api/chat.py` — chat router; `Depends(get_current_user)` injected here.

### Established Patterns
- `@lru_cache` + `get_settings()` singleton — all new config fields follow this pattern.
- Async-first: `AsyncEngine`, `AsyncSession`, `aiosqlite` — consistent with existing `AsyncQdrantClient` and `AsyncOpenAI` usage.
- Module structure: new code lives under `backend/app/api/auth.py` (router) and `backend/app/services/auth.py` (JWT logic) and `backend/app/db/` (SQLAlchemy models + session).

### Integration Points
- `backend/app/main.py` lifespan — add `async_engine` creation, `Base.metadata.create_all()`, user seed.
- `backend/app/api/chat.py` — add `current_user: User = Depends(get_current_user)` to the chat route.
- `backend/app/main.py` `create_app()` — register `auth_router` at prefix `/auth`.

</code_context>

<specifics>
## Specific Ideas

- `get_current_user` dependency: if `Authorization` header is missing or token is expired, raise `HTTPException(status_code=401, detail="...", headers={"WWW-Authenticate": "Bearer"})`.
- Refresh token type check: decode JWT, assert `payload["type"] == "refresh"` before issuing new access token — prevents access tokens from being used as refresh tokens.
- Startup seed: if `ADMIN_USERNAME` is not set in `.env`, skip seed silently (don't crash). Document in `.env.example` that it's required for first-time setup.
- SQLite file path `backend/data/users.db` — add `backend/data/` to `.gitignore`, not the directory itself (keep the directory).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-authentication*
*Context gathered: 2026-04-25*

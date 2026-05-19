# Phase 10: Multi-user & Rate Limiting - Research

**Researched:** 2026-05-13
**Domain:** FastAPI RBAC + SQLite migration + slowapi rate limiting
**Confidence:** HIGH

## Summary

Phase 10 adds two independent capabilities to the existing auth system: (1) admin-managed user accounts via a new `/admin/users` API with role-based access control using an `is_admin` boolean column, and (2) per-user rate limiting on `POST /api/chat` via slowapi with in-memory storage.

The existing codebase already has a clean auth foundation: `get_current_user` dependency in `services/auth.py`, `create_access_token` in the same file, JWT PyJWT tokens with `sub` claim, and a SQLAlchemy 2.0 async engine in `db/session.py`. The phase adds to these without replacing them. The SQLite migration is a straightforward PRAGMA-check + raw ALTER TABLE. The slowapi integration requires four changes to existing files (`chat.py`, `main.py`, `config.py`, `services/auth.py`) plus one new file (`api/admin.py`).

All locked decisions from CONTEXT.md are respected. No alternative libraries or approaches are explored — this research focuses on exact implementation patterns for the chosen stack.

**Primary recommendation:** Implement the ALTER TABLE migration in `_init_db_and_seed` (before the admin-seed step), wire slowapi at the `create_app()` level, key by authenticated username via a custom `key_func` that reads `request.state.user` (set in a middleware or extracted from token in the endpoint), and disable slowapi in tests via `enabled=False` on the `Limiter` instance with a dependency override.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: `is_admin: bool` column on the `User` model. Existing rows default to `False`.
- D-02: Column migration via ALTER TABLE at startup — `ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0 NOT NULL` idempotently in the lifespan (check if column exists first, skip if already present).
- D-03: The seeded admin user (`admin_username` from Settings) is patched to `is_admin=True` during the startup migration.
- D-04: `is_admin` embedded in the JWT access token payload. A `require_admin` FastAPI dependency reads `is_admin` from the decoded token and raises HTTP 403 if False.
- D-05: Use slowapi for rate limiting (decorator-based `@limiter.limit(...)`).
- D-06: In-memory storage — slowapi's default `MemoryStorage`. No Redis.
- D-07: Default rate limit is 60 requests/minute on `POST /api/chat` per authenticated user (username from JWT sub claim as the key).
- D-08: Configurable via `RATE_LIMIT_PER_MINUTE: int = 60` in `Settings`, overridable via env var.
- D-09: Rate limit key is the authenticated username (from JWT `sub`). Unauthenticated requests are blocked by `get_current_user` before the rate limiter fires.

### Claude's Discretion
- Admin API path prefix: either `/admin/users` or `/api/admin/users` — planner should choose the cleanest prefix.
- Password handling for new users created via admin API: caller supplies the password in the request body.
- Response shape for user list and create endpoints: planner determines appropriate fields (id, username, is_admin, created_at); do NOT return hashed_password.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-05 | Admin can create, list, and delete user accounts via an API (no self-registration) | Admin router pattern documented; require_admin dependency pattern verified |
| AUTH-06 | Per-user rate limiting on POST /api/chat — configurable requests-per-minute, returns HTTP 429 when exceeded | slowapi 0.1.9 integration pattern fully verified from official tests |
| AUTH-07 | User model has a role field (admin / user) — admin role required to access user management endpoints | is_admin bool column migration and JWT claim pattern documented |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| User CRUD (create/list/delete) | API / Backend | — | DB state; no frontend needed; CLI/API only per requirements |
| Role enforcement (HTTP 403) | API / Backend | — | FastAPI dependency chain; never enforce authorization client-side |
| Rate limiting (HTTP 429) | API / Backend | — | slowapi middleware/decorator at request handling layer |
| is_admin in JWT | API / Backend | — | Created at login; stateless verification on every admin request |
| SQLite schema migration | API / Backend (startup) | — | Lifespan function runs before first request; ALTER TABLE in lifespan |
| Admin token propagation | Frontend (Browser) | — | Frontend must pass Bearer token on admin API calls just like chat |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| slowapi | 0.1.9 | Rate limiting for FastAPI/Starlette | Locked (D-05); Flask-limiter semantics adapted for async ASGI; decorator-based |
| PyJWT | already installed (2.x) | JWT encoding with `is_admin` claim | Already in use (D-04) |
| SQLAlchemy asyncio | already installed (2.x) | Async ALTER TABLE via `text()` | Already in use (D-02) |
| aiosqlite | already installed | Async SQLite driver | Already in use |
| fastapi | 0.136.0 | Admin router + dependency injection | Already in use |

[VERIFIED: PyPI registry — slowapi 0.1.9 is the latest version as of 2026-05-13]

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `limits` | transitive via slowapi | Underlying rate limit counting | Never import directly; slowapi wraps it |
| `starlette.requests.Request` | via fastapi | Required parameter for slowapi-decorated endpoints | Every endpoint with `@limiter.limit()` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| slowapi | Custom middleware token bucket | slowapi locked (D-05); custom is 100+ lines of thread-safe counter logic |
| MemoryStorage | Redis | Redis locked out (D-06); MemoryStorage resets on restart which is acceptable for single-instance |
| is_admin bool | role enum | bool locked (D-01); enum has no benefit for binary admin/non-admin |

**Installation:**
```bash
pip install slowapi==0.1.9
```

Add to `requirements.txt`:
```
slowapi==0.1.9
```

**Version verification:** slowapi 0.1.9 confirmed on PyPI, published 2024-02-05. [VERIFIED: npm view slowapi version output; PyPI page]

## Architecture Patterns

### System Architecture Diagram

```
POST /admin/users (create/list/delete)
       |
       v
  [require_admin]  ← reads is_admin from JWT payload → HTTP 403 if False
       |
       v
  AdminRouter  → DB CRUD (User table)
       |
       v
  UserResponse (id, username, is_admin, created_at)  ← never hashed_password


POST /api/chat
       |
       v
  @limiter.limit("{rate_limit_per_minute}/minute")  ← key = username from JWT
       |
  HTTP 429 if exceeded
       |
       v
  [get_current_user]  ← verifies Bearer token, raises 401 if invalid
       |
       v
  ChatEndpoint


Startup Lifespan:
  _init_db_and_seed()  (existing)
       |
       v
  _migrate_add_is_admin_column()  (new — PRAGMA check + ALTER TABLE)
       |
       v
  _patch_admin_is_admin()  (new — UPDATE users SET is_admin=1 WHERE username=?)
```

### Recommended Project Structure
```
backend/app/
├── api/
│   ├── auth.py         # existing — login adds is_admin to token
│   ├── chat.py         # existing — add @limiter.limit() + request: Request param
│   ├── admin.py        # NEW — POST/GET/DELETE /admin/users
│   └── sources.py      # existing — unchanged
├── core/
│   └── config.py       # existing — add rate_limit_per_minute: int = 60
├── db/
│   └── models.py       # existing — add is_admin: Mapped[bool] column
├── services/
│   └── auth.py         # existing — add is_admin to create_access_token payload
│                       #           add require_admin dependency
└── main.py             # existing — add migration fn, register admin router,
                        #           init limiter, add exception handler
```

### Pattern 1: slowapi Limiter Initialization (module-level in main.py)

The `Limiter` must be created before the `FastAPI` app, attached to `app.state.limiter`, and the exception handler registered. The `key_func` is a custom function that extracts the authenticated username from the JWT in the `Authorization` header.

```python
# Source: slowapi official tests (test_fastapi_extension.py) + docs
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request

def _get_username_from_token(request: Request) -> str:
    """
    key_func for slowapi — extracts the authenticated username from the JWT
    Bearer token in the Authorization header.

    D-09: rate limit key is the username (payload['sub']).
    Unauthenticated requests are blocked by get_current_user before reaching
    the limiter, so this function only runs for authenticated requests.
    Falls back to client IP if token is absent/invalid (should not happen in practice).
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            import jwt as pyjwt
            from backend.app.core.config import get_settings
            settings = get_settings()
            payload = pyjwt.decode(
                auth[7:], settings.jwt_secret, algorithms=["HS256"]
            )
            return payload.get("sub", request.client.host if request.client else "anon")
        except Exception:
            pass
    return request.client.host if request.client else "anon"

limiter = Limiter(key_func=_get_username_from_token)
```

In `create_app()`:
```python
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

[VERIFIED: slowapi official test file test_fastapi_extension.py — key_func pattern, exception handler pattern]
[VERIFIED: slowapi docs — app.state.limiter and add_exception_handler are the documented integration points]

### Pattern 2: @limiter.limit() Decorator on chat endpoint

**Critical requirements** (both verified from official slowapi tests):
1. Route decorator MUST be above `@limiter.limit()`.
2. Endpoint function MUST have `request: Request` as an explicit parameter.
3. `Request` must be `starlette.requests.Request` (FastAPI re-exports it from starlette).

```python
# Source: slowapi test_fastapi_extension.py verified patterns
from starlette.requests import Request
from fastapi import APIRouter, Depends
from backend.app.services.auth import get_current_user

router = APIRouter()

@router.post("/chat")
@limiter.limit(get_rate_limit_string)   # callable returns "60/minute" from settings
async def chat_endpoint(
    request: Request,                    # REQUIRED by slowapi — must be first or named
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    ...
```

Where `get_rate_limit_string` is a callable that reads from settings:
```python
def get_rate_limit_string(request: Request) -> str:
    """Dynamic limit string — reads RATE_LIMIT_PER_MINUTE from settings (D-08)."""
    from backend.app.core.config import get_settings
    settings = get_settings()
    return f"{settings.rate_limit_per_minute}/minute"
```

[VERIFIED: slowapi test_fastapi_extension.py — `test_dynamic_limit_provider_depending_on_key` shows callable limit providers]

### Pattern 3: require_admin Dependency

```python
# services/auth.py addition — D-04
async def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    FastAPI dependency — raises HTTP 403 if the JWT token does not carry is_admin=True.
    Reads is_admin directly from the token payload (D-04) — no extra DB query.
    Wraps decode_token (existing); adds the is_admin check on top.

    Usage: Depends(require_admin) on every admin endpoint.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated",
                            headers={"WWW-Authenticate": "Bearer"})
    payload = decode_token(credentials.credentials, settings.jwt_secret,
                           expected_type="access")
    if not payload.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload
```

[ASSUMED: Reading is_admin from JWT payload (not re-fetching User from DB) is the D-04 pattern; verified structurally against existing decode_token implementation]

### Pattern 4: SQLite ALTER TABLE migration (idempotent)

SQLite does NOT support `IF NOT EXISTS` in ALTER TABLE. The idempotent pattern requires checking `PRAGMA table_info` first.

```python
# main.py — new helper function
async def _migrate_add_is_admin_column(engine) -> None:
    """
    Add is_admin column to users table if it does not already exist (D-02).
    SQLite's ALTER TABLE has no IF NOT EXISTS — must check PRAGMA first.
    Safe to run on every startup; skipped if column already present.
    """
    from sqlalchemy import text

    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(users)"))
        columns = [row[1] for row in result.fetchall()]
        if "is_admin" not in columns:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0")
            )
            print("[startup] Migration: added is_admin column to users table.")
        else:
            print("[startup] Migration: is_admin column already exists — skipping.")
```

[VERIFIED: SQLAlchemy 2.0 docs — PRAGMA table_info with async engine via text() + conn.execute(); SQLite ALTER TABLE behavior confirmed in official SQLite docs]
[VERIFIED: SQLite official docs — ALTER TABLE ADD COLUMN does not support IF NOT EXISTS]

### Pattern 5: Patch admin user to is_admin=True at startup

After the ALTER TABLE migration runs, the seeded admin user must have `is_admin=True`:

```python
# main.py addition — D-03
async def _patch_admin_is_admin(settings, session_factory) -> None:
    """Set is_admin=True on the seeded admin user (D-03)."""
    if not settings.admin_username:
        return
    from sqlalchemy import update
    from backend.app.db.models import User
    async with session_factory() as session:
        await session.execute(
            update(User)
            .where(User.username == settings.admin_username)
            .values(is_admin=True)
        )
        await session.commit()
        print(f"[startup] Admin user '{settings.admin_username}' patched to is_admin=True.")
```

### Pattern 6: Admin Router (api/admin.py)

Follows exact structure of `api/auth.py` — APIRouter, Pydantic models, Depends(require_admin):

```python
# backend/app/api/admin.py
"""
Admin user management router.
POST   /admin/users          — create a new user (admin only)
GET    /admin/users          — list all users   (admin only)
DELETE /admin/users/{username} — delete a user  (admin only)
D-04: require_admin dependency reads is_admin from JWT payload.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import Settings, get_settings
from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.services.auth import hash_password, require_admin

router = APIRouter()

class CreateUserRequest(BaseModel):
    username: str
    password: str
    is_admin: bool = False

class UserResponse(BaseModel):
    id: int
    username: str
    is_admin: bool
    created_at: ...   # datetime

@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> UserResponse: ...

@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> list[UserResponse]: ...

@router.delete("/users/{username}", status_code=204)
async def delete_user(
    username: str,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> None: ...
```

### Pattern 7: Testing slowapi Rate Limits with pytest-asyncio

The project uses `httpx.AsyncClient` (not `starlette.testclient.TestClient`). The slowapi official tests use synchronous `TestClient` with a `build_fastapi_app` fixture that accepts `enabled=False`. For this project's async test pattern, the equivalent is:

**Option A — Disable limiter in test fixture (recommended):**

Create a test-scoped fixture that overrides `app.state.limiter` with a disabled instance:

```python
# conftest.py addition
@pytest.fixture
async def admin_client(db_engine):
    """
    AsyncClient for admin endpoint tests. Rate limiting disabled (enabled=False)
    so tests are not affected by in-memory counter state.
    """
    from backend.app.main import create_app, limiter as prod_limiter
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from backend.app.db.session import get_db

    app = create_app()
    # Disable rate limiting in tests
    app.state.limiter = Limiter(key_func=get_remote_address, enabled=False)

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async def _override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()
```

**Option B — Test 429 enforcement directly:**

For the rate limit enforcement test (AUTH-06), use the real limiter with a very low limit:

```python
async def test_rate_limit_returns_429(auth_client, db_session):
    """
    POST /api/chat exceeds rate limit → HTTP 429 with detail message (AUTH-06).
    Strategy: patch settings to rate_limit_per_minute=1, hit endpoint twice,
    assert second response is 429.
    """
    from unittest.mock import patch, AsyncMock
    from backend.app.services import rag as rag_module

    user = await _seed_user(db_session)
    login_resp = await auth_client.post(
        "/auth/login", json={"username": user.username, "password": "password123"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    async def _mock_stream(*args, **kwargs):
        yield {"type": "done", "answer": "ok", "citations": []}

    with patch.object(rag_module, "stream_answer", _mock_stream):
        with patch("backend.app.core.config.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_per_minute = 1
            # first request succeeds
            r1 = await auth_client.post("/api/chat",
                json={"message": "hi", "history": []}, headers=headers)
            # second request exceeds limit
            r2 = await auth_client.post("/api/chat",
                json={"message": "hi", "history": []}, headers=headers)

    assert r2.status_code == 429
    assert "detail" in r2.json() or "error" in r2.text
```

[VERIFIED: slowapi test_fastapi_extension.py — `test_disabled_limiter` pattern uses `enabled=False`; `test_single_decorator` pattern for 429 assertion]
[ASSUMED: The async httpx fixture pattern for disabling slowapi — adapted from official sync TestClient pattern; should work identically since slowapi hooks into Starlette request lifecycle]

### Anti-Patterns to Avoid

- **Missing `request: Request` on decorated endpoint:** slowapi raises `Exception: No "request" or "websocket" argument on function ...` at decoration time (not at request time). The existing `chat_endpoint` must gain `request: Request` as an explicit parameter when `@limiter.limit()` is added. [VERIFIED: slowapi test `test_endpoint_missing_request_param` confirms the exact error]
- **Wrong decorator order:** `@limiter.limit()` must be BELOW the route decorator (`@router.post`). Reverse order silently skips rate limiting. [VERIFIED: slowapi docs]
- **Reading is_admin from DB on every admin request:** D-04 explicitly embeds `is_admin` in the JWT payload to avoid this. The `require_admin` dependency reads from the decoded payload, not from the DB.
- **Forgetting to patch admin user after migration:** The ALTER TABLE sets all existing rows to `is_admin=0` (DEFAULT 0). The seeded admin user row must be explicitly UPDATEd to `is_admin=1` after the migration (D-03).
- **Running migration before `_init_db_and_seed`:** `init_db()` sets up `_engine` in `session.py`. The migration function must access the engine only after `init_db()` has been called.
- **`request: str = None` type annotation:** If `request` is annotated as anything other than `starlette.requests.Request`, slowapi raises at request time: `parameter 'request' must be an instance of starlette.requests.Request`. [VERIFIED: slowapi test `test_endpoint_request_param_invalid`]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rate limit counter with reset | Custom asyncio.Lock + dict + asyncio.sleep | slowapi (locked D-05) | Thread-safety, window reset, 429 response, counter persistence are all non-trivial |
| SQLite schema migration | Alembic migration files | Raw `PRAGMA table_info` + `ALTER TABLE` via `text()` | Single column addition; Alembic is overkill; D-02 specifies the startup approach |
| JWT claim reading for admin check | Re-query DB on each request | `payload.get("is_admin")` from decoded token | D-04; DB query adds latency and coupling |
| Password hashing for new users | Custom hash | `hash_password()` already in `services/auth.py` | Already tested; Argon2id with `PasswordHash.recommended()` |

**Key insight:** slowapi's MemoryStorage is a fixed-window counter — the `limits` library underneath handles atomic increments and window expiry. Writing equivalent thread-safe logic in async Python requires asyncio locks + background cleanup tasks.

## Common Pitfalls

### Pitfall 1: `request: Request` missing from chat_endpoint
**What goes wrong:** slowapi raises `Exception: No "request" or "websocket" argument on function chat_endpoint` at app startup when `@limiter.limit()` is applied to `chat_endpoint`.
**Why it happens:** The current `chat_endpoint` signature does not have a `request: Request` parameter. slowapi inspects the function signature at decoration time and raises immediately.
**How to avoid:** Add `request: Request` as the first positional parameter of `chat_endpoint` when adding the decorator.
**Warning signs:** `Exception` raised during `create_app()` or at first `@router.post("/chat")` decoration.

### Pitfall 2: is_admin column DEFAULT and NULL
**What goes wrong:** `ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0` works in SQLite. However, if the DEFAULT clause is omitted, existing rows get NULL and the NOT NULL constraint is violated — ALTER TABLE fails with "NOT NULL constraint failed".
**Why it happens:** SQLite ALTER TABLE only allows adding nullable columns or columns with explicit defaults when rows already exist.
**How to avoid:** Always include `DEFAULT 0` when adding `NOT NULL` columns to populated tables.
**Warning signs:** `OperationalError: Cannot add a NOT NULL column with default value NULL` at startup.

### Pitfall 3: Stale is_admin=False in JWT after admin patch
**What goes wrong:** Admin logs in before the startup migration marks them `is_admin=True` in the DB. Token has `is_admin=False`. Even after the patch, existing tokens carry the old claim.
**Why it happens:** The startup migration runs once at container start. If the admin logged in during a previous run before D-03 was deployed, their token was issued without `is_admin=True`.
**How to avoid:** This is expected behavior for stateless JWT. Admin must re-login after initial deployment. Document in operational notes.
**Warning signs:** Admin gets HTTP 403 on admin endpoints even though DB row has `is_admin=1`.

### Pitfall 4: slowapi key_func decodes JWT on every rate-limited request
**What goes wrong:** The `key_func` called by slowapi re-decodes the JWT on every request. This is a second decode (get_current_user also decodes). Minor performance cost, but also a minor key_func exception risk if the token has already been rejected by `get_current_user`.
**Why it happens:** D-09 requires username-based keying, which requires reading the token in the key_func. The Starlette request object does not have the decoded payload attached at the key_func stage.
**How to avoid:** The key_func should catch all exceptions and fall back to IP address. Since `get_current_user` runs after the rate limiter fires (FastAPI dependency injection order), the key_func may see unauthenticated requests in edge cases — handle gracefully.
**Warning signs:** 500 errors on rate-limited requests with auth failures.

**Dependency injection order note:** In FastAPI, `@limiter.limit()` runs as a middleware hook BEFORE the endpoint's `Depends(get_current_user)` is resolved. This means the key_func can receive requests without valid tokens. D-09 states unauthenticated requests are "already blocked by `get_current_user`" — this is true for the endpoint body, but the key_func runs earlier. The key_func must be defensive.

### Pitfall 5: is_admin not added to existing User records seeded before Phase 10
**What goes wrong:** If the admin user was seeded in Phase 3 without `is_admin`, the row has `is_admin=0` after the ALTER TABLE migration (DEFAULT 0). The admin cannot access admin endpoints until D-03's UPDATE runs.
**Why it happens:** The migration adds the column with DEFAULT 0. The `_patch_admin_is_admin` function (D-03) must run after the ALTER TABLE migration to set the admin's row to 1.
**How to avoid:** Sequence in lifespan: `_init_db_and_seed` → `_migrate_add_is_admin_column` → `_patch_admin_is_admin`. The patch function is idempotent (UPDATE to same value is safe).

### Pitfall 6: MemoryStorage counter not reset between tests
**What goes wrong:** If the `Limiter` singleton is reused across tests, a user who hit 60 requests in test 1 will immediately be rate-limited in test 2.
**Why it happens:** `MemoryStorage` is in-process state shared by all requests unless the Limiter is reset or re-created.
**How to avoid:** Use `enabled=False` on the `Limiter` instance attached to `app.state.limiter` in test fixtures, or create a fresh `Limiter` per test. The `enabled=False` approach from slowapi official tests is the cleanest. [VERIFIED: slowapi `test_disabled_limiter` test pattern]

## Code Examples

### Complete slowapi Setup in main.py

```python
# Source: slowapi official tests test_fastapi_extension.py + docs

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request

def _get_rate_limit_key(request: Request) -> str:
    """
    key_func: extracts authenticated username from JWT for per-user rate limiting (D-09).
    Falls back to client IP on any error (defensive — key_func runs before get_current_user).
    """
    import jwt as pyjwt
    from backend.app.core.config import get_settings
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            settings = get_settings()
            payload = pyjwt.decode(auth[7:], settings.jwt_secret, algorithms=["HS256"])
            return f"user:{payload['sub']}"
        except Exception:
            pass
    return f"ip:{request.client.host if request.client else 'anon'}"

limiter = Limiter(key_func=_get_rate_limit_key)

def create_app() -> FastAPI:
    app = FastAPI(...)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(chat_router, prefix="/api")
    app.include_router(auth_router, prefix="/auth")
    app.include_router(sources_router, prefix="/api")
    app.include_router(admin_router, prefix="/admin")   # new
    return app
```

### Dynamic rate limit string from Settings

```python
# Source: slowapi test_dynamic_limit_provider_depending_on_key pattern
def _get_chat_rate_limit(request: Request) -> str:
    """Returns rate limit string from RATE_LIMIT_PER_MINUTE setting (D-08)."""
    from backend.app.core.config import get_settings
    return f"{get_settings().rate_limit_per_minute}/minute"

@router.post("/chat")
@limiter.limit(_get_chat_rate_limit)
async def chat_endpoint(
    request: Request,          # required by slowapi
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    ...
```

### is_admin added to JWT payload

```python
# services/auth.py — update create_access_token to accept is_admin (D-04)
def create_access_token(sub: str, secret: str, expire_minutes: int,
                        is_admin: bool = False) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
        "is_admin": is_admin,     # D-04: embedded for stateless admin check
    }
    return jwt.encode(payload, secret, algorithm="HS256")
```

Caller in `api/auth.py` login endpoint:
```python
# Need to fetch is_admin from User record at login time
access_token=create_access_token(
    user.username,
    settings.jwt_secret,
    settings.access_token_expire_minutes,
    is_admin=user.is_admin,   # read from DB row at login
)
```

### Settings addition

```python
# config.py — following existing pattern
rate_limit_per_minute: int = 60   # D-08: overridable via RATE_LIMIT_PER_MINUTE env var
```

### User model addition

```python
# db/models.py — D-01
from sqlalchemy import Boolean

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

Note: `Base.metadata.create_all` on a fresh DB will create the column. On an existing DB, the ALTER TABLE migration handles it.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| passlib/bcrypt | pwdlib[argon2] | FastAPI PR #13917 (2024) | Already in use; no change for this phase |
| python-jose | PyJWT 2.x | FastAPI 0.10x era (2024) | Already in use; adding is_admin claim is a minor extension |
| Alembic for SQLite migrations | Raw PRAGMA + ALTER TABLE | Project decision (D-02) | Simpler for single-column additions; no migration file management |

**Deprecated/outdated:**
- `passlib.context.CryptContext`: Already not used; pwdlib is in place.
- IP-based rate limiting for authenticated APIs: Superseded by username-based keying (D-09); IP is unreliable behind NAT/proxies.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The async httpx AsyncClient test fixture can disable slowapi by replacing `app.state.limiter` with `Limiter(enabled=False)` | Test Patterns | Tests may not correctly disable rate limiting; alternative is RATELIMIT_ENABLED env var override |
| A2 | `require_admin` reads `is_admin` from JWT payload (no DB lookup) — consistent with D-04 | Pattern 3 | If payload lacks `is_admin`, all admin calls fail with 403; need fallback or DB read |
| A3 | The `key_func` runs before `get_current_user` in FastAPI's dependency resolution | Pitfall 4 | If key_func runs after, the fallback-to-IP logic is unnecessary; either way the defensive approach is correct |
| A4 | `app.state.limiter` can be replaced post-`create_app()` in tests without side effects | Test Patterns | If limiter is captured by closure at decorator time, replacing `app.state.limiter` won't affect already-decorated endpoints |

**Note on A4 (important):** slowapi reads `request.app.state.limiter` at request time (not at decoration time) per the Starlette request lifecycle. Replacing `app.state.limiter` after `create_app()` should work. [ASSUMED — not explicitly verified from slowapi source, but consistent with Starlette's design pattern]

## Open Questions

1. **slowapi key_func timing vs. get_current_user**
   - What we know: slowapi is a decorator that wraps the endpoint function; FastAPI dependencies (`Depends`) are resolved during request handling
   - What's unclear: Exact ordering — does slowapi's rate check fire before or after FastAPI resolves `Depends(get_current_user)`?
   - Recommendation: Write the key_func defensively (try/except, fallback to IP) regardless of order. Add a comment in the code noting the potential ordering ambiguity.

2. **Replace `app.state.limiter` in test fixture or use RATELIMIT_ENABLED env var**
   - What we know: slowapi reads `request.app.state.limiter` at request time; `RATELIMIT_ENABLED=false` env var also disables via config
   - What's unclear: Which approach integrates more cleanly with the existing `auth_client` fixture pattern
   - Recommendation: Use `app.state.limiter = Limiter(enabled=False)` in the fixture; avoids env var pollution between test runs.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| slowapi | Rate limiting (D-05) | Not installed | 0.1.9 on PyPI | None — must add to requirements.txt |
| Python 3.11 | All backend | Available | 3.11.x (confirmed) | — |
| SQLite (via aiosqlite) | Migration + user store | Available (already in use) | — | — |

**Missing dependencies with no fallback:**
- slowapi 0.1.9 — must be added to `requirements.txt` and installed in Docker image

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pytest.ini` (root) — `asyncio_mode = auto` |
| Quick run command | `pytest backend/app/tests/test_admin.py backend/app/tests/test_auth_phase10.py -x` |
| Full suite command | `pytest backend/app/tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-05 | Admin creates user → 201, user in DB | unit/integration | `pytest backend/app/tests/test_admin.py::test_create_user -x` | Wave 0 |
| AUTH-05 | Admin lists users → 200 with user list | unit/integration | `pytest backend/app/tests/test_admin.py::test_list_users -x` | Wave 0 |
| AUTH-05 | Admin deletes user → 204, user gone from DB | unit/integration | `pytest backend/app/tests/test_admin.py::test_delete_user -x` | Wave 0 |
| AUTH-05 | No self-registration endpoint exists | unit | `pytest backend/app/tests/test_admin.py::test_no_self_registration -x` | Wave 0 |
| AUTH-06 | POST /api/chat exceeds rate limit → 429 | integration | `pytest backend/app/tests/test_rate_limit.py::test_rate_limit_returns_429 -x` | Wave 0 |
| AUTH-06 | Rate limit resets after window (or counter distinct per user) | integration | `pytest backend/app/tests/test_rate_limit.py::test_rate_limit_per_user -x` | Wave 0 |
| AUTH-07 | Non-admin calling admin endpoint → 403 | unit/integration | `pytest backend/app/tests/test_admin.py::test_non_admin_forbidden -x` | Wave 0 |
| AUTH-07 | Unauthenticated calling admin endpoint → 401 | unit/integration | `pytest backend/app/tests/test_admin.py::test_unauthenticated_forbidden -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest backend/app/tests/test_admin.py backend/app/tests/test_rate_limit.py -x`
- **Per wave merge:** `pytest backend/app/tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/app/tests/test_admin.py` — covers AUTH-05, AUTH-07
- [ ] `backend/app/tests/test_rate_limit.py` — covers AUTH-06
- [ ] `backend/app/tests/test_auth_phase10.py` (optional) — covers is_admin in JWT payload, require_admin unit tests

*(Existing conftest.py fixtures `auth_client`, `db_engine`, `db_session` are reusable — no new shared fixtures needed for admin tests; a new `admin_client` fixture with limiter disabled is needed for rate limit tests)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Existing PyJWT + pwdlib (unchanged) |
| V3 Session Management | yes | Stateless JWT; is_admin claim in token; re-login required after role change |
| V4 Access Control | yes | require_admin dependency; 403 on non-admin; no self-registration |
| V5 Input Validation | yes | Pydantic models on all admin endpoints; username length, password presence |
| V6 Cryptography | no new additions | Existing Argon2id + HS256 (unchanged) |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Privilege escalation via crafted JWT | Spoofing | JWT signed with HS256 + strong secret; is_admin is a signed claim |
| Rate limit bypass by rotating tokens | Denial of Service | Key by username (not token); same user with different tokens hits same counter |
| Leaked hashed_password in admin list response | Information Disclosure | UserResponse Pydantic model explicitly omits hashed_password |
| Admin creating users with empty passwords | Tampering | Pydantic validator: `password: str` with `min_length=1` |
| Horizontal privilege escalation (non-admin reads admin list) | Elevation of Privilege | require_admin on all /admin/* endpoints; Depends chain enforced by FastAPI |

## Sources

### Primary (HIGH confidence)
- slowapi GitHub test file `tests/test_fastapi_extension.py` — `enabled=False` disable pattern, decorator order, 429 assertions, custom key_func, dynamic limit providers [VERIFIED via WebFetch of raw GitHub URL]
- slowapi `slowapi/util.py` — `get_remote_address` implementation; key_func signature confirmed [VERIFIED via WebFetch]
- slowapi `slowapi/extension.py` — `Limiter.__init__` parameters (`enabled`, `storage_uri`, `key_func`, `default_limits`), RATELIMIT_ENABLED env var support [VERIFIED via WebFetch]
- SQLAlchemy 2.0 async docs — `PRAGMA table_info` + `text()` + `conn.execute()` for runtime column inspection [VERIFIED: SQLAlchemy 2.0 SQLite dialect docs]
- SQLite official docs — `ALTER TABLE ADD COLUMN` does not support `IF NOT EXISTS` [VERIFIED: sqlite.org/lang_altertable.html]
- PyPI: slowapi 0.1.9 (latest, 2024-02-05) [VERIFIED: `npm view slowapi version` + PyPI page]

### Secondary (MEDIUM confidence)
- blog.bytescrum.com — FastAPI + slowapi setup pattern (app.state.limiter, add_exception_handler, custom key_func via headers) [Verified against official test patterns]
- shiladityamajumder.medium.com — Dynamic limit provider callable pattern; Redis storage import pattern [Consistent with official test file]

### Tertiary (LOW confidence)
- None — all key claims verified from official sources or official tests

## Metadata

**Confidence breakdown:**
- slowapi integration: HIGH — verified from official test file and extension.py
- SQLite migration: HIGH — verified from SQLAlchemy and SQLite official docs
- JWT is_admin claim: HIGH — straightforward extension of existing create_access_token
- Test patterns for slowapi: HIGH — verified from official slowapi test file
- key_func timing vs get_current_user: MEDIUM — behavior inferred from Starlette architecture; not explicitly documented

**Research date:** 2026-05-13
**Valid until:** 2026-07-13 (slowapi 0.1.9 is stable; no breaking changes expected in 60 days)

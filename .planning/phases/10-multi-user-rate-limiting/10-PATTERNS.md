# Phase 10: Multi-user & Rate Limiting - Pattern Map

**Mapped:** 2026-05-13
**Files analyzed:** 7 new/modified files
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/db/models.py` | model | CRUD | `backend/app/db/models.py` (self) | exact — add column |
| `backend/app/core/config.py` | config | request-response | `backend/app/core/config.py` (self) | exact — add field |
| `backend/app/services/auth.py` | service | request-response | `backend/app/services/auth.py` (self) | exact — add function + modify existing |
| `backend/app/api/admin.py` | controller | CRUD | `backend/app/api/auth.py` | role-match |
| `backend/app/api/chat.py` | controller | streaming | `backend/app/api/chat.py` (self) | exact — add decorator + param |
| `backend/app/main.py` | config | request-response | `backend/app/main.py` (self) | exact — add startup fns + router |
| `backend/app/tests/test_admin.py` | test | request-response | `backend/app/tests/test_auth.py` | exact |
| `backend/app/tests/test_rate_limit.py` | test | request-response | `backend/app/tests/test_auth.py` | role-match |

---

## Pattern Assignments

### `backend/app/db/models.py` (model, CRUD)

**Analog:** self — existing `User` class

**Current model definition** (lines 17-27):
```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
```

**Imports to extend** (lines 1-10) — add `Boolean` to the `sqlalchemy` import:
```python
from sqlalchemy import Boolean, DateTime, String
```

**New column to add** (after `created_at`, following existing `Mapped[type]` = `mapped_column(...)` pattern):
```python
is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

**Docstring update** — extend the module docstring to reference D-01:
```
Single table: users (id, username, hashed_password, created_at, is_admin).
D-01: is_admin bool column — existing rows default to False via ALTER TABLE migration.
```

Note: `Base.metadata.create_all` on a fresh DB will include `is_admin`. On an existing DB, `_migrate_add_is_admin_column` in `main.py` adds it via ALTER TABLE (D-02).

---

### `backend/app/core/config.py` (config, request-response)

**Analog:** self — existing `Settings` class

**Existing field pattern** (lines 46-51) — follow exact `field: type = value  # comment` style:
```python
score_threshold: float = 0.20  # calibrated; was 0.25
```

**New field to add** after `score_threshold`, following identical style:
```python
rate_limit_per_minute: int = 60  # D-08: overridable via RATE_LIMIT_PER_MINUTE env var
```

No import changes needed. `model_config` (line 53) already enables env var overrides.

---

### `backend/app/services/auth.py` (service, request-response)

**Analog:** self — existing `get_current_user` and `create_access_token`

**Existing imports pattern** (lines 19-28) — `require_admin` needs no new imports beyond what exists; `_bearer` is already module-level:
```python
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from backend.app.core.config import Settings, get_settings
```

**create_access_token modification** (lines 54-66) — add `is_admin: bool = False` parameter and embed in payload (D-04):
```python
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

**require_admin dependency** — new function, add after `get_current_user` (line 161). Mirrors the structure of `get_current_user` (lines 126-160) exactly: same `_bearer` reuse, same `decode_token` call, same `HTTPException` raising pattern:
```python
async def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    FastAPI dependency — raises HTTP 403 if the JWT token does not carry is_admin=True.
    D-04: reads is_admin from token payload (no DB query).
    Usage: _admin: dict = Depends(require_admin) on every admin endpoint.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials, settings.jwt_secret,
                           expected_type="access")
    if not payload.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return payload
```

**Docstring update** — add to module anti-patterns list:
```
  - Never re-query DB in require_admin — read is_admin from JWT payload (D-04).
```

---

### `backend/app/api/admin.py` (controller, CRUD) — NEW FILE

**Analog:** `backend/app/api/auth.py` (entire file is the template)

**File docstring pattern** (auth.py lines 1-13) — follow identical multi-line docstring with `Decisions:` and `Anti-patterns avoided:` sections:
```python
"""
backend/app/api/admin.py
Admin user management router: POST /admin/users, GET /admin/users,
DELETE /admin/users/{username}.

Decisions:
  D-04: require_admin dependency reads is_admin from JWT payload — no DB re-query.
  AUTH-05: no self-registration endpoint — all user creation is admin-gated.

Anti-patterns avoided:
  - Never return hashed_password in any response model.
  - Never allow unauthenticated or non-admin access — require_admin on every endpoint.
"""
```

**Imports pattern** (auth.py lines 15-29) — follow same grouping (stdlib, fastapi, pydantic, sqlalchemy, local):
```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import Settings, get_settings
from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.services.auth import hash_password, require_admin
```

**router instantiation** (auth.py line 31) — identical:
```python
router = APIRouter()
```

**Pydantic models pattern** (auth.py lines 34-56) — follow same `class XRequest(BaseModel)` / `class XResponse(BaseModel)` grouping under `# ── Pydantic models ──` header:
```python
# ── Pydantic models ─────────────────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    username: str
    password: str
    is_admin: bool = False


class UserResponse(BaseModel):
    id: int
    username: str
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}
```

**Endpoint pattern** (auth.py lines 61-97) — follow same `@router.post(...)` / `async def fn(body, db, settings) -> ResponseModel` signature. `_admin: dict = Depends(require_admin)` is the second Depends layer, mirroring how auth.py uses `db: AsyncSession = Depends(get_db)`:
```python
# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> UserResponse:
    """POST /admin/users — create a new user account (admin only, AUTH-05)."""
    result = await db.execute(select(User).where(User.username == body.username))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )
    user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        is_admin=body.is_admin,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> list[UserResponse]:
    """GET /admin/users — list all user accounts (admin only, AUTH-05)."""
    result = await db.execute(select(User).order_by(User.id))
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.delete("/users/{username}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    username: str,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> None:
    """DELETE /admin/users/{username} — remove a user account (admin only, AUTH-05)."""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    await db.execute(delete(User).where(User.username == username))
    await db.commit()
```

---

### `backend/app/api/chat.py` (controller, streaming)

**Analog:** self — existing `chat_endpoint`

**Existing endpoint signature** (lines 78-82) — the `request` parameter name `request` is currently used for the Pydantic body. The slowapi `Request` must be a separate `starlette.requests.Request` parameter. Rename the body parameter to `body` and add `request: Request` as the first param:
```python
# Current (lines 78-82):
@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
```

**Required transformation** — rename body param and inject slowapi `Request`:
```python
# After modification:
from starlette.requests import Request
from backend.app.main import limiter  # imported at module level to avoid circular import

def _get_chat_rate_limit(request: Request) -> str:
    """Returns rate limit string from RATE_LIMIT_PER_MINUTE setting (D-08)."""
    from backend.app.core.config import get_settings
    return f"{get_settings().rate_limit_per_minute}/minute"

@router.post("/chat")
@limiter.limit(_get_chat_rate_limit)
async def chat_endpoint(
    request: Request,              # REQUIRED by slowapi — must be starlette.requests.Request
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
```

**Critical anti-pattern** (from RESEARCH.md): `@router.post("/chat")` MUST be above `@limiter.limit(...)`. Wrong order silently skips rate limiting.

**Body reference update** — all `request.message`, `request.history`, `request.source_filter` inside the function body change to `body.message`, `body.history`, `body.source_filter`.

---

### `backend/app/main.py` (config, request-response)

**Analog:** self — existing `_init_db_and_seed`, `lifespan`, `create_app`

**New helper function pattern** — follows the existing `_init_db_and_seed` pattern (lines 28-66): async function, accepts engine/settings, docstring with decision references, `print("[startup] ...")` log lines, raw `sqlalchemy.text()` for SQL:

```python
async def _migrate_add_is_admin_column(engine) -> None:
    """
    Add is_admin column to users table if not already present (D-02).
    SQLite ALTER TABLE has no IF NOT EXISTS — must check PRAGMA table_info first.
    Safe to call on every startup; skipped if column exists.
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


async def _patch_admin_is_admin(settings, session_factory) -> None:
    """Set is_admin=True on the seeded admin user (D-03)."""
    if not settings.admin_username:
        return
    from sqlalchemy import update

    async with session_factory() as session:
        await session.execute(
            update(User)
            .where(User.username == settings.admin_username)
            .values(is_admin=True)
        )
        await session.commit()
        print(f"[startup] Admin user '{settings.admin_username}' patched to is_admin=True.")
```

**Limiter instantiation pattern** — add at module level, BEFORE `create_app()` (mirrors the existing `COLLECTION_NAME = "policies"` constant at the top):
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request

def _get_rate_limit_key(request: Request) -> str:
    """
    key_func: extracts authenticated username from JWT for per-user rate limiting (D-09).
    Falls back to client IP on any error — key_func runs before get_current_user.
    """
    import jwt as pyjwt
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
```

**lifespan update** (lines 109-151) — add migration calls after `_init_db_and_seed`, before telemetry setup. Follow existing sequential `await` call pattern:
```python
# After _init_db_and_seed:
from backend.app.db import session as db_session_mod
await _migrate_add_is_admin_column(db_session_mod._engine)
from backend.app.db.session import _session_factory
await _patch_admin_is_admin(settings, _session_factory)
```

**create_app update** (lines 155-165) — add `limiter` to app state, register exception handler, include admin router. Follow existing `app.include_router(...)` pattern:
```python
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

**New import to add at top of file:**
```python
from backend.app.api.admin import router as admin_router
```

**Circular import risk:** `chat.py` imports `limiter` from `main.py`; `main.py` imports `chat_router` from `chat.py`. To break this, define `limiter` in a dedicated module (e.g., `backend/app/core/limiter.py`) and import it in both `main.py` and `chat.py`.

---

### `backend/app/api/auth.py` — login endpoint modification

**Analog:** self — lines 61-97

**login endpoint update** — pass `is_admin=user.is_admin` to `create_access_token` (D-04). Change lines 90-97:
```python
# Before:
return TokenResponse(
    access_token=create_access_token(
        user.username, settings.jwt_secret, settings.access_token_expire_minutes
    ),
    ...
)

# After (D-04 — embed is_admin in access token):
return TokenResponse(
    access_token=create_access_token(
        user.username,
        settings.jwt_secret,
        settings.access_token_expire_minutes,
        is_admin=user.is_admin,
    ),
    ...
)
```

---

### `backend/app/tests/test_admin.py` (test, request-response) — NEW FILE

**Analog:** `backend/app/tests/test_auth.py` (entire file is the template)

**Module docstring pattern** (test_auth.py lines 1-16) — identical structure with `Test → Requirement mapping:` table:
```python
"""
backend/app/tests/test_admin.py
Phase 10 admin user management tests.

Test → Requirement mapping:
  test_create_user             → AUTH-05
  test_list_users              → AUTH-05
  test_delete_user             → AUTH-05
  test_no_self_registration    → AUTH-05
  test_non_admin_forbidden     → AUTH-07
  test_unauthenticated_forbidden → AUTH-07
"""
```

**Imports pattern** (test_auth.py lines 17-28):
```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.db.models import User
from backend.app.services.auth import create_access_token, hash_password
```

**_seed_user helper pattern** (test_auth.py lines 36-42) — identical pattern, extend to accept `is_admin`:
```python
async def _seed_user(
    db_session: AsyncSession,
    username: str = "testuser",
    password: str = "password123",
    is_admin: bool = False,
) -> User:
    """Helper: insert a User into the test DB and return it."""
    user = User(username=username, hashed_password=hash_password(password), is_admin=is_admin)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
```

**Admin token helper** — follow `test_login_valid` pattern (test_auth.py lines 47-55) to get a real signed token:
```python
async def _get_admin_token(auth_client, db_session) -> str:
    """Seed an admin user and return a valid Bearer token for them."""
    await _seed_user(db_session, username="admin", is_admin=True)
    resp = await auth_client.post(
        "/auth/login", json={"username": "admin", "password": "password123"}
    )
    return resp.json()["access_token"]
```

**non-admin 403 test pattern** — follow `test_chat_requires_auth` (test_auth.py lines 73-75) for the negative case:
```python
async def test_non_admin_forbidden(auth_client, db_session):
    """GET /admin/users by a non-admin user → 403 (AUTH-07)."""
    await _seed_user(db_session, username="normaluser", is_admin=False)
    resp = await auth_client.post(
        "/auth/login", json={"username": "normaluser", "password": "password123"}
    )
    token = resp.json()["access_token"]
    r = await auth_client.get(
        "/admin/users", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 403


async def test_unauthenticated_forbidden(auth_client):
    """GET /admin/users with no token → 401 (AUTH-07)."""
    r = await auth_client.get("/admin/users")
    assert r.status_code == 401
```

---

### `backend/app/tests/test_rate_limit.py` (test, request-response) — NEW FILE

**Analog:** `backend/app/tests/test_auth.py` — `test_chat_with_valid_token` (lines 79-105) as closest structural match

**admin_client fixture** — new fixture needed in `conftest.py` or local to this test file. Based on the `auth_client` fixture (conftest.py lines 112-136) with `app.state.limiter` replaced:
```python
@pytest.fixture
async def rate_limited_client(db_engine):
    """
    AsyncClient with a real Limiter (not disabled) for rate limit enforcement tests.
    Uses a very low limit via patched settings — not via global slowapi config.
    """
    from backend.app.main import create_app
    from backend.app.db.session import get_db
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    app = create_app()
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

**disabled limiter fixture** — for admin endpoint tests in test_admin.py that must not be rate limited:
```python
@pytest.fixture
async def admin_client(db_engine):
    """AsyncClient with rate limiting disabled for admin endpoint tests."""
    from backend.app.main import create_app
    from backend.app.db.session import get_db
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    app = create_app()
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

**Rate limit 429 test pattern** — follows `test_chat_with_valid_token` (test_auth.py lines 79-105) for the setup; adds a settings patch for `rate_limit_per_minute=1`:
```python
async def test_rate_limit_returns_429(rate_limited_client, db_session):
    """POST /api/chat exceeds rate limit → 429 (AUTH-06)."""
    from unittest.mock import patch
    from backend.app.services import rag as rag_module

    user = await _seed_user(db_session)
    login_resp = await rate_limited_client.post(
        "/auth/login", json={"username": user.username, "password": "password123"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    async def _mock_stream(*args, **kwargs):
        yield {"type": "done", "answer": "ok", "citations": []}

    with patch.object(rag_module, "stream_answer", _mock_stream):
        with patch("backend.app.api.chat._get_chat_rate_limit", return_value="1/minute"):
            r1 = await rate_limited_client.post(
                "/api/chat", json={"message": "hi", "history": []}, headers=headers
            )
            r2 = await rate_limited_client.post(
                "/api/chat", json={"message": "hi", "history": []}, headers=headers
            )

    assert r1.status_code != 429
    assert r2.status_code == 429
```

---

## Shared Patterns

### Module Docstring Convention
**Source:** `backend/app/api/auth.py` (lines 1-13), `backend/app/services/auth.py` (lines 1-16)
**Apply to:** `api/admin.py` (new), any new function in `services/auth.py`

Every module has:
1. First line: `backend/app/path/file.py`
2. One-line description
3. `Decisions:` block with `D-XX:` references
4. `Anti-patterns avoided:` block
```python
"""
backend/app/api/admin.py
[One-line description].

Decisions:
  D-XX: [decision text].

Anti-patterns avoided:
  - [pattern].
"""
```

### Auth/Guard Pattern
**Source:** `backend/app/services/auth.py` (lines 121-160)
**Apply to:** All admin endpoints in `api/admin.py`

```python
# Module-level HTTPBearer — reuse existing _bearer in services/auth.py
_bearer = HTTPBearer(auto_error=False)

# In endpoint signature:
_admin: dict = Depends(require_admin)
```

The `require_admin` dependency wraps `decode_token` (lines 87-116) — identical `try/except jwt.InvalidTokenError` structure, adds `is_admin` check.

### Error Handling Pattern
**Source:** `backend/app/api/auth.py` (lines 83-88), `backend/app/services/auth.py` (lines 103-116)
**Apply to:** All admin CRUD endpoints

```python
# Consistent HTTPException with status code from status module (not raw int):
raise HTTPException(
    status_code=status.HTTP_4XX_YYYYYYY,
    detail="Human-readable message",
)
# Always use status.HTTP_* constants, never raw integers
```

### DB Query Pattern
**Source:** `backend/app/api/auth.py` (lines 75-81)
**Apply to:** All admin CRUD operations

```python
# Async SQLAlchemy 2.0 select pattern:
result = await db.execute(select(User).where(User.username == body.username))
user = result.scalar_one_or_none()
if user is None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="...")
```

### Test Seed + Login Pattern
**Source:** `backend/app/tests/test_auth.py` (lines 36-55)
**Apply to:** `test_admin.py`, `test_rate_limit.py`

```python
async def _seed_user(db_session, username="admin", password="password123") -> User:
    user = User(username=username, hashed_password=hash_password(password))
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
```

### Startup Helper Function Pattern
**Source:** `backend/app/main.py` (lines 28-66) — `_init_db_and_seed`
**Apply to:** `_migrate_add_is_admin_column`, `_patch_admin_is_admin`

Pattern: async function, accepts `engine` or `(settings, session_factory)`, docstring mentions decision refs, `print("[startup] ...")` for status logging.

### Pydantic Response Model (no sensitive fields)
**Source:** `backend/app/api/auth.py` (lines 41-56) — `TokenResponse`, `AccessTokenResponse`
**Apply to:** `UserResponse` in `api/admin.py`

```python
class UserResponse(BaseModel):
    # Only safe fields — never include hashed_password
    id: int
    username: str
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}  # allows .model_validate(orm_object)
```

---

## Circular Import Risk

`chat.py` needs `limiter` from `main.py`, but `main.py` imports `chat_router` from `chat.py`. To resolve, extract `limiter` into its own module:

**Recommended resolution:** Create `backend/app/core/limiter.py` with the `Limiter` instance and `_get_rate_limit_key` function. Both `main.py` and `chat.py` import from `core/limiter.py`. This follows the existing pattern of `core/config.py` being a shared import point.

---

## No Analog Found

All files have close analogs in the codebase. No files require falling back to RESEARCH.md patterns exclusively.

---

## Metadata

**Analog search scope:** `backend/app/` — all subdirectories
**Files scanned:** 7 (models.py, services/auth.py, api/auth.py, api/chat.py, core/config.py, main.py, tests/conftest.py, tests/test_auth.py)
**Pattern extraction date:** 2026-05-13

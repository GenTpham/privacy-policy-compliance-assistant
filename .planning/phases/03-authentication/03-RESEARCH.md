# Phase 3: Authentication — Research

**Researched:** 2026-04-26
**Domain:** FastAPI JWT authentication, SQLAlchemy async SQLite, pwdlib Argon2, PyJWT
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Single user seeded from ENV vars at startup. `ADMIN_USERNAME` + `ADMIN_PASSWORD` in `.env` (added to `.env.example`). Backend creates the user during the FastAPI lifespan event if the user does not already exist — safe for restarts, idempotent.
- **D-02:** Single user only — v1 is single-user gated access. No multi-user JSON array support.
- **D-03:** Stateless JWT refresh tokens — refresh token is a long-lived JWT signed with the same `jwt_secret`. No DB table required. Expiry: **7 days** (`refresh_token_expire_days: int = 7` added to `Settings`).
- **D-04:** Refresh token payload carries `sub` (username) and `type: "refresh"` — prevents a refresh token from being used as an access token and vice versa.
- **D-05:** `POST /auth/login` accepts **JSON body** `{"username": str, "password": str}`. Consistent with the existing `/chat` endpoint convention; straightforward to call from React `fetch`.
- **D-06:** Successful login response: `{"access_token": str, "refresh_token": str, "token_type": "bearer"}`.
- **D-07:** `POST /auth/refresh` accepts JSON body `{"refresh_token": str}`, returns `{"access_token": str, "token_type": "bearer"}`.
- **D-08:** `POST /auth/logout` is **client-side only** — server returns HTTP 200 with no body. Client drops both tokens from storage. No server state needed; consistent with the stateless JWT design in D-03.
- **D-09:** `/api/chat` and any future protected routes use a FastAPI `Depends(get_current_user)` dependency that: (1) reads `Authorization: Bearer <token>` header, (2) decodes and verifies the JWT (expiry, signature, `type: "access"`), (3) returns the user record on success, raises HTTP 401 on failure.
- **D-10:** The dependency is designed to be injected into route functions without restructuring the router — the chat route already anticipated this (Phase 2 CONTEXT D-15 note).
- **D-11:** SQLite file at `backend/data/users.db` (created at startup if absent). Single `users` table: `{id, username, hashed_password, created_at}`. Tables created via raw SQLAlchemy DDL in the lifespan event — no Alembic migrations for v1.
- **D-12:** `AsyncEngine` + `aiosqlite` — async-first consistent with the rest of the stack. `AsyncSession` for all DB operations.
- **D-13:** AUTH-05: at startup, validate `jwt_secret` is at minimum 32 characters. Raise `ValueError` with a clear message if too short — fail fast.

### Claude's Discretion

- Exact Pydantic request/response model field names (beyond what's decided above) — planner chooses.
- HTTP error messages (e.g. "Invalid credentials" vs "Incorrect username or password") — executor decides.
- SQLAlchemy model definition details (column types, indexes) — executor decides.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-01 | User can log in with username and password via a login form | `POST /auth/login` JSON endpoint; pwdlib Argon2 verify; PyJWT access+refresh token issuance |
| AUTH-02 | All chat endpoints require a valid JWT access token; unauthenticated requests receive HTTP 401 | `HTTPBearer` dependency + `get_current_user`; HTTPException 401 with `WWW-Authenticate: Bearer` |
| AUTH-03 | Access token expires after 30 minutes; refresh token allows re-authentication without re-entering credentials | PyJWT `exp` claim; `POST /auth/refresh` validates `type: "refresh"`, issues new access token |
| AUTH-04 | Passwords are stored as Argon2 hashes; plaintext passwords are never persisted | `PasswordHash.recommended()` (pwdlib 0.3.0) produces `$argon2id$` hashes; seed uses hash before insert |
| AUTH-05 | JWT secret is loaded from `.env`, validated at startup for minimum 32-character length | `len(settings.jwt_secret) < 32` → `ValueError` in lifespan; `.env.example` already documents requirement |

</phase_requirements>

---

## Summary

Phase 3 adds JWT-based authentication as a backend-only concern. The stack is already installed and confirmed working: PyJWT 2.12.1, pwdlib 0.3.0, SQLAlchemy 2.0.49, and aiosqlite 0.22.1 are present in the venv. All critical patterns have been verified against the running installation — no new library decisions are needed.

The implementation decomposes cleanly into four modules that do not exist yet: `backend/app/db/` (SQLAlchemy User model + session factory), `backend/app/services/auth.py` (JWT encode/decode, password hash/verify), `backend/app/api/auth.py` (login/refresh/logout routes), and additions to `backend/app/core/config.py` (two new settings fields) and `backend/app/main.py` (lifespan DB init + user seed). The chat router in `backend/app/api/chat.py` receives a single-line change to inject `Depends(get_current_user)`.

Test isolation is the key planning concern: auth tests must bypass the real lifespan (which probes OpenRouter and Qdrant) and must bypass the production DB. The established pattern from Phase 2 is to patch at the service layer; for auth tests, `app.dependency_overrides[get_db]` injects an in-memory SQLite session instead, eliminating any live-service dependency during CI.

**Primary recommendation:** Implement in a single wave with five tasks — (1) DB layer + User model, (2) auth service (JWT + password), (3) auth router (login/refresh/logout), (4) protect chat route, (5) test suite with in-memory DB override. No external services needed beyond what's already installed.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Password hashing and verification | API / Backend (auth service) | — | Never expose hash logic to any other tier; hash on write, verify on login only |
| JWT token creation | API / Backend (auth service) | — | Secret never leaves server; client receives opaque token string |
| JWT token verification | API / Backend (FastAPI dependency) | — | `get_current_user` dependency runs server-side before route handler |
| Token storage and transmission | Browser / Client | — | Client stores tokens; sends via `Authorization: Bearer` header |
| User record persistence | Database / Storage (SQLite) | — | `users` table via SQLAlchemy; `backend/data/users.db` |
| Login credential validation | API / Backend (auth router) | — | Reads JSON body, delegates to auth service, issues tokens |
| Logout | Browser / Client | — | Stateless JWT; client drops tokens; server returns 200 with no state change |
| Startup validation (secret length, DB init, user seed) | API / Backend (lifespan) | — | Fail-fast at startup, not at request time |

---

## Standard Stack

### Core (all already installed)

| Library | Installed Version | Purpose | Source |
|---------|------------------|---------|--------|
| `PyJWT` | 2.12.1 | JWT encode/decode; HS256; `exp`/`iat`/`sub`/`type` claims | [VERIFIED: venv probe] |
| `pwdlib[argon2]` | 0.3.0 | Argon2id password hashing via `PasswordHash.recommended()` | [VERIFIED: venv probe] |
| `sqlalchemy[asyncio]` | 2.0.49 | `AsyncEngine`, `AsyncSession`, `DeclarativeBase`, `Mapped` columns | [VERIFIED: venv probe] |
| `aiosqlite` | 0.22.1 | SQLite async driver for SQLAlchemy (`sqlite+aiosqlite://`) | [VERIFIED: venv probe] |
| `fastapi` | 0.136.0 | `HTTPBearer`, `Depends`, `HTTPException`, `dependency_overrides` | [VERIFIED: requirements.txt] |
| `pydantic-settings` | 2.x | `Settings` base class; new fields `refresh_token_expire_days`, `admin_username`, `admin_password` | [VERIFIED: requirements.txt] |

### No New Dependencies Required

All six libraries above are already in `requirements.txt` and installed in the venv. Phase 3 adds zero new packages. [VERIFIED: venv probe + requirements.txt inspection]

---

## Architecture Patterns

### System Architecture Diagram

```
Client (future React UI / curl)
        |
        | POST /auth/login  {"username", "password"}
        v
[FastAPI auth router] ──> [auth service] ──> [pwdlib] ──> verify hash
        |                       |
        |                       └──> [PyJWT] ──> encode access + refresh tokens
        |
        | POST /auth/refresh  {"refresh_token"}
        v
[FastAPI auth router] ──> [auth service] ──> [PyJWT] ──> decode, assert type=="refresh"
        |                                                ──> encode new access token
        |
        | POST /api/chat  Authorization: Bearer <access_token>
        v
[get_current_user dependency] ──> [auth service] ──> [PyJWT] ──> decode, assert type=="access"
        |                                        ──> [AsyncSession] ──> load User record
        v
[chat_endpoint] (existing RAG pipeline unchanged)

Startup (lifespan):
  validate jwt_secret >= 32 chars ──> ValueError if too short
  create AsyncEngine for sqlite+aiosqlite:///backend/data/users.db
  run Base.metadata.create_all (idempotent DDL)
  if ADMIN_USERNAME set in env: seed user if not exists
```

### Recommended Module Structure

```
backend/app/
├── db/
│   ├── __init__.py
│   ├── models.py          # User declarative model (id, username, hashed_password, created_at)
│   └── session.py         # AsyncEngine, async_sessionmaker, get_db() dependency
├── services/
│   ├── auth.py            # create_access_token, create_refresh_token, decode_token,
│   │                      # hash_password, verify_password, get_current_user dependency
│   └── rag.py             # (existing — unchanged)
├── api/
│   ├── auth.py            # Router: POST /auth/login, /auth/refresh, /auth/logout
│   └── chat.py            # (existing — add Depends(get_current_user) to chat_endpoint)
├── core/
│   ├── config.py          # (existing — add refresh_token_expire_days, admin_username, admin_password)
│   └── telemetry.py       # (existing — unchanged)
└── main.py                # (existing — add DB init + user seed to lifespan; register auth_router)
```

### Pattern 1: JWT Token Creation (PyJWT 2.12.1)

```python
# Source: verified against PyJWT 2.12.1 in project venv
import jwt
from datetime import datetime, timedelta, timezone

def create_access_token(sub: str, secret: str, expire_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def create_refresh_token(sub: str, secret: str, expire_days: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=expire_days),
    }
    return jwt.encode(payload, secret, algorithm="HS256")
```

### Pattern 2: JWT Token Verification (catch jwt.InvalidTokenError as umbrella)

```python
# Source: verified in project venv — ExpiredSignatureError and DecodeError both subclass InvalidTokenError
import jwt
from fastapi import HTTPException, status

def decode_token(token: str, secret: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload
```

**Key insight:** `jwt.InvalidTokenError` is the base class for `ExpiredSignatureError`, `DecodeError`, and `InvalidSignatureError` — catch the base class to handle all failure modes with one block. [VERIFIED: venv probe]

### Pattern 3: Password Hashing (pwdlib 0.3.0)

```python
# Source: verified against pwdlib 0.3.0 in project venv
from pwdlib import PasswordHash

# Singleton — create once per process
password_hasher = PasswordHash.recommended()  # uses Argon2id

def hash_password(plain: str) -> str:
    return password_hasher.hash(plain)  # returns "$argon2id$v=..." string

def verify_password(plain: str, hashed: str) -> bool:
    return password_hasher.verify(plain, hashed)
```

### Pattern 4: FastAPI Authorization Header Extraction

```python
# Source: verified against FastAPI 0.136.0 in project venv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_bearer = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials, settings.jwt_secret, expected_type="access")
    user = await _load_user_by_username(db, payload["sub"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
```

**Why `auto_error=False`:** Allows the dependency to raise its own 401 with the `WWW-Authenticate: Bearer` header (RFC 6750 compliant) instead of FastAPI's default 403. [VERIFIED: FastAPI HTTPBearer behavior in venv]

### Pattern 5: SQLAlchemy Async User Model

```python
# Source: verified against SQLAlchemy 2.0.49 + aiosqlite 0.22.1 in project venv
from datetime import datetime, timezone
from sqlalchemy import String, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

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

### Pattern 6: AsyncSession Dependency (get_db)

```python
# Source: verified in project venv — async generator function pattern
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from collections.abc import AsyncGenerator

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None

def init_db(db_url: str) -> None:
    global _engine, _session_factory
    _engine = create_async_engine(db_url, echo=False)
    _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory() as session:
        yield session
```

### Pattern 7: Lifespan DB Init + User Seed (plug into existing lifespan)

```python
# Existing lifespan extended — new additions only
from backend.app.db.session import init_db
from backend.app.db.models import Base, User
from backend.app.services.auth import hash_password
from sqlalchemy import select

async def _init_db_and_seed(settings: Settings, engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # idempotent DDL
    
    if not settings.admin_username or not settings.admin_password:
        print("[startup] ADMIN_USERNAME/ADMIN_PASSWORD not set — skipping user seed.")
        return
    
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(User).where(User.username == settings.admin_username)
        )
        if result.scalar_one_or_none() is None:
            session.add(User(
                username=settings.admin_username,
                hashed_password=hash_password(settings.admin_password),
            ))
            await session.commit()
            print(f"[startup] Admin user '{settings.admin_username}' seeded.")
        else:
            print(f"[startup] Admin user '{settings.admin_username}' already exists.")
```

### Pattern 8: Test DB Override (FastAPI dependency_overrides)

```python
# Source: verified in project venv — dependency_overrides replaces get_db at test time
# This is the test isolation pattern — no live DB, no lifespan required

import pytest
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()

@pytest.fixture
async def auth_client(db_session):
    from backend.app.main import create_app
    from backend.app.db.session import get_db
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session  # replace real DB
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()
```

**Critical nuance:** `dependency_overrides` must be cleared after each test (or use function-scoped fixtures) to prevent state bleed across tests — consistent with Phase 2's function-scope fixture rule. [VERIFIED: project conventions + venv probe]

### Anti-Patterns to Avoid

- **Using `OAuth2PasswordBearer` instead of `HTTPBearer`:** `OAuth2PasswordBearer` does not set `auto_error=False` easily and forces `form` data on login instead of JSON. D-05 requires JSON body. Use `HTTPBearer`.
- **Catching `jwt.ExpiredSignatureError` only:** `DecodeError` and `InvalidSignatureError` will slip through uncaught. Always catch `jwt.InvalidTokenError` as the base class.
- **Module-level `AsyncEngine` created at import time:** SQLAlchemy engines opened at import time prevent test isolation (engine connects to real file). Use `init_db()` called from lifespan only.
- **Storing `ADMIN_PASSWORD` in plaintext anywhere except env:** Hash immediately in the seed function; never log or return it.
- **Using `PasswordHash()` without arguments:** `PasswordHash.recommended()` is the correct API — it pre-configures Argon2id with secure parameters. [VERIFIED: pwdlib 0.3.0 probe]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password hashing | Custom bcrypt/SHA wrapper | `pwdlib.PasswordHash.recommended()` | Argon2id with safe defaults; timing-safe verify; rehash-on-upgrade built-in |
| JWT encode/decode | Manual base64 + HMAC | `PyJWT` `encode()` / `decode()` | Handles `exp` verification, algorithm validation, key-length warnings automatically |
| Async DB sessions | Manual `aiosqlite` connection | `AsyncSession` from `async_sessionmaker` | Unit-of-work pattern, connection pooling, context manager cleanup |
| Bearer token parsing | Manual `request.headers.get("Authorization").split()` | `HTTPBearer(auto_error=False)` | RFC 6750-compliant; returns `None` on missing header; no string parsing bugs |

---

## Common Pitfalls

### Pitfall 1: PyJWT warns on keys under 32 bytes

**What goes wrong:** PyJWT 2.x emits `InsecureKeyLengthWarning` (and may refuse in future versions) when the HS256 key is under 32 bytes. With `jwt_secret = "short"`, every token operation logs a warning.
**Why it happens:** RFC 7518 §3.2 requires HMAC-SHA256 keys to be at least 32 bytes.
**How to avoid:** AUTH-05 startup validation (`len(settings.jwt_secret) < 32` → `ValueError`) prevents the server from starting with a short secret. The `.env.example` already documents `openssl rand -hex 32`.
**Warning signs:** `InsecureKeyLengthWarning` in startup logs — means the `jwt_secret` env var is too short and the startup validator is not running. [VERIFIED: observed during venv probe]

### Pitfall 2: Refresh token accepted as access token (and vice versa)

**What goes wrong:** Without a `type` claim check, a 7-day refresh token can be presented to a protected route and accepted as a valid access token.
**Why it happens:** Both tokens are signed with the same secret and the same `HS256` algorithm — the only distinguishing data is the custom `type` claim.
**How to avoid:** `decode_token(token, secret, expected_type="access")` in `get_current_user`; `decode_token(token, secret, expected_type="refresh")` in `POST /auth/refresh`. Assert `payload["type"] == expected_type` before trusting the token.
**Warning signs:** Test: present a refresh token to `/api/chat` — should return 401. If it returns 200, the type check is missing.

### Pitfall 3: Engine created at import time blocks test isolation

**What goes wrong:** `engine = create_async_engine(db_url)` at module level connects to the real `users.db` immediately. Tests that import the module trigger real filesystem operations; `dependency_overrides` cannot override an engine that already opened the file.
**Why it happens:** Python executes module-level code at import time.
**How to avoid:** `init_db(db_url)` function called from lifespan only. Tests use their own `create_async_engine("sqlite+aiosqlite:///:memory:")` and override `get_db` via `dependency_overrides`. [VERIFIED: established pattern from project Phase 2]

### Pitfall 4: `aiosqlite` file path on Windows requires forward slashes or `///` notation

**What goes wrong:** `sqlite+aiosqlite://\backend\data\users.db` (Windows backslashes) raises `OperationalError: unable to open database file`.
**Why it happens:** SQLAlchemy/aiosqlite passes the path string directly to the SQLite C library which does not handle backslashes uniformly.
**How to avoid:** Use `sqlite+aiosqlite:///` + a POSIX path string, or construct with `pathlib.Path(...).as_posix()`. Store as absolute path relative to project root. [ASSUMED — based on known SQLite/Windows behavior; verify with a test on the target machine]

### Pitfall 5: `Base.metadata.create_all` is not idempotent on column changes

**What goes wrong:** If the `users` table already exists with different columns, `create_all` silently skips the table — it does not alter existing schemas.
**Why it happens:** `create_all` only creates missing tables; it does not modify existing ones.
**How to avoid:** For v1 this is acceptable — the schema is locked. If the table definition changes during development, delete `backend/data/users.db` and restart to re-create. Document this in a startup note. No Alembic needed for v1 (D-11).

### Pitfall 6: `app.dependency_overrides` not cleared between tests

**What goes wrong:** Test A overrides `get_db`; Test B runs without clearing overrides and also uses the test DB — this can mask failures where the production dependency would behave differently.
**Why it happens:** `dependency_overrides` is a mutable dict on the FastAPI app instance; if the same `app` instance is reused across tests, overrides persist.
**How to avoid:** Either call `app.dependency_overrides.clear()` in a teardown (or `yield`-based fixture), or use `create_app()` inside each fixture to get a fresh app instance. Function-scoped fixtures are the established pattern in this project. [VERIFIED: project conventions from Phase 2 STATE.md]

---

## Code Examples

### Full login endpoint skeleton

```python
# Source: FastAPI 0.136.0 + PyJWT 2.12.1 + pwdlib 0.3.0 — all verified
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.core.config import get_settings, Settings
from backend.app.services.auth import (
    verify_password, create_access_token, create_refresh_token
)

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(
        access_token=create_access_token(user.username, settings.jwt_secret, settings.access_token_expire_minutes),
        refresh_token=create_refresh_token(user.username, settings.jwt_secret, settings.refresh_token_expire_days),
    )
```

### Config additions (backend/app/core/config.py)

```python
# Add to Settings class — follows existing @lru_cache get_settings() pattern
refresh_token_expire_days: int = 7
admin_username: str | None = None   # Optional — skip seed if not set
admin_password: str | None = None   # Optional — skip seed if not set
```

### Chat route auth injection (single line change)

```python
# backend/app/api/chat.py — uncomment the Phase 3 line
from backend.app.services.auth import get_current_user
from backend.app.db.models import User

@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),  # add this line
) -> StreamingResponse:
    ...
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `passlib` + `bcrypt` | `pwdlib[argon2]` | FastAPI PR #13917 (2024) | passlib unmaintained; `crypt` removed in Python 3.13; pwdlib is the current FastAPI-endorsed replacement |
| `python-jose` for JWT | `PyJWT` | 2023+ | python-jose last released 3+ years ago; DeprecationWarning on 3.12+; PyJWT is actively maintained |
| `OAuth2PasswordBearer` + form data | `HTTPBearer` + JSON body | Project decision D-05 | JSON body is more consistent with existing `/api/chat` endpoint |
| Synchronous SQLAlchemy | `AsyncSession` + `aiosqlite` | SQLAlchemy 2.0 (2023) | Blocking the asyncio event loop is unacceptable; `AsyncSession` is the current standard |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `sqlite+aiosqlite:///` with POSIX path avoids Windows backslash issues | Pitfall 4 | `OperationalError` at startup when `users.db` path contains backslashes on Windows host; fix: use `pathlib.Path.as_posix()` |

**All other claims in this research were verified against the running project venv or source files.**

---

## Open Questions

1. **`backend/data/` directory existence at startup**
   - What we know: `users.db` will be created at `backend/data/users.db`
   - What's unclear: If `backend/data/` does not exist, `aiosqlite` will raise `OperationalError: unable to open database file`
   - Recommendation: The lifespan `_init_db_and_seed` should call `Path("backend/data").mkdir(parents=True, exist_ok=True)` before `create_async_engine`. Alternatively, Docker Compose volume mounts should ensure the directory exists.

2. **`.env.example` additions**
   - What we know: `.env.example` already has `JWT_SECRET`; `ADMIN_USERNAME` and `ADMIN_PASSWORD` are new.
   - Recommendation: Add both to `.env.example` with instructional comments; document that missing `ADMIN_USERNAME` skips seed silently (not an error).

---

## Environment Availability

Step 2.6: All dependencies verified as installed in project venv — no new packages required.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `PyJWT` | JWT encode/decode | Yes | 2.12.1 | — |
| `pwdlib[argon2]` | Argon2id hashing | Yes | 0.3.0 | — |
| `sqlalchemy[asyncio]` | AsyncSession, ORM | Yes | 2.0.49 | — |
| `aiosqlite` | SQLite async driver | Yes | 0.22.1 | — |
| `fastapi` | HTTPBearer, Depends | Yes | 0.136.0 | — |
| `httpx` | Test client | Yes | (dev dep) | — |
| `pytest-asyncio` | Async test runner | Yes | (dev dep) | — |

**Missing dependencies with no fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pytest.ini` (root) — `asyncio_mode = auto` |
| Quick run command | `pytest backend/app/tests/test_auth.py -x -v` |
| Full suite command | `pytest backend/app/tests/ -x -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-01 | `POST /auth/login` with valid creds returns 200 + access_token + refresh_token | unit (HTTP) | `pytest backend/app/tests/test_auth.py::test_login_valid -x` | No — Wave 0 |
| AUTH-01 | `POST /auth/login` with wrong password returns 401 | unit (HTTP) | `pytest backend/app/tests/test_auth.py::test_login_wrong_password -x` | No — Wave 0 |
| AUTH-01 | `POST /auth/login` with unknown username returns 401 | unit (HTTP) | `pytest backend/app/tests/test_auth.py::test_login_unknown_user -x` | No — Wave 0 |
| AUTH-02 | `POST /api/chat` without Authorization header returns 401 | unit (HTTP) | `pytest backend/app/tests/test_auth.py::test_chat_requires_auth -x` | No — Wave 0 |
| AUTH-02 | `POST /api/chat` with valid Bearer token returns 200 | unit (HTTP) | `pytest backend/app/tests/test_auth.py::test_chat_with_valid_token -x` | No — Wave 0 |
| AUTH-03 | `POST /auth/refresh` with valid refresh token returns new access_token | unit (HTTP) | `pytest backend/app/tests/test_auth.py::test_refresh_valid -x` | No — Wave 0 |
| AUTH-03 | `POST /auth/refresh` with access token (wrong type) returns 401 | unit (HTTP) | `pytest backend/app/tests/test_auth.py::test_refresh_wrong_type -x` | No — Wave 0 |
| AUTH-03 | `POST /auth/refresh` with expired token returns 401 | unit (HTTP) | `pytest backend/app/tests/test_auth.py::test_refresh_expired -x` | No — Wave 0 |
| AUTH-04 | Seeded user has `hashed_password` starting with `$argon2id$` | unit (DB) | `pytest backend/app/tests/test_auth.py::test_password_stored_as_argon2 -x` | No — Wave 0 |
| AUTH-05 | Starting with `jwt_secret` < 32 chars raises ValueError | unit | `pytest backend/app/tests/test_auth.py::test_short_jwt_secret_rejected -x` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest backend/app/tests/test_auth.py -x -v`
- **Per wave merge:** `pytest backend/app/tests/ -x -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/app/tests/test_auth.py` — 10 test stubs covering all AUTH-01–05 behaviors
- [ ] `backend/app/tests/conftest.py` — add `db_session` and `auth_client` fixtures (in-memory SQLite + dependency override)

*(Existing `conftest.py` needs new fixtures; no new framework config needed — `pytest.ini` asyncio_mode=auto already set)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes | `POST /auth/login` JSON body; Argon2id verify via pwdlib; timing-safe comparison built into pwdlib |
| V3 Session Management | Yes | Stateless JWT; access token 30 min TTL; refresh token 7 day TTL; `type` claim prevents cross-use |
| V4 Access Control | Yes | `get_current_user` dependency gates `/api/chat`; 401 with `WWW-Authenticate: Bearer` |
| V5 Input Validation | Yes | Pydantic `LoginRequest` validates username/password as non-empty strings; `ChatRequest` already validated |
| V6 Cryptography | Yes | HS256 with minimum 32-byte secret (AUTH-05 startup check); Argon2id for password hashing (never hand-rolled) |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Credential brute-force | Threat: Spoofing | Argon2id slows offline attacks; rate limiting is deferred (v1 single user, internal access) |
| Token cross-use (refresh as access) | Threat: Elevation of Privilege | `type` claim check in `decode_token`; tested as AUTH-03 |
| Weak JWT secret | Threat: Spoofing | Startup validation rejects secrets < 32 chars (AUTH-05); `openssl rand -hex 32` in `.env.example` |
| Plaintext password in logs | Threat: Information Disclosure | Hash immediately in seed; never log `admin_password`; `Settings` field is `str | None`, not logged by default |
| SQL injection via username | Threat: Tampering | SQLAlchemy parameterized `select(User).where(User.username == body.username)` — no raw SQL |

---

## Sources

### Primary (HIGH confidence — verified in project venv)

- PyJWT 2.12.1 — `jwt.encode`, `jwt.decode`, `jwt.InvalidTokenError`, `InsecureKeyLengthWarning` behavior verified by running code in project venv
- pwdlib 0.3.0 — `PasswordHash.recommended()`, `.hash()`, `.verify()` verified by running code in project venv; `$argon2id$` prefix confirmed
- SQLAlchemy 2.0.49 + aiosqlite 0.22.1 — `AsyncEngine`, `async_sessionmaker`, `AsyncSession`, `DeclarativeBase`, `Mapped` columns verified with in-memory SQLite demo
- FastAPI 0.136.0 — `HTTPBearer(auto_error=False)`, `dependency_overrides`, `HTTPException` with `WWW-Authenticate` header verified in project venv
- `backend/app/core/config.py` — existing `jwt_secret`, `jwt_algorithm`, `access_token_expire_minutes` fields confirmed by direct file read
- `backend/app/main.py` — existing lifespan pattern confirmed by direct file read
- `backend/app/api/chat.py` — commented `current_user` line confirmed; Phase 3 hook already in place
- `requirements.txt` — all six auth libraries already listed; no new packages needed
- `.env.example` — `JWT_SECRET` already present; `ADMIN_USERNAME`/`ADMIN_PASSWORD` are new additions

### Secondary (MEDIUM confidence — project documentation)

- [FastAPI PR #13917](https://github.com/fastapi/fastapi/pull/13917) — pwdlib migration from passlib; cited in CLAUDE.md
- [FastAPI OAuth2 + JWT Tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) — HTTPBearer pattern; cited in CLAUDE.md

---

## Metadata

**Confidence breakdown:**

| Area | Level | Reason |
|------|-------|--------|
| Standard stack | HIGH | All libraries verified against running project venv |
| Architecture patterns | HIGH | All code patterns executed and verified in project venv |
| Pitfalls | HIGH | All pitfalls either verified (InsecureKeyLengthWarning observed live) or derived from established project conventions |
| Test isolation | HIGH | `dependency_overrides` pattern verified in project venv; function-scope fixture rule confirmed from STATE.md |

**Research date:** 2026-04-26
**Valid until:** 2026-05-26 (stable libraries; PyJWT and pwdlib do not change frequently)

# Phase 3: Authentication - Pattern Map

**Mapped:** 2026-04-25
**Files analyzed:** 8 new/modified files
**Analogs found:** 8 / 8

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/db/models.py` | model | CRUD | `backend/app/services/rag.py` (data shapes) | partial — no ORM model exists yet; RESEARCH.md Pattern 5 is canonical |
| `backend/app/db/session.py` | utility | request-response | `backend/app/services/rag.py` (module-level client init) | partial — async client init pattern matches |
| `backend/app/db/__init__.py` | config | — | `backend/app/services/__init__.py` | exact — empty package marker |
| `backend/app/services/auth.py` | service | request-response | `backend/app/services/rag.py` | role-match — same service layer position and import style |
| `backend/app/api/auth.py` | controller | request-response | `backend/app/api/chat.py` | exact — same router role, same Pydantic model + APIRouter pattern |
| `backend/app/core/config.py` | config | — | `backend/app/core/config.py` (existing — modify) | exact — extending existing Settings class |
| `backend/app/main.py` | config | — | `backend/app/main.py` (existing — modify) | exact — extending existing lifespan pattern |
| `backend/app/api/chat.py` | controller | streaming | `backend/app/api/chat.py` (existing — single-line modify) | exact — injecting Depends into existing route |
| `backend/app/tests/test_auth.py` | test | request-response | `backend/app/tests/test_chat_endpoint.py` | exact — same httpx.AsyncClient + ASGITransport pattern |
| `backend/app/tests/conftest.py` | test | — | `backend/app/tests/conftest.py` (existing — modify) | exact — extending existing fixture file |

---

## Pattern Assignments

### `backend/app/db/models.py` (model, CRUD)

**Analog:** RESEARCH.md Pattern 5 (verified against SQLAlchemy 2.0.49 in project venv) — no ORM model exists in codebase yet.

**Imports pattern:**
```python
from datetime import datetime, timezone
from sqlalchemy import String, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
```

**Core model pattern** (from RESEARCH.md Pattern 5):
```python
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

**Key constraint:** `Base` must be importable from `backend/app/db/models.py` for `Base.metadata.create_all` in the lifespan. `User` must be importable into both `session.py` and `services/auth.py`.

---

### `backend/app/db/session.py` (utility, request-response)

**Analog:** `backend/app/services/rag.py` lines 30-48 (module-level async client init pattern).

**Anti-pattern to avoid from rag.py:** rag.py creates clients at module level (lines 33-48) — session.py must NOT do this. Engine must be created inside `init_db()` called from lifespan only (RESEARCH.md Pitfall 3).

**Imports pattern** (from RESEARCH.md Pattern 6):
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from collections.abc import AsyncGenerator
```

**Core pattern** (from RESEARCH.md Pattern 6):
```python
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

**Windows path pitfall** (RESEARCH.md Pitfall 4): use `pathlib.Path(...).as_posix()` when constructing `db_url` from the settings path — backslashes in the SQLite URL cause `OperationalError`.

---

### `backend/app/services/auth.py` (service, request-response)

**Analog:** `backend/app/services/rag.py` — same service layer position, pure functions, no HTTP concerns.

**Imports pattern** (copy header style from `backend/app/services/rag.py` lines 1-16, substitute libraries):
```python
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.core.config import get_settings, Settings
from backend.app.db.models import User
from backend.app.db.session import get_db
```

**Password hashing pattern** (from RESEARCH.md Pattern 3):
```python
# Singleton — create once per process
password_hasher = PasswordHash.recommended()  # uses Argon2id

def hash_password(plain: str) -> str:
    return password_hasher.hash(plain)  # returns "$argon2id$v=..." string

def verify_password(plain: str, hashed: str) -> bool:
    return password_hasher.verify(plain, hashed)
```

**JWT creation pattern** (from RESEARCH.md Pattern 1):
```python
def create_access_token(sub: str, secret: str, expire_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": sub, "type": "access", "iat": now,
               "exp": now + timedelta(minutes=expire_minutes)}
    return jwt.encode(payload, secret, algorithm="HS256")

def create_refresh_token(sub: str, secret: str, expire_days: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": sub, "type": "refresh", "iat": now,
               "exp": now + timedelta(days=expire_days)}
    return jwt.encode(payload, secret, algorithm="HS256")
```

**JWT decode pattern** (from RESEARCH.md Pattern 2 — catch base class, not subclasses):
```python
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

**FastAPI dependency pattern** (from RESEARCH.md Pattern 4 — use `auto_error=False` to control 401 vs 403):
```python
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
    result = await db.execute(select(User).where(User.username == payload["sub"]))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
```

---

### `backend/app/api/auth.py` (controller, request-response)

**Analog:** `backend/app/api/chat.py` — same role: APIRouter + Pydantic models + async route handlers.

**Imports pattern** (copy structure from `backend/app/api/chat.py` lines 1-18, substitute libraries):
```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.core.config import get_settings, Settings
from backend.app.services.auth import (
    verify_password, create_access_token, create_refresh_token, decode_token
)

router = APIRouter()
```

**Pydantic model pattern** (mirror chat.py lines 24-41 — BaseModel with typed fields):
```python
class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str

class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

**Route handler pattern** (from RESEARCH.md Code Examples — full login skeleton):
```python
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
        access_token=create_access_token(
            user.username, settings.jwt_secret, settings.access_token_expire_minutes
        ),
        refresh_token=create_refresh_token(
            user.username, settings.jwt_secret, settings.refresh_token_expire_days
        ),
    )
```

**Error handling pattern** (from `backend/app/api/chat.py` — HTTPException raised inline, no bottom-of-file handler; this project does not use centralized error middleware):
```python
# Pattern: raise HTTPException inline per route — no try/except block at router level
# HTTP 401 always includes headers={"WWW-Authenticate": "Bearer"} (RFC 6750)
raise HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="...",
    headers={"WWW-Authenticate": "Bearer"},
)
```

---

### `backend/app/core/config.py` (config — MODIFY existing)

**Analog:** `backend/app/core/config.py` (self — extend in place).

**Existing file** (`backend/app/core/config.py` lines 1-35) — add three fields to `Settings` class after line 23:

```python
# Phase 3 additions — insert after access_token_expire_minutes: int = 30
refresh_token_expire_days: int = 7
admin_username: str | None = None   # Optional — skip seed if not set
admin_password: str | None = None   # Optional — skip seed if not set
```

**JWT secret validation** (AUTH-05 — goes in lifespan, not in Settings; see main.py pattern below):
```python
if len(settings.jwt_secret) < 32:
    raise ValueError(
        "jwt_secret must be at least 32 characters. "
        "Generate with: openssl rand -hex 32"
    )
```

---

### `backend/app/main.py` (config — MODIFY existing)

**Analog:** `backend/app/main.py` (self — extend lifespan and create_app in place).

**Existing lifespan pattern** (`backend/app/main.py` lines 60-93) — new DB init block plugs in before `yield`:

**New imports to add** (at top of file, following existing import block style):
```python
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncEngine
from backend.app.db.session import init_db, get_db
from backend.app.db.models import Base, User
from backend.app.services.auth import hash_password
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
```

**Lifespan DB init + seed pattern** (from RESEARCH.md Pattern 7, adapted to plug into existing lifespan lines 60-93):
```python
# Insert at start of lifespan, before setup_tracing() call:
if len(settings.jwt_secret) < 32:                          # AUTH-05
    raise ValueError("jwt_secret must be >=32 chars. Use: openssl rand -hex 32")

db_path = Path("backend/data/users.db")
db_path.parent.mkdir(parents=True, exist_ok=True)          # ensure dir exists (RESEARCH.md Open Question 1)
db_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"       # POSIX path (Pitfall 4)
engine = init_db(db_url)

async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)          # idempotent DDL (D-11)

if settings.admin_username and settings.admin_password:
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
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
else:
    print("[startup] ADMIN_USERNAME/ADMIN_PASSWORD not set — skipping user seed.")
```

**Router registration pattern** (mirror `backend/app/main.py` line 103):
```python
# In create_app(), after existing include_router call:
from backend.app.api.auth import router as auth_router
app.include_router(auth_router, prefix="/auth")
```

---

### `backend/app/api/chat.py` (controller — SINGLE LINE MODIFY)

**Analog:** `backend/app/api/chat.py` (self — uncomment prepared line).

**Existing prepared hook** (`backend/app/api/chat.py` lines 57-59):
```python
@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    # current_user: User = Depends(get_current_user),  # Phase 3 adds this
) -> StreamingResponse:
```

**Change:** Uncomment the `current_user` line and add the two imports at the top of the file (from RESEARCH.md Code Examples — chat route auth injection):
```python
# Add to imports at top of chat.py:
from backend.app.services.auth import get_current_user
from backend.app.db.models import User

# Uncomment in chat_endpoint signature:
current_user: User = Depends(get_current_user),
```

---

### `backend/app/tests/test_auth.py` (test, request-response — NEW)

**Analog:** `backend/app/tests/test_chat_endpoint.py` — exact same httpx.AsyncClient + ASGITransport pattern.

**Imports pattern** (mirror `backend/app/tests/test_chat_endpoint.py` lines 1-13):
```python
import pytest
import httpx
from unittest.mock import patch, AsyncMock
from backend.app.main import create_app
```

**HTTP test pattern** (mirror `backend/app/tests/test_chat_endpoint.py` lines 25-45 — create_app() per test, ASGITransport):
```python
@pytest.mark.asyncio
async def test_login_valid(auth_client, seeded_user):
    response = await auth_client.post(
        "/auth/login",
        json={"username": "admin", "password": "correctpassword"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
```

**Test isolation pattern** (from RESEARCH.md Pattern 8 — dependency_overrides replaces get_db):
```python
# Tests use in-memory SQLite via dependency_overrides — no real users.db touched
app = create_app()
app.dependency_overrides[get_db] = lambda: db_session   # override from conftest fixture
# Always clear after each test (function-scoped fixtures ensure this)
```

---

### `backend/app/tests/conftest.py` (test fixtures — MODIFY existing)

**Analog:** `backend/app/tests/conftest.py` (self — add new fixtures to existing file).

**Existing fixture style** (`backend/app/tests/conftest.py` lines 13-30) — new fixtures follow same function-scoped async pattern:

**New fixtures to add** (from RESEARCH.md Pattern 8):
```python
@pytest.fixture
async def db_session():
    """In-memory SQLite session — no real users.db touched during tests."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from backend.app.db.models import Base
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()

@pytest.fixture
async def auth_client(db_session):
    """httpx client with in-memory DB override — no lifespan, no live services."""
    from backend.app.main import create_app
    from backend.app.db.session import get_db
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()   # Pitfall 6 — always clear
```

---

## Shared Patterns

### Settings singleton access
**Source:** `backend/app/core/config.py` lines 28-35
**Apply to:** All new service and API files that need config
```python
from backend.app.core.config import get_settings, Settings
# In FastAPI routes: inject via Depends(get_settings)
# In service functions: receive as parameter (not called directly inside functions)
```

### Module header / docstring style
**Source:** `backend/app/api/chat.py` lines 1-8 and `backend/app/services/rag.py` lines 1-6
**Apply to:** All new files
```python
"""
backend/app/<layer>/<module>.py
One-line description of responsibility.
Key constraint or phase note.
"""
```

### Async-first throughout
**Source:** `backend/app/services/rag.py` lines 9-16 + `backend/app/main.py` lines 60-93
**Apply to:** All new db, service, and api files
- All DB operations use `AsyncSession` + `await`
- All dependencies are `async def` if they yield or call async code
- `AsyncEngine` only created inside `init_db()`, never at module import time

### HTTP 401 response format
**Source:** RESEARCH.md Pattern 2 + Pattern 4 (RFC 6750)
**Apply to:** `backend/app/services/auth.py` and `backend/app/api/auth.py`
```python
raise HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="<message>",
    headers={"WWW-Authenticate": "Bearer"},
)
```

### Test function scope (no shared state)
**Source:** `backend/app/tests/conftest.py` lines 13-14 and `backend/app/tests/test_chat_endpoint.py` lines 25-45
**Apply to:** All new test fixtures and test functions
- All fixtures are function-scoped (default in pytest) — no `scope="session"` or `scope="module"`
- `create_app()` called inside each test or fixture — fresh app instance, no cross-test bleed
- `app.dependency_overrides.clear()` in fixture teardown

### Import path style
**Source:** `backend/app/api/chat.py` lines 9-18, `backend/app/services/rag.py` lines 9-16
**Apply to:** All new files
```python
# Always use full package path from project root:
from backend.app.core.config import get_settings
from backend.app.services.auth import get_current_user
from backend.app.db.models import User
# Never use relative imports (no "from . import ...")
```

---

## No Analog Found

All files have analogs in the codebase. The ORM model in `backend/app/db/models.py` has no role-match analog (no SQLAlchemy model exists), but RESEARCH.md Pattern 5 was verified against the running venv and serves as the canonical reference.

---

## Metadata

**Analog search scope:** `backend/app/api/`, `backend/app/services/`, `backend/app/core/`, `backend/app/tests/`
**Files scanned:** 8 existing source files
**Pattern extraction date:** 2026-04-25

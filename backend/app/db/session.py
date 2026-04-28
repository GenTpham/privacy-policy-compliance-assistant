"""
backend/app/db/session.py
AsyncEngine + async_sessionmaker factory.
init_db(db_url) is called from the FastAPI lifespan ONLY — never at import time.
This ensures test fixtures can substitute an in-memory SQLite engine via
dependency_overrides[get_db] without touching the real users.db file.

Decision D-12: AsyncEngine + aiosqlite — async-first consistent with rest of stack.
Pitfall 3: engine MUST NOT be created at module level (blocks test isolation).
Pitfall 4: db_url must use forward slashes on Windows — use pathlib.Path.as_posix().
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


def init_db(db_url: str) -> None:
    """
    Initialize the module-level engine and session factory.
    Must be called once from the FastAPI lifespan before the first request.
    Safe to call again (will re-initialize — idempotent for restart scenarios).
    """
    global _engine, _session_factory
    _engine = create_async_engine(db_url, echo=False)
    _session_factory = async_sessionmaker(
        _engine, class_=AsyncSession, expire_on_commit=False
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields one AsyncSession per request.
    Raises AssertionError if init_db() was not called (fail-fast, not silent).
    Tests override this via app.dependency_overrides[get_db].
    """
    assert _session_factory is not None, (
        "init_db() must be called before get_db() — check FastAPI lifespan."
    )
    async with _session_factory() as session:
        yield session

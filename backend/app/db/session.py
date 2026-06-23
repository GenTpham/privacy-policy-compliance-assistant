"""
Database session management.
Supports both SQLite (dev) and PostgreSQL (prod) via DATABASE_URL.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

_engine = None
_session_factory = None

def init_db(db_url: str) -> None:
    """Initialize the async engine and session factory."""
    global _engine, _session_factory

    connect_args = {}
    if "sqlite" in db_url:
        connect_args = {"check_same_thread": False}

    _engine = create_async_engine(db_url, connect_args=connect_args, echo=False)
    _session_factory = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    """FastAPI dependency — yields an AsyncSession."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with _session_factory() as session:
        yield session

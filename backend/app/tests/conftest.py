"""
backend/app/tests/conftest.py
Shared pytest fixtures for Phase 2 unit tests and Phase 3 auth tests.
All fixtures are function-scoped — each test receives a fresh mock instance.
"""
import os

# Set required env vars so get_settings() is callable in test assertions.
# setdefault is safe: real .env values are not overridden during local dev runs.
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET", "a" * 32)

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


@pytest.fixture
def mock_openrouter():
    """
    Mocked AsyncOpenAI client — controls embed and chat responses.
    Function-scoped: each test gets a fresh mock with no shared state.
    """
    client = MagicMock(spec=AsyncOpenAI)

    # Embedding: returns a single 128-dim vector
    embed_resp = MagicMock()
    embed_resp.data = [MagicMock(embedding=[0.1] * 128)]
    client.embeddings.create = AsyncMock(return_value=embed_resp)

    # Chat completion stream: default is an empty async iterator (no tokens)
    # Individual tests override this via mock_openrouter.chat.completions.create.return_value
    client.chat.completions.create = AsyncMock(return_value=_empty_async_iter())
    return client


@pytest.fixture
def mock_qdrant():
    """
    Mocked AsyncQdrantClient — returns controlled ScoredPoint results.
    Default: empty list (no chunks above threshold) — tests override as needed.
    """
    client = MagicMock(spec=AsyncQdrantClient)
    # qdrant-client 1.13+ uses query_points() — returns QueryResponse with .points
    mock_response = MagicMock()
    mock_response.points = []
    client.query_points = AsyncMock(return_value=mock_response)
    return client


@pytest.fixture
def sample_scored_point():
    """
    One fake ScoredPoint with all required payload fields.
    Represents a single retrieved Qdrant chunk — use in citation and prompt tests.
    """
    point = MagicMock()
    point.id = "abc-123"
    point.score = 0.82
    point.payload = {
        "text": "Personal data must be retained no longer than 30 days.",
        "title": "Privacy Policy v2",
        "source_doc": "policy_v2",
        "passage_id": "p-001",
    }
    return point


async def _empty_async_iter():
    """Helper: async iterator that yields nothing — simulates zero LLM tokens."""
    return
    yield  # makes this an async generator


@pytest.fixture
async def db_engine():
    """
    Shared in-memory SQLite engine for a single test.
    Creates all tables from Base.metadata, yields the engine, then disposes it.
    Function-scoped — each test gets a clean database state.
    Import guards: imports are local to avoid triggering module-level engine creation in session.py.
    """
    from backend.app.db.models import Base
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    """
    Test-side AsyncSession for seeding data — NOT shared with the HTTP override.
    Both db_session and auth_client share the same db_engine (same in-memory DB),
    but use separate session objects, mirroring production isolation behaviour.
    Explicit rollback on teardown guards against pending uncommitted mutations.
    """
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()  # ensure no pending transaction at teardown


@pytest.fixture
async def auth_client(db_engine):
    """
    httpx.AsyncClient wired to the FastAPI app with get_db replaced by the in-memory db_engine.
    Uses a separate session factory from db_session — both share the same engine but
    hold independent sessions, avoiding shared-connection isolation caveats.
    Bypasses the production lifespan (no OpenRouter/Qdrant needed).
    Function-scoped — app.dependency_overrides is cleared after each test.
    """
    from backend.app.main import create_app
    from backend.app.db.session import get_db

    app = create_app()
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_scored_points_multi():
    """
    Two fake ScoredPoints from different source documents — for conflict path tests.
    Simulates a top-10 retrieval returning chunks from Policy A and Policy B.
    Function-scoped: each test receives a fresh list.
    """
    def _make(idx, title, text):
        point = MagicMock()
        point.id = f"id-{idx}"
        point.score = 0.80
        point.payload = {
            "text": text,
            "title": title,
            "source_doc": f"doc_{idx}",
            "chunk_index": 0,
        }
        return point

    return [
        _make(1, "Policy A", "Data is retained for 30 days."),
        _make(2, "Policy B", "Data is retained indefinitely."),
    ]

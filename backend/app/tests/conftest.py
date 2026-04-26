"""
backend/app/tests/conftest.py
Shared pytest fixtures for Phase 2 unit tests and Phase 3 auth tests.
All fixtures are function-scoped — each test receives a fresh mock instance.
"""
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
async def db_session():
    """
    In-memory SQLite session for auth tests.
    Creates all tables from Base.metadata, yields an AsyncSession, then disposes the engine.
    Function-scoped — each test gets a clean database state.
    Import guards: imports are local to avoid triggering module-level engine creation in session.py.
    """
    from backend.app.db.models import Base
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def auth_client(db_session):
    """
    httpx.AsyncClient wired to the FastAPI app with get_db replaced by the in-memory db_session.
    Bypasses the production lifespan (no OpenRouter/Qdrant needed).
    Function-scoped — app.dependency_overrides is cleared after each test.
    """
    from backend.app.main import create_app
    from backend.app.db.session import get_db

    app = create_app()

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()

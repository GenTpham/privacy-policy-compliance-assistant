"""
backend/app/tests/test_sources_endpoint.py
HTTP-level tests for GET /api/sources endpoint.
Uses httpx.AsyncClient with ASGITransport — no live server needed.

Run: pytest backend/app/tests/test_sources_endpoint.py -x -v
"""
import pytest
import httpx
from unittest.mock import patch, AsyncMock

from backend.app.db.models import User
from backend.app.main import create_app
from backend.app.services.auth import get_current_user


# ── Shared helpers ────────────────────────────────────────────────────────────

def _stub_current_user():
    """Override for get_current_user — returns a dummy User without DB/JWT checks."""
    return User(id=1, username="test", hashed_password="$argon2id$stub")


async def _minimal_done_stream(*args, **kwargs):
    """Minimal stream stub — yields one done event."""
    yield {"type": "done", "answer": "stubbed", "citations": []}


# ── GET /api/sources ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sources_returns_list():
    """UX-01: GET /api/sources with auth returns {"sources": [...]} with HTTP 200."""
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_current_user
    try:
        with patch(
            "backend.app.services.rag.get_distinct_sources",
            new_callable=AsyncMock,
            return_value=["Google Privacy Policy", "OpenAI Privacy Policy"],
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/sources")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert "sources" in data
    assert isinstance(data["sources"], list)
    assert data["sources"] == ["Google Privacy Policy", "OpenAI Privacy Policy"]


@pytest.mark.asyncio
async def test_sources_requires_auth(db_engine):
    """UX-01: GET /api/sources without bearer token returns HTTP 401."""
    from backend.app.db.session import get_db
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    app = create_app()
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with factory() as session:
            yield session

    # Override get_db so the app can init, but no auth override — real JWT check applied
    app.dependency_overrides[get_db] = _override_get_db
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/sources")  # no Authorization header
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sources_returns_500_on_qdrant_error():
    """UX-01: GET /api/sources returns HTTP 500 when Qdrant raises an exception."""
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_current_user
    try:
        with patch(
            "backend.app.services.rag.get_distinct_sources",
            side_effect=Exception("Qdrant down"),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/sources")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to retrieve source list"


# ── ChatRequest.source_filter ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_source_filter_omitted_defaults_to_none():
    """POST /api/chat without source_filter field should pass source_filter=None to generator."""
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_current_user
    captured_kwargs = {}

    async def _capture_stream(*args, **kwargs):
        captured_kwargs.update(kwargs)
        yield {"type": "done", "answer": "stubbed", "citations": []}

    try:
        with patch("backend.app.services.rag.stream_answer", side_effect=_capture_stream):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/chat",
                    json={"message": "what is the policy?", "history": []},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured_kwargs.get("source_filter") is None


@pytest.mark.asyncio
async def test_chat_source_filter_passed_to_stream_answer():
    """POST /api/chat with source_filter passes it to rag.stream_answer as keyword arg."""
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_current_user
    captured_kwargs = {}

    async def _capture_stream(*args, **kwargs):
        captured_kwargs.update(kwargs)
        yield {"type": "done", "answer": "stubbed", "citations": []}

    try:
        with patch("backend.app.services.rag.stream_answer", side_effect=_capture_stream):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/chat",
                    json={
                        "message": "what is the policy?",
                        "history": [],
                        "source_filter": "Google Privacy Policy",
                    },
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured_kwargs.get("source_filter") == "Google Privacy Policy"


@pytest.mark.asyncio
async def test_chat_source_filter_passed_to_conflict_stream():
    """POST /api/chat with conflict keyword and source_filter passes it to stream_conflict_answer."""
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_current_user
    captured_kwargs = {}

    async def _capture_conflict(*args, **kwargs):
        captured_kwargs.update(kwargs)
        yield {"type": "done", "answer": "stubbed", "citations": []}

    try:
        with patch("backend.app.services.rag.stream_conflict_answer", side_effect=_capture_conflict):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/chat",
                    json={
                        "message": "conflict between policies",
                        "history": [],
                        "source_filter": "Policy A",
                    },
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured_kwargs.get("source_filter") == "Policy A"

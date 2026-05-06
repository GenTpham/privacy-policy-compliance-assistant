"""
backend/app/tests/test_sources_endpoint.py
Phase 9 Plan 01 HTTP-level tests for GET /api/sources endpoint and
ChatRequest.source_filter propagation in POST /api/chat.

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
    """Override get_current_user — returns a dummy User without DB/JWT checks."""
    return User(id=1, username="test", hashed_password="$argon2id$stub")


async def _minimal_done_stream(*args, **kwargs):
    """Minimal stream stub — yields one done event."""
    yield {"type": "done", "answer": "stubbed", "citations": []}


# ── GET /api/sources ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sources_authenticated_returns_200():
    """GET /api/sources returns HTTP 200 with {sources: list} when authenticated."""
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_current_user
    try:
        with patch("backend.app.services.rag.get_distinct_sources", new=AsyncMock(return_value=["Policy A", "Policy B"])):
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
    assert data["sources"] == ["Policy A", "Policy B"]


@pytest.mark.asyncio
async def test_sources_unauthenticated_returns_401():
    """GET /api/sources returns HTTP 401 when no bearer token provided."""
    app = create_app()
    # No override — real get_current_user which requires a valid token
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/sources")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sources_qdrant_exception_returns_500():
    """GET /api/sources returns HTTP 500 with detail when Qdrant raises an exception."""
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_current_user
    try:
        with patch(
            "backend.app.services.rag.get_distinct_sources",
            new=AsyncMock(side_effect=Exception("Qdrant connection error")),
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
                    json={"message": "what is the policy?", "history": [], "source_filter": "Google Privacy Policy"},
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

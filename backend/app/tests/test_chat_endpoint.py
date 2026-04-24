"""
backend/app/tests/test_chat_endpoint.py
HTTP-level tests for POST /api/chat endpoint.
Uses httpx.AsyncClient with ASGITransport — no live server needed.

Run: pytest backend/app/tests/test_chat_endpoint.py -x -v
"""
import pytest


# ── RAG-05 smoke: content-type is text/event-stream ──────────────────────────

@pytest.mark.asyncio
async def test_endpoint_content_type():
    """
    RAG-05 smoke: POST /api/chat returns HTTP 200 with Content-Type: text/event-stream.
    Uses httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app())).
    """
    pytest.skip("stub — implemented in Wave 1")


# ── D-05 / T-02-02: role='system' in history rejected with 422 ───────────────

@pytest.mark.asyncio
async def test_system_role_rejected():
    """
    Security (T-02-02): POST /api/chat with history=[{role:'system', content:'...'}]
    must return HTTP 422 (Pydantic validation error — Literal['user','assistant'] rejects 'system').
    This verifies the prompt injection mitigation from RESEARCH.md Pitfall 3.
    """
    pytest.skip("stub — implemented in Wave 1")

"""
backend/app/tests/test_rate_limit.py
Phase 10 rate limiting tests.

Test → Requirement mapping:
  test_rate_limit_returns_429   → AUTH-06 (per-user 429 when limit exceeded)
  test_rate_limit_per_user      → AUTH-06 (different users have independent counters)
"""
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import User
from backend.app.services.auth import hash_password
from backend.app.services import rag as rag_module


# ── Helpers ─────────────────────────────────────────────────────────────────────

async def _seed_user(
    db_session: AsyncSession,
    username: str = "ratelimituser",
    password: str = "password123",
    is_admin: bool = False,
) -> User:
    """Insert a User into the test DB and return it."""
    user = User(
        username=username,
        hashed_password=hash_password(password),
        is_admin=is_admin,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _login(client, username: str, password: str = "password123") -> str:
    """Login and return access token."""
    resp = await client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


async def _mock_stream(*args, **kwargs):
    """Minimal mock for rag.stream_answer — yields a single done event."""
    yield {"type": "done", "answer": "ok", "citations": []}


# ── Tests ────────────────────────────────────────────────────────────────────────

async def test_rate_limit_returns_429(rate_limited_client, db_session):
    """
    POST /api/chat exceeds per-user rate limit → HTTP 429 on second request (AUTH-06).

    Strategy: patch _get_chat_rate_limit to return "1/minute" so the limit is 1 req/min.
    First request succeeds; second request is rejected with 429.
    """
    user = await _seed_user(db_session, username="rlu1")
    token = await _login(rate_limited_client, "rlu1")
    headers = {"Authorization": f"Bearer {token}"}

    with patch.object(rag_module, "stream_answer", _mock_stream):
        with patch.object(rag_module, "stream_conflict_answer", _mock_stream):
            with patch("backend.app.core.limiter.get_settings", return_value=type("S", (), {"rate_limit_per_minute": 1, "jwt_secret": "a" * 32})()):
                r1 = await rate_limited_client.post(
                    "/api/chat",
                    json={"message": "test", "history": []},
                    headers=headers,
                )
                r2 = await rate_limited_client.post(
                    "/api/chat",
                    json={"message": "test", "history": []},
                    headers=headers,
                )

    assert r1.status_code != 429, f"First request should succeed, got {r1.status_code}"
    assert r2.status_code == 429, f"Second request should be rate limited, got {r2.status_code}"


async def test_rate_limit_per_user(rate_limited_client, db_session):
    """
    Two different users have independent rate limit counters (AUTH-06).

    Strategy: patch limit to "1/minute". User A hits the limit. User B should
    still succeed on their first request.
    """
    user_a = await _seed_user(db_session, username="usera")
    user_b = await _seed_user(db_session, username="userb")
    token_a = await _login(rate_limited_client, "usera")
    token_b = await _login(rate_limited_client, "userb")

    with patch.object(rag_module, "stream_answer", _mock_stream):
        with patch.object(rag_module, "stream_conflict_answer", _mock_stream):
            with patch("backend.app.core.limiter.get_settings", return_value=type("S", (), {"rate_limit_per_minute": 1, "jwt_secret": "a" * 32})()):
                # User A: first request succeeds, second is rate limited
                ra1 = await rate_limited_client.post(
                    "/api/chat",
                    json={"message": "test", "history": []},
                    headers={"Authorization": f"Bearer {token_a}"},
                )
                ra2 = await rate_limited_client.post(
                    "/api/chat",
                    json={"message": "test", "history": []},
                    headers={"Authorization": f"Bearer {token_a}"},
                )
                # User B: first request should succeed (independent counter)
                rb1 = await rate_limited_client.post(
                    "/api/chat",
                    json={"message": "test", "history": []},
                    headers={"Authorization": f"Bearer {token_b}"},
                )

    assert ra1.status_code != 429, f"User A first request should succeed, got {ra1.status_code}"
    assert ra2.status_code == 429, f"User A second request should be rate limited, got {ra2.status_code}"
    assert rb1.status_code != 429, f"User B first request should succeed (independent counter), got {rb1.status_code}"

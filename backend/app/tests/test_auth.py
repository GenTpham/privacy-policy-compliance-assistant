"""
backend/app/tests/test_auth.py
Wave 0 stubs for Phase 3 authentication requirements.
All tests skip — implemented in Wave 2 (plans 02-03).

Test → Requirement mapping:
  test_login_valid                → AUTH-01
  test_login_wrong_password       → AUTH-01
  test_login_unknown_user         → AUTH-01
  test_chat_requires_auth         → AUTH-02
  test_chat_with_valid_token      → AUTH-02
  test_refresh_valid              → AUTH-03
  test_refresh_wrong_type         → AUTH-03
  test_refresh_expired            → AUTH-03
  test_password_stored_as_argon2  → AUTH-04
  test_short_jwt_secret_rejected  → AUTH-05
"""
import pytest

# Wave 0: all stubs skip before fixtures run — CI never blocked by missing Wave 1 modules.
pytestmark = pytest.mark.skip("stub — implemented in Wave 1")


# ── AUTH-01: Login endpoint ────────────────────────────────────────────────────

async def test_login_valid(auth_client, db_session):
    """POST /auth/login with correct creds → 200 + access_token + refresh_token (D-06)."""


async def test_login_wrong_password(auth_client, db_session):
    """POST /auth/login with wrong password → 401."""


async def test_login_unknown_user(auth_client, db_session):
    """POST /auth/login with username that does not exist → 401."""


# ── AUTH-02: Chat endpoint protection ─────────────────────────────────────────

async def test_chat_requires_auth(auth_client):
    """POST /api/chat without Authorization header → 401."""


async def test_chat_with_valid_token(auth_client, db_session):
    """POST /api/chat with valid Bearer access token → not 401 (auth passes)."""


# ── AUTH-03: Token refresh ─────────────────────────────────────────────────────

async def test_refresh_valid(auth_client, db_session):
    """POST /auth/refresh with valid refresh token → 200 + new access_token (D-07)."""


async def test_refresh_wrong_type(auth_client, db_session):
    """POST /auth/refresh with an access token (type mismatch) → 401 (D-04)."""


async def test_refresh_expired(auth_client, db_session):
    """POST /auth/refresh with an expired refresh token → 401."""


# ── AUTH-04: Password hashing ──────────────────────────────────────────────────

async def test_password_stored_as_argon2(db_session):
    """Seeded user hashed_password starts with '$argon2id$' — no plaintext."""


# ── AUTH-05: JWT secret validation ────────────────────────────────────────────

def test_short_jwt_secret_rejected():
    """Startup with jwt_secret shorter than 32 chars raises ValueError."""

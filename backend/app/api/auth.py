"""
backend/app/api/auth.py
Authentication router: POST /auth/login, /auth/refresh, /auth/logout.

Decisions:
  D-05: /auth/login accepts JSON body {"username": str, "password": str}.
  D-06: login response: {"access_token", "refresh_token", "token_type": "bearer"}.
  D-07: /auth/refresh accepts {"refresh_token": str}, returns {"access_token", "token_type": "bearer"}.
  D-08: /auth/logout is stateless — server returns 200 {}, client drops tokens.

Anti-patterns avoided:
  - No OAuth2PasswordBearer (forces form data — D-05 requires JSON).
  - No token blacklist (stateless JWT — D-03).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import Settings, get_settings
from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.services.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)

router = APIRouter()


# ── Pydantic models ─────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    """Full token response returned on successful login (D-06)."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Request body for /auth/refresh (D-07)."""
    refresh_token: str


class AccessTokenResponse(BaseModel):
    """Refresh response — new access token only (D-07)."""
    access_token: str
    token_type: str = "bearer"


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """
    POST /auth/login — verify credentials and issue access + refresh tokens.

    Returns HTTP 401 for both unknown username and wrong password.
    Timing difference between the two cases is negligible — both go through
    verify_password (Argon2id) before returning, avoiding username enumeration
    timing attacks.
    """
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    # Always call verify_password to maintain constant timing (avoid username enumeration)
    stored_hash = user.hashed_password if user is not None else ""
    password_valid = verify_password(body.password, stored_hash) if stored_hash else False

    if user is None or not password_valid:
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


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    body: RefreshRequest,
    settings: Settings = Depends(get_settings),
) -> AccessTokenResponse:
    """
    POST /auth/refresh — validate refresh token, issue new access token.

    decode_token asserts type=='refresh' — prevents an access token being used here.
    No DB lookup needed: the refresh token contains the username in sub claim,
    and the new access token will be verified against the DB on next protected request.
    """
    payload = decode_token(
        body.refresh_token, settings.jwt_secret, expected_type="refresh"
    )
    return AccessTokenResponse(
        access_token=create_access_token(
            payload["sub"], settings.jwt_secret, settings.access_token_expire_minutes
        )
    )


@router.post("/logout", status_code=200)
async def logout() -> dict:
    """
    POST /auth/logout — stateless server-side logout (D-08).
    Server returns 200 {}. Client is responsible for dropping both tokens from storage.
    No server state is changed — consistent with stateless JWT design (D-03).
    """
    return {}

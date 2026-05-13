"""
backend/app/services/auth.py
JWT token creation/verification (PyJWT 2.12.1) and password hashing (pwdlib 0.3.0).
Also exposes the get_current_user FastAPI dependency used on all protected routes.

Key decisions:
  D-03: Stateless JWT refresh tokens — same secret as access tokens, distinguished by type claim.
  D-04: payload["type"] in {"access", "refresh"} — decode_token enforces expected_type.
  D-09: HTTPBearer(auto_error=False) — raises our own 401 with WWW-Authenticate header.
  AUTH-05: jwt_secret < 32 chars → ValueError raised at startup (not here — in lifespan).

Anti-patterns avoided:
  - Never catch jwt.ExpiredSignatureError alone — catch jwt.InvalidTokenError (base class).
  - Never use PasswordHash() without arguments — use PasswordHash.recommended() for Argon2id.
  - Never use OAuth2PasswordBearer (forces form data; D-05 requires JSON body).
  - Never re-query DB in require_admin — read is_admin from JWT payload (D-04).
"""
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import Settings, get_settings
from backend.app.db.models import User
from backend.app.db.session import get_db

# ── Password hashing ────────────────────────────────────────────────────────────

# Module-level singleton — PasswordHash.recommended() configures Argon2id with secure defaults.
# Creating per-request would re-tune parameters each time (slow and unnecessary).
_password_hasher = PasswordHash.recommended()

# Sentinel hash used when no user is found — ensures verify_password (Argon2id) is always
# called so the timing cost is paid regardless of whether the username exists.
# This prevents username enumeration via response latency.
_DUMMY_HASH: str = _password_hasher.hash("__dummy__")


def hash_password(plain: str) -> str:
    """Hash a plaintext password using Argon2id. Returns '$argon2id$...' string."""
    return _password_hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify plaintext against an Argon2id hash. Timing-safe (built into pwdlib)."""
    return _password_hasher.verify(plain, hashed)


# ── JWT token creation ──────────────────────────────────────────────────────────

def create_access_token(sub: str, secret: str, expire_minutes: int,
                        is_admin: bool = False) -> str:
    """
    Encode a short-lived access token.
    Payload: sub, type='access', iat, exp (now + expire_minutes), is_admin (D-04).
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
        "is_admin": is_admin,     # D-04: embedded for stateless admin check
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def create_refresh_token(sub: str, secret: str, expire_days: int) -> str:
    """
    Encode a long-lived refresh token.
    Payload: sub, type='refresh', iat, exp (now + expire_days).
    D-04: type='refresh' prevents this token from being accepted as an access token.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=expire_days),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


# ── JWT token verification ──────────────────────────────────────────────────────

def decode_token(token: str, secret: str, expected_type: str) -> dict:
    """
    Decode and verify a JWT. Raises HTTP 401 on any failure.

    Args:
        token: Raw JWT string (without 'Bearer ' prefix — HTTPBearer strips that).
        secret: HS256 signing secret from settings.jwt_secret.
        expected_type: 'access' or 'refresh' — must match payload['type'].

    Raises:
        HTTPException(401): If token is invalid, expired, or wrong type.

    Note: Catches jwt.InvalidTokenError (base class for ExpiredSignatureError,
    DecodeError, InvalidSignatureError) — never catch only one subclass.
    """
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


# ── FastAPI dependency ──────────────────────────────────────────────────────────

# Module-level HTTPBearer instance — auto_error=False so we raise our own 401
# with WWW-Authenticate header instead of FastAPI's default 403.
_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """
    FastAPI dependency — extracts and verifies the Bearer token, returns the User record.

    Flow:
      1. HTTPBearer extracts 'Authorization: Bearer <token>' header (None if absent).
      2. decode_token validates signature, expiry, and type='access'.
      3. User record is loaded from DB by username in payload['sub'].
      4. 401 is raised at any failure point with WWW-Authenticate: Bearer header.

    Inject into routes via: current_user: User = Depends(get_current_user)
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(
        credentials.credentials, settings.jwt_secret, expected_type="access"
    )
    username: str = payload["sub"]
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    FastAPI dependency — raises HTTP 403 if the JWT token does not carry is_admin=True.

    D-04: reads is_admin from token payload — no DB query on every admin request.
    The is_admin claim is embedded at login time via create_access_token.

    Usage: _admin: dict = Depends(require_admin) on every admin endpoint.

    Anti-patterns avoided:
      - Never re-query DB here — read is_admin from JWT payload (D-04).
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials, settings.jwt_secret,
                           expected_type="access")
    if not payload.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return payload

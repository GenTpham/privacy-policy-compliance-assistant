"""
backend/app/core/limiter.py
Module-level slowapi Limiter singleton — extracted here to avoid circular import.

chat.py imports limiter from this module.
main.py imports limiter from this module to wire app.state.limiter.

Decisions:
  D-05: slowapi Limiter with custom key_func.
  D-06: MemoryStorage (default) — in-memory, resets on container restart.
  D-09: Rate limit key is the authenticated username (payload['sub']); falls back
        to client IP if the token is absent or cannot be decoded. key_func runs
        before FastAPI resolves Depends(get_current_user), so the fallback is
        necessary for defensive correctness.

Anti-patterns avoided:
  - Do not import chat_router or admin_router here — that creates circular imports.
  - Do not import limiter from main.py in chat.py — main.py imports chat_router.
"""
import jwt as pyjwt
from slowapi import Limiter
from starlette.requests import Request

from backend.app.core.config import get_settings


def _get_rate_limit_key(request: Request) -> str:
    """
    key_func for slowapi — returns the authenticated username prefixed with 'user:'
    so per-user counting is distinct from IP-based fallback keys.

    Falls back to 'ip:<host>' on any decode error. This is intentional: the key_func
    runs before FastAPI dependency injection resolves get_current_user, so the
    function can receive requests with invalid or absent tokens.

    D-09: username-based keying; rotating tokens for the same user hit the same counter.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            settings = get_settings()
            payload = pyjwt.decode(
                auth[7:], settings.jwt_secret, algorithms=["HS256"]
            )
            return f"user:{payload['sub']}"
        except Exception:
            pass
    host = request.client.host if request.client else "anon"
    return f"ip:{host}"


def _get_chat_rate_limit(request: Request) -> str:
    """
    Dynamic limit string — reads RATE_LIMIT_PER_MINUTE from Settings (D-08).
    Passed as a callable to @limiter.limit() so changing the env var takes effect
    without a code change.
    """
    return f"{get_settings().rate_limit_per_minute}/minute"


limiter = Limiter(key_func=_get_rate_limit_key)

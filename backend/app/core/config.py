"""
backend/app/core/config.py
Pydantic-settings configuration — reads secrets from .env at startup.
Missing required fields raise ValidationError immediately (fail-fast pattern).
"""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Required — no default. Missing value raises ValidationError at startup.
    openrouter_api_key: str
    jwt_secret: str

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                f"JWT_SECRET must be at least 32 characters (got {len(v)}). "
                "Generate with: openssl rand -hex 32"
            )
        return v

    # Qdrant connection — override QDRANT_HOST to "qdrant" inside Docker Compose
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None

    # JWT configuration (used in Phase 3+)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Auth — Phase 3 additions
    refresh_token_expire_days: int = 7
    admin_username: str | None = None   # Optional — skip seed if not set (D-01)
    admin_password: str | None = None   # Optional — skip seed if not set (D-01)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    """
    Return a singleton Settings instance.
    @lru_cache ensures Settings() is called once per process.
    Raises pydantic_core.ValidationError if required env vars are absent.
    """
    return Settings()

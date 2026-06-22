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

    # Qdrant Cloud — full cluster URL and API key (no host/port)
    qdrant_url: str
    qdrant_api_key: str
    # REST timeout (seconds); Cloud upserts with wait=True often exceed the 5s client default
    qdrant_timeout_seconds: int = 120
    # Set true in tests only — skips Cloud collection verification at startup
    qdrant_skip_startup_verify: bool = False

    # JWT configuration (used in Phase 3+)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Auth — Phase 3 additions
    refresh_token_expire_days: int = 7
    admin_username: str | None = None   # Optional — skip seed if not set (D-01)
    admin_password: str | None = None   # Optional — skip seed if not set (D-01)

    # Neo4j configuration
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str

    # Observability — Phoenix OTLP/gRPC collector endpoint
    # Override via PHOENIX_COLLECTOR_ENDPOINT env var when using --profile observability
    phoenix_collector_endpoint: str = "http://phoenix:4317"

    # RAG retrieval threshold — overridable via SCORE_THRESHOLD env var.
    # Calibrated in Phase 7 (2026-05-05): set to 0.20 based on score distribution
    # analysis of 100 validation examples. See ANALYSIS.md in phases/07-eval-calibration/.
    # Hard floor: >= 0.20 (D-06). Nemotron cosine scores for relevant matches: 0.32–0.64
    # in 150-sample distribution; no scores observed in 0.20–0.32 range (threshold not
    # filtering). Root cause of 23% context_hit is ranking mismatch, not threshold.
    score_threshold: float = 0.20  # calibrated; was 0.25
    rate_limit_per_minute: int = 60  # D-08: overridable via RATE_LIMIT_PER_MINUTE env var

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    """
    Return a singleton Settings instance.
    @lru_cache ensures Settings() is called once per process.
    Raises pydantic_core.ValidationError if required env vars are absent.
    """
    return Settings()

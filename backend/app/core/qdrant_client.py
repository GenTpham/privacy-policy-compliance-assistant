"""Shared AsyncQdrantClient factory — URL + API key from Settings."""
from qdrant_client import AsyncQdrantClient

from backend.app.core.config import Settings


def require_qdrant_settings(settings: Settings) -> tuple[str, str]:
    url = settings.qdrant_url.strip()
    api_key = settings.qdrant_api_key.strip()
    if not url:
        raise RuntimeError("QDRANT_URL is required. Set QDRANT_URL in .env.")
    if not api_key:
        raise RuntimeError("QDRANT_API_KEY is required. Set QDRANT_API_KEY in .env.")
    return url, api_key


def make_qdrant_client(settings: Settings) -> AsyncQdrantClient:
    url, api_key = require_qdrant_settings(settings)
    return AsyncQdrantClient(
        url=url,
        api_key=api_key,
        timeout=settings.qdrant_timeout_seconds,
    )

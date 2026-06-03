import os
from unittest.mock import patch

import pytest

from backend.app.core.config import Settings

os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")
os.environ.setdefault("JWT_SECRET", "x" * 32)
os.environ.setdefault("QDRANT_URL", "https://cluster.qdrant.io")
os.environ.setdefault("QDRANT_API_KEY", "qdrant_key")

from backend.ingestion import ingest


def _make_settings(**overrides) -> Settings:
    return Settings(
        openrouter_api_key="test-openrouter-key",
        jwt_secret="x" * 32,
        qdrant_url=overrides.get("qdrant_url"),
        qdrant_api_key=overrides.get("qdrant_api_key"),
    )


def test_require_qdrant_cloud_settings_missing_url():
    settings = _make_settings(qdrant_url=None, qdrant_api_key="qdrant_key")
    with pytest.raises(RuntimeError, match="QDRANT_URL"):
        ingest._require_qdrant_cloud_settings(settings)


def test_require_qdrant_cloud_settings_missing_api_key():
    settings = _make_settings(qdrant_url="https://cluster.qdrant.io", qdrant_api_key=None)
    with pytest.raises(RuntimeError, match="QDRANT_API_KEY"):
        ingest._require_qdrant_cloud_settings(settings)


def test_make_qdrant_client_uses_url_and_api_key():
    settings = _make_settings(
        qdrant_url="https://cluster.qdrant.io",
        qdrant_api_key="qdrant_key",
    )
    with patch("backend.ingestion.ingest.AsyncQdrantClient") as mock_client:
        ingest._make_qdrant_client(settings)
    mock_client.assert_called_once_with(
        url="https://cluster.qdrant.io",
        api_key="qdrant_key",
    )

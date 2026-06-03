from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.config import Settings
from backend.app.core import qdrant_client as qc
from backend.app.core import qdrant_startup as qs


def _make_settings(**overrides) -> Settings:
    return Settings(
        openrouter_api_key="test-openrouter-key",
        jwt_secret="x" * 32,
        qdrant_url=overrides.get("qdrant_url", "https://cluster.qdrant.io"),
        qdrant_api_key=overrides.get("qdrant_api_key", "qdrant_key"),
    )


def test_require_qdrant_settings_missing_url():
    settings = _make_settings(qdrant_url="  ")
    with pytest.raises(RuntimeError, match="QDRANT_URL"):
        qc.require_qdrant_settings(settings)


def test_require_qdrant_settings_missing_api_key():
    settings = _make_settings(qdrant_api_key="")
    with pytest.raises(RuntimeError, match="QDRANT_API_KEY"):
        qc.require_qdrant_settings(settings)


@pytest.mark.asyncio
async def test_ensure_title_facet_index_skips_when_present():
    qdrant = AsyncMock()
    qdrant.get_collection = AsyncMock(return_value=MagicMock(payload_schema={"title": {}}))
    await qs.ensure_title_facet_index(qdrant)
    qdrant.create_payload_index.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_title_facet_index_creates_when_missing():
    from qdrant_client.models import PayloadSchemaType

    qdrant = AsyncMock()
    qdrant.get_collection = AsyncMock(return_value=MagicMock(payload_schema={}))
    await qs.ensure_title_facet_index(qdrant)
    qdrant.create_payload_index.assert_called_once_with(
        collection_name=qs.COLLECTION_NAME,
        field_name="title",
        field_schema=PayloadSchemaType.KEYWORD,
    )


def test_make_qdrant_client_uses_url_and_api_key():
    settings = _make_settings(
        qdrant_url="https://cluster.qdrant.io",
        qdrant_api_key="qdrant_key",
    )
    with patch("backend.app.core.qdrant_client.AsyncQdrantClient") as mock_client:
        qc.make_qdrant_client(settings)
    mock_client.assert_called_once_with(
        url="https://cluster.qdrant.io",
        api_key="qdrant_key",
        timeout=120,
    )

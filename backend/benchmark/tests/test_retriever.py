"""Tests for benchmark retriever."""
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

import pytest

from backend.benchmark.retriever import retrieve_chunks, RetrievalResult


@pytest.fixture
def mock_qdrant():
    client = AsyncMock()
    point = SimpleNamespace(
        id="test-id",
        score=0.85,
        payload={"doc_id": "doc1", "text": "sample text", "chunk_index": 0},
    )
    client.query_points.return_value = SimpleNamespace(points=[point])
    return client


@pytest.fixture
def mock_openrouter():
    client = AsyncMock()
    embedding_data = SimpleNamespace(embedding=[0.1] * 768, index=0)
    client.embeddings.create.return_value = SimpleNamespace(data=[embedding_data])
    return client


class TestRetrieveChunks:
    @pytest.mark.asyncio
    async def test_returns_retrieval_result(self, mock_qdrant, mock_openrouter):
        result = await retrieve_chunks(
            query="test question",
            collection_name="test_collection",
            qdrant=mock_qdrant,
            openrouter=mock_openrouter,
            top_k=5,
        )
        assert isinstance(result, RetrievalResult)
        assert len(result.chunks) == 1
        assert result.chunks[0]["text"] == "sample text"
        assert result.chunks[0]["score"] == 0.85

    @pytest.mark.asyncio
    async def test_calls_qdrant_with_correct_params(self, mock_qdrant, mock_openrouter):
        await retrieve_chunks(
            query="test",
            collection_name="my_collection",
            qdrant=mock_qdrant,
            openrouter=mock_openrouter,
            top_k=3,
        )
        mock_qdrant.query_points.assert_called_once()
        call_kwargs = mock_qdrant.query_points.call_args.kwargs
        assert call_kwargs["collection_name"] == "my_collection"
        assert call_kwargs["limit"] == 3

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_qdrant, mock_openrouter):
        mock_qdrant.query_points.return_value = SimpleNamespace(points=[])
        result = await retrieve_chunks(
            query="nothing",
            collection_name="empty",
            qdrant=mock_qdrant,
            openrouter=mock_openrouter,
        )
        assert result.chunks == []
        assert result.doc_ids == []

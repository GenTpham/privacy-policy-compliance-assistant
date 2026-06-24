"""Tests for LLM context enrichment with mocked OpenRouter API."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.ingestion.chunker import Chunk
from backend.ingestion.llm_enricher import (
    enrich_chunk,
    enrich_chunks_batch,
    ENRICHMENT_PROMPT_TEMPLATE,
    MAX_CONCURRENCY,
)


def _make_chunk(text: str = "Sample chunk text", context_header: str = "") -> Chunk:
    return Chunk(
        text=text,
        title="Test Policy",
        source_doc="test.pdf",
        passage_id="p1",
        chunk_index=0,
        token_count=10,
        context_header=context_header,
    )


class TestEnrichChunk:
    """Unit tests for single chunk enrichment."""

    @pytest.mark.asyncio
    async def test_enrich_prepends_llm_context(self):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="This chunk discusses data collection rules."))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        chunk = _make_chunk(text="We collect your email address.")
        result = await enrich_chunk(mock_client, chunk, full_passage="Full document text here.")

        assert result.llm_context == "This chunk discusses data collection rules."
        assert "This chunk discusses data collection rules." in result.enriched_text
        assert "We collect your email address." in result.enriched_text

    @pytest.mark.asyncio
    async def test_enrich_fallback_on_api_error(self):
        mock_client = AsyncMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        chunk = _make_chunk(text="We collect your email address.")
        result = await enrich_chunk(mock_client, chunk, full_passage="Full document text here.")

        # Should fallback gracefully — llm_context is empty, enriched_text still works
        assert result.llm_context == ""
        assert "We collect your email address." in result.enriched_text


class TestEnrichChunksBatch:
    """Tests for batch enrichment with concurrency control."""

    @pytest.mark.asyncio
    async def test_batch_enriches_all_chunks(self):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Context summary."))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        chunks = [_make_chunk(text=f"Chunk {i}") for i in range(5)]
        results = await enrich_chunks_batch(
            mock_client, chunks, full_passage="Full passage."
        )

        assert len(results) == 5
        for r in results:
            assert r.llm_context == "Context summary."

    @pytest.mark.asyncio
    async def test_batch_handles_partial_failures(self):
        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise Exception("Transient API failure")
            mock_resp = MagicMock()
            mock_resp.choices = [
                MagicMock(message=MagicMock(content="OK context."))
            ]
            return mock_resp

        mock_client = AsyncMock()
        mock_client.chat.completions.create.side_effect = side_effect

        chunks = [_make_chunk(text=f"Chunk {i}") for i in range(5)]
        results = await enrich_chunks_batch(
            mock_client, chunks, full_passage="Full passage."
        )

        assert len(results) == 5
        # The 3rd chunk (index 2) should have empty llm_context due to failure
        enriched_count = sum(1 for r in results if r.llm_context != "")
        assert enriched_count == 4  # 4 succeeded, 1 failed gracefully


class TestPromptTemplate:
    """The prompt template should contain required placeholders."""

    def test_template_has_required_placeholders(self):
        assert "{full_passage}" in ENRICHMENT_PROMPT_TEMPLATE
        assert "{chunk_text}" in ENRICHMENT_PROMPT_TEMPLATE


class TestConcurrencyLimit:
    """MAX_CONCURRENCY should be a reasonable value for OpenRouter free tier."""

    def test_max_concurrency_is_set(self):
        assert isinstance(MAX_CONCURRENCY, int)
        assert 1 <= MAX_CONCURRENCY <= 100

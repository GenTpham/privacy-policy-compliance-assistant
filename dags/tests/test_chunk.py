"""Tests for chunk_text DAG task logic."""
import json

import pytest

from dags.tasks.chunk import chunk_text_content


class TestChunkTextContent:
    def test_chunks_short_text_into_single_chunk(self):
        text = "This is a short policy document about data privacy."
        chunks = chunk_text_content(
            text=text,
            doc_id="doc-1",
            title="Privacy Policy",
            tenant_id="tenant-1",
            user_id="user-1",
        )
        assert len(chunks) >= 1
        assert chunks[0]["text"] == text
        assert chunks[0]["title"] == "Privacy Policy"
        assert chunks[0]["doc_id"] == "doc-1"
        assert chunks[0]["tenant_id"] == "tenant-1"

    def test_chunks_long_text_into_multiple_chunks(self):
        # Create text longer than MAX_TOKENS (400 tokens ≈ ~1600 chars)
        text = "Privacy policy section. " * 200  # ~4800 chars ≈ 1200 tokens
        chunks = chunk_text_content(text, "doc-2", "Long Policy", "t-1", "u-1")
        assert len(chunks) > 1

    def test_each_chunk_has_required_fields(self):
        text = "Data retention policy for customer information."
        chunks = chunk_text_content(text, "doc-3", "Retention", "t-1", "u-1")
        for chunk in chunks:
            assert "id" in chunk
            assert "text" in chunk
            assert "title" in chunk
            assert "doc_id" in chunk
            assert "tenant_id" in chunk
            assert "user_id" in chunk
            assert "chunk_index" in chunk

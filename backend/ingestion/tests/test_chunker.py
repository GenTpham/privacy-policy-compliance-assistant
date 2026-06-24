"""Tests for the context-aware chunker."""
import pytest

from backend.ingestion.chunker import Chunk, chunk_passage, MAX_TOKENS, _count_tokens


class TestFastPath:
    """Passages that fit within MAX_TOKENS should return a single chunk."""

    def test_short_passage_returns_single_chunk(self):
        text = "This is a short passage about data collection."
        chunks = chunk_passage(
            text=text,
            passage_id="p1",
            title="Privacy Policy",
            source_doc="policy.pdf",
        )
        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].passage_id == "p1"
        assert "This is a short passage" in chunks[0].text

    def test_short_passage_token_count_accurate(self):
        text = "Short text for token counting."
        chunks = chunk_passage(
            text=text, passage_id="p2", title="T", source_doc="S"
        )
        assert chunks[0].token_count == _count_tokens(chunks[0].text)


class TestMarkdownHeaderTracking:
    """Chunks from documents with Markdown headers should include breadcrumb context."""

    def test_breadcrumb_injected_for_h1_h2(self):
        text = (
            "# Điều 1. Thu thập dữ liệu\n\n"
            "## Khoản 1. Thông tin cá nhân\n\n"
            "Chúng tôi thu thập họ tên và email của bạn.\n\n"
            "## Khoản 2. Thông tin thiết bị\n\n"
            "Chúng tôi ghi nhận địa chỉ IP mỗi lần đăng nhập."
        )
        chunks = chunk_passage(
            text=text, passage_id="md1", title="Chính sách Zalo", source_doc="zalo.pdf"
        )
        # All chunks should exist
        assert len(chunks) >= 1
        # First chunk should contain its header context
        assert "Điều 1" in chunks[0].context_header

    def test_no_headers_means_empty_context_header(self):
        text = "Plain text without any markdown headers at all."
        chunks = chunk_passage(
            text=text, passage_id="plain1", title="T", source_doc="S"
        )
        assert chunks[0].context_header == ""


class TestListPreservation:
    """List items should not be split mid-list."""

    def test_numbered_list_kept_together(self):
        # Build a list that fits in one chunk
        items = [f"{i}. Item number {i} with some description text." for i in range(1, 6)]
        text = "Introduction paragraph.\n\n" + "\n".join(items)
        chunks = chunk_passage(
            text=text, passage_id="list1", title="T", source_doc="S"
        )
        # The list should not be split across chunks if it fits
        full_text = " ".join(c.text for c in chunks)
        for item in items:
            assert item in full_text

    def test_bullet_list_not_split_mid_item(self):
        items = [f"- Bullet point {i} explaining a policy rule." for i in range(1, 4)]
        text = "## Rules\n\n" + "\n".join(items)
        chunks = chunk_passage(
            text=text, passage_id="bullet1", title="T", source_doc="S"
        )
        # Each chunk should contain complete bullet points (no partial lines)
        for chunk in chunks:
            lines = [l for l in chunk.text.split("\n") if l.strip()]
            for line in lines:
                # A line starting with "- " should not be truncated mid-word
                if line.strip().startswith("- Bullet"):
                    assert line.strip().endswith(".")


class TestLongPassageSplitting:
    """Passages exceeding MAX_TOKENS must be split."""

    def test_long_passage_splits_within_token_limit(self):
        # Generate a passage that definitely exceeds MAX_TOKENS
        long_text = "This is a sentence about data privacy. " * 200
        chunks = chunk_passage(
            text=long_text, passage_id="long1", title="T", source_doc="S"
        )
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.token_count <= MAX_TOKENS + 10  # small tolerance for edge rounding

    def test_chunk_indices_are_sequential(self):
        long_text = "Word " * 500
        chunks = chunk_passage(
            text=long_text, passage_id="seq1", title="T", source_doc="S"
        )
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i


class TestTokenBudget:
    """MAX_TOKENS should be 350 (safety buffer for Nemotron tokenizer mismatch)."""

    def test_max_tokens_is_350(self):
        assert MAX_TOKENS == 350


class TestChunkDataclass:
    """Chunk dataclass should include the new context_header field."""

    def test_chunk_has_context_header(self):
        chunk = Chunk(
            text="some text",
            title="T",
            source_doc="S",
            passage_id="p1",
            chunk_index=0,
            token_count=5,
            context_header="[Source: T | Context: H1 > H2]",
        )
        assert chunk.context_header == "[Source: T | Context: H1 > H2]"

    def test_enriched_text_combines_header_and_text(self):
        chunk = Chunk(
            text="some text",
            title="T",
            source_doc="S",
            passage_id="p1",
            chunk_index=0,
            token_count=5,
            context_header="[Source: T | Context: H1]",
        )
        assert chunk.enriched_text == "[Source: T | Context: H1]\n\nsome text"

    def test_enriched_text_without_header(self):
        chunk = Chunk(
            text="some text",
            title="T",
            source_doc="S",
            passage_id="p1",
            chunk_index=0,
            token_count=5,
            context_header="",
        )
        assert chunk.enriched_text == "some text"

    def test_enriched_text_with_llm_context(self):
        chunk = Chunk(
            text="some text",
            title="T",
            source_doc="S",
            passage_id="p1",
            chunk_index=0,
            token_count=5,
            context_header="[Source: T | Context: H1]",
            llm_context="This chunk explains data retention rules.",
        )
        expected = "[Source: T | Context: H1]\n\nThis chunk explains data retention rules.\n\nsome text"
        assert chunk.enriched_text == expected

"""Tests for the naive fixed-size chunker (baseline)."""
from backend.benchmark.naive_chunker import naive_chunk


class TestNaiveChunk:
    """Test the naive character-based chunker."""

    def test_short_text_returns_single_chunk(self):
        result = naive_chunk("Hello world", chunk_size=1000)
        assert len(result) == 1
        assert result[0] == "Hello world"

    def test_long_text_splits_at_chunk_size(self):
        text = "A" * 2500
        result = naive_chunk(text, chunk_size=1000)
        assert len(result) == 3
        assert len(result[0]) == 1000
        assert len(result[1]) == 1000
        assert len(result[2]) == 500

    def test_empty_text_returns_empty_list(self):
        result = naive_chunk("", chunk_size=1000)
        assert result == []

    def test_whitespace_only_returns_empty_list(self):
        result = naive_chunk("   ", chunk_size=1000)
        assert result == []

    def test_exact_chunk_size_returns_one_chunk(self):
        text = "B" * 1000
        result = naive_chunk(text, chunk_size=1000)
        assert len(result) == 1

    def test_no_overlap_by_default(self):
        text = "abcdefghij" * 200  # 2000 chars, no repeating 10-char sequences across boundaries that easily match unless by chance
        result = naive_chunk(text, chunk_size=1000, overlap=0)
        # First chunk ends at char 1000, second starts at char 1000
        assert len(result) == 2
        # No shared overlap
        assert text[:1000] == result[0]
        assert text[1000:] == result[1]

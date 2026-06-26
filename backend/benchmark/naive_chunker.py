"""
Naive fixed-size character chunker — the baseline "lazy default" approach.

This intentionally does NO smart splitting: no sentence boundaries, no semantic
awareness, no markdown header tracking, no overlap. It represents the minimal
effort RAG approach that many enterprises use out of the box.
"""
from backend.benchmark.config import NAIVE_CHUNK_SIZE, NAIVE_CHUNK_OVERLAP


def naive_chunk(
    text: str,
    chunk_size: int = NAIVE_CHUNK_SIZE,
    overlap: int = NAIVE_CHUNK_OVERLAP,
) -> list[str]:
    """
    Split text into fixed-size character chunks with optional overlap.

    Args:
        text: Input text to chunk.
        chunk_size: Maximum characters per chunk.
        overlap: Number of overlapping characters between consecutive chunks.

    Returns:
        List of text chunks. Empty list if input is empty/whitespace.
    """
    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap if overlap > 0 else end

    return chunks

"""
Retrieve top-K chunks from a Qdrant collection for a given query.
Shared by both naive and optimized benchmark paths.
"""
from dataclasses import dataclass, field

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from backend.benchmark.config import EMBED_MODEL, TOP_K


@dataclass
class RetrievalResult:
    """Container for retrieval output."""
    chunks: list[dict] = field(default_factory=list)    # [{text, doc_id, score, chunk_index}]
    doc_ids: list[str] = field(default_factory=list)    # unique doc_ids in retrieval order

    @property
    def texts(self) -> list[str]:
        """Return chunk texts as a flat list (for Ragas contexts)."""
        return [c["text"] for c in self.chunks]


async def retrieve_chunks(
    query: str,
    collection_name: str,
    qdrant: AsyncQdrantClient,
    openrouter: AsyncOpenAI,
    top_k: int = TOP_K,
) -> RetrievalResult:
    """
    Embed query and retrieve top-K chunks from the specified collection.

    Args:
        query: The question text.
        collection_name: Qdrant collection to search.
        qdrant: Async Qdrant client.
        openrouter: Async OpenAI client (for embedding).
        top_k: Number of results to retrieve.

    Returns:
        RetrievalResult with chunks and doc_ids.
    """
    # Embed query
    resp = await openrouter.embeddings.create(
        model=EMBED_MODEL,
        input=[query],
        encoding_format="float",
    )
    query_vector = resp.data[0].embedding

    # Query Qdrant
    response = await qdrant.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    )

    chunks: list[dict] = []
    seen_doc_ids: list[str] = []

    for point in response.points:
        doc_id = point.payload.get("doc_id", "")
        chunks.append({
            "text": point.payload.get("text", ""),
            "doc_id": doc_id,
            "score": round(point.score, 4),
            "chunk_index": point.payload.get("chunk_index", 0),
        })
        if doc_id not in seen_doc_ids:
            seen_doc_ids.append(doc_id)

    return RetrievalResult(chunks=chunks, doc_ids=seen_doc_ids)

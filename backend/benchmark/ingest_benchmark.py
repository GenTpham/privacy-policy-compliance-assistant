"""
Ingest FiQA corpus into two Qdrant collections for benchmarking:
  - fiqa_naive_rag: naive fixed-size chunks
  - fiqa_optimized_rag: project's optimized chunker with context headers

Both collections use the same Nemotron embedding model via OpenRouter.
"""
import asyncio
import uuid

from openai import AsyncOpenAI
from qdrant_client.models import Distance, PointStruct, VectorParams

from backend.app.core.config import get_settings
from backend.app.core.qdrant_client import make_qdrant_client
from backend.benchmark.config import (
    EMBED_BATCH_SIZE,
    EMBED_MODEL,
    EMBED_SLEEP_SECONDS,
    NAIVE_COLLECTION,
    OPTIMIZED_COLLECTION,
)
from backend.benchmark.data_loader import FiQAData
from backend.benchmark.naive_chunker import naive_chunk
from backend.ingestion.chunker import chunk_passage
from backend.ingestion.ingest import embed_batch


async def _probe_dim(client: AsyncOpenAI) -> int:
    """Probe embedding dimension from the API."""
    resp = await client.embeddings.create(
        model=EMBED_MODEL, input="probe", encoding_format="float"
    )
    return len(resp.data[0].embedding)


async def _ensure_collection(qdrant, name: str, dim: int) -> None:
    """Create collection if it doesn't exist. Skip if it does."""
    existing = await qdrant.get_collections()
    existing_names = {c.name for c in existing.collections}
    if name in existing_names:
        print(f"[benchmark-ingest] Collection '{name}' already exists — skipping creation.")
        return
    await qdrant.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )
    print(f"[benchmark-ingest] Created collection '{name}' (dim={dim}, COSINE).")


async def _embed_and_upsert(
    qdrant,
    collection_name: str,
    chunks: list[dict],
) -> int:
    """
    Embed chunks and upsert into the specified collection.

    Args:
        chunks: list of {"id": str, "text": str} dicts.

    Returns:
        Number of points upserted.
    """
    total = len(chunks)
    upserted = 0

    for batch_start in range(0, total, EMBED_BATCH_SIZE):
        batch = chunks[batch_start : batch_start + EMBED_BATCH_SIZE]
        texts = [c["text"] for c in batch]

        embeddings = await embed_batch(texts)

        points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, c["id"])),
                vector=emb,
                payload={
                    "doc_id": c.get("doc_id", ""),
                    "text": c["text"],
                    "chunk_index": c.get("chunk_index", 0),
                },
            )
            for c, emb in zip(batch, embeddings)
        ]

        await qdrant.upsert(collection_name=collection_name, points=points, wait=True)
        upserted += len(batch)
        print(f"  [{collection_name}] {upserted}/{total} upserted")
        await asyncio.sleep(EMBED_SLEEP_SECONDS)

    return upserted


async def ingest_naive(qdrant, data: FiQAData, dim: int) -> int:
    """Ingest FiQA corpus using naive chunking into fiqa_naive_rag collection."""
    await _ensure_collection(qdrant, NAIVE_COLLECTION, dim)

    chunks: list[dict] = []
    for doc_id, text in data.corpus.items():
        doc_chunks = naive_chunk(text)
        for i, chunk_text in enumerate(doc_chunks):
            chunks.append({
                "id": f"naive-{doc_id}-{i}",
                "doc_id": doc_id,
                "text": chunk_text,
                "chunk_index": i,
            })

    print(f"[benchmark-ingest] Naive: {len(chunks)} chunks from {len(data.corpus)} docs")
    return await _embed_and_upsert(qdrant, NAIVE_COLLECTION, chunks)


async def ingest_optimized(qdrant, data: FiQAData, dim: int) -> int:
    """Ingest FiQA corpus using project's optimized chunker into fiqa_optimized_rag."""
    await _ensure_collection(qdrant, OPTIMIZED_COLLECTION, dim)

    chunks: list[dict] = []
    for doc_id, text in data.corpus.items():
        optimized_chunks = chunk_passage(
            text=text,
            passage_id=doc_id,
            title=f"FiQA-{doc_id}",
            source_doc=f"FiQA-{doc_id}",
        )
        for c in optimized_chunks:
            chunks.append({
                "id": f"opt-{doc_id}-{c.chunk_index}",
                "doc_id": doc_id,
                "text": c.enriched_text,
                "chunk_index": c.chunk_index,
            })

    print(f"[benchmark-ingest] Optimized: {len(chunks)} chunks from {len(data.corpus)} docs")
    return await _embed_and_upsert(qdrant, OPTIMIZED_COLLECTION, chunks)


async def ingest_both(data: FiQAData) -> dict:
    """
    Run full ingestion for both collections.

    Returns dict with counts: {"naive": N, "optimized": M}
    """
    settings = get_settings()
    openrouter = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
    )
    qdrant = make_qdrant_client(settings)

    dim = await _probe_dim(openrouter)
    print(f"[benchmark-ingest] Probed embedding dim: {dim}")

    naive_count = await ingest_naive(qdrant, data, dim)
    optimized_count = await ingest_optimized(qdrant, data, dim)

    return {"naive": naive_count, "optimized": optimized_count}

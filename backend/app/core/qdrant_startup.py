"""Startup/readiness checks for a pre-ingested Qdrant Cloud collection."""
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance

COLLECTION_NAME = "policies"


async def verify_qdrant_for_serving(qdrant: AsyncQdrantClient) -> int:
    """
    Confirm the policies collection exists on Qdrant Cloud and has indexed points.
    Does not create collections or run ingestion — deploy assumes one-time ingest already ran.
    """
    try:
        info = await qdrant.get_collection(COLLECTION_NAME)
    except UnexpectedResponse as exc:
        if "404" in str(exc) or "not found" in str(exc).lower():
            raise RuntimeError(
                f"Qdrant collection '{COLLECTION_NAME}' not found at QDRANT_URL. "
                "Index the corpus once against this cluster: python -m backend.ingestion.ingest"
            ) from exc
        raise
    except Exception as exc:
        raise RuntimeError(
            f"Cannot reach Qdrant at QDRANT_URL: {exc}. "
            "Check QDRANT_URL, QDRANT_API_KEY, and network access."
        ) from exc

    distance = info.config.params.vectors.distance
    if distance != Distance.COSINE:
        raise RuntimeError(
            f"Collection '{COLLECTION_NAME}' uses {distance}, expected COSINE. "
            "Delete the collection and re-run one-time ingestion."
        )

    count_result = await qdrant.count(collection_name=COLLECTION_NAME, exact=True)
    point_count = count_result.count
    if point_count == 0:
        raise RuntimeError(
            f"Collection '{COLLECTION_NAME}' is empty. "
            "Run one-time ingestion: python -m backend.ingestion.ingest"
        )

    dim = info.config.params.vectors.size
    print(
        f"[startup] Qdrant Cloud ready: collection='{COLLECTION_NAME}' "
        f"points={point_count} dim={dim} distance=COSINE"
    )
    return point_count


async def check_qdrant_ready(qdrant: AsyncQdrantClient) -> dict:
    """Lightweight readiness probe for /health/ready."""
    info = await qdrant.get_collection(COLLECTION_NAME)
    count_result = await qdrant.count(collection_name=COLLECTION_NAME, exact=True)
    return {
        "collection": COLLECTION_NAME,
        "points": count_result.count,
        "vector_dim": info.config.params.vectors.size,
        "distance": str(info.config.params.vectors.distance),
    }

"""
backend/app/main.py
FastAPI application factory.
Lifespan: probes embedding dimension, bootstraps Qdrant 'policies' collection.
"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from backend.app.api.chat import router as chat_router
from backend.app.core.config import get_settings
from backend.app.core.telemetry import setup_tracing

COLLECTION_NAME = "policies"


async def _probe_embedding_dim(client: AsyncOpenAI, model: str) -> int:
    """
    Call the embedding API once with a test string and return the vector dimension.
    Nemotron's output dimension is not documented — must be discovered at runtime.
    Never hardcode this value (AI-SPEC Critical Failure Mode 5).
    """
    resp = await client.embeddings.create(model=model, input="probe", encoding_format="float")
    dim = len(resp.data[0].embedding)
    print(f"[startup] Nemotron embedding dimension: {dim}")
    return dim


async def _ensure_collection(qdrant: AsyncQdrantClient, dim: int) -> None:
    """
    Create the 'policies' collection with COSINE distance if it does not exist.
    COSINE is IMMUTABLE after creation — verify after create (AI-SPEC §6 guardrail).
    Decision D-09: skip creation if collection already exists, proceed to verify.
    """
    existing = {c.name for c in (await qdrant.get_collections()).collections}
    if COLLECTION_NAME not in existing:
        await qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        print(f"[startup] Created collection '{COLLECTION_NAME}' (dim={dim}, COSINE).")
    else:
        print(f"[startup] Collection '{COLLECTION_NAME}' already exists — skipping creation.")

    # Guardrail: verify distance metric is COSINE regardless of whether we just created it
    info = await qdrant.get_collection(COLLECTION_NAME)
    actual_distance = info.config.params.vectors.distance
    if actual_distance != Distance.COSINE:
        raise RuntimeError(
            f"Collection '{COLLECTION_NAME}' distance metric is {actual_distance}, "
            f"expected COSINE. Delete the collection and re-ingest to fix. "
            f"This is an immutable collection property."
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI lifespan — runs at startup and shutdown.
    Startup: telemetry → probe embedding dim → bootstrap Qdrant collection.
    Shutdown: (nothing needed — Qdrant client has no persistent connection to close).
    """
    settings = get_settings()

    # Telemetry (gracefully skips if Phoenix is not running)
    setup_tracing()

    openrouter = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
        default_headers={
            "HTTP-Referer": "https://privacy-policy-assistant",
            "X-OpenRouter-Title": "Privacy Policy Assistant",
        },
    )
    qdrant = AsyncQdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        api_key=settings.qdrant_api_key,
    )

    dim = await _probe_embedding_dim(
        openrouter, "nvidia/llama-nemotron-embed-vl-1b-v2"
    )
    await _ensure_collection(qdrant, dim)

    print("[startup] FastAPI ready.")
    yield
    # Shutdown — nothing to close


def create_app() -> FastAPI:
    app = FastAPI(
        title="Privacy Policy Compliance Assistant",
        description="RAG-based chatbot for privacy policy Q&A with inline citations.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(chat_router, prefix="/api")
    return app


app = create_app()


@app.get("/health")
async def health() -> dict:
    """
    Liveness probe — returns 200 if the service is running.
    Does NOT check Qdrant connectivity (that is verified at startup).
    """
    return {"status": "ok"}

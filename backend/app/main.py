"""
backend/app/main.py
FastAPI application factory.
Lifespan: probes embedding dimension, bootstraps Qdrant 'policies' collection.
"""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select

from backend.app.api.admin import router as admin_router
from backend.app.api.auth import router as auth_router
from backend.app.api.chat import router as chat_router
from backend.app.api.sources import router as sources_router
from backend.app.core.config import get_settings
from backend.app.core.limiter import limiter
from backend.app.core.telemetry import setup_tracing
from backend.app.db.models import Base, User
from backend.app.db.session import init_db, get_db
from backend.app.services.auth import hash_password

COLLECTION_NAME = "policies"


async def _init_db_and_seed(settings) -> None:
    """
    Idempotent: create users table if not exists, seed admin user if env vars set.
    Called from lifespan. D-01: single user from ENV vars.
    D-13 (AUTH-05): jwt_secret length validated before this runs.
    """
    # Ensure backend/data/ directory exists (Research Open Question 1)
    Path("backend/data").mkdir(parents=True, exist_ok=True)

    db_url = "sqlite+aiosqlite:///backend/data/users.db"
    init_db(db_url)

    # Import session factory (available after init_db call)
    from backend.app.db.session import _session_factory

    # Create tables (idempotent — skips existing tables)
    from backend.app.db import session as db_session_mod
    engine = db_session_mod._engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed admin user from env vars if set
    if not settings.admin_username or not settings.admin_password:
        print("[startup] ADMIN_USERNAME/ADMIN_PASSWORD not set — skipping user seed.")
        return

    async with _session_factory() as session:
        result = await session.execute(
            select(User).where(User.username == settings.admin_username)
        )
        if result.scalar_one_or_none() is None:
            session.add(User(
                username=settings.admin_username,
                hashed_password=hash_password(settings.admin_password),
            ))
            await session.commit()
            print(f"[startup] Admin user '{settings.admin_username}' seeded.")
        else:
            print(f"[startup] Admin user '{settings.admin_username}' already exists.")


async def _migrate_add_is_admin_column(engine) -> None:
    """
    Add is_admin column to users table if not already present (D-02).
    SQLite's ALTER TABLE has no IF NOT EXISTS — must check PRAGMA table_info first.
    Safe to call on every startup; skipped if column exists.
    """
    from sqlalchemy import text

    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(users)"))
        columns = [row[1] for row in result.fetchall()]
        if "is_admin" not in columns:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0")
            )
            print("[startup] Migration: added is_admin column to users table.")
        else:
            print("[startup] Migration: is_admin column already exists — skipping.")


async def _patch_admin_is_admin(settings, session_factory) -> None:
    """
    Set is_admin=True on the seeded admin user (D-03).
    Idempotent — running UPDATE to same value is safe.
    Must run after _migrate_add_is_admin_column so the column exists.
    """
    if not settings.admin_username:
        return
    from sqlalchemy import update as sa_update

    async with session_factory() as session:
        await session.execute(
            sa_update(User)
            .where(User.username == settings.admin_username)
            .values(is_admin=True)
        )
        await session.commit()
        print(f"[startup] Admin user '{settings.admin_username}' patched to is_admin=True.")


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

    # AUTH-05: fail fast if jwt_secret is too short (< 32 chars)
    if len(settings.jwt_secret) < 32:
        raise ValueError(
            f"JWT_SECRET must be at least 32 characters long "
            f"(currently {len(settings.jwt_secret)} chars). "
            f"Generate one with: openssl rand -hex 32"
        )

    # Phase 3: Initialize DB and seed admin user
    await _init_db_and_seed(settings)

    # Phase 10: idempotent schema migration + admin user role patch
    from backend.app.db import session as db_session_mod
    await _migrate_add_is_admin_column(db_session_mod._engine)
    from backend.app.db.session import _session_factory
    await _patch_admin_is_admin(settings, _session_factory)

    # Telemetry — pass endpoint from settings so PHOENIX_COLLECTOR_ENDPOINT env var works
    # Gracefully skips if Phoenix is not running or packages are not installed
    setup_tracing(endpoint=settings.phoenix_collector_endpoint)

    openrouter = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
        default_headers={
            "HTTP-Referer": "https://privacy-policy-assistant",
            "X-OpenRouter-Title": "Privacy Policy Assistant",
        },
    )
    qdrant = AsyncQdrantClient(
        url=f"http://{settings.qdrant_host}:{settings.qdrant_port}",
        api_key=settings.qdrant_api_key or None,
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
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(chat_router, prefix="/api")
    app.include_router(auth_router, prefix="/auth")
    app.include_router(sources_router, prefix="/api")
    app.include_router(admin_router, prefix="/admin")
    return app


app = create_app()


@app.get("/health")
async def health() -> dict:
    """
    Liveness probe — returns 200 if the service is running.
    Does NOT check Qdrant connectivity (that is verified at startup).
    """
    return {"status": "ok"}

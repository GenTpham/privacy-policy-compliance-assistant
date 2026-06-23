"""
backend/app/main.py
FastAPI application factory.
Lifespan: verifies pre-ingested Qdrant Cloud collection (no ingest on startup).
"""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select

from backend.app.api.admin import router as admin_router
from backend.app.api.auth import router as auth_router
from backend.app.api.chat import router as chat_router
from backend.app.api.dashboard import router as dashboard_router
from backend.app.api.sources import router as sources_router
from backend.app.core.config import get_settings
from backend.app.core.qdrant_client import make_qdrant_client
from backend.app.core.qdrant_startup import check_qdrant_ready, verify_qdrant_for_serving
from backend.app.core.limiter import limiter
from backend.app.core.telemetry import setup_tracing
from backend.app.db.models import Base, User
from backend.app.db.session import init_db, get_db
from backend.app.services.auth import hash_password

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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI lifespan — runs at startup and shutdown.
    Startup: DB → verify pre-ingested Qdrant Cloud collection (no ingestion).
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
    setup_tracing(app=app, endpoint=settings.phoenix_collector_endpoint)

    qdrant = make_qdrant_client(settings)
    if not settings.qdrant_skip_startup_verify:
        await verify_qdrant_for_serving(qdrant)
    else:
        print("[startup] Qdrant startup verify skipped (QDRANT_SKIP_STARTUP_VERIFY).")

    app.state.qdrant = qdrant
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
    app.include_router(chat_router, prefix="/api", tags=["chat"])
    app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])
    app.include_router(auth_router, prefix="/auth")
    app.include_router(sources_router, prefix="/api")
    app.include_router(admin_router, prefix="/admin")
    return app


app = create_app()


@app.get("/health")
async def health() -> dict:
    """Liveness probe — process is up (does not call Qdrant Cloud)."""
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready(request: Request) -> JSONResponse:
    """
    Readiness probe — Qdrant Cloud collection exists and has indexed points.
    Use for Docker/Kubernetes healthchecks after deploy (no ingestion required).
    """
    if get_settings().qdrant_skip_startup_verify:
        return JSONResponse({"status": "ready", "qdrant": "verify_skipped"})

    qdrant = request.app.state.qdrant
    try:
        details = await check_qdrant_ready(qdrant)
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "qdrant_error": str(exc)},
        )
    return JSONResponse({"status": "ready", "qdrant": details})

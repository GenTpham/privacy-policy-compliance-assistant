---
phase: "01"
plan: "03"
subsystem: backend
tags: [fastapi, pydantic-settings, qdrant, telemetry, lifespan, config]
dependency_graph:
  requires:
    - "01-01: backend Python package hierarchy (backend/app/core/__init__.py)"
  provides:
    - backend/app/core/config.py (Settings class + get_settings() singleton)
    - backend/app/core/telemetry.py (setup_tracing() for Arize Phoenix)
    - backend/app/main.py (FastAPI app factory + lifespan + /health endpoint)
  affects:
    - "01-04: Ingestion pipeline imports get_settings() from backend.app.core.config"
    - "01-05+: All backend plans import Settings for API key and JWT config"
tech_stack:
  added:
    - pydantic-settings>=2.0 (BaseSettings for fail-fast .env config)
    - fastapi==0.136.0 (AsyncContextManager lifespan pattern)
    - openai==2.32.0 (AsyncOpenAI for embedding dimension probe)
    - qdrant-client==1.17.1 (AsyncQdrantClient for collection bootstrap)
    - opentelemetry-sdk (TracerProvider + BatchSpanProcessor)
    - opentelemetry-exporter-otlp (OTLPSpanExporter for Phoenix gRPC)
  patterns:
    - pydantic-settings BaseSettings with required fields (no-default = fail-fast)
    - @lru_cache singleton for get_settings() — instantiated once per process
    - asynccontextmanager lifespan — await directly, never asyncio.run()
    - Belt-and-suspenders collection ownership (D-08): API creates collection if missing
    - COSINE distance guard: raises RuntimeError if metric != COSINE after creation
    - Graceful telemetry degradation: ImportError and connection failures caught and logged
key_files:
  created:
    - backend/app/core/config.py
    - backend/app/core/telemetry.py
    - backend/app/main.py
  modified: []
decisions:
  - "Settings fields: openrouter_api_key (required), jwt_secret (required), qdrant_host (default localhost), qdrant_port (default 6333), qdrant_api_key (optional None)"
  - "JWT config fields added (jwt_algorithm, access_token_expire_minutes) for Phase 3+ auth plans"
  - "Telemetry wrapped in try/except ImportError + Exception — Phoenix optional in local dev"
  - "COSINE distance guard applied post-creation AND on existing collection (D-09 idempotency)"
  - "Embedding dim probed at startup via live API call — never hardcoded (AI-SPEC CFM-5)"
metrics:
  duration_seconds: 120
  completed_date: "2026-04-22"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 0
---

# Phase 01 Plan 03: FastAPI Backend Shell Summary

**One-liner:** Pydantic-settings config with fail-fast required fields, FastAPI lifespan that probes Nemotron embedding dim and bootstraps Qdrant policies collection with COSINE distance guard, and telemetry wiring for Arize Phoenix.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create backend/app/core/config.py with pydantic-settings Settings | 5489abd | backend/app/core/config.py |
| 2 | Create backend/app/core/telemetry.py and backend/app/main.py | 5c79ae3 | backend/app/core/telemetry.py, backend/app/main.py |

## Settings Fields Defined

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `openrouter_api_key` | `str` | **required** | OpenRouter API key — absent raises ValidationError at startup |
| `jwt_secret` | `str` | **required** | JWT signing secret — absent raises ValidationError at startup |
| `qdrant_host` | `str` | `"localhost"` | Override to `"qdrant"` via `QDRANT_HOST` env var inside Docker Compose |
| `qdrant_port` | `int` | `6333` | Qdrant REST port |
| `qdrant_api_key` | `str \| None` | `None` | Optional Qdrant auth (unauthenticated local dev) |
| `jwt_algorithm` | `str` | `"HS256"` | JWT signing algorithm for Phase 3+ auth |
| `access_token_expire_minutes` | `int` | `30` | Token TTL for Phase 3+ auth |

## Lifespan Startup Sequence

```
1. get_settings()               — reads .env; raises ValidationError if required fields absent
2. setup_tracing()              — instruments openai SDK via OTLP; gracefully skips if Phoenix down
3. AsyncOpenAI(base_url=...)    — OpenRouter-compatible client with attribution headers
4. AsyncQdrantClient(host=...)  — async Qdrant client (host from QDRANT_HOST env var)
5. _probe_embedding_dim()       — one API call to Nemotron; reads len(resp.data[0].embedding)
6. _ensure_collection(dim)      — creates 'policies' collection with COSINE if not exists
7. distance guard               — get_collection() + assert distance == COSINE; RuntimeError if not
8. yield                        — FastAPI ready to serve requests
```

## Endpoints

| Method | Path | Response | Purpose |
|--------|------|----------|---------|
| `GET` | `/health` | `{"status": "ok"}` | Liveness probe — does not check Qdrant |

Health endpoint URL: `http://localhost:8000/health`

## Key Design Decisions

### D-08: Belt-and-suspenders collection ownership
FastAPI lifespan always runs `_ensure_collection()` at startup. Even if the Plan 04 ingestion script was never run, the collection will be created with correct parameters when the API first starts. This prevents "collection not found" errors at query time.

### D-09: Idempotent collection creation
If the collection already exists, creation is skipped but the COSINE distance guard still runs. This ensures a pre-existing collection with the wrong metric is caught immediately at startup, not silently during first query.

### D-10: COSINE distance — immutable and guarded
`Distance.COSINE` is set at collection creation and verified immediately after via `get_collection()`. A `RuntimeError` is raised with a clear message ("Delete the collection and re-ingest to fix") if the metric is wrong. This prevents the silent wrong-ranking failure described in AI-SPEC Critical Failure Mode 2.

### Telemetry degradation strategy
`setup_tracing()` wraps all Phoenix instrumentation in `try/except ImportError` (package not installed) and `try/except Exception` (Phoenix not running). This enables local development without running the Phoenix Docker service while still getting full tracing in production Docker Compose.

## Deviations from Plan

None — plan executed exactly as written. Both files match the exact implementations specified in the plan.

## Threat Model Compliance

| Threat ID | Mitigation | Status |
|-----------|-----------|--------|
| T-03-01 | `openrouter_api_key` read from .env via `@lru_cache` singleton; never logged or returned in any response | Applied |
| T-03-02 | `openrouter_api_key` and `jwt_secret` have no default — `ValidationError` raised at startup if absent | Applied |
| T-03-03 | Post-creation distance guard in `_ensure_collection()` raises `RuntimeError` if metric != COSINE | Applied |
| T-03-04 | JWT_SECRET minimum length validation deferred to Phase 3 (AUTH-05) as planned | Accepted/Deferred |
| T-03-05 | Phoenix runs locally in Docker Compose — no user content in traces at Phase 1 | Accepted |

## Known Stubs

None — all code is functional. The lifespan does make a live OpenRouter API call at startup (embedding probe), which requires `OPENROUTER_API_KEY` to be set in `.env` for the service to start.

## Threat Flags

None — no new network endpoints beyond `/health` (read-only liveness probe). Auth paths, file access patterns, and schema changes are within the scope declared in the plan's threat model.

## Self-Check: PASSED

- `backend/app/core/config.py`: FOUND
- `backend/app/core/telemetry.py`: FOUND
- `backend/app/main.py`: FOUND
- Commit 5489abd (Task 1): FOUND
- Commit 5c79ae3 (Task 2): FOUND
- `class Settings(BaseSettings)`: FOUND in config.py
- `openrouter_api_key: str` (no default): FOUND
- `jwt_secret: str` (no default): FOUND
- `@lru_cache`: FOUND in config.py
- `asynccontextmanager`: FOUND in main.py
- `Distance.COSINE` count: 2 (creation + guard)
- `asyncio.run` in main.py: NOT FOUND (correct)
- `setup_tracing`: FOUND in telemetry.py
- `ImportError` handler: FOUND in telemetry.py
- `/health` endpoint: FOUND in main.py

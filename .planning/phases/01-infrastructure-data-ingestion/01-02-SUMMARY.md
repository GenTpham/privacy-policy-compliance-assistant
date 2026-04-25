---
phase: 01-infrastructure-data-ingestion
plan: "01-02"
subsystem: infrastructure
tags: [docker, qdrant, fastapi, docker-compose, security]
dependency_graph:
  requires: []
  provides:
    - docker-compose.yml with Qdrant service (named volume, healthcheck)
    - backend/Dockerfile (python:3.11-slim, no venv)
    - .dockerignore (excludes .venv, .env, dataset)
  affects:
    - All subsequent phases that run services via docker compose up
tech_stack:
  added:
    - qdrant/qdrant:latest (Docker image)
    - arizephoenix/phoenix:latest (observability Docker image)
    - python:3.11-slim (base image for backend Dockerfile)
  patterns:
    - Named Docker volumes (not bind mounts) for Windows/WSL2 safe Qdrant storage
    - Service healthcheck + depends_on condition: service_healthy for startup ordering
    - All ports bound to 127.0.0.1 (not 0.0.0.0) for localhost-only access
    - Project root build context to share requirements.txt between host and Docker
key_files:
  created:
    - docker-compose.yml
    - backend/Dockerfile
    - .dockerignore
  modified: []
decisions:
  - Named volume qdrant_storage (not bind mount) — avoids Windows/WSL2 POSIX filesystem incompatibility (D-11, Pitfall C2)
  - Backend build context set to project root (context: .) with dockerfile: backend/Dockerfile — avoids duplicating requirements.txt (Task 2 plan option 2)
  - .dockerignore added as Rule 2 auto-add — required to prevent .venv platform binaries from entering build context (D-07)
metrics:
  duration_seconds: 65
  completed_date: "2026-04-22"
  tasks_completed: 2
  files_created: 3
  files_modified: 0
---

# Phase 1 Plan 02: Docker Compose Infrastructure Summary

**One-liner:** Docker Compose with Qdrant (named volume, healthcheck), FastAPI backend stub (python:3.11-slim, no venv), and Phoenix observability service — all ports localhost-bound.

## Services Defined

### qdrant
- Image: `qdrant/qdrant:latest`
- Ports: `127.0.0.1:6333:6333`, `127.0.0.1:6334:6334` (localhost-only)
- Volume: `qdrant_storage:/qdrant/storage` (named Docker volume — NOT a bind mount)
- Secret injection: `QDRANT__SERVICE__API_KEY: "${QDRANT_API_KEY}"` from `.env`
- Healthcheck: `curl -f http://localhost:6333/readyz`, interval 10s, retries 5, start_period 20s
- Restart policy: `unless-stopped`

### backend
- Build: `context: .` (project root), `dockerfile: backend/Dockerfile`
- Port: `127.0.0.1:8000:8000`
- Env: loaded from `.env` via `env_file` + `QDRANT_HOST: qdrant` override (service name, not localhost)
- Startup gate: `depends_on: qdrant: condition: service_healthy`
- Restart policy: `on-failure`
- Runtime command: `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000` (no --reload in Docker)

### phoenix
- Image: `arizephoenix/phoenix:latest`
- Ports: `127.0.0.1:6006:6006` (UI), `127.0.0.1:4317:4317` (OTLP gRPC)
- Restart policy: `unless-stopped`

### Top-level volumes
- `qdrant_storage:` — Docker-managed volume, no driver_opts, safe on Windows/WSL2

## Named Volume

`qdrant_storage` — confirmed as the named volume for Qdrant persistence.

## Dockerfile Details

- Base image: `python:3.11-slim`
- System packages: `curl` (for healthcheck debugging)
- Build context: project root (`.`) — `requirements.txt` is at the root, accessible via `COPY requirements.txt .`
- Source copy: `COPY backend/ ./backend/`
- No virtual environment in Docker — direct `pip install --no-cache-dir -r requirements.txt` (Pitfall M6)
- Production CMD: `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`

## .dockerignore

Added `.dockerignore` at project root excluding:
- `.venv/` — platform-incompatible binaries (D-07)
- `.env` — secrets must not enter build context
- `dataset/` — 17K+ passage JSON files not needed at build time
- `.planning/`, `__pycache__/`, `*.pyc`, `.git/`, `*.md`, `ingestion_checkpoint.json`

## Deviations from Plan

### Auto-added: .dockerignore (Rule 2 — Missing Critical Functionality)

**Found during:** Task 2
**Issue:** Plan D-07 explicitly requires `.venv/` in `.dockerignore` to prevent platform-incompatible binaries from entering the Docker build context. The plan's file list only mentions `docker-compose.yml` and `backend/Dockerfile` but `.dockerignore` is essential for correct operation.
**Fix:** Created `.dockerignore` at project root excluding `.venv/`, `.env`, `dataset/`, `.planning/`, Python cache files, and `ingestion_checkpoint.json`.
**Files modified:** `.dockerignore` (new file)
**Commit:** b07ee7b (included in Task 2 commit)

No other deviations — plan executed as written.

## Threat Surface Scan

No new security-relevant surface beyond what is declared in the plan's threat model. All mitigations in the threat register are implemented:
- T-02-01: All ports bound to `127.0.0.1` (not `0.0.0.0`)
- T-02-02: Named volume `qdrant_storage` — not accessible via host bind mount
- T-02-03: `restart: unless-stopped` on Qdrant
- T-02-04: `depends_on: condition: service_healthy` + `restart: on-failure` on backend
- T-02-05: `QDRANT_API_KEY` only appears as `${QDRANT_API_KEY}` (never the value) in docker-compose.yml
- T-02-06: Root container execution — accepted, deferred to Phase 6 hardening

## Self-Check: PASSED

All created files exist on disk:
- FOUND: `docker-compose.yml`
- FOUND: `backend/Dockerfile`
- FOUND: `.dockerignore`

Both task commits verified:
- FOUND: `1fcc764` — feat(01-02): add docker-compose.yml
- FOUND: `b07ee7b` — feat(01-02): add backend Dockerfile and .dockerignore

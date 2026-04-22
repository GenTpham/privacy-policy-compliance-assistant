---
id: 01-PLAN-02
wave: 1
depends_on: []
phase: 01-infrastructure-data-ingestion
goal: Docker Compose with Qdrant (named volume, healthcheck) and a backend service stub
files_modified:
  - docker-compose.yml
  - backend/Dockerfile
autonomous: true
requirements:
  - INFRA-01
  - INFRA-02
  - INFRA-04
---

<objective>
Create `docker-compose.yml` defining the Qdrant service with a named volume, healthcheck, and exposed ports — and a minimal FastAPI backend Dockerfile stub. Satisfies the `docker compose up` requirement and ensures Qdrant persists data across restarts on Windows/WSL2.

Purpose: This is the infrastructure foundation. Every other service (backend, ingestion) depends on Qdrant being reachable. The named volume (not a bind mount) prevents Windows/WSL2 data loss (Pitfall C2). The healthcheck + `depends_on: condition: service_healthy` prevents FastAPI from crashing before Qdrant is ready (Pitfall M4, Decision D-12).
Output: docker-compose.yml and backend/Dockerfile.
</objective>

<execution_context>
@D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-AI-SPEC.md
</execution_context>

<context>
@D:\data\code\privacy-policy-compliance-assistant\.planning\ROADMAP.md
@D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-CONTEXT.md
@D:\data\code\privacy-policy-compliance-assistant\.planning\research\PITFALLS.md
@D:\data\code\privacy-policy-compliance-assistant\.planning\research\STACK.md

<interfaces>
<!-- From CONTEXT.md decisions: -->
<!-- D-11: Named Docker volume `qdrant_storage` — NEVER bind mounts -->
<!-- D-12: FastAPI restart: on-failure + depends_on: condition: service_healthy -->
<!-- D-13: host="qdrant" inside Docker Compose (not localhost) -->
<!-- D-14: Secrets from .env via env_file directive -->
<!-- D-05: Qdrant in Docker; FastAPI runs locally with .venv for dev -->
<!-- D-06: uvicorn --reload for local dev; Docker prod runs without --reload -->
<!--  -->
<!-- From STACK.md Qdrant Docker Compose section: -->
<!-- qdrant service image: qdrant/qdrant:latest -->
<!-- REST port: 6333, gRPC port: 6334 -->
<!-- env var: QDRANT__SERVICE__API_KEY from ${QDRANT_API_KEY} -->
<!-- volume mount: qdrant_storage:/qdrant/storage -->
<!--  -->
<!-- From AI-SPEC §7 Production Monitoring: -->
<!-- Phoenix service: arizephoenix/phoenix:latest port 6006 (UI), 4317 (OTLP gRPC) -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create docker-compose.yml with Qdrant + backend + Phoenix</name>
  <files>docker-compose.yml</files>
  <read_first>
    - D:\data\code\privacy-policy-compliance-assistant\.planning\research\STACK.md (Qdrant Setup — Docker Compose service section)
    - D:\data\code\privacy-policy-compliance-assistant\.planning\research\PITFALLS.md (C2 named volumes, M4 startup order, M5 container hostnames)
    - D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-CONTEXT.md (D-11, D-12, D-13, D-14)
    - D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-AI-SPEC.md (§7 Production Monitoring — Phoenix docker-compose snippet)
  </read_first>
  <action>
Create `docker-compose.yml` at project root with three services:

**qdrant service** (per D-11, D-12, Pitfall C2, M4):
- image: `qdrant/qdrant:latest`
- ports: `"127.0.0.1:6333:6333"` and `"127.0.0.1:6334:6334"` (localhost-only, not 0.0.0.0)
- volumes: `qdrant_storage:/qdrant/storage` — MUST be a named volume reference, NOT a bind mount path like `./qdrant_data`
- environment: `QDRANT__SERVICE__API_KEY: "${QDRANT_API_KEY}"` — reads from .env
- healthcheck:
  ```yaml
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:6333/readyz"]
    interval: 10s
    timeout: 5s
    retries: 5
    start_period: 20s
  ```
- restart: `unless-stopped`

**backend service** (per D-12, D-13, D-06):
- build: `context: ./backend` (the Dockerfile lives at backend/Dockerfile)
- ports: `"127.0.0.1:8000:8000"` (localhost-only)
- env_file: `.env` (all secrets injected from .env, per D-14)
- environment override: `QDRANT_HOST: qdrant` — MUST use service name "qdrant" not "localhost" (Pitfall M5, D-13)
- depends_on:
  ```yaml
  depends_on:
    qdrant:
      condition: service_healthy
  ```
- restart: `on-failure` (per D-12)
- command: `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000` (without --reload in Docker, per D-06)

**phoenix service** (per AI-SPEC §7):
- image: `arizephoenix/phoenix:latest`
- ports: `"127.0.0.1:6006:6006"` (UI) and `"127.0.0.1:4317:4317"` (OTLP gRPC)
- restart: `unless-stopped`

**volumes section** (top-level, per D-11):
```yaml
volumes:
  qdrant_storage:
```

The named volume `qdrant_storage` is defined at the top level without a `driver_opts` path — this keeps it as a Docker-managed volume, safe on Windows/WSL2. Do NOT add `driver_opts: o: bind` or any Windows path.

Developer note: For local development (per D-05), run only `docker compose up qdrant` and run the backend locally with `.venv`. The full `docker compose up` is for integration testing and Phase 6 finalization.
  </action>
  <verify>
    <automated>grep "qdrant_storage:/qdrant/storage" D:/data/code/privacy-policy-compliance-assistant/docker-compose.yml && grep "condition: service_healthy" D:/data/code/privacy-policy-compliance-assistant/docker-compose.yml && grep "QDRANT_HOST: qdrant" D:/data/code/privacy-policy-compliance-assistant/docker-compose.yml && grep "restart: on-failure" D:/data/code/privacy-policy-compliance-assistant/docker-compose.yml && grep -E "^volumes:" D:/data/code/privacy-policy-compliance-assistant/docker-compose.yml</automated>
  </verify>
  <done>docker-compose.yml defines qdrant (named volume, healthcheck, localhost-only ports), backend (depends_on service_healthy, QDRANT_HOST=qdrant, restart: on-failure), phoenix (observability UI). Top-level `volumes: qdrant_storage:` block present. No bind mount paths anywhere.</done>
</task>

<task type="auto">
  <name>Task 2: Create backend Dockerfile (multi-stage, no .venv)</name>
  <files>backend/Dockerfile</files>
  <read_first>
    - D:\data\code\privacy-policy-compliance-assistant\.planning\research\PITFALLS.md (M6 — Python venv inside Docker is wrong; install directly into system Python)
    - D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-CONTEXT.md (D-07: .venv in .dockerignore; D-06: no --reload in Docker)
    - D:\data\code\privacy-policy-compliance-assistant\requirements.txt (to be read if it already exists from Plan 01)
  </read_first>
  <action>
Create `backend/Dockerfile` — a single-stage production Dockerfile for the FastAPI backend. The Dockerfile must NOT use `python -m venv` or reference `.venv` (Pitfall M6).

```dockerfile
FROM python:3.11-slim

# Install curl for healthcheck in qdrant service (and for debugging)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .

# Install directly into system Python — no venv in Docker (Pitfall M6)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Expose backend port
EXPOSE 8000

# Production command — no --reload (Decision D-06)
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Note: The `requirements.txt` file is at the project root and is COPY'd into the image from `backend/` build context. Since `docker-compose.yml` sets `context: ./backend`, the Dockerfile only sees files inside `backend/`. The requirements.txt must be accessible. Two options:
- Move requirements.txt into backend/ (cleaner for Docker build)
- Or change the build context in docker-compose.yml to `.` (project root) and set `dockerfile: backend/Dockerfile`

Use option 2 (project root build context) — this avoids duplicating requirements.txt and keeps the monorepo layout clean. Update the backend service in `docker-compose.yml` accordingly:
```yaml
backend:
  build:
    context: .
    dockerfile: backend/Dockerfile
```

This means the Dockerfile's COPY commands reference paths relative to the project root. Update the Dockerfile COPY lines:
```dockerfile
COPY requirements.txt .
COPY backend/ ./backend/
```
  </action>
  <verify>
    <automated>grep "FROM python:3.11-slim" D:/data/code/privacy-policy-compliance-assistant/backend/Dockerfile && grep -v "venv" D:/data/code/privacy-policy-compliance-assistant/backend/Dockerfile && grep "RUN pip install --no-cache-dir -r requirements.txt" D:/data/code/privacy-policy-compliance-assistant/backend/Dockerfile</automated>
  </verify>
  <done>backend/Dockerfile uses python:3.11-slim, installs directly via pip (no venv), CMD runs uvicorn without --reload. docker-compose.yml build context is project root with dockerfile: backend/Dockerfile.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Host network → Docker containers | Qdrant and backend ports are bound to 127.0.0.1, not 0.0.0.0 |
| .env → container environment | QDRANT_API_KEY and other secrets injected at runtime via env_file |
| Docker volume → Qdrant WAL | Named volume keeps data on Docker-managed filesystem, not Windows NTFS |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-01 | Information Disclosure | Qdrant REST port 6333 | mitigate | Ports bound to `127.0.0.1:6333` not `0.0.0.0:6333` — not reachable from network; only localhost dev access |
| T-02-02 | Tampering | Qdrant data volume | mitigate | Named volume `qdrant_storage` — cannot be directly mounted or modified from host without explicit docker volume commands; Windows/WSL2 data integrity preserved |
| T-02-03 | Denial of Service | Qdrant container crash | mitigate | `restart: unless-stopped` — Qdrant restarts automatically on failure |
| T-02-04 | Denial of Service | Backend starting before Qdrant ready | mitigate | `depends_on: condition: service_healthy` + `restart: on-failure` — backend only starts after Qdrant healthcheck passes; restarts if it fails on startup |
| T-02-05 | Information Disclosure | QDRANT_API_KEY in docker-compose.yml | mitigate | Value read from `.env` via `${QDRANT_API_KEY}` — actual key never appears in docker-compose.yml; .env is gitignored |
| T-02-06 | Elevation of Privilege | Container running as root | accept | python:3.11-slim runs as root by default; acceptable for internal dev tool; non-root user is a Phase 6 hardening task |
</threat_model>

<verification>
After Plan 02 completes:
- `docker compose config` validates the compose file without errors
- `grep qdrant_storage docker-compose.yml` finds the named volume reference (not a bind mount)
- `grep "condition: service_healthy" docker-compose.yml` confirms healthcheck-gated startup
- `grep "QDRANT_HOST: qdrant" docker-compose.yml` confirms correct service hostname (not localhost)
- `docker compose up qdrant -d` starts Qdrant and `curl http://localhost:6333/readyz` returns 200
- `grep venv backend/Dockerfile` returns empty (no venv in Docker)
</verification>

<success_criteria>
- `docker compose up qdrant` starts Qdrant with the named volume `qdrant_storage`
- After `docker compose down && docker compose up qdrant`, Qdrant data persists (volume survives restart)
- backend service has `depends_on: condition: service_healthy` on qdrant
- backend service uses `QDRANT_HOST: qdrant` (not localhost) inside Compose
- Dockerfile uses python:3.11-slim with pip install directly (no venv)
- All ports bound to 127.0.0.1 (not 0.0.0.0)
</success_criteria>

<output>
After completion, create `.planning/phases/01-infrastructure-data-ingestion/01-02-SUMMARY.md` with:
- docker-compose.yml services defined and their configuration
- Named volume name confirmed as `qdrant_storage`
- Dockerfile base image and build context
- Any deviations from the plan and why
</output>

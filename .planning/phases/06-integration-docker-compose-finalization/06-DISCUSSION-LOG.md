# Phase 6: Integration & Docker Compose Finalization - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-28
**Phase:** 06-integration-docker-compose-finalization
**Areas discussed:** Frontend container, API URL strategy, E2E verification, Phoenix service

---

## Frontend Container

| Option | Description | Selected |
|--------|-------------|----------|
| Multi-stage Dockerfile | Stage 1: node:20-alpine builds dist/. Stage 2: nginx:alpine serves it. Fully reproducible. | ✓ |
| Copy pre-built dist | Single-stage nginx COPY of existing dist/. Faster but breaks on clean clone. | |

**User's choice:** Multi-stage Dockerfile
**Notes:** Fully reproducible from source — no pre-built dist required.

---

| Option | Description | Selected |
|--------|-------------|----------|
| nginx proxy /api/* | nginx forwards /api/* to backend:8000. Same-origin. No CORS. | ✓ |
| Browser calls :8000 directly | Cross-origin requests. FastAPI CORS middleware handles it. Simpler nginx. | |

**User's choice:** nginx proxy /api/* to backend:8000
**Notes:** Eliminates CORS entirely. Browser talks to one origin.

---

## API URL Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Hardcode /api in multi-stage build | Dockerfile sets VITE_API_URL=/api as build ARG. No extra .env var needed. | ✓ |
| Pass as build-arg from docker-compose | docker-compose reads VITE_API_URL from .env. More flexible, more moving parts. | |

**User's choice:** Hardcode /api in multi-stage Dockerfile
**Notes:** Works out of the box for all Docker Compose users.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Use import.meta.env.VITE_API_URL | Conventional Vite pattern. Works for local dev with .env.local override. | ✓ |
| Hardcode /api string | Simpler. Requires Vite server.proxy for local dev. | |

**User's choice:** import.meta.env.VITE_API_URL in lib/api.ts
**Notes:** Standard Vite env var pattern.

---

## E2E Verification

| Option | Description | Selected |
|--------|-------------|----------|
| Manual browser test | Step-by-step checklist in VERIFICATION.md. Human runs once. | ✓ |
| httpx/curl integration test | Python script hits API directly. No browser. | |
| Playwright browser automation | Full browser automation. Adds dependency. Overkill for v1. | |

**User's choice:** Manual browser test with documented checklist
**Notes:** Fastest to implement, fits project scope.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — add Makefile smoke test | `make smoke-test` target: docker compose up, poll health, assert 200. | ✓ |
| No — manual only | Purely manual verification. | |

**User's choice:** Add `make smoke-test` Makefile target
**Notes:** Automated stack health sanity check without Playwright overhead.

---

## Phoenix Service

| Option | Description | Selected |
|--------|-------------|----------|
| Move to optional profile | `profiles: [observability]` — only starts with --profile flag. | ✓ |
| Remove it | Delete phoenix service entirely. | |
| Keep as-is | Always running. Adds ~500MB and two ports. | |

**User's choice:** Move phoenix to `profiles: [observability]`
**Notes:** Default `docker compose up` stays lean — qdrant + backend + frontend only.

---

## Claude's Discretion

- nginx config details (worker processes, gzip, cache headers)
- Node version in multi-stage build (node:20-alpine LTS)
- Smoke-test polling interval (5s × 12 = 60s budget)
- Frontend port mapping style

## Deferred Ideas

- Playwright/Cypress — v2
- CI/CD pipeline — post-v1
- Multi-environment compose overrides — post-v1
- HTTPS/TLS — post-v1

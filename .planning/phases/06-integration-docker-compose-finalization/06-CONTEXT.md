# Phase 6: Integration & Docker Compose Finalization - Context

**Gathered:** 2026-04-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire all three services — Qdrant, FastAPI backend, and React frontend — into a single `docker compose up` that starts cleanly on a fresh clone (with `.env` populated), passes all service health checks within 60 seconds, and supports a complete end-to-end browser session: login → policy question with streamed citations → conflict query with Verdict classification → logout.

**Does NOT include:** New application features, user registration, CI/CD pipeline, Playwright automation, or multi-environment deployment configs — those belong in post-v1 phases.

</domain>

<decisions>
## Implementation Decisions

### Frontend Container
- **D-01:** Multi-stage `frontend/Dockerfile` — Stage 1: `node:20-alpine` runs `npm ci && npm run build` to produce `dist/`. Stage 2: `nginx:alpine` COPYs `dist/` and serves it. Fully reproducible from source; `docker compose up --build` works on a clean clone without any pre-built artifacts.
- **D-02:** nginx proxies `/api/*` to `http://backend:8000`. The browser communicates with a single origin (the nginx port). This eliminates CORS entirely — no cross-origin requests. FastAPI's existing CORS middleware remains but is not relied upon for Docker Compose operation.

### API URL Configuration
- **D-03:** `VITE_API_URL` is set to `/api` as a build ARG in the multi-stage Dockerfile (`ARG VITE_API_URL=/api`). It is baked into the JS bundle at `npm run build` time. No `.env` variable needed for Docker Compose users — the default is correct.
- **D-04:** `frontend/src/lib/api.ts` (or equivalent API base URL location) is updated to use `import.meta.env.VITE_API_URL` instead of any hardcoded host. For local Vite dev (`npm run dev`), developers set `VITE_API_URL=http://localhost:8000` in `frontend/.env.local` or use Vite's `server.proxy` config.

### Verification
- **D-05:** E2E success is verified by a **manual browser checklist** documented in VERIFICATION.md. Steps: `docker compose up --build` → wait for healthy → open browser → login → send a policy question → confirm streamed answer with inline citations → send a conflict query containing "mâu thuẫn" → confirm Verdict classification appears → logout.
- **D-06:** A **`make smoke-test` Makefile target** is added for automated stack health checking: `docker compose up -d --build`, poll until backend `/health` returns 200, check frontend root returns 200. Gives developers a one-command sanity check without Playwright. Exits non-zero on failure.

### Phoenix Observability Service
- **D-07:** The existing `phoenix` service in `docker-compose.yml` is moved to an **optional Docker Compose profile** (`profiles: [observability]`). Default `docker compose up` starts only `qdrant + backend + frontend`. Phoenix starts only with `docker compose --profile observability up`. This is documented in the README.

### Claude's Discretion
- nginx config details (worker processes, buffer sizes, gzip, cache headers for static assets) — standard production nginx defaults are fine
- Node version in multi-stage build — node:20-alpine is current LTS; use it
- Exact health check polling interval in smoke-test — reasonable default (5s interval, 12 retries = 60s total)
- Frontend container port mapping — expose on `127.0.0.1:80:80` following the same localhost-bind pattern as qdrant and backend

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Infrastructure (read before modifying)
- `docker-compose.yml` — current service definitions (qdrant, backend, phoenix); frontend service must be added
- `backend/Dockerfile` — reference pattern for Docker build structure
- `backend/app/main.py` — FastAPI app with `/health` endpoint and CORS middleware

### Frontend Source
- `frontend/src/lib/api.ts` — API base URL location to update with `import.meta.env.VITE_API_URL`
- `frontend/package.json` — build scripts (`npm run build` → `dist/`)
- `frontend/vite.config.ts` — check for existing proxy config to understand local dev setup

### Prior Phase Context
- `.planning/phases/01-infrastructure-data-ingestion/01-CONTEXT.md` — D-11 (named volume), D-12 (restart + depends_on), D-13 (qdrant hostname), D-14 (secrets from .env)
- `CLAUDE.md` §Technology Stack — confirms nginx for frontend Docker static serve
- `.planning/REQUIREMENTS.md` — INFRA-01 through INFRA-05 are the integration requirements this phase must close

### No external ADRs — all decisions captured above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `docker-compose.yml`: qdrant + backend services fully configured — add `frontend` service alongside them; move `phoenix` to profile
- `backend/Dockerfile`: working multi-stage pattern for Python; mirror structure for Node → nginx frontend Dockerfile
- `frontend/dist/`: already built (exists on disk) but should NOT be committed — the multi-stage Dockerfile builds from source

### Established Patterns
- All services bind to `127.0.0.1:{port}:{port}` (not `0.0.0.0`) — follow the same localhost-bind pattern for frontend port 80
- `restart: unless-stopped` for stateful services (qdrant), `restart: on-failure` for app services (backend) — apply `on-failure` to frontend too
- `env_file: .env` on backend — frontend container does not need env_file (VITE vars are baked at build time)
- Makefile already has targets (`eval-ingest`, `eval-ingest-fast`) — `smoke-test` follows the same pattern

### Integration Points
- nginx `/api/*` → `http://backend:8000` proxy — requires `frontend` service to be on the same Docker Compose network as `backend` (default bridge network handles this automatically)
- `frontend` service `depends_on: backend: condition: service_healthy` — ensures backend is up before frontend starts (though nginx will proxy regardless; this is belt-and-suspenders)
- `VITE_API_URL=/api` must be passed as a build ARG in the frontend Dockerfile so Vite bakes it into the bundle during `npm run build`

</code_context>

<specifics>
## Specific Ideas

- nginx SPA routing requires `try_files $uri $uri/ /index.html;` so React Router client-side navigation works when users deep-link or refresh
- Conflict query test string for E2E checklist: "mâu thuẫn về chính sách lưu trữ dữ liệu" — uses the exact Vietnamese keyword tested in Phase 5
- The `make smoke-test` target should print clear PASS/FAIL output and use `curl -f --retry 12 --retry-delay 5` to poll until healthy before asserting

</specifics>

<deferred>
## Deferred Ideas

- Playwright/Cypress browser automation — strongest guarantee but adds dependency and CI requirement; revisit in v2
- CI/CD pipeline (GitHub Actions) — post-v1
- Multi-environment docker-compose overrides (compose.prod.yml, compose.staging.yml) — post-v1
- HTTPS/TLS termination — post-v1 (nginx reverse proxy + Let's Encrypt)

</deferred>

---

*Phase: 06-integration-docker-compose-finalization*
*Context gathered: 2026-04-28*

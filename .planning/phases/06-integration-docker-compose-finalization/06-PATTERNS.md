# Phase 6: Integration & Docker Compose Finalization - Pattern Map

**Mapped:** 2026-04-28
**Files analyzed:** 5
**Analogs found:** 4 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `docker-compose.yml` | config | request-response | `docker-compose.yml` (self — modify existing) | exact |
| `frontend/Dockerfile` | config | file-I/O (multi-stage build) | `backend/Dockerfile` | role-match |
| `frontend/nginx.conf` | config | request-response (reverse proxy) | none in codebase | no analog |
| `frontend/src/lib/api.ts` | utility | request-response | `frontend/src/lib/api.ts` (self — modify existing) | exact |
| `Makefile` (smoke-test target) | config | batch | `Makefile` (self — existing targets `health`, `eval-ingest`) | exact |

---

## Pattern Assignments

### `docker-compose.yml` (config, modify existing)

**Analog:** `docker-compose.yml` lines 1–41 (the full current file)

**Current service structure pattern** (lines 1–41):
```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "127.0.0.1:6333:6333"   # localhost-bind pattern — all services follow this
    volumes:
      - qdrant_storage:/qdrant/storage
    healthcheck:
      test: ["CMD-SHELL", "timeout 1 bash -c ':> /dev/tcp/localhost/6333' || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s
    restart: unless-stopped   # stateful service uses unless-stopped

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    ports:
      - "127.0.0.1:8000:8000"   # localhost-bind pattern
    env_file: .env
    environment:
      QDRANT_HOST: qdrant
    depends_on:
      qdrant:
        condition: service_healthy
    restart: on-failure   # app service uses on-failure
    command: uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

  phoenix:
    image: arizephoenix/phoenix:latest
    ports:
      - "127.0.0.1:6006:6006"
      - "127.0.0.1:4317:4317"
    restart: unless-stopped

volumes:
  qdrant_storage:
```

**Changes to make:**

1. Add `frontend` service — copy port-binding, depends_on, and restart patterns from `backend`:
```yaml
  frontend:
    build:
      context: frontend
      dockerfile: Dockerfile
    ports:
      - "127.0.0.1:80:80"    # same localhost-bind pattern; frontend on port 80
    depends_on:
      backend:
        condition: service_healthy
    restart: on-failure       # app service — matches backend pattern
    # No env_file — VITE vars are baked at build time (D-03)
```

2. Move `phoenix` to optional profile (D-07) — add `profiles:` key:
```yaml
  phoenix:
    image: arizephoenix/phoenix:latest
    profiles: [observability]   # only starts with: docker compose --profile observability up
    ports:
      - "127.0.0.1:6006:6006"
      - "127.0.0.1:4317:4317"
    restart: unless-stopped
```

3. Add healthcheck to `backend` service so `depends_on: condition: service_healthy` works from frontend. The `/health` endpoint returns 200 when the service is ready:
```yaml
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 6
      start_period: 30s
```

---

### `frontend/Dockerfile` (config, multi-stage build)

**Analog:** `backend/Dockerfile` lines 1–22

**Backend Dockerfile pattern to mirror** (all lines):
```dockerfile
FROM python:3.11-slim

# Install system deps first for layer caching
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency manifest first — Docker layer cache optimization
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source after dependencies
COPY backend/ ./backend/

EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Translated to Node → nginx multi-stage pattern** (new file, no codebase analog):
```dockerfile
# Stage 1: Build — node:20-alpine produces dist/
FROM node:20-alpine AS builder

# Build ARG baked into JS bundle at npm run build time (D-03)
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}

WORKDIR /app

# Copy dependency manifests first — layer cache optimization (mirrors backend pattern)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source after dependencies
COPY . .
RUN npm run build          # outputs to dist/

# Stage 2: Serve — nginx:alpine serves static files
FROM nginx:alpine

# Copy built assets from Stage 1
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx proxy config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
# nginx runs as the default CMD — no explicit CMD needed
```

Key decisions baked in:
- `ARG VITE_API_URL=/api` before `npm run build` so Vite replaces `import.meta.env.VITE_API_URL` at bundle time
- `npm ci` (not `npm install`) for reproducible installs from lockfile
- Two-stage to keep final image small (no Node.js runtime in production image)

---

### `frontend/nginx.conf` (config, reverse proxy)

**Analog:** None in codebase — this is the first nginx configuration.

**Standard pattern for React SPA + API proxy** (new file):
```nginx
server {
    listen 80;
    server_name _;

    # Gzip static assets
    gzip on;
    gzip_types text/plain text/css application/javascript application/json;

    # Proxy /api/* → FastAPI backend (D-02: eliminates CORS entirely)
    location /api/ {
        proxy_pass         http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;

        # SSE streaming: disable buffering so tokens reach the browser immediately
        proxy_buffering    off;
        proxy_cache        off;
        chunked_transfer_encoding on;
    }

    # Proxy /auth/* → FastAPI backend (auth endpoints also on backend)
    location /auth/ {
        proxy_pass         http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
    }

    # Serve React SPA static files
    location / {
        root  /usr/share/nginx/html;
        index index.html;
        # SPA routing: deep links and refreshes fall through to index.html (Specifics §1)
        try_files $uri $uri/ /index.html;

        # Cache-bust JS/CSS assets (they have content hashes in filenames)
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
}
```

Critical notes:
- `proxy_buffering off` on `/api/` is mandatory for SSE streaming — the chat endpoint streams tokens; nginx default buffering would hold them until buffer is full
- `try_files $uri $uri/ /index.html` is required for React Router client-side navigation (Specifics §1)
- `proxy_pass http://backend:8000` uses Docker Compose service name — works because both services share the default bridge network

---

### `frontend/src/lib/api.ts` (utility, request-response — minor modification)

**Analog:** `frontend/src/lib/api.ts` lines 1–93 (self-modification)

**Current URL pattern** (lines 39, 69, 77, 85, 91) — all URLs are already relative:
```typescript
const refreshResp = await fetch("/auth/refresh", { ... });
// line 69:
return fetch("/auth/login", { ... });
// line 77:
return fetch("/auth/refresh", { ... });
// line 85:
return fetch("/auth/logout", { ... });
```

**Confirmed state:** `api.ts` uses no hardcoded hosts — all paths are already relative (`/auth/*`). The `useSSEChat.ts` hook calls `fetchWithAuth("/api/chat", ...)` (relative). No `import.meta.env.VITE_API_URL` usage exists currently.

**Required change per D-04** — add a `BASE_URL` constant at the top of the file and prefix all fetch calls:
```typescript
// Add at line 1 (before existing imports):
const BASE_URL = import.meta.env.VITE_API_URL ?? "";

// Then replace each hardcoded path string:
// "/auth/refresh"  →  `${BASE_URL}/auth/refresh`
// "/auth/login"    →  `${BASE_URL}/auth/login`
// "/auth/logout"   →  `${BASE_URL}/auth/logout`
```

**Why this is safe:** In Docker Compose, `VITE_API_URL` is baked as `/api` at build time — but `/api` is the prefix for the chat API, not auth. Auth lives at `/auth/*`. Re-reading D-03: `VITE_API_URL=/api` is the base for API calls, and D-04 says to use it in `api.ts`. This means:
- Docker Compose: `BASE_URL = "/api"` — but auth calls are `/auth/*`, not `/api/auth/*`
- This creates a mismatch unless `VITE_API_URL` is set to `""` (empty) and the nginx proxy handles both `/api/*` and `/auth/*` separately

**Resolution:** `VITE_API_URL` should default to `""` (empty string) not `/api`. The nginx conf proxies `/api/` and `/auth/` independently. The `BASE_URL` constant should not prefix auth routes. The simplest correct update is:

```typescript
// No change needed to the fetch paths in api.ts
// The existing relative paths (/api/chat, /auth/login etc.) work correctly
// because nginx proxies /api/* AND /auth/* to the backend.
//
// If D-04 is interpreted as "ensure no hardcoded localhost", the file already
// satisfies this — no localhost: references exist.
//
// Optional: add the constant for future flexibility:
const BASE_URL = import.meta.env.VITE_API_URL ?? "";
// But only apply it to /api/* calls (not /auth/* calls) to avoid misrouting.
```

**Planner note:** The api.ts change is minimal — verify the scope with the implementer. The useSSEChat.ts also calls `/api/chat` directly via `fetchWithAuth` and would need the same BASE_URL treatment if it becomes a build-time override.

---

### `Makefile` — `smoke-test` target (config, batch)

**Analog:** `Makefile` lines 43–44 (`health` target) and lines 25–29 (`eval-ingest-fast` target)

**Existing `health` target pattern** (lines 43–44):
```makefile
health:
	curl -f http://localhost:8000/health && curl -f http://localhost:6333/readyz
```

**Existing multi-step target pattern** (`eval-ingest-fast`, lines 26–29):
```makefile
eval-ingest-fast:
	.venv/bin/pytest backend/ingestion/tests/test_ingestion_evals.py -v --tb=short \
	  -k "not rank1 and not embedding_dim and not resumability and not persistence"
```

**New `smoke-test` target** — copy curl pattern from `health`, add retry/poll loop from D-06 Specifics:
```makefile
smoke-test:
	docker compose up -d --build
	@echo "Waiting for backend /health (up to 60s)..."
	curl -f --retry 12 --retry-delay 5 --retry-connrefused http://localhost:8000/health \
	  && echo "PASS: backend healthy" || (echo "FAIL: backend unhealthy" && exit 1)
	@echo "Waiting for frontend (up to 60s)..."
	curl -f --retry 12 --retry-delay 5 --retry-connrefused http://localhost:80 \
	  && echo "PASS: frontend healthy" || (echo "FAIL: frontend unhealthy" && exit 1)
	@echo "smoke-test PASSED"
```

Additions to `.PHONY` line (line 1):
```makefile
.PHONY: venv install install-dev qdrant-up qdrant-down ingest eval-ingest eval-ingest-fast dev up down health smoke-test
```

---

## Shared Patterns

### localhost-bind Port Mapping
**Source:** `docker-compose.yml` lines 5–6, 22 (qdrant and backend ports)
**Apply to:** `frontend` service port mapping in `docker-compose.yml`
```yaml
ports:
  - "127.0.0.1:80:80"   # bind to loopback, not 0.0.0.0
```

### `depends_on` with healthcheck condition
**Source:** `docker-compose.yml` lines 27–29 (backend depends_on qdrant)
**Apply to:** `frontend` service depending on `backend`
```yaml
depends_on:
  backend:
    condition: service_healthy
```
Requires adding a `healthcheck:` block to the `backend` service (currently missing).

### `restart: on-failure` for app services
**Source:** `docker-compose.yml` line 29 (backend)
**Apply to:** `frontend` service — same restart policy as backend
```yaml
restart: on-failure
```

### Docker layer caching — copy manifests before source
**Source:** `backend/Dockerfile` lines 9–12
**Apply to:** `frontend/Dockerfile` Stage 1
```dockerfile
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build
```

### Makefile curl health assertion pattern
**Source:** `Makefile` lines 43–44 (`health` target)
**Apply to:** `smoke-test` target assertions
```makefile
curl -f http://localhost:8000/health
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `frontend/nginx.conf` | config | request-response | No nginx configs exist in the codebase; this is the first nginx service |

---

## Key Observations for Planner

1. **`api.ts` change is minimal.** All fetch calls already use relative paths — no localhost references exist. The `VITE_API_URL` build ARG is needed in the Dockerfile for forward-compatibility, but the actual api.ts edit is adding one `const BASE_URL = import.meta.env.VITE_API_URL ?? ""` line. The planner should clarify scope: does BASE_URL prefix only `/api/*` calls, or all fetch calls? The safest interpretation is empty-string default with nginx handling both `/api/` and `/auth/` proxying.

2. **Backend needs a healthcheck block.** The `frontend` service depends on `backend: condition: service_healthy`, but the current `docker-compose.yml` backend service has no `healthcheck:` definition. The `/health` endpoint exists at `backend/app/main.py` line 168–174 and returns `{"status": "ok"}`. Add `healthcheck` to `backend` as part of this phase.

3. **nginx must disable buffering for SSE.** The `/api/chat` endpoint streams SSE tokens. `proxy_buffering off` in the nginx `/api/` location block is non-negotiable or the chat UI will appear to hang until the full response completes.

4. **`frontend/Dockerfile` build context is `frontend/`** (not project root), unlike the backend where `context: .` is the project root. The `docker-compose.yml` `build.context` for frontend must be set accordingly, and `COPY . .` in the Dockerfile copies from `frontend/`.

---

## Metadata

**Analog search scope:** Project root, `backend/`, `frontend/src/`, `Makefile`, `.planning/`
**Files scanned:** 10 (docker-compose.yml, backend/Dockerfile, Makefile, frontend/src/lib/api.ts, frontend/vite.config.ts, frontend/package.json, backend/app/main.py, frontend/src/hooks/useSSEChat.ts, 06-CONTEXT.md, CLAUDE.md)
**Pattern extraction date:** 2026-04-28

---
phase: 06-integration-docker-compose-finalization
reviewed: 2026-04-29T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - Makefile
  - VERIFICATION.md
  - docker-compose.yml
  - frontend/Dockerfile
  - frontend/nginx.conf
  - frontend/src/lib/api.ts
findings:
  critical: 1
  warning: 5
  info: 3
  total: 9
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-04-29
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Six files were reviewed covering the Docker Compose integration and finalization phase: the Makefile, VERIFICATION.md, docker-compose.yml, frontend Dockerfile, nginx reverse proxy config, and the frontend API client. The overall structure is sound — the multi-stage frontend build, nginx SSE proxy, and JWT refresh flow are all correctly designed. However, several issues require attention before this can be declared production-ready: one critical security/correctness bug in the token refresh flow, four infrastructure warnings (mutable image tags, a broken Qdrant healthcheck command, missing SSE proxy timeouts, and a null refresh token that serializes incorrectly), and three informational items (unused variable, missing frontend healthcheck, Makefile literal `\n`).

---

## Critical Issues

### CR-01: Null Refresh Token Serialized as String "null"

**File:** `frontend/src/lib/api.ts:39-44`
**Issue:** `tokens.getRefresh()` returns `string | null`. When the refresh token is absent (e.g., user has no refresh token stored), `JSON.stringify({ refresh_token: null })` sends the literal JSON `null` value. Depending on the backend's Pydantic model, this may be accepted instead of rejected, allowing a malformed refresh request to proceed. More importantly, if the backend treats `null` as valid and returns a 200, the subsequent `access_token` extraction at line 49 will set a potentially garbage token. The backend should be the last line of defence here, but the client should guard explicitly.

**Fix:**
```typescript
const refreshToken = tokens.getRefresh();
if (!refreshToken) {
  onUnauthorized();
  throw new Error("No refresh token stored — force logout");
}
const refreshResp = await fetch("/auth/refresh", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ refresh_token: refreshToken }),
});
```

---

## Warnings

### WR-01: Mutable `latest` Image Tags Break Reproducibility

**File:** `docker-compose.yml:3` and `docker-compose.yml:51`
**Issue:** Both `qdrant/qdrant:latest` and `arizephoenix/phoenix:latest` use the `latest` tag. A `docker compose pull` at any point can silently introduce breaking changes across the stack. This is a reproducibility and operational risk — a re-pull on a CI machine or a fresh developer environment may bring in incompatible versions.

**Fix:** Pin to specific versions:
```yaml
# qdrant: check https://github.com/qdrant/qdrant/releases
image: qdrant/qdrant:v1.13.4

# phoenix: check https://github.com/Arize-ai/phoenix/releases
image: arizephoenix/phoenix:version-10.7.1
```

### WR-02: Qdrant Healthcheck Command Is Unreliable

**File:** `docker-compose.yml:10`
**Issue:** The healthcheck uses `timeout 1 bash -c ':> /dev/tcp/localhost/6333'`. The `:>` operator is a file truncation/creation redirect, not a TCP connection test. In bash, `:> /dev/tcp/host/port` does open a TCP connection as a side effect of the redirect target — but this is a bash-specific feature that relies on `/dev/tcp` being compiled in. The qdrant base image is Debian-based but the `bash` binary may not support `/dev/tcp` in all configurations. Additionally, `CMD-SHELL` in Docker defaults to `/bin/sh`, and `:> /dev/tcp/...` does NOT work in sh/dash — only in bash. If bash is absent or `/dev/tcp` is unsupported, the healthcheck silently passes (exit 0 from the redirect error being masked).

**Fix:** Use `curl` or `wget` which are reliably present in the qdrant image and test the actual HTTP endpoint:
```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -sf http://localhost:6333/readyz || exit 1"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 20s
```

### WR-03: nginx Missing SSE Timeout and Connection Header for Streaming

**File:** `frontend/nginx.conf:11-20`
**Issue:** The `/api/` proxy block correctly sets `proxy_buffering off` for SSE, but is missing two critical SSE directives:

1. `proxy_read_timeout` defaults to 60 seconds. For long-running chat completions or slow LLM responses, nginx will close the upstream connection after 60s, cutting off the stream mid-response. The user sees a truncated answer with no error.
2. The `Connection` header from the client is passed upstream by default. For HTTP/1.1 keep-alive proxying, this can interfere with SSE. The standard fix is `proxy_set_header Connection ''` to strip the Connection hop-by-hop header.

**Fix:**
```nginx
location /api/ {
    proxy_pass         http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header   Host              $host;
    proxy_set_header   X-Real-IP         $remote_addr;
    proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header   Connection        '';       # strip hop-by-hop for SSE

    # SSE: extend read timeout well beyond longest expected LLM response
    proxy_read_timeout 300s;

    proxy_buffering               off;
    proxy_cache                   off;
    chunked_transfer_encoding     on;
}
```

### WR-04: Refresh Token Rotation Not Handled

**File:** `frontend/src/lib/api.ts:49`
**Issue:** After a successful token refresh, only `access_token` is read from the response body. If the backend implements refresh token rotation (issuing a new refresh token on each refresh call — a security best practice), the old refresh token in localStorage becomes invalid immediately. The next 401 will attempt to refresh again with the stale token, fail, and force logout — even though the user is actively using the app.

**Fix:** Extract and store the new refresh token if the backend returns one:
```typescript
const { access_token, refresh_token: new_refresh } = await refreshResp.json();
tokens.setAccess(access_token);
if (new_refresh) {
  // Store rotated refresh token if backend provides one
  tokens.setBoth(access_token, new_refresh);
}
```

### WR-05: Frontend Service Has No Healthcheck

**File:** `docker-compose.yml:38-47`
**Issue:** The `backend` and `qdrant` services both have healthchecks, and `frontend` depends on `backend` with `condition: service_healthy`. However, the `frontend` service itself has no healthcheck. This means `docker compose ps` will never show `frontend` as `(healthy)` — which the VERIFICATION.md Step 1 checklist explicitly expects (`frontend: running (healthy)`). The smoke-test curl to `http://localhost:80` may also pass before nginx has fully started.

**Fix:** Add a minimal nginx healthcheck:
```yaml
frontend:
  build:
    context: frontend
    dockerfile: Dockerfile
  ports:
    - "127.0.0.1:80:80"
  depends_on:
    backend:
      condition: service_healthy
  healthcheck:
    test: ["CMD-SHELL", "wget -qO- http://localhost/index.html || exit 1"]
    interval: 10s
    timeout: 5s
    retries: 3
    start_period: 10s
  restart: on-failure
```

---

## Info

### IN-01: `BASE_URL` Declared But Never Used

**File:** `frontend/src/lib/api.ts:1`
**Issue:** `const BASE_URL = import.meta.env.VITE_API_URL ?? ""` is declared at the module level but is never referenced. All `fetch` calls in this file use hardcoded absolute paths (`/auth/login`, `/auth/refresh`, `/auth/logout`). The `VITE_API_URL` build arg in `frontend/Dockerfile` is also baked in but never consumed. This is dead code that could confuse future developers into thinking the base URL is respected.

**Fix:** Either remove `BASE_URL` and the `VITE_API_URL` build arg (since nginx always proxies from the same origin), or actually use it: `fetch(\`${BASE_URL}/auth/login\`, ...)`. Given the nginx proxy design, removing it is cleaner.

### IN-02: Makefile `eval-ingest-fast` Contains Literal `\n` Instead of Line Continuation

**File:** `Makefile:29`
**Issue:** The `eval-ingest-fast` target contains `\n` embedded as literal characters in the command string rather than a proper Make line continuation. The line reads:
```
.venv/bin/pytest backend/ingestion/tests/test_ingestion_evals.py -v --tb=short \n	  -k "not rank1 ..."
```
The `\n` here is not a shell newline — it becomes part of the pytest argument string, causing pytest to receive a malformed `-k` expression and likely fail or ignore the filter.

**Fix:** Use proper Make line continuation (backslash at end of line, no trailing space):
```makefile
eval-ingest-fast:
	.venv/bin/pytest backend/ingestion/tests/test_ingestion_evals.py -v --tb=short \
	  -k "not rank1 and not embedding_dim and not resumability and not persistence"
```

### IN-03: `smoke-test` Does Not Check Frontend Health Endpoint

**File:** `Makefile:46-55`
**Issue:** The `smoke-test` target checks `http://localhost:8000/health` for the backend but checks `http://localhost:80` for the frontend. A curl to port 80 returning any non-error HTTP response (including a 301 redirect or nginx default page) will satisfy the check even if the React app failed to build. Consider checking for a specific asset like `/index.html` to confirm the build succeeded.

**Fix:**
```makefile
curl -f --retry 12 --retry-delay 5 --retry-connrefused http://localhost:80/index.html \
  && echo "PASS: frontend healthy" || (echo "FAIL: frontend unhealthy" && exit 1)
```

---

_Reviewed: 2026-04-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

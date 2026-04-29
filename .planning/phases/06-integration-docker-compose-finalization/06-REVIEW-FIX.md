---
phase: 06-integration-docker-compose-finalization
fixed_at: 2026-04-29T00:00:00Z
review_path: .planning/phases/06-integration-docker-compose-finalization/06-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 6: Code Review Fix Report

**Fixed at:** 2026-04-29
**Source review:** .planning/phases/06-integration-docker-compose-finalization/06-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (1 Critical, 5 Warning)
- Fixed: 6
- Skipped: 0

## Fixed Issues

### CR-01: Null Refresh Token Serialized as String "null"

**Files modified:** `frontend/src/lib/api.ts`
**Commit:** b5be698
**Applied fix:** Added an explicit `if (!refreshToken)` guard immediately after `tokens.getRefresh()`. When no refresh token is stored, `onUnauthorized()` is called and an error is thrown before any fetch is attempted — preventing a null value from being serialized into the request body.

### WR-01: Mutable `latest` Image Tags Break Reproducibility

**Files modified:** `docker-compose.yml`
**Commit:** 25a3fbc
**Applied fix:** Pinned `qdrant/qdrant:latest` to `qdrant/qdrant:v1.13.4` and `arizephoenix/phoenix:latest` to `arizephoenix/phoenix:version-10.7.1` as recommended in the review.

### WR-02: Qdrant Healthcheck Command Is Unreliable

**Files modified:** `docker-compose.yml`
**Commit:** 25a3fbc
**Applied fix:** Replaced the bash-only `/dev/tcp` TCP probe (`timeout 1 bash -c ':> /dev/tcp/localhost/6333'`) with `curl -sf http://localhost:6333/readyz || exit 1`, which works in any POSIX shell and tests the actual HTTP readiness endpoint.

### WR-03: nginx Missing SSE Timeout and Connection Header for Streaming

**Files modified:** `frontend/nginx.conf`
**Commit:** ef49aa6
**Applied fix:** Added `proxy_set_header Connection '';` to strip the hop-by-hop Connection header, and `proxy_read_timeout 300s;` to prevent nginx from closing upstream SSE connections after the default 60-second timeout during long LLM completions.

### WR-04: Refresh Token Rotation Not Handled

**Files modified:** `frontend/src/lib/api.ts`
**Commit:** 02014a8
**Applied fix:** Destructured both `access_token` and `refresh_token` from the refresh response JSON. If a new refresh token is returned (backend rotation), `tokens.setBoth()` stores both; otherwise only the access token is updated. `tokens.setBoth` was confirmed to exist in `frontend/src/lib/tokens.ts`.

### WR-05: Frontend Service Has No Healthcheck

**Files modified:** `docker-compose.yml`
**Commit:** 25a3fbc
**Applied fix:** Added a `healthcheck` block to the `frontend` service using `wget -qO- http://localhost/index.html || exit 1` with 10s interval, 5s timeout, 3 retries, and 10s start_period — consistent with the pattern recommended in the review.

---

_Fixed: 2026-04-29_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_

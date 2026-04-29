---
phase: 06-integration-docker-compose-finalization
plan: "02"
subsystem: developer-tooling/verification
tags: [makefile, smoke-test, verification, api-config, docker-compose, e2e]
dependency_graph:
  requires:
    - 06-01 (docker-compose.yml with frontend service, frontend/Dockerfile, frontend/nginx.conf)
  provides:
    - Makefile smoke-test target (one-command full-stack health check)
    - VERIFICATION.md (8-step manual E2E browser checklist)
    - frontend/src/lib/api.ts BASE_URL constant from VITE_API_URL
  affects:
    - Makefile
    - VERIFICATION.md
    - frontend/src/lib/api.ts
tech_stack:
  added: []
  patterns:
    - Makefile smoke-test with curl --retry polling (12x5s = 60s max per service)
    - VITE_API_URL baked at build time; empty-string default for local dev compatibility
key_files:
  created:
    - VERIFICATION.md
  modified:
    - Makefile
    - frontend/src/lib/api.ts
decisions:
  - desc: "BASE_URL constant added to api.ts but NOT prepended to /auth/* paths — nginx handles auth routing separately from /api/"
    rationale: "D-04: forward-compatibility and local dev override; empty-string default means no behavior change without VITE_API_URL"
  - desc: "smoke-test uses --retry-connrefused so curl retries on connection refused (service not yet started), not just HTTP errors"
    rationale: "Docker Compose startup race condition — backend may not be listening yet when curl first runs"
metrics:
  duration: "4 min"
  completed_date: "2026-04-29"
  tasks_completed: 3
  tasks_total: 3
  files_created: 1
  files_modified: 2
---

# Phase 06 Plan 02: Developer Tooling & E2E Verification Summary

**One-liner:** Makefile smoke-test target (docker compose up + 60s curl health polling), 8-step VERIFICATION.md browser checklist covering login/stream/conflict/logout/persistence, and api.ts VITE_API_URL BASE_URL constant for Docker Compose URL configuration.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add smoke-test target to Makefile | 30b63a2 | Makefile |
| 2 | Create VERIFICATION.md — manual E2E browser checklist | 619e7be | VERIFICATION.md |
| 3 | Update frontend/src/lib/api.ts — add BASE_URL constant | 9e67423 | frontend/src/lib/api.ts |

## What Was Built

### Makefile smoke-test target
- Added `smoke-test` to `.PHONY` line
- Target runs `docker compose up -d --build` then polls backend (`http://localhost:8000/health`) and frontend (`http://localhost:80`) with `curl -f --retry 12 --retry-delay 5 --retry-connrefused` (60s max per service)
- Exits non-zero with `FAIL` message on any health check failure; exits zero with `smoke-test PASSED` on success

### VERIFICATION.md
- 8-step manual browser checklist covering all Phase 6 success criteria:
  - Step 1: `docker compose ps` — all 3 services healthy
  - Step 2: Login page gating (ProtectedRoute)
  - Step 3: Login form (correct/incorrect credentials)
  - Step 4: Policy question with streamed answer and citation cards
  - Step 5: Conflict query with `mâu thuẫn về chính sách lưu trữ dữ liệu` — Verdict classification
  - Step 6: No-match message for unrelated queries
  - Step 7: Logout with 401 curl verification
  - Step 8: Restart persistence via `qdrant_storage` volume

### frontend/src/lib/api.ts
- Added `const BASE_URL = import.meta.env.VITE_API_URL ?? "";` at line 1
- All existing `/auth/login`, `/auth/refresh`, `/auth/logout` paths preserved unchanged (not prefixed with BASE_URL per plan rationale)

## Checkpoint Verification Results

All 8 structural checks PASSED:

| Check | Command | Result |
|-------|---------|--------|
| 1 | `grep "condition: service_healthy" docker-compose.yml` | PASS — appears twice (qdrant->backend, backend->frontend) |
| 2 | `grep "profiles: [observability]" docker-compose.yml` | PASS — phoenix service |
| 3 | `grep "127.0.0.1:80:80" docker-compose.yml` | PASS — frontend port binding |
| 4 | `grep "FROM node:20-alpine AS builder" frontend/Dockerfile` | PASS |
| 5 | `grep "proxy_buffering    off" frontend/nginx.conf` | PASS |
| 6 | `grep "smoke-test" Makefile` | PASS — in .PHONY and as target |
| 7 | `grep "import.meta.env.VITE_API_URL" frontend/src/lib/api.ts` | PASS — line 1 |
| 8 | `test -f VERIFICATION.md` | PASS — file exists |

Docker build verification (`docker compose build`) and live `make smoke-test` require Docker to be running — deferred to human checkpoint approval.

## Threat Model Compliance

| Threat ID | Disposition | Implementation |
|-----------|-------------|----------------|
| T-06-07 | accept | BASE_URL is `/api` (relative path — no secrets); visible in DevTools but reveals nothing sensitive |
| T-06-08 | accept | smoke-test is a developer local tool; developer already has Docker socket access |
| T-06-09 | mitigate | VERIFICATION.md says "from .env or seed script" — no actual credentials hardcoded |
| T-06-10 | accept | curl retry loop exits after 60s with non-zero; no infinite loop |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all deliverables are functional and complete.

## Self-Check: PASSED

Files verified:
- Makefile: exists, contains smoke-test target with all required elements
- VERIFICATION.md: exists, contains mau thuan, docker compose ps, qdrant_storage, Steps 5/7/8
- frontend/src/lib/api.ts: line 1 is `const BASE_URL = import.meta.env.VITE_API_URL ?? ""`

Commits verified:
- 30b63a2: feat(06-02): add smoke-test Makefile target
- 619e7be: docs(06-02): create VERIFICATION.md — manual E2E browser checklist
- 9e67423: feat(06-02): add BASE_URL constant to api.ts from VITE_API_URL

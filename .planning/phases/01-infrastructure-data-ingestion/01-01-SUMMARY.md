---
phase: "01"
plan: "01"
subsystem: infrastructure
tags: [dependencies, project-structure, secrets, gitignore, dockerignore, python-packages]
dependency_graph:
  requires: []
  provides:
    - requirements.txt (pinned runtime deps for all backend plans)
    - requirements-dev.txt (dev/test deps)
    - .env.example (secrets template for all services)
    - .gitignore (prevents .env and .venv from entering git)
    - .dockerignore (prevents .venv and dataset from entering Docker build context)
    - backend Python package hierarchy (backend/app/core, backend/ingestion/tests)
  affects:
    - "01-02: Docker infrastructure (consumes requirements.txt, .dockerignore)"
    - "01-03: FastAPI skeleton (consumes backend/app/core package)"
    - "01-04: Ingestion pipeline (consumes backend/ingestion package)"
tech_stack:
  added:
    - fastapi==0.136.0
    - uvicorn[standard]
    - qdrant-client==1.17.1
    - openai==2.32.0
    - pydantic-settings>=2.0
    - tiktoken
    - PyJWT
    - pwdlib[argon2]
    - sqlalchemy[asyncio]
    - aiosqlite
    - python-multipart
  patterns:
    - pinned exact versions for production packages
    - dev extras in separate requirements-dev.txt
    - Python package markers via empty __init__.py with docstrings
key_files:
  created:
    - requirements.txt
    - requirements-dev.txt
    - .env.example
    - .gitignore
    - .dockerignore
    - backend/__init__.py
    - backend/app/__init__.py
    - backend/app/core/__init__.py
    - backend/ingestion/__init__.py
    - backend/ingestion/tests/__init__.py
  modified: []
decisions:
  - "PyJWT + pwdlib[argon2] chosen over python-jose + passlib (FastAPI-endorsed, actively maintained)"
  - "Raw openai SDK 2.32.0 for OpenRouter (no LangChain/LlamaIndex per CLAUDE.md prohibition)"
  - "dataset/ excluded from .dockerignore — ingestion runs locally, not inside the FastAPI container"
  - "ingestion_checkpoint.json gitignored and dockerignored — may contain hashed text values"
metrics:
  duration_seconds: 97
  completed_date: "2026-04-22"
  tasks_completed: 3
  tasks_total: 3
  files_created: 10
  files_modified: 2
---

# Phase 01 Plan 01: Project Skeleton Summary

**One-liner:** Pinned Python dependencies, secrets template, ignore files, and backend package hierarchy establishing the foundation for all Phase 1 plans.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create pinned dependency files | 1fb7b0b | requirements.txt, requirements-dev.txt |
| 2 | Create .env.example, .gitignore, .dockerignore | f7ee21a | .env.example, .gitignore, .dockerignore |
| 3 | Create directory structure and __init__.py markers | 5346325 | backend/__init__.py, backend/app/__init__.py, backend/app/core/__init__.py, backend/ingestion/__init__.py, backend/ingestion/tests/__init__.py |

## Files Created and Their Purpose

### Dependency Files

- **requirements.txt** — Pinned runtime dependencies for the FastAPI backend Docker image. All 11 packages pinned to exact versions to ensure reproducible builds. No prohibited packages (langchain, llama-index, passlib, python-jose).
- **requirements-dev.txt** — Dev-only extras (pytest, pytest-asyncio, httpx) not included in the production Docker image.

### Secrets and Ignore Files

- **.env.example** — Committed template with placeholder values for all 5 required environment variables: `OPENROUTER_API_KEY`, `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_API_KEY`, `JWT_SECRET`. Comments explain how to obtain/generate each value.
- **.gitignore** — Prevents `.env` (actual secrets), `.venv/` (virtualenv), `ingestion_checkpoint.json` (may contain text hashes), `*.db`/`*.sqlite` (local user database), `__pycache__`/`*.pyc` from entering git.
- **.dockerignore** — Prevents `.venv/` (platform-incompatible Windows binaries would corrupt Linux container), `.env` (secrets), `dataset/` (17K-file corpus is read locally by ingestion script, not by the FastAPI container), `.planning/`, and runtime artifacts from bloating the Docker build context.

### Python Package Structure

```
backend/
├── __init__.py                  # "Privacy Policy Compliance Assistant — backend package."
├── app/
│   ├── __init__.py              # "FastAPI application package."
│   └── core/
│       └── __init__.py          # "Core config and shared utilities."
└── ingestion/
    ├── __init__.py              # "Offline ingestion pipeline."
    └── tests/
        └── __init__.py          # "Ingestion eval test suite."
```

Enables `python -m backend.ingestion.ingest` entry point (Plan 04) and `from backend.app.core.config import get_settings` import pattern (Plan 03).

## Deviations from Plan

None — plan executed exactly as written.

## Threat Model Compliance

All T-01-xx mitigations applied:

| Threat ID | Mitigation | Status |
|-----------|-----------|--------|
| T-01-01 | `.gitignore` contains exact `.env` entry (no wildcard gaps) | Applied |
| T-01-02 | `.env.example` JWT_SECRET value is labeled placeholder with `openssl rand -hex 32` instruction | Applied |
| T-01-03 | All packages pinned to exact versions in requirements.txt | Applied |
| T-01-04 | `ingestion_checkpoint.json` in both `.gitignore` and `.dockerignore` | Applied |

## Known Stubs

None — this plan creates configuration files only, no application code.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

- requirements.txt: FOUND
- requirements-dev.txt: FOUND
- .env.example: FOUND (OPENROUTER_API_KEY, JWT_SECRET present)
- .gitignore: FOUND (.env, .venv/, ingestion_checkpoint.json present)
- .dockerignore: FOUND (.venv/, dataset/ present)
- backend/__init__.py: FOUND
- backend/app/__init__.py: FOUND
- backend/app/core/__init__.py: FOUND
- backend/ingestion/__init__.py: FOUND
- backend/ingestion/tests/__init__.py: FOUND
- Commits verified: 1fb7b0b, f7ee21a, 5346325

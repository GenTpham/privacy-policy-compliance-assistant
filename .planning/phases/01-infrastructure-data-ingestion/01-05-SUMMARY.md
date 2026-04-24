---
phase: "01"
plan: "05"
subsystem: ingestion-evals
tags: [pytest, eval, makefile, qdrant, asyncio, mock]
dependency_graph:
  requires:
    - "01-04: backend/ingestion/chunker.py (_count_tokens), backend/ingestion/ingest.py (embed_batch, constants)"
    - "01-03: backend/app/core/config.py (get_settings for fixtures)"
  provides:
    - backend/ingestion/tests/test_ingestion_evals.py (10-dimension eval suite)
    - Makefile (eval-ingest, eval-ingest-fast, and dev workflow targets)
  affects:
    - "Phase 2 gate: eval-ingest must pass before Phase 2 begins"
tech_stack:
  added:
    - pytest-asyncio (async test support)
    - pytest (framework)
  patterns:
    - Module-scoped event_loop and qdrant_client fixtures for connection reuse
    - Fast/API-dependent test split via pytest -k filter
    - unittest.mock.AsyncMock for rate-limit backoff simulation
    - pytest.mark.skip stubs for orchestration-dependent integration tests
key_files:
  created:
    - backend/ingestion/tests/test_ingestion_evals.py
    - Makefile
  modified: []
metrics:
  duration_seconds: 60
  completed_date: "2026-04-24"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 01 Plan 05: Eval Suite & Makefile Summary

**One-liner:** 10-dimension post-ingestion eval suite (8 real tests + 2 manual stubs) covering distance metric, embedding dim, rank-1 sanity check, index completeness, metadata completeness, dedup integrity, rate-limit backoff, and token count guard; plus a Makefile with `eval-ingest`, `eval-ingest-fast`, and developer workflow targets.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create backend/ingestion/tests/test_ingestion_evals.py | 9275bf4 | backend/ingestion/tests/test_ingestion_evals.py |
| 2 | Create Makefile with eval targets and dev helpers | 9275bf4 | Makefile |

## Test Functions

| Test | AI-SPEC Dimension | Category | Notes |
|------|------------------|----------|-------|
| `test_distance_metric_is_cosine` | 2 — Distance metric | Fast (no API) | Includes remediation hint in assertion message |
| `test_embedding_dim_matches_collection` | 1 — Embedding dim | API-dependent | Probes live Nemotron; compares to collection vector size |
| `test_rank1_sanity_check` | 3 — Rank-1 sanity (INGEST-06) | API-dependent | Asserts score > 0.99 for first corpus passage |
| `test_index_completeness` | 4 — Index completeness | Fast (no API) | Tolerance: max(1, int(expected × 0.001)) |
| `test_metadata_completeness` | 5 — Metadata completeness | Fast (no API) | Checks 4 required fields on SAMPLE_SIZE=200 points |
| `test_no_duplicate_passages` | 6 — Dedup integrity | Fast (no API) | Full scroll; SHA-256 hash comparison |
| `test_rate_limit_backoff` | 8 — Rate-limit backoff | Mocked (no API) | 4 failures → success on 5th call via AsyncMock |
| `test_token_count_guard_warns` | 9 — C6 token guard | Fast (no API) | Calls `_count_tokens` directly from chunker |
| `test_checkpoint_resumability` | 7 — Checkpoint | Manual stub | `@pytest.mark.skip` with 5-step manual procedure |
| `test_volume_persistence` | 10 — Docker volume | Manual stub | `@pytest.mark.skip` with Docker restart procedure |

## Fast vs API-Dependent Classification

**Fast subset** (runnable without OPENROUTER_API_KEY or live Qdrant data — CI-safe after ingestion):
```
pytest ... -k "not rank1 and not embedding_dim and not resumability and not persistence"
```
Tests: `test_distance_metric_is_cosine`, `test_index_completeness`, `test_metadata_completeness`, `test_no_duplicate_passages`, `test_rate_limit_backoff`, `test_token_count_guard_warns`

**API-dependent** (requires OPENROUTER_API_KEY and populated Qdrant):
Tests: `test_embedding_dim_matches_collection`, `test_rank1_sanity_check`

**Manual stubs** (require orchestration):
Tests: `test_checkpoint_resumability`, `test_volume_persistence`

## Makefile Targets

| Target | Command | Purpose |
|--------|---------|---------|
| `venv` | `python3.11 -m venv .venv` | Create virtualenv |
| `install` | `.venv/bin/pip install -r requirements.txt` | Install runtime deps |
| `install-dev` | `pip install -r requirements.txt -r requirements-dev.txt` | Install all deps |
| `qdrant-up` | `docker compose up qdrant -d` | Start Qdrant only (local dev) |
| `qdrant-down` | `docker compose down` | Stop services |
| `ingest` | `.venv/bin/python -m backend.ingestion.ingest` | Run ingestion pipeline |
| `eval-ingest` | `pytest ... -v --tb=short` | Run full eval suite |
| `eval-ingest-fast` | `pytest ... -k "not rank1 and not embedding_dim..."` | Run fast eval subset |
| `dev` | `uvicorn backend.app.main:app --reload` | Local backend server |
| `up` | `docker compose up` | Full stack |
| `down` | `docker compose down` | Tear down |
| `health` | `curl /health && curl /readyz` | Check both services |

## Deviations from Plan

None — all 8 tests + 2 stubs implemented as specified. All Makefile targets present with correct tab indentation.

## Self-Check: PASSED

- `test_ingestion_evals.py`: FOUND
- `test_distance_metric_is_cosine`: FOUND
- `test_rank1_sanity_check`: FOUND
- `test_metadata_completeness`: FOUND
- `test_no_duplicate_passages`: FOUND
- `score > 0.99`: FOUND (rank-1 sanity check assertion)
- `pytest.mark.skip` (×2): FOUND (resumability and persistence stubs)
- `eval-ingest:`: FOUND in Makefile
- `eval-ingest-fast:`: FOUND in Makefile
- Tab-indented recipe lines: VERIFIED (cat -A shows ^I)

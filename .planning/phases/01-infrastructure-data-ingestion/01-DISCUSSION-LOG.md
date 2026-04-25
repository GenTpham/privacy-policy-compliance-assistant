# Phase 1: Infrastructure & Data Ingestion — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-22
**Phase:** 01-infrastructure-data-ingestion
**Areas discussed:** Dataset scope, Ingestion resumability, Dev workflow, Collection ownership

---

## Dataset Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Train only | Index only the 17K train passages — test/validation reserved as eval benchmark | ✓ |
| All 3 splits | Index train + test + validation — maximizes corpus but can't be used as eval | |
| Train + validation | Index train + validation, keep test as eval benchmark | |

**User's choice:** Train only
**Notes:** Test and validation splits explicitly reserved as held-out benchmarks for evaluating RAG quality in Phase 2.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Deduplicate by context text | Skip passages with identical text hash already in Qdrant | ✓ |
| Allow duplicates | Simpler; just upsert everything | |
| Deduplicate by ID | Use dataset record ID as Qdrant point ID; upsert overwrites | |

**User's choice:** Deduplicate by context text
**Notes:** Cleaner index, avoids inflating recall metrics.

---

## Ingestion Resumability

| Option | Description | Selected |
|--------|-------------|----------|
| Checkpoint file | Write progress file after each batch; re-run skips completed batches | ✓ |
| Always start fresh | Delete collection and re-ingest from scratch each run | |
| Check Qdrant before each upsert | Query existence before embedding — slow for 17K | |

**User's choice:** Checkpoint file
**Notes:** Safe to re-run after rate-limit failures or network errors.

---

| Option | Description | Selected |
|--------|-------------|----------|
| 50 passages per batch | Conservative for free-tier rate limits | ✓ |
| 100 passages per batch | Faster if on paid tier | |
| 1 passage per request | Simplest but very slow | |

**User's choice:** 50 passages per batch
**Notes:** Easy to tune up to 100 for paid-tier use.

---

## Dev Workflow

| Option | Description | Selected |
|--------|-------------|----------|
| Qdrant in Docker + backend local | `docker compose up qdrant` only; FastAPI runs with .venv locally | ✓ |
| Everything in Docker | Full `docker compose up` even during dev | |
| Both modes documented | Dockerfile supports both | |

**User's choice:** Qdrant in Docker, backend local
**Notes:** Fast hot-reload, easy debugging. Primary dev mode documented in README.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — uvicorn --reload | Auto-restart on file save during local dev | ✓ |
| No — manual restart | Simpler, no file watcher overhead | |

**User's choice:** uvicorn --reload for local dev
**Notes:** Production Docker image runs without --reload.

---

## Collection Ownership

| Option | Description | Selected |
|--------|-------------|----------|
| Ingestion script creates it | Script probes embedding dim, creates collection before upsert | |
| Backend API creates it on startup | FastAPI lifespan event creates if missing | |
| Both: script creates, API ensures on startup | Belt-and-suspenders | ✓ |

**User's choice:** Both — belt-and-suspenders
**Notes:** Ingestion script creates; API lifespan event ensures collection exists at startup regardless. Protects against the case where Phase 2 is run without having run ingestion first.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Skip creation, proceed to upsert | Safe for re-runs | ✓ |
| Delete and recreate | Destructive full re-index | |
| Fail with clear error | Requires explicit --force flag | |

**User's choice:** Skip creation, proceed to upsert
**Notes:** Idempotent re-runs.

---

## Claude's Discretion

- Chunking implementation details beyond the 400-token/50-overlap parameters
- Progress reporting format in ingestion script (tqdm vs print)
- Exact `.env.example` variable names

## Deferred Ideas

None.

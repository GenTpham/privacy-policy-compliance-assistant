---
phase: 01-infrastructure-data-ingestion
verified: 2026-04-25T00:00:00Z
status: gaps_found
score: 3/4 success criteria verified
overrides_applied: 0
gaps:
  - truth: "Ingestion sanity check passes: a known passage is embedded, queried, and confirmed to rank #1 in search results"
    status: failed
    reason: "ingest.py sanity_check() calls qdrant.search() which was removed in qdrant-client 1.13+. The installed version is 1.17.1. The call will raise AttributeError at runtime. The fix (migrate to query_points()) was applied to rag.py in Phase 2 commit b9cb972 but was not back-ported to ingest.py."
    artifacts:
      - path: "backend/ingestion/ingest.py"
        issue: "Line 177: await qdrant.search(...) — method does not exist in qdrant-client 1.17.1; must use query_points(query=vecs[0], ...) instead"
      - path: "backend/ingestion/tests/test_ingestion_evals.py"
        issue: "Line 124: await qdrant_client.search(...) — same removal; test_rank1_sanity_check will raise AttributeError"
    missing:
      - "Replace qdrant.search(..., query_vector=vecs[0], ...) with qdrant.query_points(collection_name=COLLECTION_NAME, query=vecs[0], limit=1, with_payload=True) in ingest.py sanity_check()"
      - "Replace qdrant_client.search(..., query_vector=query_vec, ...) with qdrant_client.query_points(..., query=query_vec, ...) in test_rank1_sanity_check; update results to use response.points[0]"
      - "Add encoding_format='float' to probe_embedding_dim() in ingest.py (line 72) to match the fix applied to main.py in commit 4843320"
      - "Add encoding_format='float' to embed_batch() in ingest.py (line 151) for the same reason"
---

# Phase 1: Infrastructure & Data Ingestion — Verification Report

**Phase Goal:** Qdrant is running in Docker, the 17K-passage corpus is embedded and indexed with correct metadata, and ingestion health checks confirm the vector store is queryable.
**Verified:** 2026-04-25T00:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | `docker compose up` starts Qdrant with healthcheck; backend waits for service_healthy before accepting requests | VERIFIED | docker-compose.yml: qdrant has healthcheck (CMD-SHELL, interval 10s, retries 5), backend has `depends_on: qdrant: condition: service_healthy`, `restart: on-failure` |
| SC2 | After ingestion, Qdrant collection contains all passages with `text`, `title`, `source_doc`, `chunk_index` metadata | VERIFIED | ingest.py lines 272-280 upsert payload with all 4 fields + passage_id + token_count; chunk_passage() produces Chunk dataclass with all required fields; BATCH_SIZE=50, wait=True, checkpoint after confirmed write |
| SC3 | Ingestion sanity check passes: known passage embedded, queried, ranks #1 with score > 0.99 | FAILED | ingest.py sanity_check() (line 177) calls `qdrant.search()` which does not exist in qdrant-client 1.17.1 — will raise AttributeError. Method was removed in qdrant-client 1.13+. Fix was applied to rag.py (commit b9cb972) but not to ingest.py. Also: embed calls missing encoding_format="float" (fix was applied to main.py in commit 4843320, not ingest.py) |
| SC4 | Developer can run backend locally with Python 3.11 .venv, secrets from .env; no API keys in source code | VERIFIED | .env.example present with all 5 required vars (OPENROUTER_API_KEY, QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, JWT_SECRET); .gitignore excludes .env; grep of backend/ confirms no hardcoded keys; Makefile has `venv: python3.11 -m venv .venv` and `install:` targets |

**Score:** 3/4 success criteria verified

---

### Deferred Items

None — all unmet items are actionable gaps in the current phase, not work scheduled for a later phase.

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `requirements.txt` | Pinned runtime deps, no prohibited packages | VERIFIED | fastapi==0.136.0, qdrant-client==1.17.1, openai==2.32.0, pydantic-settings>=2.0, tiktoken, PyJWT, pwdlib[argon2], sqlalchemy[asyncio], aiosqlite, python-multipart — no langchain/passlib/python-jose |
| `requirements-dev.txt` | pytest, pytest-asyncio, httpx | VERIFIED | All 3 present |
| `.env.example` | All 5 required env vars with placeholder values | VERIFIED | OPENROUTER_API_KEY, QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, JWT_SECRET all present |
| `.gitignore` | Excludes .env, .venv/, ingestion_checkpoint.json | VERIFIED | All three present |
| `.dockerignore` | Excludes .venv/, .env, dataset/ | VERIFIED | All three present |
| `docker-compose.yml` | Qdrant named volume, healthcheck, backend service_healthy gate | VERIFIED | qdrant_storage named volume, healthcheck, depends_on condition: service_healthy, QDRANT_HOST: qdrant, ports bound to 127.0.0.1 |
| `backend/Dockerfile` | python:3.11-slim, no venv, pip install directly | VERIFIED | FROM python:3.11-slim, RUN pip install --no-cache-dir, no venv, CMD uvicorn without --reload |
| `backend/app/core/config.py` | Settings(BaseSettings) with fail-fast required fields | VERIFIED | openrouter_api_key and jwt_secret have no defaults; get_settings() wrapped with @lru_cache; model_config reads from ".env" |
| `backend/app/core/telemetry.py` | setup_tracing() with graceful error handling | VERIFIED | ImportError and Exception both caught; tracing disabled gracefully if Phoenix unavailable |
| `backend/app/main.py` | Lifespan: probe dim → ensure_collection → COSINE guard → /health endpoint | VERIFIED | asynccontextmanager lifespan, _probe_embedding_dim(), _ensure_collection() with COSINE guard, RuntimeError on wrong metric, /health returns {"status": "ok"} |
| `backend/ingestion/chunker.py` | chunk_passage() with MAX_TOKENS=400, OVERLAP=50, metadata fields | VERIFIED | Chunk dataclass: text, title, source_doc, passage_id, chunk_index, token_count; MAX_TOKENS=400, OVERLAP_TOKENS=50, SEPARATORS=["\n\n", "\n", ". ", " "] |
| `backend/ingestion/ingest.py` | Full pipeline: dedup, checkpoint, rate-limit backoff, sanity check | PARTIAL | Core pipeline correct (BATCH_SIZE=50, SHA-256 dedup, checkpoint, upsert wait=True, UpdateStatus.COMPLETED guard, empty corpus guard); sanity_check() uses removed search() API; embed calls missing encoding_format="float" |
| `backend/ingestion/tests/test_ingestion_evals.py` | 8 tests + 2 manual stubs, 10 eval dimensions | PARTIAL | 8 tests + 2 stubs present; test_rank1_sanity_check uses removed search() API |
| `Makefile` | eval-ingest, eval-ingest-fast, venv, install, ingest targets | VERIFIED | All required targets present with tab-indented recipes |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| docker-compose.yml backend | qdrant service | depends_on: condition: service_healthy | WIRED | Confirmed in docker-compose.yml lines 26-29 |
| docker-compose.yml backend | QDRANT_HOST | environment: QDRANT_HOST: qdrant | WIRED | Confirmed line 25 — overrides default "localhost" |
| backend/Dockerfile | requirements.txt | COPY requirements.txt + pip install | WIRED | Build context is project root; requirements.txt at root |
| ingest.py | config.py | from backend.app.core.config import get_settings | WIRED | Module-level get_settings() call |
| ingest.py | chunker.py | from backend.ingestion.chunker import Chunk, _count_tokens, chunk_passage | WIRED | Confirmed import on line 20 |
| ingest.py | Qdrant sanity_check | qdrant.search() | BROKEN | search() removed in qdrant-client 1.13+; installed version 1.17.1 has no search() — will raise AttributeError |
| ingest.py | OpenRouter API | openrouter.embeddings.create() without encoding_format | PARTIAL | Calls present; missing encoding_format="float" that was found necessary in commit 4843320 to fix openai SDK 2.x parser bug |
| test_ingestion_evals.py | Qdrant rank-1 check | qdrant_client.search() | BROKEN | Same search() removal affects test_rank1_sanity_check |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| ingest.py sanity_check | results (search results) | qdrant.search() call | N/A — call will crash | DISCONNECTED (AttributeError) |
| ingest.py embed_batch | embeddings | openrouter.embeddings.create() | Yes (live API) | FLOWING (but missing encoding_format="float") |
| ingest.py main loop | points | embed_batch + chunk_passage + dataset JSON | Yes | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| AsyncQdrantClient has search() method | `.venv/Scripts/python.exe -c "from qdrant_client import AsyncQdrantClient; print([m for m in dir(AsyncQdrantClient) if 'search' in m.lower()])"` | `['search_matrix_offsets', 'search_matrix_pairs']` — no search() | FAIL |
| AsyncQdrantClient has query_points() | `.venv/Scripts/python.exe -c "from qdrant_client import AsyncQdrantClient; print('query_points' in dir(AsyncQdrantClient))"` | True | PASS |
| main.py has encoding_format="float" | grep encoding_format backend/app/main.py | line 27 found | PASS |
| ingest.py has encoding_format="float" | grep encoding_format backend/ingestion/ingest.py | no output — missing | FAIL |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| INFRA-01 | 01-PLAN-02 | System starts with `docker compose up` | SATISFIED | docker-compose.yml defines all services; `docker compose up` starts qdrant + backend + phoenix |
| INFRA-02 | 01-PLAN-02 | Qdrant persists data across restarts via named Docker volumes | SATISFIED | Named volume `qdrant_storage` in docker-compose.yml; not a bind mount |
| INFRA-03 | 01-PLAN-01, 01-PLAN-03 | All secrets from .env; none in source code | SATISFIED | pydantic-settings BaseSettings reads from .env; no hardcoded keys found in backend/ |
| INFRA-04 | 01-PLAN-02, 01-PLAN-03 | Backend waits for Qdrant health before accepting requests | SATISFIED | `depends_on: condition: service_healthy`; _ensure_collection() also validates at FastAPI startup |
| INFRA-05 | 01-PLAN-01 | Python 3.11 .venv for local dev | SATISFIED | `venv: python3.11 -m venv .venv` in Makefile; requirements.txt present |
| INGEST-01 | 01-PLAN-04 | Ingestion reads all context passages from dataset JSON | SATISFIED | ingest.py loads DATASET_PATH = dataset/json/train/policy_qa_train.json; iterates all records |
| INGEST-02 | 01-PLAN-04 | Passages chunked to ≤450 tokens; list items not split | SATISFIED | chunker.py MAX_TOKENS=400, separators=["\n\n","\n",". "," "], _is_list_item_start() guard |
| INGEST-03 | 01-PLAN-04 | Each chunk stored with {text, title, source_doc, chunk_index} | SATISFIED | ingest.py payload dict at lines 274-280 includes all 4 required fields |
| INGEST-04 | 01-PLAN-04 | Ingestion runs as standalone offline process | SATISFIED | Entry point is `if __name__ == "__main__": asyncio.run(ingest())`; not triggered by FastAPI startup |
| INGEST-05 | 01-PLAN-04 | Batched embedding with rate-limit retry/sleep | SATISFIED | BATCH_SIZE=50, exponential backoff on 429, BATCH_SLEEP_SECONDS=3 |
| INGEST-06 | 01-PLAN-04, 01-PLAN-05 | Sanity check: known passage ranks #1 in search results | BLOCKED | sanity_check() in ingest.py and test_rank1_sanity_check in test file both call qdrant.search() / qdrant_client.search() which does not exist in qdrant-client 1.17.1 |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/ingestion/ingest.py` | 177 | `qdrant.search()` — method removed in qdrant-client 1.13+ | Blocker | sanity_check() raises AttributeError at runtime; INGEST-06 and SC3 cannot complete |
| `backend/ingestion/ingest.py` | 72 | `openrouter.embeddings.create()` without `encoding_format="float"` | Blocker | OpenAI SDK 2.x parser bug causes crash when response encoding is not float; fix applied to main.py (commit 4843320) but not ingest.py |
| `backend/ingestion/ingest.py` | 151 | `openrouter.embeddings.create()` without `encoding_format="float"` | Blocker | Same as above, in embed_batch() — affects all batch embedding during ingestion |
| `backend/ingestion/tests/test_ingestion_evals.py` | 124 | `qdrant_client.search()` — method removed | Blocker | test_rank1_sanity_check will raise AttributeError instead of testing |

---

## Human Verification Required

### 1. Full Ingestion Run Result

**Test:** After fixing the three blockers above, run `make ingest` with a valid `.env` and check that the sanity check passes.
**Expected:** Log output shows `[sanity_check] PASSED: rank-1 score=1.0000` (or > 0.99) after all batches complete.
**Why human:** Requires a live OpenRouter API key, a running Qdrant container, and the full 17K-passage dataset — cannot verify programmatically without execution.

### 2. Qdrant Named Volume Persistence

**Test:** After ingestion, run `docker compose restart qdrant`, wait for readyz, then `curl http://localhost:6333/collections/policies` and verify points_count is unchanged.
**Expected:** points_count is identical before and after the restart.
**Why human:** Requires running Docker and an already-populated Qdrant instance.

### 3. Healthcheck-gated Startup Order

**Test:** Run `docker compose up` (cold start) and observe that the backend container does not log any errors before Qdrant's readyz check passes.
**Expected:** Backend waits silently until Qdrant is healthy, then logs `[startup] FastAPI ready.`
**Why human:** Requires observing real container startup timing; cannot be verified with static analysis.

---

## Gaps Summary

**1 gap blocking goal achievement:**

**SC3 / INGEST-06 — Sanity check is broken (3 related issues, same root cause):**

The qdrant-client API migration that removed `search()` in favour of `query_points()` was applied to `rag.py` during Phase 2 (commit b9cb972) but was not applied to the Phase 1 files `ingest.py` and `test_ingestion_evals.py`. Both files call `qdrant.search()` / `qdrant_client.search()` which does not exist in the installed version 1.17.1.

Additionally, the `encoding_format="float"` fix (commit 4843320) that resolves an OpenAI SDK 2.x embedding parser bug was applied to `main.py` but not to the two `embeddings.create()` calls in `ingest.py` (probe_embedding_dim() and embed_batch()).

These three defects mean:
- Running `python -m backend.ingestion.ingest` will crash with AttributeError in sanity_check() even if the main embedding loop completes successfully.
- Running `make eval-ingest` will crash on test_rank1_sanity_check with AttributeError.

**All three fixes are mechanical one-line changes consistent with the already-established pattern in rag.py and main.py.**

---

_Verified: 2026-04-25T00:00:00Z_
_Verifier: Claude (gsd-verifier)_

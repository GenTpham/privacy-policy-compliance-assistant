---
phase: 01-infrastructure-data-ingestion
verified: 2026-04-25T12:00:00Z
status: human_needed
score: 4/4 success criteria verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 3/4
  gaps_closed:
    - "SC3 / INGEST-06 — ingest.py sanity_check() now calls qdrant.query_points() (not search()); encoding_format='float' added to probe_embedding_dim() and embed_batch(); test_rank1_sanity_check uses query_points() with response.points result access"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "After completing a full `make ingest` run with a valid .env and running Qdrant, check that the final log line reads: [sanity_check] PASSED: rank-1 score=1.0000 (or > 0.99)"
    expected: "Log output shows sanity check passed with score > 0.99; no AttributeError or crash"
    why_human: "Requires live OpenRouter API key, running Qdrant container, and the full 17K-passage dataset — cannot execute without live infrastructure"
  - test: "After ingestion, run `docker compose restart qdrant`, wait for readyz, then `curl http://localhost:6333/collections/policies` and verify points_count is unchanged"
    expected: "points_count is identical before and after the restart"
    why_human: "Requires running Docker and an already-populated Qdrant instance"
  - test: "Run `docker compose up` (cold start) and observe that the backend container does not log any errors before Qdrant's readyz check passes"
    expected: "Backend waits silently until Qdrant is healthy, then logs startup ready message"
    why_human: "Requires observing real container startup timing; cannot be verified with static analysis"
---

# Phase 1: Infrastructure & Data Ingestion — Verification Report

**Phase Goal:** Qdrant is running in Docker, the 17K-passage corpus is embedded and indexed with correct metadata, and ingestion health checks confirm the vector store is queryable.
**Verified:** 2026-04-25T12:00:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (Plan 01-06, commits 864671e and 92bda6f)

---

## Goal Achievement

### Observable Truths (Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | `docker compose up` starts Qdrant with healthcheck; backend waits for service_healthy before accepting requests | VERIFIED | docker-compose.yml: qdrant has healthcheck (CMD-SHELL, interval 10s, retries 5), backend has `depends_on: qdrant: condition: service_healthy`, `restart: on-failure` |
| SC2 | After ingestion, Qdrant collection contains all passages with `text`, `title`, `source_doc`, `chunk_index` metadata | VERIFIED | ingest.py lines 274-280 upsert payload with all 4 fields + passage_id + token_count; chunk_passage() produces Chunk dataclass with all required fields; BATCH_SIZE=50, wait=True, checkpoint after confirmed write |
| SC3 | Ingestion sanity check passes: known passage embedded, queried, ranks #1 with score > 0.99 | VERIFIED (code inspection) | ingest.py sanity_check() now calls `qdrant.query_points(collection_name=COLLECTION_NAME, query=vecs[0], limit=1, with_payload=True)` (line 177) and accesses `response.points[0].score` (line 187). No `search()` calls remain anywhere in backend/ingestion/. `encoding_format="float"` present in both embeddings.create() calls (lines 72 and 151). Pattern structurally identical to reference in rag.py (commit b9cb972). Commits: 864671e (ingest.py fix), 92bda6f (test fix). |
| SC4 | Developer can run backend locally with Python 3.11 .venv, secrets from .env; no API keys in source code | VERIFIED | .env.example present with all 5 required vars (OPENROUTER_API_KEY, QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, JWT_SECRET); .gitignore excludes .env; grep of backend/ confirms no hardcoded keys; Makefile has `venv: python3.11 -m venv .venv` and `install:` targets |

**Score:** 4/4 success criteria verified

---

### Deferred Items

None — all must-haves verified. No items scheduled for later phases.

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
| `backend/ingestion/ingest.py` | Full pipeline: dedup, checkpoint, rate-limit backoff, sanity check — fixed API calls | VERIFIED | Core pipeline correct (BATCH_SIZE=50, SHA-256 dedup, checkpoint, upsert wait=True, UpdateStatus.COMPLETED guard, empty corpus guard); sanity_check() uses query_points() (line 177); encoding_format="float" in probe_embedding_dim() (line 72) and embed_batch() (line 151); no search() calls remain |
| `backend/ingestion/tests/test_ingestion_evals.py` | 8 tests + 2 manual stubs, 10 eval dimensions — fixed API calls | VERIFIED | 8 tests + 2 stubs present; test_rank1_sanity_check uses query_points() (line 124) with response.points result access (lines 131-132); encoding_format="float" in both live API calls (lines 93 and 121); no search() calls remain |
| `Makefile` | eval-ingest, eval-ingest-fast, venv, install, ingest targets | VERIFIED | All required targets present with tab-indented recipes |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| docker-compose.yml backend | qdrant service | depends_on: condition: service_healthy | WIRED | Confirmed in docker-compose.yml |
| docker-compose.yml backend | QDRANT_HOST | environment: QDRANT_HOST: qdrant | WIRED | Confirmed — overrides default "localhost" |
| backend/Dockerfile | requirements.txt | COPY requirements.txt + pip install | WIRED | Build context is project root; requirements.txt at root |
| ingest.py | config.py | from backend.app.core.config import get_settings | WIRED | Module-level get_settings() call |
| ingest.py | chunker.py | from backend.ingestion.chunker import Chunk, _count_tokens, chunk_passage | WIRED | Confirmed import on line 20 |
| ingest.py sanity_check() | AsyncQdrantClient.query_points() | `await qdrant.query_points(collection_name=COLLECTION_NAME, query=vecs[0], limit=1, with_payload=True)` | WIRED | Confirmed at line 177; returns QueryResponse; result accessed via response.points[0].score at line 187 |
| ingest.py probe_embedding_dim() | openrouter.embeddings.create() | encoding_format="float" kwarg | WIRED | Confirmed at line 72 — matches main.py commit 4843320 pattern |
| ingest.py embed_batch() | openrouter.embeddings.create() | encoding_format="float" kwarg | WIRED | Confirmed at line 151 |
| test_rank1_sanity_check | AsyncQdrantClient.query_points() | `await qdrant_client.query_points(collection_name=COLLECTION_NAME, query=query_vec, limit=1, with_payload=True)` | WIRED | Confirmed at line 124; result accessed via response.points[0].score at line 132 |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| ingest.py sanity_check | response | qdrant.query_points() call | Yes (live Qdrant) | FLOWING — correct API call; response.points accessed |
| ingest.py embed_batch | embeddings | openrouter.embeddings.create() with encoding_format="float" | Yes (live API) | FLOWING |
| ingest.py main loop | points | embed_batch + chunk_passage + dataset JSON | Yes | FLOWING |
| test_rank1_sanity_check | response | qdrant_client.query_points() call | Yes (live Qdrant) | FLOWING — correct API call; response.points accessed |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| No search() calls remain in ingestion files | `grep -rn "qdrant.search\|qdrant_client.search" backend/ingestion/` | No output | PASS |
| query_points present in ingest.py | `grep -n "query_points" backend/ingestion/ingest.py` | Line 177 | PASS |
| query_points present in test file | `grep -n "query_points" backend/ingestion/tests/test_ingestion_evals.py` | Line 124 | PASS |
| encoding_format="float" in ingest.py (2 calls) | `grep -n "encoding_format" backend/ingestion/ingest.py` | Lines 72 and 151 | PASS |
| encoding_format="float" in test file (2 calls) | `grep -n "encoding_format" backend/ingestion/tests/test_ingestion_evals.py` | Lines 93 and 121 | PASS |
| query=vecs[0] (not query_vector=) in ingest.py | `grep -n "query=vecs\[0\]" backend/ingestion/ingest.py` | Line 179 | PASS |
| query=query_vec (not query_vector=) in test file | `grep -n "query=query_vec" backend/ingestion/tests/test_ingestion_evals.py` | Line 126 | PASS |
| response.points access in ingest.py | `grep -n "response\.points" backend/ingestion/ingest.py` | Lines 184, 187 | PASS |
| response.points access in test file | `grep -n "response\.points" backend/ingestion/tests/test_ingestion_evals.py` | Lines 131, 132 | PASS |
| Gap closure commits exist in git history | `git log --oneline -5` | 864671e and 92bda6f confirmed | PASS |
| Full live ingest run with sanity check log | Requires live Docker + API | Not runnable without infrastructure | SKIP (human required) |

---

## Requirements Coverage

All requirement IDs declared across all plans for Phase 1 are accounted for below.

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| INFRA-01 | 01-PLAN-02 | System starts with `docker compose up` | SATISFIED | docker-compose.yml defines all services; `docker compose up` starts qdrant + backend + phoenix |
| INFRA-02 | 01-PLAN-02 | Qdrant persists data across restarts via named Docker volumes | SATISFIED | Named volume `qdrant_storage` in docker-compose.yml; not a bind mount |
| INFRA-03 | 01-PLAN-01, 01-PLAN-03 | All secrets from .env; none in source code | SATISFIED | pydantic-settings BaseSettings reads from .env; no hardcoded keys found in backend/ |
| INFRA-04 | 01-PLAN-02, 01-PLAN-03 | Backend waits for Qdrant health before accepting requests | SATISFIED | `depends_on: condition: service_healthy`; _ensure_collection() also validates at FastAPI startup |
| INFRA-05 | 01-PLAN-01, 01-PLAN-03 | Python 3.11 .venv for local dev | SATISFIED | `venv: python3.11 -m venv .venv` in Makefile; requirements.txt present |
| INGEST-01 | 01-PLAN-04 | Ingestion reads all context passages from dataset JSON | SATISFIED | ingest.py loads DATASET_PATH = dataset/json/train/policy_qa_train.json; iterates all records |
| INGEST-02 | 01-PLAN-04 | Passages chunked to ≤450 tokens; list items not split | SATISFIED | chunker.py MAX_TOKENS=400, separators=["\n\n","\n",". "," "], _is_list_item_start() guard |
| INGEST-03 | 01-PLAN-04, 01-PLAN-05 | Each chunk stored with {text, title, source_doc, chunk_index} | SATISFIED | ingest.py payload dict includes all 4 required fields plus passage_id and token_count |
| INGEST-04 | 01-PLAN-04 | Ingestion runs as standalone offline process | SATISFIED | Entry point is `if __name__ == "__main__": asyncio.run(ingest())`; not triggered by FastAPI startup |
| INGEST-05 | 01-PLAN-04 | Batched embedding with rate-limit retry/sleep | SATISFIED | BATCH_SIZE=50, exponential backoff on 429, BATCH_SLEEP_SECONDS=3 |
| INGEST-06 | 01-PLAN-04, 01-PLAN-05, 01-PLAN-06 | Sanity check: known passage ranks #1 in search results | SATISFIED (code inspection) | sanity_check() in ingest.py calls query_points() (commit 864671e); test_rank1_sanity_check calls query_points() (commit 92bda6f); both use response.points result access; encoding_format="float" present in all live embedding calls; structurally correct per rag.py reference |

**Orphaned requirements check:** REQUIREMENTS.md maps INFRA-01 through INGEST-06 to Phase 1. All 11 are claimed in plan frontmatter and verified above. No orphaned requirements.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | All prior blockers resolved by gap closure | — | — |

No blockers, warnings, or notable anti-patterns detected in the modified files. The gap closure removed all four prior blocker-severity items.

---

## Human Verification Required

### 1. Full Ingestion Run — Sanity Check Log

**Test:** With a valid `.env` (real OPENROUTER_API_KEY) and Qdrant running (`docker compose up qdrant`), run `make ingest` and observe the terminal output to completion.
**Expected:** Final log lines include `[sanity_check] Running rank-1 sanity check...` followed by `[sanity_check] PASSED: rank-1 score=1.0000` (or any score > 0.99). No AttributeError, no crash.
**Why human:** Requires a live OpenRouter API key that incurs API calls, a running Qdrant container, and the full 17K-passage dataset file. Cannot execute programmatically in a static analysis context.

### 2. Qdrant Named Volume Persistence

**Test:** After full ingestion completes and `policies` collection has data, run `docker compose restart qdrant`, wait for the readyz endpoint (`curl -f http://localhost:6333/readyz`), then `curl -s http://localhost:6333/collections/policies | python -m json.tool` and compare `points_count` to the pre-restart value.
**Expected:** `points_count` is identical before and after the restart, confirming the named volume `qdrant_storage` persists across container lifecycle events.
**Why human:** Requires running Docker with an already-populated Qdrant instance.

### 3. Healthcheck-Gated Startup Order

**Test:** From a cold state (`docker compose down -v && docker compose up`), watch the combined log output (`docker compose logs -f`). Note the timestamps when Qdrant first passes its health check versus when the backend first logs a startup message.
**Expected:** Backend logs no application errors during Qdrant startup delay. Backend begins serving only after Qdrant is healthy. No "connection refused" or "collection not found" errors on first request.
**Why human:** Requires observing real container startup timing and interleaved log output; cannot be verified with static analysis.

---

## Gap Closure Summary

**Previous status:** gaps_found (3/4 SC verified, SC3 blocked by two root causes)

**Root cause 1 — qdrant-client API removal:** `qdrant.search()` and `qdrant_client.search()` were removed in qdrant-client 1.13+. The installed version is 1.17.1. The fix (migrate to `query_points()`) had been applied to `rag.py` in Phase 2 (commit b9cb972) but not back-ported to `ingest.py` (sanity_check()) or `test_ingestion_evals.py` (test_rank1_sanity_check).

**Root cause 2 — encoding_format omission:** The `encoding_format="float"` argument required by openai SDK 2.x to avoid an embedding parser bug had been applied to `main.py` (commit 4843320) but not to the two `embeddings.create()` calls in `ingest.py` (probe_embedding_dim() and embed_batch()) or the two live calls in `test_ingestion_evals.py`.

**Gap closure (Plan 01-06):** Five mechanical edits applied across two files. All four blockers from the prior report are resolved. Code inspection against the reference implementations in `rag.py` and `main.py` confirms structural correctness. Git confirms commits 864671e and 92bda6f exist and apply the described changes.

**Current status:** 4/4 SC verified. Three human verification items remain (live ingest run, volume persistence, startup ordering) — these were present in the original report and require live infrastructure.

---

_Verified: 2026-04-25T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Yes — gap closure after Plan 01-06_

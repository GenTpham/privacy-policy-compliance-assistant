---
phase: 01-infrastructure-data-ingestion
reviewed: 2026-04-25T00:00:00Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - .dockerignore
  - .env.example
  - .gitignore
  - Makefile
  - backend/Dockerfile
  - backend/__init__.py
  - backend/app/__init__.py
  - backend/app/core/__init__.py
  - backend/app/core/config.py
  - backend/app/core/telemetry.py
  - backend/app/main.py
  - backend/ingestion/__init__.py
  - backend/ingestion/chunker.py
  - backend/ingestion/ingest.py
  - backend/ingestion/tests/__init__.py
  - backend/ingestion/tests/test_ingestion_evals.py
  - docker-compose.yml
  - requirements-dev.txt
  - requirements.txt
findings:
  critical: 1
  warning: 6
  info: 4
  total: 11
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-04-25T00:00:00Z
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

The infrastructure and ingestion pipeline is well-structured overall: pydantic-settings config, async-first Qdrant client, chunker with overlap, checkpoint/resumability, and a solid eval suite. The critical failure is a deprecated API call in `sanity_check()` that will raise an error at the end of every ingest run. There are also two instances where `encoding_format="float"` was intentionally added to `main.py` (based on a prior fix in git history) but was not applied to the same API call in `ingest.py`. The lifespan clients are not shared to request handlers via `app.state`, which will cause the chat router to fail at runtime. Several smaller issues follow.

## Critical Issues

### CR-01: `sanity_check()` uses deprecated `qdrant.search()` — will raise `AttributeError` at runtime

**File:** `backend/ingestion/ingest.py:177`
**Issue:** `qdrant.search()` was removed from `qdrant-client` 1.13+ in favour of `query_points()`. The commit history confirms this migration was applied to other call sites (`b9cb972`) but `sanity_check()` was missed. Every successful ingest run will crash on the final sanity check, leaving the checkpoint in an inconsistent "completed but not verified" state.
**Fix:**
```python
# Replace qdrant.search() with qdrant.query_points()
results = await qdrant.query_points(
    collection_name=COLLECTION_NAME,
    query=vecs[0],
    limit=1,
    with_payload=True,
)
hits = results.points  # QueryResponse wraps points in .points attribute

if not hits:
    raise AssertionError("[sanity_check] FAILED: no results returned for first passage query")

score = hits[0].score
```

## Warnings

### WR-01: `probe_embedding_dim()` and `embed_batch()` omit `encoding_format="float"`

**File:** `backend/ingestion/ingest.py:72` and `backend/ingestion/ingest.py:151`
**Issue:** `main.py:27` explicitly passes `encoding_format="float"` with a comment referencing a prior OpenAI SDK 2.x embedding parser bug (`4843320`). The same fix was not applied to either embedding call in `ingest.py`. This means the ingest pipeline may receive base64-encoded embeddings that the SDK fails to parse, causing `probe_embedding_dim()` or `embed_batch()` to raise on some SDK versions.
**Fix:**
```python
# Line 72 — probe_embedding_dim
resp = await openrouter.embeddings.create(
    model=EMBED_MODEL, input="probe", encoding_format="float"
)

# Line 151 — embed_batch
resp = await openrouter.embeddings.create(
    model=EMBED_MODEL, input=texts, encoding_format="float"
)
```

### WR-02: `test_rank1_sanity_check` uses deprecated `qdrant_client.search()`

**File:** `backend/ingestion/tests/test_ingestion_evals.py:124`
**Issue:** Same deprecated `search()` method as CR-01. The test will raise `AttributeError` when run against `qdrant-client>=1.13`.
**Fix:**
```python
results = await qdrant_client.query_points(
    collection_name=COLLECTION_NAME,
    query=query_vec,
    limit=1,
    with_payload=True,
)
hits = results.points
assert hits, "No results returned for first passage query — collection may be empty"
score = hits[0].score
assert score > 0.99, (...)
```

### WR-03: Lifespan clients not stored in `app.state` — chat router has no access to them

**File:** `backend/app/main.py:72-84`
**Issue:** `openrouter` and `qdrant` are created inside `lifespan()` but never attached to `app.state`. The chat router imported at line 14 will have no way to access these shared clients. Any request handler that tries to obtain them (e.g. via `request.app.state`) will get an `AttributeError`, or the router will be forced to create new client instances on every request.
**Fix:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_tracing()

    openrouter = AsyncOpenAI(...)
    qdrant = AsyncQdrantClient(...)

    dim = await _probe_embedding_dim(openrouter, "nvidia/llama-nemotron-embed-vl-1b-v2")
    await _ensure_collection(qdrant, dim)

    # Attach to app.state so request handlers can access via request.app.state
    app.state.openrouter = openrouter
    app.state.qdrant = qdrant
    app.state.embed_model = "nvidia/llama-nemotron-embed-vl-1b-v2"

    print("[startup] FastAPI ready.")
    yield
    # Optionally: await qdrant.close()
```

### WR-04: `skipped_checkpoint` computed incorrectly and silently discarded

**File:** `backend/ingestion/ingest.py:257`
**Issue:** The variable `skipped_checkpoint` is computed on line 257 with a formula that is likely wrong (`len(seen_hashes) - len(work_queue) + len(completed_hashes)` double-counts entries that are in both `seen_hashes` and `completed_hashes`). It is also never referenced after assignment — it is dead code. The summary log on line 312 instead uses an ad-hoc expression `len(completed_hashes) - upserted` which produces the correct value only when resuming from a fresh checkpoint start. The inaccurate skip count may mask silent data loss during partial re-runs.
**Fix:** Remove the dead variable and use a clearer count in the summary:
```python
# Before the loop, snapshot how many were already done
initial_completed = len(completed_hashes)  # replaces the broken skipped_checkpoint

# In the summary log:
f"skipped_checkpoint={initial_completed} "
```

### WR-05: Makefile `eval-ingest-fast` has a malformed line continuation

**File:** `Makefile:29`
**Issue:** The command contains a literal `\n` string followed by two leading spaces:
```
.venv/bin/pytest backend/ingestion/tests/test_ingestion_evals.py -v --tb=short \n	  -k "not rank1 ..."
```
This is not a valid shell line continuation. `\n` is not the same as a backslash followed by a newline. Make will pass the literal characters `\n` to the shell, causing the `-k` filter to be silently ignored and all tests (including slow API tests) to run.
**Fix:** Replace `\n` with an actual backslash-newline continuation (a real line break immediately after the backslash):
```makefile
eval-ingest-fast:
	.venv/bin/pytest backend/ingestion/tests/test_ingestion_evals.py -v --tb=short \
	  -k "not rank1 and not embedding_dim and not resumability and not persistence"
```

### WR-06: `requirements-dev.txt` missing `pytest-timeout` declared in test docstring

**File:** `requirements-dev.txt:1-3` / `backend/ingestion/tests/test_ingestion_evals.py:11`
**Issue:** The test module docstring documents `pytest ... --timeout=120` as the correct invocation for API-dependent tests. `pytest-timeout` is not in `requirements-dev.txt`, so `--timeout=120` will silently be ignored (pytest does not error on unknown options from non-installed plugins). API-dependent tests that hang will block CI indefinitely.
**Fix:**
```
# requirements-dev.txt
pytest
pytest-asyncio
pytest-timeout
httpx
```

## Info

### IN-01: `qdrant/qdrant:latest` and `arizephoenix/phoenix:latest` are unpinned image tags

**File:** `docker-compose.yml:2` and `docker-compose.yml:33`
**Issue:** Using `latest` means the exact image pulled will differ between developer machines and CI over time, making builds non-reproducible. A breaking change in Qdrant's storage format or Phoenix's gRPC API could silently break the stack.
**Fix:** Pin to a specific digest or version tag, e.g.:
```yaml
image: qdrant/qdrant:v1.13.3
image: arizephoenix/phoenix:v10.6.0
```

### IN-02: Default `JWT_SECRET` in `.env.example` is a weak placeholder that hints at insecurity

**File:** `.env.example:12`
**Issue:** `JWT_SECRET=change-me-generate-with-openssl-rand-hex-32` — if a developer copies `.env.example` to `.env` without generating a real secret, the backend will start successfully with a predictable, publicly-visible JWT secret. The comment explains how to generate a proper value, but there is no runtime enforcement beyond the `minimum 32 characters` note.
**Fix:** Add a startup validator in `config.py` that rejects the known placeholder value:
```python
@field_validator("jwt_secret")
@classmethod
def jwt_secret_not_placeholder(cls, v: str) -> str:
    if v.startswith("change-me"):
        raise ValueError(
            "JWT_SECRET must be changed from the placeholder. "
            "Generate one with: openssl rand -hex 32"
        )
    if len(v) < 32:
        raise ValueError("JWT_SECRET must be at least 32 characters")
    return v
```

### IN-03: `_is_list_item_start()` in chunker is defined but never called

**File:** `backend/ingestion/chunker.py:42-47`
**Issue:** The function `_is_list_item_start()` is defined with a detailed docstring about the "Atomic unit rule" but is never referenced anywhere in `chunk_passage()` or its helpers. This is dead code that adds cognitive overhead without providing the stated semantic protection.
**Fix:** Either integrate the function into the chunking logic to prevent splitting list items mid-item, or remove it until the feature is implemented.

### IN-04: Module-level client instantiation in `ingest.py` calls `get_settings()` at import time

**File:** `backend/ingestion/ingest.py:48-63`
**Issue:** `settings = get_settings()`, `openrouter = AsyncOpenAI(...)`, and `qdrant = AsyncQdrantClient(...)` are all executed at module import time (not inside `ingest()`). This means importing any symbol from `ingest.py` (as the test suite does on line 238) will trigger a `ValidationError` if `OPENROUTER_API_KEY` is not set in the environment — even in tests that mock the client. This pattern also makes the module harder to test in isolation.
**Fix:** Move client construction inside `ingest()` (and accept them as parameters in `embed_batch`, `ensure_collection`, `sanity_check`), or guard with a lazy-init pattern. At minimum, the `test_rate_limit_backoff` test currently relies on patching the already-constructed module-level `openrouter` object, which works but is fragile.

---

_Reviewed: 2026-04-25T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

---
phase: 08-corpus-expansion
reviewed: 2026-05-05T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - backend/ingestion/ingest_doc.py
  - backend/ingestion/validate_corpus.py
  - backend/ingestion/tests/test_ingest_doc.py
  - requirements.txt
findings:
  critical: 3
  warning: 4
  info: 2
  total: 9
status: issues_found
---

# Phase 08: Code Review Report

**Reviewed:** 2026-05-05T00:00:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Four files were reviewed: the single-document ingest CLI (`ingest_doc.py`), the corpus health validator (`validate_corpus.py`), the test suite for the ingest CLI, and `requirements.txt`. The implementation is generally well-structured and follows project conventions (async-first, raw RAG, no LangChain). Three blockers were found: the `qdrant.retrieve()` call crashes if the collection does not yet exist (the very first ingest), the module-level client instantiation in `validate_corpus.py` crashes on import unless all required env vars are set, and the Qdrant `vectors` config access makes an unsafe attribute assumption that will raise `AttributeError` on collections with named vectors. Four warnings cover retry logic that silently abandons non-rate-limit errors, the missing-collection crash in the validator, an unpinned `pypdf` dependency, and a sleep that fires after the final batch.

---

## Critical Issues

### CR-01: `qdrant.retrieve()` called before collection exists — crashes on first-ever ingest

**File:** `backend/ingestion/ingest_doc.py:211`

**Issue:** `ingest_doc` calls `qdrant.retrieve()` at step 6 (dedup check) before calling `ensure_collection()` at step 9. When the Qdrant `policies` collection does not yet exist — the very first time any document is ingested — `retrieve()` raises an exception (Qdrant returns a 404). The dedup check is supposed to be a convenience; it should not block initial ingestion. The `ensure_collection` guard is wasted because execution never reaches it.

**Fix:** Move the `probe_embedding_dim` / `ensure_collection` calls to before the `retrieve` call, or wrap the `retrieve` call to handle a missing-collection error gracefully:

```python
# Step 5. Initialize clients
openrouter, qdrant = _make_clients()

# Step 6. Probe dim and ensure collection exists FIRST
dim = await probe_embedding_dim(openrouter)
await ensure_collection(qdrant, dim)

# Step 7. Retrieve existing IDs from Qdrant (dedup check — collection now guaranteed to exist)
found = await qdrant.retrieve(
    collection_name=COLLECTION_NAME,
    ids=all_ids,
    with_payload=False,
    with_vectors=False,
)
existing = {str(r.id) for r in found}

# Step 8. Dry-run path — no writes
if dry_run:
    ...
    return

# Step 9. Filter to new-only chunks
new_pairs = [(c, uid) for c, uid in zip(chunks, all_ids) if uid not in existing]
if not new_pairs:
    print("[ingest_doc] All chunks already indexed — nothing to do.")
    return

# Step 10. Batch embed and upsert (collection already ensured above — remove second call)
```

Note: with this reordering, `ensure_collection` and `probe_embedding_dim` are called even on dry-run and even when everything is already indexed, which adds two API calls. An alternative is to catch the specific Qdrant "collection not found" exception in the retrieve call and short-circuit to `existing = set()`.

---

### CR-02: Module-level client instantiation in `validate_corpus.py` — crashes on import without env vars

**File:** `backend/ingestion/validate_corpus.py:24-28`

**Issue:** `get_settings()` and `AsyncQdrantClient(...)` are executed at module scope, not inside `validate_corpus()`. `get_settings()` raises `pydantic_core.ValidationError` if `OPENROUTER_API_KEY` or `JWT_SECRET` are not set — both are required with no defaults. This means:
1. `import validate_corpus` in any test or other module will crash unless the environment is fully configured.
2. Any future import-time usage (e.g., `from backend.ingestion.validate_corpus import ...`) will fail in CI or unit-test contexts.
3. The `AsyncQdrantClient` is created at import time, opening a connection handle before any async event loop is running, which is incorrect for async clients.

**Fix:** Move client initialization inside the `validate_corpus()` function:

```python
async def validate_corpus() -> None:
    settings = get_settings()
    qdrant = AsyncQdrantClient(
        url=f"http://{settings.qdrant_host}:{settings.qdrant_port}",
        api_key=settings.qdrant_api_key or None,
    )

    # Step 1 — Total count
    count_result = await qdrant.count(collection_name=COLLECTION_NAME, exact=True)
    ...
```

This mirrors the pattern used in `ingest_doc.py` (`_make_clients()` called inside the async function), which is correct.

---

### CR-03: Unsafe attribute access on `vectors` config — `AttributeError` if collection uses named vectors

**File:** `backend/ingestion/ingest_doc.py:143,150`

**Issue:** `ensure_collection` accesses `info.config.params.vectors.size` and `info.config.params.vectors.distance` as if `vectors` is always a `VectorParams` object. In Qdrant, when a collection is created with named vectors (the `vectors_config` is a `dict[str, VectorParams]`), `info.config.params.vectors` is a `dict`, not a `VectorParams`. Accessing `.size` on a dict raises `AttributeError`. This crash would occur if a collection named `policies` was created with named vectors by any other tool or migration.

```python
existing_dim = info.config.params.vectors.size          # line 143 — AttributeError if vectors is dict
...
if info.config.params.vectors.distance != Distance.COSINE:  # line 150 — same
```

**Fix:** Add a type guard before accessing `.size` and `.distance`:

```python
vectors_config = info.config.params.vectors
if isinstance(vectors_config, dict):
    raise RuntimeError(
        f"[ensure_collection] Collection '{COLLECTION_NAME}' uses named vectors, "
        "but this pipeline expects a single unnamed vector config. "
        "Delete and recreate the collection."
    )
existing_dim = vectors_config.size
...
if vectors_config.distance != Distance.COSINE:
    ...
```

---

## Warnings

### WR-01: `embed_batch` retry logic silently abandons non-rate-limit errors on first failure

**File:** `backend/ingestion/ingest_doc.py:105-113`

**Issue:** The retry loop only retries on 429/rate-limit errors. Any other transient error (e.g., `ConnectionError`, `TimeoutError`, HTTP 502/503) causes an immediate `raise RuntimeError(...)` on the first attempt without retrying. This is fragile for a production ingestion pipeline that may run over slow or unstable network connections to OpenRouter.

Additionally, on the final attempt (`attempt == retries - 1`) for a rate-limit error, the condition `is_rate_limit and attempt < retries - 1` is False (because `attempt` equals `retries - 1`), so execution falls through to `raise RuntimeError(...)`, which is correct. But the error message says "failed after {retries} retries" even when the failure happened on attempt 0 for a non-rate-limit error — misleading.

**Fix:** Widen retry to cover transient errors, or at minimum raise the original exception type instead of wrapping:

```python
RETRYABLE_STATUS_CODES = {"429", "500", "502", "503", "504"}

for attempt in range(retries):
    try:
        resp = await openrouter.embeddings.create(
            model=EMBED_MODEL, input=texts, encoding_format="float"
        )
        return [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]
    except Exception as exc:
        err_str = str(exc).lower()
        is_retryable = any(code in err_str for code in RETRYABLE_STATUS_CODES) or "rate limit" in err_str
        if is_retryable and attempt < retries - 1:
            wait = 2 ** attempt
            print(f"[rate_limit] retryable error on attempt {attempt + 1}/{retries} — sleeping {wait}s")
            await asyncio.sleep(wait)
            continue
        raise  # re-raise original exception, preserving type and traceback
raise RuntimeError(f"embed_batch failed after {retries} retries")
```

---

### WR-02: `validate_corpus.py` has no error handling for missing collection

**File:** `backend/ingestion/validate_corpus.py:34`

**Issue:** If the `policies` collection does not exist in Qdrant, `qdrant.count()` raises a raw Qdrant exception with no user-friendly message. The validator is a diagnostic tool and should provide a clear, actionable error rather than a stack trace.

**Fix:** Wrap the initial count call:

```python
from qdrant_client.http.exceptions import UnexpectedResponse

try:
    count_result = await qdrant.count(collection_name=COLLECTION_NAME, exact=True)
except UnexpectedResponse as exc:
    if "404" in str(exc) or "not found" in str(exc).lower():
        print(f"[error] Collection '{COLLECTION_NAME}' does not exist. Run ingestion first.")
        return
    raise
```

---

### WR-03: `pypdf` is unpinned in `requirements.txt`

**File:** `requirements.txt:16`

**Issue:** All other critical packages are pinned to exact versions (`fastapi==0.136.0`, `qdrant-client==1.17.1`, `openai==2.32.0`), but `pypdf` has no version constraint. `pypdf` has a history of breaking changes between major versions (v3 → v4 changed the API significantly). An unconstrained `pypdf` will be upgraded silently in any fresh Docker build, potentially breaking `extract_pdf`.

**Fix:** Pin `pypdf` to a known-good version:

```
pypdf==5.4.0
```

(Replace `5.4.0` with the version verified during development.)

---

### WR-04: `asyncio.sleep` fires unconditionally after the last batch

**File:** `backend/ingestion/ingest_doc.py:277`

**Issue:** `await asyncio.sleep(BATCH_SLEEP_SECONDS)` is inside the batch loop with no guard, so it fires after the final batch. For a single-batch document (the common case), this adds 3 unnecessary seconds after all work is complete.

**Fix:** Sleep only between batches, not after the last one:

```python
for batch_start in range(0, total, BATCH_SIZE):
    batch = new_pairs[batch_start: batch_start + BATCH_SIZE]
    ...
    result = await qdrant.upsert(...)
    if result.status != UpdateStatus.COMPLETED:
        raise RuntimeError(...)

    # Sleep only between batches — skip after the last one
    if batch_start + BATCH_SIZE < total:
        await asyncio.sleep(BATCH_SLEEP_SECONDS)
```

---

## Info

### IN-01: `test_ingest_doc_upserts_new_chunks` — fragile `points` extraction from `call_args`

**File:** `backend/ingestion/tests/test_ingest_doc.py:227`

**Issue:** The test extracts `points` with a fragile fallback: `call_kwargs.args[0] if call_kwargs.args else []`. If `qdrant.upsert` is ever called with `points` as a positional argument, this returns the `collection_name` string, not the points list — silently making `len(points) == 1` pass because `len("policies") == 8`. The assertion `points[0].payload["file_type"]` would then raise `AttributeError` and expose the bug, but `assert len(points) == 1` would pass falsely if a single-character collection name were used.

**Fix:** Assert the keyword argument directly, which is how `ingest_doc.py` actually calls `upsert`:

```python
call_kwargs = mock_qdrant.upsert.call_args.kwargs
points = call_kwargs["points"]
assert len(points) == 1
```

---

### IN-02: Magic constant `BATCH_SLEEP_SECONDS = 3` with no comment explaining rate-limit rationale

**File:** `backend/ingestion/ingest_doc.py:27`

**Issue:** `BATCH_SLEEP_SECONDS = 3` is defined as a constant but has no comment explaining what rate limit it defends against or how the value was chosen. Future maintainers have no context for whether this value is conservative, calibrated, or arbitrary.

**Fix:** Add an inline comment:

```python
BATCH_SLEEP_SECONDS = 3  # pause between embedding batches — OpenRouter free-tier rate limit is ~20 RPM
```

---

_Reviewed: 2026-05-05T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

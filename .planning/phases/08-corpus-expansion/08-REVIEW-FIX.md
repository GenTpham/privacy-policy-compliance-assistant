---
phase: 08-corpus-expansion
fixed_at: 2026-05-05T00:00:00Z
review_path: .planning/phases/08-corpus-expansion/08-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 6
skipped: 1
status: partial
---

# Phase 08: Code Review Fix Report

**Fixed at:** 2026-05-05T00:00:00Z
**Source review:** .planning/phases/08-corpus-expansion/08-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (3 Critical + 4 Warning)
- Fixed: 6
- Skipped: 1

## Fixed Issues

### CR-01: `qdrant.retrieve()` called before collection exists — crashes on first-ever ingest

**Files modified:** `backend/ingestion/ingest_doc.py`
**Commit:** 060c8ba
**Applied fix:** Moved `probe_embedding_dim` and `ensure_collection` calls to step 6 (before the dedup `retrieve` at step 7). Collection is now guaranteed to exist before any `retrieve()` or `upsert()` call. The batch loop comment updated to "collection already ensured above". Step numbers in comments renumbered accordingly.

---

### CR-02: Module-level client instantiation in `validate_corpus.py` — crashes on import without env vars

**Files modified:** `backend/ingestion/validate_corpus.py`
**Commit:** 97200d9
**Applied fix:** Removed the `# ── Client initialization ──` module-level block entirely. `settings = get_settings()` and `AsyncQdrantClient(...)` are now the first statements inside `validate_corpus()`, as local variables. Added a comment explaining why they must not be at module level, mirroring the `_make_clients()` pattern from `ingest_doc.py`.

---

### CR-03: Unsafe attribute access on `vectors` config — `AttributeError` if collection uses named vectors

**Files modified:** `backend/ingestion/ingest_doc.py`
**Commit:** cd8adf2
**Applied fix:** In `ensure_collection`, extracted `vectors_config = info.config.params.vectors` then added `isinstance(vectors_config, dict)` check. If the collection uses named vectors, a `RuntimeError` with a clear message is raised instead of crashing with `AttributeError`. The subsequent `.size` and `.distance` accesses now go through `vectors_config` (the extracted variable) rather than repeated `info.config.params.vectors` attribute chains.

---

### WR-01: `embed_batch` retry logic silently abandons non-rate-limit errors on first failure

**Files modified:** `backend/ingestion/ingest_doc.py`
**Commit:** b03a36b
**Applied fix:** Added `RETRYABLE_STATUS_CODES = {"429", "500", "502", "503", "504"}` constant before `embed_batch`. The retry condition now checks `any(code in err_str for code in RETRYABLE_STATUS_CODES) or "rate limit" in err_str`. On the final attempt (or a non-retryable error), the function does a bare `raise` to re-raise the original exception preserving its type and traceback, rather than wrapping it in `RuntimeError`.

---

### WR-02: `validate_corpus.py` has no error handling for missing collection

**Files modified:** `backend/ingestion/validate_corpus.py`
**Commit:** 883a179
**Applied fix:** Added `from qdrant_client.http.exceptions import UnexpectedResponse` import. Wrapped the `qdrant.count()` call in `try/except UnexpectedResponse`. If the exception contains "404" or "not found", prints `[error] Collection 'policies' does not exist. Run ingestion first.` and returns early. Other `UnexpectedResponse` variants are re-raised.

---

### WR-03: `pypdf` is unpinned in `requirements.txt`

**Files modified:** `requirements.txt`
**Commit:** e8f902b
**Applied fix:** Changed `pypdf` to `pypdf>=4.0,<5`. Uses a range rather than an exact pin to allow patch-level updates within the 4.x stable series while blocking a future major-version upgrade that could introduce breaking API changes. (The REVIEW.md suggested either `pypdf==5.4.0` or `pypdf>=4.0,<5`; the range form is used per the prompt guidance.)

---

### WR-04: `asyncio.sleep` fires unconditionally after the last batch

**Files modified:** `backend/ingestion/ingest_doc.py`
**Commit:** d27aae9
**Applied fix:** Wrapped `await asyncio.sleep(BATCH_SLEEP_SECONDS)` with `if batch_start + BATCH_SIZE < total:`. Added a comment explaining the guard. Sleep now only fires between batches, eliminating the 3-second unnecessary delay after the final batch completes.

---

## Skipped Issues

### IN-01: `test_ingest_doc_upserts_new_chunks` — fragile `points` extraction from `call_args`

**File:** `backend/ingestion/tests/test_ingest_doc.py:227`
**Reason:** Finding is classified as Info (IN-01), which is outside the `critical_warning` fix scope. Not processed.
**Original issue:** The test extracts `points` with a fragile fallback `call_kwargs.args[0] if call_kwargs.args else []` that silently passes if `upsert` is called with `points` as a positional argument. Fix would assert `call_kwargs.kwargs["points"]` directly.

---

_Fixed: 2026-05-05T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_

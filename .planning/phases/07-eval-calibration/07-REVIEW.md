---
phase: 07-eval-calibration
reviewed: 2026-05-05T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - backend/app/core/config.py
  - backend/app/services/rag.py
  - backend/app/tests/conftest.py
  - backend/app/tests/test_rag.py
  - backend/eval/passage_existence_check.py
findings:
  critical: 0
  warning: 5
  info: 3
  total: 8
status: issues_found
---

# Phase 07: Code Review Report

**Reviewed:** 2026-05-05T00:00:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

This phase moved `score_threshold` from a hardcoded literal in `rag.py` into pydantic-settings (`config.py`), updated `test_rag.py` assertions to call `get_settings().score_threshold` dynamically, and introduced `passage_existence_check.py` as a calibration script. The structural goals are correctly implemented: the threshold is now overridable via `SCORE_THRESHOLD` env var and the tests no longer hardcode the literal value.

Five warnings and three informational items were found. No critical security vulnerabilities or data-loss risks are present.

The most consequential issue (WR-01) is a latent test reliability defect: `_fake_stream` is an async generator function, and `AsyncMock(return_value=_fake_stream("token"))` stores the **unawaited generator object** as the return value rather than the async iterable. The tests happen to pass today because `pytest-asyncio` in auto mode tolerates this, but the mock does not accurately represent the real call path, making it fragile under mock library updates.

---

## Warnings

### WR-01: `AsyncMock(return_value=_fake_stream(...))` stores an unawaited async generator object

**File:** `backend/app/tests/test_rag.py:83,116,214,263`

**Issue:** `_fake_stream` is an `async def` function containing `yield`, making it an async generator *function*. Calling `_fake_stream("token")` returns an async generator object immediately (no await needed). However, the production code path does `stream = await openrouter.chat.completions.create(...)` and then `async for chunk in stream:`. When `AsyncMock(return_value=_fake_stream("token"))` is used, `await create(...)` returns the already-constructed generator object — which works accidentally because the generator is iterable. But if the mock were configured via `side_effect` (the semantically correct approach for an async generator callable) or if `AsyncMock` behaviour changes, the tests would silently yield zero tokens. The tests confirm streaming shape, but the mock does not faithfully model the real awaitable → iterable boundary, leaving the delta-before-done assertion brittle.

**Fix:**

```python
# Option A — side_effect (correct for async-generator-backed mocks):
mock_openrouter.chat.completions.create = AsyncMock(side_effect=lambda **kw: _fake_stream("Hello"))

# Option B — wrap in AsyncMock that returns the generator when awaited (explicit):
async def _make_stream(token):
    return _fake_stream(token)   # awaiting returns the async generator

mock_openrouter.chat.completions.create = AsyncMock(side_effect=_make_stream)
```

---

### WR-02: `lru_cache` on `get_settings()` prevents `SCORE_THRESHOLD` env override in tests

**File:** `backend/app/core/config.py:56` / `backend/app/tests/conftest.py:10`

**Issue:** `get_settings` is decorated with `@lru_cache`. Once the cache is populated (at import time when `rag.py` evaluates `_settings = get_settings()` at module level), any subsequent `os.environ["SCORE_THRESHOLD"] = "0.35"` override in a test has no effect — `get_settings()` returns the cached instance. The test in `test_retrieve_params` (line 72) compares `call_kwargs.get("score_threshold") == get_settings().score_threshold`, which tests equality against the same cached value both sides, making the assertion trivially pass regardless of what was actually passed to Qdrant. A test that temporarily patches `SCORE_THRESHOLD` to a different value to verify the threshold is forwarded would silently be testing the wrong value.

**Fix:** Either clear the cache in a test fixture, or expose a `_get_settings_uncached` path for tests. At minimum, document the limitation:

```python
# In conftest.py — add a fixture or autouse fixture that clears the cache:
import pytest
from backend.app.core.config import get_settings

@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
```

---

### WR-03: Silent empty-string embedding call when both `context` and `answers.text` are absent

**File:** `backend/eval/passage_existence_check.py:163-168`

**Issue:** On line 164, `text_to_check` falls back to `ground_truth`, which itself falls back to `""` (line 159). When an example in the validation JSON has neither a `"context"` field nor `"answers": {"text": [...]}` entries, `text_to_check` is an empty string. The script then calls `openrouter.embeddings.create(input="")` which either returns a meaningless zero-length embedding or triggers an API error. The outer `except Exception` on line 180 catches this and prints an error, but the `all_results` list is silently shorter, distorting the summary statistics without any indication that a record was skipped vs. had a genuine API error.

**Fix:**

```python
text_to_check = context_text if context_text else ground_truth
if not text_to_check.strip():
    print(f"{i:>4}  {title[:20]:20}  SKIP: empty context and no answer text", file=sys.stderr)
    continue
```

---

### WR-04: Off-by-one in percentile index calculation — `p90` indexes position `0.90 * n`, not the 90th percentile

**File:** `backend/eval/passage_existence_check.py:206,213,220,227`

**Issue:** Standard percentile calculation for a 0-based sorted list uses `int(len * fraction)` which gives the element *at* that fraction of the list, not the P-th percentile value (which conventionally uses `ceil(len * fraction) - 1` or nearest-rank). For `n=20` examples, `p90_idx = int(20 * 0.90) = 18` which is the 19th element (0-based), i.e., the second-highest value — reasonably close. But for `n=10`, `p90_idx = 9` which is the maximum element, misrepresenting the 90th percentile as the max. This produces misleading calibration data in ANALYSIS.md that informed the threshold decision.

**Fix:**

```python
# Use nearest-rank method (no external dependency):
def _percentile(sorted_data: list, p: float) -> float:
    n = len(sorted_data)
    idx = max(0, min(n - 1, int(round(p * n)) - 1))
    return sorted_data[idx]

# Or use statistics.quantiles() from stdlib (Python 3.8+):
import statistics
q = statistics.quantiles(all_scores, n=100)  # returns 99 cut points
p25, p75, p90 = q[24], q[74], q[89]
```

---

### WR-05: `found_in_corpus` heuristic truncates to 50 characters — unreliable for short or non-ASCII passages

**File:** `backend/eval/passage_existence_check.py:90-93`

**Issue:** The corpus-hit check (lines 90-93) truncates `context_lower` to its first 50 characters and searches for that prefix in each returned passage's text. This produces false negatives when:
- The ground-truth passage starts with boilerplate shared across many passages (e.g. a policy header repeated verbatim), causing false positives.
- The passage is shorter than 50 characters, making the prefix the full text, but the indexed chunk may have been split differently.
- Vietnamese text (multi-byte UTF-8) may be truncated mid-character at byte boundaries when `[:50]` operates on the character string (safe at the Python level but the 50-char window may be insufficient for Vietnamese where meaningful content starts further in).

The `found_in_corpus` field was used in the ANALYSIS.md calibration results. Misleading values here could cause incorrect conclusions about whether passages are indexed.

**Fix:**

```python
# Use a longer prefix and normalise whitespace for robustness:
context_norm = " ".join(context_text.lower().split())[:120]
found_in_corpus = any(
    context_norm[:80] in " ".join((r.payload.get("text", "") or "").lower().split())
    for r in results.points
)
```

---

## Info

### IN-01: Module-level `get_settings()` call in `rag.py` forces env vars to be set before import

**File:** `backend/app/services/rag.py:41`

**Issue:** Line 41 calls `get_settings()` at module import time to construct `_settings` for the module-level `openrouter` and `qdrant` client singletons (lines 43-55). This means any test that imports from `rag.py` requires `OPENROUTER_API_KEY` and `JWT_SECRET` to be in the environment *before* the import. `conftest.py` handles this via `os.environ.setdefault(...)` at the top of the file, but only if `conftest.py` is loaded first (pytest guarantee). Any standalone script that imports `rag.py` without pre-setting env vars will raise a pydantic `ValidationError` at import time with no clear error message about what is missing.

**Fix:** This is an architectural trade-off already documented. At minimum, add a comment to `rag.py` noting that `conftest.py` must set env vars before import, and consider lazy client initialisation if the startup coupling becomes painful.

---

### IN-02: Histogram bucket for `"0.50+"` uses exclusive upper bound `1.00`, silently drops score `== 1.0`

**File:** `backend/eval/passage_existence_check.py:239,245`

**Issue:** The `"0.50+"` bucket is defined as `(0.50, 1.00)` and the loop condition is `lo <= s < hi`. A perfect cosine similarity score of exactly `1.0` (e.g. when a passage is queried verbatim) would fall outside all buckets and be omitted from the histogram count without any indication.

**Fix:**

```python
("0.50+", 0.50, float("inf")),  # catches all scores >= 0.50
```

---

### IN-03: `qdrant_api_key or None` double-None idiom is a no-op

**File:** `backend/app/services/rag.py:54`

**Issue:** `_settings.qdrant_api_key` is typed `str | None = None`. The expression `_settings.qdrant_api_key or None` returns `None` when the value is `None` and also returns `None` when the value is `""` (empty string). But since pydantic-settings reads from `.env`, an empty string is a possible value; the `or None` normalises it — which is the apparent intent. However the idiom is confusing because the field type already allows `None` and pydantic will have already set it to `None` if absent. The `or None` adds no value when the field is `None`, and converts `""` (which should arguably be a misconfiguration) into `None` silently.

**Fix:** Either validate that `qdrant_api_key` is non-empty when set (via a field validator in `config.py`), or simplify to:

```python
qdrant = AsyncQdrantClient(
    url=f"http://{_settings.qdrant_host}:{_settings.qdrant_port}",
    api_key=_settings.qdrant_api_key,  # None when not set; pydantic already handles this
)
```

---

_Reviewed: 2026-05-05T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

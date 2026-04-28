---
phase: 05-cross-document-conflict-detection
reviewed: 2026-04-28T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - backend/app/api/chat.py
  - backend/app/services/rag.py
  - backend/app/tests/conftest.py
  - backend/app/tests/test_chat_endpoint.py
  - backend/app/tests/test_rag.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-04-28T00:00:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Phase 5 adds keyword-based conflict routing in `chat.py` (`is_conflict_query` + `_CONFLICT_PATTERN`) and a parallel async generator `stream_conflict_answer` in `rag.py` along with its prompt-builder `_build_conflict_messages`. The TDD stubs in the three test files are replaced with passing assertions and a new multi-document conftest fixture.

The routing logic and prompt construction are correct. No security vulnerabilities or data-loss risks were found. The three warnings are maintainability and correctness concerns that should be addressed before the next phase builds on this code. The info items are minor quality notes.

## Warnings

### WR-01: stream_conflict_answer duplicates ~80% of stream_answer — divergence risk

**File:** `backend/app/services/rag.py:249-344`
**Issue:** `stream_conflict_answer` is a near-verbatim copy of `stream_answer`. The only behavioral differences are `limit=10` (vs `limit=5`) and the call to `_build_conflict_messages` (vs `_build_messages`). The embed call (lines 271-276), Qdrant retrieval (279-285), streaming loop (301-320), citation fallback (327-336), and done yield (344) are identical. Any future bug fix or enhancement applied to `stream_answer` (error handling, retry logic, token counting, etc.) must be manually mirrored to `stream_conflict_answer`. This has already caused one silent divergence: the Verdict warning log (lines 339-342) exists only in the conflict path — there is no equivalent guard in the standard path, which makes the two functions harder to reason about in parallel over time.
**Fix:** Extract the shared pipeline into a private helper that accepts `limit` and `message_builder` parameters:

```python
async def _stream_rag(
    message: str,
    history: list[dict],
    limit: int,
    message_builder,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> AsyncGenerator[dict, None]:
    embed_resp = await openrouter.embeddings.create(
        model=EMBEDDING_MODEL, input=message, encoding_format="float"
    )
    query_vector = embed_resp.data[0].embedding
    response = await qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=limit,
        score_threshold=0.55,
        with_payload=True,
    )
    results = response.points
    if not results:
        yield {"type": "done", "answer": "No matching policy found for your question.", "citations": []}
        return
    messages = message_builder(message, results, history)
    # ... shared streaming loop and citation fallback ...

async def stream_answer(message, history, **kw):
    async for event in _stream_rag(message, history, limit=5, message_builder=_build_messages, **kw):
        yield event

async def stream_conflict_answer(message, history, **kw):
    async for event in _stream_rag(message, history, limit=10, message_builder=_build_conflict_messages, **kw):
        yield event
```

---

### WR-02: Empty-answer done event when LLM yields zero content tokens

**File:** `backend/app/services/rag.py:164,191-202` (same pattern at `301,327-344`)
**Issue:** If the LLM stream produces only `None`-content chunks (e.g. the model returns an empty completion, all chunks have `delta.content = None`), `full_answer` remains `""`. `_build_verified_citations("", results)` returns `[]`, so the abstain fallback fires and returns all retrieved chunks as citations. The done event becomes `{"type": "done", "answer": "", "citations": [...all chunks...]}`. Clients receive citations with no answer text — this is likely to render confusingly (citation list with no accompanying narrative). This can occur in practice if the model hits a content filter, returns an empty stop sequence, or if the API returns finish_reason=`content_filter` with no tokens.
**Fix:** Detect the empty-answer case explicitly and substitute the abstain message rather than silently falling back to raw citations:

```python
if not full_answer:
    yield {
        "type": "done",
        "answer": "The provided policies do not contain sufficient information to answer this question.",
        "citations": [],
    }
    return

citations = _build_verified_citations(full_answer, results)
if not citations and results:
    # LLM answered without [N] refs — show which sources were consulted
    citations = [...]

yield {"type": "done", "answer": full_answer, "citations": citations}
```

---

### WR-03: test_conflict_route_dispatches_conflict_generator patches wrong target path

**File:** `backend/app/tests/test_chat_endpoint.py:135-136`
**Issue:** The test patches `backend.app.services.rag.stream_conflict_answer` and `backend.app.services.rag.stream_answer`, but `chat.py` imports the module via `from backend.app.services import rag` and calls `rag.stream_conflict_answer(...)`. The patch must target the name as accessed by the calling module — since `chat.py` looks up the attribute on the `rag` module object at call time (not a local binding), patching the module attribute is correct. However, if `chat.py` were ever refactored to import directly (`from backend.app.services.rag import stream_conflict_answer`), the patches would silently stop working. The test passes today but is fragile to that refactor.

Additionally, the test verifies `mock_conflict.assert_called_once()` but does not verify the arguments — specifically that `request.message` and `history` were passed correctly. A routing bug that calls `stream_conflict_answer("", [])` would pass the current assertion.
**Fix:** Add argument verification to the mock assertion:

```python
mock_conflict.assert_called_once_with(
    "mâu thuẫn về chính sách lưu trữ dữ liệu",
    [],  # history
)
```

And add a comment explaining why the module-level patch target is correct for module-attribute access.

---

## Info

### IN-01: History-slice condition is unnecessarily verbose in both message builders

**File:** `backend/app/services/rag.py:75` (same at line `242`)
**Issue:** `history[-6:] if len(history) > 6 else history` is equivalent to just `history[-6:]`. Python's slice operator never raises for out-of-range slices — `[1, 2][-6:]` returns `[1, 2]`. The conditional adds a branch with no effect and makes readers wonder if there is a semantic difference between the two cases.
**Fix:**
```python
recent_history = history[-6:]
```

---

### IN-02: CHAT_MODEL constant includes -it suffix not mentioned in project constraints

**File:** `backend/app/services/rag.py:21`
**Issue:** `CHAT_MODEL = "google/gemma-4-26b-a4b-it"` — the CLAUDE.md project constraint states the model as "Gemma 4 26B A4B" without the `-it` (instruction-tuned) suffix. If the OpenRouter model identifier changes or the constraint is updated to a different variant, this value is the only place it is set. Not a bug, but worth confirming the exact identifier against OpenRouter's model catalog.
**Fix:** Confirm `google/gemma-4-26b-a4b-it` is the correct current OpenRouter model slug and add a brief comment noting the source, e.g.:
```python
# OpenRouter model slug — verify at: https://openrouter.ai/google/gemma-4-26b-a4b-it
CHAT_MODEL = "google/gemma-4-26b-a4b-it"
```

---

### IN-03: sample_scored_points_multi fixture is missing passage_id payload key

**File:** `backend/app/tests/conftest.py:139-153`
**Issue:** The `sample_scored_point` fixture (line 57-62) includes a `passage_id` key in its payload. The new `sample_scored_points_multi` fixture (lines 139-153) omits `passage_id`. This inconsistency is not a test failure today because no tested code path reads `passage_id` from a conflict chunk, but it creates an asymmetry between the two fixtures that may cause unexpected `KeyError` failures if future tests or production code begins reading `passage_id` from conflict results.
**Fix:**
```python
point.payload = {
    "text": text,
    "title": title,
    "source_doc": f"doc_{idx}",
    "chunk_index": 0,
    "passage_id": f"p-{idx:03d}",  # mirror sample_scored_point shape
}
```

---

_Reviewed: 2026-04-28T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

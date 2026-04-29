# Phase 5: Cross-Document Conflict Detection — Pattern Map

**Mapped:** 2026-04-28
**Files analyzed:** 5 (2 modified source files + 3 modified test files)
**Analogs found:** 5 / 5

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/services/rag.py` (add `stream_conflict_answer` + `_build_conflict_messages`) | service | streaming, request-response | `backend/app/services/rag.py` `stream_answer()` + `_build_messages()` | exact — same file, same pattern |
| `backend/app/api/chat.py` (add `is_conflict_query` + routing branch) | router | request-response | `backend/app/api/chat.py` `chat_endpoint()` | exact — same file, same pattern |
| `backend/app/tests/test_rag.py` (add 6 conflict tests) | test | request-response | `backend/app/tests/test_rag.py` existing tests | exact — same file, same pattern |
| `backend/app/tests/test_chat_endpoint.py` (add 3 conflict/detection tests) | test | request-response | `backend/app/tests/test_chat_endpoint.py` existing tests | exact — same file, same pattern |
| `backend/app/tests/conftest.py` (add `sample_scored_points_multi` fixture) | test fixture | — | `backend/app/tests/conftest.py` `sample_scored_point` fixture | exact — same file, extend pattern |

---

## Pattern Assignments

### `backend/app/services/rag.py` — `stream_conflict_answer()` (service, streaming)

**Analog:** `stream_answer()` in `backend/app/services/rag.py` (lines 113–202)

**Imports pattern** (lines 1–16): No new imports required. `re`, `AsyncGenerator`, `AsyncOpenAI`, `AsyncQdrantClient`, `get_settings`, `logger` are all already present.

**Core async generator pattern** (lines 113–202) — copy verbatim structure, change only `limit` and message builder:

```python
# backend/app/services/rag.py lines 113-148 — embed + retrieve structure to replicate
async def stream_answer(
    message: str,
    history: list[dict],
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> AsyncGenerator[dict, None]:
    # Step 1: Embed query
    embed_resp = await openrouter.embeddings.create(
        model=EMBEDDING_MODEL,
        input=message,
        encoding_format="float",
    )
    query_vector = embed_resp.data[0].embedding

    # Step 2: Retrieve — stream_conflict_answer changes limit=5 → limit=10
    response = await qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=5,          # ← change to 10 for conflict path
        score_threshold=0.55,
        with_payload=True,
    )
    results = response.points

    # Step 3: Early return on zero results (D-16 — same "No matching policy" response)
    if not results:
        yield {
            "type": "done",
            "answer": "No matching policy found for your question.",
            "citations": [],
        }
        return
```

**Streaming loop + error handling pattern** (lines 164–183) — copy verbatim into `stream_conflict_answer`:

```python
# backend/app/services/rag.py lines 164-183
full_answer = ""
try:
    stream = await openrouter.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        stream=True,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    async for chunk in stream:
        # Guard: first and last chunks have delta.content = None (Pitfall 1)
        if chunk.choices and chunk.choices[0].delta.content:
            token = chunk.choices[0].delta.content
            full_answer += token
            yield {"type": "delta", "content": token}
except Exception as exc:
    # Cannot change HTTP status after first byte sent — yield error event
    logger.error("LLM stream error: %s", exc)
    yield {"type": "error", "message": "LLM service temporarily unavailable"}
    return
```

**Abstain fallback block** (lines 191–200) — copy verbatim into `stream_conflict_answer`:

```python
# backend/app/services/rag.py lines 191-200
if not citations and results:
    citations = [
        {
            "id": i + 1,
            "qdrant_id": str(c.id),
            "title": c.payload.get("title", ""),
            "text": c.payload.get("text", ""),
        }
        for i, c in enumerate(results)
    ]

yield {"type": "done", "answer": full_answer, "citations": citations}
```

---

### `backend/app/services/rag.py` — `_build_conflict_messages()` (pure helper)

**Analog:** `_build_messages()` in `backend/app/services/rag.py` (lines 52–79)

**Core pattern** (lines 52–79) — same chunk injection format, different system instruction text:

```python
# backend/app/services/rag.py lines 52-79 — structure to replicate
def _build_messages(
    user_question: str,
    retrieved_chunks: list,
    history: list[dict],
) -> list[dict]:
    context_lines = [
        f"[{i}] source: {c.payload.get('title', 'Unknown')}\n{c.payload.get('text', '')}"
        for i, c in enumerate(retrieved_chunks, start=1)
    ]
    system_content = (
        "You are a privacy policy compliance assistant.\n"
        "Answer using ONLY the policy passages below. Cite each passage you use by its numeric ID: [1], [2], etc.\n"
        "Do not cite any source not listed in the numbered passages.\n\n"
        f"{ABSTAIN_INSTRUCTION}\n\n"
        "Context passages:\n" + "\n\n".join(context_lines)
    )
    # D-10: last 6 messages = last 3 user/assistant turns
    recent_history = history[-6:] if len(history) > 6 else history
    messages: list[dict] = [{"role": "system", "content": system_content}]
    messages.extend(recent_history)
    messages.append({"role": "user", "content": user_question})
    return messages
```

The conflict variant replaces the `system_content` string with the conflict-detection instruction block (document-by-document structure + verdict format + taxonomy + `ABSTAIN_INSTRUCTION`). The chunk injection format (`[{i}] source: {title}\n{text}`), history slicing (`history[-6:]`), and messages assembly are identical.

**`ABSTAIN_INSTRUCTION` constant** (lines 24–28) — reused by reference, not copied:

```python
# backend/app/services/rag.py lines 24-28
ABSTAIN_INSTRUCTION = (
    "If the provided passages do not contain the answer, respond: "
    "'The provided policies do not contain sufficient information to answer this question.' "
    "Do not infer, guess, or use outside knowledge."
)
```

---

### `backend/app/api/chat.py` — `is_conflict_query()` + routing branch (router)

**Analog:** `chat_endpoint()` in `backend/app/api/chat.py` (lines 58–81)

**Imports pattern** (lines 1–20) — add `import re` at the top; all other imports already present:

```python
# backend/app/api/chat.py lines 1-20
import json
from collections.abc import AsyncGenerator
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app.db.models import User
from backend.app.services import rag
from backend.app.services.auth import get_current_user
```

**Core routing pattern** (lines 58–81) — existing `_generate()` inner function; add a branch inside it:

```python
# backend/app/api/chat.py lines 74-81 — current _generate() to extend
async def _generate() -> AsyncGenerator[str, None]:
    async for event in rag.stream_answer(
        message=request.message,
        history=[h.model_dump() for h in request.history],
    ):
        yield f"data: {json.dumps(event)}\n\n"
```

After adding the routing branch this becomes:

```python
async def _generate() -> AsyncGenerator[str, None]:
    if is_conflict_query(request.message):
        generator = rag.stream_conflict_answer(request.message, history)
    else:
        generator = rag.stream_answer(request.message, history)
    async for event in generator:
        yield f"data: {json.dumps(event)}\n\n"
```

**Module-level compiled regex pattern** — place before the `router = APIRouter()` line, following the same module-level singleton convention already used for `openrouter` and `qdrant` in `rag.py`:

```python
import re

_CONFLICT_PATTERN = re.compile(
    r"conflict|contradict|mâu thuẫn|so sánh|khác nhau|differ|both documents",
    re.IGNORECASE,
)

def is_conflict_query(message: str) -> bool:
    # Note: "differ" matches "different"/"indifferent" — false positives accepted per D-03
    return bool(_CONFLICT_PATTERN.search(message))
```

---

### `backend/app/tests/test_rag.py` — 6 new conflict tests

**Analog:** Existing tests in `backend/app/tests/test_rag.py` (lines 39–197)

**Mock-based test pattern** (lines 39–51, 56–66) — copy this structure for `test_conflict_retrieve_params` and `test_conflict_done_event_shape`:

```python
# backend/app/tests/test_rag.py lines 56-66
@pytest.mark.asyncio
async def test_retrieve_params(mock_openrouter, mock_qdrant):
    """RAG-02: qdrant.search called with limit=5, score_threshold=0.55, with_payload=True."""
    with patch.object(rag, "openrouter", mock_openrouter), \
         patch.object(rag, "qdrant", mock_qdrant):
        events = [e async for e in stream_answer("test query", [])]

    mock_qdrant.query_points.assert_called_once()
    call_kwargs = mock_qdrant.query_points.call_args.kwargs
    assert call_kwargs.get("limit") == 5
    assert call_kwargs.get("score_threshold") == 0.55
    assert call_kwargs.get("with_payload") is True
```

For conflict path: same structure, assert `limit == 10` instead of `5`.

**Pure function test pattern** (lines 91–99) — copy for `test_conflict_prompt_contains_verdict_format` and `test_conflict_prompt_contains_classifications`:

```python
# backend/app/tests/test_rag.py lines 91-99
def test_system_prompt_abstain_wording(sample_scored_point):
    """
    RAG-04: _build_messages system content contains the exact D-05 abstain instruction.
    Pure function test — no mocks needed.
    """
    messages = _build_messages("test question", [sample_scored_point], [])
    system_content = messages[0]["content"]
    assert "The provided policies do not contain sufficient information to answer this question." in system_content
    assert "Do not infer, guess, or use outside knowledge." in system_content
```

For conflict path: call `_build_conflict_messages(...)` and assert for `"Verdict:"`, `"Contradictory"`, `"Consistent"`, `"One-Silent"`, and the `ABSTAIN_INSTRUCTION` wording.

**History slice test pattern** (lines 125–137) — copy for `test_conflict_history_sliced_to_6`:

```python
# backend/app/tests/test_rag.py lines 125-137
def test_history_sliced_to_6(sample_scored_point):
    long_history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"message {i}"}
        for i in range(20)
    ]
    messages = _build_messages("new question", [sample_scored_point], long_history)
    assert len(messages) == 8
    assert messages[0]["role"] == "system"
    assert messages[-1]["content"] == "new question"
```

**`_fake_stream` helper** (lines 24–34) — reuse as-is; no new stream helper needed:

```python
# backend/app/tests/test_rag.py lines 24-34
async def _fake_stream(token: str):
    """Async generator simulating one real token then a final None-content chunk."""
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = token
    yield chunk
    final = MagicMock()
    final.choices = [MagicMock()]
    final.choices[0].delta.content = None
    yield final
```

---

### `backend/app/tests/test_chat_endpoint.py` — 3 new detection/routing tests

**Analog:** Existing tests in `backend/app/tests/test_chat_endpoint.py` (lines 30–88)

**HTTP smoke test pattern** (lines 32–57) — copy for `test_conflict_route_dispatches_conflict_generator`:

```python
# backend/app/tests/test_chat_endpoint.py lines 32-57
@pytest.mark.asyncio
async def test_endpoint_content_type():
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_current_user
    try:
        with patch("backend.app.services.rag.stream_answer", side_effect=_minimal_done_stream):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/chat",
                    json={"message": "what is the data retention policy?", "history": []},
                )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
```

For conflict routing test: patch both `rag.stream_answer` and `rag.stream_conflict_answer`; send a message containing a conflict keyword; assert `stream_conflict_answer` was called and `stream_answer` was not.

**`_minimal_done_stream` stub** (lines 19–21) — reuse as-is for both `stream_answer` and `stream_conflict_answer` stubs:

```python
# backend/app/tests/test_chat_endpoint.py lines 19-21
async def _minimal_done_stream(*args, **kwargs):
    """Minimal rag.stream_answer stub — yields one done event, no LLM/Qdrant calls."""
    yield {"type": "done", "answer": "stubbed", "citations": []}
```

**`_stub_current_user` auth bypass** (lines 24–26) — reuse as-is in all new tests:

```python
# backend/app/tests/test_chat_endpoint.py lines 24-26
def _stub_current_user():
    return User(id=1, username="test", hashed_password="$argon2id$stub")
```

The `is_conflict_query` unit tests (pure function, no HTTP) do not need app fixtures — they import and call the function directly.

---

### `backend/app/tests/conftest.py` — `sample_scored_points_multi` fixture

**Analog:** `sample_scored_point` fixture in `backend/app/tests/conftest.py` (lines 48–63)

**Fixture pattern** (lines 48–63) — extend by producing a list of two MagicMock points from different source documents:

```python
# backend/app/tests/conftest.py lines 48-63 — existing fixture to extend
@pytest.fixture
def sample_scored_point():
    point = MagicMock()
    point.id = "abc-123"
    point.score = 0.82
    point.payload = {
        "text": "Personal data must be retained no longer than 30 days.",
        "title": "Privacy Policy v2",
        "source_doc": "policy_v2",
        "passage_id": "p-001",
    }
    return point
```

New fixture follows the same `MagicMock()` + `.payload` dict pattern:

```python
@pytest.fixture
def sample_scored_points_multi():
    """Two fake ScoredPoints from different source documents — for conflict path tests."""
    def _make(idx, title, text):
        point = MagicMock()
        point.id = f"id-{idx}"
        point.score = 0.80
        point.payload = {
            "text": text,
            "title": title,
            "source_doc": f"doc_{idx}",
            "chunk_index": 0,
        }
        return point
    return [
        _make(1, "Policy A", "Data is retained for 30 days."),
        _make(2, "Policy B", "Data is retained indefinitely."),
    ]
```

---

## Shared Patterns

### Async generator yield protocol
**Source:** `backend/app/services/rag.py` lines 153–202
**Apply to:** `stream_conflict_answer()` — identical three-event protocol:
- `{"type": "delta", "content": token}` — one per LLM token
- `{"type": "done", "answer": str, "citations": [...]}` — final event (payload shape unchanged per D-14)
- `{"type": "error", "message": str}` — on LLM exception

### SSE formatting
**Source:** `backend/app/api/chat.py` lines 74–79
**Apply to:** `_generate()` inner function in `chat_endpoint()` — identical for both paths:
```python
yield f"data: {json.dumps(event)}\n\n"
```

### `patch.object` mock pattern
**Source:** `backend/app/tests/test_rag.py` lines 42–44
**Apply to:** All 6 new `test_rag.py` tests that call `stream_conflict_answer`:
```python
with patch.object(rag, "openrouter", mock_openrouter), \
     patch.object(rag, "qdrant", mock_qdrant):
    events = [e async for e in stream_conflict_answer("query with conflict", [])]
```

### Auth bypass in HTTP tests
**Source:** `backend/app/tests/test_chat_endpoint.py` lines 24–26, 39
**Apply to:** All 3 new `test_chat_endpoint.py` tests:
```python
app.dependency_overrides[get_current_user] = _stub_current_user
```

### Module-level compiled regex
**Source:** `backend/app/services/rag.py` lines 18–28 (module-level constants pattern)
**Apply to:** `_CONFLICT_PATTERN` in `chat.py` — place at module level to avoid recompilation per request.

### `ABSTAIN_INSTRUCTION` reuse
**Source:** `backend/app/services/rag.py` lines 24–28
**Apply to:** `_build_conflict_messages()` — reference the same module-level constant by name (`f"{ABSTAIN_INSTRUCTION}"`) rather than duplicating the string.

---

## No Analog Found

None — all Phase 5 changes extend existing files using patterns already established in those files. No new modules are introduced.

---

## Metadata

**Analog search scope:** `backend/app/services/`, `backend/app/api/`, `backend/app/tests/`
**Files scanned:** 5 (`rag.py`, `chat.py`, `test_rag.py`, `test_chat_endpoint.py`, `conftest.py`)
**Pattern extraction date:** 2026-04-28

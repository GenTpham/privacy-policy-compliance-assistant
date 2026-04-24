---
phase: 02-core-rag-pipeline
reviewed: 2026-04-24T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - backend/app/api/__init__.py
  - backend/app/api/chat.py
  - backend/app/core/telemetry.py
  - backend/app/main.py
  - backend/app/services/__init__.py
  - backend/app/services/rag.py
  - backend/app/tests/__init__.py
  - backend/app/tests/conftest.py
  - backend/app/tests/test_chat_endpoint.py
  - backend/app/tests/test_rag.py
  - pytest.ini
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-04-24T00:00:00Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

The core RAG pipeline is well-structured: clean separation between HTTP concerns (`chat.py`) and business logic (`rag.py`), prompt injection mitigation via Pydantic `Literal` constraints, citation fabrication stripping, and proper streaming error handling. The design decisions are sound and well-documented inline.

Three warnings require attention before the test suite can be considered reliable: the HTTP endpoint tests do not suppress the FastAPI lifespan (causing live API calls to OpenRouter and Qdrant during tests), module-level settings initialisation in `rag.py` requires env vars at import time with no test fixture providing them, and the Qdrant distance-metric verification in `main.py` uses an attribute path that only works for simple (unnamed) vector configs. Three info items cover minor code simplification opportunities.

## Warnings

### WR-01: HTTP endpoint tests trigger live lifespan startup

**File:** `backend/app/tests/test_chat_endpoint.py:25-73`

**Issue:** Both `test_endpoint_content_type` and `test_system_role_rejected` call `create_app()` and then make requests via `httpx.AsyncClient(transport=httpx.ASGITransport(...))`. The ASGI transport runs the FastAPI lifespan on the first request. The lifespan calls `_probe_embedding_dim` (a live `openrouter.embeddings.create` call) and `_ensure_collection` (a live Qdrant call). Neither test suppresses the lifespan, so both tests will fail — or silently hit real APIs — in any environment that lacks valid `OPENROUTER_API_KEY` / `QDRANT_HOST` configuration.

`test_system_role_rejected` is especially misleading: the 422 is returned by Pydantic _before_ any service call, so the test assertion passes even on a connection error — but the lifespan exception may mask the failure depending on pytest-asyncio's exception handling.

**Fix:** Suppress the lifespan in both tests, or add a shared fixture that patches it:

```python
from contextlib import asynccontextmanager
from unittest.mock import patch, AsyncMock

@asynccontextmanager
async def _null_lifespan(app):
    yield

async def _minimal_done_stream(*args, **kwargs):
    yield {"type": "done", "answer": "stubbed", "citations": []}

@pytest.mark.asyncio
async def test_endpoint_content_type():
    app = create_app()
    app.router.lifespan_context = _null_lifespan  # suppress startup
    with patch("backend.app.services.rag.stream_answer", side_effect=_minimal_done_stream):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/chat",
                json={"message": "what is the data retention policy?", "history": []},
            )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
```

Alternatively, use FastAPI's `TestClient` with `lifespan="off"` when `httpx` supports it, or move to a fixture that builds the app with a patched lifespan.

---

### WR-02: Module-level `get_settings()` in `rag.py` fails at import without env vars

**File:** `backend/app/services/rag.py:33-48`

**Issue:** Lines 33-48 execute at module import time:

```python
_settings = get_settings()

openrouter = AsyncOpenAI(
    api_key=_settings.openrouter_api_key,
    ...
)
qdrant = AsyncQdrantClient(
    host=_settings.qdrant_host,
    ...
)
```

`get_settings()` calls `Settings()` which raises `pydantic_core.ValidationError` if `OPENROUTER_API_KEY` or `JWT_SECRET` are absent from the environment. The test conftest (`conftest.py`) does not set these env vars, and `pytest.ini` does not configure them. Any `import backend.app.services.rag` (e.g., in `test_rag.py` line 18) will raise `ValidationError` in a clean CI environment with no `.env` file.

The tests in `test_rag.py` successfully patch `rag.openrouter` and `rag.qdrant` after import, but the import itself must succeed first — which requires the env vars.

**Fix — Option A (recommended):** Set dummy env vars in `conftest.py` before any import of `rag`:

```python
# conftest.py — add at top, before other imports
import os
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET", "test-secret")
```

**Fix — Option B:** Lazily initialise clients inside `stream_answer` (or via a dependency-injection pattern) so module import does not require env vars:

```python
# rag.py — replace module-level instantiation with a lazy getter
_openrouter: AsyncOpenAI | None = None
_qdrant: AsyncQdrantClient | None = None

def _get_clients() -> tuple[AsyncOpenAI, AsyncQdrantClient]:
    global _openrouter, _qdrant
    if _openrouter is None:
        s = get_settings()
        _openrouter = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=s.openrouter_api_key, ...)
        _qdrant = AsyncQdrantClient(host=s.qdrant_host, port=s.qdrant_port, api_key=s.qdrant_api_key)
    return _openrouter, _qdrant
```

Option A is simpler and lower risk; Option B removes the module-import side-effect entirely.

---

### WR-03: Qdrant distance verification assumes simple (unnamed) vector config

**File:** `backend/app/main.py:51`

**Issue:** The guardrail that verifies the collection's distance metric uses:

```python
actual_distance = info.config.params.vectors.distance
```

`info.config.params.vectors` is typed as `Union[VectorParams, Dict[str, VectorParams]]`. For a collection created with named vectors (a dict), this returns a `dict` and `.distance` raises `AttributeError`, crashing the application at startup — even though the collection is otherwise valid.

While the current `create_collection` call uses simple `VectorParams` (not named vectors), any externally-created collection or future migration to named vectors would silently crash startup.

**Fix:** Guard for the dict case before accessing `.distance`:

```python
info = await qdrant.get_collection(COLLECTION_NAME)
vectors_config = info.config.params.vectors
if isinstance(vectors_config, dict):
    # Named vectors — check the default/primary vector
    actual_distance = next(iter(vectors_config.values())).distance
else:
    actual_distance = vectors_config.distance

if actual_distance != Distance.COSINE:
    raise RuntimeError(
        f"Collection '{COLLECTION_NAME}' distance metric is {actual_distance}, "
        f"expected COSINE. ..."
    )
```

---

## Info

### IN-01: Redundant condition in `_build_messages` history slice

**File:** `backend/app/services/rag.py:76`

**Issue:** `recent_history = history[-6:] if len(history) > 6 else history` — the conditional is unnecessary. `history[-6:]` already returns the full list when `len(history) <= 6` and the last 6 items when longer. The conditional adds noise without changing behaviour.

**Fix:**
```python
recent_history = history[-6:]
```

---

### IN-02: `stream_answer` accepts unvalidated history dicts

**File:** `backend/app/services/rag.py:114`

**Issue:** `history: list[dict]` has no runtime shape validation. The HTTP boundary validates via `HistoryItem` Pydantic model, but `stream_answer` is a public async generator callable directly with arbitrary dicts. A caller passing `{"role": "system", "content": "..."}` bypasses the injection guard that `chat.py` provides. This is a defence-in-depth gap — not an exploitable path today (the only caller is `chat.py`), but fragile as the service layer grows.

**Fix:** Either document the assumption explicitly (`# Caller must pre-validate role in ['user', 'assistant']`) or add a lightweight assert:

```python
for h in history:
    assert h.get("role") in ("user", "assistant"), f"Invalid history role: {h.get('role')}"
```

---

### IN-03: `print()` used for structured logging in production code

**File:** `backend/app/main.py:29,45,47,57,91` and `backend/app/core/telemetry.py:30,32,36`

**Issue:** Startup and telemetry paths use `print()` instead of the `logging` module. In a production ASGI deployment (uvicorn with log capture), `print()` output bypasses structured log formatting, log level filtering, and any log aggregation pipeline. `rag.py` correctly uses `logging.getLogger(__name__)` — `main.py` and `telemetry.py` should follow the same pattern.

**Fix:** Replace `print(...)` calls with `logger = logging.getLogger(__name__)` and use `logger.info(...)` / `logger.warning(...)` / `logger.error(...)`.

---

_Reviewed: 2026-04-24T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

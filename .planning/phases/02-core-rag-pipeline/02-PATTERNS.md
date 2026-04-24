# Phase 02: Core RAG Pipeline - Pattern Map

**Mapped:** 2026-04-24
**Files analyzed:** 8 new/modified files
**Analogs found:** 7 / 8

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/api/chat.py` | router | streaming (SSE) | `backend/app/main.py` (health route + app factory) | role-partial — same FastAPI app, no existing router |
| `backend/app/services/rag.py` | service | streaming + request-response | `backend/ingestion/ingest.py` (embed + Qdrant calls) | role-match — same clients, same async patterns |
| `backend/app/main.py` (MODIFY) | config | request-response | `backend/app/main.py` itself | exact — self-modification, add `include_router` |
| `backend/app/tests/__init__.py` | package marker | — | `backend/ingestion/tests/__init__.py` | exact — empty package marker |
| `backend/app/tests/conftest.py` | test fixture | — | `backend/ingestion/tests/test_ingestion_evals.py` (fixtures section) | role-match — same fixture style with AsyncMock |
| `backend/app/tests/test_rag.py` | test | request-response + streaming | `backend/ingestion/tests/test_ingestion_evals.py` | role-match — same pytest-asyncio + mock patterns |
| `backend/app/tests/test_chat_endpoint.py` | test | request-response | `backend/ingestion/tests/test_ingestion_evals.py` | role-match — same async test style |
| `pytest.ini` | config | — | none | no analog — new file |

---

## Pattern Assignments

### `backend/app/api/chat.py` (router, SSE streaming)

**Analog:** `backend/app/main.py` (FastAPI app factory, health route)

**Imports pattern** (`backend/app/main.py` lines 1–16):
```python
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from backend.app.core.config import get_settings
from backend.app.core.telemetry import setup_tracing
```
For `chat.py`, the import block follows the same structure — stdlib → third-party → local:
```python
import json
from collections.abc import AsyncGenerator
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app.services import rag
```

**Route pattern** (`backend/app/main.py` lines 107–113):
```python
@app.get("/health")
async def health() -> dict:
    """
    Liveness probe — returns 200 if the service is running.
    Does NOT check Qdrant connectivity (that is verified at startup).
    """
    return {"status": "ok"}
```
The chat router follows the same decorator + async def + docstring convention. Use `APIRouter` rather than `app` directly:
```python
router = APIRouter()

@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    # current_user: User = Depends(get_current_user),  # Phase 3 adds this
) -> StreamingResponse:
    ...
```

**StreamingResponse / SSE generator pattern** (no existing analog — from RESEARCH.md Pattern 1):
```python
async def _generate(request: ChatRequest) -> AsyncGenerator[str, None]:
    async for event in rag.stream_answer(
        message=request.message,
        history=[h.model_dump() for h in (request.history or [])],
    ):
        yield f"data: {json.dumps(event)}\n\n"

return StreamingResponse(_generate(request), media_type="text/event-stream")
```

**Pydantic model pattern** (`backend/ingestion/ingest.py` lines 33–44 — Pydantic BaseModel with field_validator):
```python
class PolicyPassage(BaseModel):
    id: str | int
    title: str
    context: str

    @field_validator("context")
    @classmethod
    def context_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("context is empty")
        return v
```
For `chat.py`, use `Field` constraints and `Literal` for role validation instead of field_validator:
```python
class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=8000)

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[HistoryItem] = Field(default_factory=list)
```

---

### `backend/app/services/rag.py` (service, streaming + async I/O)

**Analog:** `backend/ingestion/ingest.py`

**Imports pattern** (`backend/ingestion/ingest.py` lines 1–20):
```python
import asyncio
import hashlib
import json
import uuid
from pathlib import Path

from openai import AsyncOpenAI
from pydantic import BaseModel, field_validator
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, UpdateStatus, VectorParams

from backend.app.core.config import get_settings
from backend.ingestion.chunker import Chunk, _count_tokens, chunk_passage
```
For `rag.py`, trim to only what is needed:
```python
import json
import logging
import re
from collections.abc import AsyncGenerator

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from backend.app.core.config import get_settings
```

**Module-level client initialization pattern** (`backend/ingestion/ingest.py` lines 48–63):
```python
settings = get_settings()

openrouter = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.openrouter_api_key,
    default_headers={
        "HTTP-Referer": "https://github.com/privacy-policy-compliance-assistant",
        "X-Title": "Privacy Policy Compliance Assistant",
    },
)

qdrant = AsyncQdrantClient(
    host=settings.qdrant_host,
    port=settings.qdrant_port,
    api_key=settings.qdrant_api_key,
)
```
Copy this pattern verbatim into `rag.py` (module-level singletons, consistent with `ingest.py`). The `HTTP-Referer` and `X-Title` headers match the format established in `main.py` lifespan (`backend/app/main.py` lines 71–78):
```python
openrouter = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.openrouter_api_key,
    default_headers={
        "HTTP-Referer": "https://privacy-policy-assistant",
        "X-OpenRouter-Title": "Privacy Policy Assistant",
    },
)
```
Use the `main.py` header names (`X-OpenRouter-Title`) since that is the most recent version.

**Embedding call pattern** (`backend/ingestion/ingest.py` lines 70–73 and lines 150–153):
```python
resp = await openrouter.embeddings.create(model=EMBED_MODEL, input="probe")
return len(resp.data[0].embedding)
```
```python
resp = await openrouter.embeddings.create(model=EMBED_MODEL, input=texts)
return [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]
```
For `rag.py` single-query embedding:
```python
embed_resp = await openrouter.embeddings.create(
    model=EMBEDDING_MODEL,
    input=message,
)
query_vector = embed_resp.data[0].embedding
```

**Qdrant search pattern** (`backend/ingestion/ingest.py` lines 177–184 — sanity_check):
```python
results = await qdrant.search(
    collection_name=COLLECTION_NAME,
    query_vector=vecs[0],
    limit=1,
    with_payload=True,
)
```
Extend for Phase 2 with `score_threshold`:
```python
results = await qdrant.search(
    collection_name=COLLECTION_NAME,
    query_vector=query_vector,
    limit=top_k,
    score_threshold=score_threshold,
    with_payload=True,
)
```

**Empty-results guard pattern** (`backend/ingestion/ingest.py` lines 183–185):
```python
if not results:
    raise AssertionError("[sanity_check] FAILED: no results returned for first passage query")
```
For `rag.py` the guard yields a done event instead of raising (D-14):
```python
if not results:
    yield {
        "type": "done",
        "answer": "No matching policy found for your question.",
        "citations": [],
    }
    return
```

**Error handling / logging pattern** (`backend/ingestion/ingest.py` lines 154–163):
```python
except Exception as exc:
    err_str = str(exc).lower()
    is_rate_limit = "429" in err_str or "rate limit" in err_str or "rate_limit" in err_str
    if is_rate_limit and attempt < retries - 1:
        wait = 2 ** attempt
        print(f"[rate_limit] 429 on attempt {attempt + 1}/{retries} — sleeping {wait}s")
        await asyncio.sleep(wait)
        continue
    raise RuntimeError(f"embed_batch failed after {retries} retries: {exc}") from exc
```
For `rag.py` streaming error handler (inside generator — cannot raise after headers sent):
```python
try:
    stream = await openrouter.chat.completions.create(...)
    async for chunk in stream:
        ...
except Exception as exc:
    logger.error("LLM stream error: %s", exc)
    yield {"type": "error", "message": "LLM service temporarily unavailable"}
    return
```
Use `logger.error(...)` (not `print`) — `rag.py` is a library module, not a script. Use `logging.getLogger(__name__)` at the top of the file.

**Constants block pattern** (`backend/ingestion/ingest.py` lines 22–29):
```python
COLLECTION_NAME = "policies"
BATCH_SIZE = 50
MAX_TOKENS_WARN = 400
CHECKPOINT_PATH = Path("ingestion_checkpoint.json")
DATASET_PATH = Path("dataset/json/train/policy_qa_train.json")
EMBED_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2"
BATCH_SLEEP_SECONDS = 3
```
For `rag.py`:
```python
COLLECTION_NAME = "policies"
EMBEDDING_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2"
CHAT_MODEL = "google/gemma-4-26b-a4b"
ABSTAIN_INSTRUCTION = (
    "If the provided passages do not contain the answer, respond: "
    "'The provided policies do not contain sufficient information to answer this question.' "
    "Do not infer, guess, or use outside knowledge."
)
```

---

### `backend/app/main.py` (MODIFY — add `include_router`)

**Analog:** `backend/app/main.py` itself — lines 95–101 (`create_app`):
```python
def create_app() -> FastAPI:
    return FastAPI(
        title="Privacy Policy Compliance Assistant",
        description="RAG-based chatbot for privacy policy Q&A with inline citations.",
        version="0.1.0",
        lifespan=lifespan,
    )
```
Change to:
```python
from backend.app.api.chat import router as chat_router

def create_app() -> FastAPI:
    app = FastAPI(
        title="Privacy Policy Compliance Assistant",
        description="RAG-based chatbot for privacy policy Q&A with inline citations.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(chat_router, prefix="/api")
    return app
```
The only change is: assign to `app` variable, add `app.include_router(...)`, return `app`. All other lines in `main.py` are untouched.

---

### `backend/app/tests/__init__.py` (NEW — package marker)

**Analog:** `backend/ingestion/tests/__init__.py`

Read that file to confirm it is empty (zero bytes). The new `backend/app/tests/__init__.py` follows the same pattern — empty file, no content.

---

### `backend/app/tests/conftest.py` (NEW — shared pytest fixtures)

**Analog:** `backend/ingestion/tests/test_ingestion_evals.py` — fixtures section (lines 36–60):

```python
@pytest.fixture(scope="module")
def event_loop():
    """Override pytest-asyncio event loop to module scope for connection reuse."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="module")
async def qdrant_client():
    settings = get_settings()
    client = AsyncQdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        api_key=settings.qdrant_api_key,
    )
    yield client
    await client.close()


@pytest.fixture(scope="module")
def corpus_passages() -> list[dict]:
    """Load corpus once per module — avoids re-reading 17K records per test."""
    return json.loads(DATASET_PATH.read_text())
```

For `conftest.py`, fixtures are unit-test scoped (function scope) and use `MagicMock` / `AsyncMock` rather than real clients. Use `AsyncMock` pattern shown in the rate-limit test (`test_ingestion_evals.py` lines 243–258):
```python
from unittest.mock import AsyncMock, MagicMock, patch
```
The `conftest.py` fixtures are function-scoped (not module-scoped) because each test should receive a fresh mock. Do NOT use `scope="module"` for mock fixtures — side effects from one test (e.g., `return_value` overrides) bleed into the next.

**Import pattern** for conftest (mirrors ingestion test imports, lines 14–26):
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
```

---

### `backend/app/tests/test_rag.py` (NEW — unit tests for rag.py)

**Analog:** `backend/ingestion/tests/test_ingestion_evals.py`

**File header / docstring pattern** (lines 1–12):
```python
"""
backend/ingestion/tests/test_ingestion_evals.py
Post-ingestion eval suite. Run after python -m backend.ingestion.ingest completes.

Fast tests (no API calls): test_distance_metric_is_cosine, test_index_completeness, ...
API-dependent tests:       test_embedding_dim_matches_collection, test_rank1_sanity_check
...

Run fast tests: pytest backend/ingestion/tests/test_ingestion_evals.py -v -k "..."
Run all:        pytest backend/ingestion/tests/test_ingestion_evals.py -v --timeout=120
"""
```
Copy the same structure: docstring with fast-test vs API-dependent categorization and quick `pytest` run commands.

**Async test decorator pattern** (lines 64–65):
```python
@pytest.mark.asyncio
async def test_distance_metric_is_cosine(qdrant_client: AsyncQdrantClient) -> None:
```
With `asyncio_mode = "auto"` in `pytest.ini`, the `@pytest.mark.asyncio` decorator is not required but is harmless. The existing ingestion tests use it explicitly — keep the same convention for clarity.

**Mock patch pattern** (`test_ingestion_evals.py` lines 255–259):
```python
with patch("backend.ingestion.ingest.openrouter") as mock_openrouter:
    mock_openrouter.embeddings.create = mock_create
    with patch("backend.ingestion.ingest.asyncio.sleep", new_callable=AsyncMock):
        result = await embed_batch(["test text"], retries=5)
```
For `test_rag.py`, patch the module-level globals in `rag.py`:
```python
with patch("backend.app.services.rag.openrouter", mock_openrouter):
    with patch("backend.app.services.rag.qdrant", mock_qdrant):
        events = [e async for e in rag.stream_answer("question", [])]
```

**Async generator consumption pattern** (no existing analog — needed for `stream_answer` tests):
```python
events = [e async for e in rag.stream_answer("question", [])]
```
This is the standard Python async list comprehension; no special import needed.

**Assert structure pattern** (`test_ingestion_evals.py` lines 131–136):
```python
assert results, "No results returned for first passage query — collection may be empty"
score = results[0].score
assert score > 0.99, (
    f"Rank-1 sanity check FAILED: score={score:.4f} (expected > 0.99). ..."
)
```
Copy the convention of inline descriptive assertion messages. All assertions in `test_rag.py` should include a readable failure message.

**Pure function test pattern** (`test_ingestion_evals.py` lines 266–292 — `test_token_count_guard_warns`):
```python
def test_token_count_guard_warns(corpus_passages: list[dict]) -> None:
    """..."""
    long_passages = [...]
    if not long_passages:
        pytest.skip("...")
    over_limit = [p for p in long_passages if _count_tokens(p) > 400]
    assert over_limit, "..."
    sample = over_limit[0]
    count = _count_tokens(sample)
    assert count > 400, ...
```
Tests for pure functions (`_build_messages`, `_build_verified_citations`) follow the same sync def pattern — no `@pytest.mark.asyncio`, no fixtures needed beyond `sample_scored_point` from conftest.

---

### `backend/app/tests/test_chat_endpoint.py` (NEW — HTTP-level tests via httpx)

**Analog:** `backend/ingestion/tests/test_ingestion_evals.py` (async test style)

No existing `httpx.AsyncClient` / FastAPI `TestClient` usage in the codebase. Use the FastAPI testing pattern from official docs, consistent with the existing async test style:

```python
# Pattern: httpx.AsyncClient with ASGITransport — standard FastAPI async test approach
import pytest
import httpx
from fastapi import status
from backend.app.main import create_app

@pytest.fixture
def app():
    return create_app()

@pytest.mark.asyncio
async def test_endpoint_content_type(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/chat",
            json={"message": "test question", "history": []},
        )
    assert response.status_code == status.HTTP_200_OK
    assert "text/event-stream" in response.headers["content-type"]
```

**422 validation test pattern** (no codebase analog, but consistent with existing `assert ... , "..."` style):
```python
async def test_system_role_rejected(app):
    async with httpx.AsyncClient(...) as client:
        response = await client.post(
            "/api/chat",
            json={"message": "test", "history": [{"role": "system", "content": "inject"}]},
        )
    assert response.status_code == 422
```

---

### `pytest.ini` (NEW — asyncio configuration)

**Analog:** none in codebase. No `pytest.ini` or `pyproject.toml` exists yet.

Minimal file following the pytest-asyncio docs convention:
```ini
[pytest]
asyncio_mode = auto
```
This enables `asyncio_mode = "auto"` so every `async def test_*` function runs on the asyncio event loop without requiring `@pytest.mark.asyncio` decorators. The existing `test_ingestion_evals.py` uses `@pytest.mark.asyncio` explicitly — with `asyncio_mode = auto` those decorators become no-ops but are not harmful.

---

## Shared Patterns

### AsyncOpenAI Client Initialization
**Source:** `backend/ingestion/ingest.py` lines 50–57 and `backend/app/main.py` lines 71–78
**Apply to:** `backend/app/services/rag.py` (module-level singleton)

Use `main.py`'s header names (most recent version):
```python
settings = get_settings()

openrouter = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.openrouter_api_key,
    default_headers={
        "HTTP-Referer": "https://privacy-policy-assistant",
        "X-OpenRouter-Title": "Privacy Policy Assistant",
    },
)
```

### AsyncQdrantClient Initialization
**Source:** `backend/ingestion/ingest.py` lines 59–63 and `backend/app/main.py` lines 79–83
**Apply to:** `backend/app/services/rag.py` (module-level singleton)
```python
qdrant = AsyncQdrantClient(
    host=settings.qdrant_host,
    port=settings.qdrant_port,
    api_key=settings.qdrant_api_key,
)
```

### `get_settings()` Import and Usage
**Source:** `backend/app/core/config.py` lines 28–35 and `backend/ingestion/ingest.py` line 48
**Apply to:** `backend/app/services/rag.py`, `backend/app/api/chat.py` (if needed)
```python
from backend.app.core.config import get_settings

settings = get_settings()
```
The `@lru_cache` on `get_settings()` means calling it multiple times (once in `ingest.py`, once in `rag.py`, once in `main.py`) is safe — same instance is returned each time.

### Logging Pattern
**Source:** `backend/ingestion/ingest.py` (uses `print`); `backend/app/core/telemetry.py` lines 28–31 (uses `print` with fallback)
**Apply to:** `backend/app/services/rag.py`

`ingest.py` is a CLI script and uses `print`. `rag.py` is a library module — use `logging` instead:
```python
import logging
logger = logging.getLogger(__name__)
# Usage:
logger.warning("[warn] fabricated citation [%d] stripped from response (only %d chunks retrieved)", ref_id, n)
logger.error("LLM stream error: %s", exc)
```
This is the Python standard convention for library modules. The `%`-style format arguments are preferred over f-strings for `logging` calls (deferred evaluation).

### Pydantic BaseModel Pattern
**Source:** `backend/ingestion/ingest.py` lines 33–44
**Apply to:** `backend/app/api/chat.py` (ChatRequest, HistoryItem, Citation models)

All models use `class Foo(BaseModel):` with type annotations. Field constraints use `Field(...)`. No `model_config` needed for chat models (they are pure HTTP boundary models, not settings).

### Module Docstring Pattern
**Source:** Every existing `.py` file — `backend/app/main.py` lines 1–5, `backend/ingestion/ingest.py` lines 1–8
**Apply to:** All new files
```python
"""
backend/app/services/rag.py
[One-line description].
[Optional: longer description if non-obvious.]
"""
```
Every file starts with a triple-quoted docstring stating the module path and purpose. This is established convention in the codebase.

### Async Test Mock Pattern
**Source:** `backend/ingestion/tests/test_ingestion_evals.py` lines 230–261
**Apply to:** `backend/app/tests/conftest.py`, `backend/app/tests/test_rag.py`
```python
from unittest.mock import AsyncMock, MagicMock, patch

# For replacing module-level globals:
with patch("backend.app.services.rag.openrouter", mock_openrouter):
    ...

# For AsyncMock return values:
mock_client.some_async_method = AsyncMock(return_value=expected_value)
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `pytest.ini` | config | — | No `pytest.ini` or `pyproject.toml` exists in the repo yet; pattern comes from pytest-asyncio docs |

---

## Metadata

**Analog search scope:** `backend/` (all `.py` files — 11 total)
**Files scanned:** 7 source files read in full
**Pattern extraction date:** 2026-04-24

**Key observations:**
- The codebase has one established service pattern (`ingest.py`) that uses module-level `AsyncOpenAI` + `AsyncQdrantClient` singletons initialized from `get_settings()`. `rag.py` must follow the same pattern.
- `main.py` is the canonical reference for `AsyncOpenAI` header names (`X-OpenRouter-Title` vs `X-Title` in `ingest.py`) — use `main.py`'s version as the most recent.
- No existing `APIRouter` usage exists — `chat.py` introduces the first router. The `app.include_router()` call in `create_app()` is the integration point.
- Tests in `backend/ingestion/tests/` use `@pytest.mark.asyncio` explicitly. With `asyncio_mode = auto` in `pytest.ini`, this becomes optional but should be kept for consistency with the existing test style.
- `conftest.py` is a new file for the project (no existing one) — fixtures must be self-contained.

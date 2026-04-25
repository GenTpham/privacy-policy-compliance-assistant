# Phase 02: Core RAG Pipeline — Research

**Researched:** 2026-04-24
**Domain:** FastAPI SSE streaming + Qdrant async search + OpenAI streaming + citation verification
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `POST /chat` with JSON body `{"message": str, "history": [...]}`. Returns `StreamingResponse` with `Content-Type: text/event-stream`.
- **D-02:** Two event types using an explicit `type` field:
  - Token events: `data: {"type": "delta", "content": "token"}\n\n`
  - Final event: `data: {"type": "done", "answer": "full answer", "citations": [...]}\n\n`
- **D-03:** Token-by-token streaming — emit each token as it arrives, no sentence buffering.
- **D-04:** Retrieved chunks injected into the system message as a numbered list `[1]`–`[5]`. User message contains only the question.
- **D-05:** Hard abstain instruction — exact wording: "If the provided passages do not contain the answer, respond: 'The provided policies do not contain sufficient information to answer this question.' Do not infer, guess, or use outside knowledge."
- **D-06:** Chunk IDs are sequential 1-based integers assigned at retrieval time. Citations map position N → `{qdrant_id, title, text}`.
- **D-07:** Strip fabricated IDs, keep answer. If LLM references `[N]` where N > len(retrieved chunks), remove from `citations` list in `done` event and log a warning.
- **D-08:** Verification runs after streaming on accumulated answer text. `done` event is emitted only after full text is accumulated and citations are verified.
- **D-09:** Client-owned, stateless server. Client sends `history` in every request.
- **D-10:** Server takes the last 6 messages (last 3 turns) from `history` before appending new user message.
- **D-11:** `history` field is optional — `history: []` or omitted for the first turn.
- **D-12:** Score threshold: 0.55 (RAG-02).
- **D-13:** Top-k: 5, `limit=5` and `score_threshold=0.55`.
- **D-14:** When zero chunks exceed threshold, return `{"type": "done", "answer": "No matching policy found for your question.", "citations": []}` without calling LLM.
- **D-15:** New code: `backend/app/api/chat.py` (router) and `backend/app/services/rag.py` (RAG logic).
- **D-16:** Separate service from router — no HTTP concerns in `rag.py`.

### Claude's Discretion

- Exact Pydantic request/response model field names and validation rules.
- Temperature and `max_tokens` for Gemma (executor sets sensible defaults: temperature ≈ 0, max_tokens ≈ 1024).
- Error handling for OpenRouter failures (timeouts, 5xx).
- Regex or parser for extracting `[N]` citation references from answer text.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RAG-01 | User question is embedded via `nvidia/llama-nemotron-embed-vl-1b-v2` on OpenRouter and used to query Qdrant | AsyncOpenAI `embeddings.create()` pattern; `rag.py` service owns embed step |
| RAG-02 | System retrieves top-5 chunks (score ≥ 0.55); below-threshold chunks discarded | `AsyncQdrantClient.search()` with `limit=5, score_threshold=0.55, with_payload=True` |
| RAG-03 | Retrieved chunks passed to `google/gemma-4-26b-a4b` with grounded-response system prompt | `AsyncOpenAI.chat.completions.create()` with numbered-chunk system message |
| RAG-04 | System prompt instructs model to cite only from provided chunks by numeric ID; "cite or abstain" | D-05 hard abstain wording + numbered `[1]`–`[5]` chunk injection in system role |
| RAG-05 | LLM response streamed via SSE; first token within 3 seconds | `stream=True` + FastAPI `StreamingResponse` with `async for chunk` loop |
| RAG-06 | Conversation history (last 3 turns) included in LLM prompt | D-10: slice last 6 messages from client-sent `history` before appending user message |
| RAG-07 | When no chunk exceeds score threshold, return "no matching policy found" without calling LLM | Early return in `rag.py` before calling chat completions |
| CITE-01 | Every answer includes at least one verbatim excerpt from retrieved chunk with source doc title | Qdrant `payload.text` + `payload.title` surfaced in `citations` array of `done` event |
| CITE-02 | Each citation linked to chunk ID in response: `{id, title, text}` | `citations` list in `done` event built from retrieved `ScoredPoint.payload` + positional ID |
| CITE-03 | Citation IDs referenced in answer text verified programmatically to exist in retrieved set | Post-stream regex extraction of `[N]` references; strip IDs where N > len(retrieved) |

</phase_requirements>

---

## Summary

Phase 2 implements the entire RAG query path: a FastAPI POST endpoint that embeds the user's question, retrieves relevant chunks from Qdrant, streams Gemma 4 26B tokens as SSE, then emits a final `done` event with the full answer and verified citations. All decisions about the SSE format, prompt structure, citation stripping, and stateless history are already locked in CONTEXT.md — this research focuses on the exact Python patterns needed to implement each step correctly.

The technical implementation has four distinct sub-problems, each with well-established patterns: (1) FastAPI `StreamingResponse` with `text/event-stream` using an async generator that yields JSON-encoded SSE lines, (2) `AsyncQdrantClient.search()` (or `query_points()`) with `score_threshold` and `with_payload=True`, (3) `AsyncOpenAI.chat.completions.create(stream=True)` with `async for chunk` iteration accessing `chunk.choices[0].delta.content`, and (4) a simple regex `re.findall(r'\[(\d+)\]', answer_text)` for citation extraction. All four patterns are confirmed from official sources.

The integration point with Phase 1 is clean: `backend/app/main.py` uses `create_app()` factory + `lifespan` context manager with `app.include_router(chat_router, prefix="/api")` added to `create_app()`. The Phase 3 auth dependency slot is anticipated via a commented `Depends(get_current_user)` parameter on the chat route — no restructuring needed later.

**Primary recommendation:** Use `StreamingResponse` with a raw async generator that yields `f"data: {json.dumps(event)}\n\n"` strings directly. Do not use `EventSourceResponse` or `sse-starlette` — FastAPI 0.136.0 now includes native `EventSourceResponse` via `fastapi.sse`, but the raw `StreamingResponse` pattern is simpler, requires no additional imports, and the locked D-02 format maps directly to manually formatted SSE lines.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HTTP request handling, SSE response | API layer (`chat.py` router) | — | FastAPI route owns HTTP protocol; no business logic here |
| Query embedding | Service layer (`rag.py`) | External (OpenRouter) | Embedding is a RAG concern, not an HTTP concern |
| Qdrant vector retrieval | Service layer (`rag.py`) | Data (Qdrant container) | Retrieval is RAG business logic |
| Prompt construction | Service layer (`rag.py`) | — | System/user message assembly is pure Python |
| LLM token streaming | Service layer (`rag.py`) | External (OpenRouter) | Service yields tokens; router wraps in StreamingResponse |
| Citation extraction + verification | Service layer (`rag.py`) | — | Regex + list check; runs after streaming on accumulated text |
| Conversation history slicing | Service layer (`rag.py`) | — | D-10 logic: last 6 messages from client-sent array |
| Pydantic request/response models | API layer (`chat.py`) | — | Validation is HTTP boundary concern |
| Config access | Core layer (`config.py`) | — | All clients initialized from `get_settings()` singleton |

---

## Standard Stack

### Core (Phase 2 — no new packages required)

All libraries needed for Phase 2 are already present from Phase 1. No new `pip install` needed.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastapi` | 0.136.0 | `StreamingResponse`, `APIRouter`, request body validation | Already installed; `response_class=EventSourceResponse` also available via `fastapi.sse` in this version |
| `openai` (AsyncOpenAI) | 2.32.0 | `chat.completions.create(stream=True)`, `embeddings.create()` | Already installed; covers both LLM + embedding via OpenRouter base_url override |
| `qdrant-client` (AsyncQdrantClient) | 1.17.1 | `search()` with `score_threshold`, `with_payload=True` | Already installed; async-safe |
| `pydantic` | bundled with fastapi | `ChatRequest`, `Citation`, `HistoryItem` models | Field validation, JSON serialization |

**Version verification:** All versions confirmed in STACK.md and installed in Phase 1. No new packages. [VERIFIED: existing project requirements]

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `re` (stdlib) | stdlib | Citation ID extraction regex `re.findall(r'\[(\d+)\]', text)` | In `rag.py` post-streaming citation verification |
| `json` (stdlib) | stdlib | SSE event serialization: `json.dumps({"type": "delta", "content": token})` | In the async generator yielding SSE lines |
| `logging` (stdlib) | stdlib | `[warn] fabricated citation [N] stripped` log entries | Warning on citation strip in `rag.py` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw `StreamingResponse` + manual SSE format | `fastapi.sse.EventSourceResponse` + `ServerSentEvent` | FastAPI 0.136.0 includes native SSE support via `fastapi.sse` — cleaner API but adds one import; raw `StreamingResponse` is simpler and sufficient for the locked D-02 format |
| `client.chat.completions.create(stream=True)` + `async for` | `client.chat.completions.stream()` context manager | New context manager uses event objects (`event.type == 'content.delta'`); older `stream=True` + `chunk.choices[0].delta.content` is equally supported and more widely documented |
| `re.findall(r'\[(\d+)\]', text)` | `re.finditer` or manual parser | `findall` returns list of string match groups — convert to `int` and deduplicate; simpler than iterating match objects for this use case |

---

## Architecture Patterns

### System Architecture Diagram

```
POST /api/chat
    │  {message, history: [...]}
    ▼
chat.py router
    │  validate ChatRequest (Pydantic)
    │  call rag_service.stream_answer(message, history)
    ▼
rag.py service
    ├── embed(message) ──────────────────────────────► OpenRouter (Nemotron)
    │       ◄──────────────── query_vector [float...]
    │
    ├── qdrant.search(limit=5, score_threshold=0.55) ► Qdrant "policies" collection
    │       ◄──────────────── ScoredPoint[] (id, score, payload{text, title, source_doc})
    │
    │   [if 0 chunks] ──► yield {"type":"done","answer":"No matching...","citations":[]}
    │   [if ≥1 chunk] ──► build system prompt (numbered chunks) + user message + history
    │
    ├── openrouter.chat.completions.create(stream=True) ► OpenRouter (Gemma 4 26B)
    │       ◄── stream of chunks
    │
    │   async for chunk in stream:
    │       token = chunk.choices[0].delta.content
    │       if token: yield {"type":"delta","content":token}
    │               accumulate → full_answer
    │
    └── verify_citations(full_answer, retrieved_chunks)
            extract [N] refs via regex
            strip N > len(retrieved) → log warning
            ──► yield {"type":"done","answer":full_answer,"citations":[{id,title,text},...]}

chat.py router
    │  wrap async generator in StreamingResponse(media_type="text/event-stream")
    │  each yield → "data: {json}\n\n"
    ▼
Client (SSE stream)
```

### Recommended Project Structure (Phase 2 additions)

```
backend/app/
├── main.py                   # MODIFY: add app.include_router(chat_router, prefix="/api")
├── core/
│   ├── config.py             # NO CHANGE — get_settings() already has all needed fields
│   └── telemetry.py          # NO CHANGE — already instruments openai SDK
├── api/
│   └── chat.py               # NEW: APIRouter with POST /chat endpoint
└── services/
    └── rag.py                # NEW: embed → retrieve → stream → verify citations
```

### Pattern 1: FastAPI StreamingResponse for SSE

**What:** Wrap an async generator in `StreamingResponse` with `media_type="text/event-stream"`. Each `yield` from the generator becomes one SSE frame.

**When to use:** Any FastAPI endpoint that needs to push token-by-token LLM output to the client.

```python
# Source: FastAPI official docs — fastapi.tiangolo.com/tutorial/server-sent-events/
# + CONTEXT.md D-01, D-02 (locked SSE format)
import json
from collections.abc import AsyncGenerator
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()

async def _event(data: dict) -> str:
    """Format one SSE frame per the locked D-02 format."""
    return f"data: {json.dumps(data)}\n\n"


@router.post("/chat")
async def chat_endpoint(request: ChatRequest) -> StreamingResponse:
    async def generate() -> AsyncGenerator[str, None]:
        async for event in rag_service.stream_answer(
            message=request.message,
            history=request.history or [],
        ):
            yield await _event(event)

    return StreamingResponse(generate(), media_type="text/event-stream")
```

**Note:** `EventSourceResponse` from `fastapi.sse` is also available in FastAPI 0.136.0 and handles keep-alive pings automatically. Either pattern works; raw `StreamingResponse` is chosen here because the D-02 format is already locked and the additional `ServerSentEvent` wrapper is not needed. [VERIFIED: fastapi.tiangolo.com/tutorial/server-sent-events/]

### Pattern 2: Qdrant Async Search with Score Threshold

**What:** `AsyncQdrantClient.search()` (legacy) or `.query_points()` (current) — both accept `score_threshold` and `with_payload`.

**When to use:** RAG retrieval step — query by vector, filter by score, return payload for citation building.

```python
# Source: python-client.qdrant.tech/qdrant_client.async_qdrant_client
# Confirmed: score_threshold param on search() and query_points()
from qdrant_client import AsyncQdrantClient

async def retrieve(
    qdrant: AsyncQdrantClient,
    query_vector: list[float],
    collection: str = "policies",
    limit: int = 5,
    score_threshold: float = 0.55,
) -> list:  # list[ScoredPoint]
    return await qdrant.search(
        collection_name=collection,
        query_vector=query_vector,
        limit=limit,
        score_threshold=score_threshold,
        with_payload=True,
    )
    # Each result: result.id (str), result.score (float), result.payload (dict)
    # payload keys from Phase 1 ingestion: "text", "title", "source_doc", "passage_id"
```

**Note:** `query_points()` is the newer recommended method and accepts the same parameters. Either works with qdrant-client 1.17.1. `search()` is used in the existing codebase (see `ingest.py` sanity_check) — keep consistent. [VERIFIED: python-client.qdrant.tech]

### Pattern 3: AsyncOpenAI Streaming Chat Completions

**What:** `client.chat.completions.create(stream=True)` returns an async stream. Iterate with `async for chunk` and access `chunk.choices[0].delta.content`.

**When to use:** LLM generation step — send numbered-chunk system prompt + user question + history.

```python
# Source: github.com/openai/openai-python/blob/main/helpers.md
# Confirmed: both stream=True pattern and .stream() context manager supported in openai 2.32.0
from openai import AsyncOpenAI

async def stream_completion(
    openrouter: AsyncOpenAI,
    messages: list[dict],
    model: str = "google/gemma-4-26b-a4b",
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> AsyncGenerator[str, None]:
    """Yield text tokens one by one from streaming chat completions."""
    stream = await openrouter.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

**Alternative — context manager pattern (also valid):**
```python
async with openrouter.chat.completions.stream(
    model=model,
    messages=messages,
    max_tokens=max_tokens,
) as stream:
    async for event in stream:
        if event.type == "content.delta":
            yield event.content
```

Both patterns are supported in openai SDK 2.32.0. Use `stream=True` + `async for chunk` for consistency with the existing codebase style. [VERIFIED: github.com/openai/openai-python/blob/main/helpers.md]

### Pattern 4: Citation Extraction + Verification (CITE-03 / D-07 / D-08)

**What:** After streaming, scan accumulated answer for `[N]` references. Strip any N that exceeds the number of retrieved chunks.

**When to use:** Always — in `rag.py` after the streaming loop completes, before emitting the `done` event.

```python
# Source: Python stdlib re module — no external library needed
import re
import logging

logger = logging.getLogger(__name__)

def build_verified_citations(
    answer: str,
    retrieved_chunks: list,  # list[ScoredPoint] from Qdrant, positional 1-based
) -> list[dict]:
    """
    Extract [N] references from answer, verify against retrieved set, build citations.
    Fabricated IDs (N > len(retrieved_chunks)) are stripped with a warning log.
    """
    n = len(retrieved_chunks)
    # Extract all [N] references — deduplicated, preserving order of first occurrence
    raw_ids = list(dict.fromkeys(
        int(m) for m in re.findall(r'\[(\d+)\]', answer)
    ))

    verified = []
    for ref_id in raw_ids:
        if 1 <= ref_id <= n:
            chunk = retrieved_chunks[ref_id - 1]  # 1-based → 0-based index
            verified.append({
                "id": ref_id,
                "qdrant_id": str(chunk.id),
                "title": chunk.payload.get("title", ""),
                "text": chunk.payload.get("text", ""),
            })
        else:
            logger.warning(
                "[warn] fabricated citation [%d] stripped from response (only %d chunks retrieved)",
                ref_id, n,
            )

    return verified
```

### Pattern 5: Adding the Chat Router to the Existing App

**What:** Add `app.include_router(chat_router, prefix="/api")` to `create_app()` in `main.py`.

**When to use:** The one-time router registration — matches D-15/D-16 and Phase 3 anticipation.

```python
# Modification to backend/app/main.py — create_app() function only
# Source: FastAPI official docs — routing
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

**Phase 3 anticipation pattern for the chat route:**
```python
# backend/app/api/chat.py — route signature
# Commented Depends slot lets Phase 3 add auth without restructuring
@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    # current_user: User = Depends(get_current_user),  # Phase 3 adds this
) -> StreamingResponse:
    ...
```

### Pattern 6: Pydantic Models for Chat Request/Response

**What:** Pydantic models for the HTTP boundary — request body validation and citation response shape.

```python
# backend/app/api/chat.py — Pydantic models
from pydantic import BaseModel, Field

class HistoryItem(BaseModel):
    role: str  # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[HistoryItem] = Field(default_factory=list)

class Citation(BaseModel):
    id: int           # 1-based position in retrieved set
    qdrant_id: str    # Qdrant point UUID
    title: str        # source document title (from payload.title)
    text: str         # verbatim chunk text (from payload.text)

# Note: no ChatResponse model needed — the SSE stream is untyped bytes.
# The done event shape {type, answer, citations} is enforced by rag.py logic,
# not by a FastAPI response model. This is intentional — SSE endpoints
# cannot use response_model with StreamingResponse.
```

### Pattern 7: System Prompt Assembly (D-04 / D-05 / RAG-04)

**What:** Build the numbered-chunk system message. History is sliced to last 6 messages (D-10). Abstain instruction is exact wording from D-05.

```python
# backend/app/services/rag.py — prompt assembly
ABSTAIN_INSTRUCTION = (
    "If the provided passages do not contain the answer, respond: "
    "'The provided policies do not contain sufficient information to answer this question.' "
    "Do not infer, guess, or use outside knowledge."
)

def build_messages(
    user_question: str,
    retrieved_chunks: list,  # list[ScoredPoint]
    history: list[dict],     # [{"role": ..., "content": ...}]
) -> list[dict]:
    # Build numbered context block
    context_lines = []
    for i, chunk in enumerate(retrieved_chunks, start=1):
        context_lines.append(
            f"[{i}] source: {chunk.payload.get('title', 'Unknown')}\n"
            f"{chunk.payload.get('text', '')}"
        )
    context_block = "\n\n".join(context_lines)

    system_content = (
        "You are a privacy policy compliance assistant.\n"
        "Answer questions using ONLY the policy passages provided below.\n"
        "Cite each passage you use by its numeric ID: [1], [2], etc.\n"
        "Do not cite any source not present in the numbered passages.\n\n"
        f"{ABSTAIN_INSTRUCTION}\n\n"
        f"Context passages:\n{context_block}"
    )

    # History: take last 6 messages (3 turns) per D-10
    recent_history = history[-6:] if len(history) > 6 else history
    messages = [{"role": "system", "content": system_content}]
    messages.extend([{"role": h["role"], "content": h["content"]} for h in recent_history])
    messages.append({"role": "user", "content": user_question})
    return messages
```

### Anti-Patterns to Avoid

- **Buffering tokens before yielding:** Collecting all tokens and emitting one big response defeats SSE and violates RAG-05 (first token within 3s). Yield each token immediately.
- **Storing session state server-side:** D-09 mandates stateless server. Never store conversation history in a dict or database keyed by session ID in Phase 2.
- **Fabricated `citations` in the `done` event:** Never include a `Citation` entry where the `id` was not present in the retrieved chunk set. D-07 mandates stripping + logging.
- **Calling the LLM when zero chunks meet the threshold:** D-14 mandates early return with the "no matching policy found" `done` event. Skipping this allows the LLM to hallucinate answers with no corpus support.
- **Synchronous Qdrant client:** `QdrantClient` (sync) blocks the asyncio event loop. Always `AsyncQdrantClient`.
- **Hardcoding Qdrant clients or OpenAI clients inside route functions:** Initialize once (module-level or via dependency injection), not per-request. Client initialization has overhead.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE frame formatting | Custom SSE encoder with field escaping, retry headers, event IDs | `f"data: {json.dumps(event)}\n\n"` (raw) or `fastapi.sse.EventSourceResponse` | SSE spec is simple for this use case; JSON-only events with no retry/ID needed |
| LLM streaming | Manual HTTP chunked streaming | `AsyncOpenAI.chat.completions.create(stream=True)` with `async for` | SDK handles HTTP/2 framing, connection pooling, stream teardown |
| Citation ID regex | Manual string scanner with index tracking | `re.findall(r'\[(\d+)\]', text)` | One line; handles edge cases (multiple on same line, adjacent brackets) |
| Async vector search | Manual httpx calls to Qdrant REST API | `AsyncQdrantClient.search()` | Client handles serialization, auth, retries, gRPC vs REST |
| Pydantic validation of request body | Manual `json.loads` + isinstance checks | `class ChatRequest(BaseModel)` | Field validation, min_length, error messages are free |

**Key insight:** This entire pipeline is ~100 lines of straightforward Python. Every component has a well-matched library call. The only "custom" code is prompt assembly, citation building, and the generator wiring — all pure business logic with no infrastructure complexity.

---

## Common Pitfalls

### Pitfall 1: `choices[0].delta.content` is `None` on First and Last Chunks

**What goes wrong:** The first streamed chunk from OpenRouter often has `delta.content = None` (metadata chunk with role). The last chunk has `delta.content = None` with `finish_reason = "stop"`. If you yield `None` as a token, the client receives `data: {"type": "delta", "content": null}\n\n` — a confusing empty event.

**Why it happens:** OpenAI/OpenRouter streaming protocol always emits a role-setting chunk before content chunks and a stop chunk after.

**How to avoid:** Guard with `if chunk.choices and chunk.choices[0].delta.content:` before yielding. Strictly check truthiness — empty string `""` is also falsy and safe to skip.

**Warning signs:** Client receives `{"type": "delta", "content": null}` events.

### Pitfall 2: `StreamingResponse` Generator Exception Handling

**What goes wrong:** If `openrouter.chat.completions.create()` raises (timeout, 5xx from OpenRouter) inside the async generator, FastAPI has already sent `200 OK` with `text/event-stream` headers. The response status cannot be changed mid-stream. The error silently closes the stream — the client sees the connection drop with no `done` event.

**Why it happens:** HTTP status is committed when the first byte is sent. Generator exceptions after that cannot change it.

**How to avoid:** Wrap the LLM call section in `try/except` inside the generator. On exception: yield a `{"type": "error", "message": "LLM service temporarily unavailable"}` event before returning. This lets the frontend handle gracefully.

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

**Warning signs:** Frontend SSE EventSource closes without receiving a `done` event; no 5xx response code visible to the client.

### Pitfall 3: Client-Sent History Not Validated for Role Values

**What goes wrong:** Client sends `history` with arbitrary role strings (e.g., `"system"` injected by a malicious client). If passed directly to OpenRouter, a second `system` role message overrides the prompt guardrails, defeating D-04/D-05 citation enforcement and the abstain instruction.

**Why it happens:** Server is stateless — it trusts the client-sent history completely.

**How to avoid:** In `ChatRequest`, restrict `HistoryItem.role` to `Literal["user", "assistant"]` — Pydantic rejects any other value with a 422 response. Never allow `"system"` role in client-sent history.

```python
from typing import Literal
class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=8000)
```

**Warning signs:** System prompt appears in retrieved history; LLM cites policy names not in the retrieved chunks.

### Pitfall 4: Qdrant `search()` Returns Empty List (Not an Error) When Score Threshold Filters All Results

**What goes wrong:** When no chunks meet `score_threshold=0.55`, `qdrant.search()` returns `[]` — not an exception, not None. If the service naively checks `if results:` to gate the LLM call, this works correctly. But if the calling code expects a non-empty list and indexes into it without checking, an `IndexError` propagates into the generator, triggering Pitfall 2.

**Why it happens:** Qdrant score threshold is a silent filter, not a "no results found" error condition.

**How to avoid:** Explicit check per D-14: `if not results: yield no_results_event; return`. Always before accessing `results[0]`.

**Warning signs:** `IndexError: list index out of range` in generator; stream closes without `done` event.

### Pitfall 5: Token Accumulation Buffer Not Initialized (Empty Answer on `done` Event)

**What goes wrong:** The `full_answer` accumulation buffer used to build the `done` event is reset or not initialized before the streaming loop. The `done` event fires with `answer = ""`.

**Why it happens:** The streaming generator is a Python `async def` with both `yield` (for delta events) and a post-loop section (for done event). If `full_answer` is modified in a closure or class method without careful scoping, it can be empty.

**How to avoid:** Declare `full_answer = ""` at the top of the generator function body, before the streaming loop. Use `full_answer += token` inside the loop. This is not a closure issue in a flat `async def` function.

**Warning signs:** `done` event has empty `answer` field; `citations` is `[]` even though the LLM produced output.

---

## Code Examples

### Complete `rag.py` Service — Verified Patterns

```python
# backend/app/services/rag.py
# Source: patterns verified from official docs — see Sources section
import json
import logging
import re
from collections.abc import AsyncGenerator

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "policies"
EMBEDDING_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2"
CHAT_MODEL = "google/gemma-4-26b-a4b"
ABSTAIN_INSTRUCTION = (
    "If the provided passages do not contain the answer, respond: "
    "'The provided policies do not contain sufficient information to answer this question.' "
    "Do not infer, guess, or use outside knowledge."
)


async def stream_answer(
    message: str,
    history: list[dict],
    openrouter: AsyncOpenAI,
    qdrant: AsyncQdrantClient,
    top_k: int = 5,
    score_threshold: float = 0.55,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> AsyncGenerator[dict, None]:
    """
    Core RAG pipeline as an async generator.
    Yields: {"type": "delta", "content": token}
    Then:   {"type": "done", "answer": full_text, "citations": [...]}
    """
    # Step 1: Embed query
    embed_resp = await openrouter.embeddings.create(
        model=EMBEDDING_MODEL,
        input=message,
    )
    query_vector = embed_resp.data[0].embedding

    # Step 2: Retrieve (score_threshold filters low-relevance chunks)
    results = await qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k,
        score_threshold=score_threshold,
        with_payload=True,
    )

    # Step 3: Early return if no chunks meet threshold (RAG-07, D-14)
    if not results:
        yield {
            "type": "done",
            "answer": "No matching policy found for your question.",
            "citations": [],
        }
        return

    # Step 4: Build messages (D-04, D-05, D-10)
    messages = _build_messages(message, results, history)

    # Step 5: Stream LLM (RAG-05, D-03)
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
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                full_answer += token
                yield {"type": "delta", "content": token}
    except Exception as exc:
        logger.error("LLM stream error: %s", exc)
        yield {"type": "error", "message": "LLM service temporarily unavailable"}
        return

    # Step 6: Verify citations, emit done event (CITE-03, D-07, D-08)
    citations = _build_verified_citations(full_answer, results)
    yield {"type": "done", "answer": full_answer, "citations": citations}


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
        "Answer using ONLY the policy passages below. Cite by numeric ID [1], [2], etc.\n"
        f"{ABSTAIN_INSTRUCTION}\n\n"
        "Context passages:\n" + "\n\n".join(context_lines)
    )
    recent_history = history[-6:]
    messages = [{"role": "system", "content": system_content}]
    messages.extend(recent_history)
    messages.append({"role": "user", "content": user_question})
    return messages


def _build_verified_citations(answer: str, retrieved_chunks: list) -> list[dict]:
    n = len(retrieved_chunks)
    raw_ids = list(dict.fromkeys(int(m) for m in re.findall(r'\[(\d+)\]', answer)))
    citations = []
    for ref_id in raw_ids:
        if 1 <= ref_id <= n:
            chunk = retrieved_chunks[ref_id - 1]
            citations.append({
                "id": ref_id,
                "qdrant_id": str(chunk.id),
                "title": chunk.payload.get("title", ""),
                "text": chunk.payload.get("text", ""),
            })
        else:
            logger.warning(
                "[warn] fabricated citation [%d] stripped from response (only %d chunks retrieved)",
                ref_id, n,
            )
    return citations
```

### Client Initialization Pattern for `rag.py`

The project uses module-level clients or FastAPI `Depends()` for client injection. The existing `main.py` pattern initializes clients in `lifespan` — Phase 2 should use `get_settings()` to construct clients in `rag.py` or accept them as parameters (for testability).

```python
# Option A: Accept clients as parameters (preferred for testability)
async def stream_answer(message, history, openrouter: AsyncOpenAI, qdrant: AsyncQdrantClient, ...):
    ...

# Option B: Construct at module level (simpler, matches existing ingest.py pattern)
_settings = get_settings()
_openrouter = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=_settings.openrouter_api_key,
    default_headers={
        "HTTP-Referer": "https://privacy-policy-assistant",
        "X-OpenRouter-Title": "Privacy Policy Assistant",
    },
)
_qdrant = AsyncQdrantClient(
    host=_settings.qdrant_host,
    port=_settings.qdrant_port,
    api_key=_settings.qdrant_api_key,
)
```

Option A (parameter injection) is preferred because it allows tests to pass mock clients without patching module-level globals.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `stream=True` + `async for chunk in stream` accessing `chunk.choices[0].delta.content` | `.chat.completions.stream()` context manager with event objects | openai SDK 1.x+ | Both patterns work in 2.32.0; new pattern is more semantic but not required |
| `sse-starlette` third-party package for SSE | `fastapi.sse.EventSourceResponse` (built-in) | FastAPI 0.130+ | Native SSE in FastAPI; no third-party dependency needed |
| `QdrantClient.search()` (sync) | `AsyncQdrantClient.search()` (async) | qdrant-client 1.x | Sync client blocks event loop; always use async in FastAPI |

**Deprecated/outdated:**
- `sse-starlette`: Third-party SSE library was the only option before FastAPI added native `fastapi.sse`. Still works but unnecessary new dependency.
- `python-jose`: JWT library, irrelevant for Phase 2 but flagged in PITFALLS.md — do not introduce.
- `passlib`: Password library, irrelevant for Phase 2.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `chunk.choices[0].delta.content` is `None` on first/last streaming chunk from OpenRouter | Pitfall 1, Pattern 3 | If OpenRouter emits empty string instead of None, the guard `if chunk.choices[0].delta.content:` still works (empty string is falsy) — risk is LOW |
| A2 | FastAPI 0.136.0 includes `fastapi.sse.EventSourceResponse` natively | Standard Stack, Alternatives Considered | If this module import fails, use raw `StreamingResponse` pattern (already the recommended approach) — risk is LOW |
| A3 | `qdrant.search()` returns `[]` (not raises) when `score_threshold` filters all results | Pattern 2, Pitfall 4 | [ASSUMED] based on Qdrant documentation wording "less similar results will not be returned" — if it raises instead, the `try/except` around retrieval would catch it and the empty-results guard would need adjustment |

**If this table had HIGH-risk items:** They would need user confirmation before execution. None of the above assumptions affect the locked decisions from CONTEXT.md.

---

## Open Questions

1. **Client injection strategy: module-level globals vs. FastAPI Depends**
   - What we know: `ingest.py` uses module-level globals; `main.py` uses lifespan-local variables not exposed to routers
   - What's unclear: The planner must choose between (a) module-level singletons in `rag.py`, (b) FastAPI `app.state` set in lifespan, or (c) `Depends()` factories
   - Recommendation: Use module-level singletons in `rag.py` initialized from `get_settings()` — consistent with existing `ingest.py` pattern and simpler than `app.state`. For testing, mock via `unittest.mock.patch`.

2. **`stream_answer` generator wiring — where do clients come from in the route?**
   - What we know: D-16 separates router from RAG service; clients must reach `rag.py`
   - What's unclear: Does `chat.py` call `rag.stream_answer(message, history)` (module-level clients in rag.py) or `rag.stream_answer(message, history, openrouter=..., qdrant=...)` (injected)
   - Recommendation: Module-level clients in `rag.py` (simpler); router just calls `rag.stream_answer(message, history)`.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| FastAPI | HTTP endpoint | ✓ | 0.136.0 (installed Phase 1) | — |
| openai SDK | LLM + embedding | ✓ | 2.32.0 (installed Phase 1) | — |
| qdrant-client | Vector search | ✓ | 1.17.1 (installed Phase 1) | — |
| Qdrant container | Data retrieval | Assumed ✓ | Phase 1 deployed | Cannot run without populated collection |
| OpenRouter API key | LLM + embedding calls | Assumed ✓ | From .env | Phase 2 will fail at runtime if key missing or out of credits |

**Missing dependencies with no fallback:** None — all Phase 2 dependencies were installed and verified in Phase 1.

**Note:** Phase 2 will fail at runtime if Qdrant collection `policies` is not populated (ingestion not run). The `lifespan` in `main.py` already verifies the collection exists and has COSINE distance — but does not verify it has points. This is acceptable: the retrieval step returns `[]` if the collection is empty, triggering the D-14 "no matching policy" fallback.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (installed Phase 1) |
| Config file | None (inferred from pytest.ini or pyproject.toml — none yet, Wave 0 creates) |
| Quick run command | `pytest backend/app/tests/test_rag.py -x -v` |
| Full suite command | `pytest backend/ -v --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RAG-01 | embed() calls OpenRouter with correct model ID | unit (mock) | `pytest backend/app/tests/test_rag.py::test_embed_calls_correct_model -x` | ❌ Wave 0 |
| RAG-02 | search() uses limit=5, score_threshold=0.55 | unit (mock) | `pytest backend/app/tests/test_rag.py::test_retrieve_params -x` | ❌ Wave 0 |
| RAG-03 | chat.completions.create() called with system message containing numbered chunks | unit (mock) | `pytest backend/app/tests/test_rag.py::test_prompt_contains_numbered_chunks -x` | ❌ Wave 0 |
| RAG-04 | System prompt contains hard abstain instruction verbatim | unit (pure) | `pytest backend/app/tests/test_rag.py::test_system_prompt_abstain_wording -x` | ❌ Wave 0 |
| RAG-05 | SSE delta events arrive before done event | unit (mock) | `pytest backend/app/tests/test_rag.py::test_delta_before_done -x` | ❌ Wave 0 |
| RAG-06 | Last 6 messages from history sent to LLM, not more | unit (pure) | `pytest backend/app/tests/test_rag.py::test_history_sliced_to_6 -x` | ❌ Wave 0 |
| RAG-07 | Empty retrieval → done event with no-match message, no LLM call | unit (mock) | `pytest backend/app/tests/test_rag.py::test_no_results_early_return -x` | ❌ Wave 0 |
| CITE-01 | citations list contains title and text fields with non-empty values | unit (pure) | `pytest backend/app/tests/test_rag.py::test_citations_have_title_and_text -x` | ❌ Wave 0 |
| CITE-02 | done event structure: {type, answer, citations: [{id, qdrant_id, title, text}]} | unit (pure) | `pytest backend/app/tests/test_rag.py::test_done_event_shape -x` | ❌ Wave 0 |
| CITE-03 | Citation IDs > len(retrieved) are stripped from done event | unit (pure) | `pytest backend/app/tests/test_rag.py::test_fabricated_citation_stripped -x` | ❌ Wave 0 |
| D-05 | chat endpoint returns 422 if history item has role="system" | unit (httpx) | `pytest backend/app/tests/test_chat_endpoint.py::test_system_role_rejected -x` | ❌ Wave 0 |
| RAG-05 | HTTP endpoint returns 200 text/event-stream content-type | smoke (httpx) | `pytest backend/app/tests/test_chat_endpoint.py::test_endpoint_content_type -x` | ❌ Wave 0 |

### Fixtures Needed (Wave 0)

```python
# backend/app/tests/conftest.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

@pytest.fixture
def mock_openrouter():
    """Mocked AsyncOpenAI client — controls embed and chat responses."""
    client = MagicMock(spec=AsyncOpenAI)
    # Embedding: returns a single vector
    embed_resp = MagicMock()
    embed_resp.data = [MagicMock(embedding=[0.1] * 128)]
    client.embeddings.create = AsyncMock(return_value=embed_resp)
    # Chat completion stream: yields two content chunks then stops
    client.chat.completions.create = AsyncMock()
    return client

@pytest.fixture
def mock_qdrant():
    """Mocked AsyncQdrantClient — returns controlled ScoredPoint results."""
    client = MagicMock(spec=AsyncQdrantClient)
    client.search = AsyncMock(return_value=[])  # default: empty results
    return client

@pytest.fixture
def sample_scored_point():
    """One fake ScoredPoint with all required payload fields."""
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

### Key Assertions for Each Requirement

**RAG-07 (no LLM call when empty retrieval):**
```python
async def test_no_results_early_return(mock_openrouter, mock_qdrant):
    mock_qdrant.search.return_value = []  # no chunks above threshold
    events = [e async for e in stream_answer("any question", [], mock_openrouter, mock_qdrant)]
    assert events[-1]["type"] == "done"
    assert "No matching policy" in events[-1]["answer"]
    mock_openrouter.chat.completions.create.assert_not_called()
```

**CITE-03 (fabricated ID stripped):**
```python
def test_fabricated_citation_stripped(sample_scored_point):
    # LLM answer references [1] (valid) and [3] (fabricated — only 1 chunk retrieved)
    answer = "Per [1], data is retained 30 days. See also [3]."
    citations = _build_verified_citations(answer, [sample_scored_point])
    ids = [c["id"] for c in citations]
    assert 1 in ids
    assert 3 not in ids
```

**RAG-06 (history sliced to 6):**
```python
def test_history_sliced_to_6(sample_scored_point):
    long_history = [{"role": "user" if i%2==0 else "assistant", "content": f"msg {i}"} for i in range(20)]
    messages = _build_messages("new question", [sample_scored_point], long_history)
    # system message + 6 history + 1 user = 8 total
    assert len(messages) == 8
    assert messages[0]["role"] == "system"
    assert messages[-1]["content"] == "new question"
```

**D-05 (abstain wording in system prompt):**
```python
def test_system_prompt_abstain_wording(sample_scored_point):
    messages = _build_messages("test", [sample_scored_point], [])
    system_msg = messages[0]["content"]
    assert "The provided policies do not contain sufficient information" in system_msg
    assert "Do not infer, guess, or use outside knowledge" in system_msg
```

### Sampling Rate

- **Per task commit:** `pytest backend/app/tests/test_rag.py -x -v` (unit tests only, ~2 seconds)
- **Per wave merge:** `pytest backend/ -v --tb=short` (all backend tests)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/app/tests/__init__.py` — package marker
- [ ] `backend/app/tests/conftest.py` — shared fixtures (mock_openrouter, mock_qdrant, sample_scored_point)
- [ ] `backend/app/tests/test_rag.py` — unit tests for `rag.py` service (RAG-01 through RAG-07, CITE-01 through CITE-03)
- [ ] `backend/app/tests/test_chat_endpoint.py` — HTTP-level tests via `httpx.AsyncClient` (endpoint content-type, 422 on bad input)
- [ ] `pytest.ini` or `pyproject.toml` `[tool.pytest.ini_options]` — `asyncio_mode = "auto"` for pytest-asyncio

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 3 adds auth; Phase 2 endpoint is unauthenticated by design |
| V3 Session Management | no | Stateless server (D-09) — no sessions |
| V4 Access Control | no | Phase 3 |
| V5 Input Validation | yes | Pydantic `ChatRequest` — `min_length=1`, `max_length` on message; `Literal["user","assistant"]` on history role |
| V6 Cryptography | no | No crypto in Phase 2 |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via history | Tampering | `Literal["user","assistant"]` role validation; server never allows `"system"` role in client history |
| Oversized message body (DoS) | Denial of Service | `max_length=4000` on `message` field; FastAPI 413 if body too large |
| Fabricated citations as misinformation | Spoofing | D-07 programmatic citation verification; fabricated IDs stripped before `done` event |
| LLM output as unvalidated code injection | Tampering | Answer is treated as plain text; never eval'd or executed |

---

## Sources

### Primary (HIGH confidence)
- [FastAPI SSE docs — fastapi.tiangolo.com/tutorial/server-sent-events/] — `EventSourceResponse`, `ServerSentEvent`, `StreamingResponse` SSE pattern
- [qdrant-client AsyncQdrantClient API — python-client.qdrant.tech/qdrant_client.async_qdrant_client] — `search()` / `query_points()` signature, `score_threshold`, `with_payload` parameters
- [openai-python helpers.md — github.com/openai/openai-python/blob/main/helpers.md] — streaming patterns, `.stream()` context manager vs `stream=True`
- [CONTEXT.md D-01 through D-16] — all locked decisions; no alternatives researched
- [STACK.md] — confirmed library versions (fastapi 0.136.0, openai 2.32.0, qdrant-client 1.17.1)
- [ARCHITECTURE.md] — query flow, context budget, async-first design
- [PITFALLS.md C4, C5] — citation hallucination rate, abstain enforcement patterns
- [01-AI-SPEC.md §4b.3] — prompt engineering pattern for numbered chunks and abstain instruction
- [backend/app/main.py] — existing integration point; `create_app()`, `lifespan`, client initialization pattern
- [backend/app/core/config.py] — `get_settings()` singleton; confirmed all needed fields present

### Secondary (MEDIUM confidence)
- [OpenAI Python streaming guide — platform.openai.com] — streaming response patterns (403 on fetch; content from search results)
- [FastAPI APIRouter guide — fastapi.tiangolo.com/reference/apirouter/] — `include_router`, prefix parameter

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries installed and confirmed from Phase 1; no new packages needed
- SSE streaming pattern: HIGH — verified from official FastAPI docs (fetched)
- Qdrant search API: HIGH — verified from official qdrant-client docs (fetched)
- OpenAI async streaming: HIGH — verified from official openai-python helpers.md (fetched)
- Citation regex: HIGH — stdlib `re.findall`, standard pattern
- Architecture: HIGH — directly derived from CONTEXT.md locked decisions + existing code

**Research date:** 2026-04-24
**Valid until:** 2026-05-24 (30 days — stable library stack, no fast-moving dependencies)

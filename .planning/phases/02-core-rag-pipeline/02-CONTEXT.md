# Phase 2: Core RAG Pipeline — Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement the `/chat` endpoint: embed user question → retrieve top-5 chunks from Qdrant with score ≥ 0.55 → pass to Gemma 4 26B via OpenRouter with a numbered-chunk system prompt → stream tokens back as SSE → emit a final `done` event carrying `{answer, citations}` with fabricated IDs stripped. Phase complete when a `curl` call returns a streamed, grounded, cited answer.

**Does NOT include:** Authentication (Phase 3), frontend (Phase 4), cross-document conflict detection (Phase 5), or conversation session persistence across logins (v2 requirement).

</domain>

<decisions>
## Implementation Decisions

### SSE Streaming Format
- **D-01:** Use `POST /chat` with JSON body `{"message": str, "history": [...]}`. Returns `StreamingResponse` with `Content-Type: text/event-stream`.
- **D-02:** **Two event types** using an explicit `type` field:
  - Token events: `data: {"type": "delta", "content": "token"}\n\n`
  - Final event: `data: {"type": "done", "answer": "full answer", "citations": [...]}\n\n`
- **D-03:** Token-by-token streaming — emit each token from the LLM as it arrives. Do NOT buffer to sentence boundaries.

### Prompt Architecture
- **D-04:** Retrieved chunks injected into the **system message** as a numbered list:
  ```
  Context passages:
  [1] source: {title}
  {text}

  [2] source: {title}
  {text}
  ...
  ```
  The user message contains only the question. System and user roles remain cleanly separated.
- **D-05:** **Hard abstain instruction** — exact wording:
  > "If the provided passages do not contain the answer, respond: 'The provided policies do not contain sufficient information to answer this question.' Do not infer, guess, or use outside knowledge."
- **D-06:** Chunk IDs in the prompt are **sequential 1-based integers** assigned at retrieval time (`[1]` through `[5]`). The `citations` list maps position `N → {qdrant_id, title, text}`. The answer text may reference `[1]`, `[3]`, etc. — these are verified against the retrieved set (not against Qdrant UUIDs directly).

### Citation Verification (CITE-03)
- **D-07:** **Strip fabricated IDs, keep answer.** If the LLM references `[N]` where N > the number of retrieved chunks, remove that reference from the `citations` list in the `done` event and log a warning. The partial answer is still delivered.
- **D-08:** Verification runs **after streaming, on the accumulated answer text.** Tokens stream to the client as they arrive (meets RAG-05). The `done` event is emitted only after the full text is accumulated and citations are verified/stripped. The `citations` array in the `done` event will never contain fabricated entries.

### Conversation State
- **D-09:** **Client-owned, stateless server.** The client sends `history` in every request body. Server never stores session state.
- **D-10:** History shape: `[{"role": "user"|"assistant", "content": str}]` — direct pass-through to the OpenAI messages array. Server takes the last 6 messages (3 user/assistant pairs = last 3 turns per RAG-06) from the array before appending the new user message.
- **D-11:** History field is optional — `history: []` or omitted for the first turn.

### Retrieval Parameters (locked from requirements)
- **D-12:** Score threshold: 0.55 (RAG-02). Chunks below this score are discarded.
- **D-13:** Top-k: 5 (RAG-02). Pass `limit=5` and `score_threshold=0.55` to Qdrant search.
- **D-14:** When zero chunks exceed the threshold, return `{"type": "done", "answer": "No matching policy found for your question.", "citations": []}` without calling the LLM (RAG-07).

### Module Structure
- **D-15:** New code lives under `backend/app/api/` (router) and `backend/app/services/` (RAG logic). The chat router is registered on the existing FastAPI app in `backend/app/main.py`.
- **D-16:** Separate `backend/app/services/rag.py` for retrieval + prompt assembly + streaming, and `backend/app/api/chat.py` for the FastAPI router. This keeps HTTP concerns out of the RAG service.

### Claude's Discretion
- Exact Pydantic request/response models (field names, validation rules) — planner chooses, must match the decisions above.
- Temperature and max_tokens for Gemma — executor sets sensible defaults (temperature ≈ 0, max_tokens ≈ 1024).
- Error handling for OpenRouter failures (timeouts, 5xx) — executor implements appropriate HTTP exceptions.
- Regex or parser used to extract `[N]` citation references from the answer text for CITE-03 verification.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §RAG Pipeline (RAG-01–07)
- `.planning/REQUIREMENTS.md` §Citations (CITE-01–03)

### Prior Phase Infrastructure
- `.planning/phases/01-infrastructure-data-ingestion/01-CONTEXT.md` — D-08 through D-14: collection name (`policies`), COSINE distance, embedding model, `get_settings()` pattern, `AsyncQdrantClient` and `AsyncOpenAI` initialization
- `backend/app/core/config.py` — `get_settings()` singleton with `openrouter_api_key`, `qdrant_host/port/api_key`
- `backend/app/main.py` — existing FastAPI app factory, lifespan pattern, COLLECTION_NAME constant

### Research Findings
- `.planning/research/STACK.md` — confirmed library versions, OpenAI SDK base_url override for OpenRouter
- `.planning/research/PITFALLS.md` — relevant sections for Phase 2: §C5 (citation hallucination 17-33% rate, enforce "cite or abstain"), §C6 (token truncation on embedding)
- `.planning/research/ARCHITECTURE.md` — RAG pipeline design, query flow

### Dataset (for eval)
- `dataset/json/test/policy_qa_test.json` — held-out eval benchmark; question+answers fields provide ground truth for Phase 2 retrieval quality testing

No external ADRs — all decisions captured above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/core/config.py` — `get_settings()` singleton; provides `openrouter_api_key`, `qdrant_host`, `qdrant_port`, `qdrant_api_key`. Phase 2 reads these directly — no new settings fields needed for the RAG pipeline itself.
- `backend/app/main.py` — `create_app()` factory and `lifespan` context manager. The Phase 2 chat router attaches to the existing `app` instance.
- `backend/app/core/telemetry.py` — `setup_tracing()` already instruments `openai` SDK calls via OpenTelemetry. Phase 2 gets free tracing on all embedding and LLM calls with no additional code.

### Established Patterns
- `AsyncOpenAI` with `base_url="https://openrouter.ai/api/v1"` and attribution headers — established in `main.py`. RAG service reuses this exact initialization pattern.
- `AsyncQdrantClient` with `host/port/api_key` from `get_settings()` — established in `main.py`.
- `@lru_cache` + `get_settings()` singleton — use for any module-level resource that should be instantiated once.
- Async-first: all I/O uses `await`; no synchronous blocking in async routes.

### Integration Points
- The `policies` Qdrant collection (created in Phase 1) is the primary data source. Query via `AsyncQdrantClient.search()` with `COLLECTION_NAME = "policies"`.
- `backend/app/main.py` `create_app()` — add `app.include_router(chat_router, prefix="/api")` here.
- Phase 3 (Auth) will add a JWT dependency to the `/chat` route. Design the route to accept a future `Depends(get_current_user)` parameter without restructuring.

</code_context>

<specifics>
## Specific Ideas

- The `done` event emitted at the end of the stream is the authoritative source for the full answer and citations — the frontend should use this for rendering the final state, not the accumulated delta stream.
- Citation stripping in the `done` payload: if `[3]` appears in the answer text but only 2 chunks were retrieved, remove entry 3 from citations and log `[warn] fabricated citation [3] stripped from response`.
- The test split (`dataset/json/test/`) contains ground-truth QA pairs — the Phase 2 eval plan should include a metric measuring what fraction of test questions retrieve the correct passage as top-1 or top-3 result.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-core-rag-pipeline*
*Context gathered: 2026-04-24*

---
phase: 02-core-rag-pipeline
verified: 2026-04-24T10:00:00Z
status: human_needed
score: 9/9 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Send a curl request to POST /api/chat with a real policy question against a live stack"
    expected: "Streamed SSE response with first token arriving within 3 seconds, followed by a done event with non-empty citations"
    why_human: "Requires live Qdrant (with ingested corpus) and live OpenRouter key; cannot verify latency or real retrieval programmatically"
  - test: "Ask a follow-up question in a multi-turn conversation with history=[prior turn]"
    expected: "Answer references the prior turn context, confirming history (last 3 turns) is wired end-to-end through the HTTP layer"
    why_human: "End-to-end conversation coherence requires a live LLM and real corpus — unit tests verify the slice logic but not the round-trip"
---

# Phase 2: Core RAG Pipeline Verification Report

**Phase Goal:** The `/chat` endpoint accepts a question, retrieves relevant chunks from Qdrant, streams a grounded answer via SSE, and returns a response payload with verified inline citations.
**Verified:** 2026-04-24T10:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | stream_answer async generator yields delta events before the done event | VERIFIED | test_delta_before_done PASSES; code yields `{"type":"delta"}` in streaming loop before final `{"type":"done"}` |
| 2 | When qdrant.search returns [], done event fires with 'No matching policy found' and LLM is never called | VERIFIED | test_no_results_early_return PASSES; `if not results: yield done; return` at line 150–156 of rag.py |
| 3 | System message contains the exact D-05 abstain instruction verbatim | VERIFIED | test_system_prompt_abstain_wording PASSES; ABSTAIN_INSTRUCTION constant embedded in system_content at line 73 of rag.py |
| 4 | Fabricated citation IDs (N > len(retrieved)) are stripped with a warning log | VERIFIED | test_fabricated_citation_stripped PASSES; `[warn] fabricated citation [%d] stripped` logger.warning at line 104 of rag.py |
| 5 | History is sliced to last 6 messages before being prepended to the LLM messages array | VERIFIED | test_history_sliced_to_6 PASSES; `history[-6:] if len(history) > 6 else history` at line 76 of rag.py |
| 6 | Embedding call uses model='nvidia/llama-nemotron-embed-vl-1b-v2' | VERIFIED | test_embed_calls_correct_model PASSES; EMBEDDING_MODEL constant at line 20 of rag.py |
| 7 | Qdrant search uses limit=5, score_threshold=0.55, with_payload=True | VERIFIED | test_retrieve_params PASSES; explicit kwargs at lines 143–147 of rag.py |
| 8 | POST /api/chat returns Content-Type: text/event-stream with HTTP 200 | VERIFIED | test_endpoint_content_type PASSES; StreamingResponse(media_type="text/event-stream") at line 79 of chat.py |
| 9 | history with role='system' is rejected with HTTP 422 | VERIFIED | test_system_role_rejected PASSES; `Literal["user", "assistant"]` on HistoryItem.role at line 30 of chat.py |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pytest.ini` | asyncio_mode = auto configuration | VERIFIED | `asyncio_mode = auto` present; asyncio mode=AUTO confirmed in test run |
| `backend/app/tests/__init__.py` | Package marker | VERIFIED | Exists (empty file) |
| `backend/app/tests/conftest.py` | Shared fixtures: mock_openrouter, mock_qdrant, sample_scored_point | VERIFIED | All three function-scoped fixtures present; no scope=module |
| `backend/app/tests/test_rag.py` | 10 test stubs for RAG-01-07 and CITE-01-03 | VERIFIED | 10 tests, all PASS (not skip); 117+ lines |
| `backend/app/tests/test_chat_endpoint.py` | 2 HTTP-level tests | VERIFIED | 2 tests, both PASS |
| `backend/app/services/__init__.py` | Package marker | VERIFIED | Exists (empty file) |
| `backend/app/services/rag.py` | Full RAG pipeline: stream_answer, _build_messages, _build_verified_citations | VERIFIED | All three functions present; 186 lines; substantive implementation |
| `backend/app/api/__init__.py` | Package marker | VERIFIED | Exists (empty file) |
| `backend/app/api/chat.py` | APIRouter with ChatRequest, HistoryItem, Citation, POST /chat | VERIFIED | All exports present; 80 lines; StreamingResponse wired |
| `backend/app/main.py` | FastAPI app factory with chat_router registered under /api | VERIFIED | include_router(chat_router, prefix="/api") at line 103 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/app/services/rag.py` | OpenRouter embeddings API | `openrouter.embeddings.create(model=EMBEDDING_MODEL)` | VERIFIED | EMBEDDING_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2" at line 20; call at line 134 |
| `backend/app/services/rag.py` | Qdrant policies collection | `qdrant.search(collection_name=COLLECTION_NAME, score_threshold=0.55)` | VERIFIED | score_threshold=0.55 at line 145; collection_name=COLLECTION_NAME at line 142 |
| `backend/app/services/rag.py` | OpenRouter chat API | `openrouter.chat.completions.create(model=CHAT_MODEL, stream=True)` | VERIFIED | CHAT_MODEL = "google/gemma-4-26b-a4b" at line 21; stream=True at line 167 |
| `backend/app/api/chat.py` | `backend/app/services/rag.py` | `rag.stream_answer(message=request.message, history=[h.model_dump() for h in ...])` | VERIFIED | `async for event in rag.stream_answer(...)` at lines 73–77 of chat.py |
| `backend/app/main.py` | `backend/app/api/chat.py` | `app.include_router(chat_router, prefix="/api")` | VERIFIED | Import at line 14 + include_router call at line 103 of main.py |
| `backend/app/api/chat.py` | client (SSE stream) | `StreamingResponse(_generate(), media_type="text/event-stream")` | VERIFIED | Line 79 of chat.py; confirmed by test_endpoint_content_type |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `backend/app/services/rag.py` | `query_vector` | `openrouter.embeddings.create(model=EMBEDDING_MODEL, input=message)` | Yes (real API call via AsyncOpenAI; module-level singleton initialized from get_settings()) | WIRED — real API call, not static |
| `backend/app/services/rag.py` | `results` | `qdrant.search(collection_name=COLLECTION_NAME, ...)` | Yes (real Qdrant search; module-level AsyncQdrantClient) | WIRED — real search call, not static |
| `backend/app/api/chat.py` | `event` stream | `rag.stream_answer(message=request.message, history=[h.model_dump() ...])` | Yes — history converted from validated Pydantic models before passing | FLOWING — request data flows to rag.py |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 12 tests pass | `.venv/Scripts/python.exe -m pytest backend/app/tests/ -v` | 12 passed, 0 failed, 0 skipped in 0.91s | PASS |
| HistoryItem rejects role=system | Pydantic ValidationError raised on `HistoryItem(role='system', content='x')` | ValidationError raised correctly | PASS |
| Empty message rejected | Pydantic ValidationError raised on `ChatRequest(message='', history=[])` | ValidationError raised correctly | PASS |
| ABSTAIN_INSTRUCTION contains required text | Python import + assertion | Both substrings confirmed present | PASS |
| Live curl smoke test (requires running services) | `curl -N -X POST http://localhost:8000/api/chat -d '{"message":"test"}'` | Cannot test without live Qdrant + OpenRouter | SKIP |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RAG-01 | 02-01, 02-02, 02-03 | User question is embedded via nvidia/llama-nemotron-embed-vl-1b-v2 | SATISFIED | EMBEDDING_MODEL constant + embeddings.create call in rag.py; test_embed_calls_correct_model PASSES |
| RAG-02 | 02-01, 02-02, 02-03 | Top-5 chunks with score_threshold ≥ 0.55 | SATISFIED | limit=5, score_threshold=0.55 in rag.py:141-147; test_retrieve_params PASSES |
| RAG-03 | 02-01, 02-02, 02-03 | Retrieved chunks passed to gemma-4-26b-a4b with grounded system prompt | SATISFIED | CHAT_MODEL constant + _build_messages numbering "[1] source:"; test_prompt_contains_numbered_chunks PASSES |
| RAG-04 | 02-01, 02-02, 02-03 | System prompt instructs cite-or-abstain | SATISFIED | ABSTAIN_INSTRUCTION constant with exact D-05 wording in system_content; test_system_prompt_abstain_wording PASSES |
| RAG-05 | 02-01, 02-02, 02-03 | LLM response streamed via SSE; first token within 3s | SATISFIED (programmatic) | delta events yielded per-token; StreamingResponse(media_type="text/event-stream"); test_delta_before_done and test_endpoint_content_type PASS. 3-second latency requires live verification (see Human Verification) |
| RAG-06 | 02-01, 02-02, 02-03 | Conversation history (last 3 turns = 6 messages) included in prompt | SATISFIED | history[-6:] slice in rag.py:76; test_history_sliced_to_6 PASSES |
| RAG-07 | 02-01, 02-02, 02-03 | No-match case returns message without calling LLM | SATISFIED | Early return with "No matching policy found" when results=[]; test_no_results_early_return PASSES |
| CITE-01 | 02-01, 02-02, 02-03 | Every answer includes verbatim excerpt with source title | SATISFIED | _build_verified_citations returns {title, text} from payload; test_citations_have_title_and_text PASSES |
| CITE-02 | 02-01, 02-02, 02-03 | Response payload: {answer, citations: [{id, title, text}]} | SATISFIED | done event shape {type, answer, citations}; citation keys {id, qdrant_id, title, text}; test_done_event_shape PASSES |
| CITE-03 | 02-01, 02-02, 02-03 | Citation IDs verified against retrieved set (no fabricated IDs) | SATISFIED | _build_verified_citations strips N > len(retrieved_chunks); test_fabricated_citation_stripped PASSES |

All 10 requirements mapped to Phase 2 are SATISFIED by the implementation. No orphaned requirements found.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | No blockers, stubs, or placeholder anti-patterns found in implementation files |

No TODO/FIXME/placeholder comments found in rag.py, chat.py, or main.py. No empty return stubs. All test stubs from Plan 02-01 have been replaced with real implementations (12 PASS, 0 skip).

### Human Verification Required

#### 1. Live SSE Smoke Test (RAG-05 latency)

**Test:** With Qdrant running and corpus ingested, run:
```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"what is the data retention policy?"}'
```
**Expected:** `data: {"type": "delta", "content": "..."}` lines appear progressively within 3 seconds, followed by `data: {"type": "done", "answer": "...", "citations": [...]}` where citations contain non-empty title and text fields referencing actual policy passages.
**Why human:** Requires live Qdrant with ingested corpus + valid OpenRouter API key. Token latency (≤3 seconds) cannot be verified from static code analysis.

#### 2. Multi-Turn Conversation Coherence (RAG-06 end-to-end)

**Test:** Send two sequential requests where the second includes the first turn in `history`:
```bash
# First request
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"what is the data retention period?", "history":[]}'

# Second request referencing first turn
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"does that apply to employee data too?", "history":[{"role":"user","content":"what is the data retention period?"},{"role":"assistant","content":"<first answer>"}]}'
```
**Expected:** Second answer references the context established by the first turn; coherent follow-up response demonstrating history wiring through the HTTP layer to the LLM.
**Why human:** End-to-end conversation coherence depends on live LLM behavior and real corpus retrieval — the code correctly slices and passes history (verified by test_history_sliced_to_6), but whether the LLM produces a coherent follow-up requires human judgment on a live stack.

### Gaps Summary

No gaps found. All 9 observable truths are verified, all 10 requirements (RAG-01–07, CITE-01–03) are satisfied, all artifacts exist and are substantive, all key links are wired, and data flows through the pipeline correctly.

The `human_needed` status is due to 2 items requiring a live stack (latency verification and multi-turn coherence) — these are observable behaviors that cannot be confirmed from static code analysis alone.

---

_Verified: 2026-04-24T10:00:00Z_
_Verifier: Claude (gsd-verifier)_

# Phase 5: Cross-Document Conflict Detection — Research

**Researched:** 2026-04-28
**Domain:** RAG pipeline extension — conflict routing, prompt engineering, keyword detection
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Keyword Detection (CONFLICT-01)**
- D-01: Case-insensitive substring match using `re.search(pattern, message, re.IGNORECASE)` where pattern is a regex join of the 7 required keywords.
- D-02: Keyword list is exactly: `conflict`, `contradict`, `mâu thuẫn`, `so sánh`, `khác nhau`, `differ`, `both documents`
- D-03: False positives (e.g., "indifferent") are acceptable — running the conflict path on a normal query degrades gracefully.
- D-04: Detection happens in `chat.py` (the router) before calling the service layer.

**Module Architecture**
- D-05: New async generator `stream_conflict_answer(message, history)` added to `backend/app/services/rag.py` alongside `stream_answer()`. No new module.
- D-06: `chat.py` router detects keyword, calls either `rag.stream_answer()` or `rag.stream_conflict_answer()`.

**Retrieval (CONFLICT-02)**
- D-07: `stream_conflict_answer()` uses `limit=10`, same `score_threshold=0.55`.
- D-08: No source-document filtering — retrieval across all documents in `policies` collection.

**Conflict Prompt Design (CONFLICT-03)**
- D-09: Same numbered chunk injection format as standard prompt: `[1] source: {title}\n{text}`
- D-10: Prompt organizes answer document-by-document, citing passages with `[N]` references.
- D-11: Prompt concludes with: `Verdict: <classification> — <one-sentence reason>`
- D-12: Classification taxonomy: `Contradictory`, `Consistent`, `One-Silent`
- D-13: Conflict prompt retains the hard abstain instruction from Phase 2 D-05.

**Response Payload (CONFLICT-04)**
- D-14: `done` event payload shape is unchanged: `{answer, citations: [{id, qdrant_id, title, text}]}`
- D-15: Phase 4 frontend requires no changes.
- D-16: Zero chunks above threshold returns the same "No matching policy found" response as the standard path.

### Claude's Discretion
- Exact system prompt wording for the conflict-detection path (beyond structural decisions above)
- Whether to add "do not cite sources not in the numbered list" reminder to the conflict prompt (recommended: yes)
- Temperature and max_tokens for conflict responses (recommend same defaults: temperature=0.0, max_tokens=1024)
- Test fixture design for `stream_conflict_answer()` — follow `patch.object(rag, 'openrouter', mock)` pattern from Phase 2

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CONFLICT-01 | Detect comparison-intent queries via 7 keywords (case-insensitive regex) | D-01/D-02 locked; `re.search` with `re.IGNORECASE` flag; no library needed |
| CONFLICT-02 | Retrieve top-10 chunks across all source documents for comparison queries | D-07/D-08 locked; same `query_points()` call with `limit=10` |
| CONFLICT-03 | Use dedicated conflict-detection prompt classifying passages as contradictory/consistent/one-silent | D-09–D-13 locked; prompt structure fully specified |
| CONFLICT-04 | Conflict response identifies documents and cites exact passages from each side by numeric ID | D-14 locked; `_build_verified_citations()` fully reusable; payload shape unchanged |
</phase_requirements>

---

## Summary

Phase 5 is a pure backend extension to the existing RAG pipeline. It adds a routing branch in `chat.py` and a second async generator in `rag.py`. There are no new external dependencies, no schema changes, no frontend changes, and no new Docker services.

The implementation is a surgical 3-step change: (1) add a 7-keyword regex detector in `chat.py`, (2) add `stream_conflict_answer()` to `rag.py` that mirrors `stream_answer()` but with `limit=10` and a conflict-focused system prompt, and (3) add tests that verify the detection, retrieval parameter change, prompt structure, verdict format, and payload shape.

The Phase 2 helpers `_build_messages()`, `_build_verified_citations()`, and the existing module-level `openrouter` and `qdrant` singletons are directly reused or adapted. The planner should treat this phase as two focused units of work: a Wave 0 test stub pass, then a Wave 1 implementation pass.

**Primary recommendation:** Add `stream_conflict_answer()` to `rag.py` and the detection branch to `chat.py`; write tests that mirror the Phase 2 test pattern exactly.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Keyword detection / routing | API (chat.py router) | — | D-04 locks detection in the router; service layer stays pure |
| Conflict retrieval (top-10) | Service (rag.py) | Qdrant | Only `limit` changes; same `query_points()` call |
| Conflict prompt assembly | Service (rag.py) | — | Mirrors `_build_messages()`; prompt text differs, injection format identical |
| LLM response streaming | Service (rag.py) | OpenRouter | Same `chat.completions.create(stream=True)` call and delta/done event sequence |
| Citation verification | Service (rag.py) | — | `_build_verified_citations()` is fully reusable as-is |
| SSE plumbing | API (chat.py) | — | `_generate()` inner function wraps either generator identically |

---

## Standard Stack

### Core (all already installed — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `openai` SDK | 2.32.0 | OpenRouter LLM + embed calls | Already in use; OpenRouter is OpenAI-compatible [VERIFIED: CLAUDE.md] |
| `qdrant-client` | 1.17.1 | Async vector search | Already in use; `query_points()` established in `rag.py` [VERIFIED: codebase] |
| `fastapi` | 0.136.0 | Router + SSE response | Already in use; `StreamingResponse` established in `chat.py` [VERIFIED: codebase] |
| `re` (stdlib) | Python 3.11 | Regex keyword detection | No third-party dep; `re.search()` + `re.IGNORECASE` is the locked approach [VERIFIED: D-01] |

### Supporting (test layer — already installed)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` + `pytest-asyncio` | existing | Unit tests for async generators | All tests in this phase follow established pattern |
| `unittest.mock` | stdlib | `patch.object(rag, 'openrouter', mock)` | Established mock pattern from Phase 2 |
| `httpx` | existing | `AsyncClient` for HTTP-level tests | Used in `test_chat_endpoint.py` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `re.search()` for keyword detection | `str.lower() + any(kw in msg)` | Simple substring works but is less readable for 7 keywords; regex join is cleaner |
| In-line conflict prompt string | Separate `_build_conflict_messages()` function | Separate function is more testable; matches Phase 2 pattern of `_build_messages()` |

**Installation:** No new packages required. All dependencies are already present in the project virtualenv.

---

## Architecture Patterns

### System Architecture Diagram

```
POST /api/chat
      │
      ▼
[chat.py: chat_endpoint()]
      │
      ├─ keyword_detect(message) ──► NO ──► rag.stream_answer()  (limit=5, standard prompt)
      │                                            │
      └─ YES ──► rag.stream_conflict_answer()      │
                     │                             │
                     ▼                             ▼
              [embed query]               [embed query]
                     │                             │
                     ▼                             ▼
              [qdrant.query_points         [qdrant.query_points
               limit=10, thresh=0.55]      limit=5, thresh=0.55]
                     │                             │
                     ▼                             ▼
              [_build_conflict_messages()]  [_build_messages()]
                     │                             │
                     ▼                             ▼
              [openrouter stream]          [openrouter stream]
                     │                             │
                     ▼                             ▼
              [_build_verified_citations()] [_build_verified_citations()]
                     │                             │
                     └──────────────┬──────────────┘
                                    ▼
                         SSE: delta* → done
                         (payload shape identical)
```

### Recommended Project Structure

No structural changes. All new code goes into existing files:

```
backend/app/
├── api/
│   └── chat.py           # add: keyword detection helper + routing branch
├── services/
│   └── rag.py            # add: stream_conflict_answer() + _build_conflict_messages()
└── tests/
    ├── conftest.py        # add: sample_scored_points_multi (2+ chunks, 2 titles)
    ├── test_rag.py        # add: 6 new tests for conflict path
    └── test_chat_endpoint.py  # add: 2 new tests (conflict route triggers, standard unaffected)
```

### Pattern 1: Keyword Detection Helper

**What:** A module-level function in `chat.py` that returns `True` when the message contains any conflict keyword.
**When to use:** Called once per request, before the service dispatch decision.

```python
# Source: CONTEXT.md D-01/D-02 + re stdlib docs [ASSUMED wording; structure is locked]
import re

_CONFLICT_PATTERN = re.compile(
    r"conflict|contradict|mâu thuẫn|so sánh|khác nhau|differ|both documents",
    re.IGNORECASE,
)

def is_conflict_query(message: str) -> bool:
    return bool(_CONFLICT_PATTERN.search(message))
```

Placing the compiled pattern at module level avoids recompilation on every request. [ASSUMED: minor optimization; correct per Python re docs]

### Pattern 2: stream_conflict_answer() Structure

**What:** Async generator in `rag.py` that mirrors `stream_answer()` with two differences: `limit=10` and a conflict-specialized system prompt.
**When to use:** Called by `chat.py` when `is_conflict_query()` is `True`.

```python
# Source: codebase rag.py stream_answer() + CONTEXT.md D-05–D-13 [VERIFIED: codebase]
async def stream_conflict_answer(
    message: str,
    history: list[dict],
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> AsyncGenerator[dict, None]:
    # Step 1: embed (identical to stream_answer)
    embed_resp = await openrouter.embeddings.create(
        model=EMBEDDING_MODEL, input=message, encoding_format="float"
    )
    query_vector = embed_resp.data[0].embedding

    # Step 2: retrieve top-10 (D-07: only limit changes)
    response = await qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=10,
        score_threshold=0.55,
        with_payload=True,
    )
    results = response.points

    # Step 3: early return if no results (D-16 — same as RAG-07)
    if not results:
        yield {"type": "done", "answer": "No matching policy found for your question.", "citations": []}
        return

    # Step 4: build conflict messages
    messages = _build_conflict_messages(message, results, history)

    # Step 5–6: stream + verify (identical to stream_answer)
    ...
```

### Pattern 3: _build_conflict_messages() Prompt Structure

**What:** Builds the OpenAI messages array using the conflict-detection system prompt.
**When to use:** Called only from `stream_conflict_answer()`.

The system prompt must include:
1. Role statement: "You are a privacy policy compliance assistant specializing in cross-document comparison."
2. Same numbered chunk injection format as `_build_messages()` (D-09).
3. Instruction to organize answer document-by-document (D-10).
4. Verdict format instruction (D-11): `Verdict: <classification> — <one-sentence reason>`
5. Classification taxonomy with exact definitions (D-12).
6. Hard abstain instruction — verbatim from `ABSTAIN_INSTRUCTION` constant (D-13).
7. "Do not cite any source not listed in the numbered passages." reminder (Claude's Discretion).

```python
# Source: CONTEXT.md D-09–D-13 [VERIFIED: decisions locked in CONTEXT.md]
def _build_conflict_messages(
    user_question: str,
    retrieved_chunks: list,
    history: list[dict],
) -> list[dict]:
    context_lines = [
        f"[{i}] source: {c.payload.get('title', 'Unknown')}\n{c.payload.get('text', '')}"
        for i, c in enumerate(retrieved_chunks, start=1)
    ]
    system_content = (
        "You are a privacy policy compliance assistant specializing in cross-document comparison.\n"
        "Answer using ONLY the policy passages below. Cite each passage you use by its numeric ID: [1], [2], etc.\n"
        "Do not cite any source not listed in the numbered passages.\n\n"
        "Organize your answer document-by-document: describe what each involved document says "
        "about the topic, citing the relevant passages with [N] references.\n\n"
        "Conclude your answer with a verdict on the last line, using exactly this format:\n"
        "Verdict: <classification> — <one-sentence reason>\n\n"
        "Classification must be exactly one of:\n"
        "- Contradictory — the documents make directly conflicting statements on this topic\n"
        "- Consistent — both documents address the topic and are in agreement\n"
        "- One-Silent — one document addresses the topic; the other does not mention it "
        "(absence is not a conflict)\n\n"
        f"{ABSTAIN_INSTRUCTION}\n\n"
        "Context passages:\n" + "\n\n".join(context_lines)
    )
    recent_history = history[-6:] if len(history) > 6 else history
    messages: list[dict] = [{"role": "system", "content": system_content}]
    messages.extend(recent_history)
    messages.append({"role": "user", "content": user_question})
    return messages
```

### Pattern 4: Routing Branch in chat.py

**What:** `chat_endpoint()` detects conflict intent and dispatches to the appropriate generator.
**When to use:** Every request to `POST /api/chat`.

```python
# Source: CONTEXT.md D-04/D-06 + codebase chat.py [VERIFIED: codebase + locked decision]
@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    history = [h.model_dump() for h in request.history]

    async def _generate() -> AsyncGenerator[str, None]:
        if is_conflict_query(request.message):
            generator = rag.stream_conflict_answer(request.message, history)
        else:
            generator = rag.stream_answer(request.message, history)
        async for event in generator:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")
```

### Anti-Patterns to Avoid

- **Detection in the service layer:** `stream_conflict_answer()` must not decide whether it should be called. Detection is the router's responsibility (D-04). This keeps `rag.py` functions pure and independently testable.
- **New module for conflict logic:** D-05 locks all conflict logic in `rag.py`. A new `rag_conflict.py` module would duplicate the client singleton initialization and diverge from the established pattern.
- **Dynamic pattern recompilation:** Calling `re.compile()` inside `is_conflict_query()` on every request is wasteful. Compile once at module level.
- **Widening HistoryItem.role:** Never add `"system"` to the Literal — this is the security control from Phase 2 (established in conftest + test_chat_endpoint.py).
- **Changing the done payload shape:** D-14 locks the shape as `{answer, citations: [{id, qdrant_id, title, text}]}`. Do not add `conflict_classification` or `verdict` as top-level fields. The verdict is in the answer prose.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fabricated citation stripping | Custom per-function verifier | `_build_verified_citations()` (already in `rag.py`) | Same logic applies to 10-chunk results; no changes needed |
| LLM streaming error handling | New try/except wrapper | Copy the `try/except` block from `stream_answer()` verbatim | Pattern is already tested; re-inventing introduces new failure modes |
| Test mock setup | New fixture types | Extend existing `mock_openrouter`/`mock_qdrant` from `conftest.py` | Function-scoped fixtures already handle isolation correctly |
| SSE formatting | New serializer | Reuse `f"data: {json.dumps(event)}\n\n"` from `_generate()` | Identical for both paths; no change needed |

**Key insight:** Every non-trivial piece of infrastructure (client singletons, citation verifier, SSE plumbing, streaming pattern, test mocks) already exists and is tested. Phase 5 is almost entirely an assembly task using existing parts.

---

## Common Pitfalls

### Pitfall 1: Unicode in the Compiled Regex
**What goes wrong:** `re.compile()` with `re.IGNORECASE` handles ASCII case folding but Vietnamese diacritics (`mâu thuẫn`, `so sánh`, `khác nhau`) are not affected by ASCII case folding. If the pattern uses raw bytes rather than a Unicode string, non-ASCII characters may fail to match.
**Why it happens:** Python 3 strings are Unicode by default, so this is not a problem as long as the pattern is a `str` literal (not `bytes`). The risk is introducing encoding errors if the source file is saved without UTF-8 encoding.
**How to avoid:** Ensure `rag.py` or `chat.py` source file is UTF-8 (the default in Python 3). Confirm with a test: `assert is_conflict_query("mâu thuẫn về lưu trữ dữ liệu")`.
**Warning signs:** `re.error` at compile time, or Vietnamese keyword tests failing while English ones pass.

### Pitfall 2: "indifferent" / "different" False Positives
**What goes wrong:** The word "differ" is a substring of "different", "indifferent", "difference". The regex `differ` will match any of these.
**Why it happens:** D-03 explicitly accepts this as a known tradeoff — false positives degrade gracefully (top-10 + conflict prompt still produces a valid answer).
**How to avoid:** No action required per D-03. Document this in a comment in the code.
**Warning signs:** None — this is intentional behavior.

### Pitfall 3: History Slice Off-By-One
**What goes wrong:** `_build_conflict_messages()` uses a different history slice than `_build_messages()`, introducing inconsistency.
**Why it happens:** Copy-paste error during implementation — the conflict function uses a different bound.
**How to avoid:** Use the exact same slicing logic: `history[-6:] if len(history) > 6 else history`. Add a test that verifies the conflict path also produces at most 8 messages (system + 6 history + user) with a long history.
**Warning signs:** Test `test_conflict_history_sliced_to_6` failing.

### Pitfall 4: Returning All Chunks on Abstain
**What goes wrong:** When the LLM abstains on a conflict query (no `[N]` references in the answer), the "return all retrieved chunks as citations" fallback from `stream_answer()` is not automatically present in `stream_conflict_answer()` unless explicitly copied.
**Why it happens:** The fallback block at the end of `stream_answer()` (lines 190–201 of the current `rag.py`) is in the function body, not in a helper. A new function that calls `_build_verified_citations()` without copying this fallback will silently omit source citations on abstain responses.
**How to avoid:** Copy the abstain fallback block into `stream_conflict_answer()`. Consider extracting it into a helper if the duplication feels too heavy.
**Warning signs:** Integration test with a conflict query that produces no `[N]` references returns `citations: []` instead of all 10 retrieved chunks.

### Pitfall 5: delta.content = None on First/Last Chunk
**What goes wrong:** OpenRouter streams a first chunk with `delta.content = None` (role announcement) and a last chunk with `delta.content = None` (stop reason). Writing `full_answer += chunk.choices[0].delta.content` without a None guard raises `TypeError`.
**Why it happens:** The guard `if chunk.choices and chunk.choices[0].delta.content:` already exists in `stream_answer()`. It must be replicated exactly in the streaming loop of `stream_conflict_answer()`.
**How to avoid:** Copy the streaming loop verbatim from `stream_answer()`.
**Warning signs:** `TypeError: can only concatenate str (not "NoneType") to str` in tests or at runtime.

---

## Code Examples

### Existing stream_answer() Streaming Loop (reference for replication)
```python
# Source: backend/app/services/rag.py lines 165-183 [VERIFIED: codebase]
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
```

### Abstain Fallback Block (must be copied into stream_conflict_answer)
```python
# Source: backend/app/services/rag.py lines 190-201 [VERIFIED: codebase]
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
```

### Phase 2 Test Mock Pattern (reuse in Phase 5 tests)
```python
# Source: backend/app/tests/test_rag.py lines 40-50 [VERIFIED: codebase]
with patch.object(rag, "openrouter", mock_openrouter), \
     patch.object(rag, "qdrant", mock_qdrant):
    events = [e async for e in stream_answer("test query", [])]
```

### Multi-Chunk Fixture (needed in conftest.py for conflict tests)
```python
# Source: [ASSUMED — follows existing sample_scored_point pattern from conftest.py]
@pytest.fixture
def sample_scored_points_multi():
    """Two fake ScoredPoints from different source documents — for conflict path tests."""
    def _make(idx, title, text):
        point = MagicMock()
        point.id = f"id-{idx}"
        point.score = 0.80
        point.payload = {"text": text, "title": title, "source_doc": f"doc_{idx}", "chunk_index": 0}
        return point
    return [
        _make(1, "Policy A", "Data is retained for 30 days."),
        _make(2, "Policy B", "Data is retained indefinitely."),
    ]
```

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pytest.ini` (asyncio_mode=auto) |
| Quick run command | `pytest backend/app/tests/test_rag.py backend/app/tests/test_chat_endpoint.py -x -v` |
| Full suite command | `pytest backend/app/tests/ -x -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONFLICT-01 | `is_conflict_query("mâu thuẫn")` returns True | unit | `pytest backend/app/tests/test_chat_endpoint.py::test_conflict_detection_keywords -x` | Wave 0 |
| CONFLICT-01 | Standard query ("retention policy") returns False | unit | `pytest backend/app/tests/test_chat_endpoint.py::test_standard_query_not_detected -x` | Wave 0 |
| CONFLICT-01 | "indifferent" triggers conflict path (false positive accepted) | unit | `pytest backend/app/tests/test_chat_endpoint.py::test_false_positive_graceful -x` | Wave 0 |
| CONFLICT-02 | `stream_conflict_answer()` calls `query_points(limit=10, score_threshold=0.55)` | unit | `pytest backend/app/tests/test_rag.py::test_conflict_retrieve_params -x` | Wave 0 |
| CONFLICT-03 | Conflict system prompt contains verdict format instruction | unit | `pytest backend/app/tests/test_rag.py::test_conflict_prompt_contains_verdict_format -x` | Wave 0 |
| CONFLICT-03 | Conflict system prompt contains all three classification terms | unit | `pytest backend/app/tests/test_rag.py::test_conflict_prompt_contains_classifications -x` | Wave 0 |
| CONFLICT-03 | Conflict prompt retains abstain instruction wording | unit | `pytest backend/app/tests/test_rag.py::test_conflict_prompt_abstain_wording -x` | Wave 0 |
| CONFLICT-04 | `done` event from conflict path has same shape as standard path | unit | `pytest backend/app/tests/test_rag.py::test_conflict_done_event_shape -x` | Wave 0 |
| CONFLICT-04 | Standard path unaffected (still limit=5) after routing branch added | unit | `pytest backend/app/tests/test_rag.py::test_retrieve_params -x` | Existing |
| CONFLICT-01+02 | HTTP POST with conflict keyword calls `stream_conflict_answer`, not `stream_answer` | integration | `pytest backend/app/tests/test_chat_endpoint.py::test_conflict_route_dispatches_conflict_generator -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest backend/app/tests/test_rag.py -x -v`
- **Per wave merge:** `pytest backend/app/tests/ -x -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/app/tests/test_rag.py` — add 6 new test stubs (CONFLICT-02 through CONFLICT-04 unit tests)
- [ ] `backend/app/tests/test_chat_endpoint.py` — add 3 new test stubs (CONFLICT-01 detection + routing)
- [ ] `backend/app/tests/conftest.py` — add `sample_scored_points_multi` fixture

*(Existing test infrastructure (pytest.ini, conftest.py base fixtures, import structure) is already in place — no new setup files needed.)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | JWT auth already in place via `Depends(get_current_user)` — unchanged |
| V3 Session Management | no | Stateless server; no change |
| V4 Access Control | no | Same endpoint, same auth dependency |
| V5 Input Validation | yes | `ChatRequest.message` max_length=4000; `HistoryItem.role: Literal["user","assistant"]` — both unchanged and already enforced |
| V6 Cryptography | no | No cryptographic operations added |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via keyword payload | Tampering | Keywords only gate the routing decision; system prompt is assembled server-side from trusted templates |
| Fabricated citation IDs in conflict answer | Tampering | `_build_verified_citations()` strips IDs > len(retrieved_chunks) — same as standard path |
| History role escalation | Elevation of Privilege | `HistoryItem.role: Literal["user","assistant"]` rejects "system" with HTTP 422 — unchanged from Phase 2 |

**No new attack surface introduced.** The conflict path is a routing branch within the same authenticated endpoint, using the same input validation, the same citation verifier, and the same streaming infrastructure.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `qdrant.search()` | `qdrant.query_points()` | qdrant-client 1.13+ | Already migrated in Phase 2; `stream_conflict_answer()` uses same `.points` accessor |
| Inline regex in function body | Module-level compiled pattern | — | Performance micro-optimization; not required but conventional |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Multi-chunk fixture wording (`sample_scored_points_multi`) | Code Examples | Low — fixture is test scaffolding only; executor adjusts freely |
| A2 | Exact system prompt wording for conflict-detection beyond structural requirements | Code Examples / Patterns | Low — Claude's Discretion area; wording can be adjusted in implementation |

**Note:** All architecture decisions (D-01 through D-16) are locked in CONTEXT.md and treated as VERIFIED for planning purposes.

---

## Open Questions

1. **Temperature for conflict responses**
   - What we know: Claude's Discretion area; standard path uses `temperature=0.0, max_tokens=1024`.
   - What's unclear: Whether a slightly higher temperature (e.g., 0.1) might produce more natural verdict phrasing.
   - Recommendation: Default to `temperature=0.0, max_tokens=1024` matching the standard path. This is the safest choice for a compliance context where determinism is preferred.

2. **Verdict format enforcement**
   - What we know: D-11 specifies the exact format. The model may not always produce it.
   - What's unclear: Whether the planner should add a post-processing check that parses the last line for "Verdict:" and emits a warning log if absent.
   - Recommendation: Log a warning if "Verdict:" is not found in `full_answer` before emitting the `done` event. Do not reject or re-generate the response — the answer is still valid without the verdict line.

---

## Environment Availability

Step 2.6: SKIPPED — Phase 5 is a pure Python code change within existing services. No new external tools, services, CLIs, or runtimes are required beyond what is already installed and running.

---

## Sources

### Primary (HIGH confidence)
- `backend/app/services/rag.py` — existing implementation; all patterns for Phase 5 derived from this file [VERIFIED: codebase]
- `backend/app/api/chat.py` — existing router; routing branch pattern derived from this file [VERIFIED: codebase]
- `backend/app/tests/conftest.py` — existing fixtures; mock patterns confirmed [VERIFIED: codebase]
- `.planning/phases/05-cross-document-conflict-detection/05-CONTEXT.md` — all D-XX decisions [VERIFIED: read]
- `.planning/phases/02-core-rag-pipeline/02-CONTEXT.md` — upstream locked decisions that carry forward [VERIFIED: read]
- `pytest.ini` — `asyncio_mode=auto` confirmed [VERIFIED: codebase]

### Secondary (MEDIUM confidence)
- Python 3.11 `re` stdlib — `re.IGNORECASE` handling of Unicode confirmed correct for str literals [ASSUMED: training knowledge; low risk]

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; all patterns verified in existing codebase
- Architecture: HIGH — all D-XX decisions locked in CONTEXT.md; implementation path is unambiguous
- Pitfalls: HIGH — derived from reading actual implementation code, not general knowledge
- Test plan: HIGH — mirrors exact test pattern from Phase 2 tests

**Research date:** 2026-04-28
**Valid until:** 2026-06-28 (stable codebase, no fast-moving external deps for this phase)

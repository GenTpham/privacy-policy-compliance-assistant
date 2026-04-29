# Phase 5: Cross-Document Conflict Detection — Context

**Gathered:** 2026-04-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Detect comparison-intent queries via keyword matching → retrieve top-10 chunks from across all source documents → run a dedicated conflict-detection prompt → return a classified response that identifies the specific documents involved and cites exact passages from each side. Standard single-document queries are completely unaffected — they continue to use top-5 retrieval and the normal grounded-response prompt.

**Does NOT include:** Frontend changes (Phase 4 UI works as-is with no schema changes), new API endpoints, or ingestion pipeline modifications.

</domain>

<decisions>
## Implementation Decisions

### Keyword Detection (CONFLICT-01)
- **D-01:** Case-insensitive substring match using `re.search(pattern, message, re.IGNORECASE)` where pattern is a regex join of the 7 required keywords.
- **D-02:** Keyword list is exactly as specified in REQUIREMENTS.md CONFLICT-01 — no additions in v1:
  `conflict`, `contradict`, `mâu thuẫn`, `so sánh`, `khác nhau`, `differ`, `both documents`
- **D-03:** False positives (e.g., "indifferent") are acceptable — running the conflict path on a normal query degrades gracefully (top-10 retrieval + conflict prompt still produces a valid answer).
- **D-04:** Detection happens in `chat.py` (the router) before calling the service layer. The router decides which generator to call based on detection result.

### Module Architecture
- **D-05:** New async generator `stream_conflict_answer(message, history)` added to `backend/app/services/rag.py` alongside the existing `stream_answer()`. No new module. Reuses the same module-level `openrouter` and `qdrant` client singletons.
- **D-06:** `chat.py` router detects the keyword, then calls either `rag.stream_answer()` or `rag.stream_conflict_answer()`. HTTP/SSE plumbing is identical for both paths.

### Retrieval (CONFLICT-02)
- **D-07:** `stream_conflict_answer()` uses `limit=10` (not 5) and the same `score_threshold=0.55` as the standard path. The threshold is unchanged — only the result count increases.
- **D-08:** No source-document filtering — retrieval is across all documents in the `policies` collection.

### Conflict Prompt Design (CONFLICT-03)
- **D-09:** Conflict-detection system prompt uses the **same numbered chunk injection format** as the standard prompt (D-04 from Phase 2 CONTEXT) — `[1] source: {title}\n{text}` — so citation mechanics are identical.
- **D-10:** Prompt instructs the model to organize its answer **document-by-document**: describe what each involved document says about the topic, citing relevant passages with `[N]` references.
- **D-11:** Prompt instructs the model to conclude the answer with a **verdict at the end**:
  `Verdict: <classification> — <one-sentence reason>`
  where `<classification>` is exactly one of: `Contradictory`, `Consistent`, or `One-Silent`.
- **D-12:** Classification taxonomy — exact definitions the model is given:
  - `Contradictory` — the documents make directly conflicting statements on this topic
  - `Consistent` — both documents address the topic and are in agreement
  - `One-Silent` — one document addresses the topic; the other does not mention it
- **D-13:** The conflict prompt retains the hard abstain instruction (D-05 from Phase 2 CONTEXT): if the retrieved passages do not contain enough information to compare, the model must say so explicitly rather than inferring.

### Response Payload (CONFLICT-04)
- **D-14:** The `done` event payload shape is **unchanged**: `{answer, citations: [{id, qdrant_id, title, text}]}`. No new fields added. Document identification is conveyed through:
  1. The prose answer (model names each document in its per-document breakdown)
  2. The existing `citations[].title` field (already surfaces the source document name)
- **D-15:** Phase 4 frontend (ChatPage, MessageBubble, CitationCard) requires **no changes** for this phase.
- **D-16:** When zero chunks exceed the score threshold on a conflict query, return the same "No matching policy found" response as the standard path (same RAG-07 behavior).

### Claude's Discretion
- Exact system prompt wording for the conflict-detection path (beyond the structural decisions above)
- Whether to add an explicit "do not cite sources not in the numbered list" reminder to the conflict prompt (recommended: yes, carry forward from Phase 2)
- Temperature and max_tokens for conflict responses (recommend same defaults: temperature=0.0, max_tokens=1024)
- Test fixture design for `stream_conflict_answer()` — follow the same `patch.object(rag, 'openrouter', mock)` pattern established in Phase 2

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §Cross-Document Conflict Detection (CONFLICT-01–04)

### Prior Phase Context (locked decisions)
- `.planning/phases/02-core-rag-pipeline/02-CONTEXT.md` — D-01 through D-16: SSE event format, prompt architecture, citation verification, done payload shape, module split pattern. All apply to this phase.
- `.planning/phases/01-infrastructure-data-ingestion/01-CONTEXT.md` — collection name (`policies`), COSINE distance, chunk metadata fields (`text`, `title`, `source_doc`, `chunk_index`)

### Existing Implementation (read before writing new code)
- `backend/app/services/rag.py` — existing `stream_answer()` and `_build_messages()`. `stream_conflict_answer()` must use the same client singletons and follow the same async generator pattern.
- `backend/app/api/chat.py` — existing chat router. Detection logic and routing branch added here.
- `backend/app/core/config.py` — `get_settings()` singleton (no new settings fields needed for this phase)

No external ADRs — all decisions captured above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `openrouter` and `qdrant` singletons in `rag.py` — `stream_conflict_answer()` reuses these directly; no re-initialization needed
- `_build_messages()` in `rag.py` — can be reused or adapted for the conflict prompt. The chunk injection format is identical; only the system-level instruction text differs
- `_build_verified_citations()` in `rag.py` — fully reusable for conflict responses; citation verification mechanics are unchanged
- `HistoryItem` and `ChatRequest` Pydantic models in `chat.py` — no changes needed; the conflict path accepts the same request shape

### Established Patterns
- Async generator yielding `{"type": "delta"/"done"/"error", ...}` — both paths follow this exact protocol
- `qdrant.query_points(collection_name=COLLECTION_NAME, query=vector, limit=N, score_threshold=0.55, with_payload=True)` — same call, only `limit` changes from 5 to 10
- `patch.object(rag, 'openrouter', mock)` and `patch.object(rag, 'qdrant', mock)` — test mock pattern for the new function

### Integration Points
- `chat.py` `chat_endpoint()` — add keyword detection before calling `rag.stream_answer()`. Branch: if conflict → call `rag.stream_conflict_answer()`, else → call `rag.stream_answer()`
- `_generate()` inner function in `chat_endpoint` — can wrap either generator with identical SSE formatting

</code_context>

<specifics>
## Specific Ideas

- The document-by-document structure works naturally when `source_doc` or `title` metadata varies across the top-10 chunks. The prompt should instruct the model to group its analysis by document title.
- For the "One-Silent" verdict: the prompt should clarify that "one-silent" means the second document simply does not address the topic — it is not a conflict. This prevents the model from treating absence as implicit disagreement.
- The conflict path is a routing branch, not a middleware. Detection and routing in `chat.py` keeps `rag.py` functions pure (no detection logic in the service layer).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 05-cross-document-conflict-detection*
*Context gathered: 2026-04-28*

# Phase 9: UX Enhancements - Research

**Researched:** 2026-05-06
**Domain:** FastAPI endpoint design, Qdrant payload filtering, React state / SSE hook, citation UI
**Confidence:** HIGH

---

## Summary

Phase 9 is a narrow feature addition to an existing, fully-deployed system. The three requirements (source filter dropdown, backend payload filter, score display on citation cards) each touch one layer cleanly:

- **UX-01/02**: A new `GET /api/sources` endpoint returns distinct `title` values from Qdrant; the frontend sidebar wires to this real list and passes the chosen `source_filter` string in the `POST /api/chat` body; the backend applies a Qdrant `must` payload filter.
- **UX-03**: The `score` field already lives on every `ScoredPoint` returned by `qdrant.query_points()` (it is `r.score`). Adding it to citations requires one dict key in `rag.py`, one field in the `Citation` TypeScript interface, and a score badge component addition to `CitationCard.tsx`.

The UI-SPEC is complete and locked — it specifies exact components, colors, copy, accessibility attributes, and file paths. The planner MUST follow 09-UI-SPEC.md as a hard contract, not as suggestions.

**Primary recommendation:** Work backend-first (new endpoint + rag.py changes) before frontend (useSSEChat, CitationCard, AskAssistantScreen), because the backend score field and sources list shape drives both the TypeScript interface and the render logic.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Source list discovery | API / Backend | Database / Storage (Qdrant) | Backend queries Qdrant for distinct titles; frontend only fetches the result |
| Source filter enforcement | API / Backend | — | Qdrant `must` filter runs server-side; client only sends the filter name |
| Score field in citations | API / Backend | — | `r.score` is already on `ScoredPoint`; must be added to the dict before SSE emission |
| Score badge display | Browser / Client | — | Pure render — applies traffic-light color thresholds from existing `ConfidenceBar` logic |
| Source filter sidebar UI | Browser / Client | — | `useState` + fetch on mount; purely cosmetic now, functional after this phase |
| SSE payload (done event) | API / Backend | — | Adding `score` to `done` event citations is a backend schema change |

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UX-01 | User can select a specific policy source from a dropdown in the chat UI ("All sources" is the default) | Frontend: `GET /api/sources` on mount populates sidebar buttons; existing `activeFilter` state wires to real data |
| UX-02 | Backend filters Qdrant retrieval by source when a filter is active — only passages from the selected policy are returned | Qdrant `query_filter=Filter(must=[FieldCondition(key="title", match=MatchValue(value=source_filter))])` in `rag.py` |
| UX-03 | Each citation card displays the retrieval score (cosine similarity) so users can assess match confidence | `r.score` already on `ScoredPoint`; add `"score": round(chunk.score, 4)` to citation dict; render with `score.toFixed(2)` in CitationCard |
</phase_requirements>

---

## Standard Stack

No new dependencies required. All capabilities use libraries already in `requirements.txt` and `package.json`.

### Core (already installed)

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| `qdrant-client` | 1.17.1 | Payload filter (`Filter`, `FieldCondition`, `MatchValue`, `facet()`) | Already installed [VERIFIED: requirements.txt] |
| `fastapi` | 0.136.0 | New `GET /api/sources` router | Already installed [VERIFIED: requirements.txt] |
| React + Vitest | 19 + 4.x | Frontend state, fetch, CitationCard test | Already installed [VERIFIED: package.json] |
| `lucide-react` | 1.11.0 | Icons in CitationCard (already used) | Already installed [VERIFIED: package.json] |

### No New Packages

Phase 9 introduces zero new Python packages and zero new npm packages. The UI-SPEC explicitly states: "No new component library dependencies added in Phase 9." [VERIFIED: 09-UI-SPEC.md]

---

## Architecture Patterns

### System Architecture Diagram

```
Browser
  AskAssistantScreen
    on mount ──────► GET /api/sources ──────► qdrant.facet("title") ──► ["Google...", "OpenAI...", ...]
    activeFilter (state) ◄─────────────────── {"sources": [...]}
    submit(input) ─────► POST /api/chat
                          body: { message, history, source_filter: "Google Privacy Policy" | null }
                            │
                            ▼
                      chat.py router
                        ChatRequest.source_filter ──► rag.stream_answer(source_filter=...)
                                                            │
                                                            ├──► qdrant.query_points(
                                                            │       query_filter=Filter(must=[
                                                            │         FieldCondition("title", MatchValue("Google Privacy Policy"))
                                                            │       ])
                                                            │     )
                                                            │
                                                            └──► done event:
                                                                 citations[].score = round(r.score, 4)
                            │
                            ▼
                      SSE stream ──► useSSEChat ──► Citation.score ──► CitationCard score badge
                                                                    ──► AskAssistantScreen Evidence panel ConfidenceBar
```

### Recommended Project Structure (changes only)

```
backend/
  app/
    api/
      sources.py          # NEW — GET /api/sources
      __init__.py         # register sources router (already empty)
      chat.py             # ADD source_filter to ChatRequest + pass to rag
    services/
      rag.py              # ADD source_filter param + Qdrant must filter + score in citations
  tests/
    test_sources_endpoint.py  # NEW — endpoint + Qdrant integration tests
    test_rag.py               # EXTEND — source_filter propagation, score in done event

frontend/
  src/
    hooks/
      useSSEChat.ts            # ADD score to Citation interface; add source_filter to submit()
    components/
      chat/
        CitationCard.tsx       # ADD score badge in collapsed trigger row; accept score prop
    pages/
      AskAssistantScreen.tsx   # REPLACE mock POLICIES with /api/sources fetch; wire source_filter to submit()
```

### Pattern 1: Qdrant Payload Filter (UX-02)

**What:** Apply a `must` condition on `payload.title` when `source_filter` is non-null.
**When to use:** Every `stream_answer` / `stream_conflict_answer` call when a filter is active.

```python
# Source: [VERIFIED: Qdrant filtering docs + qdrant_client.models confirmed in codebase imports]
from qdrant_client.models import Filter, FieldCondition, MatchValue

response = await qdrant.query_points(
    collection_name=COLLECTION_NAME,
    query=query_vector,
    limit=5,
    score_threshold=_threshold,
    with_payload=True,
    query_filter=Filter(
        must=[
            FieldCondition(
                key="title",
                match=MatchValue(value=source_filter),
            )
        ]
    ) if source_filter else None,
)
```

**Critical detail:** The parameter name on `AsyncQdrantClient.query_points()` is `query_filter` (not `filter`). [VERIFIED: qdrant_client docs — the existing `rag.py` omits it when no filter needed; add it conditionally]

### Pattern 2: GET /api/sources Using facet() (UX-01)

**What:** Fetch distinct `title` values from Qdrant using the facet API. The facet API was introduced in Qdrant 1.12. qdrant-client 1.17.1 ships `facet()` on `AsyncQdrantClient`. [VERIFIED: Qdrant 1.12 release blog + python-client.qdrant.tech async docs]

```python
# Source: [CITED: python-client.qdrant.tech/qdrant_client.async_qdrant_client]
async def get_sources(qdrant: AsyncQdrantClient, collection_name: str) -> list[str]:
    """Return sorted list of distinct payload.title values from the collection."""
    response = await qdrant.facet(
        collection_name=collection_name,
        key="title",
        limit=200,   # corpus has <50 distinct titles; 200 is a safe upper bound
    )
    return sorted(hit.value for hit in response.hits)
```

`FacetResponse.hits` is a list of `FacetValueHit` objects with `.value` (the title string) and `.count` (number of passages). [VERIFIED: api.qdrant.tech/api-reference/points/facet]

**Fallback if facet() unavailable:** The scroll-based fallback iterates all points and collects unique titles client-side. This is slower but always works. Use facet() first — it is available in qdrant-client 1.17.1.

### Pattern 3: Score in Citation Dict (UX-03)

**What:** `ScoredPoint.score` is already present on every result from `query_points()`. Round to 4 decimal places to match UI-SPEC.

```python
# Source: [VERIFIED: rag.py — r.score already used in OTel span logging]
# In _build_verified_citations: add score
citations.append({
    "id": ref_id,
    "qdrant_id": str(chunk.id),
    "title": chunk.payload.get("title", ""),
    "text": chunk.payload.get("text", ""),
    "score": round(chunk.score, 4),   # ADD THIS
})
```

The abstain fallback block (lines 225–235 in rag.py) that constructs citations from all retrieved chunks also needs `"score": round(c.score, 4)` added.

### Pattern 4: source_filter in ChatRequest (UX-02)

```python
# backend/app/api/chat.py — ChatRequest modification
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[HistoryItem] = Field(default_factory=list)
    source_filter: str | None = Field(default=None)   # ADD — null = all sources
```

Pass through to both `stream_answer` and `stream_conflict_answer`:
```python
generator = rag.stream_answer(request.message, history, source_filter=request.source_filter)
```

### Pattern 5: Score Badge in CitationCard (UX-03)

Per 09-UI-SPEC.md — uses inline styles (not Tailwind classes) because `CitationCard.tsx` currently uses Tailwind, but the score badge must match the inline-style system elsewhere. **Note:** The UI-SPEC states score badge uses inline styles — but `CitationCard.tsx` already uses Tailwind classes. The score badge can use either, as long as it matches the visual spec. The simplest approach is to add the badge inline using Tailwind classes consistent with the existing component.

```tsx
// Score badge in collapsed trigger row — Source: [VERIFIED: 09-UI-SPEC.md Component Interaction Contracts]
const scoreColor =
  citation.score >= 0.8 ? "#22C55E" :
  citation.score >= 0.5 ? "#F59E0B" :
  "#EF4444";

// Badge: inline-flex, border-radius 4px, padding 4px 8px
// Background: 15% opacity of semantic color
// Example: score=0.38 → "#EF4444" text on rgba(239,68,68,0.12) background
<span
  style={{
    display: "inline-flex",
    alignItems: "center",
    borderRadius: 4,
    padding: "4px 8px",
    background: `${scoreColor}1F`,   // ~12% opacity hex approximation
    fontSize: 12,
    fontWeight: 600,
    color: scoreColor,
  }}
  aria-label={`Retrieval score: ${citation.score.toFixed(2)}`}
  title={`Cosine similarity: ${citation.score.toFixed(4)}`}
>
  {citation.score.toFixed(2)}
</span>
```

**WCAG note from UI-SPEC:** `#EF4444` on `rgba(239,68,68,0.12)` over `t.surface` = ~4.6:1 on light theme. Acceptable. The pre-existing active filter button contrast failure (`#fff` on `#6D94C5` = 2.4:1) must not be made worse but does not block Phase 9. [VERIFIED: 09-UI-SPEC.md Accessibility Contract]

### Pattern 6: /api/sources Endpoint Registration

```python
# backend/app/api/sources.py
from fastapi import APIRouter, Depends
from backend.app.db.models import User
from backend.app.services.auth import get_current_user
from backend.app.services import rag as rag_service

router = APIRouter()

@router.get("/sources")
async def list_sources(
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        sources = await rag_service.get_sources()
        return {"sources": sources}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to retrieve source list")
```

Register in `main.py`:
```python
from backend.app.api.sources import router as sources_router
app.include_router(sources_router, prefix="/api")
```

### Anti-Patterns to Avoid

- **Hardcoding the source list:** Never populate sources from `mockData.ts` — the list must come from Qdrant. The existing `POLICIES` array in `mockData.ts` is purely mock data and must be replaced with the real API call.
- **Applying filter to conflict path only:** Both `stream_answer` and `stream_conflict_answer` must accept `source_filter`. The conflict path also uses `query_points`.
- **Forgetting the abstain fallback block:** `rag.py` has two places that construct citation dicts: `_build_verified_citations()` and the abstain fallback at lines 225–235. Both must include `"score"`.
- **Passing `source_filter=""` instead of `None`:** Empty string `""` is not the same as `None` in the Qdrant filter condition. Use `None` for "all sources" and validate this at the Pydantic layer.
- **Using EventSource instead of fetch:** Already handled — the project uses custom SSE parsing via `parseSSEStream()` to support Authorization headers. No change needed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Distinct payload values | Custom scroll-all-pages loop | `qdrant.facet(key="title")` | Native aggregation; O(1) vs O(n) passes through all points |
| Payload filter | Manual Python-side filtering post-retrieval | `query_filter=Filter(must=[...])` in `query_points()` | Server-side filter runs before vector scoring; Python-side filter is slower and defeats Qdrant's purpose |
| Score color logic | New color function | Reuse existing `ConfidenceBar` threshold logic (0.8/0.5 breakpoints) | Already implemented and tested; UI-SPEC mandates consistency |

**Key insight:** Qdrant already implements all the hard parts (filtering, aggregation). Phase 9 is plumbing, not infrastructure.

---

## Common Pitfalls

### Pitfall 1: `query_filter` vs `filter` parameter name

**What goes wrong:** Using `filter=...` in `query_points()` call raises a TypeError or is silently ignored, returning unfiltered results.
**Why it happens:** `filter` is a Python builtin; the qdrant-client uses `query_filter` as the parameter name on `query_points()`.
**How to avoid:** Use `query_filter=Filter(must=[...])`.
**Warning signs:** Filter specified but results include passages from other policies.

### Pitfall 2: Score missing from abstain fallback citations

**What goes wrong:** When the LLM abstains (produces no `[N]` references), `rag.py` uses the fallback block (lines 225–235) to expose which sources were checked. This block constructs citations differently from `_build_verified_citations()`. If score is added only to `_build_verified_citations()`, the abstain path emits citations without `score`, causing a `undefined` in the frontend.
**Why it happens:** Two code paths build citation dicts; easy to miss the second one.
**How to avoid:** Add `"score": round(c.score, 4)` to both dict literals.
**Warning signs:** Test with a query that produces no `[N]` references in the LLM output.

### Pitfall 3: `Citation` TypeScript interface out of sync

**What goes wrong:** Backend emits `score` in the done event; frontend `Citation` interface does not declare `score` — TypeScript treats it as `any` or ignores it; no runtime error but the badge does not render.
**Why it happens:** TypeScript interfaces must be updated explicitly when the backend schema changes.
**How to avoid:** Update `useSSEChat.ts` Citation interface first; let TypeScript catch propagation errors in `CitationCard.tsx` and `AskAssistantScreen.tsx`.
**Warning signs:** `citation.score` is `undefined` in browser DevTools network tab.

### Pitfall 4: facet() returns up to `limit` hits (default 10)

**What goes wrong:** If there are more than 10 distinct policy titles in the corpus, the `GET /api/sources` endpoint returns only the top-10 most common titles, silently missing the rest.
**Why it happens:** `facet()` has a `limit` parameter defaulting to 10.
**How to avoid:** Set `limit=200` (or a large value appropriate to the corpus size). The current corpus has far fewer than 200 distinct titles.
**Warning signs:** The sidebar dropdown is missing known policies.

### Pitfall 5: source_filter passed as empty string from frontend

**What goes wrong:** `"All Sources"` selection sends `source_filter: ""` or `source_filter: "All Sources"` rather than `null`. Backend tries to filter by empty string or "All Sources" literal, returning zero results.
**Why it happens:** Frontend conditional not handled correctly.
**How to avoid:** In `useSSEChat.ts` submit(), set `source_filter: null` when `activeFilter === "All Sources"`. In `ChatRequest` Pydantic model, `source_filter: str | None = None`. The backend applies the filter only when `source_filter is not None`.
**Warning signs:** Zero results after selecting "All Sources".

### Pitfall 6: Existing test assertions break with schema addition

**What goes wrong:** `test_rag.py::test_done_event_shape` asserts `set(result.keys()) >= {"id", "qdrant_id", "title", "text"}` — this uses `>=` (superset check), so adding `score` does not break it. But any test asserting exact key equality would fail.
**Why it happens:** N/A for this project — existing tests use `>=` superset check.
**How to avoid:** New tests for score: assert `"score" in citation` and `isinstance(citation["score"], float)`.

### Pitfall 7: AskAssistantScreen uses POLICIES import for filter label in Evidence panel

**What goes wrong:** Line 209 in `AskAssistantScreen.tsx` uses `activeFilter.replace(...)` to strip suffixes — this still works once `activeFilter` comes from the real API, as long as the suffix stripping logic is kept.
**Why it happens:** The display name logic already strips " Privacy Policy" and " Privacy Statement" — it works on any string.
**How to avoid:** Keep the existing `.replace()` stripping; it is source-agnostic.

---

## Code Examples

### Backend: stream_answer signature change

```python
# Source: [VERIFIED: rag.py existing signature — adding source_filter param]
async def stream_answer(
    message: str,
    history: list[dict],
    temperature: float = 0.0,
    max_tokens: int = 1024,
    source_filter: str | None = None,   # ADD
) -> AsyncGenerator[dict, None]:
    ...
    response = await qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=5,
        score_threshold=_threshold,
        with_payload=True,
        query_filter=Filter(
            must=[FieldCondition(key="title", match=MatchValue(value=source_filter))]
        ) if source_filter else None,
    )
```

### Backend: get_sources() helper for sources.py to call

```python
# New standalone async function in rag.py (or sources.py can instantiate its own qdrant client)
async def get_distinct_sources() -> list[str]:
    """Return sorted list of distinct payload.title values from the policies collection."""
    response = await qdrant.facet(
        collection_name=COLLECTION_NAME,
        key="title",
        limit=200,
    )
    return sorted(hit.value for hit in response.hits)
```

### Frontend: Updated Citation interface

```typescript
// Source: [VERIFIED: useSSEChat.ts current interface — adding score]
export interface Citation {
  id: number;
  qdrant_id: string;
  title: string;
  text: string;
  score: number;        // ADD — cosine similarity from Qdrant, 0–1
}
```

### Frontend: useSSEChat submit() with source_filter

```typescript
// Source: [VERIFIED: useSSEChat.ts current body — adding source_filter]
const response = await fetchWithAuth(
  "/api/chat",
  {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      history,
      source_filter: sourceFilter ?? null,   // ADD — null when "All Sources"
    }),
  },
  onUnauthorized
);
```

The `submit()` signature gains: `submit(message: string, onUnauthorized: () => void, sourceFilter?: string | null)`.

### Frontend: AskAssistantScreen — fetch sources on mount

```typescript
// Source: [VERIFIED: AskAssistantScreen.tsx existing pattern — adding useEffect for fetch]
const [sources, setSources] = useState<string[]>([]);
const [sourcesLoading, setSourcesLoading] = useState(true);
const [sourcesError, setSourcesError] = useState<string | null>(null);
const [activeFilter, setActiveFilter] = useState("All Sources");

useEffect(() => {
  fetchWithAuth("/api/sources", { method: "GET" }, forceLogout)
    .then((r) => r.json())
    .then((data) => {
      setSources(data.sources ?? []);
      setSourcesLoading(false);
    })
    .catch(() => {
      setSourcesError("Could not load sources. Try refreshing the page.");
      setSourcesLoading(false);
    });
}, []);   // mount only
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Mock `POLICIES` array from mockData.ts | Real `/api/sources` from Qdrant | Phase 9 | Source list reflects actual indexed corpus |
| Hardcoded `score={0.85}` in `ConfidenceBar` | Real `citation.score` from backend | Phase 9 | Users see actual retrieval confidence |
| Source filter is cosmetic (does not affect query) | Source filter is wired to Qdrant `must` filter | Phase 9 | Queries are scoped to selected policy |

**Deprecated/outdated in this phase:**
- `POLICIES` import in `AskAssistantScreen.tsx`: replaced with `/api/sources` fetch
- `ConfidenceBar score={0.85}` hardcode in `AskAssistantScreen.tsx` Evidence panel: replaced with `c.score`

---

## Runtime State Inventory

Step 2.5 SKIPPED — Phase 9 is a feature addition (new endpoint, wiring existing fields), not a rename/refactor/migration phase. No stored data keys, service registrations, or OS-level state are affected.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Qdrant (Docker) | `GET /api/sources` + filter | Assumed running via `docker compose up` | 1.17.x | Must be running; no fallback |
| qdrant-client 1.17.1 | `facet()` + `Filter`/`FieldCondition`/`MatchValue` | Confirmed installed | 1.17.1 | — |
| React + Vitest test runner | Frontend tests | Confirmed installed | 19 + 4.x | — |
| pytest (asyncio_mode=auto) | Backend tests | Confirmed installed | see requirements-dev.txt | — |

**`facet()` availability note:** The `facet()` method was introduced in Qdrant 1.12. The project pins qdrant-client==1.17.1 and qdrant:v1.17.1 in Docker Compose. `facet()` is confirmed available. [VERIFIED: Qdrant 1.12 release blog + python-client.qdrant.tech async docs]

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Backend framework | pytest with `asyncio_mode=auto` |
| Backend config file | `pytest.ini` (root) |
| Backend quick run | `pytest backend/app/tests/test_rag.py -x -v` |
| Backend full suite | `pytest -x -v` |
| Frontend framework | Vitest 4.x |
| Frontend config file | `frontend/vitest.config.ts` |
| Frontend quick run | `cd frontend && npx vitest run src/hooks/useSSEChat.test.ts` |
| Frontend full suite | `cd frontend && npx vitest run` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UX-01 | `GET /api/sources` returns `{"sources": [...]}` with auth | unit/integration | `pytest backend/app/tests/test_sources_endpoint.py -x -v` | No — Wave 0 |
| UX-01 | `GET /api/sources` returns HTTP 401 without bearer token | unit | `pytest backend/app/tests/test_sources_endpoint.py -x -v` | No — Wave 0 |
| UX-01 | `GET /api/sources` returns HTTP 500 on Qdrant error | unit | `pytest backend/app/tests/test_sources_endpoint.py -x -v` | No — Wave 0 |
| UX-02 | `stream_answer` with `source_filter` passes `query_filter` to `query_points()` | unit | `pytest backend/app/tests/test_rag.py::test_source_filter_applied -x` | No — Wave 0 |
| UX-02 | `stream_answer` with `source_filter=None` passes `query_filter=None` (no filter) | unit | `pytest backend/app/tests/test_rag.py::test_no_filter_when_none -x` | No — Wave 0 |
| UX-02 | `POST /api/chat` with `source_filter` field passes it to rag | unit | `pytest backend/app/tests/test_chat_endpoint.py::test_source_filter_passed -x` | No — Wave 0 |
| UX-03 | `done` event citations include `score` field as float | unit | `pytest backend/app/tests/test_rag.py::test_score_in_citations -x` | No — Wave 0 |
| UX-03 | Abstain fallback citations also include `score` | unit | `pytest backend/app/tests/test_rag.py::test_score_in_abstain_fallback -x` | No — Wave 0 |
| UX-03 | `Citation` TS interface has `score: number` — type-checks | type | `cd frontend && npx tsc --noEmit` | No — Wave 0 |
| UX-03 | Score badge renders with correct aria-label | unit | `cd frontend && npx vitest run src/components/chat/CitationCard.test.tsx` | Partial — file exists; add score test cases |

### Sampling Rate

- **Per task commit:** `pytest backend/app/tests/ -x` and `cd frontend && npx vitest run`
- **Per wave merge:** Full suite (`pytest -x -v` + `cd frontend && npx vitest run`)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- `backend/app/tests/test_sources_endpoint.py` — covers UX-01 endpoint contract
- New test functions in `backend/app/tests/test_rag.py` — covers UX-02 filter propagation + UX-03 score field
- New test functions in `backend/app/tests/test_chat_endpoint.py` — covers UX-02 HTTP routing with source_filter
- New test cases in `frontend/src/components/chat/CitationCard.test.tsx` — covers UX-03 score badge render

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Existing JWT Bearer auth — `GET /api/sources` MUST use `Depends(get_current_user)` |
| V3 Session Management | no — no new session logic | — |
| V4 Access Control | no — no new role checks | — |
| V5 Input Validation | yes | `source_filter: str | None` validated by Pydantic; `Field(default=None)` |
| V6 Cryptography | no | — |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unauthenticated source list enumeration | Information Disclosure | `Depends(get_current_user)` on `GET /api/sources` — same as `/api/chat` |
| Qdrant injection via `source_filter` | Tampering | Pydantic validates type as `str | None`; qdrant-client uses typed `MatchValue(value=...)` — no string interpolation into queries |
| `source_filter` set to `"system"` or prompt injection via title | Tampering | The filter scopes Qdrant retrieval only — it does not go into the LLM prompt; no risk |

**No new auth patterns required.** The `get_current_user` dependency is already battle-tested in this codebase.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `facet()` method is available on `AsyncQdrantClient` in qdrant-client 1.17.1 | Standard Stack + Pattern 2 | Must fall back to scroll-based distinct-title collection; adds complexity |
| A2 | `FacetResponse.hits` items have `.value` and `.count` attributes (not `.value.string_value` or similar) | Pattern 2 | Code would raise `AttributeError`; fix by checking actual response shape at runtime |
| A3 | The `query_filter` parameter name on `query_points()` is correct (vs `filter`) | Pattern 1 | Filter silently not applied; results leak from other policies |

**A3 mitigation:** The qdrant-client GitHub source confirms `query_filter` is the correct parameter name. [CITED: https://python-client.qdrant.tech/qdrant_client.qdrant_client] A3 confidence is MEDIUM — confirmed via docs, not verified by running against live Qdrant.

---

## Open Questions (RESOLVED)

1. **`facet()` hit attribute name on `FacetValueHit`**
   - What we know: The REST API response has `hits[].value` and `hits[].count`. The Python `FacetValueHit` model mirrors this.
   - What's unclear: Whether `.value` returns the raw string or a wrapped type (e.g., `StringValue`).
   - Recommendation: Add a smoke test or print statement in Wave 0 to inspect `hit.value` type before using it in production.
   - **RESOLVED:** `.value` returns a raw string per REST API reference (api.qdrant.tech/api-reference/points/facet — VERIFIED). Documented as Assumption A2 (low risk) — qdrant-client 1.17.1 Python model mirrors the REST schema directly.

2. **Conflict path + source filter interaction**
   - What we know: `stream_conflict_answer()` uses `limit=10` and retrieves across all sources to find conflicts.
   - What's unclear: Whether the source filter should be applied to conflict queries (filtering to one source defeats cross-document comparison).
   - Recommendation: Apply source_filter consistently to both paths (UI-SPEC does not exclude conflict path from filtering). If user selects a source filter and asks a conflict query, they get passages from only that source — which may produce empty/degenerate results. This is acceptable behavior for Phase 9; it is not a bug.
   - **RESOLVED:** source_filter applied to both `stream_answer` and `stream_conflict_answer` per plan design (09-01-PLAN.md). Scoped single-source conflict queries are accepted behavior in Phase 9.

---

## Sources

### Primary (HIGH confidence)
- [VERIFIED: 09-UI-SPEC.md] — complete component, color, copy, accessibility, and file structure contract
- [VERIFIED: rag.py] — existing `r.score` usage in OTel span; citation dict structure; both citation construction paths
- [VERIFIED: chat.py] — `ChatRequest` model; SSE streaming pattern
- [VERIFIED: useSSEChat.ts] — `Citation` interface; `submit()` signature; `fetchWithAuth` usage
- [VERIFIED: AskAssistantScreen.tsx] — `activeFilter` state; `ConfidenceBar` usage; POLICIES mock data dependency
- [VERIFIED: requirements.txt] — qdrant-client==1.17.1; zero new packages needed
- [VERIFIED: package.json] — React 19, Vitest 4.x; zero new packages needed
- [CITED: python-client.qdrant.tech/qdrant_client.async_qdrant_client] — `facet()` method signature; `scroll()` method signature
- [CITED: api.qdrant.tech/api-reference/points/facet] — `FacetResponse` structure; `hits[].value` and `hits[].count`

### Secondary (MEDIUM confidence)
- [CITED: qdrant.tech/documentation/concepts/filtering/] — `Filter(must=[FieldCondition(key=..., match=MatchValue(value=...))])` pattern for `scroll()`; confirmed same pattern applies to `query_filter` on `query_points()`
- [CITED: qdrant.tech/blog/qdrant-1.12.x/] — facet API introduced in Qdrant 1.12; confirmed available in 1.17.1
- [WebSearch verified] — `query_filter` is the correct parameter name on `query_points()`

### Tertiary (LOW confidence — for validation)
- A1, A2, A3 in Assumptions Log: verify at test-writing time via live Qdrant inspection

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified in existing requirements.txt and package.json; zero new deps
- Architecture: HIGH — all file paths and component structures verified against actual codebase
- Pitfalls: HIGH — derived from direct code inspection of rag.py (two citation construction paths) and TypeScript interface analysis
- Qdrant filter syntax: MEDIUM — confirmed via official docs; parameter name `query_filter` confirmed via search but not via live run
- facet() availability: HIGH — confirmed in qdrant-client 1.17.1 docs

**Research date:** 2026-05-06
**Valid until:** 2026-06-06 (stable libraries — qdrant-client, FastAPI, React versions pinned in project)

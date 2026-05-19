# Phase 9: UX Enhancements - Pattern Map

**Mapped:** 2026-05-06
**Files analyzed:** 8 (1 new, 7 modified)
**Analogs found:** 8 / 8

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/api/sources.py` | route | request-response | `backend/app/api/auth.py` | role-match |
| `backend/app/api/chat.py` | route | request-response | self (modify existing) | exact |
| `backend/app/services/rag.py` | service | streaming + CRUD | self (modify existing) | exact |
| `frontend/src/hooks/useSSEChat.ts` | hook | streaming | self (modify existing) | exact |
| `frontend/src/components/chat/CitationCard.tsx` | component | request-response | self (modify existing) | exact |
| `frontend/src/pages/AskAssistantScreen.tsx` | page | request-response | self (modify existing) | exact |
| `backend/app/tests/test_sources_endpoint.py` | test | request-response | `backend/app/tests/test_chat_endpoint.py` | exact |
| `backend/app/tests/test_rag.py` (extend) | test | streaming | self (modify existing) | exact |

---

## Pattern Assignments

### `backend/app/api/sources.py` (NEW — route, request-response)

**Analog:** `backend/app/api/auth.py` (router structure, Depends pattern) + `backend/app/api/chat.py` (Depends(get_current_user) guard)

**Imports pattern** — copy from `backend/app/api/auth.py` lines 15-29, `backend/app/api/chat.py` lines 14-20:
```python
from fastapi import APIRouter, Depends, HTTPException
from backend.app.db.models import User
from backend.app.services.auth import get_current_user
from backend.app.services import rag
```

**Router declaration pattern** — copy from `backend/app/api/auth.py` line 32:
```python
router = APIRouter()
```

**Auth guard pattern** — copy from `backend/app/api/chat.py` lines 77-79:
```python
@router.get("/sources")
async def list_sources(
    current_user: User = Depends(get_current_user),
) -> dict:
```

**Error handling pattern** — copy from `backend/app/api/auth.py` lines 83-87 (HTTPException raise):
```python
try:
    sources = await rag.get_distinct_sources()
    return {"sources": sources}
except Exception:
    raise HTTPException(status_code=500, detail="Failed to retrieve source list")
```

**Router registration pattern** — copy from `backend/app/main.py` lines 16-17, 161-162:
```python
# In main.py — add alongside existing router imports and include_router calls:
from backend.app.api.sources import router as sources_router
app.include_router(sources_router, prefix="/api")
```

---

### `backend/app/api/chat.py` (MODIFY — add source_filter to ChatRequest)

**Analog:** self — modify existing file at `backend/app/api/chat.py`

**Current ChatRequest** (lines 54-62) — add `source_filter` field:
```python
# CURRENT (lines 54-62):
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[HistoryItem] = Field(default_factory=list)

# PHASE 9 MODIFICATION — add one field:
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[HistoryItem] = Field(default_factory=list)
    source_filter: str | None = Field(default=None)   # null = all sources
```

**Generator dispatch pattern** (lines 96-102) — pass source_filter through to both paths:
```python
# CURRENT (lines 96-102):
async def _generate() -> AsyncGenerator[str, None]:
    if is_conflict_query(request.message):
        generator = rag.stream_conflict_answer(request.message, history)
    else:
        generator = rag.stream_answer(request.message, history)

# PHASE 9 MODIFICATION:
async def _generate() -> AsyncGenerator[str, None]:
    if is_conflict_query(request.message):
        generator = rag.stream_conflict_answer(request.message, history, source_filter=request.source_filter)
    else:
        generator = rag.stream_answer(request.message, history, source_filter=request.source_filter)
```

**Pydantic validation note:** `str | None` with `Field(default=None)` rejects empty string `""` at the application layer — the Pydantic model accepts it but rag.py must treat `None` as "all sources" and non-None as a filter. An empty-string guard belongs in rag.py (`if source_filter` is falsy for both `None` and `""`).

---

### `backend/app/services/rag.py` (MODIFY — source_filter param + Qdrant filter + score in citations)

**Analog:** self — three targeted changes within existing file

**Change 1: stream_answer signature** (line 142-146) — add source_filter param:
```python
# CURRENT (lines 141-146):
async def stream_answer(
    message: str,
    history: list[dict],
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> AsyncGenerator[dict, None]:

# PHASE 9 MODIFICATION:
async def stream_answer(
    message: str,
    history: list[dict],
    temperature: float = 0.0,
    max_tokens: int = 1024,
    source_filter: str | None = None,
) -> AsyncGenerator[dict, None]:
```

**Change 2: Qdrant query_points call** (lines 172-179) — add query_filter parameter.
Copy the import pattern from existing qdrant_client usage in the file; add models import at top:
```python
# ADD to imports at top of rag.py:
from qdrant_client.models import Filter, FieldCondition, MatchValue

# MODIFY the query_points call (lines 172-179):
# CURRENT:
response = await qdrant.query_points(
    collection_name=COLLECTION_NAME,
    query=query_vector,
    limit=5,
    score_threshold=_threshold,
    with_payload=True,
)

# PHASE 9 MODIFICATION:
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

Apply the same query_filter change to `stream_conflict_answer` (lines 315-322) — same pattern, limit=10.

**Change 3: score in _build_verified_citations** (lines 110-136) — add score key:
```python
# CURRENT (lines 124-129):
citations.append({
    "id": ref_id,
    "qdrant_id": str(chunk.id),
    "title": chunk.payload.get("title", ""),
    "text": chunk.payload.get("text", ""),
})

# PHASE 9 MODIFICATION:
citations.append({
    "id": ref_id,
    "qdrant_id": str(chunk.id),
    "title": chunk.payload.get("title", ""),
    "text": chunk.payload.get("text", ""),
    "score": round(chunk.score, 4),   # ADD — cosine similarity from Qdrant ScoredPoint
})
```

**Change 4: score in abstain fallback** (lines 225-234) — SAME addition, different code path:
```python
# CURRENT (lines 226-234) — abstain fallback in stream_answer:
citations = [
    {
        "id": i + 1,
        "qdrant_id": str(c.id),
        "title": c.payload.get("title", ""),
        "text": c.payload.get("text", ""),
    }
    for i, c in enumerate(results)
]

# PHASE 9 MODIFICATION:
citations = [
    {
        "id": i + 1,
        "qdrant_id": str(c.id),
        "title": c.payload.get("title", ""),
        "text": c.payload.get("text", ""),
        "score": round(c.score, 4),   # ADD
    }
    for i, c in enumerate(results)
]
```

Apply the same score addition to the abstain fallback in `stream_conflict_answer` (lines 367-376).

**Change 5: get_distinct_sources() helper** — NEW function at module level (add after module-level singletons, around line 56):
```python
async def get_distinct_sources() -> list[str]:
    """Return sorted list of distinct payload.title values from the policies collection.
    Uses Qdrant facet API (available since Qdrant 1.12; pinned to 1.17.1).
    limit=200: corpus has <50 distinct titles; safe upper bound.
    """
    response = await qdrant.facet(
        collection_name=COLLECTION_NAME,
        key="title",
        limit=200,
    )
    return sorted(hit.value for hit in response.hits)
```

---

### `frontend/src/hooks/useSSEChat.ts` (MODIFY — add score to Citation, add source_filter to submit)

**Analog:** self — two targeted changes within existing file

**Change 1: Citation interface** (lines 4-9) — add score field:
```typescript
// CURRENT (lines 4-9):
export interface Citation {
  id: number;
  qdrant_id: string;
  title: string;
  text: string;
}

// PHASE 9 MODIFICATION:
export interface Citation {
  id: number;
  qdrant_id: string;
  title: string;
  text: string;
  score: number;   // cosine similarity from Qdrant, 0–1, 4 decimal places max
}
```

**Change 2: UseSSEChatReturn interface** (lines 19-23) — add source_filter param to submit:
```typescript
// CURRENT (lines 19-23):
export interface UseSSEChatReturn {
  messages: Message[];
  isStreaming: boolean;
  submit: (message: string, onUnauthorized: () => void) => Promise<void>;
}

// PHASE 9 MODIFICATION:
export interface UseSSEChatReturn {
  messages: Message[];
  isStreaming: boolean;
  submit: (message: string, onUnauthorized: () => void, sourceFilter?: string | null) => Promise<void>;
}
```

**Change 3: submit() signature and fetch body** (lines 68-100) — add sourceFilter param, inject in body:
```typescript
// CURRENT (lines 68-69):
const submit = useCallback(
  async (message: string, onUnauthorized: () => void): Promise<void> => {

// PHASE 9 MODIFICATION:
const submit = useCallback(
  async (message: string, onUnauthorized: () => void, sourceFilter?: string | null): Promise<void> => {
```

```typescript
// CURRENT (lines 96-100):
body: JSON.stringify({ message, history }),

// PHASE 9 MODIFICATION:
body: JSON.stringify({
  message,
  history,
  source_filter: sourceFilter ?? null,   // null when "All Sources" or omitted
}),
```

**useCallback dependency array** (line 173) — add sourceFilter if it comes from props, but since it is a parameter, the array stays `[messages, isStreaming]`.

---

### `frontend/src/components/chat/CitationCard.tsx` (MODIFY — add score badge to collapsed trigger row)

**Analog:** self + `frontend/src/components/ui/ConfidenceBar.tsx` (traffic-light color logic)

**Traffic-light color logic pattern** — copy from `frontend/src/components/ui/ConfidenceBar.tsx` line 6:
```typescript
// Source: ConfidenceBar.tsx line 6 — reuse exact same thresholds (UI-SPEC mandates consistency)
const color = score >= 0.8 ? "#22C55E" : score >= 0.5 ? "#F59E0B" : "#EF4444";
```

**Change 1: CitationCardProps** (lines 11-13) — add optional score:
```typescript
// CURRENT:
interface CitationCardProps {
  citation: Citation;
}

// PHASE 9 MODIFICATION:
interface CitationCardProps {
  citation: Citation;
}
// No change needed — score comes from citation.score (Citation interface already updated in useSSEChat.ts)
```

**Change 2: Score badge in collapsed trigger row** — insert between preview div and ChevronDown (between lines 55 and 57):
```tsx
// ADD after the preview div (after line 55), before the ChevronDown (line 57):
{/* Score badge — inline-flex, traffic-light color, 12px/600 per UI-SPEC Typography */}
{citation.score !== undefined && (
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
      flexShrink: 0,
    }}
    aria-label={`Retrieval score: ${citation.score.toFixed(2)}`}
    title={`Cosine similarity: ${citation.score.toFixed(4)}`}
  >
    {citation.score.toFixed(2)}
  </span>
)}
```

**scoreColor derived variable** — add after `preview` declaration (line 29):
```tsx
// ADD after line 29 (after preview derivation):
const scoreColor =
  citation.score >= 0.8 ? "#22C55E" :
  citation.score >= 0.5 ? "#F59E0B" :
  "#EF4444";
```

**CollapsibleTrigger layout change** — the trigger row already uses `flex items-start justify-between gap-2`. The score badge fits between the preview div and ChevronDown with no layout changes needed. The badge uses `flexShrink: 0` to prevent compression on narrow screens.

**No ConfidenceBar in CitationCard** — per UI-SPEC: score badge (inline) only in collapsed row. ConfidenceBar lives exclusively in the Evidence panel (`AskAssistantScreen`).

---

### `frontend/src/pages/AskAssistantScreen.tsx` (MODIFY — replace mock data with API fetch, wire real scores)

**Analog:** self — four targeted changes within existing file

**Change 1: Remove POLICIES import, add sources state** (lines 1-6, 18-19):
```typescript
// CURRENT (line 5):
import { POLICIES, SUGGESTED_PROMPTS } from "@/lib/mockData";

// PHASE 9 MODIFICATION — remove POLICIES from import:
import { SUGGESTED_PROMPTS } from "@/lib/mockData";
```

```typescript
// CURRENT (line 18):
const [activeFilter, setActiveFilter] = useState(POLICIES[0].name);

// PHASE 9 MODIFICATION — replace with real-API state:
const [sources, setSources] = useState<string[]>([]);
const [sourcesLoading, setSourcesLoading] = useState(true);
const [sourcesError, setSourcesError] = useState<string | null>(null);
const [activeFilter, setActiveFilter] = useState("All Sources");
```

**Change 2: useEffect for sources fetch on mount** — add after the existing useEffect (after line 31). Copy fetchWithAuth pattern from existing useSSEChat.ts usage:
```typescript
// ADD new useEffect for source list (mount only):
useEffect(() => {
  fetchWithAuth("/api/sources", { method: "GET" }, forceLogout)
    .then((r) => r.json())
    .then((data: { sources: string[] }) => {
      setSources(data.sources ?? []);
      setSourcesLoading(false);
    })
    .catch(() => {
      setSourcesError("Could not load sources. Try refreshing the page.");
      setSourcesLoading(false);
    });
}, []);   // mount only — dependency on forceLogout would cause re-fetch on every render
```

**fetchWithAuth import** — add to imports:
```typescript
import { fetchWithAuth } from "@/lib/api";
```

**Change 3: sidebar filter buttons** (lines 47-61) — replace POLICIES-based map with sources-based map:
```tsx
// CURRENT (lines 39-61): uses indexedPolicies from POLICIES.filter(...)
// PHASE 9 MODIFICATION — replace sidebar content:

{sourcesLoading ? (
  // Skeleton rows while loading (3 placeholders, aria-busy)
  <div aria-busy="true">
    {[0, 1, 2].map((i) => (
      <div
        key={i}
        style={{ height: 32, borderRadius: 5, background: t.border, marginBottom: 2, animation: "pulse 1s ease-in-out infinite" }}
      />
    ))}
  </div>
) : sourcesError ? (
  // Error state — role="alert" for screen readers (UI-SPEC Accessibility)
  <div role="alert" style={{ fontSize: 12, color: t.faint }}>
    {sourcesError}
  </div>
) : (
  // "All Sources" prepended + real sources from API
  <nav aria-label="Policy source filter">
    {["All Sources", ...sources].map((name) => (
      <button
        key={name}
        onClick={() => setActiveFilter(name)}
        title={name}
        style={{
          display: "block", width: "100%", textAlign: "left",
          padding: "7px 10px", borderRadius: 5, fontSize: 12, border: "none", cursor: "pointer", marginBottom: 2,
          background: activeFilter === name ? accent : "transparent",
          color: activeFilter === name ? "#fff" : t.text3,
          fontWeight: activeFilter === name ? 600 : 400,
          transition: "background 0.1s",
        }}
      >
        {name === "All Sources" ? name : name.replace(" Privacy Policy", "").replace(" Privacy Statement", "")}
      </button>
    ))}
  </nav>
)}
```

**Change 4: wire source_filter to submit** (line 35):
```typescript
// CURRENT (line 35):
submit(input, forceLogout);

// PHASE 9 MODIFICATION:
submit(input, forceLogout, activeFilter === "All Sources" ? null : activeFilter);
```

**Change 5: replace hardcoded ConfidenceBar score** (lines 131-133, 219):
```tsx
// CURRENT (line 132):
<ConfidenceBar score={0.88} />

// PHASE 9 MODIFICATION — use first citation score for message-area confidence bar:
<ConfidenceBar score={msg.citations[0]?.score ?? 0} />

// CURRENT (line 219) — Evidence panel:
<div style={{ width: 80 }}><ConfidenceBar score={0.85} /></div>

// PHASE 9 MODIFICATION:
<div style={{ width: 80 }}><ConfidenceBar score={c.score ?? 0} /></div>
```

**Section label spacing fix** — per UI-SPEC Checker revision, change `marginBottom: 10` to `marginBottom: 8` (line 46) and `fontSize: 11` to `fontSize: 12` (line 46):
```tsx
// CURRENT (line 46):
<div style={{ fontSize: 11, fontWeight: 600, color: t.faint, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 10 }}>Policy Source</div>

// PHASE 9 MODIFICATION:
<div style={{ fontSize: 12, fontWeight: 600, color: t.faint, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 8 }}>Policy Source</div>
```

---

### `backend/app/tests/test_sources_endpoint.py` (NEW — Wave 0 test stubs)

**Analog:** `backend/app/tests/test_chat_endpoint.py` (exact — same httpx + ASGITransport + dependency override pattern)

**Module structure pattern** — copy from `backend/app/tests/test_chat_endpoint.py` lines 1-17:
```python
"""
backend/app/tests/test_sources_endpoint.py
HTTP-level tests for GET /api/sources endpoint.
Uses httpx.AsyncClient with ASGITransport — no live server needed.

Run: pytest backend/app/tests/test_sources_endpoint.py -x -v
"""
import pytest
import httpx
from unittest.mock import patch, AsyncMock

from backend.app.db.models import User
from backend.app.main import create_app
from backend.app.services.auth import get_current_user
```

**Auth stub helper** — copy from `backend/app/tests/test_chat_endpoint.py` lines 25-27:
```python
def _stub_current_user():
    """Override for get_current_user — returns a dummy User without DB/JWT checks."""
    return User(id=1, username="test", hashed_password="$argon2id$stub")
```

**Authenticated GET pattern** — copy client setup from `backend/app/tests/test_chat_endpoint.py` lines 39-55, adapt for GET:
```python
@pytest.mark.asyncio
async def test_sources_returns_list():
    """UX-01: GET /api/sources with auth returns {"sources": [...]} with HTTP 200."""
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_current_user
    try:
        with patch("backend.app.services.rag.get_distinct_sources", new_callable=AsyncMock,
                   return_value=["Google Privacy Policy", "OpenAI Privacy Policy"]):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/sources")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert "sources" in data
    assert isinstance(data["sources"], list)
```

**Unauthenticated 401 pattern** — copy from `backend/app/tests/test_auth.py` style (no override = real auth, no token = 401):
```python
@pytest.mark.asyncio
async def test_sources_requires_auth():
    """UX-01: GET /api/sources without bearer token returns HTTP 401."""
    app = create_app()
    # No dependency_overrides — real get_current_user will reject missing token
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/sources")  # no Authorization header
    assert response.status_code == 401
```

**Qdrant error → 500 pattern** — copy HTTPException raise pattern:
```python
@pytest.mark.asyncio
async def test_sources_returns_500_on_qdrant_error():
    """UX-01: GET /api/sources returns HTTP 500 when Qdrant raises an exception."""
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_current_user
    try:
        with patch("backend.app.services.rag.get_distinct_sources",
                   side_effect=Exception("Qdrant down")):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/sources")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to retrieve source list"
```

---

### `backend/app/tests/test_rag.py` (EXTEND — add score and source_filter tests)

**Analog:** self — add new test functions following existing patterns in the file

**Fixture pattern for scored point** — extend existing `sample_scored_point` in `conftest.py` (line 56-69). The fixture already has `point.score = 0.82` — no changes needed to conftest.

**UX-03 score in citations test** — copy pure function test pattern from `test_rag.py` lines 166-176:
```python
def test_score_in_citations(sample_scored_point):
    """UX-03: _build_verified_citations includes 'score' field as float rounded to 4 decimals."""
    citations = _build_verified_citations("[1]", [sample_scored_point])
    assert len(citations) == 1
    assert "score" in citations[0]
    assert isinstance(citations[0]["score"], float)
    assert citations[0]["score"] == round(sample_scored_point.score, 4)
```

**UX-02 source_filter propagation test** — copy mock test pattern from `test_rag.py` lines 63-73:
```python
@pytest.mark.asyncio
async def test_source_filter_applied(mock_openrouter, mock_qdrant):
    """UX-02: stream_answer with source_filter passes query_filter to query_points()."""
    with patch.object(rag, "openrouter", mock_openrouter), \
         patch.object(rag, "qdrant", mock_qdrant):
        events = [e async for e in stream_answer("test query", [], source_filter="Google Privacy Policy")]

    call_kwargs = mock_qdrant.query_points.call_args.kwargs
    assert call_kwargs.get("query_filter") is not None

@pytest.mark.asyncio
async def test_no_filter_when_none(mock_openrouter, mock_qdrant):
    """UX-02: stream_answer with source_filter=None passes query_filter=None."""
    with patch.object(rag, "openrouter", mock_openrouter), \
         patch.object(rag, "qdrant", mock_qdrant):
        events = [e async for e in stream_answer("test query", [], source_filter=None)]

    call_kwargs = mock_qdrant.query_points.call_args.kwargs
    assert call_kwargs.get("query_filter") is None
```

**UX-03 score in abstain fallback test** — copy done event shape from `test_rag.py` lines 179-189, use mock with real chunk retrieval and no [N] references in LLM output:
```python
@pytest.mark.asyncio
async def test_score_in_abstain_fallback(mock_openrouter, mock_qdrant, sample_scored_point):
    """UX-03: abstain fallback citations (no [N] refs in answer) also include score field."""
    mock_resp = MagicMock(); mock_resp.points = [sample_scored_point]
    mock_qdrant.query_points = AsyncMock(return_value=mock_resp)
    # LLM returns answer with NO [N] references — triggers abstain fallback
    mock_openrouter.chat.completions.create = AsyncMock(return_value=_fake_stream("No citations here."))

    with patch.object(rag, "openrouter", mock_openrouter), \
         patch.object(rag, "qdrant", mock_qdrant):
        events = [e async for e in stream_answer("test query", [])]

    done = events[-1]
    assert done["type"] == "done"
    assert len(done["citations"]) > 0
    assert "score" in done["citations"][0]
    assert isinstance(done["citations"][0]["score"], float)
```

---

## Shared Patterns

### Authentication Guard
**Source:** `backend/app/api/chat.py` lines 77-79
**Apply to:** `backend/app/api/sources.py`
```python
current_user: User = Depends(get_current_user)
```
Every protected route uses this exact pattern. `sources.py` must include it — the RESEARCH.md security contract requires `GET /api/sources` to require Bearer token.

### fetchWithAuth (Frontend)
**Source:** `frontend/src/lib/api.ts` lines 17-72
**Apply to:** `frontend/src/pages/AskAssistantScreen.tsx` (sources fetch on mount)
```typescript
// Already used in useSSEChat.ts lines 92-100 — same pattern for sources fetch:
fetchWithAuth("/api/sources", { method: "GET" }, forceLogout)
```
The function handles 401 refresh automatically. Import from `@/lib/api`.

### Inline Theme Token Styling
**Source:** `frontend/src/pages/AskAssistantScreen.tsx` lines 44-80 (existing sidebar)
**Apply to:** All new UI elements in `AskAssistantScreen.tsx`
```typescript
// All new elements must use t.* tokens from useTheme(), not Tailwind classes.
// AskAssistantScreen lives in the "App shell screens" styling system (UI-SPEC Design System).
const { t, accent } = useTheme();
```
The CitationCard score badge is an exception — it uses inline styles with semantic traffic-light colors (not theme tokens), which is also inline-style-based and consistent.

### Traffic-Light Color Logic
**Source:** `frontend/src/components/ui/ConfidenceBar.tsx` line 6
**Apply to:** `CitationCard.tsx` score badge, `AskAssistantScreen.tsx` Evidence panel
```typescript
const color = score >= 0.8 ? "#22C55E" : score >= 0.5 ? "#F59E0B" : "#EF4444";
```
UI-SPEC mandates the same thresholds (0.8 / 0.5) used by `ConfidenceBar` — copy exactly, do not recalculate.

### pytest + httpx Test Structure
**Source:** `backend/app/tests/test_chat_endpoint.py` lines 1-55
**Apply to:** `backend/app/tests/test_sources_endpoint.py`
```python
# Pattern: create_app() → dependency_overrides → ASGITransport → client.get/post
app = create_app()
app.dependency_overrides[get_current_user] = _stub_current_user
try:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/sources")
finally:
    app.dependency_overrides.clear()
```
Always clear `dependency_overrides` in a `finally` block to prevent fixture bleed.

### Score Superset Key Check (existing test pattern)
**Source:** `backend/app/tests/test_rag.py` line 188
**Apply to:** New score assertions in `test_rag.py`
```python
# Existing test uses >= (superset) check — adding score does NOT break it:
assert set(result.keys()) >= {"id", "qdrant_id", "title", "text"}
# New score test uses:
assert "score" in citation
assert isinstance(citation["score"], float)
```

---

## No Analog Found

No files are without analogs. All 8 files have close matches in the codebase.

---

## Critical Implementation Notes

### Two citation construction paths — both need score
`rag.py` builds citation dicts in two places:
1. `_build_verified_citations()` (lines 110-136) — primary path when LLM cites `[N]` references
2. Abstain fallback (lines 225-234 in `stream_answer`, lines 367-376 in `stream_conflict_answer`) — used when LLM produces no `[N]` references

Both dicts must include `"score": round(chunk.score, 4)`. Missing the abstain path causes `citation.score` to be `undefined` in the frontend for queries where the LLM abstains.

### `query_filter` not `filter`
The Qdrant client parameter is `query_filter` (not `filter`). Using `filter=` raises a TypeError or is silently ignored. The existing codebase does not use `filter=` anywhere — follow the existing `query_points()` call signature at lines 172-179 exactly and add `query_filter=` as a new keyword argument.

### TypeScript type propagation order
Update `useSSEChat.ts` Citation interface first. TypeScript will then surface propagation errors in `CitationCard.tsx` (where `citation.score` is used) and `AskAssistantScreen.tsx` (where `c.score` replaces hardcoded `0.85`). This order prevents runtime `undefined` errors from reaching production.

### AskAssistantScreen — two ConfidenceBar hardcodes
Line 132: `<ConfidenceBar score={0.88} />` in the message area confidence row.
Line 219: `<ConfidenceBar score={0.85} />` in the Evidence panel per-citation card.
Both must be replaced. Missing line 132 leaves a hardcoded score visible to users in the message thread.

---

## Metadata

**Analog search scope:** `backend/app/api/`, `backend/app/services/`, `backend/app/tests/`, `frontend/src/hooks/`, `frontend/src/components/chat/`, `frontend/src/pages/`, `frontend/src/lib/`, `frontend/src/components/ui/`
**Files scanned:** 24
**Pattern extraction date:** 2026-05-06

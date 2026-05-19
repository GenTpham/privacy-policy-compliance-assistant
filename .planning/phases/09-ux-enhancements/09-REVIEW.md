---
phase: 09-ux-enhancements
reviewed: 2026-05-13T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - backend/app/api/chat.py
  - backend/app/api/sources.py
  - backend/app/main.py
  - backend/app/services/rag.py
  - backend/app/tests/test_chat_endpoint.py
  - backend/app/tests/test_rag.py
  - backend/app/tests/test_rag_phase9.py
  - backend/app/tests/test_sources_endpoint.py
  - frontend/src/components/chat/CitationCard.tsx
  - frontend/src/hooks/useSSEChat.ts
  - frontend/src/pages/AskAssistantScreen.tsx
findings:
  critical: 1
  warning: 6
  info: 4
  total: 11
status: issues_found
---

# Phase 9: Code Review Report

**Reviewed:** 2026-05-13T00:00:00Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 9 adds source-filter UX (sidebar + filter propagation), confidence score display in
CitationCard, and the GET /api/sources endpoint. The backend pipeline and test coverage are
generally solid. The main critical defect is a response.body nullability crash in the SSE
hook. Beyond that, six warning-level issues were found: a silently swallowed 401 in the
sources fetch, a stale message timestamp rendered on every render cycle, an empty-string
`source_filter` that bypasses the Pydantic `min_length` contract, an unguarded
`response.body!` dereference, a silent error-loss path in the sources endpoint, and a Topic
Filter UI element that is completely wired up visually but never forwarded to the backend,
creating a misleading affordance.

---

## Critical Issues

### CR-01: `response.body!` non-null assertion crashes on null body in `parseSSEStream`

**File:** `frontend/src/hooks/useSSEChat.ts:34`

**Issue:** `parseSSEStream` unconditionally calls `response.body!.getReader()` with a
non-null assertion. `Response.body` is `null` when the fetch response has no body (e.g. a
205 Reset Content, a network proxy that strips the body, or a browser quirk on some older
versions). When `body` is null, `getReader()` throws a `TypeError` at runtime. The error
bubbles up to the `catch (_err)` block in `submit`, which replaces the placeholder
assistant message correctly — but only if the assistant placeholder was already added to
state. If the throw occurs before `setMessages` completes, the error propagates out of the
`try` block and `setIsStreaming(false)` is never reached, permanently locking the chat
input. More critically, the non-null assertion signals intent that the code assumes body is
always present, which is a fragile invariant that will silently fail in edge environments.

**Fix:**
```typescript
// In parseSSEStream, guard against null body
async function* parseSSEStream(
  response: Response
): AsyncGenerator<Record<string, unknown>> {
  if (!response.body) {
    throw new Error("Response body is null — cannot parse SSE stream");
  }
  const reader = response.body.getReader();
  // ... rest unchanged
```

The `submit` catch block already handles thrown errors and calls `setIsStreaming(false)`, so
this guard converts a silent crash into a handled error event.

---

## Warnings

### WR-01: 401 response from `/api/sources` fetch is silently swallowed — user never gets logged out

**File:** `frontend/src/pages/AskAssistantScreen.tsx:38-48`

**Issue:** The `fetchWithAuth` call for the sources list uses a raw `.then().catch()` chain
and never inspects `r.ok` before calling `r.json()`. If the token is expired and the
backend returns HTTP 401, `fetchWithAuth` will call `onUnauthorized` (i.e. `forceLogout`)
internally per the library's contract — but if the implementation instead returns the 401
`Response` object without throwing (which is the common pattern for auth refresh flows),
`r.json()` will silently parse `{"detail": "Not authenticated"}` as `data`, assign
`data.sources` as `undefined`, fall through to `setSources([] )`, and leave the user logged
in with an empty source list. There is also no check of `r.ok` to distinguish a 500 error
from a 200 with an empty array.

**Fix:**
```tsx
fetchWithAuth("/api/sources", { method: "GET" }, forceLogout)
  .then((r) => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  })
  .then((data: { sources: string[] }) => {
    setSources(data.sources ?? []);
    setSourcesLoading(false);
  })
  .catch(() => {
    setSourcesError("Could not load sources. Try refreshing the page.");
    setSourcesLoading(false);
  });
```

### WR-02: Message timestamps are recalculated on every render, not at message creation time

**File:** `frontend/src/pages/AskAssistantScreen.tsx:208`

**Issue:** `new Date().toTimeString().slice(0, 5)` is evaluated inside `messages.map()`
during every render. Because the component re-renders on every SSE delta event
(state updates from `setMessages` in `useSSEChat`), the timestamp displayed under each
message continuously changes while streaming is in progress. Once streaming finishes and
the component stops re-rendering at high frequency, the displayed time will reflect the
last render's clock, not the time the message was sent or received. This produces
incorrect timestamps.

**Fix:** Add a `timestamp` field to the `Message` interface and populate it at creation
time:
```typescript
// In useSSEChat.ts Message interface:
export interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  isNoMatch?: boolean;
  isError?: boolean;
  timestamp: string; // set at creation time
}

// When creating userMessage:
const userMessage: Message = {
  role: "user",
  content: message,
  timestamp: new Date().toTimeString().slice(0, 5),
};
```
Then render `{msg.timestamp}` instead of `{new Date().toTimeString().slice(0, 5)}`.

### WR-03: Empty string `source_filter` bypasses backend validation but gets treated as no-filter — contract mismatch

**File:** `backend/app/services/rag.py:196-199` and `backend/app/services/rag.py:344-347`

**Issue:** Both `stream_answer` and `stream_conflict_answer` use a falsy check
(`if source_filter`) to decide whether to apply a Qdrant filter. An empty string `""`
is falsy in Python, so `source_filter=""` silently skips the filter. This is intentional
per `test_stream_answer_empty_string_filter_treated_as_falsy`, but the `ChatRequest` model
in `chat.py` declares `source_filter: str | None` with no `min_length` constraint. A
client can POST `{"source_filter": ""}` and receive results from all sources, which is
indistinguishable from `source_filter=null` — the client cannot detect that its filter was
ignored. The frontend never sends `""` (it sends `null` for "All Sources"), so this is not
a live bug today, but the missing validation allows the confusion to persist and the
contract is undocumented.

**Fix:** Add `min_length=1` to the `source_filter` field, making the empty-string case an
explicit HTTP 422:
```python
source_filter: str | None = Field(default=None, min_length=1)
```
If the empty-string passthrough behavior is intentional, document it explicitly in the
field description.

### WR-04: `sources.py` swallows the exception entirely — no logging before re-raising as 500

**File:** `backend/app/api/sources.py:24-28`

**Issue:** The bare `except Exception:` block discards the original exception entirely
before raising `HTTPException`. There is no `logger.error(...)` or `logger.exception(...)`
call, so when Qdrant is unreachable or returns an unexpected payload, the only observable
signal is the HTTP 500 response to the client. The root cause is invisible in server logs,
making operational debugging very difficult.

**Fix:**
```python
import logging
logger = logging.getLogger(__name__)

@router.get("/sources")
async def list_sources(
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        sources = await rag.get_distinct_sources()
        return {"sources": sources}
    except Exception:
        logger.exception("Failed to retrieve source list from Qdrant")
        raise HTTPException(status_code=500, detail="Failed to retrieve source list")
```

### WR-05: Topic Filter UI is a fully interactive affordance that is never forwarded to the backend

**File:** `frontend/src/pages/AskAssistantScreen.tsx:122-138` and `frontend/src/pages/AskAssistantScreen.tsx:51-54`

**Issue:** The sidebar renders a functional-looking "Topic Filter" section with six
clickable buttons. `topicFilter` state is updated correctly on click, and it is displayed
in the header breadcrumb (line 149). However, `topicFilter` is never passed to `submit()`,
never included in the POST body, and the backend has no `topic_filter` parameter on any
endpoint. The filter is entirely cosmetic. Users who click "Data Retention" or
"User Rights" will receive exactly the same results as clicking "All Topics" — with no
indication that the filter had no effect. This is a misleading affordance.

**Fix (short-term):** Remove the Topic Filter section from the UI until backend support
exists, or add a visible "coming soon" label to set user expectation.

**Fix (long-term):** Implement topic-filter support in the backend (e.g., a `topic_filter`
field on `ChatRequest` that adds topic keywords to the LLM prompt or a Qdrant payload
filter on a `topic` field).

### WR-06: `isStreaming` closure stale-read risk in `submit` callback

**File:** `frontend/src/hooks/useSSEChat.ts:69-179`

**Issue:** The `submit` callback is memoized with `useCallback([messages, isStreaming])`.
The `isStreaming` guard on line 71 (`if (isStreaming) return`) reads from the closure. If
`isStreaming` transitions to `true` between the time a component renders and the time the
user's click is processed (e.g., rapid double-click before React re-renders), the check
executes against the stale `false` value and two concurrent submits are initiated. While
the `messages` dependency means the callback is recreated on every new message (which
partially mitigates this), the race is still possible within a single render cycle.

**Fix:** Use a `ref` to guard concurrent submits instead of (or in addition to) the state
value, since refs are synchronous and not subject to render-cycle staleness:
```typescript
const isStreamingRef = useRef(false);

const submit = useCallback(async (...) => {
  if (isStreamingRef.current) return;
  isStreamingRef.current = true;
  setIsStreaming(true);
  try {
    // ...
  } finally {
    isStreamingRef.current = false;
    setIsStreaming(false);
  }
}, [messages]); // remove isStreaming from deps
```

---

## Info

### IN-01: `Citation` Pydantic model in `chat.py` does not include `score` field

**File:** `backend/app/api/chat.py:66-74`

**Issue:** The `Citation` Pydantic model is used only for docstring/documentation purposes
(the actual response is a `StreamingResponse`, so FastAPI never validates it), but it is
out of sync with the actual citation dict shape produced by `rag._build_verified_citations`
which now includes a `score` field. Any developer using `Citation` as a reference will
have an incomplete picture.

**Fix:** Add `score: float` to the `Citation` model to keep it in sync with the actual
runtime shape.

### IN-02: `_fake_stream` helper is duplicated between `test_rag.py` and `test_rag_phase9.py`

**File:** `backend/app/tests/test_rag.py:31-41` and `backend/app/tests/test_rag_phase9.py:23-32`

**Issue:** The `_fake_stream` async generator is copy-pasted verbatim into both test files.
If the token simulation logic needs to change, both copies must be updated in sync.

**Fix:** Move `_fake_stream` to `conftest.py` as a module-level function or pytest fixture
so both test files share a single definition.

### IN-03: `_stub_current_user` is duplicated between `test_chat_endpoint.py` and `test_sources_endpoint.py`

**File:** `backend/app/tests/test_chat_endpoint.py:25-27` and `backend/app/tests/test_sources_endpoint.py:19-21`

**Issue:** Same pattern as IN-02 — the `_stub_current_user` helper is duplicated across
two test files. Move to `conftest.py` to eliminate duplication.

### IN-04: Evidence panel always shows `activeFilter` label regardless of which message's citations are displayed

**File:** `frontend/src/pages/AskAssistantScreen.tsx:265-268`

**Issue:** Each citation card in the right evidence panel renders the current
`activeFilter` value as the source label (line 267), not the citation's actual `c.title`.
This means if a user changes the active filter after a query, all evidence cards will
display the new filter name rather than the document the citation actually came from.
The `c.title` field is already available on each citation object.

**Fix:** Replace:
```tsx
{activeFilter.replace(" Privacy Policy", "").replace(" Privacy Statement", "")}
```
with:
```tsx
{c.title.replace(" Privacy Policy", "").replace(" Privacy Statement", "")}
```

---

_Reviewed: 2026-05-13T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

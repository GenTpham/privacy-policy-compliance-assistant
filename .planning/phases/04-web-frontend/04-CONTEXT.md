# Phase 4: Web Frontend — Context

**Gathered:** 2026-04-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a React SPA (Vite + Tailwind) that: gates access behind a login page, streams chat responses token-by-token from the FastAPI SSE endpoint, renders expandable citation cards under each assistant message, shows a clear "no matching policy" message when retrieval yields no results, and lets the user log out cleanly. Phase complete when all 5 browser-level success criteria from ROADMAP.md pass.

**Does NOT include:** Cross-document conflict detection UI (Phase 5), Docker Compose wiring of the frontend container (Phase 6), user registration, social login, file upload, or multi-language UI labels.

</domain>

<decisions>
## Implementation Decisions

### Layout
- **D-01:** Single-column, full-width layout. Messages stack vertically; citation cards appear inline below each assistant answer. No sidebar. Aligns with ROADMAP spec ("scrollable message history panel" + "expandable citation cards below the answer text").
- **D-02:** Clean & minimal visual tone — white/light-gray background, muted accent colors, no branded flourishes. Appropriate for a compliance research tool.

### Streaming Response UX
- **D-03:** While the LLM is streaming, display a **blinking `|` cursor** appended to the end of the growing text. Clear in-progress signal without heavy loading states.
- **D-04:** Citation cards appear **after the `done` event fires, with a fade-in animation**. They are never shown mid-stream (citations only exist in the `done` payload, not `delta` events). This avoids layout jumps while the response is still streaming.

### Citation Cards
- **D-05:** All citation cards start **collapsed** by default. User clicks to expand.
- **D-06:** A collapsed card shows: **document title + excerpt preview** (~50 chars of verbatim text). Example: "📄 Google Privacy Policy — 'Users may request deletion of their personal...'" — enough to judge relevance before expanding.
- **D-07:** Expanded state shows the full verbatim excerpt from the `citations[N].text` field.

### Session & Token Handling
- **D-08:** Tokens stored in **`localStorage`** — access token and refresh token persist across page refreshes. Acceptable for an internal compliance tool (not a public consumer app).
- **D-09:** On HTTP 401 from `/api/chat`, perform a **silent refresh**: call `POST /auth/refresh` with the stored refresh token, update `localStorage` with the new access token, then retry the original request transparently. The user's conversation is never interrupted.
- **D-10:** If the refresh call itself returns 401 (refresh token expired or invalid), clear both tokens from `localStorage` and redirect to `/login`. This is the only forced logout path (besides the explicit logout button).
- **D-11:** On logout button click, call `POST /auth/logout`, clear both tokens from `localStorage`, and navigate to `/login`. The auth header is not sent after logout — the backend returns 401 on subsequent `/api/chat` calls (verifying UI-06).

### Routing
- **D-12:** Two routes: `/login` and `/chat` (or `/`). An unauthenticated visit to `/chat` redirects to `/login`. After successful login, redirect to `/chat`.

### Component Library
- **D-13:** Use **shadcn/ui** components built on Radix UI primitives for accessible UI elements (input, button, card, collapsible for citation cards). Tailwind CSS for styling. No custom CSS framework.

### Claude's Discretion
- Exact Tailwind color palette and spacing — executor chooses a clean, accessible scheme.
- Whether to use React Query, SWR, or plain `fetch` for the auth calls (non-streaming endpoints).
- SSE parsing implementation — native `EventSource` vs `fetch` with `ReadableStream` (executor decides based on auth header requirements; `EventSource` does not support custom headers, so `fetch`+`ReadableStream` is likely needed).
- Exact animation timing for citation card fade-in.
- Error state design for network failures mid-stream.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §Web Interface (UI-01–UI-06)
- `.planning/REQUIREMENTS.md` §Citations (CITE-04)

### Backend API Contract (must match exactly)
- `.planning/phases/02-core-rag-pipeline/02-CONTEXT.md` — D-01 through D-08: `POST /chat` SSE format, event types (`delta`/`done`), citation payload shape `{id, title, text}`, "no matching policy" response shape
- `.planning/phases/03-authentication/03-CONTEXT.md` — D-05 through D-11: login/refresh/logout endpoint formats, token shapes, logout semantics

### Existing Backend Files (read to understand integration points)
- `backend/app/api/chat.py` — chat endpoint, SSE event format
- `backend/app/api/auth.py` — auth router: POST /auth/login, /auth/refresh, /auth/logout
- `backend/app/core/config.py` — Settings (jwt_secret, access_token_expire_minutes=30, refresh_token_expire_days=7)

### Stack Reference
- `CLAUDE.md` §Technology Stack — React (Vite) + Tailwind, shadcn/ui, nginx for Docker static serve, JWT token storage pattern

No external ADRs — all decisions captured above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- No existing frontend code — this is a greenfield React app.
- `backend/app/api/auth.py` — auth router to integrate against. Endpoints: `POST /auth/login` (JSON → `{access_token, refresh_token, token_type}`), `POST /auth/refresh` (JSON `{refresh_token}` → `{access_token, token_type}`), `POST /auth/logout` (no body → `{}`).
- `backend/app/api/chat.py` — `POST /api/chat` with `Authorization: Bearer <token>` header, body `{message, history}`, returns SSE stream.

### Established Patterns (backend, for API integration)
- All auth endpoints return JSON — use `fetch` with `Content-Type: application/json`.
- Chat endpoint uses SSE — use `fetch` + `ReadableStream` (not `EventSource`) because a custom `Authorization` header is required.
- Conversation history shape: `[{role: "user"|"assistant", content: str}]` — client owns and sends this on every request (D-09, Phase 2).

### Integration Points
- `/api/chat` — POST with `Authorization: Bearer <access_token>`. Body: `{message: str, history: [...]}`. Returns SSE.
- `/auth/login` — POST with JSON body. Returns tokens on success, 401 on failure.
- `/auth/refresh` — POST with `{refresh_token}`. Returns new access token.
- `/auth/logout` — POST (no body). Stateless — just clear localStorage client-side.
- Backend runs on port 8000 locally; frontend proxies `/api` and `/auth` via Vite dev proxy config.

</code_context>

<specifics>
## Specific Ideas

- The `EventSource` API cannot send custom headers — the `Authorization: Bearer` header required by `/api/chat` means the SSE stream **must** be consumed via `fetch` + `ReadableStream`, not `EventSource`. Executor must implement a custom SSE parser over the fetch response body.
- The blinking cursor (D-03) should stop once the `done` event fires and the full answer text replaces the streaming buffer.
- Citation fade-in (D-04): a simple CSS `opacity 0→1` transition over ~200ms is sufficient — no complex animation needed.
- Collapsed citation card preview (D-06): truncate `citations[N].text` at ~50 characters with an ellipsis. Show the document `title` as the primary label.
- Silent refresh (D-09): implement as an `axios` interceptor or a `fetch` wrapper that catches 401, attempts refresh once, and retries. Must not create infinite loops — track "already-retried" state.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-web-frontend*
*Context gathered: 2026-04-27*

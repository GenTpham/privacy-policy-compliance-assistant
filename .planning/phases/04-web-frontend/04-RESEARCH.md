# Phase 4: Web Frontend — Research

**Researched:** 2026-04-27
**Domain:** React SPA with Vite, Tailwind CSS, shadcn/ui, fetch-based SSE, JWT auth
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Single-column, full-width layout. Messages stack vertically; citation cards appear inline below each assistant answer. No sidebar.
- **D-02:** Clean & minimal visual tone — white/light-gray background, muted accent colors, no branded flourishes.
- **D-03:** While the LLM is streaming, display a **blinking `|` cursor** appended to the end of the growing text.
- **D-04:** Citation cards appear **after the `done` event fires, with a fade-in animation**. Never shown mid-stream.
- **D-05:** All citation cards start **collapsed** by default.
- **D-06:** Collapsed card shows: document title + ~50-char excerpt preview.
- **D-07:** Expanded state shows the full verbatim excerpt from `citations[N].text`.
- **D-08:** Tokens stored in **`localStorage`** — access token and refresh token persist across page refreshes.
- **D-09:** On HTTP 401 from `/api/chat`, perform a **silent refresh**: call `POST /auth/refresh`, update `localStorage`, retry the original request.
- **D-10:** If refresh call itself returns 401, clear both tokens and redirect to `/login`.
- **D-11:** On logout button click, call `POST /auth/logout`, clear both tokens, navigate to `/login`.
- **D-12:** Two routes: `/login` and `/chat` (or `/`). Unauthenticated visit to `/chat` redirects to `/login`.
- **D-13:** Use **shadcn/ui** + Radix UI + Tailwind CSS. No custom CSS framework.

### Claude's Discretion

- Exact Tailwind color palette and spacing (constrained by UI-SPEC.md)
- Whether to use React Query, SWR, or plain `fetch` for auth calls (UI-SPEC.md locks: plain `fetch` — keep dependencies minimal)
- SSE parsing implementation — **`fetch` + `ReadableStream` is required** (EventSource cannot send Authorization header)
- Exact animation timing for citation card fade-in (UI-SPEC.md locks: 200ms ease-out)
- Error state design for network failures mid-stream

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | User redirected to login when unauthenticated; after login, redirected to chat | React Router v6 `ProtectedRoute` wrapper + `Navigate` component; `localStorage` token check |
| UI-02 | Chat interface has text input and scrollable message history panel | ChatInput + MessageList components; CSS `overflow-y: auto` on message list; `flex` layout |
| UI-03 | LLM response tokens appear progressively as they stream | `fetch` + `ReadableStream` SSE parser; streaming state in React; blinking cursor via CSS |
| UI-04 | Each assistant message shows expandable citation cards with title and verbatim excerpt | shadcn `Collapsible` + `Card`; Radix accessible by default; fade-in via CSS transition |
| UI-05 | "No matching policy found" message when no relevant policy found | Detect `done` event with `citations: []` and specific answer text; render `NoMatchMessage` |
| UI-06 | User can log out; session cleared, returned to login | `POST /auth/logout` + clear `localStorage` + React Router `navigate('/login')` |
| CITE-04 | Frontend displays each citation as expandable inline panel with title and verbatim excerpt | shadcn `Collapsible` component; citation data from `done` SSE event payload |

</phase_requirements>

---

## Summary

Phase 4 is a greenfield React SPA consuming a FastAPI backend that is already complete through Phase 3. The backend exposes three integration points: `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout` (all JSON), and `POST /api/chat` (SSE stream). The frontend must gate access behind a login page, stream tokens progressively, render expandable citation cards, and handle token refresh silently.

The stack is fully locked: React 19 + Vite 8 + Tailwind 4 + shadcn/ui (new-york style) + React Router v6. All packages are current (versions confirmed against npm registry 2026-04-27). The UI design contract in `04-UI-SPEC.md` is signed off and provides exact color values, spacing, typography, component file structure, and copy. This research focuses on the non-obvious implementation patterns: custom SSE parsing over `fetch`, the silent-refresh interceptor pattern, React Router v6 protected routes, and shadcn/ui initialization order.

The only open area of discretion is error handling for network failures mid-stream (not specified in UI-SPEC). All other decisions are locked and well-supported by verified documentation.

**Primary recommendation:** Initialize shadcn/ui in Wave 0 before writing any component code. Use `fetch` + `ReadableStream` for SSE. Implement silent refresh as a wrapper function, not a global interceptor, to avoid complexity.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Auth token storage | Browser / Client | — | localStorage is browser-tier; no server state for JWT in this design |
| Route guard (ProtectedRoute) | Browser / Client | — | Reads localStorage; redirects before render — pure client logic |
| SSE stream parsing | Browser / Client | — | `fetch` + `ReadableStream` runs in browser; server owns the SSE format |
| Citation card expand/collapse | Browser / Client | — | Pure UI interaction state; no server call needed |
| Streaming cursor blink | Browser / Client | — | CSS animation; no React state needed beyond "is streaming" flag |
| Silent token refresh | Browser / Client | API / Backend | Client intercepts 401 and calls `/auth/refresh`; backend issues new token |
| Message history management | Browser / Client | — | Client owns conversation history; sends full history on every POST |
| Login form validation | Browser / Client | API / Backend | Client validates non-empty; backend enforces credential correctness |
| "No matching policy" detection | Browser / Client | — | Detected from `done` event payload (`citations: []`); no separate endpoint |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react | 19.2.5 | UI rendering | Locked in CLAUDE.md; current stable |
| react-dom | 19.2.5 | DOM renderer | Paired with react |
| vite | 8.0.10 | Build tool + dev server | Locked in CLAUDE.md; provides dev proxy for `/api` and `/auth` |
| typescript | 6.0.3 | Type safety | Standard for production React; shadcn/ui generates TypeScript |
| tailwindcss | 4.2.4 | Utility CSS | Locked in CLAUDE.md |
| react-router-dom | 7.14.2 | Client-side routing | Standard React routing; v6 API used throughout UI-SPEC |
| lucide-react | 1.11.0 | Icon library | Bundled with shadcn/ui; FileText, ChevronDown, AlertCircle icons needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @radix-ui/react-collapsible | 1.1.12 | Citation card accordion | Installed via `npx shadcn@latest add collapsible` |
| class-variance-authority | 0.7.1 | shadcn variant helper | Installed automatically with shadcn init |
| clsx | 2.1.1 | Conditional classnames | Installed automatically with shadcn init |
| tailwind-merge | 3.5.0 | Merge Tailwind classes | Installed automatically with shadcn init |
| tailwindcss-animate | 1.0.7 | CSS keyframe animations | Used by shadcn; provides `animate-pulse` for cursor blink |
| autoprefixer | 10.5.0 | PostCSS vendor prefixes | Standard Vite+Tailwind setup |
| postcss | 8.5.12 | CSS processing | Required by Tailwind |
| @vitejs/plugin-react | 6.0.1 | Vite React transform | Required for JSX/TSX in Vite |
| @types/react | 19.2.14 | React TypeScript types | Paired with react 19 |

### Test Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| vitest | 4.1.5 | Unit test runner | Vite-native; replaces Jest for this stack |
| @testing-library/react | 16.3.2 | React component tests | Standard for Testing Library approach |
| @testing-library/user-event | 14.6.1 | Simulate user interactions | Form submit, click, keyboard events |
| @testing-library/jest-dom | 6.9.1 | DOM matchers for vitest | `.toBeInTheDocument()`, `.toHaveValue()` |
| happy-dom | 20.9.0 | jsdom-compatible environment | Faster than jsdom; Vite-native; configure via `vitest.config.ts` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| plain `fetch` | axios | axios adds interceptor convenience but is 40KB extra; UI-SPEC.md explicitly requires plain fetch |
| plain `fetch` | React Query | RQ adds caching/retry/mutation DX; overkill for 3 auth endpoints; UI-SPEC.md rejects it |
| `EventSource` | `fetch` + `ReadableStream` | EventSource cannot send Authorization header — **blocked by auth requirement** |
| React Router v6 | TanStack Router | TanStack Router is newer but shadcn/ui examples and community patterns are RR v6 |
| vitest | Jest | Jest requires babel transform; vitest is Vite-native, faster, zero config |

**Installation (greenfield):**
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install react-router-dom lucide-react
npm install -D tailwindcss @tailwindcss/vite postcss autoprefixer
npm install -D vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom happy-dom
npx shadcn@latest init   # new-york style, neutral base, CSS variables
npx shadcn@latest add button input card collapsible form label separator
```

**Version verification:** All versions confirmed via `npm view <package> version` on 2026-04-27. [VERIFIED: npm registry]

---

## Architecture Patterns

### System Architecture Diagram

```
Browser
  │
  ├─── /login  ──► LoginPage ──► useAuth.login() ──► POST /auth/login ──► {access_token, refresh_token}
  │                                                                             │
  │                                                                    localStorage.setItem(tokens)
  │                                                                             │
  └─── / ──► ProtectedRoute ──► (token absent?) ──► Navigate to /login
                │
                └─► ChatPage
                      │
                      ├─── Header (title + logout button)
                      │         └──► useAuth.logout() ──► POST /auth/logout ──► clear localStorage
                      │
                      ├─── MessageList (overflow-y: auto)
                      │         └── MessageBubble (user | assistant)
                      │                   └── CitationCard[] (Collapsible, after done event)
                      │
                      └─── ChatInput (text + Send)
                                └──► useSSEChat.submit()
                                          │
                                          ├─► fetch POST /api/chat (Authorization: Bearer token)
                                          │         │
                                          │   SSE stream (ReadableStream)
                                          │         ├── delta event ──► append token to streamingBuffer
                                          │         ├── done event  ──► set finalAnswer + citations (fade in)
                                          │         └── error event ──► show inline error message
                                          │
                                          └─► 401 response ──► useAuth.refresh()
                                                                    ├── POST /auth/refresh ──► new access_token
                                                                    │         └──► retry original request (once)
                                                                    └── refresh 401 ──► clear localStorage ──► /login
```

### Recommended Project Structure
```
frontend/
  src/
    components/
      auth/
        LoginForm.tsx          # Login form with validation states
      chat/
        ChatPage.tsx           # Main chat layout — composes sub-components
        MessageList.tsx        # Scrollable message history (overflow-y auto)
        MessageBubble.tsx      # User + assistant bubble variants
        ChatInput.tsx          # Text input + Send button row (52px height)
        CitationCard.tsx       # Collapsible citation card (shadcn Collapsible)
        StreamingCursor.tsx    # Blinking | cursor (CSS animate-pulse)
        NoMatchMessage.tsx     # "No matching policy found" inline state
      layout/
        Header.tsx             # Fixed top bar (56px): title + Log out button
        ProtectedRoute.tsx     # Checks localStorage, renders Navigate or children
    hooks/
      useAuth.ts               # login(), logout(), refresh(), token state
      useSSEChat.ts            # fetch + ReadableStream SSE parser, 401 intercept
    lib/
      api.ts                   # fetch wrappers for /auth/* endpoints
      tokens.ts                # localStorage read/write/clear helpers
    pages/
      LoginPage.tsx            # Centered card layout (/login)
      ChatPage.tsx             # Chat interface (/ or /chat)
    App.tsx                    # React Router routes
    main.tsx                   # Vite entry point
  vite.config.ts               # Dev proxy: /api + /auth → http://localhost:8000
  tailwind.config.ts
  components.json              # Created by `npx shadcn@latest init`
  index.html
  vitest.config.ts             # happy-dom environment, setupFiles
  src/test/setup.ts            # @testing-library/jest-dom import
```

### Pattern 1: fetch + ReadableStream SSE Parser

**What:** Custom SSE parser over `fetch` response body. Required because `EventSource` does not support custom headers.
**When to use:** Any SSE endpoint that requires an `Authorization: Bearer` header — this is the only approach.

```typescript
// Source: MDN ReadableStream API + CONTEXT.md Specifics section
// hooks/useSSEChat.ts (core pattern)

async function* parseSSEStream(
  response: Response
): AsyncGenerator<Record<string, unknown>> {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE spec: events are separated by double newlines
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? ""; // keep incomplete last chunk

    for (const event of events) {
      for (const line of event.split("\n")) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6).trim();
          if (data) yield JSON.parse(data);
        }
      }
    }
  }
}
```

**Backend event contract (from `backend/app/api/chat.py`):**
```typescript
// SSE event types — must match backend exactly
type SSEEvent =
  | { type: "delta"; content: string }
  | { type: "done"; answer: string; citations: Citation[] }
  | { type: "error"; message: string };  // note: field is "message" not "detail"

// Citation shape from backend/app/api/chat.py Citation model
interface Citation {
  id: number;       // 1-based position in retrieved set
  qdrant_id: string; // Qdrant point UUID
  title: string;
  text: string;
}
```

### Pattern 2: Silent Refresh as Fetch Wrapper

**What:** A `fetchWithAuth` wrapper that catches 401, attempts one refresh, retries, then redirects on second 401.
**When to use:** All authenticated API calls (`/api/chat`). Auth endpoints (`/auth/*`) do NOT go through this wrapper.

```typescript
// Source: CONTEXT.md D-09, D-10
// lib/api.ts

let isRefreshing = false; // prevent concurrent refresh storms

export async function fetchWithAuth(
  url: string,
  options: RequestInit,
  onUnauthorized: () => void  // callback to clear localStorage + navigate
): Promise<Response> {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${localStorage.getItem("access_token")}`,
    },
  });

  if (response.status !== 401) return response;
  if (isRefreshing) { onUnauthorized(); throw new Error("Already refreshing"); }

  isRefreshing = true;
  try {
    const refreshResp = await fetch("/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: localStorage.getItem("refresh_token") }),
    });
    if (!refreshResp.ok) { onUnauthorized(); throw new Error("Refresh failed"); }
    const { access_token } = await refreshResp.json();
    localStorage.setItem("access_token", access_token);
  } finally {
    isRefreshing = false;
  }

  // Retry original request once with new token
  return fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${localStorage.getItem("access_token")}`,
    },
  });
}
```

**IMPORTANT:** SSE streaming is initiated via `fetch`. The 401 check must happen on the initial response (before reading the body). Once the SSE stream has started (HTTP 200 received), mid-stream errors arrive as `{type: "error"}` events — they cannot be caught as HTTP 401.

### Pattern 3: React Router v6 Protected Route

**What:** A wrapper component that checks for a token and redirects unauthenticated users.
**When to use:** Wrap all authenticated routes.

```typescript
// Source: React Router v6 docs — [VERIFIED: reactrouter.com]
// components/layout/ProtectedRoute.tsx

import { Navigate } from "react-router-dom";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem("access_token");
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

// App.tsx route config
<Routes>
  <Route path="/login" element={<LoginPage />} />
  <Route
    path="/"
    element={
      <ProtectedRoute>
        <ChatPage />
      </ProtectedRoute>
    }
  />
</Routes>
```

### Pattern 4: Citation Card with shadcn Collapsible

**What:** Collapsible citation card using Radix-based shadcn component. Keyboard accessible by default.
**When to use:** Each entry in the `citations` array from the `done` event.

```typescript
// Source: shadcn/ui collapsible docs — [CITED: ui.shadcn.com/docs/components/collapsible]
// components/chat/CitationCard.tsx (pattern)

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronDown, FileText } from "lucide-react";

// Collapsed preview: truncate text at ~50 chars
const preview = text.length > 50 ? text.slice(0, 50) + "…" : text;

// CSS for chevron rotation on open:
// data-[state=open]:rotate-180 transition-transform duration-150
```

### Pattern 5: Streaming Cursor

**What:** A blinking `|` appended to the streaming text buffer via CSS animation.
**When to use:** While `isStreaming === true`; remove when `done` event fires.

```typescript
// Source: UI-SPEC.md Animation Contract + Tailwind animate-pulse
// components/chat/StreamingCursor.tsx

export function StreamingCursor() {
  // animate-pulse provides opacity oscillation at 1s interval (matches D-03)
  return <span className="animate-pulse text-zinc-950 font-normal">|</span>;
}

// Usage in MessageBubble:
// {isStreaming && <StreamingCursor />}
```

### Pattern 6: Vite Dev Proxy

**What:** Proxy `/api` and `/auth` paths to `http://localhost:8000` during development. Avoids CORS issues.
**When to use:** Required — backend is on port 8000, frontend dev server on port 5173.

```typescript
// Source: Vite docs — [CITED: vite.dev/config/server-options#server-proxy]
// vite.config.ts

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": "/src" },  // matches shadcn/ui path alias convention
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/auth": "http://localhost:8000",
    },
  },
});
```

### Anti-Patterns to Avoid

- **Using `EventSource` for `/api/chat`:** EventSource does not support custom headers. The `Authorization: Bearer` header is required. Using EventSource will result in a 401 from the backend that cannot be retried.
- **Showing citation cards during streaming:** Citation data only exists in the `done` event payload. Attempting to render them from `delta` events will find no data. Always gate citation render on `done`.
- **Calling `POST /auth/logout` without a Bearer token:** The logout endpoint in `auth.py` accepts requests without a token (it returns `{}` unconditionally), but the auth router may have a dependency. Safe approach: always send the Bearer header on logout, but do not wait for 401 — clear localStorage regardless of response status.
- **Infinite refresh loop:** If `fetchWithAuth` is called inside the refresh logic itself, a 401 from `/auth/refresh` will recurse infinitely. Track `isRefreshing` flag and throw (triggering `onUnauthorized`) if already refreshing.
- **Modifying conversation history on the server:** The backend is stateless — the client sends `history` on every request. Never try to fetch history from the backend; own it in React state.
- **Parsing SSE with `response.text()`:** This buffers the entire response before parsing. Use `ReadableStream` to get tokens progressively.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Accessible expand/collapse | Custom div with onClick toggle | shadcn `Collapsible` (Radix) | Keyboard navigation, aria-expanded, focus management — 20+ edge cases |
| Form field validation | Custom input state machine | shadcn `Form` (React Hook Form) | Handles error display, touched state, async validation — battle-tested |
| Classname conditional merging | Manual string concatenation | `cn()` helper (`clsx` + `tailwind-merge`) | Handles Tailwind class conflicts (e.g., `text-sm text-base` → keeps `text-base`) |
| CSS transitions | Manual JS animation | Tailwind `transition`, `animate-pulse`, `duration-*` | GPU-accelerated; declarative; no requestAnimationFrame |
| SVG icons | Custom SVG markup | `lucide-react` | Tree-shakeable; consistent 24px grid; named exports |
| Route protection | Manual `useEffect` redirect | React Router `<Navigate replace />` | Synchronous — prevents flash of unprotected content |

**Key insight:** shadcn/ui components are code-owned (copied into the project), not a black-box dependency. The executor can inspect and modify them if needed, but should not rewrite from scratch.

---

## Common Pitfalls

### Pitfall 1: shadcn Initialization Must Come First
**What goes wrong:** Writing component code that imports from `@/components/ui/*` before running `npx shadcn@latest init`. All imports fail; TypeScript LSP reports missing modules.
**Why it happens:** shadcn generates components locally — they don't exist until `init` and `add` are run.
**How to avoid:** Wave 0 task must run `npx shadcn@latest init` and `npx shadcn@latest add [components]` before any component code is written. Verify `frontend/components.json` exists.
**Warning signs:** `Cannot find module '@/components/ui/button'` TypeScript error.

### Pitfall 2: SSE Buffer Fragmentation
**What goes wrong:** A single SSE event arrives split across multiple `ReadableStream` chunks. Naively parsing each chunk as a complete event misses events or parses partial JSON.
**Why it happens:** Network packets don't align with SSE event boundaries.
**How to avoid:** Maintain a `buffer` string; split on `"\n\n"` (double newline = SSE event boundary); keep the last (potentially incomplete) fragment in the buffer for the next chunk.
**Warning signs:** `JSON.parse` throws on partial data; some tokens silently dropped.

### Pitfall 3: React Router v6 API Changes
**What goes wrong:** Using `useHistory()` or `<Switch>` from React Router v5 — these don't exist in v6/v7. The installed version is `react-router-dom@7.14.2`.
**Why it happens:** Search results and training data often show v5 examples.
**How to avoid:** Use `useNavigate()` (not `useHistory`), `<Routes>` (not `<Switch>`), `<Route element={...}>` (not `<Route component={...}>`).
**Warning signs:** `useHistory is not a function` or `Switch is not exported` errors.

### Pitfall 4: Tailwind 4 Config Breaking Change
**What goes wrong:** Tailwind 4 changes how the configuration file is structured — `tailwind.config.js` with `content` array is v3 syntax. Tailwind 4 uses a CSS-first configuration via `@import "tailwindcss"` in the main CSS file.
**Why it happens:** Tailwind 4 was released in early 2025; most tutorials still show v3 config.
**How to avoid:** Vite + Tailwind 4 setup uses `@tailwindcss/vite` plugin (confirmed installed: 4.2.4). Follow the Tailwind v4 Vite guide, not the v3 PostCSS guide. `shadcn@latest init` handles this correctly.
**Warning signs:** Tailwind classes not applying despite appearing in HTML; empty `tailwind.config.js`.

### Pitfall 5: `error` Event Field Name
**What goes wrong:** The backend SSE error event shape is `{type: "error", message: "..."}` (field: `message`). The UI-SPEC uses `detail` in one place. Using `event.detail` returns `undefined`.
**Why it happens:** Inconsistency between documentation and implementation.
**How to avoid:** Confirmed from `backend/app/services/rag.py` line 183: `yield {"type": "error", "message": "LLM service temporarily unavailable"}`. Use `event.message` not `event.detail`.
**Warning signs:** Error message displays as `undefined` in the UI.

### Pitfall 6: `animate-pulse` vs Custom Blink
**What goes wrong:** `animate-pulse` in Tailwind applies a `opacity: 0.5` oscillation (for loading skeletons). The blinking cursor needs a `step-end` easing (hard on/off) for a natural cursor feel.
**Why it happens:** `animate-pulse` is the closest built-in, but not identical to a cursor blink.
**How to avoid:** UI-SPEC.md Animation Contract specifies `step-end` easing. Use a custom CSS keyframe in `tailwind.config.ts` or a `@keyframes blink` in the global CSS, not `animate-pulse`.
**Warning signs:** Cursor fades in/out smoothly rather than toggling sharply.

---

## Code Examples

### SSE Hook Structure (useSSEChat.ts)
```typescript
// Conceptual structure — confirmed against CONTEXT.md integration points
// hooks/useSSEChat.ts

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  isNoMatch?: boolean;
}

interface UseSSEChatReturn {
  messages: Message[];
  isStreaming: boolean;
  submit: (message: string) => Promise<void>;
}

// State machine:
// idle → streaming (on submit) → done (on "done" event) → idle
// idle → streaming → error (on "error" event) → idle
```

### Token Storage Helpers (tokens.ts)
```typescript
// lib/tokens.ts
export const tokens = {
  getAccess: () => localStorage.getItem("access_token"),
  getRefresh: () => localStorage.getItem("refresh_token"),
  setAccess: (t: string) => localStorage.setItem("access_token", t),
  setBoth: (access: string, refresh: string) => {
    localStorage.setItem("access_token", access);
    localStorage.setItem("refresh_token", refresh);
  },
  clearAll: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  },
};
```

### "No Matching Policy" Detection
```typescript
// Detect no-match from done event — from backend/app/services/rag.py line 154-158
// done event with citations:[] and specific answer text signals no retrieval result
// UI should check for citations.length === 0 as the reliable signal (answer text may vary)

const isNoMatch = event.citations.length === 0;
```

### Collapsible Chat Input (Enter key submit)
```typescript
// ChatInput should submit on Enter (not Shift+Enter)
// Matches ACCESSIBILITY CONTRACT: "submit on Enter in chat input"
const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    onSubmit();
  }
};
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| CRA (Create React App) | Vite | 2022-2023 | CRA is unmaintained; Vite is the standard |
| React Router v5 (`Switch`, `useHistory`) | React Router v6/v7 (`Routes`, `useNavigate`) | 2021 (v6), 2024 (v7) | Different component API — v5 code does not compile on v7 |
| passlib + bcrypt | pwdlib[argon2] | 2024 (backend — already adopted) | Frontend unaffected — auth backend already uses pwdlib |
| `EventSource` for auth-gated SSE | `fetch` + `ReadableStream` | Always — EventSource never supported custom headers | Required for this project's auth-gated SSE endpoint |
| Tailwind v3 PostCSS config | Tailwind v4 CSS-first config | 2025 | `tailwind.config.js` with `content` array is v3 only |
| Jest + Babel | vitest | 2022+ | vitest is Vite-native; zero config for Vite projects |
| jsdom | happy-dom | 2023+ | happy-dom is 10-15x faster for component tests |

**Deprecated/outdated:**
- `Create React App`: Unmaintained since 2022. Do not use.
- `React Router useHistory()`: Removed in v6. Use `useNavigate()`.
- `EventSource` for auth-gated SSE: Cannot send Authorization header. Use `fetch` + `ReadableStream`.
- Tailwind v3 `tailwind.config.js` with `content` array: v4 uses `@tailwindcss/vite` plugin and CSS imports.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `no-match` detection should use `citations.length === 0` as the reliable signal | Code Examples | If backend sends empty citations for valid answers, false-positive no-match UI; check backend behavior at integration time |
| A2 | React Router v7.14.2 retains v6 API (`Routes`, `useNavigate`, `Navigate`) | Standard Stack / Patterns | If v7 introduced breaking changes, route code would fail; [ASSUMED] based on React Router changelog knowledge |
| A3 | Tailwind 4 + `@tailwindcss/vite` + shadcn v4 are compatible without manual PostCSS config | Standard Stack | If shadcn generates a PostCSS config that conflicts with vite plugin, setup would fail; `shadcn@latest init` should handle |

---

## Open Questions

1. **"No match" detection signal**
   - What we know: Backend yields `{type: "done", answer: "No matching policy found for your question.", citations: []}` when no chunks exceed threshold (rag.py line 154)
   - What's unclear: Should the frontend detect no-match by `citations.length === 0`, by matching the answer string, or both?
   - Recommendation: Use `citations.length === 0` as primary signal (robust to answer text changes). Optionally also check if answer contains "No matching policy" as secondary confirmation.

2. **Conversation history scroll behavior**
   - What we know: UI-SPEC says "scroll-to-bottom on new message"
   - What's unclear: Should auto-scroll be disabled if the user has manually scrolled up?
   - Recommendation: Use `useRef` + `useEffect` to scroll to bottom on message append. If user scroll-interrupt tracking is needed, add it as a future enhancement — keep Wave 0 simple.

3. **Empty chat initial state**
   - What we know: UI-SPEC copywriting contract specifies "Ask a policy question" heading and example prompt text
   - What's unclear: Should the empty state be a separate component or inline in MessageList?
   - Recommendation: Inline in MessageList when `messages.length === 0` — no separate component needed.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Vite, npm, shadcn CLI | ✓ | v24.11.0 | — |
| npm | Package install | ✓ | 11.12.1 | — |
| npx | shadcn CLI (`npx shadcn@latest init`) | ✓ | bundled with npm 11 | — |
| Backend (port 8000) | Vite dev proxy, integration tests | ✗ (Phase 3 pending) | — | Mock in unit tests; use wiremock/msw for integration |

**Missing dependencies with no fallback:** None — all build tools available.

**Missing dependencies with fallback:**
- Backend (port 8000): Not running (Phase 3 pending execution). Frontend unit tests must mock all fetch calls via `vi.stubGlobal('fetch', ...)` or MSW. Integration testing deferred to Phase 6.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | vitest 4.1.5 |
| Config file | `frontend/vitest.config.ts` (Wave 0 creates this) |
| Quick run command | `cd frontend && npm run test -- --run` |
| Full suite command | `cd frontend && npm run test -- --run --coverage` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | Unauthenticated visit to `/` renders `Navigate` to `/login` | unit | `vitest run src/components/layout/ProtectedRoute.test.tsx` | ❌ Wave 0 |
| UI-01 | Authenticated visit to `/login` redirects to `/chat` | unit | included in LoginPage tests | ❌ Wave 0 |
| UI-02 | ChatPage renders message list + input field | unit | `vitest run src/components/chat/ChatPage.test.tsx` | ❌ Wave 0 |
| UI-03 | Streaming cursor shown during stream, removed on `done` | unit | `vitest run src/hooks/useSSEChat.test.ts` | ❌ Wave 0 |
| UI-03 | Tokens appended progressively to message | unit | included in useSSEChat tests | ❌ Wave 0 |
| UI-04 | Citation cards render after `done` event, collapsed by default | unit | `vitest run src/components/chat/CitationCard.test.tsx` | ❌ Wave 0 |
| UI-04 | Click expands citation to show full text | unit | included in CitationCard tests | ❌ Wave 0 |
| UI-05 | No-match state renders correct heading and body | unit | `vitest run src/components/chat/NoMatchMessage.test.tsx` | ❌ Wave 0 |
| UI-06 | Logout clears localStorage and navigates to `/login` | unit | `vitest run src/hooks/useAuth.test.ts` | ❌ Wave 0 |
| CITE-04 | Citation card shows document title and verbatim excerpt | unit | included in CitationCard tests | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd frontend && npm run test -- --run`
- **Per wave merge:** `cd frontend && npm run test -- --run --coverage`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `frontend/vitest.config.ts` — test runner config with happy-dom environment
- [ ] `frontend/src/test/setup.ts` — `@testing-library/jest-dom` import
- [ ] `frontend/src/components/layout/ProtectedRoute.test.tsx` — REQ UI-01
- [ ] `frontend/src/components/chat/ChatPage.test.tsx` — REQ UI-02
- [ ] `frontend/src/hooks/useSSEChat.test.ts` — REQ UI-03
- [ ] `frontend/src/components/chat/CitationCard.test.tsx` — REQ UI-04, CITE-04
- [ ] `frontend/src/components/chat/NoMatchMessage.test.tsx` — REQ UI-05
- [ ] `frontend/src/hooks/useAuth.test.ts` — REQ UI-06
- [ ] Framework install: `npm create vite@latest frontend -- --template react-ts` if `frontend/` does not exist

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | JWT stored in localStorage; login form submits to FastAPI `/auth/login` |
| V3 Session Management | yes | Access token 30-min expiry; silent refresh; forced logout on refresh 401 |
| V4 Access Control | yes | ProtectedRoute guard; all `/api/chat` calls require Bearer token |
| V5 Input Validation | yes | ChatRequest.message max_length=4000 enforced server-side; client trims empty messages |
| V6 Cryptography | no | No client-side crypto — tokens are opaque JWTs managed by backend |

### Known Threat Patterns for React SPA + JWT

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XSS reading localStorage tokens | Information Disclosure | CSP headers (Phase 6); sanitize any user-generated content rendered as HTML (no dangerouslySetInnerHTML) |
| CSRF on `/auth/logout` | Tampering | Not applicable — stateless JWT; no server session cookie |
| Token leakage in browser history | Information Disclosure | Never put tokens in URL parameters |
| Prompt injection via history field | Tampering | Server enforces `HistoryItem.role: Literal["user", "assistant"]` — HTTP 422 on "system" role |
| Infinite refresh loop DoS | Denial of Service | `isRefreshing` flag prevents concurrent refresh storms |

**localStorage vs httpOnly cookie note:** D-08 locks token storage to localStorage. This is accepted for an internal compliance tool. The tradeoff (XSS exposure vs. CSRF exposure) is documented and accepted by the user in CONTEXT.md.

---

## Sources

### Primary (HIGH confidence)
- `backend/app/api/chat.py` — SSE event format, Citation model, error event field name verified
- `backend/app/api/auth.py` — auth endpoint shapes, request/response models verified
- `backend/app/services/rag.py` — no-match event shape, error event `message` field verified
- `.planning/phases/04-web-frontend/04-UI-SPEC.md` — full design contract, file structure, API contract
- `.planning/phases/04-web-frontend/04-CONTEXT.md` — locked decisions D-01 through D-13

### Secondary (MEDIUM confidence)
- npm registry (2026-04-27) — all package versions verified via `npm view <package> version`
- [CITED: ui.shadcn.com/docs/components/collapsible] — shadcn Collapsible API
- [CITED: vite.dev/config/server-options#server-proxy] — Vite proxy configuration
- [CITED: reactrouter.com/docs] — React Router v6/v7 API (Routes, Navigate, useNavigate)

### Tertiary (LOW confidence)
- A2 (Assumptions Log): React Router v7 retains v6 API — verify during Wave 0 setup
- A3 (Assumptions Log): Tailwind 4 + shadcn compatibility — verify during `shadcn@latest init`

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions confirmed against npm registry 2026-04-27
- Architecture: HIGH — backend code read directly; integration points fully specified in CONTEXT.md and UI-SPEC.md
- Pitfalls: HIGH for SSE/auth patterns (verified from backend code); MEDIUM for Tailwind 4 compat (version-specific)
- Test architecture: HIGH — vitest is Vite-native standard; test file structure follows component structure

**Research date:** 2026-04-27
**Valid until:** 2026-05-27 (stable stack; packages unlikely to break in 30 days)

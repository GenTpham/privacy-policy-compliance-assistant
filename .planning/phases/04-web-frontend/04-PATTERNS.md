# Phase 4: Web Frontend - Pattern Map

**Mapped:** 2026-04-27
**Files analyzed:** 18 new files
**Analogs found:** 0 exact / 4 role-match (backend) / 14 no analog

---

## Overview

Phase 4 is a greenfield React SPA. No frontend code exists in the repository.
The only existing analogs are backend Python files, which supply integration
contracts (endpoint shapes, SSE event formats, token semantics) rather than
code to copy directly. All patterns below are derived from:

1. Backend source files (read directly) — for API contract fidelity
2. RESEARCH.md code examples — for React/TypeScript patterns (verified against MDN, React Router docs, shadcn docs)
3. UI-SPEC.md — for exact visual and interaction contracts

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `frontend/src/lib/tokens.ts` | utility | — | — | no analog |
| `frontend/src/lib/api.ts` | utility | request-response | `backend/app/api/auth.py` | contract-reference |
| `frontend/src/hooks/useAuth.ts` | hook | request-response | `backend/app/services/auth.py` | contract-reference |
| `frontend/src/hooks/useSSEChat.ts` | hook | streaming | `backend/app/api/chat.py` | contract-reference |
| `frontend/src/components/layout/ProtectedRoute.tsx` | middleware | request-response | — | no analog |
| `frontend/src/components/layout/Header.tsx` | component | — | — | no analog |
| `frontend/src/components/auth/LoginForm.tsx` | component | request-response | — | no analog |
| `frontend/src/pages/LoginPage.tsx` | page | request-response | — | no analog |
| `frontend/src/pages/ChatPage.tsx` | page | streaming | — | no analog |
| `frontend/src/components/chat/ChatPage.tsx` | component | streaming | — | no analog |
| `frontend/src/components/chat/MessageList.tsx` | component | streaming | — | no analog |
| `frontend/src/components/chat/MessageBubble.tsx` | component | streaming | — | no analog |
| `frontend/src/components/chat/ChatInput.tsx` | component | request-response | — | no analog |
| `frontend/src/components/chat/CitationCard.tsx` | component | — | — | no analog |
| `frontend/src/components/chat/StreamingCursor.tsx` | component | — | — | no analog |
| `frontend/src/components/chat/NoMatchMessage.tsx` | component | — | — | no analog |
| `frontend/src/App.tsx` | config | — | — | no analog |
| `frontend/vite.config.ts` | config | — | — | no analog |

---

## Pattern Assignments

### `frontend/src/lib/tokens.ts` (utility)

**Analog:** None — pure localStorage utility, no codebase analog.

**Pattern source:** RESEARCH.md Code Examples section.

**Core pattern:**
```typescript
// frontend/src/lib/tokens.ts
// Single responsibility: all localStorage token I/O goes through this module.
// No logic — just named read/write/clear helpers.
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

**Key constraint:** `localStorage` key names are `"access_token"` and `"refresh_token"` (D-08).
These must be consistent across `tokens.ts`, `useAuth.ts`, and `api.ts`.

---

### `frontend/src/lib/api.ts` (utility, request-response)

**Analog:** `backend/app/api/auth.py` — supplies the exact endpoint shapes and response fields to target.

**Backend contract** (from `backend/app/api/auth.py` lines 36-53, 100-119):
```typescript
// Endpoint shapes to implement against:
// POST /auth/login
//   body: { username: string, password: string }
//   200:  { access_token: string, refresh_token: string, token_type: "bearer" }
//   401:  { detail: "Invalid credentials" }
//
// POST /auth/refresh
//   body: { refresh_token: string }
//   200:  { access_token: string, token_type: "bearer" }
//   401:  { detail: "Invalid or expired token" }
//
// POST /auth/logout
//   body: none (send Authorization: Bearer <token>)
//   200:  {}
```

**fetchWithAuth pattern** (from RESEARCH.md Pattern 2, cross-verified with CONTEXT.md D-09/D-10):
```typescript
// frontend/src/lib/api.ts
// isRefreshing module-level flag prevents concurrent refresh storms (D-10 anti-pattern).
let isRefreshing = false;

export async function fetchWithAuth(
  url: string,
  options: RequestInit,
  onUnauthorized: () => void
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

**Auth endpoints** (no auth header required — these go through plain fetch, not fetchWithAuth):
```typescript
export async function apiLogin(username: string, password: string) {
  return fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
}

export async function apiRefresh(refreshToken: string) {
  return fetch("/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function apiLogout(accessToken: string) {
  // Send bearer header but do NOT use fetchWithAuth (avoid refresh loop on logout)
  return fetch("/auth/logout", {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}
```

---

### `frontend/src/hooks/useAuth.ts` (hook, request-response)

**Analog:** `backend/app/services/auth.py` — contract reference for token semantics.

**Token semantics from backend** (`backend/app/services/auth.py` lines 54-82):
- `access_token`: short-lived (30 min), `type: "access"` claim
- `refresh_token`: long-lived (7 days), `type: "refresh"` claim
- Both are opaque JWTs from the client's perspective

**Core pattern:**
```typescript
// frontend/src/hooks/useAuth.ts
import { useNavigate } from "react-router-dom";
import { tokens } from "../lib/tokens";
import { apiLogin, apiLogout } from "../lib/api";

export function useAuth() {
  const navigate = useNavigate();

  const login = async (username: string, password: string): Promise<void> => {
    const resp = await apiLogin(username, password);
    if (!resp.ok) throw new Error("Invalid credentials");
    const { access_token, refresh_token } = await resp.json();
    tokens.setBoth(access_token, refresh_token);
    navigate("/");
  };

  const logout = async (): Promise<void> => {
    const accessToken = tokens.getAccess();
    if (accessToken) {
      await apiLogout(accessToken).catch(() => {}); // fire-and-forget (D-11)
    }
    tokens.clearAll();
    navigate("/login");
  };

  const forceLogout = (): void => {
    // Called by fetchWithAuth onUnauthorized callback (D-10)
    tokens.clearAll();
    navigate("/login");
  };

  return { login, logout, forceLogout };
}
```

---

### `frontend/src/hooks/useSSEChat.ts` (hook, streaming)

**Analog:** `backend/app/api/chat.py` — supplies the exact SSE event format.

**SSE event contract** (from `backend/app/api/chat.py` lines 68-80):
```typescript
// Must match exactly — field names are hardcoded in backend
type SSEEvent =
  | { type: "delta"; content: string }
  | { type: "done"; answer: string; citations: Citation[] }
  | { type: "error"; message: string };  // field is "message" not "detail" (Pitfall 5)

interface Citation {
  id: number;       // 1-based position in retrieved set
  qdrant_id: string;
  title: string;
  text: string;
}
```

**Request shape** (from `backend/app/api/chat.py` lines 26-43):
```typescript
// POST /api/chat body — must match ChatRequest + HistoryItem Pydantic models
interface ChatRequest {
  message: string;   // min_length=1, max_length=4000
  history: Array<{
    role: "user" | "assistant";  // Literal — "system" causes HTTP 422
    content: string;             // max_length=8000
  }>;
}
```

**SSE parser pattern** (from RESEARCH.md Pattern 1, based on MDN ReadableStream API):
```typescript
// frontend/src/hooks/useSSEChat.ts
// Buffer approach handles SSE fragmentation (Pitfall 2 from RESEARCH.md)
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
    buffer = events.pop() ?? ""; // keep incomplete last chunk in buffer

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

**Hook state machine:**
```typescript
// State: idle → streaming (on submit) → done (on "done" event) → idle
//        idle → streaming → error (on "error" event or network failure) → idle

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  isNoMatch?: boolean;
  isError?: boolean;
}

interface UseSSEChatReturn {
  messages: Message[];
  isStreaming: boolean;
  submit: (message: string) => Promise<void>;
}
```

**No-match detection** (from `backend/app/services/rag.py` line 154, per RESEARCH.md):
```typescript
// Use citations.length === 0 as primary signal (robust to answer text changes)
const isNoMatch = doneEvent.citations.length === 0;
```

---

### `frontend/src/components/layout/ProtectedRoute.tsx` (middleware, request-response)

**Analog:** None in codebase. Pattern from RESEARCH.md Pattern 3 (React Router v6 docs).

**Core pattern:**
```typescript
// frontend/src/components/layout/ProtectedRoute.tsx
// Uses React Router v6 Navigate (not v5 Redirect) — v7.14.2 retains v6 API
import { Navigate } from "react-router-dom";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem("access_token");
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
```

**Route wiring in App.tsx:**
```typescript
// frontend/src/App.tsx
import { Routes, Route } from "react-router-dom";

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

**Anti-pattern to avoid:** Do NOT use `useEffect` + `useNavigate` redirect inside the child component.
`<Navigate replace />` is synchronous and prevents flash of unprotected content (RESEARCH.md Don't Hand-Roll).

---

### `frontend/src/components/layout/Header.tsx` (component)

**Analog:** None.

**Visual contract** (from UI-SPEC.md Chat Page section):
```typescript
// frontend/src/components/layout/Header.tsx
// Fixed top bar, 56px height, full width
// Left: "Privacy Policy Assistant" (heading 20px/600)
// Right: "Log out" button (destructive hover state on hover only)
// Tailwind classes from UI-SPEC color section:
//   bg-white border-b border-zinc-200 (header bar)
//   text-zinc-950 font-semibold (title)
//   hover:text-destructive (logout button)
```

---

### `frontend/src/components/auth/LoginForm.tsx` (component, request-response)

**Analog:** None.

**Visual contract** (from UI-SPEC.md Login Page section):
```typescript
// frontend/src/components/auth/LoginForm.tsx
// shadcn Form component wrapping shadcn Input and Button
// States: default | loading | error-401 | error-network
// Uses shadcn form (React Hook Form under the hood) per RESEARCH.md Don't Hand-Roll

// Copywriting contract (from UI-SPEC.md):
// heading: "Sign in to continue"
// username label: "Username" | input type="text" autocomplete="username"
// password label: "Password" | input type="password" autocomplete="current-password"
// submit button: "Sign In" (full-width)
// loading: "Signing in..." + spinner icon
// 401 error: "Invalid username or password. Please try again." (text-destructive)
// network error: "Unable to connect. Check your connection and try again."
```

---

### `frontend/src/components/chat/CitationCard.tsx` (component)

**Analog:** None in codebase. Pattern from RESEARCH.md Pattern 4 (shadcn Collapsible docs).

**Core pattern:**
```typescript
// frontend/src/components/chat/CitationCard.tsx
// Uses shadcn Collapsible (Radix-based, keyboard accessible)
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronDown, FileText } from "lucide-react";

// Collapsed preview: first ~50 chars with ellipsis (D-06)
const preview = text.length > 50 ? text.slice(0, 50) + "…" : text;

// Visual contract from UI-SPEC.md Citation Cards section:
// Collapsed: bg-zinc-50 border border-zinc-200 rounded-md
//   - FileText icon + title (font-medium text-sm) + preview (caption 12px/400)
//   - ChevronDown right-aligned (accent color #18181b)
// Expanded: bg-white border border-zinc-300 rounded-md
//   - full citations[N].text in font-mono text-sm
//   - ChevronDown rotates 180deg (transition-transform duration-150)

// Fade-in animation (D-04): applied at the container level in MessageBubble
// opacity-0 → opacity-100 transition-opacity duration-200 ease-out
// Applied AFTER done event fires — never during delta events

// aria labels (accessibility contract):
// CollapsibleTrigger aria-label={isOpen ? "Collapse citation" : "Expand citation"}
```

---

### `frontend/src/components/chat/StreamingCursor.tsx` (component)

**Analog:** None.

**Core pattern** (from RESEARCH.md Pattern 5 + UI-SPEC.md Animation Contract):
```typescript
// frontend/src/components/chat/StreamingCursor.tsx
// Blink uses step-end easing (hard on/off — natural cursor feel)
// NOT animate-pulse (which fades 0.5 opacity — wrong for a cursor, Pitfall 6)
// Custom @keyframes blink in global CSS or tailwind.config.ts

// In global CSS (src/index.css):
// @keyframes blink {
//   0%, 100% { opacity: 1; }
//   50% { opacity: 0; }
// }

export function StreamingCursor() {
  return (
    <span
      className="text-zinc-950 font-normal"
      style={{ animation: "blink 1s step-end infinite" }}
    >
      |
    </span>
  );
}

// Usage in MessageBubble:
// {isStreaming && <StreamingCursor />}
// Remove when done event fires and isStreaming becomes false
```

---

### `frontend/src/components/chat/NoMatchMessage.tsx` (component)

**Analog:** None.

**Visual contract** (from UI-SPEC.md No Matching Policy section + Copywriting Contract):
```typescript
// frontend/src/components/chat/NoMatchMessage.tsx
// Rendered when isNoMatch === true (citations.length === 0 from done event)
// Styled as assistant message bubble with distinct treatment:
// - AlertCircle icon from lucide-react, text-amber-500, 20px
// - heading: "No matching policy found" (font-medium)
// - body: "The query did not match any passages in the indexed policy corpus.
//          Try rephrasing your question or using different terms."
// No citation cards below this message
import { AlertCircle } from "lucide-react";
```

---

### `frontend/src/components/chat/MessageBubble.tsx` (component, streaming)

**Analog:** None.

**Visual contract** (from UI-SPEC.md Message Bubbles section):
```typescript
// frontend/src/components/chat/MessageBubble.tsx
// Two variants via role prop:

// User bubble:
//   right-aligned, bg-zinc-100, rounded-lg, px-4 py-3, max-w-[70%]

// Assistant bubble:
//   left-aligned, bg-white border border-zinc-200, rounded-lg, px-4 py-3, max-w-[80%]
//   When isStreaming: append <StreamingCursor /> after text
//   When done: render citation cards below text with fade-in container
//   When isNoMatch: render <NoMatchMessage /> instead of citations

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  isStreaming?: boolean;
  isNoMatch?: boolean;
}
```

---

### `frontend/src/components/chat/MessageList.tsx` (component, streaming)

**Analog:** None.

**Core pattern:**
```typescript
// frontend/src/components/chat/MessageList.tsx
// overflow-y: auto on container
// useRef + useEffect to scroll to bottom on messages change
// Empty state rendered when messages.length === 0:
//   heading: "Ask a policy question"
//   body: 'Type a question about any privacy policy in the corpus.
//          For example: "Which policy applies to customer data retention?"'

const messagesEndRef = useRef<HTMLDivElement>(null);
useEffect(() => {
  messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
}, [messages]);
// Place <div ref={messagesEndRef} /> at bottom of message list
```

---

### `frontend/src/components/chat/ChatInput.tsx` (component, request-response)

**Analog:** None.

**Core pattern** (from RESEARCH.md Code Examples + UI-SPEC.md):
```typescript
// frontend/src/components/chat/ChatInput.tsx
// Input row height: 52px (UI-SPEC spacing exception)
// Text area or input — submit on Enter (not Shift+Enter)
// Disabled while isStreaming === true

const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    onSubmit();
  }
};

// Submit button text: "Send Message"
// aria-label on send button if icon-only
// Disable both input and button while isStreaming
```

---

### `frontend/src/App.tsx` (config)

**Analog:** None.

**Pattern:**
```typescript
// frontend/src/App.tsx
// React Router v6/v7 API — use Routes + Route (not Switch + Route v5)
// react-router-dom@7.14.2 retains v6 component API (Assumption A2 from RESEARCH.md)
import { BrowserRouter, Routes, Route } from "react-router-dom";

// Route table (UI-SPEC.md Routing Contract):
// /login → LoginPage (unauthenticated)
// / → ProtectedRoute > ChatPage (authenticated)
// Authenticated visit to /login → redirect to / (implement in LoginPage)
```

---

### `frontend/vite.config.ts` (config)

**Analog:** None.

**Core pattern** (from RESEARCH.md Pattern 6):
```typescript
// frontend/vite.config.ts
// Tailwind 4 uses @tailwindcss/vite plugin — NOT PostCSS tailwind.config.js (Pitfall 4)
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": "/src" },  // required for shadcn/ui @/ imports
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/auth": "http://localhost:8000",
    },
  },
});
```

---

### Test files (8 files, unit)

**Analog:** `backend/app/tests/test_auth.py` and `backend/app/tests/test_chat_endpoint.py` — backend test structure provides structural reference (describe each requirement, use mocking for external deps).

**Test framework:** vitest 4.1.5 + @testing-library/react + happy-dom (NOT Jest — Pitfall from RESEARCH.md)

**Configuration pattern:**
```typescript
// frontend/vitest.config.ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "happy-dom",
    setupFiles: ["./src/test/setup.ts"],
  },
  resolve: {
    alias: { "@": "/src" },
  },
});

// frontend/src/test/setup.ts
import "@testing-library/jest-dom";
```

**Test file naming convention** (from RESEARCH.md Validation Architecture):
```
src/components/layout/ProtectedRoute.test.tsx  → REQ UI-01
src/components/chat/ChatPage.test.tsx           → REQ UI-02
src/hooks/useSSEChat.test.ts                    → REQ UI-03
src/components/chat/CitationCard.test.tsx       → REQ UI-04, CITE-04
src/components/chat/NoMatchMessage.test.tsx     → REQ UI-05
src/hooks/useAuth.test.ts                       → REQ UI-06
```

**Mock pattern** (vi.stubGlobal mirrors backend's `patch.object` pattern):
```typescript
// Mock fetch for unit tests (no live backend required)
vi.stubGlobal("fetch", vi.fn());
// or use @testing-library approach:
const mockFetch = vi.fn();
global.fetch = mockFetch;
```

---

## Shared Patterns

### Authentication Header
**Applies to:** `api.ts` (fetchWithAuth), `useAuth.ts` (logout call)
**Source:** `backend/app/api/auth.py` lines 61-97 + `backend/app/services/auth.py` lines 120-160
```typescript
// Format: Authorization: Bearer <access_token>
// The backend's HTTPBearer(auto_error=False) dependency strips "Bearer " prefix
// Returns HTTP 401 with WWW-Authenticate: Bearer on missing/invalid token
headers: { Authorization: `Bearer ${tokens.getAccess()}` }
```

### SSE Event Type Discriminants
**Applies to:** `useSSEChat.ts`, test mocks
**Source:** `backend/app/api/chat.py` lines 64-80 (definitive source — read directly)
```typescript
// Three event types only — no others emitted by backend:
// "delta"  → content: string (one LLM token)
// "done"   → answer: string, citations: Citation[]
// "error"  → message: string  ← field is "message" NOT "detail" (Pitfall 5 in RESEARCH.md)
```

### shadcn cn() Helper
**Applies to:** All component files
**Source:** RESEARCH.md Don't Hand-Roll section
```typescript
// Installed automatically by `npx shadcn@latest init`
// Location after init: src/lib/utils.ts
import { cn } from "@/lib/utils";
// Usage: cn("base-class", condition && "conditional-class", props.className)
```

### Tailwind Color Tokens
**Applies to:** All component files
**Source:** UI-SPEC.md Color section
```
bg-white          → page background, assistant bubbles
bg-zinc-100       → user bubbles, secondary surface
bg-zinc-50        → citation card collapsed background
text-zinc-950     → primary text, accent elements
border-zinc-200   → default borders
border-zinc-300   → expanded citation card border
text-destructive  → error states, logout button hover
text-amber-500    → NoMatchMessage warning icon
```

---

## No Analog Found

All frontend files have no direct codebase analog (greenfield SPA). The backend files serve as contract references only, not code to copy. Patterns for all 18 files come from RESEARCH.md (verified against official documentation) and UI-SPEC.md.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `frontend/src/lib/tokens.ts` | utility | — | No localStorage utility exists anywhere |
| `frontend/src/lib/api.ts` | utility | request-response | No fetch wrapper exists; backend analog is FastAPI router |
| `frontend/src/hooks/useAuth.ts` | hook | request-response | No React hooks exist; pattern derived from RESEARCH.md |
| `frontend/src/hooks/useSSEChat.ts` | hook | streaming | No SSE consumer exists; pattern from MDN + RESEARCH.md |
| `frontend/src/components/layout/ProtectedRoute.tsx` | middleware | request-response | No route guard exists; pattern from React Router v6 docs |
| `frontend/src/components/layout/Header.tsx` | component | — | No UI components exist |
| `frontend/src/components/auth/LoginForm.tsx` | component | request-response | No UI components exist |
| `frontend/src/pages/LoginPage.tsx` | page | request-response | No pages exist |
| `frontend/src/pages/ChatPage.tsx` | page | streaming | No pages exist |
| `frontend/src/components/chat/ChatPage.tsx` | component | streaming | No UI components exist |
| `frontend/src/components/chat/MessageList.tsx` | component | streaming | No UI components exist |
| `frontend/src/components/chat/MessageBubble.tsx` | component | streaming | No UI components exist |
| `frontend/src/components/chat/ChatInput.tsx` | component | request-response | No UI components exist |
| `frontend/src/components/chat/CitationCard.tsx` | component | — | No UI components exist |
| `frontend/src/components/chat/StreamingCursor.tsx` | component | — | No UI components exist |
| `frontend/src/components/chat/NoMatchMessage.tsx` | component | — | No UI components exist |
| `frontend/src/App.tsx` | config | — | No React app scaffold exists |
| `frontend/vite.config.ts` | config | — | No Vite config exists |

---

## Critical Implementation Order

The planner MUST enforce this initialization sequence (Pitfall 1 from RESEARCH.md):

1. **Wave 0 — Scaffold only:** Run `npm create vite@latest frontend -- --template react-ts`, then `npx shadcn@latest init` (new-york style, neutral base, CSS variables), then `npx shadcn@latest add button input card collapsible form label separator`. Verify `frontend/components.json` exists before writing any component code.
2. **Wave 1 — Foundation:** `tokens.ts`, `api.ts`, `App.tsx`, `vite.config.ts`, `ProtectedRoute.tsx`
3. **Wave 2 — Auth flow:** `useAuth.ts`, `LoginForm.tsx`, `LoginPage.tsx`
4. **Wave 3 — Chat core:** `useSSEChat.ts`, `StreamingCursor.tsx`, `CitationCard.tsx`, `NoMatchMessage.tsx`
5. **Wave 4 — Chat layout:** `MessageBubble.tsx`, `MessageList.tsx`, `ChatInput.tsx`, `Header.tsx`, `ChatPage.tsx`
6. **Wave 5 — Tests:** All test files

---

## Metadata

**Analog search scope:** `backend/` (all Python source files)
**Frontend files scanned:** 0 (no frontend directory exists)
**Backend files read:** `auth.py`, `chat.py`, `services/auth.py`, `core/config.py`, `tests/test_auth.py`, `tests/test_chat_endpoint.py`, `tests/conftest.py`
**Pattern extraction date:** 2026-04-27

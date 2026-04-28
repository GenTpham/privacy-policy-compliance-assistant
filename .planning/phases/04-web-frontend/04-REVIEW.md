---
phase: 04-web-frontend
reviewed: 2026-04-28T00:00:00Z
depth: standard
files_reviewed: 24
files_reviewed_list:
  - frontend/src/App.tsx
  - frontend/src/components/auth/LoginForm.tsx
  - frontend/src/components/chat/ChatInput.tsx
  - frontend/src/components/chat/CitationCard.tsx
  - frontend/src/components/chat/MessageBubble.tsx
  - frontend/src/components/chat/MessageList.tsx
  - frontend/src/components/chat/NoMatchMessage.tsx
  - frontend/src/components/chat/StreamingCursor.tsx
  - frontend/src/components/layout/Header.tsx
  - frontend/src/components/layout/ProtectedRoute.tsx
  - frontend/src/hooks/useAuth.ts
  - frontend/src/hooks/useSSEChat.ts
  - frontend/src/lib/api.ts
  - frontend/src/lib/tokens.ts
  - frontend/src/lib/utils.ts
  - frontend/src/index.css
  - frontend/src/pages/ChatPage.tsx
  - frontend/src/pages/LoginPage.tsx
  - frontend/src/hooks/useAuth.test.ts
  - frontend/src/hooks/useSSEChat.test.ts
  - frontend/src/components/chat/ChatPage.test.tsx
  - frontend/src/components/chat/CitationCard.test.tsx
  - frontend/src/components/chat/NoMatchMessage.test.tsx
  - frontend/src/components/layout/ProtectedRoute.test.tsx
findings:
  critical: 0
  warning: 5
  info: 5
  total: 10
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-04-28T00:00:00Z
**Depth:** standard
**Files Reviewed:** 24
**Status:** issues_found

## Summary

All 24 source files reviewed at standard depth. The React SPA is well-structured — the SSE streaming pipeline, token refresh logic, and routing guard are implemented correctly. No critical security vulnerabilities, injection points, or authentication bypasses were found. localStorage token storage is an accepted tradeoff per design decision D-08 and is not flagged.

Five warnings were found, all logic bugs that could cause incorrect behavior in production: a render-time side-effect in LoginForm that calls `navigate()` during render, a module-level `isRefreshing` flag that is never reset on refresh success path, an SSE stream reader that is not cancelled on early error exit, missing handling for `isError` in `MessageBubble`, and an unbounded conversation history sent to the backend. Five informational items cover minor quality issues.

---

## Warnings

### WR-01: `navigate()` called during render in LoginForm — React rules violation

**File:** `frontend/src/components/auth/LoginForm.tsx:25-28`

**Issue:** Lines 25–28 call `navigate("/", { replace: true })` unconditionally during the render phase when a token is present. React forbids side-effects during render. In React 19 strict mode this call fires twice per render, causing a double-navigation. The correct pattern is to redirect via `<Navigate>` (declarative) or to move the imperative `navigate()` into a `useEffect`.

**Fix:**
```tsx
// Replace the imperative navigate() block (lines 25-28) with a declarative redirect:
import { Navigate } from "react-router-dom";

// Inside LoginForm, before the return:
if (tokens.getAccess()) {
  return <Navigate to="/" replace />;
}
```

---

### WR-02: `isRefreshing` module-level flag is never reset after a successful refresh

**File:** `frontend/src/lib/api.ts:36-52`

**Issue:** `isRefreshing` is set to `true` at line 36 and reset to `false` in the `finally` block at line 51. This looks correct at first glance, but the `finally` block runs before the retry fetch at line 55. If the retry itself throws a network error, execution propagates out of `fetchWithAuth` with `isRefreshing` already `false` — that part is fine. However, if `onUnauthorized()` is called inside the `try` block (line 45) and then `throw` is reached (line 46), the `finally` at line 51 still runs and resets `isRefreshing`. That path is correct.

The real bug: if `fetch("/auth/refresh", ...)` itself throws a network error (not a non-OK response, but a thrown exception such as a DNS failure), the `finally` block runs and resets `isRefreshing = false`, but `onUnauthorized()` is never called. The user is left in a half-authenticated state — the original request failed, the refresh failed with no notification, and the UI gives no feedback.

**Fix:**
```typescript
isRefreshing = true;
try {
  const refreshToken = tokens.getRefresh();
  const refreshResp = await fetch("/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!refreshResp.ok) {
    onUnauthorized();
    throw new Error("Refresh failed — force logout");
  }
  const { access_token } = await refreshResp.json();
  tokens.setAccess(access_token);
} catch (err) {
  // Catch both non-OK responses (already handled above) and network throws
  // Ensure onUnauthorized is called if it hasn't been already
  onUnauthorized();
  throw err;
} finally {
  isRefreshing = false;
}
```

A cleaner approach is to track whether `onUnauthorized` was already called with a local flag before re-throwing.

---

### WR-03: SSE ReadableStream reader not cancelled on error path — resource leak

**File:** `frontend/src/hooks/useSSEChat.ts:33-54`

**Issue:** In `parseSSEStream`, the `reader` is obtained via `response.body!.getReader()` (line 33). On the happy path, the generator exhausts the stream and the loop exits normally. However, if `JSON.parse(data)` on line 50 throws a `SyntaxError` (malformed SSE payload from the server), the generator throws without calling `reader.cancel()`. The locked reader is never released, leaving the underlying connection open until garbage collected. This is especially relevant during error events where the stream may be partially well-formed.

**Fix:**
```typescript
async function* parseSSEStream(
  response: Response
): AsyncGenerator<Record<string, unknown>> {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";

      for (const event of events) {
        for (const line of event.split("\n")) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6).trim();
            if (data) yield JSON.parse(data);
          }
        }
      }
    }
  } finally {
    reader.cancel();
  }
}
```

---

### WR-04: `isError` prop accepted by `MessageBubble` but never rendered

**File:** `frontend/src/components/chat/MessageBubble.tsx:11-28`

**Issue:** `MessageBubble` declares an `isError?: boolean` prop in its interface (line 11) and the prop is passed from `MessageList` (line 55 of `MessageList.tsx`), but the component body never reads or uses `isError`. Error messages set by `useSSEChat` in the catch block (lines 157–169 of `useSSEChat.ts`) are displayed as plain assistant bubbles with no visual distinction — the error styling that the spec likely intends is silently dropped.

**Fix:**
```tsx
export function MessageBubble({
  role,
  content,
  citations = [],
  isStreaming = false,
  isNoMatch = false,
  isError = false,
}: MessageBubbleProps) {
  // ...
  // In the assistant branch, apply error styling when isError is true:
  <div
    className={cn(
      "border rounded-lg px-4 py-3 text-zinc-950 text-base leading-relaxed w-full",
      isError
        ? "bg-red-50 border-red-200"
        : "bg-white border-zinc-200"
    )}
  >
    <span>{content}</span>
    {isStreaming && <StreamingCursor />}
  </div>
```

---

### WR-05: Unbounded conversation history grows without limit

**File:** `frontend/src/hooks/useSSEChat.ts:72-77`

**Issue:** Every `submit()` call sends the full `messages` array as `history` to the backend (lines 72–77). Since history is never truncated, a long conversation will eventually exceed the model's context window (131,072 tokens for Gemma 4 26B). When the token limit is hit the backend will return an error. The UI has no mechanism to warn the user or truncate gracefully — it will silently show the generic error message. This is a correctness issue: the feature stops working without explanation.

**Fix:** Apply a sliding window before building history. A reasonable threshold for this use case (policy Q&A, non-conversational) is the last 10 exchanges (20 messages):
```typescript
const HISTORY_LIMIT = 20; // 10 user + 10 assistant turns
const history = messages
  .slice(-HISTORY_LIMIT)
  .map((m) => ({ role: m.role, content: m.content }));
```

---

## Info

### IN-01: Non-null assertion on `response.body` is unchecked

**File:** `frontend/src/hooks/useSSEChat.ts:33`

**Issue:** `response.body!.getReader()` uses a non-null assertion. `body` can legitimately be `null` on a Response constructed without a body (e.g., in tests using `new Response(null, ...)`). A guard would make the failure message actionable rather than a cryptic `Cannot read properties of null`.

**Fix:**
```typescript
if (!response.body) {
  throw new Error("SSE response has no body — server returned empty response");
}
const reader = response.body.getReader();
```

---

### IN-02: `tokens.setRefresh` is absent — asymmetric token API

**File:** `frontend/src/lib/tokens.ts:1-18`

**Issue:** The `tokens` object exposes `setAccess` (line 7) and `setBoth` (line 10) but no `setRefresh`. After a token refresh, only the new access token is stored (`tokens.setAccess(access_token)` in `api.ts:49`). If the backend ever rotates both tokens on refresh (a common security pattern), there is no API to store the new refresh token without calling `setBoth`. Currently this is not a bug because the backend does not appear to rotate refresh tokens, but the asymmetric API is a maintenance hazard.

**Fix:**
```typescript
setRefresh: (t: string): void => {
  localStorage.setItem("refresh_token", t);
},
```

---

### IN-03: Message list uses array index as React key

**File:** `frontend/src/components/chat/MessageList.tsx:43`

**Issue:** `key={index}` is used for the messages list. If messages were ever reordered, filtered, or deleted (e.g., a "clear chat" feature), React would reuse the wrong DOM nodes. For a purely append-only list this is safe today but is a maintenance hazard if the message model changes.

**Fix:** Add a stable `id` field to the `Message` interface in `useSSEChat.ts` and use it as the key:
```typescript
// In useSSEChat.ts Message interface:
export interface Message {
  id: string; // crypto.randomUUID() at creation time
  role: "user" | "assistant";
  // ...
}

// In MessageList.tsx:
<MessageBubble key={msg.id} ... />
```

---

### IN-04: `NoMatchMessage.test.tsx` body-copy assertion will break on whitespace changes

**File:** `frontend/src/components/chat/NoMatchMessage.test.tsx:14-17`

**Issue:** The test uses two separate `getByText(/Try rephrasing your question/)` and `getByText(/The query did not match any passages/)` matchers against text that is rendered in a single `<p>` element. If the copy is ever split across child spans or the text changes slightly, both matchers silently pass against the same node. Consider asserting against the full rendered text of the container.

**Fix:**
```typescript
const para = screen.getByText(/The query did not match any passages/);
expect(para.textContent).toContain("Try rephrasing your question");
```

---

### IN-05: `blink` keyframe in `index.css` does not match step-end behavior documented in `StreamingCursor.tsx`

**File:** `frontend/src/index.css:49-52`

**Issue:** The `blink` keyframe is defined as:
```css
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
```
This produces a smooth ease-based fade (not a hard step), because the animation timing function (`step-end`) is applied in the component's inline style, not in the keyframe itself. The keyframe definition and the component comment ("step-end easing for hard on/off") are consistent — the `step-end` on the `animation` property correctly overrides interpolation. However, defining the keyframe with `50% { opacity: 0 }` instead of two discrete stops (`0% { opacity: 1 } 100% { opacity: 0 }`) is a common source of future confusion if the timing function is ever changed. No behavior bug today, but document the coupling clearly.

**Fix:** Either simplify the keyframe to two stops (since `step-end` handles the stepping):
```css
@keyframes blink {
  from { opacity: 1; }
  to { opacity: 0; }
}
```
Or add a comment explaining why `step-end` in the component produces the correct hard-switch behavior despite the multi-stop keyframe.

---

_Reviewed: 2026-04-28T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

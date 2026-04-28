# Phase 4: Web Frontend — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-27
**Phase:** 04-web-frontend
**Areas discussed:** Visual style & layout, Streaming response UX, Citation cards UX, Session & token handling

---

## Visual Style & Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Single-column, full-width | Messages stack vertically, citations inline below each answer. Aligns with ROADMAP spec. | ✓ |
| Two-panel (chat + citations sidebar) | Chat on the left, citation details panel on the right. | |
| Message-centered narrow column | Chat constrained to ~768px max, similar to Claude/ChatGPT style. | |

**User's choice:** Single-column, full-width

| Option | Description | Selected |
|--------|-------------|----------|
| Clean & minimal | White/light gray, muted colors, no branding. Professional and neutral. | ✓ |
| Dark mode by default | Dark background, light text. Easier on the eyes. | |
| Both light and dark | User-toggleable theme. More work. | |

**User's choice:** Clean & minimal

**Notes:** User moved on without further layout questions.

---

## Streaming Response UX

| Option | Description | Selected |
|--------|-------------|----------|
| Blinking cursor at end of text | `\|` cursor appended to growing text. Clear in-progress signal. | ✓ |
| Animated ellipsis placeholder first | Show `...` until first token arrives, then switch to text. | |
| Tokens appear, no indicator | Text grows with no cursor or indicator. | |

**User's choice:** Blinking cursor at end of text

| Option | Description | Selected |
|--------|-------------|----------|
| After done event, fade in | Citations appear once streaming completes and fade in smoothly. Avoids layout jumps. | ✓ |
| After done event, instant | Citations appear immediately when done fires, no animation. | |
| Progressive mid-stream | Not possible — citations are only in the done event. | |

**User's choice:** After done event, fade in

**Notes:** User confirmed citations belong after done event only (consistent with backend design).

---

## Citation Cards UX

| Option | Description | Selected |
|--------|-------------|----------|
| All collapsed, click to expand | Cards show title + preview. User clicks for full text. Keeps answer readable. | ✓ |
| First citation expanded, rest collapsed | Most relevant citation open by default. | |
| All expanded | Full text of every citation shown immediately. | |

**User's choice:** All collapsed, click to expand

| Option | Description | Selected |
|--------|-------------|----------|
| Document title + excerpt preview | "📄 Google Privacy Policy — 'Users may request deletion...'" — enough to judge relevance. | ✓ |
| Document title only | Clean and minimal. Less scannable. | |
| Citation number + document title | "[1] Google Privacy Policy" — correlates with [N] references in answer text. | |

**User's choice:** Document title + excerpt preview

---

## Session & Token Handling

| Option | Description | Selected |
|--------|-------------|----------|
| localStorage | Tokens persist across refreshes. Acceptable for internal compliance tool. | ✓ |
| sessionStorage | Tokens cleared on tab close. Lower risk but worse UX. | |
| In-memory only (React state) | Safest but lost on page refresh — must re-login every time. | |

**User's choice:** localStorage

| Option | Description | Selected |
|--------|-------------|----------|
| Silent refresh — auto-retry | On 401, call /auth/refresh, get new token, retry original request transparently. | ✓ |
| Redirect to login page | On any 401, clear tokens and redirect to /login. Simpler but interrupts conversation. | |
| Show inline error, offer re-login | Keep page, show "Session expired" with re-login button. | |

**User's choice:** Silent refresh — auto-retry with new token

---

## Claude's Discretion

- Exact Tailwind color palette and spacing
- React Query vs SWR vs plain `fetch` for auth calls
- SSE parsing implementation details (`fetch` + `ReadableStream`)
- Citation card fade-in animation timing
- Error state design for network failures mid-stream

## Deferred Ideas

None — discussion stayed within phase scope.

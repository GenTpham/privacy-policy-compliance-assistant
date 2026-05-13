---
phase: 09-ux-enhancements
fixed_at: 2026-05-13T00:00:00Z
review_path: .planning/phases/09-ux-enhancements/09-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 5
skipped: 2
status: partial
---

# Phase 9: Code Review Fix Report

**Fixed at:** 2026-05-13T00:00:00Z
**Source review:** .planning/phases/09-ux-enhancements/09-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (CR-01, WR-01 through WR-06)
- Fixed: 5 (CR-01, WR-01, WR-03, WR-04, WR-05)
- Skipped: 2 (WR-02, WR-06 — explicitly excluded per instructions)

## Fixed Issues

### CR-01: `response.body!` non-null assertion crashes on null body

**Files modified:** `frontend/src/hooks/useSSEChat.ts`
**Commit:** 6be9ec4
**Applied fix:** Replaced `response.body!.getReader()` with a null guard — if `response.body` is null, throws `'Response body is null — streaming not supported in this environment'`. The error propagates to the existing `catch` block which calls `setIsStreaming(false)`, preventing the chat input from being permanently locked.

---

### WR-01: 401 response from `/api/sources` fetch silently swallowed

**Files modified:** `frontend/src/pages/AskAssistantScreen.tsx`
**Commit:** 4d453cd
**Applied fix:** Added `r.ok` check in the `.then()` chain before calling `r.json()`. Non-2xx responses now throw `Error('Sources fetch failed: ${r.status}')`, which propagates to the `.catch()` handler that sets the sources error state.

---

### WR-03: Empty-string `source_filter` bypasses backend validation

**Files modified:** `backend/app/api/chat.py`, `backend/app/services/rag.py`
**Commit:** a91088b
**Applied fix:**
1. In `chat.py`: added `min_length=1` to the `source_filter` Field — empty strings now rejected with HTTP 422.
2. In `rag.py`: changed both `if source_filter` falsy checks to `if source_filter is not None` (lines 198 and 346, covering both `stream_answer` and `stream_conflict_answer`) — explicit None check is clearer about intent.

---

### WR-04: `sources.py` swallows exception without logging

**Files modified:** `backend/app/api/sources.py`
**Commit:** 2b3ddb3
**Applied fix:** Added `import logging` at the top of the file, created `logger = logging.getLogger(__name__)` at module level, and added `logger.exception("Failed to retrieve sources from Qdrant")` before the `raise HTTPException(...)` call. Root cause of Qdrant failures will now appear in server logs.

---

### WR-05: Topic Filter UI is non-functional misleading affordance

**Files modified:** `frontend/src/pages/AskAssistantScreen.tsx`
**Commit:** d5915dd
**Applied fix:** Added `{/* TODO(Phase 10+): wire topicFilter to submit() — currently non-functional affordance */}` comment above the topic filter buttons. All topic filter buttons now render with `opacity: 0.5`, `pointerEvents: "none" as const`, `cursor: "not-allowed"`, and a static muted color — making them visually non-interactive while preserving the UI structure for future implementation.

---

## Skipped Issues

### WR-02: Message timestamps recalculated on every render

**File:** `frontend/src/pages/AskAssistantScreen.tsx:208`
**Reason:** Explicitly excluded per fix instructions — "minor and risky to change without tests."
**Original issue:** `new Date().toTimeString().slice(0, 5)` inside `messages.map()` re-evaluates on every render during streaming, causing timestamps to shift.

---

### WR-06: `isStreaming` closure stale-read risk in `submit`

**File:** `frontend/src/hooks/useSSEChat.ts:69-179`
**Reason:** Explicitly excluded per fix instructions — "minor and risky to change without tests."
**Original issue:** `isStreaming` guard read from closure; rapid double-click before React re-renders could pass the guard. Fix requires adding `useRef` guard which changes hook behavior.

---

_Fixed: 2026-05-13T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_

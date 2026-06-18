---
title: Chat UX Improvement — Answer Card + Inline Citations
date: 2026-06-18
status: proposed
---

## Summary

Redesign the assistant answer in the chat UI so that general users can quickly scan a concise answer, click inline citation badges to verify sources, and expand a source list only when needed. The layout keeps the existing three-column app shell but focuses attention on the answer card instead of a persistent right-side evidence panel.

## Goals

- Make the assistant answer scannable for non-expert users.
- Keep source verification one click away via inline `[N]` badges.
- Collapse the evidence panel by default to reduce cognitive load.
- Preserve the existing Server-Sent Events (SSE) streaming experience.
- Reuse existing components (`CitationCard`) where possible.

## Non-Goals

- Change backend RAG logic or API shape.
- Replace the free-form chat with a wizard.
- Implement a mobile responsive redesign (may be a follow-up).
- Modify the auth or login flow.

## Context

The current UI (`frontend/src/pages/AskAssistantScreen.tsx`) renders a three-column layout: a source-filter sidebar on the left, the chat area in the center, and a persistent Evidence panel on the right. `MessageBubble` displays plain text and a citation-count button. `CitationCard` is an expandable card with a score and excerpt. For general users who only need a quick answer, the current layout spreads attention across too many panels and does not surface the most important information first.

## Approach

### UX Changes

1. **Answer Card layout**
   - Each assistant message is rendered as a card containing:
     - A concise answer text area.
     - Inline citation badges `[1]`, `[2]` placed next to the claims they support.
     - A collapsible “Sources” section below the answer.
   - User messages keep the current bubble style.

2. **Inline citation badges**
   - Badges are clickable and open the Evidence panel on the right.
   - Clicking a badge scrolls the panel to the corresponding source.
   - Badges appear only after the SSE stream finishes (the `done` event).

3. **Sources section**
   - Shows a short list of cited sources (title, company, excerpt preview, confidence bar).
   - Has a “View all sources” button that expands the Evidence panel.

4. **Evidence panel**
   - Collapsed by default.
   - Slides in when a user clicks a badge or “View all sources”.
   - Retains current behavior: full verbatim excerpt, relevance score, source ID.

5. **Suggested prompts**
   - Keep the prompt bar but rephrase suggestions for general users, e.g.:
     - “Google thu thập dữ liệu gì từ tôi?”
     - “TikTok có chia sẻ dữ liệu không?”
     - “Tôi có quyền gì với dữ liệu của mình trên Facebook?”

### Component Changes

- `frontend/src/components/chat/MessageBubble.tsx`
  - During streaming: render plain text only.
  - After `done`: render `AnswerCard`.
  - Pass `onOpenEvidence(citation)` callback.

- New: `frontend/src/components/chat/AnswerCard.tsx`
  - Renders parsed answer text with inline badges and the collapsible source list.

- New: `frontend/src/components/chat/InlineCitationBadge.tsx`
  - Clickable badge `[N]`.

- `frontend/src/components/chat/CitationCard.tsx`
  - Reused inside the collapsible source list and the Evidence panel.

- `frontend/src/pages/AskAssistantScreen.tsx`
  - Manage Evidence panel open/closed state.
  - Add `scrollToCitation(id)` helper.

- New helper: `frontend/src/lib/parseCitations.ts`
  - Parse `answer` text and `citations` array to produce renderable segments.
  - Validate that each `[N]` exists in the citation list; drop or mark invalid IDs.

### Data Flow

1. Backend returns SSE events `delta` then `done` with `answer` and `citations`.
2. `useSSEChat` stores the final message as it does today.
3. `MessageBubble` detects the assistant message is complete and renders `AnswerCard`.
4. `AnswerCard` calls `parseCitations(answer, citations)`:
   - Splits the answer into segments.
   - Replaces `[N]` references with `InlineCitationBadge`.
   - Builds a deduplicated list of cited sources in order of first appearance.
5. Clicking a badge sets `activeEvidence` in `AskAssistantScreen` and opens the Evidence panel.

### File Changes

- Modify: `frontend/src/components/chat/MessageBubble.tsx`
- Modify: `frontend/src/components/chat/CitationCard.tsx` (minor styling adjustments if needed)
- Modify: `frontend/src/pages/AskAssistantScreen.tsx`
- Create: `frontend/src/components/chat/AnswerCard.tsx`
- Create: `frontend/src/components/chat/InlineCitationBadge.tsx`
- Create: `frontend/src/lib/parseCitations.ts`
- Update: `frontend/src/lib/mockData.ts` (suggested prompts)
- Create: `frontend/src/components/chat/MessageBubble.test.tsx`
- Update: `frontend/src/components/chat/ChatPage.test.tsx`

## Error Handling

- **No matching policy:** display a friendly message and 2–3 suggested rephrasings.
- **LLM/stream error:** show the error inside the AnswerCard with a “Thử lại” button that resubmits the last user message.
- **Invalid citation ID:** if the LLM emits `[N]` not present in `citations`, hide the badge or show it as unverified.
- **No inline citations but citations exist:** show a “Sources consulted” section with the retrieved sources so the user knows what was checked.
- **Streaming state:** do not parse badges until the `done` event arrives.

## Testing

- Unit tests:
  - Streaming answer does not contain citation badges.
  - Completed answer renders the correct badges and source list.
  - Clicking a badge opens the Evidence panel and sets the active citation.
  - No-match state shows the friendly message.
  - Error state shows the retry button.
- Backend regression tests: run existing `pytest backend/app/tests`.
- Manual QA:
  - Ask a real policy question, verify the answer card and sources.
  - Click each badge and confirm the panel scrolls to the source.
  - Ask an out-of-corpus question and verify the no-match flow.

## Open Questions

- Should the Evidence panel close automatically when the user sends a new message? (Recommended: yes, to keep focus on the new answer.)
- Should the source list be expanded by default or collapsed? (Recommended: collapsed for quick scanning, one click to expand.)

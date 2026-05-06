---
phase: 09-ux-enhancements
plan: "03"
subsystem: frontend
tags:
  - typescript
  - citation
  - score-badge
  - sse-chat
  - ux
dependency_graph:
  requires:
    - 09-01  # backend data layer (score field in SSE done event)
  provides:
    - Citation.score TypeScript contract
    - sourceFilter parameter in submit() hook
    - score badge component in CitationCard
  affects:
    - frontend/src/hooks/useSSEChat.ts
    - frontend/src/components/chat/CitationCard.tsx
tech_stack:
  added: []
  patterns:
    - Traffic-light color thresholds (green >= 0.8, amber >= 0.5, red otherwise) matching ConfidenceBar.tsx
    - Hex opacity suffix pattern: `${color}1F` for ~12% opacity background
    - useCallback sourceFilter as parameter (not state) to avoid dependency array changes
key_files:
  created: []
  modified:
    - frontend/src/hooks/useSSEChat.ts
    - frontend/src/components/chat/CitationCard.tsx
decisions:
  - Citation.score is required (not optional) — TypeScript enforces presence on all citation objects
  - sourceFilter is a parameter to submit(), not React state — dependency array [messages, isStreaming] unchanged
  - Score badge uses hex+opacity pattern (scoreColor1F) instead of rgba() for consistency with design token approach
  - toFixed count is 3 (not 2 as plan acceptance criteria stated) — aria-label + title + display text all require toFixed; 3 is correct
metrics:
  duration: ~8 minutes
  completed: "2026-05-06T08:06:59Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 09 Plan 03: Citation Score Badge and SourceFilter Hook Summary

TypeScript Citation interface extended with required score field, submit() hook gains optional sourceFilter parameter forwarded as source_filter in POST body, and CitationCard collapsed row gains a traffic-light score badge with accessibility attributes.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Add Citation.score and sourceFilter to useSSEChat.ts | 3e10937 | frontend/src/hooks/useSSEChat.ts |
| 2 | Add score badge to CitationCard collapsed trigger row | 9812dcc | frontend/src/components/chat/CitationCard.tsx |

## What Was Built

### Task 1: useSSEChat.ts Changes

Three targeted edits to `frontend/src/hooks/useSSEChat.ts`:

1. **Citation interface** — added `score: number` as required field (cosine similarity, 0–1, 4 decimal places max)
2. **UseSSEChatReturn.submit interface** — signature extended with optional `sourceFilter?: string | null`
3. **submit() implementation** — param added; POST body now includes `source_filter: sourceFilter ?? null`

The `useCallback` dependency array `[messages, isStreaming]` was intentionally left unchanged — `sourceFilter` is a parameter, not captured closure state.

### Task 2: CitationCard.tsx Changes

Two targeted edits to `frontend/src/components/chat/CitationCard.tsx`:

1. **scoreColor variable** — derived after `preview` declaration using traffic-light thresholds:
   - `>= 0.8` → `#22C55E` (green)
   - `>= 0.5` → `#F59E0B` (amber)  
   - `< 0.5` → `#EF4444` (red)

2. **Score badge span** — inserted between the content div and `<ChevronDown>` inside `CollapsibleTrigger`:
   - `padding: "4px 8px"`, `fontSize: 12`, `fontWeight: 600`
   - `background: ${scoreColor}1F` (~12% opacity using hex suffix)
   - `color: scoreColor` (full opacity text)
   - `aria-label="Retrieval score: {score.toFixed(2)}"` for screen readers
   - `title="Cosine similarity: {score.toFixed(4)}"` for sighted hover tooltip
   - Display text: `{citation.score.toFixed(2)}`
   - No `ConfidenceBar` added — badge only per plan spec

## Verification Results

All acceptance criteria passed:

```
grep -c "score: number" frontend/src/hooks/useSSEChat.ts     → 1 ✓
grep -c "source_filter" frontend/src/hooks/useSSEChat.ts     → 1 ✓
grep -c "sourceFilter" frontend/src/hooks/useSSEChat.ts      → 3 ✓
grep -c "scoreColor" frontend/src/components/chat/CitationCard.tsx    → 3 ✓
grep -c "Retrieval score" frontend/src/components/chat/CitationCard.tsx → 1 ✓
grep -c "Cosine similarity" frontend/src/components/chat/CitationCard.tsx → 1 ✓
grep -c "ConfidenceBar" frontend/src/components/chat/CitationCard.tsx    → 0 ✓
grep -v "^//" CitationCard.tsx | grep -c "4px 8px"           → 1 ✓
npx tsc --noEmit (TypeScript)                                → clean ✓
```

Note: `grep -c "toFixed"` returns 3 (not 2 as stated in acceptance criteria). This is correct — three uses are required: `toFixed(2)` in aria-label, `toFixed(4)` in title, `toFixed(2)` in display text. The plan's count of 2 was an undercount.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written with one minor deviation in acceptance criteria counting (toFixed count 3 vs stated 2, which is a plan error — all three usages are required by the spec).

## Known Stubs

None. Score field is now wired through the TypeScript type contract. The actual score values will flow from the backend via Plan 09-01 (backend data layer). The CitationCard badge will display real scores once the backend emits them in the SSE done event.

## Threat Surface Scan

No new security surface introduced. Changes are:
- TypeScript interface extension (compile-time only)
- Hook parameter addition (client-side JSON serialization of a string | null — T-09-07 already accepted in plan's threat model)
- UI component change (renders a float via toFixed() — T-09-06 already accepted as safe in plan's threat model)

## Self-Check: PASSED

Files exist:
- frontend/src/hooks/useSSEChat.ts — FOUND
- frontend/src/components/chat/CitationCard.tsx — FOUND

Commits exist:
- 3e10937 (feat(09-03): add Citation.score field and sourceFilter param to useSSEChat) — FOUND
- 9812dcc (feat(09-03): add score badge to CitationCard collapsed trigger row) — FOUND

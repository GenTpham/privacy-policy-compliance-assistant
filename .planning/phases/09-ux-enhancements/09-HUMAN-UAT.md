---
status: partial
phase: 09-ux-enhancements
source: [09-VERIFICATION.md]
started: 2026-05-06T12:00:00Z
updated: 2026-05-06T12:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Sidebar loading state
expected: While `/api/sources` is loading, 3 skeleton rows appear in the Policy Source sidebar with `aria-busy="true"`. Once loaded, "All Sources" + real policy title buttons appear.
result: [pending]

### 2. Source filter scoping end-to-end
expected: Select a specific policy from the sidebar, submit a query. All citation cards reference only that policy's passages — no results from other sources appear.
result: [pending]

### 3. Score badge visual rendering
expected: Each collapsed citation card row shows a colored score badge (e.g. "0.38") between the content preview and the chevron. Badge color follows traffic-light: green ≥0.8, amber ≥0.5, red <0.5. Hovering shows "Cosine similarity: 0.3812" tooltip.
result: [pending]

### 4. ConfidenceBar uses real scores
expected: In the Evidence panel, ConfidenceBar values vary per citation based on actual retrieval scores rather than fixed values (0.85/0.88 are gone).
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps

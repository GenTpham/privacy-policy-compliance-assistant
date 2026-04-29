# Phase 5: Cross-Document Conflict Detection — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-28
**Phase:** 05-cross-document-conflict-detection
**Areas discussed:** Conflict prompt design, Done event payload, Module architecture, Keyword detection precision

---

## Conflict Prompt Design

| Option | Description | Selected |
|--------|-------------|----------|
| Verdict-first prose | Answer opens with classification label, then cites passages with explanation. Easiest to test. | |
| Document-by-document breakdown | Summarizes each document separately, then concludes with verdict at the end. | ✓ |
| Structured JSON in done event | LLM prompted for machine-readable output, backend parses into structured payload fields. | |

**User's choice:** Document-by-document breakdown

---

### Verdict placement

| Option | Description | Selected |
|--------|-------------|----------|
| Verdict at the end | Model summarizes each document first, then concludes with "Verdict: X — reason." | ✓ |
| Verdict at the top | Opens with classification label, then walks through each document. | |
| No explicit label | Natural language prose with no machine-readable verdict tag. | |

**User's choice:** Verdict at the end

---

### One-silent classification

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit three-way classification | System prompt defines Contradictory / Consistent / One-Silent as exact required terms. | ✓ |
| Two-way: Conflict or No-conflict | One-Silent becomes a sub-case of no-conflict. Simpler but loses signal. | |
| You decide | Leave taxonomy to planner/executor. | |

**User's choice:** Explicit three-way classification (Contradictory / Consistent / One-Silent)

---

## Done Event Payload

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal — prose + existing citations only | Keep `{answer, citations}` shape unchanged. Document ID in prose + citations[].title. | ✓ |
| Add conflict_type field | done event gains `conflict_type: 'contradictory'|'consistent'|'one_silent'`. Frontend needs updating. | |
| Add conflict_type and documents[] | done event gains both fields. Most structured but most schema change. | |

**User's choice:** Minimal — no schema change. Phase 4 frontend works as-is.

---

## Module Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| New stream_conflict_answer() in rag.py | Second async generator in existing module; chat.py routes to it. | ✓ |
| Separate conflict.py service | New backend/app/services/conflict.py. Cleanest separation but overkill. | |
| Branch inside stream_answer() with a flag | Single function with is_conflict: bool parameter. | |

**User's choice:** New `stream_conflict_answer()` function in `rag.py`. Routing in `chat.py`.

---

## Keyword Detection Precision

| Option | Description | Selected |
|--------|-------------|----------|
| Case-insensitive substring | re.search with IGNORECASE. Catches plurals and caps. False positives degrade gracefully. | ✓ |
| Whole-word match only | Word-boundary anchors. Stricter but misses plurals; Vietnamese terms need special handling. | |
| LLM intent classifier | Pre-classification LLM call. Most accurate but adds ~1s latency per request. | |

**User's choice:** Case-insensitive substring match

---

### Keyword list scope

| Option | Description | Selected |
|--------|-------------|----------|
| Keep exactly as specified | 7 terms from REQUIREMENTS.md only. Expand in v2 based on observed misses. | ✓ |
| Add obvious synonyms | Add: compare, comparison, versus, vs, inconsistent, disagreement. | |

**User's choice:** Exactly as specified in REQUIREMENTS.md CONFLICT-01

---

## Claude's Discretion

- Exact conflict-detection system prompt wording (beyond structural decisions)
- Whether to repeat "do not cite sources not in the list" reminder in conflict prompt
- Temperature and max_tokens for conflict path
- Test fixture design for `stream_conflict_answer()`

## Deferred Ideas

None — discussion stayed within phase scope.

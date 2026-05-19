---
phase: 08-corpus-expansion
plan: "02"
subsystem: ingestion
tags: [qdrant, admin-cli, corpus-validation, health-check]
dependency_graph:
  requires: []
  provides: [backend/ingestion/validate_corpus.py]
  affects: []
tech_stack:
  added: []
  patterns: [AsyncQdrantClient scroll pagination, Counter.most_common() for sorted breakdown, payload.get() with defaults for tamper guard]
key_files:
  created:
    - backend/ingestion/validate_corpus.py
  modified: []
decisions:
  - Self-contained AsyncQdrantClient init (no import from ingest.py) per plan spec — isolation prevents dependency on ingest module-level side effects
  - SCROLL_PAGE_SIZE=256 as DoS mitigation per threat T-08-07 — avoids unbounded single-request fetch
  - payload.get() with explicit defaults throughout — mitigates T-08-08 (missing key tampering / KeyError)
  - Deterministic first-5 samples (not random) — predictable output for admin health checks
metrics:
  duration: 55s
  completed: 2026-05-05
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 0
---

# Phase 8 Plan 02: Corpus Validation CLI Summary

**One-liner:** Async corpus health CLI using Qdrant scroll pagination — reports total count, per-source breakdown (Counter.most_common), 5 deterministic sample rows, and 4-category anomaly detection.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement backend/ingestion/validate_corpus.py | 5d26371 | backend/ingestion/validate_corpus.py (created) |

## What Was Built

`backend/ingestion/validate_corpus.py` is a standalone async CLI script invoked as `python -m backend.ingestion.validate_corpus`. It:

1. Calls `qdrant.count(exact=True)` to report total passages in the "policies" collection
2. Pages through all records via `qdrant.scroll()` with SCROLL_PAGE_SIZE=256 to gather full payload data
3. Produces a per-source breakdown using `Counter.most_common()` (sorted descending by count)
4. Prints the first 5 payload rows (deterministic — no random offset) showing title, source_doc, passage_id, chunk_index, token_count
5. Detects 4 anomaly categories: zero-length text, missing required fields (any of: title, source_doc, text, passage_id, chunk_index, token_count), token_count==0, token_count>500
6. A single record can trigger multiple anomaly categories simultaneously
7. Initializes its own AsyncQdrantClient from get_settings() — does not import from ingest.py

## Acceptance Criteria Verification

All acceptance criteria passed:

- `python -m py_compile backend/ingestion/validate_corpus.py` exits 0
- `qdrant.count` appears exactly 1 time
- `qdrant.scroll` appears 1 time
- All 4 section headers present: `[total]`, `[per_source]`, `[samples]`, `[anomalies]`
- All 4 anomaly category identifiers present: `zero_length`, `missing_fields`, `token_count_zero`, `token_count_high`
- `REQUIRED_FIELDS` defined and used
- `most_common()` used for per-source sort
- `exact=True` in count call
- Zero imports from `backend.ingestion.ingest`

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — all surfaces were within the plan's threat model (admin-only stdout, read-only Qdrant access, paginated scroll, payload.get() defaults).

## Self-Check: PASSED

- File exists: backend/ingestion/validate_corpus.py — FOUND
- Commit 5d26371 — FOUND (confirmed via git log)

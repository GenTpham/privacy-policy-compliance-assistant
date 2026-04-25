---
plan: 01-06
phase: 01-infrastructure-data-ingestion
status: complete
gap_closure: true
completed: 2026-04-25
commits:
  - 864671e
  - 92bda6f
key-files:
  modified:
    - backend/ingestion/ingest.py
    - backend/ingestion/tests/test_ingestion_evals.py
---

# Plan 01-06 Summary: Gap Closure — Qdrant API & encoding_format fixes

## What Was Built

Back-ported four mechanical API fixes to `ingest.py` and `test_ingestion_evals.py`, unblocking INGEST-06 / SC3 (ingestion sanity check). The identical corrections were already applied to `rag.py` (commit b9cb972) and `main.py` (commit 4843320) in Phase 2 but had been left behind in the Phase 1 ingestion files.

## Changes Applied

### `backend/ingestion/ingest.py`
1. **`probe_embedding_dim()`** (line 72): added `encoding_format="float"` to `embeddings.create()`
2. **`embed_batch()`** (line 151): added `encoding_format="float"` to `embeddings.create()`
3. **`sanity_check()`** (lines 177–192): replaced `qdrant.search(query_vector=...)` with `qdrant.query_points(query=...)` and updated result access from `results[0].score` → `response.points[0].score`

### `backend/ingestion/tests/test_ingestion_evals.py`
4. **`test_embedding_dim_matches_collection()`** (line 93): added `encoding_format="float"`
5. **`test_rank1_sanity_check()`** (lines 121–136): added `encoding_format="float"`; replaced `qdrant_client.search(query_vector=...)` with `qdrant_client.query_points(query=...)`; updated result access to `response.points[0].score`

## Verification

- `grep "qdrant.search\|qdrant_client.search" backend/ingestion/ingest.py backend/ingestion/tests/test_ingestion_evals.py` → no output ✓
- `grep -c "encoding_format" backend/ingestion/ingest.py` → 2 ✓
- `grep -c "query_points" backend/ingestion/ingest.py` → 1 ✓
- `grep -c "query_points" backend/ingestion/tests/test_ingestion_evals.py` → 1 ✓
- `pytest -k "rate_limit or token_count"` → 2 passed ✓ (Qdrant-dependent tests require live Docker)

## Self-Check: PASSED

All must-have truths satisfied:
- `sanity_check()` uses `query_points()` — no `search()` calls remain in ingest.py ✓
- `probe_embedding_dim()` and `embed_batch()` pass `encoding_format="float"` ✓
- `test_rank1_sanity_check` uses `query_points()` — no `search()` calls remain in test file ✓
- Result access uses `response.points[0].score` throughout ✓

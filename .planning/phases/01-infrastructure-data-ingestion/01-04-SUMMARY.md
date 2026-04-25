---
phase: "01"
plan: "04"
subsystem: ingestion
tags: [chunker, ingest, qdrant, openrouter, checkpoint, dedup, tiktoken]
dependency_graph:
  requires:
    - "01-03: backend/app/core/config.py (get_settings singleton)"
  provides:
    - backend/ingestion/chunker.py (chunk_passage() + Chunk dataclass)
    - backend/ingestion/ingest.py (full ingestion entry point)
  affects:
    - "01-05: eval suite imports COLLECTION_NAME, DATASET_PATH, embed_batch from ingest.py"
    - "02+: Phase 2 retrieval uses 'policies' collection populated by this pipeline"
tech_stack:
  added:
    - tiktoken (cl100k_base tokenizer for chunk sizing)
    - openai==2.32.0 (AsyncOpenAI for Nemotron embeddings via OpenRouter)
    - qdrant-client==1.17.1 (AsyncQdrantClient for upsert and sanity check)
    - pydantic (PolicyPassage validator — field_validator for empty context guard)
  patterns:
    - SHA-256 text hashing for dedup (intra-run + cross-run via checkpoint)
    - uuid.uuid5(NAMESPACE_DNS, passage_id:chunk_index) for stable, deterministic point IDs
    - Exponential backoff on 429: wait = 2^attempt seconds, max 5 retries
    - Checkpoint saved AFTER confirmed upsert (wait=True) — never before
    - Sanity check: embed first passage, assert rank-1 score > 0.99
key_files:
  created:
    - backend/ingestion/chunker.py
    - backend/ingestion/ingest.py
  modified: []
decisions:
  - "D-01: DATASET_PATH = dataset/json/train/policy_qa_train.json (train split only)"
  - "D-02: SHA-256 of chunk.text for dedup — intra-run (seen set) + cross-run (checkpoint)"
  - "D-03: CHECKPOINT_PATH = ingestion_checkpoint.json — saved after each confirmed batch"
  - "D-04: BATCH_SIZE = 50, upsert(wait=True) — conservative for free-tier rate limits"
  - "D-05: BATCH_SLEEP_SECONDS = 3 — polite inter-batch delay"
  - "D-08/D-09: ensure_collection() is idempotent — checks existing collection params"
  - "D-10: COSINE distance guard — RuntimeError if metric != COSINE post-creation or on existing"
  - "Embedding dim probed via live API call (probe_embedding_dim) — never hardcoded"
  - "uuid.uuid5 for stable point IDs — same passage+chunk_index always maps to same UUID"
metrics:
  duration_seconds: 90
  completed_date: "2026-04-24"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 01 Plan 04: Text Chunker & Ingestion Pipeline Summary

**One-liner:** 400-token chunker with separator-hierarchy splitting and 50-token overlap, plus full async ingestion pipeline with SHA-256 dedup, checkpoint resumability, exponential rate-limit backoff, and a rank-1 sanity check asserting score > 0.99.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create backend/ingestion/chunker.py | 7e41efb | backend/ingestion/chunker.py |
| 2 | Create backend/ingestion/ingest.py | 7e41efb | backend/ingestion/ingest.py |

## Chunker Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| `MAX_TOKENS` | 400 | Target chunk size (cl100k_base) |
| `OVERLAP_TOKENS` | 50 | ~12.5% overlap — preserves clause continuity |
| `SEPARATORS` | `["\n\n", "\n", ". ", " "]` | Priority order: paragraph → sentence → word |
| Fast path | `token_count <= MAX_TOKENS` | Most dataset passages take this path (single chunk) |

## Chunk Dataclass Fields

| Field | Type | Source |
|-------|------|--------|
| `text` | `str` | Chunk text content |
| `title` | `str` | Dataset record `title` field |
| `source_doc` | `str` | Set to `title` — used for citations in Phase 2 |
| `passage_id` | `str` | Dataset record `id` field (cast to str) |
| `chunk_index` | `int` | 0-based index within original passage |
| `token_count` | `int` | Token count of this chunk (tiktoken cl100k_base) |

## Ingestion Pipeline Decisions (D-01 through D-14)

| Decision | Status | Implementation |
|----------|--------|----------------|
| D-01: Train split only | Applied | `DATASET_PATH = Path("dataset/json/train/policy_qa_train.json")` |
| D-02: SHA-256 dedup | Applied | `hashlib.sha256(chunk.text.encode()).hexdigest()` — intra-run (seen set) + cross-run (checkpoint) |
| D-03: Checkpoint resumability | Applied | `ingestion_checkpoint.json` saved after each `upsert(wait=True)` confirms |
| D-04: Batch size 50 + wait=True | Applied | `BATCH_SIZE = 50`, `qdrant.upsert(..., wait=True)` |
| D-05: 3s inter-batch sleep | Applied | `await asyncio.sleep(BATCH_SLEEP_SECONDS)` after every batch |
| D-08: Belt-and-suspenders collection | Applied | `ensure_collection()` runs at ingest start, not only at API startup |
| D-09: Idempotent collection | Applied | Skips creation if exists; still runs COSINE guard |
| D-10: COSINE distance immutable | Applied | Guard runs post-creation AND on existing collections |
| Embedding dim never hardcoded | Applied | `probe_embedding_dim()` — live API call to Nemotron |
| Stable point IDs | Applied | `uuid.uuid5(NAMESPACE_DNS, f"{passage_id}:{chunk_index}")` |
| Pydantic corpus validation | Applied | `PolicyPassage` with `context_not_empty` field_validator |
| C6 token count guard | Applied | Warns if `_count_tokens(chunk.text) > MAX_TOKENS_WARN (400)` |

## AI-SPEC §6 Guardrails Implemented

| Guardrail | Trigger | Intervention |
|-----------|---------|-------------|
| Empty corpus | 0 valid passages after Pydantic validation | `ValueError` — script exits |
| Dimension mismatch | Existing collection dim != probed Nemotron dim | `RuntimeError` with delete/re-ingest instructions |
| Distance metric wrong | Collection distance != COSINE | `RuntimeError` with delete/re-ingest instructions |
| Upsert failure | `result.status != UpdateStatus.COMPLETED` | `RuntimeError` — checkpoint saved to last good batch |
| API key absent | `openrouter_api_key` missing from `.env` | `ValidationError` from `get_settings()` at module import |

## Deviations from Plan

None — plan executed exactly as specified. All constants, guardrails, and pipeline steps match the plan.

## Self-Check: PASSED

- `backend/ingestion/chunker.py`: FOUND
- `backend/ingestion/ingest.py`: FOUND
- `MAX_TOKENS = 400`: FOUND in chunker.py
- `OVERLAP_TOKENS = 50`: FOUND in chunker.py
- `SEPARATORS = ["\n\n", "\n", ". ", " "]`: FOUND in chunker.py
- `BATCH_SIZE = 50`: FOUND in ingest.py
- `wait=True`: FOUND in ingest.py
- `save_checkpoint`: FOUND in ingest.py (called after confirmed upsert)
- `sanity_check`: FOUND in ingest.py
- `score > 0.99`: FOUND in ingest.py
- `Distance.COSINE` (×3): FOUND in ingest.py (creation + 2 guards)
- `UpdateStatus.COMPLETED`: FOUND in ingest.py
- `sha256`: FOUND in ingest.py
- `load_checkpoint` / `save_checkpoint`: FOUND in ingest.py
- `DATASET_PATH.*train`: FOUND in ingest.py

# Phase 8 — Pattern Map

**Generated:** 2026-05-05
**Phase:** 08-corpus-expansion

## New Files → Closest Analogs

### backend/ingestion/ingest_doc.py
**Analog:** `backend/ingestion/ingest.py`
**Role:** CLI entry point + async ingestion pipeline for a single document

Key patterns to replicate from `ingest.py`:
- Module-level constants: `COLLECTION_NAME = "policies"`, `BATCH_SIZE = 50`, `BATCH_SLEEP_SECONDS = 3`, `EMBED_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2"`
- Client initialization (same 10-line block for `openrouter` + `qdrant`):
  ```python
  settings = get_settings()
  openrouter = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=settings.openrouter_api_key, ...)
  qdrant = AsyncQdrantClient(url=f"http://{settings.qdrant_host}:{settings.qdrant_port}", ...)
  ```
- `probe_embedding_dim()` → call before `ensure_collection(dim)`
- `ensure_collection(dim)` → already guards dimension mismatch and distance metric
- `embed_batch(texts, retries=5)` → exponential backoff on 429, sort by index
- UUID5 point ID: `str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{passage_id}:{chunk_index}"))`
- PointStruct payload schema: `title`, `source_doc`, `passage_id`, `text`, `chunk_index`, `token_count`
- Upsert with `wait=True` + `UpdateStatus.COMPLETED` guard
- `asyncio.sleep(BATCH_SLEEP_SECONDS)` after each batch
- `if __name__ == "__main__": asyncio.run(main())`

**New additions vs analog:**
- argparse CLI (`file` positional + `--title` required + `--dry-run` flag)
- pypdf extraction: `from pypdf import PdfReader`
- `file_type` field added to payload: `"pdf"` or `"txt"`
- Dry-run branch: UUID5 existence check via `qdrant.retrieve(ids=...)` instead of upsert
- passage_id = `filepath.stem` (not record `id` from JSON)

---

### backend/ingestion/validate_corpus.py
**Analog:** `backend/eval/run_experiment.py` (async script that queries Qdrant/backend)
**Secondary analog:** `backend/ingestion/ingest.py` (same Qdrant client initialization)

Key patterns from `run_experiment.py`:
- `asyncio.run(main())` entry point
- `AsyncQdrantClient` usage
- Structured print output with `[section]` prefix labels (matches ingest.py style)

Key patterns from `ingest.py`:
- Same client initialization block
- `COLLECTION_NAME = "policies"` constant
- `get_settings()` for Qdrant connection params

**New APIs (not in existing code):**
- `await qdrant.count(collection_name=..., exact=True)` → `CountResult.count`
- `await qdrant.scroll(collection_name=..., limit=100, offset=None, with_payload=True, with_vectors=False)` → `(records, next_offset)`
- Pagination loop: `while next_offset is not None: ...`

---

### requirements.txt
**Analog:** existing `requirements.txt`
**Change:** Add `pypdf` on its own line (pure Python, no version pin needed initially)

---

## Established Conventions to Follow

| Convention | Source | Apply to |
|------------|--------|----------|
| `[section]` prefix on all print statements | `ingest.py` | All print output in both new scripts |
| Module-level singletons for clients | `ingest.py` | Both scripts (or shared module) |
| `asyncio.run(main())` entry point | `ingest.py`, `run_experiment.py` | Both scripts |
| `get_settings()` for all config | `config.py` | Both scripts |
| `wait=True` on all Qdrant upserts | `ingest.py` | `ingest_doc.py` upsert calls |
| `UpdateStatus.COMPLETED` guard after upsert | `ingest.py` | `ingest_doc.py` upsert calls |
| Exponential backoff on 429 | `embed_batch()` | Reuse same function |

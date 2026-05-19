# Phase 8: Corpus Expansion - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver two admin CLI scripts that let an admin grow the Qdrant "policies" collection:

1. **`ingest_doc.py`** — ingest a single PDF or TXT policy document. Extracts text, chunks it with the existing chunker, deduplicates by content hash, embeds with Nemotron, and upserts to Qdrant.
2. **`validate_corpus.py`** — report corpus health: total passage count, per-source breakdown, 5 sample payload rows, and flagged anomalies.

**Does NOT include:** UI upload, real-time ingestion, OCR for scanned PDFs, or any frontend changes — those are deferred.

</domain>

<decisions>
## Implementation Decisions

### PDF Extraction Library
- **D-01:** Use `pypdf` (add to `requirements.txt`). Pure Python, no C dependencies, easy Docker build. API: `PdfReader(path).pages[i].extract_text()`.
- **D-02:** Concatenate all pages with double newline (`\n\n`) into one text blob, then pass to `chunk_passage()`. Chunker's separator hierarchy (`\n\n` → `\n` → `. `) handles natural boundaries. No page-level splitting.
- **D-03:** Hard fail with a clear error if the entire document yields zero text (scanned/image PDF, encrypted, corrupted). Error message: `"No text extracted — PDF may be scanned/image-based or encrypted. OCR is not supported."` Do not silently ingest empty.

### Document Chunking Strategy
- **D-04:** `passage_id` = filename stem (e.g., `"google-privacy-policy"` from `google-privacy-policy.pdf`). Stable, readable, traceable to source file. Dedup by content hash is still the dedup mechanism — passage_id is metadata.
- **D-05:** Add `file_type` field to Qdrant payload for new-document chunks: `"pdf"` or `"txt"`. Existing dataset-ingested chunks have no `file_type` field (no migration needed for them). New chunks only.
- **D-06:** TXT files use the same pipeline as PDFs — read entire file, pass full text to `chunk_passage()`. No paragraph-splitting assumption.

### CLI Design
- **D-07:** Separate module `backend/ingestion/ingest_doc.py`. Invoked as:
  ```
  python -m backend.ingestion.ingest_doc path/to/file.pdf --title "Google Privacy Policy"
  ```
  Existing `ingest.py` (dataset batch job) stays untouched.
- **D-08:** `--title` is a **required** argument. It sets both `title` and `source_doc` in the Qdrant payload. This becomes the Phase 9 source-filter identifier — admin must name it explicitly rather than risk filename-derived names like `"policy_final_v2"`.
- **D-09:** `--dry-run` flag supported. In dry-run mode: extract text, chunk, compute hashes, check which are already in Qdrant, then print `"Would ingest N chunks (M already indexed — would skip)"` without writing anything. No Qdrant upserts.

### Validation Script
- **D-10:** Separate script `backend/ingestion/validate_corpus.py`. Invoked as:
  ```
  python -m backend.ingestion.validate_corpus
  ```
  Validates the entire "policies" collection regardless of how data was ingested.
- **D-11:** Reports all four sections:
  1. Total passage count (total Qdrant points in "policies")
  2. Per-source breakdown — count by `source_doc` payload field, sorted descending
  3. 5 random sample payload rows — shows `title`, `source_doc`, `passage_id`, `chunk_index`, `token_count`
  4. Anomaly flags — check for: zero-length `text`, missing required fields (`title`, `source_doc`, `text`), `token_count = 0` or `token_count > 500`. Print count + first example of each anomaly type found.

### Claude's Discretion
- Exact argparse error messages and help strings
- Whether to use `qdrant.scroll()` or `qdrant.count()` for dry-run dedup check (scroll is needed to compare hashes, but count suffices for total)
- Output formatting (plain text with `[section]` headers — match existing `ingest.py` style)
- Whether `validate_corpus.py` uses `qdrant.scroll()` with pagination or `qdrant.query_points()` for sampling

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Ingestion Pipeline (extend, don't rewrite)
- `backend/ingestion/ingest.py` — full dataset ingestion pipeline; `embed_batch()`, `ensure_collection()`, `probe_embedding_dim()`, UUID5 point ID pattern, BATCH_SIZE=50, BATCH_SLEEP_SECONDS=3, checkpoint pattern. `ingest_doc.py` reuses these utilities.
- `backend/ingestion/chunker.py` — `chunk_passage()` and `Chunk` dataclass. Reuse as-is. `_count_tokens()` is also importable.

### Config
- `backend/app/core/config.py` — `Settings` class with `get_settings()` singleton. Has `qdrant_host`, `qdrant_port`, `qdrant_api_key`, `openrouter_api_key`. Use for client initialization.

### Requirements
- `.planning/REQUIREMENTS.md` — CORP-01 and CORP-02 are the requirements this phase must close
- `.planning/PROJECT.md` §Key Decisions — existing dedup pattern, score_threshold, qdrant:v1.17.1 pin

### No external ADRs — all decisions captured above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `embed_batch(texts, retries=5)` in `ingest.py` — exponential backoff on 429s; import directly
- `chunk_passage(text, passage_id, title, source_doc)` in `chunker.py` — takes full text; works for entire-doc concatenation
- `ensure_collection(dim)` in `ingest.py` — dimension mismatch guard, distance metric guard; call before upsert
- `probe_embedding_dim()` in `ingest.py` — live API call to get Nemotron dim; needed for ensure_collection
- `AsyncQdrantClient` + `AsyncOpenAI` initialization pattern in `ingest.py` — copy the same client setup

### Established Patterns
- SHA-256 content-hash dedup: `hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()` — same dedup key for new chunks
- UUID5 point IDs: `uuid.uuid5(uuid.NAMESPACE_DNS, f"{passage_id}:{chunk_index}")` — same ID scheme
- Qdrant payload schema (existing): `title`, `source_doc`, `passage_id`, `text`, `chunk_index`, `token_count`. New chunks add `file_type`.
- Upsert with `wait=True` + `UpdateStatus.COMPLETED` guard — preserve this for correctness
- Rate-limit delay: `asyncio.sleep(BATCH_SLEEP_SECONDS)` after each batch
- COLLECTION_NAME = `"policies"` — hardcoded constant; keep consistent

### Integration Points
- `ingest_doc.py` connects to same Qdrant collection as `ingest.py` and the live RAG service — no schema migration, just additive upsert
- Phase 9 source filter will use `source_doc` payload field — the `--title` arg value becomes a filter key; naming matters

</code_context>

<specifics>
## Specific Ideas

- Dry-run output format: match existing `[section]` logging style from `ingest.py`, e.g. `[dry_run] Would ingest 42 chunks (8 already indexed — would skip)`
- Anomaly threshold for token_count: flag > 500 (existing MAX_TOKENS_WARN = 400, but 500 is a reasonable hard-anomaly threshold vs the soft warning)
- validate_corpus.py sample: use `qdrant.scroll()` with `limit=5` and a random offset, or just take the first 5 — deterministic is fine for a CLI health check

</specifics>

<deferred>
## Deferred Ideas

- OCR support for scanned PDFs — would require `tesseract` or `pytesseract`; not needed for v2.0 admin workflow
- End-user PDF upload via chat UI — explicitly out of scope (v3.0, CORP-03/04)
- Per-document ingestion history log (track what was ingested when) — useful but not required by CORP-01/02
- `validate_corpus.py` --source filter flag (validate one source only) — deferred; full-collection validation is sufficient for v2.0

</deferred>

---

*Phase: 08-corpus-expansion*
*Context gathered: 2026-05-05*

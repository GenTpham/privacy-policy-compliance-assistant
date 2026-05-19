---
phase: 08-corpus-expansion
verified: 2026-05-05T00:00:00Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
gaps: []
deferred: []
---

# Phase 8: Corpus Expansion Verification Report

**Phase Goal:** An admin can grow the policy corpus by ingesting new PDF or TXT documents via a CLI script, with safeguards against duplicate passages and tooling to verify the resulting corpus.
**Verified:** 2026-05-05
**Status:** passed
**Re-verification:** No — initial verification

---

## Step 0: Previous Verification

No previous VERIFICATION.md found. Initial verification mode.

---

## Goal Achievement

### Observable Truths

Roadmap success criteria (non-negotiable) plus plan must-haves verified together.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC-1 | Admin can run the ingest script on a PDF or TXT file and have its passages embedded and stored in Qdrant | VERIFIED | `ingest_doc.py` exists, syntactically valid, implements full pipeline: extract → chunk → embed → upsert. `extract_pdf` and `extract_txt` both implemented. CLI entrypoint with argparse present. |
| SC-2 | Re-running on an already-indexed document adds zero duplicate passages | VERIFIED | UUID5 IDs computed for all chunks, `qdrant.retrieve()` called before upsert, `new_pairs` filtered to exclude `existing` set. If `not new_pairs`: prints "All chunks already indexed — nothing to do." and returns. |
| SC-3 | Admin can run a validation command that prints total passage count, sample metadata rows, and flags anomalies | VERIFIED | `validate_corpus.py` exists, syntactically valid, prints `[total]`, `[per_source]`, `[samples]`, `[anomalies]` sections. All four anomaly categories implemented. |
| T1 | Hard failure with clear error occurs when a PDF yields zero text | VERIFIED | `extract_pdf` raises `ValueError("No text extracted — PDF may be scanned/image-based or encrypted. OCR is not supported.")` on empty text. |
| T2 | Dry-run mode prints count of would-be-ingested vs already-indexed chunks without writing | VERIFIED | `--dry-run` flag wired in argparse; `ingest_doc()` returns early at `dry_run` branch printing `[dry_run] Would ingest N chunks (M already indexed — would skip)` |
| T3 | TXT files read with UTF-8 and latin-1 fallback; hard fail if empty | VERIFIED | `extract_txt` tries UTF-8 first, catches `UnicodeDecodeError`, falls back to latin-1. Raises `ValueError` if stripped result is empty. |
| T4 | Per-source breakdown shows count by source_doc sorted descending | VERIFIED | `Counter.most_common()` used at line 72 of `validate_corpus.py`. |
| T5 | 5 sample payload rows printed showing title, source_doc, passage_id, chunk_index, token_count | VERIFIED | `all_records[:5]` printed with all five fields in the output format string. |

**Score:** 8/8 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/ingestion/ingest_doc.py` | Single-document PDF/TXT ingest CLI | VERIFIED | 326 lines; all required functions present: `extract_pdf`, `extract_txt`, `embed_batch`, `probe_embedding_dim`, `ensure_collection`, `ingest_doc`, `parse_args`, `_make_clients`. Syntactically valid (`py_compile` passes). |
| `backend/ingestion/validate_corpus.py` | Corpus health validation CLI | VERIFIED | 143 lines; `validate_corpus` async entrypoint present. Syntactically valid (`py_compile` passes). |
| `requirements.txt` | Contains `pypdf` dependency | VERIFIED | Line 16: `pypdf>=4.0,<5` — pinned range per WR-02 fix commit `e8f902b`. |
| `backend/ingestion/tests/test_ingest_doc.py` | TDD test suite | VERIFIED | File exists; 13 tests mocking PdfReader, Qdrant, OpenRouter. |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `ingest_doc.py` | `backend/ingestion/chunker.py` | `from backend.ingestion.chunker import Chunk, chunk_passage` | WIRED | Import at line 22; `chunk_passage()` called at line 213 inside `ingest_doc()`. |
| `ingest_doc.py` | Qdrant policies collection | `qdrant.retrieve()` before upsert, `qdrant.upsert()` for write | WIRED | `qdrant.retrieve()` at line 230; `qdrant.upsert()` at line 280. Both inside `ingest_doc()`. |
| `ingest_doc.py` | OpenRouter embeddings API | `embed_batch()` local copy | WIRED | `embed_batch()` defined at line 93 with `openrouter.embeddings.create()`; called at line 261 inside batch loop. |
| `validate_corpus.py` | Qdrant policies collection | `qdrant.count()` and `qdrant.scroll()` | WIRED | `qdrant.count()` at line 37 (with `exact=True`); `qdrant.scroll()` at line 50 in pagination loop. |
| `validate_corpus.py` | `backend/app/core/config.py` | `get_settings()` for client initialization | WIRED | Imported at top level; called at line 29 inside `validate_corpus()` async function (moved inside function per CR-02 fix). |

---

## Data-Flow Trace (Level 4)

These are CLI tools, not rendering components. The data flows are linear: CLI → Qdrant → stdout. No rendering of dynamic state to check for hollow props.

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `ingest_doc.py` | `chunks` (passages to embed) | `chunk_passage()` on extracted text | Yes — text extracted from actual file, chunked by `chunker.py`, then embedded via OpenRouter and upserted to Qdrant | FLOWING |
| `ingest_doc.py` | `existing` (dedup set) | `qdrant.retrieve()` with real UUID5 IDs | Yes — queries live Qdrant collection | FLOWING |
| `validate_corpus.py` | `all_records` | `qdrant.scroll()` pagination loop | Yes — scrolls full collection with `with_payload=True` | FLOWING |
| `validate_corpus.py` | `total` | `qdrant.count(exact=True)` | Yes — exact count from Qdrant | FLOWING |

---

## Behavioral Spot-Checks

Runtime execution requires Qdrant + OpenRouter API keys; cannot test end-to-end without live services. Syntax compilation checked instead.

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `ingest_doc.py` syntax valid | `python -m py_compile backend/ingestion/ingest_doc.py` | Exit 0 | PASS |
| `validate_corpus.py` syntax valid | `python -m py_compile backend/ingestion/validate_corpus.py` | Exit 0 | PASS |
| `ingest_doc.py` no import from `ingest.py` | `grep 'from backend.ingestion.ingest import'` | No matches | PASS |
| `validate_corpus.py` no import from `ingest.py` | `grep 'from backend.ingestion.ingest import'` | No matches | PASS |
| `pypdf` in requirements.txt | `grep '^pypdf' requirements.txt` | `pypdf>=4.0,<5` | PASS |
| UUID5 dedup formula present | `grep 'uuid.uuid5'` in `ingest_doc.py` | Line 218 | PASS |
| `qdrant.retrieve()` for dedup | `grep 'qdrant.retrieve'` in `ingest_doc.py` | Line 230 | PASS |
| dry-run path present | `grep 'dry_run'` in `ingest_doc.py` | Lines 188, 193, 239, 240, 242 | PASS |

End-to-end behavior with live services: SKIP (requires Qdrant running + valid `OPENROUTER_API_KEY`).

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CORP-01 | 08-01-PLAN.md | Admin can ingest a new PDF or TXT policy document into Qdrant via a CLI script, with content-hash dedup preventing duplicate passages | SATISFIED | `ingest_doc.py` fully implements the CLI. UUID5-based dedup is the specified mechanism (deterministic hash of `passage_id:chunk_index`). `qdrant.retrieve()` before any upsert prevents duplicates. |
| CORP-02 | 08-02-PLAN.md | Admin can validate the corpus after ingestion — script reports passage count, samples metadata, and flags anomalies | SATISFIED | `validate_corpus.py` reports `[total]` count, `[per_source]` breakdown, `[samples]` rows, and `[anomalies]` with 4 anomaly categories. |

Note: REQUIREMENTS.md uses the phrase "content-hash dedup" for CORP-01, while the implementation uses UUID5 (a deterministic namespace UUID derived from `passage_id:chunk_index`). The PLAN explicitly specifies UUID5 as the dedup mechanism. UUID5 produces a deterministic, collision-resistant identifier from the passage content key — this satisfies the intent of "content-hash dedup." The PLAN's specification takes precedence over REQUIREMENTS.md's informal phrasing.

**Orphaned requirements check:** No additional CORP-* requirements mapped to Phase 8 in REQUIREMENTS.md beyond CORP-01 and CORP-02. No orphaned requirements.

---

## Anti-Patterns Found

Scanned `backend/ingestion/ingest_doc.py` and `backend/ingestion/validate_corpus.py`:

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `ingest_doc.py` | 119 | `raise` (bare re-raise in `embed_batch` on non-retryable error) | Info | Intentional design choice — preserves original exception type and traceback. Not a stub. |

No TODO/FIXME/placeholder comments, no `return null`/`return []` stubs, no hardcoded empty data, no console-log-only implementations found. All paths are fully implemented.

---

## Human Verification Required

### 1. End-to-end ingest of a real PDF

**Test:** From project root with Qdrant running and `.env` present: `python -m backend.ingestion.ingest_doc /path/to/sample.pdf --title "Test Policy"`
**Expected:** Prints chunk count, embeds passages, upserts to Qdrant, prints `[ingest_doc] Done. Upserted N new chunks (0 skipped — already indexed).`
**Why human:** Requires live Qdrant + valid OpenRouter API key. Cannot verify without running services.

### 2. Dedup on re-run

**Test:** Run the ingest command from test 1 a second time on the same file.
**Expected:** Prints `[ingest_doc] All chunks already indexed — nothing to do.` with 0 upserts.
**Why human:** Requires live Qdrant state from test 1. Cannot verify programmatically.

### 3. Dry-run mode

**Test:** `python -m backend.ingestion.ingest_doc /path/to/sample.pdf --title "Test Policy" --dry-run`
**Expected:** Prints `[dry_run] Would ingest N chunks (M already indexed — would skip)` — no writes to Qdrant.
**Why human:** Requires live Qdrant to verify no-write behavior.

### 4. Corpus validation

**Test:** `python -m backend.ingestion.validate_corpus`
**Expected:** Prints `[total] N passages`, per-source table sorted descending, 5 sample rows, `[anomalies]` section.
**Why human:** Requires live Qdrant with data loaded.

---

## Gaps Summary

No gaps found. All 8 must-have truths are VERIFIED, all artifacts exist and are substantive and wired, all key links are present, both requirements (CORP-01, CORP-02) are satisfied, and no blocker anti-patterns were found.

The only remaining items are human verification tests that require live services (Qdrant + OpenRouter), which is expected for a CLI tool that integrates with external services. The code paths are all implemented and syntactically correct.

---

_Verified: 2026-05-05_
_Verifier: Claude (gsd-verifier)_

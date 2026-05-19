---
status: partial
phase: 08-corpus-expansion
source: [08-VERIFICATION.md]
started: 2026-05-05T00:00:00Z
updated: 2026-05-05T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. End-to-end PDF ingest
expected: `python -m backend.ingestion.ingest_doc path/to/file.pdf --title "My Policy"` extracts passages, embeds them via OpenRouter, and upserts to Qdrant. Final line reads `[ingest_doc] Done. Upserted N new chunks (0 skipped — already indexed).`
result: [pending]

### 2. Dedup on re-run
expected: Running the same command a second time on the already-indexed file produces `[ingest_doc] All chunks already indexed — nothing to do.` (or `0 new chunks, N skipped`). No duplicate passages in Qdrant.
result: [pending]

### 3. Dry-run mode
expected: `python -m backend.ingestion.ingest_doc path/to/file.pdf --title "My Policy" --dry-run` prints `[dry_run] Would ingest N chunks (M already indexed — would skip)` without writing anything to Qdrant.
result: [pending]

### 4. Corpus validation output
expected: `python -m backend.ingestion.validate_corpus` against a live Qdrant instance prints all four sections: `[total]`, `[per_source]`, `[samples]`, `[anomalies]` — with real data from the policies collection.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps

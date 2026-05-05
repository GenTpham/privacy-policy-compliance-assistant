---
phase: 08-corpus-expansion
plan: "01"
subsystem: ingestion
tags: [pypdf, qdrant, openrouter, embedding, cli, pdf, txt, dedup, uuid5]

# Dependency graph
requires:
  - phase: 01-ingestion
    provides: "Qdrant 'policies' collection with COSINE distance, chunk_passage, ingest.py patterns"
  - phase: 06-docker-compose
    provides: "Docker Compose config, Settings/get_settings, env config pattern"
provides:
  - "backend/ingestion/ingest_doc.py: single-document PDF/TXT ingest CLI with dedup"
  - "pypdf dependency in requirements.txt"
affects: [09-ux-enhancements, corpus-expansion, admin-tooling]

# Tech tracking
tech-stack:
  added: [pypdf]
  patterns:
    - "Self-contained clients in CLI scripts (no module-level singletons from ingest.py)"
    - "UUID5 dedup via qdrant.retrieve() before upsert — idempotent by design"
    - "probe_embedding_dim + ensure_collection parameterized on client instance"
    - "TDD: failing tests → implementation → all green, committed separately"

key-files:
  created:
    - backend/ingestion/ingest_doc.py
    - backend/ingestion/tests/test_ingest_doc.py
  modified:
    - requirements.txt

key-decisions:
  - "Self-contained clients in ingest_doc.py — do not import module-level singletons from ingest.py to avoid side effects from top-level Settings call"
  - "UUID5-based dedup matches ingest.py formula exactly (uuid.NAMESPACE_DNS, passage_id:chunk_index)"
  - "file_type field added to Qdrant payload (pdf/txt) as new metadata field for corpus analytics"
  - "probe_embedding_dim/ensure_collection take client as parameter (not module globals) for testability"

patterns-established:
  - "Admin CLI scripts: self-contained clients, argparse with required --title, dry-run flag"
  - "Dedup pattern: compute all UUID5 IDs → qdrant.retrieve() → filter → upsert only new"

requirements-completed: [CORP-01]

# Metrics
duration: 15min
completed: 2026-05-05
---

# Phase 8 Plan 01: Corpus Expansion — Single-Document Ingest CLI Summary

**Admin CLI `ingest_doc.py` for idempotent PDF/TXT ingestion into Qdrant with UUID5 dedup, dry-run mode, and hard-fail on empty/encrypted documents**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-05T16:27:00Z
- **Completed:** 2026-05-05T16:42:00Z
- **Tasks:** 2 (+ TDD RED commit)
- **Files modified:** 3

## Accomplishments
- Delivered `backend/ingestion/ingest_doc.py` — admin CLI for ingesting single PDF or TXT policy documents
- UUID5-based idempotent dedup (retrieve before upsert) prevents duplicate passages across runs
- Dry-run mode previews chunk count without writing to Qdrant
- Hard-fail on empty/encrypted/zero-text PDF and empty TXT files (T-08-01)
- Exponential backoff on 429 rate limits (T-08-02, retries=5 cap)
- `file_type` field ("pdf"/"txt") added to Qdrant payload for corpus analytics
- Full TDD cycle: 13 failing tests (RED) → implementation → all 13 passing (GREEN)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add pypdf to requirements.txt** - `a659f01` (chore)
2. **Task 2 RED: Failing tests for ingest_doc CLI** - `19647d2` (test)
3. **Task 2 GREEN: Implement ingest_doc.py** - `df1531d` (feat)

## Files Created/Modified
- `backend/ingestion/ingest_doc.py` - Single-document PDF/TXT ingest CLI with dedup, dry-run, rate-limit backoff
- `backend/ingestion/tests/test_ingest_doc.py` - 13 TDD tests covering extract_pdf, extract_txt, ingest_doc, parse_args
- `requirements.txt` - Added `pypdf` (PDF text extraction)

## Decisions Made
- Self-contained clients in `ingest_doc.py` — do not import module-level singletons from `ingest.py` to avoid side effects from top-level `Settings()` call at import time
- `probe_embedding_dim` and `ensure_collection` are parameterized on client instances (not module globals) for testability and isolation
- `file_type` payload field added as new metadata not present in original `ingest.py` — enables future corpus filtering by document type
- UUID5 formula matches `ingest.py` exactly (`uuid.NAMESPACE_DNS`, `f"{passage_id}:{chunk_index}"`) ensuring cross-script dedup consistency

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pypdf not installed in test environment**
- **Found during:** Task 2 GREEN phase (first test run)
- **Issue:** `pypdf` not installed in local Python environment; tests failed with `ModuleNotFoundError: No module named 'pypdf'`
- **Fix:** Ran `python -m pip install pypdf` (and also tiktoken, qdrant-client, openai, pydantic-settings for import chain)
- **Files modified:** None (runtime environment only; pypdf already in requirements.txt)
- **Verification:** All 13 tests passed after install
- **Committed in:** Not a code change — environment setup only

---

**Total deviations:** 1 auto-fixed (1 blocking — environment setup)
**Impact on plan:** Minor environment issue only. No code changes required. All plan requirements delivered as specified.

## Issues Encountered
- pypdf and transitive dependencies not installed in the test Python environment — resolved by pip install during GREEN phase. No impact on deliverables.

## Known Stubs
None — all functions are fully implemented with real logic.

## Threat Flags
None — no new network endpoints or trust boundaries introduced beyond what the plan's threat model covers.

## User Setup Required
None — no external service configuration required. Admin runs `python -m backend.ingestion.ingest_doc path/to/file.pdf --title "Policy Name"` from project root with Qdrant running and `.env` present.

## Next Phase Readiness
- `backend/ingestion/ingest_doc.py` is ready for admin use to expand the corpus with new PDF/TXT policy documents
- Phase 8 Plan 02 can proceed (source filter UI or score display)
- No blockers

## Self-Check: PASSED
- `backend/ingestion/ingest_doc.py`: exists
- `backend/ingestion/tests/test_ingest_doc.py`: exists (13 tests, all passing)
- `requirements.txt`: contains `pypdf`
- Commits: a659f01 (chore), 19647d2 (test), df1531d (feat) — all confirmed in git log

---
*Phase: 08-corpus-expansion*
*Completed: 2026-05-05*

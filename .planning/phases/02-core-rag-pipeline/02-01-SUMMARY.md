---
phase: 02-core-rag-pipeline
plan: 01
subsystem: testing
tags: [pytest, pytest-asyncio, qdrant-client, openai, asyncmock, tdd, wave0]

# Dependency graph
requires:
  - phase: 01-infra-ingestion
    provides: backend/app package structure, AsyncQdrantClient usage patterns, ingestion test style
provides:
  - pytest.ini with asyncio_mode=auto (no per-test @pytest.mark.asyncio needed)
  - backend/app/tests/ package with conftest.py providing mock_openrouter, mock_qdrant, sample_scored_point
  - 10 test stubs in test_rag.py covering RAG-01-07 and CITE-01-03
  - 2 HTTP-level test stubs in test_chat_endpoint.py
affects:
  - 02-core-rag-pipeline (Wave 1 plans 02-02, 02-03 implement against these stubs)

# Tech tracking
tech-stack:
  added: [pytest-asyncio (asyncio_mode=auto), httpx (test transport)]
  patterns:
    - Function-scoped AsyncMock fixtures (no scope=module to prevent state bleed)
    - pytest.skip("stub — implemented in Wave 1") pattern for Nyquist-compliant pre-implementation stubs
    - MagicMock(spec=AsyncOpenAI) and MagicMock(spec=AsyncQdrantClient) for typed mock clients

key-files:
  created:
    - pytest.ini
    - backend/app/tests/__init__.py
    - backend/app/tests/conftest.py
    - backend/app/tests/test_rag.py
    - backend/app/tests/test_chat_endpoint.py
  modified: []

key-decisions:
  - "Function-scoped fixtures only — module scope causes test-order-dependent state bleed with async mocks"
  - "pytest.skip('stub') not assert False — CI never blocked by pre-implementation stubs (T-02-W0-02)"
  - "asyncio_mode=auto in pytest.ini — existing ingestion tests using explicit @pytest.mark.asyncio remain valid (no-op with auto)"

patterns-established:
  - "Stub pattern: async def test_foo(fixture_args): pytest.skip('stub — implemented in Wave 1')"
  - "Mock fixture pattern: MagicMock(spec=RealClass) with AsyncMock for coroutine methods"
  - "sample_scored_point payload keys: text, title, source_doc, passage_id (mirrors Phase 1 ingestion schema)"

requirements-completed: [RAG-01, RAG-02, RAG-03, RAG-04, RAG-05, RAG-06, RAG-07, CITE-01, CITE-02, CITE-03]

# Metrics
duration: 8min
completed: 2026-04-24
---

# Phase 2 Plan 01: Wave 0 Test Infrastructure Summary

**pytest infrastructure with 12 collectable stubs defining the RAG and citation contract before Wave 1 implementation — asyncio_mode=auto, three function-scoped mock fixtures, 10 RAG stubs and 2 HTTP endpoint stubs, all skipping cleanly**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-24T08:33:20Z
- **Completed:** 2026-04-24T08:42:14Z
- **Tasks:** 4
- **Files modified:** 5

## Accomplishments

- pytest.ini sets `asyncio_mode = auto` so all async tests run without per-test decorators
- conftest.py provides three function-scoped fixtures: `mock_openrouter` (AsyncOpenAI mock with 128-dim embed), `mock_qdrant` (AsyncQdrantClient mock returning []), `sample_scored_point` (typed payload dict matching ingestion schema)
- test_rag.py: 10 stubs covering RAG-01–07 (embed model, retrieve params, prompt format, abstain wording, SSE delta, history slicing, empty retrieval) and CITE-01–03 (citation fields, done event shape, fabricated citation stripping)
- test_chat_endpoint.py: 2 HTTP stubs (SSE content-type smoke, system role rejection 422)
- Full suite: 12 collected, 12 skipped, 0 failed, exit code 0

## Task Commits

Each task was committed atomically:

1. **Task 1: pytest.ini and test package marker** - `934c0a7` (chore)
2. **Task 2: conftest.py — shared pytest fixtures** - `a005536` (feat)
3. **Task 3: test_rag.py — 10 test stubs for RAG-01–07 and CITE-01–03** - `536eb95` (test)
4. **Task 4: test_chat_endpoint.py — 2 HTTP-level test stubs** - `ee9e4d0` (test)

## Files Created/Modified

- `pytest.ini` - asyncio_mode=auto configuration at project root
- `backend/app/tests/__init__.py` - Empty package marker for test imports
- `backend/app/tests/conftest.py` - Shared fixtures: mock_openrouter, mock_qdrant, sample_scored_point
- `backend/app/tests/test_rag.py` - 10 stubs for RAG and citation requirements
- `backend/app/tests/test_chat_endpoint.py` - 2 HTTP-level stubs for chat endpoint

## Decisions Made

- Function-scoped fixtures only — module scope causes test-order-dependent state bleed with async mocks (addresses T-02-W0-01)
- Used `pytest.skip("stub")` pattern not `assert False` — keeps CI green before Wave 1 ships (addresses T-02-W0-02)
- `asyncio_mode=auto` is backward-compatible with existing ingestion tests using explicit `@pytest.mark.asyncio`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created Python virtual environment and installed dependencies**
- **Found during:** Task 2 (conftest.py verification)
- **Issue:** No `.venv` existed in the project; `qdrant_client` and `openai` modules unavailable for import verification
- **Fix:** Created `.venv` with `python -m venv .venv` and installed `qdrant-client==1.17.1`, `openai==2.32.0`, `pytest`, `pytest-asyncio`, `httpx`
- **Files modified:** `.venv/` (not tracked in git, gitignored)
- **Verification:** `python -c "from qdrant_client import AsyncQdrantClient; from openai import AsyncOpenAI"` returned OK
- **Committed in:** N/A (venv not committed per .gitignore)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Required for verification only. No scope changes. Venv setup is normal developer environment bootstrapping.

## Issues Encountered

- No `.venv` existed, blocking conftest.py syntax verification. Resolved by creating venv and installing deps (deviation Rule 3).

## User Setup Required

None - no external service configuration required. Run `python -m venv .venv && pip install -r requirements.txt -r requirements-dev.txt` to set up local dev environment if not already done.

## Known Stubs

All 12 tests are intentional stubs — this is a Wave 0 plan whose entire purpose is to create pre-implementation stubs. Wave 1 plans (02-02, 02-03) will implement the services these tests verify.

| File | Test | Reason |
|------|------|--------|
| test_rag.py | all 10 tests | Wave 1 implements backend/app/services/rag.py |
| test_chat_endpoint.py | all 2 tests | Wave 1 implements POST /api/chat endpoint |

## Next Phase Readiness

- Wave 1 plan 02-02 (RAG service implementation) can proceed — test contract is defined
- Wave 1 plan 02-03 (chat endpoint) can proceed — HTTP test contract is defined
- Stub function names are locked — Wave 1 must NOT rename these functions
- pytest infrastructure confirmed working: 12 tests collected, all skip cleanly, exit code 0

---
*Phase: 02-core-rag-pipeline*
*Completed: 2026-04-24*

## Self-Check: PASSED

- FOUND: pytest.ini
- FOUND: backend/app/tests/__init__.py
- FOUND: backend/app/tests/conftest.py
- FOUND: backend/app/tests/test_rag.py
- FOUND: backend/app/tests/test_chat_endpoint.py
- FOUND commit: 934c0a7 (Task 1)
- FOUND commit: a005536 (Task 2)
- FOUND commit: 536eb95 (Task 3)
- FOUND commit: ee9e4d0 (Task 4)

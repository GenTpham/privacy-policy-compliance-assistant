---
id: 01-PLAN-05
wave: 3
depends_on:
  - 01-PLAN-04
phase: 01-infrastructure-data-ingestion
goal: Pytest eval suite covering all 10 eval dimensions from AI-SPEC §5; Makefile eval targets
files_modified:
  - backend/ingestion/tests/test_ingestion_evals.py
  - Makefile
autonomous: true
requirements:
  - INGEST-03
  - INGEST-06
---

<objective>
Create the post-ingestion eval test suite (pytest) that verifies the Qdrant index is correct after `python -m backend.ingestion.ingest` completes. Covers distance metric, embedding dim, rank-1 sanity check, index completeness, metadata completeness, and deduplication integrity. Also creates a Makefile with `eval-ingest` and `eval-ingest-fast` targets.

Purpose: These tests are the gate before Phase 2 begins. The 10 dimensions in AI-SPEC §5 cannot be verified by running the ingestion script alone. They require reading back from Qdrant after ingestion and asserting structural correctness. INGEST-06 (rank-1 sanity check) is the critical pass/fail signal.
Output: test_ingestion_evals.py (runnable pytest suite) and Makefile (eval targets).
</objective>

<execution_context>
@D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-AI-SPEC.md
</execution_context>

<context>
@D:\data\code\privacy-policy-compliance-assistant\.planning\ROADMAP.md
@D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-CONTEXT.md

<interfaces>
<!-- From AI-SPEC §5 Evaluation Strategy — core eval scaffolding (reference implementation): -->
<!-- COLLECTION_NAME = "policies" -->
<!-- DATASET_PATH = Path("dataset/json/train/policy_qa_train.json") -->
<!-- SAMPLE_SIZE = 200 -->
<!--
<!-- eval dimensions (10 total): -->
<!-- 1. probe_embedding_dim correctness (dim > 0, matches collection) -->
<!-- 2. distance metric == COSINE -->
<!-- 3. rank-1 sanity check: score > 0.99 (INGEST-06) -->
<!-- 4. index completeness: points_count within 0.1% of unique passage count -->
<!-- 5. metadata completeness: all 4 fields on 200 sampled points -->
<!-- 6. deduplication integrity: no duplicate text hashes -->
<!-- 7. checkpoint resumability (integration test) -->
<!-- 8. rate-limit backoff correctness (mock test) -->
<!-- 9. token count guard (C6) — passages > 400 tokens logged as warnings -->
<!-- 10. Qdrant volume persistence (Docker restart test) -->
<!--
<!-- From ingest.py (Plan 04 output): -->
<!--   from backend.app.core.config import get_settings -->
<!--   COLLECTION_NAME = "policies" -->
<!--   DATASET_PATH = Path("dataset/json/train/policy_qa_train.json") -->
<!--
<!-- CI-safe tests vs API-dependent tests: -->
<!--   Fast (no API): test_distance_metric_is_cosine, test_index_completeness, -->
<!--                  test_metadata_completeness, test_no_duplicate_passages -->
<!--   API-dependent: test_embedding_dim_matches_collection, test_rank1_sanity_check -->
<!--   Integration: test_checkpoint_resumability, test_volume_persistence -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create backend/ingestion/tests/test_ingestion_evals.py</name>
  <files>backend/ingestion/tests/test_ingestion_evals.py</files>
  <read_first>
    - D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-AI-SPEC.md (§5 Evaluation Strategy — full section including Dimensions table, Eval Tooling, and Core eval scaffolding snippet)
    - D:\data\code\privacy-policy-compliance-assistant\backend\ingestion\ingest.py (if exists — to import COLLECTION_NAME and DATASET_PATH constants)
    - D:\data\code\privacy-policy-compliance-assistant\backend\app\core\config.py (get_settings signature)
  </read_first>
  <action>
Create `backend/ingestion/tests/test_ingestion_evals.py` implementing all 10 eval dimensions from AI-SPEC §5. Use the core scaffolding from AI-SPEC §5 as the base and extend it with all remaining dimensions.

**File structure:**

```python
"""
backend/ingestion/tests/test_ingestion_evals.py
Post-ingestion eval suite. Run after python -m backend.ingestion.ingest completes.

Fast tests (no API calls): test_distance_metric_is_cosine, test_index_completeness,
                           test_metadata_completeness, test_no_duplicate_passages
API-dependent tests:       test_embedding_dim_matches_collection, test_rank1_sanity_check
Integration tests:         test_checkpoint_resumability (requires running a partial ingest),
                           test_volume_persistence (requires Docker)

Run fast tests: pytest backend/ingestion/tests/test_ingestion_evals.py -v -k "not rank1 and not embedding_dim and not resumability and not persistence"
Run all:        pytest backend/ingestion/tests/test_ingestion_evals.py -v --timeout=120
"""
```

**Implement exactly these 8 tests** (dimensions 1–6, 8, 9 from AI-SPEC §5; dimensions 7 and 10 require external orchestration noted inline):

1. `test_distance_metric_is_cosine` — assert `info.config.params.vectors.distance == Distance.COSINE`; include remediation hint in assertion message: "Collection must be deleted and re-ingested to fix distance metric"
2. `test_embedding_dim_matches_collection` — probe live Nemotron API; compare `len(resp.data[0].embedding)` to `info.config.params.vectors.size`; mark with `@pytest.mark.asyncio`
3. `test_rank1_sanity_check` — embed `passages[0]["context"]` from dataset; assert `results[0].score > 0.99` (INGEST-06)
4. `test_index_completeness` — compute `unique_texts = {p["context"].strip() for p in passages if p.get("context","").strip()}`; compare to `info.points_count`; tolerance `max(1, int(expected * 0.001))`
5. `test_metadata_completeness` — scroll 200 points; assert all four fields (`title`, `source_doc`, `passage_id`, `text`) are present and non-empty strings on every sampled point
6. `test_no_duplicate_passages` — full scroll all points; SHA-256 hash all `text` payloads; assert `len(hashes) == len(set(hashes))`
7. `test_rate_limit_backoff` — use `unittest.mock.AsyncMock` to mock `openrouter.embeddings.create` raising a 429-like exception on first 4 calls then succeeding; assert retry count and final success; import `embed_batch` from `backend.ingestion.ingest`
8. `test_token_count_guard_warns` — for passages in dataset with `token_count > 400` (computed via tiktoken), verify the ingest script would log a warning; test this by calling the token counting logic directly from `backend.ingestion.chunker` — assert `_count_tokens(long_text) > 400` for a known long passage

**Fixture:**
```python
@pytest.fixture(scope="module")
def event_loop():
    """Override pytest-asyncio event loop to module scope for connection reuse."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="module")
async def qdrant_client():
    from qdrant_client import AsyncQdrantClient
    from backend.app.core.config import get_settings
    settings = get_settings()
    client = AsyncQdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        api_key=settings.qdrant_api_key,
    )
    yield client
```

**Note on dimensions 7 (checkpoint resumability) and 10 (volume persistence):** These require orchestration (killing a process mid-run, or running `docker compose restart`) that cannot be expressed as a pytest test without a full test harness. Add them as `@pytest.mark.skip(reason="integration test — run manually")` stubs with inline instructions documenting the manual steps. Do NOT omit them — they must appear in the file so they are visible to future implementers.

Stub for dimension 7:
```python
@pytest.mark.skip(reason="integration test — see docstring for manual steps")
def test_checkpoint_resumability():
    """
    Manual steps:
    1. Run: python -m backend.ingestion.ingest (let it complete ~50 batches, then kill with Ctrl+C)
    2. Note ingestion_checkpoint.json exists with completed_hashes entries
    3. Run: python -m backend.ingestion.ingest again
    4. Verify: output shows "Resuming — N hashes already confirmed" (N > 0)
    5. Verify: final points_count equals a single full-run result (no duplicates from re-run)
    """
    pass
```

Stub for dimension 10:
```python
@pytest.mark.skip(reason="integration test — requires Docker")
def test_volume_persistence():
    """
    Manual steps:
    1. After full ingest, record: docker exec <qdrant_container> curl -s localhost:6333/collections/policies
    2. Run: docker compose restart qdrant
    3. Wait for Qdrant health: curl -f http://localhost:6333/readyz
    4. Re-check: curl -s http://localhost:6333/collections/policies
    5. Assert: points_count is unchanged (named volume persists data)
    """
    pass
```
  </action>
  <verify>
    <automated>grep "test_distance_metric_is_cosine" D:/data/code/privacy-policy-compliance-assistant/backend/ingestion/tests/test_ingestion_evals.py && grep "test_rank1_sanity_check" D:/data/code/privacy-policy-compliance-assistant/backend/ingestion/tests/test_ingestion_evals.py && grep "test_metadata_completeness" D:/data/code/privacy-policy-compliance-assistant/backend/ingestion/tests/test_ingestion_evals.py && grep "test_no_duplicate_passages" D:/data/code/privacy-policy-compliance-assistant/backend/ingestion/tests/test_ingestion_evals.py && grep "score > 0.99" D:/data/code/privacy-policy-compliance-assistant/backend/ingestion/tests/test_ingestion_evals.py</automated>
  </verify>
  <done>test_ingestion_evals.py has 8 implemented tests + 2 manual-step stubs. Covers: distance metric, embedding dim, rank-1 sanity check (score > 0.99), index completeness (0.1% tolerance), metadata completeness (4 fields on 200 points), no duplicate passages, rate-limit backoff (mocked), token count guard. Fast subset runnable without API calls.</done>
</task>

<task type="auto">
  <name>Task 2: Create Makefile with eval targets and dev helpers</name>
  <files>Makefile</files>
  <read_first>
    - D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-AI-SPEC.md (§5 CI/CD Integration — Makefile targets section)
    - D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-CONTEXT.md (D-05, D-07: local dev workflow)
  </read_first>
  <action>
Create `Makefile` at the project root with the eval targets from AI-SPEC §5 and developer workflow helpers (per D-05, D-07):

```makefile
.PHONY: venv install install-dev qdrant-up qdrant-down ingest eval-ingest eval-ingest-fast health

# ── Environment setup ─────────────────────────────────────────────────────────
venv:
	python3.11 -m venv .venv

install:
	.venv/bin/pip install -r requirements.txt

install-dev:
	.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# ── Local dev: Qdrant only (D-05 workflow) ─────────────────────────────────────
qdrant-up:
	docker compose up qdrant -d

qdrant-down:
	docker compose down

# ── Data ingestion ────────────────────────────────────────────────────────────
ingest:
	.venv/bin/python -m backend.ingestion.ingest

# ── Eval targets (from AI-SPEC §5) ───────────────────────────────────────────
eval-ingest:
	.venv/bin/pytest backend/ingestion/tests/test_ingestion_evals.py -v --tb=short

eval-ingest-fast:
	.venv/bin/pytest backend/ingestion/tests/test_ingestion_evals.py -v --tb=short \
	  -k "not rank1 and not embedding_dim and not resumability and not persistence"

# ── Local backend dev ─────────────────────────────────────────────────────────
dev:
	.venv/bin/uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

# ── Docker full stack ─────────────────────────────────────────────────────────
up:
	docker compose up

down:
	docker compose down

# ── Health check ──────────────────────────────────────────────────────────────
health:
	curl -f http://localhost:8000/health && curl -f http://localhost:6333/readyz
```

Tab-indented commands are required for Makefile syntax — ensure each command line uses a real tab character, not spaces.
  </action>
  <verify>
    <automated>grep "eval-ingest:" D:/data/code/privacy-policy-compliance-assistant/Makefile && grep "eval-ingest-fast:" D:/data/code/privacy-policy-compliance-assistant/Makefile && grep "ingest:" D:/data/code/privacy-policy-compliance-assistant/Makefile && grep "venv:" D:/data/code/privacy-policy-compliance-assistant/Makefile</automated>
  </verify>
  <done>Makefile has venv, install, install-dev, qdrant-up, qdrant-down, ingest, eval-ingest, eval-ingest-fast, dev, up, down, health targets. All recipe lines use tab indentation.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Test suite → Qdrant | Read-only scroll and search calls to local Qdrant — no writes |
| Test suite → OpenRouter API | API-dependent tests call embedding API with test string; OPENROUTER_API_KEY from .env |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-05-01 | Information Disclosure | OPENROUTER_API_KEY in test fixture | mitigate | Loaded via get_settings() from .env — not hardcoded; API-dependent tests marked so they can be skipped in CI without a key |
| T-05-02 | Denial of Service | test_no_duplicate_passages full scroll | accept | Full scroll of 17K points is a one-time post-ingest verification; not run in hot path; adds ~2–5 seconds |
| T-05-03 | Tampering | Makefile targets running destructive commands | accept | No destructive operations (no collection delete, no data wipe) in Makefile targets; eval targets are read-only |
</threat_model>

<verification>
After Plan 05 completes:
- `pytest backend/ingestion/tests/test_ingestion_evals.py --collect-only` lists at least 8 test functions without import errors
- `grep "score > 0.99" backend/ingestion/tests/test_ingestion_evals.py` finds the rank-1 threshold assertion (INGEST-06)
- `grep "pytest.mark.skip" backend/ingestion/tests/test_ingestion_evals.py` finds 2 integration stubs (resumability, persistence)
- `make eval-ingest-fast` command is syntactically valid (Makefile tab-indented)
- After full ingestion completes: `make eval-ingest-fast` passes all non-API-dependent tests
- After full ingestion completes: `make eval-ingest` passes all tests including rank-1 sanity check (score > 0.99)
</verification>

<success_criteria>
- test_ingestion_evals.py: 8 real tests + 2 manual-step stubs (10 dimensions covered)
- test_rank1_sanity_check: asserts score > 0.99 (INGEST-06)
- test_metadata_completeness: checks all 4 fields (title, source_doc, passage_id, text) on 200 sampled points (INGEST-03)
- Fast subset (eval-ingest-fast) skips API-dependent tests — runnable in CI without OPENROUTER_API_KEY
- Makefile: eval-ingest and eval-ingest-fast targets match AI-SPEC §5 specification
</success_criteria>

<output>
After completion, create `.planning/phases/01-infrastructure-data-ingestion/01-05-SUMMARY.md` with:
- Test functions implemented and which eval dimension each covers
- Fast vs API-dependent test classification
- Makefile targets created
- Any deviations from the plan and why
</output>

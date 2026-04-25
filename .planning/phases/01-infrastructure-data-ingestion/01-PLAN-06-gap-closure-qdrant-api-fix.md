---
phase: "01"
plan: "06"
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/ingestion/ingest.py
  - backend/ingestion/tests/test_ingestion_evals.py
autonomous: true
requirements:
  - INGEST-06
gap_closure: true

must_haves:
  truths:
    - "sanity_check() in ingest.py completes without AttributeError — qdrant.query_points() is called, not qdrant.search()"
    - "embed_batch() and probe_embedding_dim() in ingest.py pass encoding_format='float' to every embeddings.create() call"
    - "test_rank1_sanity_check in test_ingestion_evals.py completes without AttributeError — qdrant_client.query_points() is called, not qdrant_client.search()"
    - "test_rank1_sanity_check result access uses response.points[0].score, not results[0].score from a list"
  artifacts:
    - path: "backend/ingestion/ingest.py"
      provides: "Fixed ingestion pipeline — encoding_format and query_points API"
      contains: "query_points"
    - path: "backend/ingestion/tests/test_ingestion_evals.py"
      provides: "Fixed eval suite — query_points API, response.points result access"
      contains: "query_points"
  key_links:
    - from: "ingest.py sanity_check()"
      to: "AsyncQdrantClient.query_points()"
      via: "await qdrant.query_points(collection_name=COLLECTION_NAME, query=vecs[0], limit=1, with_payload=True)"
      pattern: "query_points"
    - from: "ingest.py probe_embedding_dim()"
      to: "openrouter.embeddings.create()"
      via: "encoding_format=\"float\" kwarg"
      pattern: "encoding_format=\"float\""
    - from: "ingest.py embed_batch()"
      to: "openrouter.embeddings.create()"
      via: "encoding_format=\"float\" kwarg"
      pattern: "encoding_format=\"float\""
    - from: "test_rank1_sanity_check"
      to: "AsyncQdrantClient.query_points()"
      via: "await qdrant_client.query_points(collection_name=COLLECTION_NAME, query=query_vec, limit=1, with_payload=True)"
      pattern: "query_points"
---

<objective>
Fix four mechanical API-call defects in ingest.py and test_ingestion_evals.py that prevent
SC3 (sanity check) from passing. These are back-port fixes: the identical corrections were
already applied to rag.py (commit b9cb972) and main.py (commit 4843320) in Phase 2; this
plan applies the same changes to the Phase 1 ingestion files that were left behind.

Purpose: Unblock INGEST-06 / SC3 — "Ingestion sanity check passes: a known passage is
embedded, queried, and confirmed to rank #1 in search results."

Output: Two files with targeted one-line changes each. No new files created.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

<interfaces>
<!-- Reference implementations already in the codebase. Executor must read these before editing. -->

From backend/app/services/rag.py (commit b9cb972 — the query_points migration):
```python
# qdrant-client 1.13+ replaced search() with query_points() — returns QueryResponse with .points
response = await qdrant.query_points(
    collection_name=COLLECTION_NAME,
    query=query_vector,
    limit=5,
    score_threshold=0.55,
    with_payload=True,
)
results = response.points
```

From backend/app/main.py (commit 4843320 — the encoding_format fix):
```python
resp = await client.embeddings.create(model=model, input="probe", encoding_format="float")
```

AsyncQdrantClient.query_points() returns a QueryResponse object (NOT a plain list).
Results are accessed via `.points` attribute: `response.points[0].score`, `response.points[0].id`.
Passing `score_threshold` is optional and omitted in the sanity check (limit=1 is sufficient).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Fix ingest.py — add encoding_format="float" and replace qdrant.search() with query_points()</name>
  <files>backend/ingestion/ingest.py</files>

  <read_first>
    - backend/ingestion/ingest.py (the file being modified — understand current state at lines 72, 151, 177-192)
    - backend/app/main.py (reference: encoding_format="float" pattern, line 27)
    - backend/app/services/rag.py (reference: query_points() pattern, lines 143-150)
  </read_first>

  <action>
Make exactly three targeted edits to backend/ingestion/ingest.py:

**Edit 1 — probe_embedding_dim() (line 72):**
Current:
```python
    resp = await openrouter.embeddings.create(model=EMBED_MODEL, input="probe")
```
Replace with:
```python
    resp = await openrouter.embeddings.create(model=EMBED_MODEL, input="probe", encoding_format="float")
```

**Edit 2 — embed_batch() (line 151):**
Current:
```python
            resp = await openrouter.embeddings.create(model=EMBED_MODEL, input=texts)
```
Replace with:
```python
            resp = await openrouter.embeddings.create(model=EMBED_MODEL, input=texts, encoding_format="float")
```

**Edit 3 — sanity_check() (lines 177-192):**
Current block:
```python
    results = await qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=vecs[0],
        limit=1,
        with_payload=True,
    )

    if not results:
        raise AssertionError("[sanity_check] FAILED: no results returned for first passage query")

    score = results[0].score
```
Replace with:
```python
    response = await qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=vecs[0],
        limit=1,
        with_payload=True,
    )

    if not response.points:
        raise AssertionError("[sanity_check] FAILED: no results returned for first passage query")

    score = response.points[0].score
```

Rationale:
- encoding_format="float" fixes an OpenAI SDK 2.x parser bug that crashes when the response
  encoding is not explicitly declared (pattern from commit 4843320 / main.py line 27).
- query_points() is the current AsyncQdrantClient API. search() was removed in qdrant-client 1.13+;
  installed version is 1.17.1 (pattern from commit b9cb972 / rag.py lines 143-150).
- query_points() returns a QueryResponse object; results live in .points (NOT the response itself).

Do NOT change any other lines. Do NOT modify function signatures, constants, comments, or
the main ingestion loop.
  </action>

  <verify>
    <automated>
cd D:/data/code/privacy-policy-compliance-assistant && grep -n "encoding_format" backend/ingestion/ingest.py
    </automated>
  </verify>

  <acceptance_criteria>
    - backend/ingestion/ingest.py contains `encoding_format="float"` on the probe_embedding_dim() embeddings.create() call (line ~72)
    - backend/ingestion/ingest.py contains `encoding_format="float"` on the embed_batch() embeddings.create() call (line ~151)
    - backend/ingestion/ingest.py does NOT contain `qdrant.search(` anywhere
    - backend/ingestion/ingest.py contains `qdrant.query_points(` in sanity_check()
    - backend/ingestion/ingest.py contains `query=vecs[0],` (not `query_vector=vecs[0],`)
    - backend/ingestion/ingest.py contains `response.points` (not `results[0]`) for result access
    - Verify: `grep -n "qdrant.search" backend/ingestion/ingest.py` returns no output
    - Verify: `grep -n "encoding_format" backend/ingestion/ingest.py` shows exactly 2 matches
    - Verify: `grep -n "query_points" backend/ingestion/ingest.py` shows exactly 1 match
  </acceptance_criteria>

  <done>ingest.py has encoding_format="float" in both embeddings.create() calls and uses query_points() with response.points access in sanity_check(). No search() calls remain.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Fix test_ingestion_evals.py — replace qdrant_client.search() with query_points() in test_rank1_sanity_check</name>
  <files>backend/ingestion/tests/test_ingestion_evals.py</files>

  <read_first>
    - backend/ingestion/tests/test_ingestion_evals.py (the file being modified — understand current state of test_rank1_sanity_check at lines 108-136)
    - backend/app/services/rag.py (reference: query_points() call and response.points access pattern)
  </read_first>

  <action>
Make exactly one targeted edit to backend/ingestion/tests/test_ingestion_evals.py.

**Edit — test_rank1_sanity_check (lines 124-136):**

Current block (starting at line 124):
```python
    results = await qdrant_client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vec,
        limit=1,
        with_payload=True,
    )

    assert results, "No results returned for first passage query — collection may be empty"
    score = results[0].score
    assert score > 0.99, (
        f"Rank-1 sanity check FAILED: score={score:.4f} (expected > 0.99). "
        "This may indicate a distance metric mismatch, failed ingestion, or model change."
    )
```

Replace with:
```python
    response = await qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec,
        limit=1,
        with_payload=True,
    )

    assert response.points, "No results returned for first passage query — collection may be empty"
    score = response.points[0].score
    assert score > 0.99, (
        f"Rank-1 sanity check FAILED: score={score:.4f} (expected > 0.99). "
        "This may indicate a distance metric mismatch, failed ingestion, or model change."
    )
```

Rationale:
- qdrant_client.search() does not exist in qdrant-client 1.17.1 (removed in 1.13+).
- query_points() returns QueryResponse; results are in .points (list of ScoredPoint).
- Parameter rename: query_vector= becomes query= (matching the new API signature).
- The assert message and score threshold (> 0.99) are unchanged.

Do NOT change any other test functions, fixtures, imports, or constants.
Do NOT add encoding_format to test_rank1_sanity_check's embeddings.create() call (line 121)
— that call is a separate concern; fix it only if it causes a failure during execution.
NOTE: line 93 in test_embedding_dim_matches_collection also calls embeddings.create() without
encoding_format. Update BOTH test_embedding_dim_matches_collection (line 93) and
test_rank1_sanity_check (line 121) to add encoding_format="float" for consistency with
the established pattern, since both make live API calls.
  </action>

  <verify>
    <automated>
cd D:/data/code/privacy-policy-compliance-assistant && grep -n "search\|query_points\|encoding_format" backend/ingestion/tests/test_ingestion_evals.py
    </automated>
  </verify>

  <acceptance_criteria>
    - backend/ingestion/tests/test_ingestion_evals.py does NOT contain `qdrant_client.search(` anywhere
    - backend/ingestion/tests/test_ingestion_evals.py contains `qdrant_client.query_points(` in test_rank1_sanity_check
    - backend/ingestion/tests/test_ingestion_evals.py contains `query=query_vec,` (not `query_vector=query_vec,`)
    - backend/ingestion/tests/test_ingestion_evals.py contains `response.points` for result access (not `results[0]`)
    - backend/ingestion/tests/test_ingestion_evals.py contains `encoding_format="float"` in both live API embedding calls (test_embedding_dim_matches_collection line ~93 and test_rank1_sanity_check line ~121)
    - Verify: `grep -n "qdrant_client.search" backend/ingestion/tests/test_ingestion_evals.py` returns no output
    - Verify: `grep -n "query_points" backend/ingestion/tests/test_ingestion_evals.py` shows exactly 1 match
    - Verify: `grep -c "encoding_format" backend/ingestion/tests/test_ingestion_evals.py` returns 2
  </acceptance_criteria>

  <done>test_rank1_sanity_check uses query_points() with response.points result access. Both live-API embeddings.create() calls in the test file include encoding_format="float". No search() calls remain.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| ingest.py → OpenRouter API | API key transmitted over TLS; embedding responses deserialized by openai SDK |
| ingest.py → Qdrant | Qdrant API key in env var; upsert payloads contain policy text (non-PII) |
| test file → Qdrant (live tests) | Same as above; test reads from already-ingested collection |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-G-01 | Tampering | ingest.py embed_batch() | mitigate | encoding_format="float" ensures the openai SDK parser validates the response structure; prevents silent corruption from unexpected base64-encoded embedding responses |
| T-01-G-02 | Denial of Service | ingest.py sanity_check() | accept | sanity_check() reads a single passage from the local corpus file; no external input accepted; no DoS surface |
| T-01-G-03 | Information Disclosure | test_ingestion_evals.py | accept | Tests run against a local Qdrant instance; OPENROUTER_API_KEY read from .env; no secrets emitted to stdout; low risk in offline eval context |
| T-01-G-04 | Elevation of Privilege | ingest.py → Qdrant upsert | accept | Qdrant runs in Docker on loopback; api_key required in non-local environments; ingest.py is an offline script, not an HTTP-exposed surface |
</threat_model>

<verification>
After both tasks complete, run the following checks from the project root:

```bash
# Verify no search() calls remain in either file
grep -rn "\.search(" backend/ingestion/ && echo "FAIL: search() calls remain" || echo "PASS: no search() calls"

# Verify query_points is present in both files
grep -n "query_points" backend/ingestion/ingest.py backend/ingestion/tests/test_ingestion_evals.py

# Verify encoding_format is present in ingest.py (expect 2 matches)
grep -c "encoding_format" backend/ingestion/ingest.py

# Run the mocked tests (fast, no live API required)
cd D:/data/code/privacy-policy-compliance-assistant && .venv/Scripts/python.exe -m pytest backend/ingestion/tests/test_ingestion_evals.py -v -k "not rank1 and not embedding_dim and not resumability and not persistence" --tb=short 2>&1 | tail -20
```

Live API verification (requires .env with valid OPENROUTER_API_KEY and running Qdrant):
```bash
python -m backend.ingestion.ingest
# Expected final log line: [sanity_check] PASSED: rank-1 score=1.0000
```
</verification>

<success_criteria>
- `grep "qdrant.search\|qdrant_client.search" backend/ingestion/ingest.py backend/ingestion/tests/test_ingestion_evals.py` returns no output
- `grep -c "encoding_format" backend/ingestion/ingest.py` returns 2
- `grep -c "query_points" backend/ingestion/ingest.py` returns 1
- `grep -c "query_points" backend/ingestion/tests/test_ingestion_evals.py` returns 1
- Fast eval tests (non-API) pass: `pytest -k "not rank1 and not embedding_dim and not resumability and not persistence"` exits 0
- INGEST-06 / SC3 is unblocked: when run with live credentials, sanity_check() logs `[sanity_check] PASSED`
</success_criteria>

<output>
After completion, create `.planning/phases/01-infrastructure-data-ingestion/01-06-SUMMARY.md`
with the standard summary format documenting the four mechanical fixes applied.
</output>

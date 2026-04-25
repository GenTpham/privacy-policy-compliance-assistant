---
phase: 02
slug: core-rag-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-04-24"
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (installed Phase 1) |
| **Config file** | `pytest.ini` — Wave 0 creates with `asyncio_mode = "auto"` |
| **Quick run command** | `pytest backend/app/tests/test_rag.py -x -v` |
| **Full suite command** | `pytest backend/ -v --tb=short` |
| **Estimated runtime** | ~5 seconds (all mocked, no live API calls) |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/app/tests/test_rag.py -x -v`
- **After every plan wave:** Run `pytest backend/ -v --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | — | — | N/A | setup | `pytest backend/app/tests/ --collect-only` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | RAG-01 | — | N/A | unit (mock) | `pytest backend/app/tests/test_rag.py::test_embed_calls_correct_model -x` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 1 | RAG-02 | — | N/A | unit (mock) | `pytest backend/app/tests/test_rag.py::test_retrieve_params -x` | ❌ W0 | ⬜ pending |
| 02-02-03 | 02 | 1 | RAG-07 | — | No LLM call when 0 chunks meet threshold | unit (mock) | `pytest backend/app/tests/test_rag.py::test_no_results_early_return -x` | ❌ W0 | ⬜ pending |
| 02-02-04 | 02 | 1 | RAG-03 | — | N/A | unit (mock) | `pytest backend/app/tests/test_rag.py::test_prompt_contains_numbered_chunks -x` | ❌ W0 | ⬜ pending |
| 02-02-05 | 02 | 1 | RAG-04 | — | Abstain instruction blocks hallucination | unit (pure) | `pytest backend/app/tests/test_rag.py::test_system_prompt_abstain_wording -x` | ❌ W0 | ⬜ pending |
| 02-02-06 | 02 | 1 | RAG-05 | — | N/A | unit (mock) | `pytest backend/app/tests/test_rag.py::test_delta_before_done -x` | ❌ W0 | ⬜ pending |
| 02-02-07 | 02 | 1 | RAG-06 | — | N/A | unit (pure) | `pytest backend/app/tests/test_rag.py::test_history_sliced_to_6 -x` | ❌ W0 | ⬜ pending |
| 02-02-08 | 02 | 1 | CITE-01 | — | N/A | unit (pure) | `pytest backend/app/tests/test_rag.py::test_citations_have_title_and_text -x` | ❌ W0 | ⬜ pending |
| 02-02-09 | 02 | 1 | CITE-02 | — | N/A | unit (pure) | `pytest backend/app/tests/test_rag.py::test_done_event_shape -x` | ❌ W0 | ⬜ pending |
| 02-02-10 | 02 | 1 | CITE-03 | T-02-01 | Fabricated citations stripped before done event | unit (pure) | `pytest backend/app/tests/test_rag.py::test_fabricated_citation_stripped -x` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 1 | RAG-05 | — | N/A | smoke (httpx) | `pytest backend/app/tests/test_chat_endpoint.py::test_endpoint_content_type -x` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 1 | D-05 | T-02-02 | Prompt injection via history role="system" rejected | unit (httpx) | `pytest backend/app/tests/test_chat_endpoint.py::test_system_role_rejected -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/app/tests/__init__.py` — package marker (empty file)
- [ ] `backend/app/tests/conftest.py` — shared fixtures: `mock_openrouter`, `mock_qdrant`, `sample_scored_point`
- [ ] `backend/app/tests/test_rag.py` — 10 unit test stubs for RAG-01–07 and CITE-01–03
- [ ] `backend/app/tests/test_chat_endpoint.py` — 2 HTTP-level test stubs (content-type, role rejection)
- [ ] `pytest.ini` — `asyncio_mode = "auto"` for pytest-asyncio compatibility

Wave 0 must be executed before any Wave 1 plan task; all stubs must pass collection (zero failures before implementation).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| First token arrives within 3 seconds | RAG-05 | Requires live OpenRouter + populated Qdrant; timing is wall-clock dependent | `curl -N -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d '{"message":"what is the data retention policy?"}' 2>&1 \| head -5` — observe first `data:` line arrives within 3s |
| Streamed tokens readable in real-time | RAG-05 | Client-side streaming behavior not verifiable in unit tests | Same curl command — tokens should appear progressively, not all at once |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

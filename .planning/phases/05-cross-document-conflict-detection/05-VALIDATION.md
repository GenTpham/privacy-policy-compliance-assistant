---
phase: 5
slug: cross-document-conflict-detection
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-28
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `pytest.ini` (asyncio_mode=auto) |
| **Quick run command** | `pytest backend/app/tests/test_rag.py backend/app/tests/test_chat_endpoint.py -x -v` |
| **Full suite command** | `pytest backend/app/tests/ -x -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/app/tests/test_rag.py backend/app/tests/test_chat_endpoint.py -x -v`
- **After every plan wave:** Run `pytest backend/app/tests/ -x -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 0 | CONFLICT-01 | — | `is_conflict_query` returns False for safe strings not in keyword list | unit | `pytest backend/app/tests/test_chat_endpoint.py::test_conflict_detection_keywords -x` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 0 | CONFLICT-01 | — | Standard query not misdetected | unit | `pytest backend/app/tests/test_chat_endpoint.py::test_standard_query_not_detected -x` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 0 | CONFLICT-01 | — | False positive (e.g. "indifferent") routes gracefully | unit | `pytest backend/app/tests/test_chat_endpoint.py::test_false_positive_graceful -x` | ❌ W0 | ⬜ pending |
| 05-01-04 | 01 | 0 | CONFLICT-02 | — | N/A | unit | `pytest backend/app/tests/test_rag.py::test_conflict_retrieve_params -x` | ❌ W0 | ⬜ pending |
| 05-01-05 | 01 | 0 | CONFLICT-03 | — | Prompt instructs model; no secrets injected | unit | `pytest backend/app/tests/test_rag.py::test_conflict_prompt_contains_verdict_format -x` | ❌ W0 | ⬜ pending |
| 05-01-06 | 01 | 0 | CONFLICT-03 | — | N/A | unit | `pytest backend/app/tests/test_rag.py::test_conflict_prompt_contains_classifications -x` | ❌ W0 | ⬜ pending |
| 05-01-07 | 01 | 0 | CONFLICT-03 | — | Abstain instruction present — prevents hallucination | unit | `pytest backend/app/tests/test_rag.py::test_conflict_prompt_abstain_wording -x` | ❌ W0 | ⬜ pending |
| 05-01-08 | 01 | 0 | CONFLICT-04 | — | N/A | unit | `pytest backend/app/tests/test_rag.py::test_conflict_done_event_shape -x` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 1 | CONFLICT-01 | — | History role=system rejected (Literal guard unchanged) | integration | `pytest backend/app/tests/test_chat_endpoint.py::test_conflict_route_dispatches_conflict_generator -x` | ❌ W0 | ⬜ pending |
| 05-02-02 | 02 | 1 | CONFLICT-04 | — | Standard path still uses limit=5 (regression) | unit | `pytest backend/app/tests/test_rag.py::test_retrieve_params -x` | ✅ existing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/app/tests/test_rag.py` — add 6 new test stubs (CONFLICT-02 through CONFLICT-04 unit tests)
- [ ] `backend/app/tests/test_chat_endpoint.py` — add 3 new test stubs (CONFLICT-01 detection + routing)
- [ ] `backend/app/tests/conftest.py` — add `sample_scored_points_multi` fixture (2 ScoredPoints from different source_doc titles)

*(Existing test infrastructure — pytest.ini with asyncio_mode=auto, conftest.py base fixtures, import structure — is already in place. No new setup files needed.)*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Conflict response verdict line appears in UI chat bubble | CONFLICT-03 | Full LLM response; requires live OpenRouter call | Ask "Which document has a conflict on data retention?" in the UI; verify last line of response starts with "Verdict:" |
| Standard query still returns 5 citations (not 10) in the UI | CONFLICT-04 | End-to-end SSE streaming; live backend needed | Ask "What is the data retention policy?" in the UI; verify citation panel shows ≤5 cards |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

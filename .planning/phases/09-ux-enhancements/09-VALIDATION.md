---
phase: 9
slug: ux-enhancements
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-06
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) + vitest (frontend) |
| **Config file** | `pytest.ini` (backend), `frontend/vite.config.ts` (frontend) |
| **Quick run command** | `python -m pytest backend/ -q --tb=short` |
| **Full suite command** | `python -m pytest backend/ -q && cd frontend && npm test -- --run` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest backend/ -q --tb=short`
- **After every plan wave:** Run full suite (backend + frontend)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 9-01-01 | 01 | 1 | UX-01 | — | GET /api/sources returns distinct title list | unit | `pytest backend/tests/test_sources.py -q` | ❌ W0 | ⬜ pending |
| 9-01-02 | 01 | 1 | UX-02 | — | POST /api/chat with source_filter scopes results | unit | `pytest backend/tests/test_rag.py -q` | ✅ | ⬜ pending |
| 9-02-01 | 02 | 1 | UX-03 | — | Citation dict contains score field | unit | `pytest backend/tests/test_rag.py -q` | ✅ | ⬜ pending |
| 9-03-01 | 03 | 2 | UX-01 | — | Source filter UI renders correctly | manual | visual inspection | N/A | ⬜ pending |
| 9-03-02 | 03 | 2 | UX-03 | — | Score badge renders on citation card | manual | visual inspection | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_sources.py` — stubs for GET /api/sources endpoint (UX-01)
- [ ] Existing `backend/tests/test_rag.py` — extend for source_filter param (UX-02) and score in citations (UX-03)

*Wave 0 should be minimal — backend tests are primary; frontend UI requires live Docker for meaningful automated tests.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Source filter dropdown populates with real policy names | UX-01 | Requires live Qdrant with indexed data | Run `docker compose up`, open UI, verify dropdown shows policy titles |
| Selected source filters chat results | UX-02 | Requires live RAG pipeline | Select a source, ask a policy question, verify all citations from that source only |
| Score badge color thresholds (red/amber/green) | UX-03 | Requires live retrieval scores | Ask question, inspect badge colors at 0.20–0.45 range — expect red for Nemotron scores |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

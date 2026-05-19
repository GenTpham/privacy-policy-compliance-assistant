---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 10
status: executing
last_updated: "2026-05-13T09:21:27.847Z"
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 14
  completed_plans: 10
  percent: 71
---

# Project State

**Project:** Privacy Policy Compliance Assistant
**Milestone:** v2.0 — Production-Quality RAG
**Current Phase:** 10

---

## Phase Status

| Phase | Name | Status |
|-------|------|--------|
| 7 | Eval & Calibration | ✅ Complete (2026-05-05) |
| 8 | Corpus Expansion | ✅ Complete (2026-05-06) |
| 9 | UX Enhancements | Complete (2026-05-06) |
| 10 | Multi-user & Rate Limiting | Not started |

---

## Current Position

Phase: 10 (Multi-user & Rate Limiting) — EXECUTING
Plan: 1 of 4
**Status:** Executing Phase 10
**Progress:** [##########    ] 75% (3 of 4 v2.0 phases complete)

---

## Project Reference

See: `.planning/PROJECT.md`
**Core value:** Users can ask any compliance question and immediately get an answer with exact quotes from the authoritative policy documents — no guessing, no hallucination, traceable to source.
**Current focus:** Phase 10 — Multi-user & Rate Limiting

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| v1.0 phases complete | 6 / 6 |
| v2.0 phases complete | 3 / 4 |
| v2.0 requirements mapped | 12 / 12 |
| Plans complete (v2.0) | 10 / TBD |

---

## Accumulated Context

### Key Decisions

- No LangChain / LlamaIndex — raw Python pipeline (linear 3-step pipeline; zero framework overhead)
- Qdrant single collection `policies` with COSINE distance metric (immutable — get it right at creation)
- Named Docker volumes (not bind mounts) for Qdrant — Windows WSL2 POSIX filesystem incompatibility
- OpenAI SDK with `base_url` override for OpenRouter (covers both LLM and embeddings)
- PyJWT + pwdlib[argon2] — current FastAPI-endorsed replacements for deprecated python-jose / passlib
- React + Vite + Tailwind + shadcn/ui (not Streamlit / Gradio) — full auth control and citation panel flexibility
- Ingestion as offline script, not on-startup (avoids re-indexing on every container restart)
- Function-scoped fixtures only — module scope causes test-order-dependent state bleed with async mocks (Phase 2 Plan 01)
- asyncio_mode=auto in pytest.ini — backward-compatible with existing @pytest.mark.asyncio decorators (Phase 2 Plan 01)
- pytest.skip('stub') pattern for Wave 0 stubs — CI never blocked by pre-implementation tests (Phase 2 Plan 01)
- patch.object(rag, 'openrouter', mock) for module-level singleton mocking — cleaner than @patch decorator for async generator tests (Phase 2 Plan 02)
- stream_answer yields delta/done/error event types — HTTP SSE routing handled in chat.py (Plan 03), not in the generator itself (Phase 2 Plan 02)
- HistoryItem.role: Literal[user, assistant] is the security control — never widen (D-03 / Pitfall 3, Phase 2 Plan 03)
- Deferred opentelemetry imports inside setup_tracing() body — telemetry.py safe to import without opentelemetry installed (Phase 2 Plan 03)
- score_threshold=0.25 (not 0.55) — Nemotron embeddings are non-deterministic; cosine scores range 0.25–0.45 for relevant matches; needs formal calibration in Phase 7
- score_threshold recommended: 0.20 — Phase 7 calibration (07-03) shows threshold=0.25 is not filtering (min observed score=0.32); root cause of 23% context_hit is ranking mismatch; setting to floor 0.20 maximizes recall headroom (ANALYSIS.md)

### Open Questions (resolve during implementation)

- Optimal score_threshold — RESOLVED: 0.20 (see ANALYSIS.md). Root cause is ranking mismatch; threshold change alone does not improve context_hit
- Source filter implementation — Qdrant payload filter via `must` conditions on source field; confirm field name in existing collection metadata
- Rate limiting library — slowapi (FastAPI-compatible) or manual token bucket in middleware; decide in Phase 10
- Role field migration — existing user records in SQLite have no role column; Phase 10 needs a migration strategy

### Watch-Outs

- Qdrant distance metric is immutable after collection creation — verify Nemotron outputs normalized vectors first
- OpenRouter embedding truncation returns HTTP 200 with no error — validate token count before every embedding call
- Citation hallucination risk (17–33% in legal RAG without enforcement) — enforce via "cite or abstain" prompt + programmatic ID verification
- Nemotron embeddings are non-deterministic — eval results may vary across runs; run experiment multiple times and report mean/stdev
- test_rag.py currently asserts score_threshold == 0.55 but production uses 0.25 — Phase 7 must fix this divergence

### Todos

- (none yet — populated during phase execution)

### Blockers

- (none)

---

## Session Continuity

*Last session: 2026-05-06 — Phase 9 complete; source filter + score badge delivered, 53 backend tests green*
*Stopped at: Phase 9 complete; ready to discuss/plan Phase 10 (Multi-user & Rate Limiting)*

### v1.0 Deliverables Summary

- Phase 1: Docker Compose + Qdrant + ingestion pipeline (3,204 unique passages indexed)
- Phase 2: RAG service (stream_answer, citations) + POST /api/chat SSE endpoint
- Phase 3: JWT auth + Argon2 password hashing + ProtectedRoute
- Phase 4: React SPA — streaming chat, expandable citation cards, logout
- Phase 5: Cross-document conflict detection (CONTRADICTORY/CONSISTENT/ONE-SILENT)
- Phase 6: Docker Compose finalization — nginx SSE proxy, Phoenix optional profile, env config

---
*State initialized: 2026-04-22*
*Last updated: 2026-05-04 — v2.0 roadmap created; Phase 7 is next*

# Project State

**Project:** Privacy Policy Compliance Assistant
**Milestone:** M1 — Initial Build
**Current Phase:** Not started

---

## Phase Status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1: Infrastructure & Data Ingestion | pending | |
| Phase 2: Core RAG Pipeline | pending | |
| Phase 3: Authentication | pending | |
| Phase 4: Web Frontend | pending | |
| Phase 5: Cross-Document Conflict Detection | pending | |
| Phase 6: Integration & Docker Compose Finalization | pending | |

---

## Current Position

**Phase:** —
**Plan:** —
**Status:** Not started
**Progress:** [----------] 0%

---

## Project Reference

See: `.planning/PROJECT.md`
**Core value:** Users can ask any compliance question and immediately get an answer with exact quotes from the authoritative policy documents — no guessing, no hallucination, traceable to source.
**Current focus:** Phase 1 — Infrastructure & Data Ingestion

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases complete | 0 / 6 |
| Requirements complete | 0 / 36 |
| Plans complete | 0 / ? |

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

### Open Questions (resolve during implementation)
- Nemotron embedding dimension — probe at runtime: `len(resp.data[0].embedding)`
- Score threshold 0.55 is a starting estimate — calibrate from actual score distributions post-ingestion
- Conflict detection false-positive rate — spike test with ~20 known cross-document questions before committing to Phase 5
- Confirm OpenRouter billing is configured before bulk ingestion of 17K passages

### Watch-Outs
- Qdrant distance metric is immutable after collection creation — verify Nemotron outputs normalized vectors first
- OpenRouter embedding truncation returns HTTP 200 with no error — validate token count before every embedding call
- Citation hallucination risk (17–33% in legal RAG without enforcement) — enforce via "cite or abstain" prompt + programmatic ID verification

### Todos
- (none yet — populated during phase execution)

### Blockers
- (none)

---

## Session Continuity

*Last session: 2026-04-22 — roadmap created, ready to begin Phase 1*

---
*State initialized: 2026-04-22*
*Last updated: 2026-04-22 after roadmap creation*

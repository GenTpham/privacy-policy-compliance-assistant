# Roadmap: Privacy Policy Compliance Assistant

## Milestones

- ✅ **v1.0 MVP** — Phases 1–6 (shipped 2026-05-04)
- **v2.0 Production-Quality RAG** — Phases 7–10 (current)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–6) — SHIPPED 2026-05-04</summary>

- [x] Phase 1: Infrastructure & Data Ingestion (5/5 plans) — completed 2026-04-24
- [x] Phase 2: Core RAG Pipeline (3/3 plans) — completed 2026-04-24
- [x] Phase 3: Authentication (3/3 plans) — completed 2026-04-25
- [x] Phase 4: Web Frontend (6/6 plans) — completed 2026-04-28
- [x] Phase 5: Cross-Document Conflict Detection (2/2 plans) — completed 2026-04-29
- [x] Phase 6: Integration & Docker Compose Finalization (2/2 plans) — completed 2026-05-04

Full archive: `.planning/milestones/v1.0-ROADMAP.md`

</details>

**v2.0 Production-Quality RAG**

- [x] **Phase 7: Eval & Calibration** — Run full experiment, analyze retrieval quality, tune score_threshold, align test suite (completed 2026-05-05)
- [x] **Phase 8: Corpus Expansion** — Admin CLI to ingest PDF/TXT policy documents with dedup and validation (completed 2026-05-05)
- [x] **Phase 9: UX Enhancements** — Source filter dropdown + retrieval score display on citation cards (completed 2026-05-06)
- [ ] **Phase 10: Multi-user & Rate Limiting** — Admin user management API + per-user rate limiting

## Phase Details

### Phase 7: Eval & Calibration
**Goal**: The RAG pipeline is formally calibrated — retrieval quality is measured, the score_threshold reflects empirical data, and the test suite accurately reflects production behavior.
**Depends on**: Phase 6 (v1.0 complete — eval infrastructure exists at `backend/eval/run_experiment.py`)
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04
**Success Criteria** (what must be TRUE):
  1. Admin can run the full experiment against the validation set and see context_hit, answer_match, and retrieved metrics in the Phoenix dashboard
  2. A written root cause analysis exists explaining why context_hit is at its measured level and what the score distribution looks like
  3. score_threshold in production config is updated to the calibrated optimal value with reasoning documented in both code comments and the decision log
  4. Running `pytest` on `test_rag.py` passes with no assertion failures — the threshold asserted in tests matches the value in production config
**Plans**: 4 plans

Plans:
- [x] 07-01-PLAN.md — Move score_threshold to Settings and wire both RAG pipelines (Wave 1)
- [x] 07-02-PLAN.md — Fix test_rag.py assertions to use get_settings().score_threshold (Wave 1)
- [x] 07-03-PLAN.md — Run baseline experiment, score distribution analysis, write ANALYSIS.md (Wave 2)
- [x] 07-04-PLAN.md — Apply calibrated threshold to Settings default, update PROJECT.md, confirm pytest (Wave 3)

### Phase 8: Corpus Expansion
**Goal**: An admin can grow the policy corpus by ingesting new PDF or TXT documents via a CLI script, with safeguards against duplicate passages and tooling to verify the resulting corpus.
**Depends on**: Phase 7 (calibrated threshold ensures newly ingested passages are retrievable with correct settings)
**Requirements**: CORP-01, CORP-02
**Success Criteria** (what must be TRUE):
  1. Admin can run the ingest script pointing at a PDF or TXT file and have its passages embedded and stored in Qdrant
  2. Re-running the script on a document that is already indexed adds zero duplicate passages (content-hash dedup enforced)
  3. Admin can run a validation command that prints total passage count, sample metadata rows, and flags any anomalies (missing fields, zero-length passages, etc.)
**Plans**: 2 plans

Plans:
- [x] 08-01-PLAN.md — ingest_doc.py: single-document PDF/TXT ingest CLI with UUID5 dedup (Wave 1)
- [x] 08-02-PLAN.md — validate_corpus.py: corpus health CLI with per-source breakdown and anomaly flags (Wave 1)

### Phase 9: UX Enhancements
**Goal**: Users have clearer control over query scope and can assess retrieval confidence — source filter scopes search to a single policy, and every citation card shows its cosine similarity score.
**Depends on**: Phase 7 (calibrated threshold makes displayed scores meaningful)
**Requirements**: UX-01, UX-02, UX-03
**Success Criteria** (what must be TRUE):
  1. A dropdown in the chat UI lists all available policy sources plus an "All sources" default option
  2. When a source is selected, only passages from that policy appear in citations — no results from other sources leak through
  3. Each citation card in the UI displays the retrieval score as a numeric value (e.g. 0.38) so users can judge match confidence
  4. Selecting "All sources" restores the default multi-source retrieval behavior with no backend change required
**Plans**: 4 plans

Plans:
- [x] 09-01-PLAN.md — Backend data layer: GET /api/sources, source_filter in RAG pipeline, score in citation dicts (Wave 1)
- [x] 09-02-PLAN.md — Backend tests: test_sources_endpoint.py, extended test_rag.py + test_chat_endpoint.py (Wave 2)
- [x] 09-03-PLAN.md — Frontend types + CitationCard: Citation.score, submit sourceFilter param, score badge (Wave 2)
- [x] 09-04-PLAN.md — AskAssistantScreen: real sources fetch, source_filter wiring, real ConfidenceBar scores (Wave 2)

### Phase 10: Multi-user & Rate Limiting
**Goal**: The system supports multiple managed user accounts with role-based access control, and the API enforces per-user rate limits to prevent abuse.
**Depends on**: Phase 7 (stable production config before layering on auth changes)
**Requirements**: AUTH-05, AUTH-06, AUTH-07
**Success Criteria** (what must be TRUE):
  1. Admin can create, list, and delete user accounts via API endpoints — no self-registration flow exists
  2. A non-admin user calling user management endpoints receives HTTP 403
  3. When a user exceeds the configured requests-per-minute limit on POST /api/chat, the API returns HTTP 429 with a clear error message
  4. The rate limit is configurable per deployment (via environment variable or config) without code changes
**Plans**: 4 plans

Plans:
- [ ] 10-01-PLAN.md — Foundation: slowapi in requirements, User.is_admin, Settings.rate_limit_per_minute, core/limiter.py, require_admin (Wave 1)
- [ ] 10-02-PLAN.md — Startup migration + admin router: _migrate_add_is_admin_column, _patch_admin_is_admin, api/admin.py, login update (Wave 2)
- [ ] 10-03-PLAN.md — Chat rate limiting: @limiter.limit on POST /api/chat, request: Request param, body rename (Wave 2)
- [ ] 10-04-PLAN.md — Tests: conftest fixtures, test_admin.py (AUTH-05/07), test_rate_limit.py (AUTH-06) (Wave 3)

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Infrastructure & Data Ingestion | v1.0 | 5/5 | Complete | 2026-04-24 |
| 2. Core RAG Pipeline | v1.0 | 3/3 | Complete | 2026-04-24 |
| 3. Authentication | v1.0 | 3/3 | Complete | 2026-04-25 |
| 4. Web Frontend | v1.0 | 6/6 | Complete | 2026-04-28 |
| 5. Cross-Document Conflict Detection | v1.0 | 2/2 | Complete | 2026-04-29 |
| 6. Integration & Docker Compose Finalization | v1.0 | 2/2 | Complete | 2026-05-04 |
| 7. Eval & Calibration | v2.0 | 4/4 | Complete    | 2026-05-05 |
| 8. Corpus Expansion | v2.0 | 0/2 | Not started | - |
| 9. UX Enhancements | v2.0 | 0/4 | Not started | - |
| 10. Multi-user & Rate Limiting | v2.0 | 0/4 | Not started | - |

---
*v1.0 shipped: 2026-05-04*
*v2.0 roadmap created: 2026-05-04*

# Requirements: Privacy Policy Compliance Assistant

**Defined:** 2026-05-04
**Core Value:** Users can ask any compliance question and immediately get an answer with exact quotes from the authoritative policy documents — no guessing, no hallucination, traceable to source.

## v2.0 Requirements

### Eval & Calibration

- [x] **EVAL-01**: User (admin) can run a full experiment on the validation dataset and see context_hit / answer_match / retrieved metrics in Phoenix
- [x] **EVAL-02**: System documents root cause analysis of context_hit metric and retrieval quality findings
- [ ] **EVAL-03**: score_threshold is updated to the calibrated optimal value with documented reasoning in code and decision log
- [ ] **EVAL-04**: test_rag.py assertions reflect the actual production score_threshold (no divergence between test and prod)

### Corpus

- [ ] **CORP-01**: Admin can ingest a new PDF or TXT policy document into Qdrant via a CLI script, with content-hash dedup preventing duplicate passages
- [ ] **CORP-02**: Admin can validate the corpus after ingestion — script reports passage count, samples metadata, and flags anomalies

### UX

- [ ] **UX-01**: User can select a specific policy source from a dropdown in the chat UI to scope their query ("All sources" is the default)
- [ ] **UX-02**: Backend filters Qdrant retrieval by source when a filter is active — only passages from the selected policy are returned
- [ ] **UX-03**: Each citation card in the UI displays the retrieval score (cosine similarity) so users can assess match confidence

### Multi-user & Rate Limiting

- [ ] **AUTH-05**: Admin can create, list, and delete user accounts via an API (no self-registration)
- [ ] **AUTH-06**: Per-user rate limiting on POST /api/chat — configurable requests-per-minute, returns HTTP 429 when exceeded
- [ ] **AUTH-07**: User model has a role field (admin / user) — admin role required to access user management endpoints

## v3.0 Requirements (deferred)

### Corpus (end-user)

- **CORP-03**: User can upload a PDF/TXT policy document directly via the chat UI
- **CORP-04**: Uploaded document is processed, chunked, embedded, and available for querying within 60 seconds

### Observability

- **OBS-01**: Phoenix alert triggers when context_hit falls below configurable threshold over a rolling window
- **OBS-02**: Admin dashboard shows corpus health — total passages, passages per source, last ingestion timestamp

## Out of Scope

| Feature | Reason |
|---------|--------|
| End-user file upload via UI | Deferred to v3.0; admin script covers corpus expansion in v2.0 |
| OAuth / SSO | Username+password sufficient; multi-user = admin-managed accounts, not federated login |
| Fine-tuning or retraining models | Inference only via OpenRouter |
| Real-time policy monitoring / alerts | Static corpus; OBS-01 deferred to v3.0 |
| Multi-language UI | Responses may be Vietnamese but UI labels remain English |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| EVAL-01 | Phase 7 | Complete (07-03) |
| EVAL-02 | Phase 7 | Complete (07-03) |
| EVAL-03 | Phase 7 | Pending |
| EVAL-04 | Phase 7 | Pending |
| CORP-01 | Phase 8 | Pending |
| CORP-02 | Phase 8 | Pending |
| UX-01 | Phase 9 | Pending |
| UX-02 | Phase 9 | Pending |
| UX-03 | Phase 9 | Pending |
| AUTH-05 | Phase 10 | Pending |
| AUTH-06 | Phase 10 | Pending |
| AUTH-07 | Phase 10 | Pending |

**Coverage:**
- v2.0 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-04*
*Last updated: 2026-05-04 — traceability confirmed against v2.0 roadmap (Phases 7–10)*

---
phase: 8
slug: corpus-expansion
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-05
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | CLI integration tests (manual run against live Qdrant) |
| **Config file** | none — scripts run directly |
| **Quick run command** | `python -m backend.ingestion.ingest_doc --help` |
| **Full suite command** | `python -m backend.ingestion.validate_corpus` |
| **Estimated runtime** | ~10 seconds (validate_corpus scroll) |

---

## Sampling Rate

- **After every task commit:** `python -m backend.ingestion.ingest_doc --help` (import sanity check)
- **After every plan wave:** Full CLI integration test (dry-run + validate)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | CORP-01 | — | N/A | cli | `python -m backend.ingestion.ingest_doc --help` | ✅ | ⬜ pending |
| 08-01-02 | 01 | 1 | CORP-01 | — | dedup enforced | cli | `python -m backend.ingestion.ingest_doc sample.pdf --title "T" --dry-run` | ✅ W1 | ⬜ pending |
| 08-02-01 | 02 | 1 | CORP-02 | — | N/A | cli | `python -m backend.ingestion.validate_corpus` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- No pytest stubs needed — both deliverables are CLI scripts tested by running them.
- Qdrant must be running: `docker compose up qdrant -d`

*Existing infrastructure covers all phase requirements once Qdrant is up.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Zero new chunks on re-ingest | CORP-01 | Requires live Qdrant + real file | Run ingest_doc twice on same file; confirm second run logs 0 new chunks |
| Corpus anomaly detection | CORP-02 | Requires corpus data | Run validate_corpus and verify output has all 4 sections |
| Dry-run writes nothing | CORP-01 | Requires count before/after | Count via validate_corpus before and after --dry-run; counts must match |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

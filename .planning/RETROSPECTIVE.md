# Retrospective

Living retrospective across all milestones.

---

## Milestone: v1.0 — MVP

**Shipped:** 2026-05-04
**Phases:** 6 | **Plans:** 21 | **Commits:** ~158

### What Was Built

- **Phase 1** — Ingestion pipeline: 25K rows → 3,204 unique passages embedded (Nemotron 2048-dim) into Qdrant with checkpoint/dedup/sanity-check
- **Phase 2** — RAG pipeline: SSE streaming `/chat` endpoint with grounded answer generation (Gemma 4 26B) and citation verification
- **Phase 3** — JWT authentication: login/refresh/logout, Argon2 hashing, ProtectedRoute, silent token refresh on 401
- **Phase 4** — React SPA: SSE streaming chat UI, expandable CitationCards, NoMatchMessage, LoginForm, useSSEChat hook
- **Phase 5** — Conflict detection: keyword-triggered routing, CONTRADICTORY/CONSISTENT/ONE-SILENT verdict classification
- **Phase 6** — Docker Compose: 3-service stack (qdrant + backend + frontend), nginx SSE proxy, healthchecks, smoke-test target

### What Worked

- **GSD wave-based parallelization** — parallel executor agents in worktrees delivered each phase faster than sequential would; Wave structure matched natural dependency ordering
- **Code review → immediate fix cycle** — `gsd-code-review` caught real issues (null guard in api.ts, nginx SSE timeout, qdrant healthcheck) that would have caused production bugs
- **Checkpoint-based ingestion** — resume-from-checkpoint made iterative ingestion development safe without losing progress
- **Human checkpoint in plan 06-02** — catching E2E issues (qdrant version mismatch, JWT_SECRET naming) before marking phase complete saved a re-execution cycle

### What Was Inefficient

- **Code reviewer pinned wrong qdrant version** — `v1.13.4` (auto-pinned from `latest`) is incompatible with `qdrant-client==1.17.1`; required 3 fix iterations to land on the correct version (`v1.17.1`)
- **score_threshold=0.55 shipped in Phase 2 without calibration** — Nemotron produces cosine scores of ~0.25–0.45 for relevant matches; the original 0.55 threshold silently returned "no match" for valid queries; caught only during E2E testing in Phase 6
- **Sanity check threshold of 0.99** — designed for deterministic embeddings; Nemotron is non-deterministic across API calls; caused ingestion to always fail the post-ingest check
- **REQUIREMENTS.md progress table not auto-updated** — progress table showed 0/5 "Planned" for all phases at milestone close; required manual ROADMAP.md rewrite

### Patterns Established

- Qdrant server version MUST match `qdrant-client` minor version (|server_minor - client_minor| ≤ 1)
- Nemotron embedding scores: calibrate retrieval thresholds empirically before setting them; 0.25 works, 0.55 does not
- Use `CMD ["bash", "-c", "..."]` (not `CMD-SHELL`) for `/dev/tcp` healthchecks in images without curl/wget
- `VITE_*` env vars baked at build time — `docker compose.yml` must pass them as `ARG`/`ENV` in the Dockerfile, not `env_file`
- Export `BASE_URL` (not `const`) to satisfy TypeScript `noUnusedLocals` when the constant is declared for future use

### Key Lessons

1. **Pin container image versions to match client library versions** — `qdrant:latest` works during dev, but pin both server and client to the same minor version before shipping
2. **Calibrate embedding thresholds on real data before setting them in code** — a threshold that looks reasonable in theory (0.55 cosine) can silently break everything if the embedding model has different score ranges
3. **Test E2E early** — the qdrant version mismatch and JWT_SECRET naming issues only surfaced during Phase 6 E2E; earlier integration testing would have caught them sooner
4. **Checkpoint files are instance-specific** — `ingestion_checkpoint.json` assumes the same Qdrant collection; wiping the volume requires deleting the checkpoint too

### Cost Observations

- Sessions: multiple across 12 days
- Model mix: primarily Sonnet-class for execution agents, Sonnet for verification
- Notable: parallel worktree execution per wave reduced wall-clock time significantly vs sequential

---

## Cross-Milestone Trends

| Metric | v1.0 |
|--------|------|
| Phases | 6 |
| Plans | 21 |
| Timeline (days) | 12 |
| Python LOC | ~1,600 |
| TypeScript LOC | ~3,000 |
| Post-execution fixes | 7 |
| Code review findings fixed | 6/9 |

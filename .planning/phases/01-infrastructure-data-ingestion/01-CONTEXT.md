# Phase 1: Infrastructure & Data Ingestion — Context

**Gathered:** 2026-04-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Set up the Docker Compose infrastructure (Qdrant + backend shell), create the Python 3.11 `.venv` for local development, and run the one-shot ingestion script that reads the privacy policy dataset, embeds all passages via Nemotron on OpenRouter, and upserts them into Qdrant with full metadata. Phase complete when: Qdrant is queryable, all ~17K passages are indexed, and the sanity check (embed a known passage → assert it ranks #1) passes.

**Does NOT include:** FastAPI chat endpoint, authentication, frontend, or cross-document logic — those are Phases 2–5.

</domain>

<decisions>
## Implementation Decisions

### Dataset Scope
- **D-01:** Index **train split only** (`dataset/json/train/policy_qa_train.json`, ~17K passages). The test and validation splits are reserved as held-out eval benchmarks to measure RAG quality after Phase 2.
- **D-02:** **Deduplicate by context text** — skip any passage whose text hash already exists in Qdrant before upserting. This keeps the index clean and prevents inflated recall metrics.

### Ingestion Resumability
- **D-03:** **Checkpoint file** — the ingestion script writes a progress file (`ingestion_checkpoint.json`) after each batch completes. On re-run, batches already confirmed in the checkpoint are skipped. Safe to re-run after a rate-limit failure or network error without re-embedding already-processed passages.
- **D-04:** **Batch size: 50 passages per OpenRouter embedding request.** Conservative for free-tier rate limits; easy to tune up to 100 for paid tier.

### Development Workflow
- **D-05:** **Qdrant in Docker, backend local** — during development, only `docker compose up qdrant` is run. FastAPI runs locally with `.venv` and `uvicorn --reload` for fast iteration. This is the primary dev mode documented in the README.
- **D-06:** `uvicorn --reload` enabled for local dev. The Docker production image runs uvicorn without `--reload`.
- **D-07:** Python 3.11 virtual environment is created with `python3.11 -m venv .venv` before any local dev. `.venv/` is added to `.dockerignore` to prevent platform-incompatible binaries from entering the Docker build context.

### Qdrant Collection Ownership
- **D-08:** **Both — belt and suspenders:**
  - The ingestion script probes Nemotron (one test embed call) to discover the embedding dimension, then creates the `policies` collection if it does not exist.
  - The FastAPI backend also checks at startup (lifespan event) and creates the collection if missing — ensures the API never starts in a broken state even if ingestion was never run.
- **D-09:** If the collection already exists when the ingestion script runs, **skip creation and proceed to upsert** — safe for re-runs and partial re-ingestion.
- **D-10:** Distance metric: **COSINE** (Nemotron outputs L2-normalized vectors; cosine and dot-product are equivalent, cosine is conventional). The metric is immutable after collection creation — must be verified correct before the first production ingest run.

### Critical Infrastructure Details (from research)
- **D-11:** Qdrant uses a **named Docker volume** (`qdrant_storage`), never a bind mount. Windows/WSL2 bind mounts cause data loss and Qdrant v1.15.0+ will refuse to start on POSIX-incompatible mounts.
- **D-12:** FastAPI service uses `restart: on-failure` and a `depends_on: condition: service_healthy` on the Qdrant healthcheck. Qdrant container includes a `healthcheck` definition.
- **D-13:** Backend connects to Qdrant via service name `qdrant` (not `localhost`) when running inside Docker Compose.
- **D-14:** All secrets (`OPENROUTER_API_KEY`, `JWT_SECRET`, `QDRANT_API_KEY`) loaded from `.env` via `pydantic-settings`. Validated at startup — service fails fast if required vars are missing.

### Claude's Discretion
- Specific chunking logic beyond the research-derived parameters (400-token target, 50-token overlap, semantic separators) — planner and executor can decide the exact implementation.
- Progress reporting format in the ingestion script (tqdm vs simple print) — executor's choice.
- Exact `.env.example` variable names — follow the `pydantic-settings` `Settings` class field names.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §Infrastructure & Deployment (INFRA-01–05)
- `.planning/REQUIREMENTS.md` §Data Ingestion (INGEST-01–06)

### Research Findings
- `.planning/research/STACK.md` — confirmed library versions, Qdrant setup pattern, pydantic-settings config
- `.planning/research/PITFALLS.md` §C1 (distance metric), §C2 (Windows named volumes), §C3 (chunking), §C6 (embedding truncation), §M4 (startup order), §M5 (container hostnames), §M6 (no venv in Docker), §M7 (rate limits)
- `.planning/research/ARCHITECTURE.md` §Chunking Strategy, §Qdrant Collection Design, §Build Order

### Dataset
- `dataset/json/train/policy_qa_train.json` — the corpus to index (fields: id, title, context, question, answers)

No external ADRs or specs — all decisions captured above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None yet — this is the first phase of a greenfield project.

### Established Patterns
- None yet — this phase establishes the foundational patterns.

### Integration Points
- `dataset/json/train/policy_qa_train.json` is the input to the ingestion script; the `context` field of each record is the passage to index, `title` is the source document name.
- The `policies` Qdrant collection created here is the primary integration point for Phase 2 (RAG pipeline queries it).
- The `.env` file and `pydantic-settings` config class created here are reused by every subsequent phase.

</code_context>

<specifics>
## Specific Ideas

- The ingestion sanity check should embed a known passage (e.g., the first record in the train set), query Qdrant for it, and assert it appears as the #1 result. This validates both the distance metric and the embedding pipeline end-to-end before declaring Phase 1 complete.
- The checkpoint file path: `ingestion_checkpoint.json` in the project root (or `backend/ingestion/`), gitignored.
- `.venv/` must be in both `.gitignore` and `.dockerignore`.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-infrastructure-data-ingestion*
*Context gathered: 2026-04-22*

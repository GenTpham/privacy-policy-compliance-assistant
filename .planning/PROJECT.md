# Privacy Policy Compliance Assistant

## What This Is

A RAG-based chatbot that lets users ask natural-language questions about privacy policies — e.g. "chính sách nào áp dụng cho lưu trữ dữ liệu khách hàng" or "quy định nào mâu thuẫn giữa hai tài liệu" — and receive answers with inline citations from the source documents. The system indexes 3,204 unique privacy policy passages from a 25K-row corpus, retrieves the most relevant chunks via semantic search, then uses an LLM to synthesize a grounded answer. Deployed via Docker Compose with a React web UI and JWT authentication.

## Core Value

Users can ask any compliance question and immediately get an answer with exact quotes from the authoritative policy documents — no guessing, no hallucination, traceable to source.

## Current Milestone: v2.0 Production-Quality RAG

**Goal:** Nâng RAG từ prototype lên production-ready — retrieval được calibrate, corpus mở rộng, UX rõ ràng hơn, và hỗ trợ multi-user.

**Target features:**
- Eval & calibration: chạy experiment đầy đủ, tune score_threshold, fix test suite
- Corpus expansion: admin script ingest PDF/TXT thêm; UI upload trong milestone sau
- Source filter + score display: user filter theo policy, hiển thị retrieval score trên citation cards
- Rate limiting + multi-user: per-user rate limit, admin quản lý users

## Current State

**v1.0 shipped: 2026-05-04**

- 6 phases complete · 21 plans · ~1,600 Python LOC · ~3,000 TypeScript LOC
- Stack: FastAPI + Qdrant + React (Vite) + nginx — all services run via `docker compose up`
- Corpus: 3,204 unique passages indexed (deduplicated from 25,017 dataset rows)
- Models: Gemma 4 26B A4B (generation) + Nemotron Embed VL 1B V2 (embedding) via OpenRouter
- Known: Nemotron embeddings are non-deterministic; RAG score_threshold tuned to 0.25 (not 0.55)

## Requirements

### Validated (v1.0)

- [x] Document ingestion pipeline: extract context passages from dataset JSON, embed with NVIDIA Nemotron, store in Qdrant — *Phase 1*
- [x] Semantic search: embed user query and retrieve top-k relevant chunks from Qdrant — *Phase 1*
- [x] Answer generation: pass retrieved chunks to Gemma 4 26B A4B (OpenRouter) with prompt instructing grounded response — *Phase 2*
- [x] Inline citations: response displays verbatim excerpt(s) from source document alongside the generated answer — *Phase 2*
- [x] Authentication: JWT login/refresh/logout with Argon2 password hashing, ProtectedRoute on frontend — *Phase 3*
- [x] Web UI: React SPA with SSE streaming, expandable citation cards, no-match message, logout — *Phase 4*
- [x] Cross-document comparison: CONTRADICTORY/CONSISTENT/ONE-SILENT verdict classification with cited passages from each document — *Phase 5*
- [x] Docker Compose: qdrant + backend + frontend all healthy, nginx SSE proxy, phoenix optional via `--profile observability` — *Phase 6*
- [x] Environment config: API keys loaded from `.env`, Python 3.11 virtualenv for local dev — *Phase 6*
- [x] Eval & calibration: formal experiment run, 23% context_hit, root cause = ranking mismatch, score_threshold calibrated to 0.20 — *Phase 7*
- [x] Test suite alignment: test_rag.py assertions use get_settings().score_threshold (no hardcoded values) — *Phase 7*

### Active (v2.0)

- [ ] Corpus expansion (admin): script to ingest additional PDF/TXT policy documents with dedup
- [ ] Source filter: user selects specific policy source via UI dropdown; Qdrant payload filter on backend
- [ ] Score display: show retrieval score on each citation card in the React UI
- [ ] Rate limiting: per-user request rate limit on the API
- [ ] Multi-user: admin creates/manages users, role-based access control

### Out of Scope

- End-user file upload via UI — deferred to v2.1; admin script covers corpus expansion in v2.0
- Real-time policy monitoring / alerts — static corpus only
- Multi-language UI — responses may be in Vietnamese but UI labels are English
- Fine-tuning or retraining models — inference only via OpenRouter
- OAuth / SSO — username+password sufficient; multi-user means admin-managed accounts, not federated login

## Context

**Dataset:** `dataset/json/` contains SQuAD-style QA pairs (train: 17,056 / test / validation). Each record has:
- `id`, `title` (domain/site name), `context` (policy passage), `question`, `answers` (ground truth)
- The `context` fields are the RAG corpus. The `question`/`answers` pairs serve as an eval benchmark.
- After content-hash deduplication: 3,204 unique passages indexed in Qdrant

**Models (via OpenRouter):**
- LLM: `google/gemma-4-26b-a4b` — generation
- Embedding: `nvidia/llama-nemotron-embed-vl-1b-v2` — vectorization (dim: 2048, non-deterministic)

**API key:** stored in `.env` as `OPENROUTER_API_KEY`

**Vector store:** Qdrant v1.17.1 — matches qdrant-client==1.17.1 (pin matters; v1.13.4 caused incompatibility)

**Dev environment:** Python 3.11, create `.venv` before running (`python3.11 -m venv .venv`)

## Constraints

- **Tech Stack**: Python 3.11 only — explicit runtime requirement
- **Models**: OpenRouter exclusively (Gemma 4 26B A4B + Nemotron Embed VL 1B V2) — no substitutions
- **Vector Store**: Qdrant — selected for Docker Compose integration
- **Deployment**: Docker Compose — all services must run via `docker compose up`
- **Auth**: Required — UI must be gated behind login
- **No cloud cost beyond OpenRouter**: Qdrant runs locally in Docker

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| RAG over fine-tuning | Model doesn't need to "memorize" policies; retrieval ensures answers reflect current documents and are traceable | ✓ Good — citations grounded, no hallucination observed |
| Qdrant over ChromaDB/FAISS | Production-ready persistence, native Docker support, fits Docker Compose deployment | ✓ Good — persistent volume survived restarts |
| OpenRouter for both LLM and embeddings | Single API key, unified billing, specified models available | ✓ Good — one SDK covers both chat and embeddings |
| Cross-doc comparison in v1 | User explicitly requested conflict detection between documents from the start | ✓ Good — keyword-triggered routing works cleanly |
| Dataset contexts as corpus | 17K passages from real privacy policies provide immediate corpus without manual document collection | ⚠ Revisit — 3,204 unique after dedup; coverage gaps exist for specific sites |
| score_threshold=0.20 (calibrated Phase 7, 2026-05-05) | Empirically determined from 100-example validation set experiment. Score distribution analysis (see phases/07-eval-calibration/ANALYSIS.md): min retrieved score was 0.32, no scores in 0.20–0.32 range, meaning 0.25 was not filtering anything. Root cause of 23% context_hit is ranking mismatch, not threshold filtering. Hard floor >= 0.20 enforced per D-06. Overridable via SCORE_THRESHOLD env var. | ✓ Calibrated — threshold at D-06 floor maximizes recall headroom; ranking improvement deferred to v2.1 |
| qdrant:v1.17.1 pin | qdrant-client==1.17.1 requires server minor version within 1; v1.13.4 caused incompatibility | ✓ Good — pin server to match client version |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-05 — Phase 7 complete: RAG pipeline calibrated, score_threshold=0.20, test suite aligned*

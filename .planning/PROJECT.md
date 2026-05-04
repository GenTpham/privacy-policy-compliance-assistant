# Privacy Policy Compliance Assistant

## What This Is

A RAG-based chatbot that lets users ask natural-language questions about privacy policies — e.g. "chính sách nào áp dụng cho lưu trữ dữ liệu khách hàng" or "quy định nào mâu thuẫn giữa hai tài liệu" — and receive answers with inline citations from the source documents. The system indexes a corpus of 17K+ privacy policy passages, retrieves the most relevant chunks via semantic search, then uses an LLM to synthesize a grounded answer. Deployed via Docker Compose with a web UI and authentication.

## Core Value

Users can ask any compliance question and immediately get an answer with exact quotes from the authoritative policy documents — no guessing, no hallucination, traceable to source.

## Requirements

### Validated

- [x] Document ingestion pipeline: extract context passages from dataset JSON, embed with NVIDIA Nemotron, store in Qdrant — *Validated in Phase 1: Infrastructure & Data Ingestion*
- [x] Semantic search: embed user query and retrieve top-k relevant chunks from Qdrant — *Validated in Phase 1: Infrastructure & Data Ingestion*
- [x] Answer generation: pass retrieved chunks to Gemma 4 26B A4B (OpenRouter) with prompt instructing grounded response — *Validated in Phase 2: Core RAG Pipeline*
- [x] Inline citations: response displays verbatim excerpt(s) from source document alongside the generated answer — *Validated in Phase 2: Core RAG Pipeline*
- [x] Authentication: user login required to access the chat interface — *Validated in Phase 3: Authentication*

### Active

- [x] Cross-document comparison: identify and surface contradictions/conflicts between policies across multiple documents in a single query — *Validated in Phase 5: Cross-Document Conflict Detection*
- [x] Web UI: chat interface with message history, input box, and citation display panel — *Validated in Phase 4: Web Frontend*
- [x] Docker Compose: all services (API backend, Qdrant, frontend) packaged and runnable with `docker compose up` — *Validated in Phase 6: Integration & Docker Compose Finalization*
- [x] Environment config: API keys loaded from `.env`, Python 3.11 virtualenv for local dev — *Validated in Phase 6: Integration & Docker Compose Finalization*

### Out of Scope

- File upload by end-users — corpus is fixed from the dataset; no user-uploaded documents in v1
- Real-time policy monitoring / alerts — static corpus only
- Multi-language UI — responses may be in Vietnamese but UI labels are flexible
- Fine-tuning or retraining models — inference only via OpenRouter

## Context

**Dataset:** `dataset/json/` contains SQuAD-style QA pairs (train: 17,056 / test / validation). Each record has:
- `id`, `title` (domain/site name), `context` (policy passage), `question`, `answers` (ground truth)
- The `context` fields are the RAG corpus. The `question`/`answers` pairs serve as an eval benchmark.

**Models (via OpenRouter):**
- LLM: `google/gemma-4-26b-a4b` — generation
- Embedding: `nvidia/llama-nemotron-embed-vl-1b-v2` — vectorization

**API key:** stored in `.env` as `OPENROUTER_API_KEY`

**Vector store:** Qdrant — chosen for production-ready persistence and Docker support

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
| RAG over fine-tuning | Model doesn't need to "memorize" policies; retrieval ensures answers reflect current documents and are traceable | — Pending |
| Qdrant over ChromaDB/FAISS | Production-ready persistence, native Docker support, fits Docker Compose deployment | — Pending |
| OpenRouter for both LLM and embeddings | Single API key, unified billing, specified models available | — Pending |
| Cross-doc comparison in v1 | User explicitly requested conflict detection between documents from the start | — Pending |
| Dataset contexts as corpus | 17K passages from real privacy policies provide immediate corpus without manual document collection | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-28 — Phase 5 complete: cross-document conflict detection (is_conflict_query + stream_conflict_answer + Verdict classification prompt; 32/32 tests green)*

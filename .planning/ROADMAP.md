# Roadmap: Privacy Policy Compliance Assistant

**6 phases** | **36 requirements**

---

## Phase Overview

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|-----------------|
| 1 | Infrastructure & Data Ingestion | Qdrant is running, the full corpus is indexed, and ingestion health checks pass | INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, INGEST-06 | 4 criteria |
| 2 | Core RAG Pipeline | 3/3 | Complete   | 2026-04-24 |
| 3 | Authentication | All chat endpoints are JWT-protected; login, refresh, and logout work end-to-end | AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05 | 4 criteria |
| 4 | Web Frontend | A browser user can log in, ask questions, see streamed answers with expandable citation cards, and log out | UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, CITE-04 | 5 criteria |
| 5 | Cross-Document Conflict Detection | Comparison queries retrieve multi-document chunks and return a classified conflict response with cited passages from each source | CONFLICT-01, CONFLICT-02, CONFLICT-03, CONFLICT-04 | 4 criteria |
| 6 | Integration & Docker Compose Finalization | The entire system starts with `docker compose up`, all health checks pass, and an end-to-end browser session works without manual intervention | (integration of all prior phases — no new requirements) | 4 criteria |

---

## Phase Details

### Phase 1: Infrastructure & Data Ingestion
**Goal:** Qdrant is running in Docker, the 17K-passage corpus is embedded and indexed with correct metadata, and ingestion health checks confirm the vector store is queryable.
**UI hint**: no
**Requirements:** INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, INGEST-06
**Success Criteria:**
1. Running `docker compose up` starts the Qdrant container and the backend service waits for Qdrant health before accepting requests.
2. After running the ingestion script, Qdrant reports the expected collection with all context passages stored, each chunk carrying `text`, `title`, `source_doc`, and `chunk_index` metadata.
3. The ingestion sanity check passes: a known passage is embedded, queried, and confirmed to rank #1 in search results.
4. A developer can run the backend locally using the Python 3.11 `.venv` with all secrets loaded from `.env` — no API keys appear in source code.
**Plans**: 5 plans

Plans:
- [ ] 01-PLAN-01-project-scaffolding.md — Project directory structure, requirements.txt, .env.example, .gitignore, .dockerignore
- [ ] 01-PLAN-02-docker-compose-infrastructure.md — docker-compose.yml (Qdrant named volume + healthcheck) and backend Dockerfile
- [ ] 01-PLAN-03-fastapi-backend-shell.md — pydantic-settings config, FastAPI lifespan with Qdrant collection bootstrap, /health endpoint
- [ ] 01-PLAN-04-ingestion-pipeline.md — Text chunker and full ingestion script (dedup, checkpoint, rate-limit backoff, sanity check)
- [ ] 01-PLAN-05-ingestion-eval-suite.md — Pytest eval suite covering all 10 AI-SPEC eval dimensions + Makefile targets

---

### Phase 2: Core RAG Pipeline
**Goal:** The `/chat` endpoint accepts a question, retrieves relevant chunks from Qdrant, streams a grounded answer via SSE, and returns a response payload with verified inline citations.
**UI hint**: no
**Requirements:** RAG-01, RAG-02, RAG-03, RAG-04, RAG-05, RAG-06, RAG-07, CITE-01, CITE-02, CITE-03
**Success Criteria:**
1. A `curl` request to `/chat` with a policy question returns a streamed SSE response with the first token arriving within 3 seconds.
2. The response payload contains `{answer, citations: [{id, title, text}]}` where every cited ID matches a chunk in the retrieved set (no fabricated IDs).
3. Every answer includes at least one verbatim excerpt from a retrieved chunk with the source document title.
4. When no chunk exceeds the 0.55 score threshold, the endpoint returns a "no matching policy found" message without calling the LLM.
5. Follow-up questions that reference the previous turn produce coherent answers, confirming conversation history (last 3 turns) is included in the prompt.
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md — Wave 0: pytest infrastructure (pytest.ini, conftest.py, 10+2 test stubs)
- [x] 02-02-PLAN.md — Wave 1: backend/app/services/rag.py (embed, retrieve, stream, verify citations)
- [x] 02-03-PLAN.md — Wave 1: backend/app/api/chat.py (router, Pydantic models, StreamingResponse) + main.py wiring

---

### Phase 3: Authentication
**Goal:** All chat endpoints require a valid JWT; users can log in with username/password, receive access and refresh tokens, and re-authenticate transparently when the access token expires.
**UI hint**: no
**Requirements:** AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05
**Success Criteria:**
1. A `curl` request to `/chat` without an Authorization header receives HTTP 401.
2. A user can POST to `/auth/login` with correct credentials and receive an access token (expires 30 min) and a refresh token.
3. Using the refresh token against `/auth/refresh` issues a new access token without re-entering credentials.
4. Passwords are stored as Argon2 hashes in SQLite; querying the database directly reveals no plaintext passwords.
**Plans**: 3 plans

Plans:
- [x] 03-01-PLAN.md — Wave 1: test infrastructure (conftest.py auth fixtures + 10 test stubs in test_auth.py)
- [x] 03-02-PLAN.md — Wave 2: DB layer (models.py + session.py) + auth service (JWT + password)
- [x] 03-03-PLAN.md — Wave 3: config extension + lifespan wiring + auth router + chat protection + 10 tests green

---

### Phase 4: Web Frontend
**Goal:** A browser user can log in through a React SPA, submit questions and see streamed tokens appear progressively, view expandable citation cards under each answer, see "no matching policy" messages, and log out cleanly.
**UI hint**: yes
**Requirements:** UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, CITE-04
**Success Criteria:**
1. An unauthenticated browser visit to the app redirects to the login page; after entering valid credentials the user lands on the chat interface.
2. Typing a question and submitting causes response tokens to appear character-by-character (streaming), not all at once after a delay.
3. Each assistant message displays expandable citation cards below the answer, each card showing the document title and the full verbatim excerpt.
4. When no relevant policy is found, the UI shows a clearly worded "No matching policy found" message in place of an answer.
5. Clicking the logout button clears the session and returns the user to the login page, with the chat endpoint now returning HTTP 401.
**Plans**: 6 plans

Plans:
- [x] 04-01-PLAN.md — Wave 1: Vite+React scaffold, shadcn/ui init (new-york), vitest+happy-dom config, 6 test stub files
- [x] 04-02-PLAN.md — Wave 2: tokens.ts, api.ts (fetchWithAuth + silent refresh), vite.config.ts proxy, App.tsx routes, ProtectedRoute
- [x] 04-03-PLAN.md — Wave 3: useAuth hook (login/logout/forceLogout), LoginForm (all states), LoginPage layout
- [x] 04-04-PLAN.md — Wave 3: useSSEChat hook (SSE parser), StreamingCursor, CitationCard, NoMatchMessage (parallel with plan 03)
- [x] 04-05-PLAN.md — Wave 4: MessageBubble, MessageList, ChatInput, Header, ChatPage composition
- [x] 04-06-PLAN.md — Wave 5: All 6 test stubs replaced with passing implementations

---

### Phase 5: Cross-Document Conflict Detection
**Goal:** Queries that imply cross-document comparison trigger a dedicated retrieval and prompting path that returns a structured conflict classification citing exact passages from each involved document.
**UI hint**: no
**Requirements:** CONFLICT-01, CONFLICT-02, CONFLICT-03, CONFLICT-04
**Success Criteria:**
1. Submitting a question containing "conflict", "mâu thuẫn", "so sánh", or "differ" causes the system to retrieve top-10 chunks (not top-5) from across all source documents.
2. The response for a comparison query uses the conflict-detection prompt and classifies the relevant passages as contradictory, consistent, or one-silent.
3. The conflict response identifies the specific documents involved and cites exact passages from each side by numeric chunk ID.
4. A standard single-document query is unaffected — it still uses top-5 retrieval and the normal grounded-response prompt.
**Plans**: 2 plans

Plans:
- [x] 05-01-PLAN.md — Wave 0: test stubs (conftest fixture + 6 test_rag stubs + 3 test_chat_endpoint stubs)
- [x] 05-02-PLAN.md — Wave 1: is_conflict_query + routing branch (chat.py) + stream_conflict_answer + _build_conflict_messages (rag.py)

---

### Phase 6: Integration & Docker Compose Finalization
**Goal:** The complete system — Qdrant, FastAPI backend, and React frontend — starts reliably with `docker compose up`, all health checks pass, restart policies handle failures, and an end-to-end browser session (login → question → streamed answer with citations → logout) works without manual intervention.
**UI hint**: no
**Requirements:** (integration phase — all 36 v1 requirements exercised end-to-end; no new requirement IDs)
**Success Criteria:**
1. Running `docker compose up` on a clean machine (with `.env` populated) brings all services healthy within 60 seconds and no manual steps are required.
2. Stopping and restarting containers leaves Qdrant data intact — previously indexed passages are immediately queryable after restart.
3. An end-to-end browser session completes successfully: login → type a policy question → receive a streamed, cited answer → log out.
4. A comparison query ("mâu thuẫn") in the same session returns a conflict-classified response citing passages from multiple documents.
**Plans**: 2 plans

Plans:
- [x] 06-01-PLAN.md — Wave 1: docker-compose.yml (backend healthcheck + frontend service + phoenix observability profile) + frontend/Dockerfile (node:20-alpine → nginx:alpine) + frontend/nginx.conf (SSE proxy + SPA routing)
- [ ] 06-02-PLAN.md — Wave 2: Makefile smoke-test target + VERIFICATION.md (E2E browser checklist) + frontend/src/lib/api.ts BASE_URL constant

---

## Requirement Coverage

| Requirement | Phase |
|-------------|-------|
| INFRA-01 | Phase 1 |
| INFRA-02 | Phase 1 |
| INFRA-03 | Phase 1 |
| INFRA-04 | Phase 1 |
| INFRA-05 | Phase 1 |
| INGEST-01 | Phase 1 |
| INGEST-02 | Phase 1 |
| INGEST-03 | Phase 1 |
| INGEST-04 | Phase 1 |
| INGEST-05 | Phase 1 |
| INGEST-06 | Phase 1 |
| RAG-01 | Phase 2 |
| RAG-02 | Phase 2 |
| RAG-03 | Phase 2 |
| RAG-04 | Phase 2 |
| RAG-05 | Phase 2 |
| RAG-06 | Phase 2 |
| RAG-07 | Phase 2 |
| CITE-01 | Phase 2 |
| CITE-02 | Phase 2 |
| CITE-03 | Phase 2 |
| AUTH-01 | Phase 3 |
| AUTH-02 | Phase 3 |
| AUTH-03 | Phase 3 |
| AUTH-04 | Phase 3 |
| AUTH-05 | Phase 3 |
| UI-01 | Phase 4 |
| UI-02 | Phase 4 |
| UI-03 | Phase 4 |
| UI-04 | Phase 4 |
| UI-05 | Phase 4 |
| UI-06 | Phase 4 |
| CITE-04 | Phase 4 |
| CONFLICT-01 | Phase 5 |
| CONFLICT-02 | Phase 5 |
| CONFLICT-03 | Phase 5 |
| CONFLICT-04 | Phase 5 |

**Total: 36/36** (Phase 6 is an integration phase that exercises all prior requirements — no new requirement IDs.)

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure & Data Ingestion | 0/5 | Planned | - |
| 2. Core RAG Pipeline | 0/3 | Planned | - |
| 3. Authentication | 0/3 | Planned | - |
| 4. Web Frontend | 0/6 | Planned | - |
| 5. Cross-Document Conflict Detection | 0/2 | Planned | - |
| 6. Integration & Docker Compose Finalization | 0/2 | Planned | - |

---
*Roadmap created: 2026-04-22*
*Last updated: 2026-04-28 — Phase 6 plans created (2 plans, 2 waves)*

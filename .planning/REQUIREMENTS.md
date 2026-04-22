# Requirements: Privacy Policy Compliance Assistant

**Defined:** 2026-04-22
**Core Value:** Users can ask any compliance question and immediately get an answer with exact quotes from the authoritative policy documents — no guessing, no hallucination, traceable to source.

---

## v1 Requirements

### Infrastructure & Deployment

- [ ] **INFRA-01**: System can be started with a single `docker compose up` command
- [ ] **INFRA-02**: Qdrant persists indexed data across container restarts using named Docker volumes
- [ ] **INFRA-03**: All API keys and secrets are loaded from a `.env` file; no secrets in source code
- [ ] **INFRA-04**: Backend service waits for Qdrant to be healthy before accepting requests (startup health check)
- [ ] **INFRA-05**: Python 3.11 virtual environment (`python3.11 -m venv .venv`) used for local development outside Docker

### Data Ingestion

- [ ] **INGEST-01**: Ingestion script reads all `context` passages from the dataset JSON files (`dataset/json/`)
- [ ] **INGEST-02**: Each passage is chunked to ≤450 tokens using semantic separators; list items and clauses are never split mid-item
- [ ] **INGEST-03**: Every chunk is stored in Qdrant with metadata: `{text, title, source_doc, chunk_index}`
- [ ] **INGEST-04**: Ingestion script runs as a standalone offline process (not triggered at web server startup)
- [ ] **INGEST-05**: Ingestion uses batched embedding requests and handles OpenRouter rate limits gracefully (with retry/sleep)
- [ ] **INGEST-06**: Ingestion script verifies Qdrant collection has correct distance metric by embedding a known passage and asserting it ranks #1 in search results

### RAG Pipeline

- [ ] **RAG-01**: User question is embedded via `nvidia/llama-nemotron-embed-vl-1b-v2` on OpenRouter and used to query Qdrant
- [ ] **RAG-02**: System retrieves top-5 most relevant chunks (with score threshold ≥0.55); chunks below threshold are discarded
- [ ] **RAG-03**: Retrieved chunks are passed to `google/gemma-4-26b-a4b` on OpenRouter with a grounded-response system prompt
- [ ] **RAG-04**: System prompt instructs the model to cite only from provided chunks by numeric ID; if context is insufficient, model must explicitly say so ("cite or abstain")
- [ ] **RAG-05**: LLM response is streamed to the client via Server-Sent Events (SSE); first token arrives within 3 seconds
- [ ] **RAG-06**: Conversation history (last 3 turns) is included in the LLM prompt for multi-turn follow-up queries
- [ ] **RAG-07**: When no chunk exceeds the score threshold, system returns a "no matching policy found" message without calling the LLM

### Citations

- [ ] **CITE-01**: Every answer includes at least one verbatim excerpt from a retrieved chunk, with the source document title
- [ ] **CITE-02**: Each citation is linked to its chunk ID in the response payload: `{answer, citations: [{id, title, text}]}`
- [ ] **CITE-03**: Citation IDs referenced in the answer text are verified programmatically to exist in the retrieved set (no fabricated IDs)
- [ ] **CITE-04**: Frontend displays each citation as an expandable inline panel beneath the answer, showing the document title and full verbatim excerpt

### Cross-Document Conflict Detection

- [ ] **CONFLICT-01**: System detects when a user query implies cross-document comparison (keywords: "conflict", "contradict", "mâu thuẫn", "so sánh", "khác nhau", "differ", "both documents")
- [ ] **CONFLICT-02**: For comparison queries, system retrieves top-10 chunks across all source documents (not limited to one)
- [ ] **CONFLICT-03**: Comparison queries use a dedicated conflict-detection prompt that instructs the model to classify retrieved passages as: contradictory, consistent, or one-silent
- [ ] **CONFLICT-04**: Conflict response identifies the specific documents involved and cites the exact passages from each side by numeric ID

### Authentication

- [ ] **AUTH-01**: User can log in with username and password via a login form
- [ ] **AUTH-02**: All chat endpoints require a valid JWT access token; unauthenticated requests receive HTTP 401
- [ ] **AUTH-03**: Access token expires after 30 minutes; refresh token allows re-authentication without re-entering credentials
- [ ] **AUTH-04**: Passwords are stored as Argon2 hashes; plaintext passwords are never persisted
- [ ] **AUTH-05**: JWT secret is loaded from `.env`, validated at startup for minimum 32-character length

### Web Interface

- [ ] **UI-01**: User is redirected to login page when not authenticated; after login, redirected to chat
- [ ] **UI-02**: Chat interface has a text input for questions and a scrollable message history panel
- [ ] **UI-03**: LLM response tokens appear progressively as they stream (not shown all at once after completion)
- [ ] **UI-04**: Each assistant message shows expandable citation cards below the answer text, with document title and verbatim excerpt
- [ ] **UI-05**: When no relevant policy is found (INFRA score threshold not met), UI shows a clear "No matching policy found" message
- [ ] **UI-06**: User can log out; session is cleared and they are returned to the login page

---

## v2 Requirements

### Retrieval Quality

- **RETR-01**: Hybrid retrieval (dense + sparse BM25) for improved recall on exact legal terms ("GDPR Article 17", specific clause references)
- **RETR-02**: Cross-encoder reranker on top-10 dense retrieval candidates for improved citation precision
- **RETR-03**: Query expansion with legal synonyms to improve recall for varied terminology

### User Experience

- **UX-01**: Confidence indicator (High / Medium / Low) displayed alongside each answer based on top chunk retrieval score
- **UX-02**: User can click a citation to see it highlighted within the full source passage context
- **UX-03**: Session conversation history persists across logins
- **UX-04**: User can export a conversation transcript with all citations for compliance record-keeping

### Corpus Management

- **CORPUS-01**: Re-ingestion procedure for updated policy documents: delete existing chunks by `source_doc` filter, re-ingest updated version
- **CORPUS-02**: Corpus version metadata displayed in UI footer ("Policies indexed as of [date]")

### Observability

- **OBS-01**: Unanswerable queries are logged with the query text and retrieval scores for corpus gap analysis
- **OBS-02**: Query latency (embed + retrieve + generate) is logged per request for performance monitoring

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| User document upload | Adds ingestion pipeline complexity, storage, and security surface; fixed corpus covers v1 use case |
| Real-time policy monitoring / change alerts | Requires web crawler + change detection pipeline; corpus is static in v1 |
| Fine-tuning or model training | Inference-only via OpenRouter; no training infrastructure |
| Knowledge graph overlay | Major additional infrastructure; Qdrant semantic search sufficient for v1 conflict detection |
| Multi-model consensus (majority voting) | Triples API cost; strong citation prompt outperforms multi-model with weak prompting |
| Voice input | No mobile-first context; text sufficient for compliance analyst use case |
| Admin dashboard / usage analytics | Docker logs + stdout sufficient for v1 monitoring |
| OAuth / social login | Username + password sufficient for internal gated access |
| Multi-tenant / organization-scoped access | Single-role gated access sufficient for v1 |
| Feedback rating loop (thumbs up/down) | Log queries offline post-launch; add in v2 based on demand |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Pending |
| INFRA-05 | Phase 1 | Pending |
| INGEST-01 | Phase 1 | Pending |
| INGEST-02 | Phase 1 | Pending |
| INGEST-03 | Phase 1 | Pending |
| INGEST-04 | Phase 1 | Pending |
| INGEST-05 | Phase 1 | Pending |
| INGEST-06 | Phase 1 | Pending |
| RAG-01 | Phase 2 | Pending |
| RAG-02 | Phase 2 | Pending |
| RAG-03 | Phase 2 | Pending |
| RAG-04 | Phase 2 | Pending |
| RAG-05 | Phase 2 | Pending |
| RAG-06 | Phase 2 | Pending |
| RAG-07 | Phase 2 | Pending |
| CITE-01 | Phase 2 | Pending |
| CITE-02 | Phase 2 | Pending |
| CITE-03 | Phase 2 | Pending |
| CITE-04 | Phase 4 | Pending |
| CONFLICT-01 | Phase 5 | Pending |
| CONFLICT-02 | Phase 5 | Pending |
| CONFLICT-03 | Phase 5 | Pending |
| CONFLICT-04 | Phase 5 | Pending |
| AUTH-01 | Phase 3 | Pending |
| AUTH-02 | Phase 3 | Pending |
| AUTH-03 | Phase 3 | Pending |
| AUTH-04 | Phase 3 | Pending |
| AUTH-05 | Phase 3 | Pending |
| UI-01 | Phase 4 | Pending |
| UI-02 | Phase 4 | Pending |
| UI-03 | Phase 4 | Pending |
| UI-04 | Phase 4 | Pending |
| UI-05 | Phase 4 | Pending |
| UI-06 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 36 total
- Mapped to phases: 36
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-22*
*Last updated: 2026-04-22 after roadmap creation — traceability table populated*

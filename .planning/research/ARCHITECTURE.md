# Architecture Research: Privacy Policy Compliance Assistant

**Domain:** RAG-based compliance chatbot
**Stack:** Python 3.11, FastAPI, Qdrant, OpenRouter (Gemma 4 26B + Nemotron embeddings), React frontend
**Researched:** 2026-04-22

---

## System Components

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Compose                        │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐   ┌────────────┐  │
│  │   Frontend   │    │   Backend    │   │   Qdrant   │  │
│  │  React/Vite  │───▶│   FastAPI    │───▶│  Vector DB │  │
│  │  nginx:80    │    │  uvicorn:8000│   │  :6333     │  │
│  └──────────────┘    └──────┬───────┘   └────────────┘  │
│                             │                            │
└─────────────────────────────│────────────────────────────┘
                              │ HTTPS
                     ┌────────▼────────┐
                     │   OpenRouter    │
                     │  Gemma 4 26B    │
                     │  Nemotron Embed │
                     └─────────────────┘
```

**Five containers/processes:**
1. **Frontend** — React SPA served by nginx; communicates with backend via JWT-authenticated REST + SSE
2. **Backend** — FastAPI (uvicorn); orchestrates RAG pipeline, auth, streaming responses
3. **Qdrant** — vector store; holds indexed policy chunks with metadata
4. **OpenRouter (external)** — embedding API (Nemotron) + LLM API (Gemma 4)
5. **SQLite (embedded)** — user credentials store inside the backend container

---

## Data Flow

### Ingestion Flow (one-time, offline)

```
dataset/json/ ──▶ parse contexts ──▶ chunk text ──▶ batch embed (Nemotron)
                                                          │
                                              ┌───────────▼───────────┐
                                              │  Qdrant collection    │
                                              │  "policies"           │
                                              │  payload: {           │
                                              │    text, title,       │
                                              │    source_doc,        │
                                              │    chunk_index        │
                                              │  }                    │
                                              └───────────────────────┘
```

### Query Flow (per user message)

```
User query
    │
    ▼
Embed query (Nemotron via OpenRouter) ──▶ query vector
    │
    ▼
Qdrant search(top_k=5, score_threshold=0.55)
    │
    ▼
Retrieved chunks (with metadata: title, source_doc, text)
    │
    ▼
Build prompt:
  [system]: "Answer using only the provided passages. Cite each by [ID]. If insufficient, say so."
  [context]: Chunk[1]: ... Chunk[2]: ... Chunk[3]: ...
  [history]: last N turns
  [user]: original query
    │
    ▼
Gemma 4 26B (OpenRouter, stream=True)
    │
    ▼
StreamingResponse (SSE) ──▶ Frontend
    │
    ▼
Citation extraction: parse [1][2] references from response ──▶ attach chunk texts
    │
    ▼
Final response: {answer: "...", citations: [{id, title, text}]}
```

### Cross-Document Conflict Flow

```
User query (implies comparison: "conflict", "differ", "both", etc.)
    │
    ▼
Retrieve top_k=10 across ALL source documents
    │
    ▼
Group by source_doc metadata
    │
    ▼
Conflict-specific prompt:
  "Examine the following passages from different policy documents.
   State whether they are: (a) consistent, (b) contradictory, or (c) one is silent.
   For each conflict found, cite the exact passage from each document by [ID]."
    │
    ▼
LLM response with cross-document citations
```

---

## Chunking Strategy

**Recommendation for policy documents:** Semantic boundary splitting with fixed token budget.

```
Target chunk size: 350–450 tokens
Overlap: 50 tokens (10-15% of chunk)
Separators: ["\n\n", "\n", ". ", " "] (in order of priority)
```

**Why:**
- Privacy policy paragraphs average 80-200 words (≈100-250 tokens). A 400-token target typically captures 2-3 complete clauses — enough semantic context for retrieval, small enough that the LLM can read multiple chunks.
- The 50-token overlap ensures a clause that spans a chunk boundary is represented in both chunks.
- List items and numbered clauses must be kept atomic — never split a `(a) ... (b) ...` enumeration across chunks.

**Metadata required on every chunk:**
```python
{
    "text": str,           # the chunk content
    "title": str,          # document/website title (from dataset "title" field)
    "source_doc": str,     # normalized document identifier
    "chunk_index": int,    # position within source document
    "char_count": int,     # for debugging and filtering
    "token_estimate": int, # estimated tokens (char_count / 4)
}
```

**Dataset-specific note:** The dataset `context` field is already a single policy passage (80-400 words typically). These can be used as chunks directly — no further splitting needed for the majority of records. Only contexts > 450 tokens need splitting.

---

## Retrieval Strategy

**Recommended for v1: Dense retrieval with score threshold + top-k=5**

```python
results = await qdrant.search(
    collection_name="policies",
    query_vector=query_embedding,
    limit=5,
    score_threshold=0.55,  # discard weakly-related chunks
    with_payload=True,
)
```

**For conflict detection queries: increase top-k to 10 and require multi-doc coverage:**
```python
results = await qdrant.search(..., limit=10, score_threshold=0.50)
# then group by source_doc and check at least 2 distinct docs are represented
```

**Hybrid retrieval (v2):** Qdrant supports sparse vector search (BM25-style). For legal terminology queries ("GDPR Article 17", exact policy names), hybrid dense+sparse retrieval significantly improves recall. Architecture supports adding `sparse_vectors_config` to the collection later without data migration — just re-ingest with sparse vectors added.

**Reranking (v2):** A cross-encoder reranker (e.g. `cross-encoder/ms-marco-MiniLM-L-6-v2`) can re-score the top-10 candidates from Qdrant. Adds ~150ms per query but improves precision significantly. Worth adding after v1 proves core functionality.

---

## Qdrant Collection Design

**Single collection: `policies`**

```python
VectorParams(
    size=EMBEDDING_DIM,      # discovered at runtime from first Nemotron call
    distance=Distance.COSINE # Nemotron outputs normalized vectors
)
```

**Why single collection:**
- Cross-document comparison requires searching across all documents simultaneously — separate collections would require parallel queries and manual result merging
- Qdrant supports metadata filtering, so document-scoped queries are still possible: `Filter(must=[FieldCondition(key="source_doc", match=MatchValue(value="..."))])`
- 17K vectors is small; Qdrant handles millions without performance concern at this scale

**Index configuration:**
```python
HnswConfigDiff(
    m=16,           # default; fine for 17K vectors
    ef_construct=100,  # default
)
# No tuning needed at this corpus size
```

---

## Cross-Document Architecture

### Query Intent Detection

Before retrieval, classify the query intent:
- **Single-document Q&A** → top_k=5, any source
- **Multi-document comparison** → top_k=10, assert ≥2 source_docs in results

Detection via keywords in query: `["conflict", "contradict", "mâu thuẫn", "khác nhau", "so sánh", "cả hai", "both", "differ", "disagree"]`

### Conflict Prompt Template

```
SYSTEM:
You are a compliance analyst. You will be given passages from multiple privacy policy documents.
Your task is to:
1. Identify any contradictions between passages from DIFFERENT documents.
2. For each contradiction, cite the exact passage by [ID] from each side.
3. If passages are consistent or one is silent where the other has a requirement, state so.
4. If no contradiction exists, say "No contradiction found" and summarize the common position.
Do NOT infer or add information not present in the passages.

CONTEXT:
[1] {title_A}: {text_A}
[2] {title_B}: {text_B}
...

USER: {query}
```

### Limitation and Mitigation

If both conflicting policies discuss the same topic but use different vocabulary (e.g. "personal data" vs "user information"), vector similarity may not retrieve both — only the one whose wording matches the query. Mitigation: expand query with synonyms (simple query expansion) or use hybrid retrieval (BM25 catches both terms).

---

## Build Order

Based on component dependencies:

```
Phase 1: Infrastructure + Data Ingestion
  - Docker Compose (Qdrant + backend shell + frontend shell)
  - Ingestion script: parse dataset → chunk → embed → upsert Qdrant
  - Verify: query Qdrant and confirm relevant chunks returned
  [NO dependency on frontend or auth]

Phase 2: Core RAG Pipeline
  - FastAPI backend: embed endpoint, Qdrant search, prompt builder, Gemma call
  - Streaming SSE endpoint
  - Citation extraction logic
  [Depends on: Phase 1 (Qdrant populated)]

Phase 3: Authentication
  - User model (SQLite), password hashing, JWT issue/verify
  - FastAPI auth endpoints + middleware
  [Depends on: Phase 2 (endpoint to protect exists)]

Phase 4: Web Frontend
  - React chat UI, login page, citation display panel
  - JWT auth flow in browser
  - SSE stream consumption and progressive rendering
  [Depends on: Phase 2 API spec, Phase 3 auth endpoints]

Phase 5: Cross-Document Conflict Detection
  - Intent classification for comparison queries
  - Multi-doc retrieval strategy
  - Conflict-specific prompt template
  [Depends on: Phase 2 RAG pipeline working correctly for single-doc]

Phase 6: Docker Compose Finalization
  - Production build (nginx frontend, uvicorn backend, named Qdrant volumes)
  - Health checks, restart policies, env injection
  - End-to-end integration test
  [Depends on: All previous phases]
```

**Critical path:** Phase 1 → Phase 2 → Phase 5 (conflict detection depends on good retrieval, not on auth/frontend)

---

## Async vs Sync

**Async throughout.** Every I/O operation in this system is async:
- OpenRouter API calls: `await openrouter.embeddings.create(...)`, `await openrouter.chat.completions.create(..., stream=True)`
- Qdrant: `AsyncQdrantClient` for all searches and upserts
- Database: `sqlalchemy[asyncio]` + `aiosqlite`
- FastAPI handles the event loop; `StreamingResponse` + `async_generator` for SSE

**Exception:** The ingestion script (`ingest.py`) can be synchronous — it's a one-shot offline process, not a web server. Using `asyncio.run()` with async code is fine if desired, but sync is simpler.

---

## Context Window Budget

Gemma 4 26B context window: 128K tokens (large, not a concern for this corpus).

Practical budget per request:
```
System prompt:      ~200 tokens
Retrieved chunks:   ~2,000 tokens (5 chunks × ~400 tokens)
Conversation history: ~500 tokens (last 3 turns)
User query:         ~50 tokens
─────────────────────────────
Total input:        ~2,750 tokens
LLM response:       ~300-800 tokens
```

Total well within Gemma 4's context window. No truncation logic needed for v1.

---

## Sources

- [Qdrant Architecture — Official Docs](https://qdrant.tech/documentation/overview/)
- [Qdrant Filtering — Payload Conditions](https://qdrant.tech/documentation/concepts/filtering/)
- [Qdrant Hybrid Search — Sparse Vectors](https://qdrant.tech/documentation/concepts/hybrid-queries/)
- [RAG Architecture Patterns — Towards AI](https://towardsai.net/p/rag-architecture)
- [FastAPI StreamingResponse + SSE](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)
- [Cross-Document RAG for Legal — ACM 2025](https://dl.acm.org/doi/10.1145/3731715.3733451)
- [Chunking for Legal Docs — Milvus Guide](https://milvus.io/ai-quick-reference/what-are-best-practices-for-chunking-lengthy-legal-documents-for-vectorization)
- [RAG Build Order Best Practices — AWS](https://aws.amazon.com/blogs/machine-learning/build-a-rag-based-question-answering-solution-with-fine-tuned-llms/)

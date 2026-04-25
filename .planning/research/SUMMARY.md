# Project Research Summary

**Project:** Privacy Policy Compliance Assistant
**Domain:** RAG-based compliance chatbot — legal document Q&A with inline citations and cross-document conflict detection
**Researched:** 2026-04-22
**Confidence:** HIGH

---

## Executive Summary

A narrow linear RAG pipeline (embed → retrieve → generate) over a fixed 17K privacy policy corpus. Raw Python implementation with no framework overhead. The stack is fully resolved and high-confidence. The dominant risk is citation hallucination (17–33% in legal RAG without enforcement), mitigated by a "cite or abstain" system prompt and programmatic citation ID verification. Cross-document conflict detection is the key differentiator and highest-complexity feature — it must be built after single-document retrieval is validated.

---

## Recommended Stack

| Component | Choice | Why |
|-----------|--------|-----|
| LLM + Embedding API | `openai` SDK 2.32.0 via OpenRouter | Single SDK covers both; `base_url` override makes it drop-in |
| RAG orchestration | Raw Python (no framework) | Linear 3-step pipeline; LangChain adds 30–40% boilerplate with zero benefit |
| Vector store | Qdrant + `qdrant-client` 1.17.1 | Async-native, Docker Compose official image, single collection supports cross-doc queries |
| Backend | FastAPI 0.136.0 + uvicorn | Async-first, StreamingResponse for SSE, Python 3.11 compatible |
| Frontend | React 18 + Vite + Tailwind + shadcn/ui | Full auth control, citation panel flexibility, Docker-deployable via nginx |
| Auth | PyJWT + pwdlib[argon2] | Current FastAPI-endorsed replacements for deprecated python-jose / passlib |
| Config | pydantic-settings 2.x | Type-safe `.env` loading; official FastAPI recommendation |
| User DB | SQLite (dev) via SQLAlchemy asyncio | Relational store for credentials; Qdrant is not a relational DB |
| LLM model | `google/gemma-4-26b-a4b` via OpenRouter | 128K context window; multilingual; pay-as-you-go |
| Embedding model | `nvidia/llama-nemotron-embed-vl-1b-v2` via OpenRouter | Free tier available; 131K token context; **dimension must be probed at runtime** |

---

## Table Stakes Features

- **Grounded answers only** — retrieve first, generate second; never answer from model training knowledge
- **Inline citations** — document title + verbatim excerpt for every claim; document-level-only attribution is insufficient
- **"Cite or abstain"** — if context does not support the answer, say so; single highest-trust behavior for compliance users
- **Passage-level metadata** — every chunk must carry `title`, `source_doc`, `chunk_index` at index time
- **Conversation history within session** — last N turns passed as context prefix for follow-up questions
- **Auth gating** — JWT-protected endpoints; sensitive compliance content must not be open
- **Cross-document conflict detection** — explicit v1 requirement; dual-retrieval + LLM comparison prompt

---

## Architecture in One Paragraph

A user query arrives at the React SPA, is sent with a JWT Authorization header to the FastAPI backend, which embeds the query via Nemotron on OpenRouter, searches the Qdrant `policies` collection (top-k=5, score_threshold=0.55), builds a prompt with retrieved chunks labeled [1]..[N] plus conversation history, streams the Gemma 4 26B response via SSE, post-processes to extract cited chunk IDs, and returns `{answer, citations: [{id, title, text}]}` to the frontend for rendering with an expandable citation panel. For conflict-detection queries (detected by keywords such as "conflict", "mâu thuẫn", "so sánh"), top-k is increased to 10 and a structured comparison prompt is used. User credentials live in SQLite via async SQLAlchemy; Qdrant runs as a named-volume Docker container alongside the backend and nginx-served frontend.

---

## Build Order

1. **Infrastructure + Data Ingestion** — Docker Compose stack, ingestion script (parse dataset → chunk → embed → upsert Qdrant with metadata), retrieval sanity checks passing
2. **Core RAG Pipeline** — working `/chat` SSE endpoint with citation enforcement, validated via curl before UI work begins
3. **Authentication** — JWT + Argon2 auth wrapping the working API; isolates auth bugs from RAG bugs
4. **Web Frontend** — React SPA with login, chat UI, SSE stream rendering, expandable citation panel
5. **Cross-Document Conflict Detection** — intent classifier, top-k=10 multi-doc retrieval, conflict-specific prompt template
6. **Docker Compose Finalization** — production hardening, health checks, restart policies, end-to-end integration test

**Critical path:** Phase 1 → Phase 2 → Phase 5 (conflict detection depends on validated single-doc retrieval)

---

## Top 5 Watch-Outs

1. **Wrong Qdrant distance metric (C1)** — immutable after collection creation; re-ingesting 17K passages is the only fix. Verify Nemotron outputs normalized vectors; run sanity check post-ingestion (embed a known passage, assert it ranks #1).

2. **Qdrant data loss on Windows/WSL2 bind mounts (C2)** — this project runs on Windows (`D:\data\code\...`); **named Docker volumes are mandatory**. Qdrant v1.15.0+ refuses to start on POSIX-incompatible filesystem mounts.

3. **Citation fabrication (C4)** — legal RAG tools hallucinate 17–33% of the time without explicit enforcement. Use numbered chunk IDs in prompt + "cite only provided IDs" instruction + programmatic post-generation verification that every cited ID exists in the retrieved set.

4. **Chunking destroys legal clause coherence (C3)** — target 400 tokens with 50-token overlap; use semantic separators; never split numbered list items mid-item; spot-check 20 random chunks before bulk ingestion.

5. **OpenRouter embedding truncation without warning (C6)** — API returns HTTP 200 with no error when input exceeds token limit. Validate token count for every chunk before the embedding call; keep chunks under 450 tokens to stay safely within Nemotron's context.

---

## Key Decisions Made by Research

| Decision | Status |
|----------|--------|
| No LangChain / LlamaIndex — raw Python pipeline | Settled |
| Qdrant single collection `policies` with COSINE distance | Settled |
| OpenAI SDK with `base_url` override for OpenRouter | Settled |
| PyJWT + pwdlib[argon2] (not python-jose / passlib) | Settled |
| React + Vite (not Streamlit / Gradio / Chainlit) | Settled |
| Named Docker volumes (not bind mounts) for Qdrant on Windows | Settled |
| Ingestion as offline script, not on-startup | Settled |

---

## Open Questions (resolve during implementation)

- **Nemotron embedding dimension** — not published; probe at runtime: `len(resp.data[0].embedding)`
- **Score threshold** — 0.55 cosine is a starting estimate; calibrate from actual score distributions post-ingestion
- **Conflict detection false-positive rate** — spike test with ~20 known cross-document questions before committing to full Phase 5 implementation
- **OpenRouter billing** — Gemma 4 26B and Nemotron are pay-as-you-go; ensure billing is configured before bulk ingestion of 17K passages

---

*Research completed: 2026-04-22 | Ready for roadmap: yes*

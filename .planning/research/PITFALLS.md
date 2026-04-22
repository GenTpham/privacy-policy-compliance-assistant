# Pitfalls Research

**Project:** Privacy Policy Compliance Assistant (RAG chatbot)
**Researched:** 2026-04-21
**Stack:** Python 3.11, Qdrant, OpenRouter (Gemma 4 26B + Nemotron embeddings), FastAPI, Docker Compose

---

## Critical Pitfalls

These failures cause silent wrong answers, data loss, or complete system breakage. Address before or during the phase listed.

---

### C1 — Wrong Distance Metric for Embedding Model

**What goes wrong:** Qdrant collection is created with `Cosine` but the embedding model outputs un-normalized vectors (or vice versa). Retrieval rankings become meaningless — similar passages score low, unrelated passages score high — without any error message.

**Why it happens:** Developers copy a Qdrant quickstart using `Cosine`, but Nemotron or another model may expect `Dot` (inner product on L2-normalized vectors). The mistake is invisible until you manually inspect retrieval scores.

**Consequences:** Every query returns wrong context. The LLM produces plausible-sounding but incorrect answers. Extremely hard to diagnose because the pipeline "works" end-to-end.

**Prevention:**
1. Check Nemotron's model card on Hugging Face or the OpenRouter model page before collection creation. If it outputs L2-normalized embeddings, either `Cosine` or `Dot` produces equivalent ranking — but pick one and document it.
2. After ingestion, run a sanity check: embed a known passage, query for it, assert it ranks #1.
3. The collection distance metric is **immutable after creation**. If you get it wrong, you must delete and recreate the collection and re-ingest all 17K passages.

**Warning signs:** Top-k retrieval returns passages with no topical relation to the query. Score distributions are flat (all scores near 0.5 or all near 1.0).

**Phase:** Corpus ingestion / vector store setup (Phase 1 or 2).

---

### C2 — Qdrant Data Loss on Windows/WSL2 Bind Mounts

**What goes wrong:** `docker-compose.yml` uses a bind mount like `./qdrant_data:/qdrant/storage`. On Windows with WSL2, this path crosses the Windows hypervisor into a non-POSIX filesystem. Qdrant's WAL (Write-Ahead Log) may silently corrupt or lose data. From Qdrant v1.15.0 onward, Qdrant performs a runtime filesystem compatibility check and will refuse to start if the check fails.

**Why it happens:** Default examples in blog posts use bind mounts. On Linux hosts they work fine. On Windows dev machines running Docker Desktop + WSL2, the volume mount goes through the Windows NTFS/hypervisor layer.

**Consequences:** Indexed data is lost on container restart. Or Qdrant refuses to start, blocking all development.

**Prevention:**
- Use a **named Docker volume** instead of a bind mount:
  ```yaml
  volumes:
    qdrant_storage:

  services:
    qdrant:
      image: qdrant/qdrant
      volumes:
        - qdrant_storage:/qdrant/storage
  ```
- If a bind mount is needed for local inspection, place the host path inside WSL2's Linux filesystem (`~/qdrant_data`), not a Windows path (`D:/data/...`).

**Warning signs:** `docker compose up` logs show filesystem compatibility errors. Data present before `docker compose down` is missing after `docker compose up`.

**Phase:** Docker Compose setup (Phase 1). Do not leave for later.

---

### C3 — Chunking Destroys Legal Clause Coherence

**What goes wrong:** Fixed-size character splitting (e.g. naive 500-char chunks with 50-char overlap) cuts across sentence boundaries mid-clause. A "data retention" clause spanning three sentences is split into fragments — none of which contain the complete obligation. Vector search retrieves fragments that individually are semantically weak, causing the LLM to miss or misstate the rule.

**Why it happens:** Fixed-size chunking is the simplest approach and the default in many tutorials. Legal/policy text does not align to uniform lengths.

**Consequences:** For a 17K-passage corpus of privacy policies, fragmented clauses are the dominant retrieval failure mode. Cross-document conflict detection becomes nearly impossible because the conflicting terms exist in separate incomplete fragments.

**Prevention:**
- Use `RecursiveCharacterTextSplitter` with semantic separators: `["\n\n", "\n", ". ", " "]` targeting 400–512 tokens with 10–15% overlap.
- Treat numbered/lettered list items and table rows as **atomic units** — never split them mid-item.
- Attach metadata to every chunk: `{source_doc, section_title, policy_name, chunk_index}`. This is mandatory for cross-document conflict detection.
- After chunking, spot-check 20 random chunks. Every chunk should be a complete, readable sentence or clause.

**Warning signs:** Retrieved chunks start or end mid-sentence. Section headers appear in chunks without the clause body.

**Phase:** Data ingestion / chunking pipeline (Phase 1).

---

### C4 — Citation Fabrication (Model Invents Policy References)

**What goes wrong:** The LLM cites a policy name, section number, or clause that does not exist in the retrieved context. It sounds authoritative. Legal/compliance users treat it as fact. In a privacy policy assistant, fabricated citations can lead to incorrect compliance decisions.

**Why it happens:** LLMs blend prior training knowledge with retrieved context. When retrieved passages are ambiguous or incomplete, the model fills in gaps with plausible-sounding but invented details. Stanford research found that legal RAG tools hallucinate 17–33% of the time even with retrieval.

**Consequences:** Compliance errors. Loss of user trust. Potential legal exposure if the assistant is used for actual compliance decisions.

**Prevention:**
1. At prompt level: assign integer IDs to retrieved chunks (`[1]`, `[2]`, ...) and instruct the model: "You MUST only cite sources using the numeric IDs provided. Do not cite any source not in the context."
2. At generation level: after response generation, programmatically verify that every cited ID exists in the retrieved set.
3. Add an explicit system prompt instruction: "If the context does not contain enough information to answer, respond: 'I could not find this in the provided policies.'"
4. Do not expose section numbers or policy version strings to the model unless they come from the retrieved chunks.

**Warning signs:** Responses cite "Section 4.2" when no such heading was retrieved. Model references policy names not in the current query's retrieved context.

**Phase:** LLM integration / response generation (Phase 2–3). Verification logic in Phase 3.

---

### C5 — Cross-Document Conflict Detection: False Positives from Semantic Similarity

**What goes wrong:** Two policy passages score high cosine similarity because they discuss the same topic (e.g. "cookies") but actually say the same thing. The system flags them as conflicting. Alternatively, genuinely conflicting passages about data retention durations ("30 days" vs "1 year") have different vocabulary, score low similarity, and are never compared — a false negative.

**Why it happens:** Vector similarity measures topical relatedness, not logical contradiction. "We retain data for 30 days" and "We retain data for 1 year" may have moderate similarity (~0.75) and get retrieved together, but a naive conflict detector that just compares similarity scores will miss the contradiction in favor of higher-scoring but non-conflicting passages.

**Consequences:** Conflict detection produces noisy results (false positives) or misses real conflicts (false negatives), making the feature unreliable for compliance use.

**Prevention:**
- Separate "candidate retrieval" from "conflict judgment": use vector search to retrieve topically related passages across documents, then use the LLM as a contradiction classifier on the retrieved pair.
- Structured prompt: "Given Passage A from Policy X and Passage B from Policy Y, are these two passages contradictory, consistent, or unrelated? Explain."
- Filter candidate pairs by requiring a minimum similarity threshold AND different source documents.
- For date/duration/numeric conflicts: apply regex extraction post-retrieval to surface quantitative contradictions that semantic search misses.

**Warning signs:** Conflict detection flags identical or paraphrased passages as conflicts. System never flags clearly different retention periods across policies.

**Phase:** Cross-document conflict feature (Phase 3 or dedicated phase). Flag for deeper research.

---

### C6 — OpenRouter Embedding API: Truncation Without Warning

**What goes wrong:** OpenRouter's embeddings API truncates inputs that exceed the model's maximum token length. Nemotron's context window may be shorter than a long policy chunk. The API returns an embedding for the truncated text with no error, no warning, and a 200 response. The resulting vector represents only part of the chunk.

**Why it happens:** OpenRouter normalizes behavior across providers; truncation is the provider's default fallback, not a documented exception condition.

**Consequences:** Long chunks get embeddings that don't represent their full content. Retrieval quality degrades silently. Chunks at the end of a long policy section are systematically under-represented.

**Prevention:**
- Count tokens before embedding. For Nemotron, check the model card for max input tokens (typically 512–8192 depending on variant).
- During ingestion, assert `len(tokens) <= max_input_tokens` for every chunk. Log and flag any violation.
- Set your chunking target size to stay comfortably under the model limit (e.g. if limit is 512 tokens, target 400 tokens per chunk).

**Warning signs:** Embeddings for long chunks have lower intra-document coherence than short chunks. No API errors despite chunks being longer than the model limit.

**Phase:** Ingestion pipeline, before first bulk embedding run (Phase 1–2).

---

## Common Mistakes

These are real problems but less catastrophic — they degrade quality rather than break the system.

---

### M1 — Retrieval Returns Too Much or Too Little (Wrong K)

**What goes wrong:** Retrieving top-3 chunks misses relevant clauses. Retrieving top-20 overwhelms the LLM context window and causes the model to ignore later chunks ("lost in the middle" effect). Both configurations look fine during development with simple test queries.

**Prevention:** Start with top-5. For conflict detection queries, use top-10. Add a relevance score threshold (e.g. discard chunks below 0.6 cosine similarity) to avoid padding context with weakly-related passages. Qdrant supports score thresholds natively via `score_threshold` in the search request.

**Phase:** Query pipeline tuning (Phase 2–3).

---

### M2 — No Fallback for Unanswerable Queries

**What goes wrong:** A user asks about a policy that was not indexed, or asks a question that genuinely cannot be answered from the corpus. The LLM retrieves the closest passages anyway (RAG always returns top-k regardless of relevance) and generates a confident but fabricated answer.

**Prevention:** Implement a minimum score gate: if the top retrieved chunk scores below a threshold (e.g. 0.55), respond with "I could not find a relevant policy for this question." Log these cases — they indicate corpus gaps.

**Phase:** Response validation layer (Phase 3).

---

### M3 — FastAPI JWT Secret Hardcoded or Weak

**What goes wrong:** JWT secret is `"secret"`, `"changeme"`, or copied from a tutorial. Any attacker who knows the secret (or tries common values) can forge tokens and bypass authentication.

**Prevention:**
- Generate secret with `openssl rand -hex 32`. Store in `.env`, never in source code.
- Use `python-jose` or `PyJWT` with `HS256` as minimum. Prefer `RS256` for production.
- Set access token expiry to 15–60 minutes. Do not use non-expiring tokens.
- Add `python-dotenv` to load secrets; validate at startup that the secret is present and meets minimum length (32+ characters).

**Warning signs:** Secret is defined as a Python string literal in `auth.py`. Token expiry not set (defaults to never).

**Phase:** Auth implementation (Phase 2).

---

### M4 — Docker Compose Service Startup Order (FastAPI Starts Before Qdrant Is Ready)

**What goes wrong:** `depends_on: qdrant` only waits for the container to start, not for Qdrant to finish initializing its collections. FastAPI attempts a connection on startup, gets a `ConnectionRefusedError`, and crashes. Docker does not automatically restart it.

**Prevention:**
- Add `restart: on-failure` or `restart: unless-stopped` to the FastAPI service in `docker-compose.yml`.
- Implement a Qdrant readiness check in FastAPI startup: retry connection with exponential backoff (3 attempts, 2s delay) before marking the service as healthy.
- Use `healthcheck` in the Qdrant service definition and `condition: service_healthy` in `depends_on`.

**Phase:** Docker Compose configuration (Phase 1).

---

### M5 — Container-to-Container Communication Using Localhost

**What goes wrong:** FastAPI's Qdrant client is configured with `host="localhost"`. Inside Docker Compose, `localhost` refers to the container itself, not to the Qdrant service. The connection fails with `Connection refused`.

**Prevention:** Use the **service name** as the hostname: `host="qdrant"` (matching the service name in `docker-compose.yml`). For OpenRouter API calls, use the public URL — external API calls work from containers by default.

**Warning signs:** Qdrant connection works locally (`docker run`) but fails in Compose. Error message says `Connection refused` on port 6333.

**Phase:** Docker Compose networking (Phase 1).

---

### M6 — Python venv Inside Docker (Redundant Interpreter)

**What goes wrong:** Developers use `python -m venv .venv` and install into `.venv` inside the Docker build context, then reference `./venv/bin/python`. This doubles the Python interpreter size inside the image and creates path confusion. More critically, if `.venv` is present on the host and gets COPY'd into the image, it may contain platform-incompatible binaries (Windows `.pyd` files inside a Linux container).

**Prevention:**
- Do not create or use a `.venv` inside Docker. Docker provides isolation natively.
- Add `.venv/` to `.dockerignore`.
- Install dependencies directly into the system Python in the Dockerfile: `pip install -r requirements.txt`.
- For multi-stage builds, install into a known prefix in stage 1, copy to stage 2.

**Warning signs:** Dockerfile contains `python -m venv`. Build fails with `cannot execute binary file: Exec format error` for a dependency.

**Phase:** Dockerfile authoring (Phase 1).

---

### M7 — OpenRouter Rate Limits in Bulk Ingestion

**What goes wrong:** During the one-time ingestion of 17K passages, the embedding API is called in a tight loop. OpenRouter free-tier models are limited to 20 requests/minute and 200 requests/day. At 17K passages, even with batching, you hit daily limits. Paid-tier limits are higher but still finite.

**Prevention:**
- Batch embedding requests: send up to 100 passages per API call if the model supports batch input (check OpenRouter's embeddings docs — `input` can be an array).
- Add rate limiting in the ingestion script: `time.sleep(3)` between batches, or use a token-bucket approach.
- Run ingestion as a one-time offline script, not inside the web service on startup.
- Cache embeddings to disk (pickle or numpy) before inserting into Qdrant so a failed ingestion can resume.

**Warning signs:** `429 Too Many Requests` during ingestion. Ingestion script exits halfway through the corpus.

**Phase:** Ingestion script (Phase 1).

---

### M8 — Single Retrieval Method (Vectors Only, No Keyword Fallback)

**What goes wrong:** Exact legal terms like "GDPR Article 17", "legitimate interest", or specific company names do not embed well. Semantic search may miss them entirely. A user asks about a specific clause reference and gets unrelated results.

**Prevention:** Qdrant supports sparse vectors and hybrid search (dense + sparse/BM25). Implement hybrid retrieval using Qdrant's built-in sparse vector support or a secondary BM25 index for keyword matching. Even a simple fallback — "if top score < 0.6, try keyword search" — significantly improves coverage for legal terminology.

**Phase:** Query pipeline (Phase 2–3). Can defer to Phase 3 if hybrid search adds complexity.

---

### M9 — RAG Latency: Everything in the Critical Path

**What goes wrong:** Each query triggers: (1) embed query via OpenRouter (~200ms), (2) Qdrant vector search (~50ms), (3) LLM completion via OpenRouter (~2–8s for Gemma 4 26B). Total: 3–10s per query. Acceptable in testing but feels broken to users.

**Prevention:**
- Cache query embeddings: identical query strings should reuse the cached vector (Redis or in-memory LRU cache).
- Use Qdrant's HNSW index (default) and keep `ef` at default or slightly higher for the 17K corpus — this is already fast enough without tuning at this scale.
- Stream LLM responses: FastAPI supports `StreamingResponse`; OpenRouter supports `stream=True`. Send chunks to the frontend as they arrive. Perceived latency drops to ~500ms for first token.
- Add a response-level cache for identical or near-identical questions (especially common policy FAQ queries).

**Phase:** Performance optimization (Phase 3 or dedicated optimization phase).

---

### M10 — Outdated Chunks After Policy Updates

**What goes wrong:** A privacy policy is updated (common — GDPR enforcement pressures mean policies change frequently). The old chunks remain in Qdrant. Conflict detection starts flagging "conflicts" between old and new versions of the same policy. Answers reflect outdated rules.

**Prevention:**
- Tag every chunk with `{policy_name, policy_version, ingested_at}` metadata.
- Implement a re-ingestion procedure: delete all chunks by `policy_name` filter, then re-ingest the updated document.
- Qdrant supports `delete_by_payload` for bulk deletion by metadata filter — use this instead of collection recreation.

**Phase:** Corpus management / update procedures (Phase 2).

---

## Phase Mapping

| Phase | Pitfalls to Address |
|-------|---------------------|
| Phase 1 — Infrastructure & Data Ingestion | C2 (Qdrant volumes), C3 (chunking), C6 (token truncation), M4 (startup order), M5 (container networking), M6 (venv in Docker), M7 (rate limits in ingestion) |
| Phase 2 — Core RAG Pipeline & Auth | C1 (distance metric), C4 (citation fabrication — basic prompt guardrails), M1 (K tuning), M3 (JWT secret), M10 (chunk metadata for updates) |
| Phase 3 — Conflict Detection & Quality | C4 (citation verification logic), C5 (cross-document conflict), M2 (unanswerable query fallback), M8 (hybrid retrieval), M9 (streaming + caching) |
| Any Phase — Code Review Checkpoint | M3 (JWT never hardcoded), M5 (no localhost in service config), M6 (no venv in Dockerfile) |

---

## Qdrant-Specific Reference

- Named volumes over bind mounts on Windows/WSL2: **critical** (C2)
- Distance metric is immutable after collection creation: **critical** (C1)
- Qdrant v1.15.0+ performs POSIX filesystem check at startup — use Docker named volumes
- `depends_on` does not wait for readiness — use healthcheck + restart policy (M4)
- Qdrant supports native sparse vector hybrid search: useful for legal terminology retrieval (M8)
- `score_threshold` parameter in search requests: use to gate low-confidence retrievals (M1, M2)

## OpenRouter-Specific Reference

- Embeddings API: `input` accepts array (batch) — use batching to reduce request count (M7)
- No error on truncated input — validate token length before calling API (C6)
- Free tier: 20 req/min, 200 req/day. Paid tier ($10+ credits): higher limits but still finite (M7)
- ~25–40ms overhead per request vs direct provider — acceptable, budget for it in latency calculations (M9)
- Model availability: Gemma 4 26B and Nemotron are pay-as-you-go, not free tier — ensure billing is configured before production ingestion

---

## Sources

- [23 RAG Pitfalls and How to Fix Them](https://www.nb-data.com/p/23-rag-pitfalls-and-how-to-fix-them)
- [Why Your RAG Pipeline Hallucinates — 7 Root Causes](https://medium.com/@umesh382.kushwaha/why-your-rag-pipeline-hallucinates-7-root-causes-and-how-to-fix-them-1a04a84be7f5)
- [Legal RAG Hallucinations — Stanford empirical study](https://dho.stanford.edu/wp-content/uploads/Legal_RAG_Hallucinations.pdf)
- [OpenRouter Embeddings API Reference](https://openrouter.ai/docs/api/reference/embeddings)
- [OpenRouter Rate Limits](https://openrouter.ai/docs/api/reference/limits)
- [Qdrant Docker Hub — Volume and persistence notes](https://hub.docker.com/r/qdrant/qdrant)
- [Qdrant Troubleshooting — Filesystem compatibility](https://qdrant.tech/documentation/operations/common-errors/)
- [Qdrant Distance Metrics](https://qdrant.tech/course/essentials/day-1/distance-metrics/)
- [Chunking for Legal Documents — Milvus](https://milvus.io/ai-quick-reference/what-are-best-practices-for-chunking-lengthy-legal-documents-for-vectorization)
- [RAG Chunking Strategies — Unstructured](https://unstructured.io/blog/chunking-for-rag-best-practices)
- [Contradiction Detection in RAG — arXiv 2504.00180](https://arxiv.org/html/2504.00180v1)
- [DRAGGED Into a Conflict — Google Research](https://research.google/pubs/dragged-into-a-conflict-detecting-and-addressing-conflicting-sources-in-retrieval-augmented-llms/)
- [Reducing False Positives in RAG Semantic Caching — InfoQ](https://www.infoq.com/articles/reducing-false-positives-retrieval-augmented-generation/)
- [FastAPI JWT Security Guide](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [FastAPI OWASP Top 10 Security](https://oneuptime.com/blog/post/2025-01-06-fastapi-owasp-security/view)
- [Docker Compose Networking — How to Debug](https://oneuptime.com/blog/post/2026-01-25-debug-docker-compose-network-issues/view)
- [Docker Networking Best Practices — Reintech](https://reintech.io/blog/docker-compose-networking-best-practices)
- [Python venv in Docker: A Misapplied Best Practice](https://wbarillon.medium.com/python-venv-in-docker-a-misapplied-best-practice-a1bd7465106e)
- [RAG Latency Optimization](https://apxml.com/courses/optimizing-rag-for-production/chapter-4-end-to-end-rag-performance/rag-latency-analysis-reduction)
- [WSL2 Docker Volume Mount Issues — docker/for-win #10476](https://github.com/docker/for-win/issues/10476)

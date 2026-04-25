# Features Research

**Domain:** RAG-based compliance / legal document chatbot (privacy policies)
**Researched:** 2026-04-21
**Confidence:** MEDIUM-HIGH (verified across multiple production sources and research papers)

---

## Table Stakes

Features that users of a compliance chatbot treat as non-negotiable. Absence causes immediate trust loss or abandonment.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Grounded answers only | Users cite these answers to legal/compliance teams — hallucination is a career risk | Low-Med | Achieved via retrieval-then-generate with strict "cite or abstain" prompt |
| Inline source citations | Every legal conclusion must be traceable; users need to verify before acting | Medium | Minimum: [Document Title, passage excerpt]. Ideal: exact paragraph reference |
| "I don't know" / abstain | Compliance professionals trust a system MORE when it declines to answer rather than guesses | Low | Prompt must explicitly instruct: if claim cannot be grounded in retrieved chunks, say so |
| Passage-level attribution | Document-level ("answer from Policy A") is insufficient; users want the exact clause | Medium | Chunk metadata must carry document title + section/paragraph ID at index time |
| Readable answer prose | Raw chunk dumps are not acceptable; LLM must synthesize a coherent answer | Low | Already solved by RAG generation step |
| Conversation history (session) | Follow-up questions like "what about for employees?" require previous turn context | Low | Store last N turns in session; pass as context prefix to LLM |
| Basic query input + response UI | Users need a chat box and a response panel — not a raw API | Low | Confirmed in scope via PROJECT.md |
| Auth / access gating | Compliance content is sensitive; open access violates organizational policy | Low | Confirmed in scope via PROJECT.md |

**Critical insight from research:** Even legal-domain RAG systems hallucinate on 17%+ of benchmark queries. The "cite or abstain" pattern (force the model to ground every claim or explicitly refuse) is the single highest-value table-stakes behavior for compliance use cases. Source: [RAG for Law — Progress](https://www.progress.com/agentic-rag/use-cases/rag-for-law), [Citation-Enforced RAG paper](https://arxiv.org/html/2603.14170v1).

---

## Differentiators

Features that distinguish a serious compliance tool from a generic chatbot demo. Not expected, but valued when present.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Cross-document conflict detection | Surfaces contradictions between policies without the user having to read both | High | The explicit v1 requirement; see Cross-Document Comparison section below |
| Confidence / uncertainty signal | Explicit "high confidence" vs "partial match — review source" labels build calibrated trust | Medium | Retrieval similarity score can proxy confidence; display to user when score is low |
| Citation deep-link / highlight | Clicking a citation scrolls to the exact passage in a side-panel rather than showing a title only | High | Tensorlake research: "precise citations separate professional apps from demos" |
| Query-specific context window | Show the user which chunks were retrieved and why — transparency into the retrieval step | Medium | Useful for power users / auditors; optional toggle |
| Session audit log | Immutable per-session log of queries + answers + sources used, exportable for compliance audit | Medium | Differentiating in enterprise compliance contexts; simple append-only log |
| Low-similarity fallback message | When top-k similarity is below threshold, warn "No closely matching policy found" instead of returning weak matches | Low | Easy to implement; high trust impact |
| Cross-language query handling | Users asking in Vietnamese receive answers synthesized from English-policy corpus with Vietnamese response prose | Medium | Gemma 4 supports multilingual; prompt must instruct language match to query language |

---

## Cross-Document Comparison

How production systems and research handle contradiction/conflict detection between policy documents.

### What "conflict" means in practice

For privacy policies, three contradiction archetypes matter:

1. **Direct contradiction** — Policy A says "data retained 30 days", Policy B says "data retained 90 days" for the same data category
2. **Scope conflict** — Policy A applies a rule to "all users", Policy B exempts "enterprise accounts" — creating ambiguous coverage
3. **Omission conflict** — Policy A mandates a right (e.g. data deletion), Policy B is silent — user doesn't know which governs them

### How production systems handle this

**Approach 1: Dual-retrieval + LLM comparison (recommended for v1)**

Retrieve the top-k chunks relevant to the query from across all documents. Pass all chunks to the LLM with a prompt like: "Given these passages from multiple documents, identify any contradictions or gaps. For each conflict, cite the exact passage from each document." This is the simplest approach and works well when the retrieval surfaces passages from different documents naturally.

**Approach 2: Multi-agent pipeline (research state, not v1)**

LegalWiz (arxiv 2510.03418) uses a multi-agent framework where one agent retrieves and another validates for contradictions with human-in-the-loop. It defines six contradiction types injected synthetically for benchmark purposes. This is research-grade complexity, not production-ready for a v1.

**Approach 3: Knowledge graph + RAG hybrid**

Some production systems (AgentiveAIQ) layer a knowledge graph over RAG to capture concept relationships (e.g. "data retention" concept linked across all documents). This enables conflict detection at the concept level rather than passage level. High complexity, not recommended for v1.

### Recommended v1 implementation

Use dual-retrieval with document-scoped metadata filtering. When the user's query implies comparison ("which policy says X" / "do these conflict"), retrieve top-k across all document scopes, then explicitly prompt the LLM: "Examine the following passages from different documents. State whether they are consistent, contradictory, or one is silent where the other has requirements. Cite each document by name." This is achievable with the existing Qdrant + OpenRouter setup.

The key engineering constraint: **chunks must carry document identity in metadata at index time** (document title, source file). Without this, the LLM cannot attribute which claim came from which policy.

**Sources:**
- [LegalWiz paper](https://arxiv.org/abs/2510.03418)
- [Multi-Round RAG for Legal Documents (ACM 2025)](https://dl.acm.org/doi/10.1145/3731715.3733451) — 78.67% recall vs 57.33% baseline
- [Contradiction Detection in RAG Systems](https://arxiv.org/html/2504.00180v1)

---

## Citation Patterns

What source attribution formats work in practice and which build the most user trust.

### Format options ranked by trust impact

**1. Inline anchor + expandable source panel (best for compliance)**

Answer prose contains lightweight markers like [1] or [Policy A]. A side panel or accordion shows the full verbatim excerpt for each citation. Users can verify without leaving the chat. This is the pattern used by Anthropic's Citations API and recommended by Tensorlake's fine-grained citation research.

Example output structure:
```
Answer: Customer data retention is limited to 90 days per policy guidelines [1], 
        however the enterprise addendum specifies 180 days for contracted accounts [2].

[1] Google Privacy Policy — Data Retention section:
    "We retain personal data for no longer than 90 days following account deletion..."

[2] Enterprise Data Processing Addendum:
    "Retention periods for enterprise accounts may extend to 180 days..."
```

**2. Source list appended to answer (acceptable for v1)**

Answer is delivered cleanly, then a "Sources:" section lists the document titles and relevant excerpts. Simpler to implement. Less immediate than inline markers but still provides traceability.

**3. Document-level reference only (insufficient for compliance)**

"Answer based on: Google Privacy Policy." This is inadequate — users cannot locate the specific clause. Do not use this pattern.

### Minimum viable citation for v1

At minimum, every answer must include:
- Document title (from chunk metadata `title` field in the dataset)
- A verbatim excerpt of the retrieved passage(s) that support the answer

Ideal but not required for v1: paragraph/section identifier, page number, deep-link to source.

### LLM prompting for citations

The system prompt must instruct the model to: (a) use only information from the provided chunks, (b) cite specific chunks by their ID or title, and (c) include a verbatim quote. Without explicit prompt instruction, LLMs synthesize and lose traceability. The Tensorlake approach of embedding hidden anchor IDs in chunks (stripped before display) that the LLM returns as citation references works well for structured citation extraction.

**Sources:**
- [Citation-Aware RAG — Tensorlake](https://www.tensorlake.ai/blog/rag-citations)
- [RAG Citations and Sources — Ailog](https://app.ailog.fr/en/blog/guides/citation-sourcing-rag)
- [Anthropic-Style Citations with Any LLM](https://medium.com/data-science-collective/anthropic-style-citations-with-any-llm-2c061671ddd5)
- [LlamaIndex Citation Query Engine](https://developers.llamaindex.ai/python/examples/workflow/citation_query_engine/)

---

## Anti-Features

Things that sound valuable for v1 but consume significant effort without proportionate benefit. Explicitly defer these.

| Anti-Feature | Why It Sounds Good | Why to Avoid in v1 | What to Do Instead |
|--------------|-------------------|--------------------|--------------------|
| Real-time document monitoring | "Stay current with policy changes" | Corpus is static dataset; no live feed exists; would require web crawler + change detection pipeline | Mark corpus version in metadata; note "indexed as of [date]" in UI footer |
| User document upload | "Let users bring their own policies" | Adds ingestion pipeline complexity, storage, security surface, chunking edge cases | Fixed corpus covers the 17K dataset; evaluate need after v1 |
| Fine-grained hallucination scorer | "Validate every sentence output" | Requires second LLM call per response (NLI model or another LLM); doubles latency and cost | Use retrieval similarity score as proxy confidence; force citation prompt instead |
| Knowledge graph layer | "Captures semantic relationships between concepts" | Major additional infrastructure (Neo4j or similar), schema design, entity extraction pipeline | Qdrant vector similarity handles semantic overlap well enough for v1 |
| Multi-model consensus (majority voting) | "More accurate answers" | Triples API cost; complicates prompting; OpenRouter constraint means limited model variety | Single model with strong citation prompt outperforms multi-model with weak prompting |
| Session persistence across logins | "Users want to return to previous conversations" | Database schema, user-session association, pagination UI; medium complexity for unclear v1 value | Keep conversation state in-session memory only; persist if v2 feedback shows demand |
| Feedback / thumbs rating loop | "Improve the system from user signals" | Valuable long-term but requires storing ratings, building analysis pipeline; won't improve v1 behavior | Log queries and responses for offline analysis post-launch; add thumbs in v2 |
| Jurisdiction / regulatory tagging | "Filter answers by GDPR vs CCPA vs PDPA" | Requires manual or LLM-based tagging of all 17K passages; no such metadata in current dataset | Use semantic search to surface jurisdictionally relevant passages naturally |
| Voice input | "Accessibility" | No mobile-first context; adds audio pipeline complexity | Text input sufficient for compliance analyst use case |
| Admin dashboard / analytics | "Monitor system usage" | Operational concern, not a chatbot feature | Docker logs + basic stdout logging sufficient for v1 monitoring |

**The most dangerous anti-feature: data volume as proxy for quality.** Research explicitly warns that indexing more data without curation degrades retrieval. The 17K dataset passages are already domain-specific; do not pad the index with generic legal text or unrelated documents.

---

## Feature Complexity Notes

Estimated implementation difficulty for each scoped feature, in the context of this stack (Python 3.11, Qdrant, OpenRouter).

| Feature | Difficulty | Primary Work | Risk |
|---------|-----------|--------------|------|
| Document ingestion pipeline (embed + store) | Low | Batch embed via OpenRouter, upsert to Qdrant with metadata | OpenRouter embed rate limits on 17K passages |
| Semantic search (top-k retrieval) | Low | Qdrant query by vector, return chunks with scores | Chunking strategy affects recall significantly |
| Grounded answer generation | Low | Prompt engineering + OpenRouter call | Prompt must force citation; easy to get wrong |
| Inline citations in response | Medium | Anchor injection in chunk text + extraction from LLM output | LLM compliance with citation format varies; needs testing |
| Cross-document conflict detection | Medium-High | Metadata-scoped retrieval + comparison prompt | Works well when relevant chunks land from multiple docs; degrades if retrieval misses one side of a conflict |
| "Cite or abstain" behavior | Low | System prompt instruction | Verify with eval benchmark from dataset QA pairs |
| Conversation history (session) | Low | In-memory list of (role, content) tuples, passed as context prefix | Context window budget; truncate if needed |
| Low-similarity fallback warning | Low | Threshold check on Qdrant score before calling LLM | Choose threshold from empirical score distribution |
| Confidence signal to user | Low-Med | Display retrieval score or categorical label (high/medium/low) in UI | Score calibration to meaningful labels requires testing |
| Auth gating | Low | FastAPI dependency injection + JWT or session cookie | Standard pattern; no novel risk |
| Web UI chat interface | Low-Med | React or simple HTML + fetch; citation display panel adds complexity | Citation expand/collapse UX needs design attention |
| Docker Compose packaging | Low | Qdrant official image + Python API image + optional frontend image | Port mapping, volume mounts, env injection |

**Highest-risk feature: Cross-document conflict detection.** The success depends on whether Qdrant retrieval naturally surfaces passages from multiple documents for a comparison query. If the top-k results cluster around one document, the LLM cannot detect conflicts. Mitigation: test with known cross-document questions from the dataset early, before building the UI layer.

**Highest-leverage low-effort feature: "Cite or abstain" prompt.** A single sentence added to the system prompt ("If the retrieved passages do not contain sufficient information to answer, state that explicitly rather than inferring") prevents the class of hallucinations that would most damage user trust in a compliance context.

---

## Sources

- [Citation-Enforced RAG for Tax Compliance (arxiv)](https://arxiv.org/html/2603.14170v1)
- [RAG for Law — Progress Agentic RAG](https://www.progress.com/agentic-rag/use-cases/rag-for-law)
- [Building RAG-Powered Chatbots for Data Governance](https://towardsagenticai.com/building-rag-powered-chatbots-for-data-governance/)
- [LegalWiz: Contradiction Detection in Legal Documents](https://arxiv.org/abs/2510.03418)
- [Contradiction Detection in RAG Systems](https://arxiv.org/html/2504.00180v1)
- [Legal Document RAG Systems — CustomGPT](https://customgpt.ai/legal-document-rag-systems/)
- [Citation-Aware RAG — Tensorlake](https://www.tensorlake.ai/blog/rag-citations)
- [RAG Citations and Sources — Ailog](https://app.ailog.fr/en/blog/guides/citation-sourcing-rag)
- [Non-Technical Challenges with RAG — Dan Giannone](https://medium.com/@DanGiannone/the-non-technical-challenges-with-rag-e91fb165565e)
- [Hardening RAG Chatbot Architecture — AWS Security Blog](https://aws.amazon.com/blogs/security/hardening-the-rag-chatbot-architecture-powered-by-amazon-bedrock-blueprint-for-secure-design-and-anti-pattern-migration/)
- [Multi-Round RAG for Legal Documents (ACM 2025)](https://dl.acm.org/doi/10.1145/3731715.3733451)
- [Analyzing Corporate Privacy Policies using AI Chatbots (ACM IMC 2024)](https://dl.acm.org/doi/abs/10.1145/3646547.3689015)

# Ingestion Chunking Overhaul Design

## 1. Overview
The current text chunking logic in the data ingestion pipeline relies on a basic recursive character splitter using `tiktoken`. To significantly improve the accuracy and contextual relevance of the retrieved passages (RAG), we are upgrading the chunking strategy to combine **Context-Aware Chunking** (Markdown structure preservation) and **LLM Semantic Enrichment** (Contextual Retrieval technique).

## 2. Architecture & Approach

### 2.1. Safe Tokenization (tiktoken adjustment)
- Continue using `tiktoken` for extreme speed and low overhead.
- Reduce `MAX_TOKENS` from 400 to **350** to create a safe buffer. This mitigates token counting mismatches between OpenAI's encoding and the Llama Nemotron embedding model, preventing out-of-bounds API errors without the heavy footprint of installing `transformers`.

### 2.2. Context-Aware Splitting
- **Header Tracking**: The splitter will maintain a state of the current document hierarchy by tracking Markdown headers (e.g., `#`, `##`).
- **List Preservation**: Enforce strict boundaries around bullet points and numbered lists to ensure they are not cut off mid-sentence.
- **Context Injection**: Each resulting chunk will have a breadcrumb-style header prepended to it.
  - *Format*: `[Source: {doc_title} | Context: {h1} > {h2}] \n\n {chunk_text}`

### 2.3. LLM Semantic Enrichment (Contextual Retrieval)
- **Concept**: Inject an LLM into the ingestion loop to provide standalone context to isolated chunks.
- **Process**:
  1. For each generated chunk, make an async call to the OpenRouter LLM API.
  2. **Prompt Strategy**: Pass the full passage context along with the isolated chunk. Ask the LLM to generate a concise 1-2 sentence context that makes the chunk understandable on its own.
  3. **Enrichment**: Prepend the LLM's generated context to the chunk before sending it to the Embedding model (Nemotron).
- **Resilience**: Implement strict concurrency limits (e.g., async `asyncio.Semaphore(50)`) and robust retry logic (using exponential backoff) to handle OpenRouter rate limits gracefully, given the large volume of passages (17k+).

## 3. Data Flow
1. `ingest()` loads raw passages.
2. `chunk_passage()` applies Context-Aware Splitting (headers + tiktoken sizing).
3. `enrich_chunk_with_llm()` is called asynchronously for each chunk.
4. The enriched chunk text is embedded via Nemotron API.
5. The chunk, its embedding, and metadata are upserted to Qdrant.

## 4. Error Handling & Testing
- **API Rate Limit Failures**: If the LLM enrichment API fails repeatedly after max retries, the system will fallback to embedding the non-enriched Context-Aware chunk to ensure the ingestion pipeline does not crash and data is still indexed.
- **Testing**: Add unit tests for the Markdown header tracking and list preservation logic.

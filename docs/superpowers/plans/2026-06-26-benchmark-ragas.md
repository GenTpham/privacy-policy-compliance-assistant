# RAG Benchmark (BeIR/FiQA + Ragas) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an end-to-end benchmark pipeline that compares our Optimized RAG system against a Naive RAG baseline using the BeIR/FiQA dataset, scoring with Ragas framework metrics (Faithfulness, Answer Correctness, Context Precision, Context Recall).

**Architecture:** Download FiQA corpus/queries/qrels from HuggingFace. Ingest the corpus into two separate Qdrant collections — one using naive fixed-size chunking, one using our optimized chunker with Nemotron embeddings. For each test query, retrieve from both collections, generate answers via the project's configured OSS LLM, then evaluate with Ragas. Output a comparative CSV report.

**Tech Stack:** `datasets` (HuggingFace), `ragas`, `openai` SDK (OpenRouter), `qdrant-client`, existing project chunker and config.

---

## File Structure

| File | Responsibility |
|------|----------------|
| Create: `backend/benchmark/__init__.py` | Package marker |
| Create: `backend/benchmark/config.py` | Benchmark-specific constants (collection names, top-K, sample sizes) |
| Create: `backend/benchmark/data_loader.py` | Download FiQA from HuggingFace, extract corpus/queries/qrels, sample subset |
| Create: `backend/benchmark/naive_chunker.py` | Simple fixed-size character chunker (baseline) |
| Create: `backend/benchmark/ingest_benchmark.py` | Embed and upsert FiQA corpus into both Qdrant collections |
| Create: `backend/benchmark/retriever.py` | Query both collections for a given question, return top-K chunks |
| Create: `backend/benchmark/generator.py` | Use the project's OSS LLM to generate answers from retrieved chunks |
| Create: `backend/benchmark/ragas_evaluator.py` | Wrap results into Ragas format, run evaluate(), export report |
| Create: `backend/benchmark/run_benchmark.py` | CLI entry point orchestrating the full pipeline |
| Create: `backend/benchmark/tests/__init__.py` | Test package marker |
| Create: `backend/benchmark/tests/test_data_loader.py` | Tests for data loading and sampling |
| Create: `backend/benchmark/tests/test_naive_chunker.py` | Tests for naive chunker |
| Create: `backend/benchmark/tests/test_retriever.py` | Tests for retrieval logic |
| Create: `backend/benchmark/tests/test_generator.py` | Tests for answer generation |
| Create: `backend/benchmark/tests/test_ragas_evaluator.py` | Tests for Ragas evaluation wrapper |

---

### Task 1: Add benchmark dependencies

**Files:**
- Modify: `requirements.txt:1-29`

- [ ] **Step 1: Add `datasets`, `ragas`, and `langchain-openai` to requirements.txt**

Ragas requires `langchain-openai` for its internal LLM wrapper. We also need `datasets` to download FiQA from HuggingFace.

```
# --- Benchmark ---
datasets
ragas
langchain-openai
```

Append these lines at the end of `requirements.txt`.

- [ ] **Step 2: Install the new dependencies**

Run:
```bash
pip install datasets ragas langchain-openai
```

Expected: All packages install successfully. Ragas pulls in its own transitive deps.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add benchmark dependencies (datasets, ragas, langchain-openai)"
```

---

### Task 2: Create benchmark config module

**Files:**
- Create: `backend/benchmark/__init__.py`
- Create: `backend/benchmark/config.py`

- [ ] **Step 1: Create the package marker**

```python
# backend/benchmark/__init__.py
"""Benchmark pipeline — compares Optimized RAG vs Naive RAG using BeIR/FiQA + Ragas."""
```

- [ ] **Step 2: Create config.py with all benchmark constants**

```python
# backend/benchmark/config.py
"""
Benchmark-specific configuration constants.
All tunables live here — no magic numbers scattered across modules.
"""

# -- Qdrant collection names (separate from production "policies" collection) --
NAIVE_COLLECTION = "fiqa_naive_rag"
OPTIMIZED_COLLECTION = "fiqa_optimized_rag"

# -- FiQA dataset --
FIQA_DATASET_NAME = "BeIR/fiqa"

# -- Sampling --
# Number of test queries to evaluate (controls API cost)
NUM_TEST_QUERIES = 100

# -- Retrieval --
TOP_K = 5  # chunks retrieved per query

# -- Naive chunker --
NAIVE_CHUNK_SIZE = 1000   # characters — intentionally crude
NAIVE_CHUNK_OVERLAP = 0   # no overlap — this is the "lazy default" baseline

# -- Embedding --
EMBED_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
EMBED_BATCH_SIZE = 50
EMBED_SLEEP_SECONDS = 3  # polite delay for free-tier

# -- Generation --
# Read from rag.py's configured CHAT_MODEL — do NOT hardcode a model here.
# The generator module will import CHAT_MODEL from backend.app.services.rag.

# -- Output --
REPORT_PATH = "benchmark_report.csv"
```

- [ ] **Step 3: Commit**

```bash
git add backend/benchmark/__init__.py backend/benchmark/config.py
git commit -m "feat(benchmark): add config module with constants"
```

---

### Task 3: Build FiQA data loader

**Files:**
- Create: `backend/benchmark/data_loader.py`
- Create: `backend/benchmark/tests/__init__.py`
- Create: `backend/benchmark/tests/test_data_loader.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/benchmark/tests/test_data_loader.py
"""Tests for FiQA data loader."""
import pytest

from backend.benchmark.data_loader import FiQAData, load_fiqa, sample_test_set


class TestLoadFiqa:
    """Test that load_fiqa returns the expected structure."""

    def test_returns_fiqa_data(self):
        data = load_fiqa()
        assert isinstance(data, FiQAData)
        assert len(data.corpus) > 0
        assert len(data.queries) > 0
        assert len(data.qrels) > 0

    def test_corpus_entries_have_text(self):
        data = load_fiqa()
        first_key = next(iter(data.corpus))
        assert isinstance(data.corpus[first_key], str)
        assert len(data.corpus[first_key]) > 0

    def test_queries_are_strings(self):
        data = load_fiqa()
        first_key = next(iter(data.queries))
        assert isinstance(data.queries[first_key], str)

    def test_qrels_map_query_to_doc_ids(self):
        data = load_fiqa()
        first_qid = next(iter(data.qrels))
        assert isinstance(data.qrels[first_qid], list)
        assert len(data.qrels[first_qid]) > 0


class TestSampleTestSet:
    """Test that sample_test_set filters correctly."""

    def test_returns_requested_count(self):
        data = load_fiqa()
        sampled = sample_test_set(data, n=10)
        assert len(sampled.queries) == 10

    def test_corpus_contains_only_relevant_docs(self):
        data = load_fiqa()
        sampled = sample_test_set(data, n=10)
        # Every doc_id referenced in qrels must exist in corpus
        for qid, doc_ids in sampled.qrels.items():
            for doc_id in doc_ids:
                assert doc_id in sampled.corpus, (
                    f"doc_id {doc_id} from qrels not found in sampled corpus"
                )

    def test_qrels_match_queries(self):
        data = load_fiqa()
        sampled = sample_test_set(data, n=10)
        assert set(sampled.qrels.keys()) == set(sampled.queries.keys())
```

- [ ] **Step 2: Create test package marker**

```python
# backend/benchmark/tests/__init__.py
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest backend/benchmark/tests/test_data_loader.py -v`
Expected: FAIL — `ImportError: cannot import name 'FiQAData' from 'backend.benchmark.data_loader'`

- [ ] **Step 4: Write the implementation**

```python
# backend/benchmark/data_loader.py
"""
Download and prepare BeIR/FiQA dataset for benchmarking.

Uses HuggingFace `datasets` library. Caches locally after first download.
Returns structured data with corpus (doc_id → text), queries (qid → question),
and qrels (qid → [list of relevant doc_ids]).
"""
from dataclasses import dataclass

from datasets import load_dataset


@dataclass
class FiQAData:
    """Structured container for FiQA benchmark data."""
    corpus: dict[str, str]       # doc_id → text
    queries: dict[str, str]      # query_id → question text
    qrels: dict[str, list[str]]  # query_id → [relevant doc_ids]


def load_fiqa() -> FiQAData:
    """
    Load BeIR/FiQA from HuggingFace.

    FiQA has three configs on HuggingFace:
      - "corpus": columns [_id, title, text]
      - "queries": columns [_id, text]
      - "default" (qrels): columns [query-id, corpus-id, score]

    Returns a FiQAData with all three components.
    """
    # Load corpus
    corpus_ds = load_dataset("BeIR/fiqa", "corpus", split="corpus")
    corpus: dict[str, str] = {}
    for row in corpus_ds:
        doc_id = str(row["_id"])
        title = row.get("title", "")
        text = row.get("text", "")
        full_text = f"{title}\n{text}".strip() if title else text
        corpus[doc_id] = full_text

    # Load queries
    queries_ds = load_dataset("BeIR/fiqa", "queries", split="queries")
    queries: dict[str, str] = {}
    for row in queries_ds:
        qid = str(row["_id"])
        queries[qid] = row["text"]

    # Load qrels (relevance judgments)
    qrels_ds = load_dataset("BeIR/fiqa", "default", split="test")
    qrels: dict[str, list[str]] = {}
    for row in qrels_ds:
        qid = str(row["query-id"])
        doc_id = str(row["corpus-id"])
        score = row.get("score", 1)
        if score > 0:  # only positive relevance
            if qid not in qrels:
                qrels[qid] = []
            qrels[qid].append(doc_id)

    return FiQAData(corpus=corpus, queries=queries, qrels=qrels)


def sample_test_set(data: FiQAData, n: int) -> FiQAData:
    """
    Sample n queries (that have qrels) and return a filtered FiQAData
    containing only the relevant corpus documents.

    Args:
        data: Full FiQAData from load_fiqa().
        n: Number of test queries to sample.

    Returns:
        A new FiQAData with only the sampled queries, their qrels,
        and the corpus documents referenced by those qrels.
    """
    # Only queries that have relevance judgments
    valid_qids = [qid for qid in data.qrels if qid in data.queries]
    selected_qids = valid_qids[:n]  # deterministic — first n

    sampled_queries = {qid: data.queries[qid] for qid in selected_qids}
    sampled_qrels = {qid: data.qrels[qid] for qid in selected_qids}

    # Collect all referenced doc_ids
    relevant_doc_ids = set()
    for doc_ids in sampled_qrels.values():
        relevant_doc_ids.update(doc_ids)

    sampled_corpus = {
        doc_id: data.corpus[doc_id]
        for doc_id in relevant_doc_ids
        if doc_id in data.corpus
    }

    return FiQAData(
        corpus=sampled_corpus,
        queries=sampled_queries,
        qrels=sampled_qrels,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest backend/benchmark/tests/test_data_loader.py -v`
Expected: All tests PASS (first run will download FiQA from HuggingFace, takes ~1 min)

- [ ] **Step 6: Commit**

```bash
git add backend/benchmark/data_loader.py backend/benchmark/tests/
git commit -m "feat(benchmark): add FiQA data loader with sampling"
```

---

### Task 4: Build naive chunker (baseline)

**Files:**
- Create: `backend/benchmark/naive_chunker.py`
- Create: `backend/benchmark/tests/test_naive_chunker.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/benchmark/tests/test_naive_chunker.py
"""Tests for the naive fixed-size chunker (baseline)."""
from backend.benchmark.naive_chunker import naive_chunk


class TestNaiveChunk:
    """Test the naive character-based chunker."""

    def test_short_text_returns_single_chunk(self):
        result = naive_chunk("Hello world", chunk_size=1000)
        assert len(result) == 1
        assert result[0] == "Hello world"

    def test_long_text_splits_at_chunk_size(self):
        text = "A" * 2500
        result = naive_chunk(text, chunk_size=1000)
        assert len(result) == 3
        assert len(result[0]) == 1000
        assert len(result[1]) == 1000
        assert len(result[2]) == 500

    def test_empty_text_returns_empty_list(self):
        result = naive_chunk("", chunk_size=1000)
        assert result == []

    def test_whitespace_only_returns_empty_list(self):
        result = naive_chunk("   ", chunk_size=1000)
        assert result == []

    def test_exact_chunk_size_returns_one_chunk(self):
        text = "B" * 1000
        result = naive_chunk(text, chunk_size=1000)
        assert len(result) == 1

    def test_no_overlap_by_default(self):
        text = "word " * 400  # 2000 chars
        result = naive_chunk(text, chunk_size=1000, overlap=0)
        # First chunk ends at char 1000, second starts at char 1000
        assert result[0] != result[1]
        # No shared content
        assert result[0][-10:] not in result[1][:10] or result[0][-10:].strip() == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/benchmark/tests/test_naive_chunker.py -v`
Expected: FAIL — `ImportError: cannot import name 'naive_chunk'`

- [ ] **Step 3: Write the implementation**

```python
# backend/benchmark/naive_chunker.py
"""
Naive fixed-size character chunker — the baseline "lazy default" approach.

This intentionally does NO smart splitting: no sentence boundaries, no semantic
awareness, no markdown header tracking, no overlap. It represents the minimal
effort RAG approach that many enterprises use out of the box.
"""
from backend.benchmark.config import NAIVE_CHUNK_SIZE, NAIVE_CHUNK_OVERLAP


def naive_chunk(
    text: str,
    chunk_size: int = NAIVE_CHUNK_SIZE,
    overlap: int = NAIVE_CHUNK_OVERLAP,
) -> list[str]:
    """
    Split text into fixed-size character chunks with optional overlap.

    Args:
        text: Input text to chunk.
        chunk_size: Maximum characters per chunk.
        overlap: Number of overlapping characters between consecutive chunks.

    Returns:
        List of text chunks. Empty list if input is empty/whitespace.
    """
    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap if overlap > 0 else end

    return chunks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/benchmark/tests/test_naive_chunker.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/benchmark/naive_chunker.py backend/benchmark/tests/test_naive_chunker.py
git commit -m "feat(benchmark): add naive character chunker baseline"
```

---

### Task 5: Build ingestion module for benchmark collections

**Files:**
- Create: `backend/benchmark/ingest_benchmark.py`

- [ ] **Step 1: Write the implementation**

This module ingests FiQA corpus into two Qdrant collections. It reuses existing project utilities (`embed_batch`, `probe_embedding_dim`, `make_qdrant_client`) to stay DRY.

```python
# backend/benchmark/ingest_benchmark.py
"""
Ingest FiQA corpus into two Qdrant collections for benchmarking:
  - fiqa_naive_rag: naive fixed-size chunks
  - fiqa_optimized_rag: project's optimized chunker with context headers

Both collections use the same Nemotron embedding model via OpenRouter.
"""
import asyncio
import uuid

from openai import AsyncOpenAI
from qdrant_client.models import Distance, PointStruct, VectorParams

from backend.app.core.config import get_settings
from backend.app.core.qdrant_client import make_qdrant_client
from backend.benchmark.config import (
    EMBED_BATCH_SIZE,
    EMBED_MODEL,
    EMBED_SLEEP_SECONDS,
    NAIVE_COLLECTION,
    OPTIMIZED_COLLECTION,
)
from backend.benchmark.data_loader import FiQAData
from backend.benchmark.naive_chunker import naive_chunk
from backend.ingestion.chunker import chunk_passage
from backend.ingestion.ingest import embed_batch


async def _probe_dim(client: AsyncOpenAI) -> int:
    """Probe embedding dimension from the API."""
    resp = await client.embeddings.create(
        model=EMBED_MODEL, input="probe", encoding_format="float"
    )
    return len(resp.data[0].embedding)


async def _ensure_collection(qdrant, name: str, dim: int) -> None:
    """Create collection if it doesn't exist. Skip if it does."""
    existing = await qdrant.get_collections()
    existing_names = {c.name for c in existing.collections}
    if name in existing_names:
        print(f"[benchmark-ingest] Collection '{name}' already exists — skipping creation.")
        return
    await qdrant.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )
    print(f"[benchmark-ingest] Created collection '{name}' (dim={dim}, COSINE).")


async def _embed_and_upsert(
    qdrant,
    collection_name: str,
    chunks: list[dict],
) -> int:
    """
    Embed chunks and upsert into the specified collection.

    Args:
        chunks: list of {"id": str, "text": str} dicts.

    Returns:
        Number of points upserted.
    """
    total = len(chunks)
    upserted = 0

    for batch_start in range(0, total, EMBED_BATCH_SIZE):
        batch = chunks[batch_start : batch_start + EMBED_BATCH_SIZE]
        texts = [c["text"] for c in batch]

        embeddings = await embed_batch(texts)

        points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, c["id"])),
                vector=emb,
                payload={
                    "doc_id": c.get("doc_id", ""),
                    "text": c["text"],
                    "chunk_index": c.get("chunk_index", 0),
                },
            )
            for c, emb in zip(batch, embeddings)
        ]

        await qdrant.upsert(collection_name=collection_name, points=points, wait=True)
        upserted += len(batch)
        print(f"  [{collection_name}] {upserted}/{total} upserted")
        await asyncio.sleep(EMBED_SLEEP_SECONDS)

    return upserted


async def ingest_naive(qdrant, data: FiQAData, dim: int) -> int:
    """Ingest FiQA corpus using naive chunking into fiqa_naive_rag collection."""
    await _ensure_collection(qdrant, NAIVE_COLLECTION, dim)

    chunks: list[dict] = []
    for doc_id, text in data.corpus.items():
        doc_chunks = naive_chunk(text)
        for i, chunk_text in enumerate(doc_chunks):
            chunks.append({
                "id": f"naive-{doc_id}-{i}",
                "doc_id": doc_id,
                "text": chunk_text,
                "chunk_index": i,
            })

    print(f"[benchmark-ingest] Naive: {len(chunks)} chunks from {len(data.corpus)} docs")
    return await _embed_and_upsert(qdrant, NAIVE_COLLECTION, chunks)


async def ingest_optimized(qdrant, data: FiQAData, dim: int) -> int:
    """Ingest FiQA corpus using project's optimized chunker into fiqa_optimized_rag."""
    await _ensure_collection(qdrant, OPTIMIZED_COLLECTION, dim)

    chunks: list[dict] = []
    for doc_id, text in data.corpus.items():
        optimized_chunks = chunk_passage(
            text=text,
            passage_id=doc_id,
            title=f"FiQA-{doc_id}",
            source_doc=f"FiQA-{doc_id}",
        )
        for c in optimized_chunks:
            chunks.append({
                "id": f"opt-{doc_id}-{c.chunk_index}",
                "doc_id": doc_id,
                "text": c.enriched_text,
                "chunk_index": c.chunk_index,
            })

    print(f"[benchmark-ingest] Optimized: {len(chunks)} chunks from {len(data.corpus)} docs")
    return await _embed_and_upsert(qdrant, OPTIMIZED_COLLECTION, chunks)


async def ingest_both(data: FiQAData) -> dict:
    """
    Run full ingestion for both collections.

    Returns dict with counts: {"naive": N, "optimized": M}
    """
    settings = get_settings()
    openrouter = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
    )
    qdrant = make_qdrant_client(settings)

    dim = await _probe_dim(openrouter)
    print(f"[benchmark-ingest] Probed embedding dim: {dim}")

    naive_count = await ingest_naive(qdrant, data, dim)
    optimized_count = await ingest_optimized(qdrant, data, dim)

    return {"naive": naive_count, "optimized": optimized_count}
```

- [ ] **Step 2: Commit**

```bash
git add backend/benchmark/ingest_benchmark.py
git commit -m "feat(benchmark): add dual-collection ingestion (naive + optimized)"
```

---

### Task 6: Build retriever module

**Files:**
- Create: `backend/benchmark/retriever.py`
- Create: `backend/benchmark/tests/test_retriever.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/benchmark/tests/test_retriever.py
"""Tests for benchmark retriever."""
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

import pytest

from backend.benchmark.retriever import retrieve_chunks, RetrievalResult


@pytest.fixture
def mock_qdrant():
    client = AsyncMock()
    point = SimpleNamespace(
        id="test-id",
        score=0.85,
        payload={"doc_id": "doc1", "text": "sample text", "chunk_index": 0},
    )
    client.query_points.return_value = SimpleNamespace(points=[point])
    return client


@pytest.fixture
def mock_openrouter():
    client = AsyncMock()
    embedding_data = SimpleNamespace(embedding=[0.1] * 768, index=0)
    client.embeddings.create.return_value = SimpleNamespace(data=[embedding_data])
    return client


class TestRetrieveChunks:
    @pytest.mark.asyncio
    async def test_returns_retrieval_result(self, mock_qdrant, mock_openrouter):
        result = await retrieve_chunks(
            query="test question",
            collection_name="test_collection",
            qdrant=mock_qdrant,
            openrouter=mock_openrouter,
            top_k=5,
        )
        assert isinstance(result, RetrievalResult)
        assert len(result.chunks) == 1
        assert result.chunks[0]["text"] == "sample text"
        assert result.chunks[0]["score"] == 0.85

    @pytest.mark.asyncio
    async def test_calls_qdrant_with_correct_params(self, mock_qdrant, mock_openrouter):
        await retrieve_chunks(
            query="test",
            collection_name="my_collection",
            qdrant=mock_qdrant,
            openrouter=mock_openrouter,
            top_k=3,
        )
        mock_qdrant.query_points.assert_called_once()
        call_kwargs = mock_qdrant.query_points.call_args.kwargs
        assert call_kwargs["collection_name"] == "my_collection"
        assert call_kwargs["limit"] == 3

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_qdrant, mock_openrouter):
        mock_qdrant.query_points.return_value = SimpleNamespace(points=[])
        result = await retrieve_chunks(
            query="nothing",
            collection_name="empty",
            qdrant=mock_qdrant,
            openrouter=mock_openrouter,
        )
        assert result.chunks == []
        assert result.doc_ids == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/benchmark/tests/test_retriever.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write the implementation**

```python
# backend/benchmark/retriever.py
"""
Retrieve top-K chunks from a Qdrant collection for a given query.
Shared by both naive and optimized benchmark paths.
"""
from dataclasses import dataclass, field

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from backend.benchmark.config import EMBED_MODEL, TOP_K


@dataclass
class RetrievalResult:
    """Container for retrieval output."""
    chunks: list[dict] = field(default_factory=list)    # [{text, doc_id, score, chunk_index}]
    doc_ids: list[str] = field(default_factory=list)    # unique doc_ids in retrieval order

    @property
    def texts(self) -> list[str]:
        """Return chunk texts as a flat list (for Ragas contexts)."""
        return [c["text"] for c in self.chunks]


async def retrieve_chunks(
    query: str,
    collection_name: str,
    qdrant: AsyncQdrantClient,
    openrouter: AsyncOpenAI,
    top_k: int = TOP_K,
) -> RetrievalResult:
    """
    Embed query and retrieve top-K chunks from the specified collection.

    Args:
        query: The question text.
        collection_name: Qdrant collection to search.
        qdrant: Async Qdrant client.
        openrouter: Async OpenAI client (for embedding).
        top_k: Number of results to retrieve.

    Returns:
        RetrievalResult with chunks and doc_ids.
    """
    # Embed query
    resp = await openrouter.embeddings.create(
        model=EMBED_MODEL,
        input=[query],
        encoding_format="float",
    )
    query_vector = resp.data[0].embedding

    # Query Qdrant
    response = await qdrant.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    )

    chunks: list[dict] = []
    seen_doc_ids: list[str] = []

    for point in response.points:
        doc_id = point.payload.get("doc_id", "")
        chunks.append({
            "text": point.payload.get("text", ""),
            "doc_id": doc_id,
            "score": round(point.score, 4),
            "chunk_index": point.payload.get("chunk_index", 0),
        })
        if doc_id not in seen_doc_ids:
            seen_doc_ids.append(doc_id)

    return RetrievalResult(chunks=chunks, doc_ids=seen_doc_ids)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/benchmark/tests/test_retriever.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/benchmark/retriever.py backend/benchmark/tests/test_retriever.py
git commit -m "feat(benchmark): add retriever module with tests"
```

---

### Task 7: Build generator module

**Files:**
- Create: `backend/benchmark/generator.py`
- Create: `backend/benchmark/tests/test_generator.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/benchmark/tests/test_generator.py
"""Tests for benchmark answer generator."""
from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace

import pytest

from backend.benchmark.generator import generate_answer


@pytest.fixture
def mock_llm_client():
    client = AsyncMock()
    choice = SimpleNamespace(
        message=SimpleNamespace(content="The answer is 42.")
    )
    client.chat.completions.create.return_value = SimpleNamespace(choices=[choice])
    return client


class TestGenerateAnswer:
    @pytest.mark.asyncio
    async def test_returns_answer_string(self, mock_llm_client):
        result = await generate_answer(
            question="What is the meaning?",
            contexts=["Context passage 1", "Context passage 2"],
            llm_client=mock_llm_client,
            chat_model="test-model",
        )
        assert isinstance(result, str)
        assert result == "The answer is 42."

    @pytest.mark.asyncio
    async def test_sends_contexts_in_prompt(self, mock_llm_client):
        await generate_answer(
            question="What?",
            contexts=["Alpha context", "Beta context"],
            llm_client=mock_llm_client,
            chat_model="test-model",
        )
        call_args = mock_llm_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        system_msg = messages[0]["content"]
        assert "Alpha context" in system_msg
        assert "Beta context" in system_msg

    @pytest.mark.asyncio
    async def test_empty_contexts_still_works(self, mock_llm_client):
        result = await generate_answer(
            question="No context?",
            contexts=[],
            llm_client=mock_llm_client,
            chat_model="test-model",
        )
        assert isinstance(result, str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/benchmark/tests/test_generator.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write the implementation**

```python
# backend/benchmark/generator.py
"""
Generate answers using the project's configured OSS LLM.
Non-streaming version for batch benchmark evaluation.
"""
from openai import AsyncOpenAI


def _build_benchmark_prompt(question: str, contexts: list[str]) -> list[dict]:
    """
    Build a simple RAG prompt for benchmarking.
    Uses numbered context passages, similar to the production prompt in rag.py.
    """
    context_lines = [
        f"[{i}] {text}" for i, text in enumerate(contexts, start=1)
    ]
    system_content = (
        "You are a helpful assistant. "
        "Answer the question using ONLY the provided context passages below. "
        "If the passages do not contain the answer, say 'I cannot answer based on the provided context.'\n\n"
        "Context passages:\n" + "\n\n".join(context_lines)
    )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": question},
    ]


async def generate_answer(
    question: str,
    contexts: list[str],
    llm_client: AsyncOpenAI,
    chat_model: str,
    temperature: float = 0.0,
    max_tokens: int = 512,
) -> str:
    """
    Generate an answer using the LLM given a question and retrieved contexts.

    Args:
        question: The user question.
        contexts: List of retrieved chunk texts.
        llm_client: AsyncOpenAI client (configured for OpenRouter or OpenAI).
        chat_model: Model identifier string.
        temperature: Sampling temperature (0.0 for deterministic).
        max_tokens: Max tokens in the response.

    Returns:
        The generated answer as a string.
    """
    messages = _build_benchmark_prompt(question, contexts)

    response = await llm_client.chat.completions.create(
        model=chat_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
    )

    return response.choices[0].message.content.strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/benchmark/tests/test_generator.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/benchmark/generator.py backend/benchmark/tests/test_generator.py
git commit -m "feat(benchmark): add answer generator module with tests"
```

---

### Task 8: Build Ragas evaluator module

**Files:**
- Create: `backend/benchmark/ragas_evaluator.py`
- Create: `backend/benchmark/tests/test_ragas_evaluator.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/benchmark/tests/test_ragas_evaluator.py
"""Tests for Ragas evaluation wrapper."""
import pytest

from backend.benchmark.ragas_evaluator import (
    BenchmarkRecord,
    prepare_ragas_dataset,
)


class TestBenchmarkRecord:
    def test_fields(self):
        rec = BenchmarkRecord(
            question="What?",
            answer="42",
            contexts=["passage 1"],
            ground_truth="The answer is 42",
        )
        assert rec.question == "What?"
        assert rec.answer == "42"
        assert rec.contexts == ["passage 1"]
        assert rec.ground_truth == "The answer is 42"


class TestPrepareRagasDataset:
    def test_returns_dataset_with_correct_columns(self):
        records = [
            BenchmarkRecord(
                question="Q1",
                answer="A1",
                contexts=["C1"],
                ground_truth="GT1",
            ),
            BenchmarkRecord(
                question="Q2",
                answer="A2",
                contexts=["C2a", "C2b"],
                ground_truth="GT2",
            ),
        ]
        ds = prepare_ragas_dataset(records)
        assert "question" in ds.column_names
        assert "answer" in ds.column_names
        assert "contexts" in ds.column_names
        assert "ground_truth" in ds.column_names
        assert len(ds) == 2

    def test_contexts_are_lists(self):
        records = [
            BenchmarkRecord(
                question="Q",
                answer="A",
                contexts=["C1", "C2"],
                ground_truth="GT",
            ),
        ]
        ds = prepare_ragas_dataset(records)
        assert isinstance(ds[0]["contexts"], list)
        assert ds[0]["contexts"] == ["C1", "C2"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/benchmark/tests/test_ragas_evaluator.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write the implementation**

```python
# backend/benchmark/ragas_evaluator.py
"""
Ragas evaluation wrapper.

Prepares benchmark records into Ragas-compatible Dataset format,
runs evaluation with configured metrics, and exports results.
"""
import csv
from dataclasses import dataclass
from pathlib import Path

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    answer_correctness,
    context_precision,
    context_recall,
    faithfulness,
)
from langchain_openai import ChatOpenAI

from backend.app.core.config import get_settings
from backend.benchmark.config import REPORT_PATH


@dataclass
class BenchmarkRecord:
    """A single benchmark evaluation record."""
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str


def prepare_ragas_dataset(records: list[BenchmarkRecord]) -> Dataset:
    """
    Convert BenchmarkRecords into a HuggingFace Dataset with
    the columns Ragas expects: question, answer, contexts, ground_truth.
    """
    data = {
        "question": [r.question for r in records],
        "answer": [r.answer for r in records],
        "contexts": [r.contexts for r in records],
        "ground_truth": [r.ground_truth for r in records],
    }
    return Dataset.from_dict(data)


def _make_judge_llm() -> ChatOpenAI:
    """
    Create the LLM used by Ragas as a "judge" to score metrics.
    Uses the project's configured OSS model via OpenRouter.
    """
    settings = get_settings()
    return ChatOpenAI(
        model="openai/gpt-oss-120b:free",
        openai_api_key=settings.openrouter_api_key,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0.0,
    )


def run_ragas_evaluation(
    naive_records: list[BenchmarkRecord],
    optimized_records: list[BenchmarkRecord],
    report_path: str = REPORT_PATH,
) -> dict:
    """
    Run Ragas evaluation on both naive and optimized record sets.

    Args:
        naive_records: Records from the naive RAG pipeline.
        optimized_records: Records from the optimized RAG pipeline.
        report_path: Path to save the CSV report.

    Returns:
        Dict with keys "naive" and "optimized", each containing
        a dict of metric_name → score.
    """
    judge_llm = _make_judge_llm()
    metrics = [faithfulness, answer_correctness, context_precision, context_recall]

    # Evaluate naive
    print("[ragas] Evaluating Naive RAG...")
    naive_ds = prepare_ragas_dataset(naive_records)
    naive_result = evaluate(
        dataset=naive_ds,
        metrics=metrics,
        llm=judge_llm,
    )

    # Evaluate optimized
    print("[ragas] Evaluating Optimized RAG...")
    optimized_ds = prepare_ragas_dataset(optimized_records)
    optimized_result = evaluate(
        dataset=optimized_ds,
        metrics=metrics,
        llm=judge_llm,
    )

    results = {
        "naive": dict(naive_result),
        "optimized": dict(optimized_result),
    }

    # Export CSV report
    _export_report(results, report_path)

    return results


def _export_report(results: dict, report_path: str) -> None:
    """Export comparison results to CSV."""
    path = Path(report_path)
    metrics = list(results["naive"].keys())

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Naive RAG", "Optimized RAG", "Improvement"])

        for metric in metrics:
            naive_score = results["naive"].get(metric, 0)
            opt_score = results["optimized"].get(metric, 0)

            if isinstance(naive_score, (int, float)) and isinstance(opt_score, (int, float)):
                improvement = opt_score - naive_score
                writer.writerow([
                    metric,
                    f"{naive_score:.4f}",
                    f"{opt_score:.4f}",
                    f"{improvement:+.4f}",
                ])
            else:
                writer.writerow([metric, str(naive_score), str(opt_score), "N/A"])

    print(f"[ragas] Report saved to {path}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/benchmark/tests/test_ragas_evaluator.py -v`
Expected: PASS for `TestBenchmarkRecord` and `TestPrepareRagasDataset`. (The `run_ragas_evaluation` function requires live API — tested via integration in Task 10.)

- [ ] **Step 5: Commit**

```bash
git add backend/benchmark/ragas_evaluator.py backend/benchmark/tests/test_ragas_evaluator.py
git commit -m "feat(benchmark): add Ragas evaluator with CSV report export"
```

---

### Task 9: Build CLI entry point

**Files:**
- Create: `backend/benchmark/run_benchmark.py`

- [ ] **Step 1: Write the implementation**

```python
# backend/benchmark/run_benchmark.py
"""
CLI entry point for the full benchmark pipeline.

Usage:
  python -m backend.benchmark.run_benchmark
  python -m backend.benchmark.run_benchmark --num-queries 50
  python -m backend.benchmark.run_benchmark --skip-ingest  (if collections already populated)

Pipeline:
  1. Download & sample FiQA dataset
  2. Ingest into naive + optimized Qdrant collections
  3. For each query: retrieve from both → generate answer with OSS LLM
  4. Score with Ragas → export comparison CSV
"""
import argparse
import asyncio
import time

from openai import AsyncOpenAI

from backend.app.core.config import get_settings
from backend.app.core.qdrant_client import make_qdrant_client
from backend.app.services.rag import CHAT_MODEL, llm_client
from backend.benchmark.config import (
    NAIVE_COLLECTION,
    NUM_TEST_QUERIES,
    OPTIMIZED_COLLECTION,
    REPORT_PATH,
    TOP_K,
)
from backend.benchmark.data_loader import load_fiqa, sample_test_set
from backend.benchmark.generator import generate_answer
from backend.benchmark.ingest_benchmark import ingest_both
from backend.benchmark.ragas_evaluator import BenchmarkRecord, run_ragas_evaluation
from backend.benchmark.retriever import retrieve_chunks


async def run_benchmark(
    num_queries: int = NUM_TEST_QUERIES,
    skip_ingest: bool = False,
    report_path: str = REPORT_PATH,
) -> None:
    """Execute the full benchmark pipeline."""

    print("=" * 80)
    print("  RAG Benchmark: Naive vs Optimized (BeIR/FiQA + Ragas)")
    print("=" * 80)

    # Step 1: Load and sample data
    print("\n[1/4] Loading FiQA dataset...")
    t0 = time.perf_counter()
    data = load_fiqa()
    sampled = sample_test_set(data, n=num_queries)
    print(
        f"  Loaded: {len(data.corpus)} docs, {len(data.queries)} queries\n"
        f"  Sampled: {len(sampled.queries)} queries, {len(sampled.corpus)} relevant docs\n"
        f"  Time: {time.perf_counter() - t0:.1f}s"
    )

    # Step 2: Ingest into both collections
    if not skip_ingest:
        print("\n[2/4] Ingesting into Qdrant (naive + optimized)...")
        t0 = time.perf_counter()
        counts = await ingest_both(sampled)
        print(
            f"  Naive: {counts['naive']} chunks | Optimized: {counts['optimized']} chunks\n"
            f"  Time: {time.perf_counter() - t0:.1f}s"
        )
    else:
        print("\n[2/4] Skipping ingestion (--skip-ingest)")

    # Step 3: Retrieve + Generate for both pipelines
    print(f"\n[3/4] Running inference loop ({len(sampled.queries)} queries × 2 pipelines)...")
    settings = get_settings()
    openrouter = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
    )
    qdrant = make_qdrant_client(settings)

    naive_records: list[BenchmarkRecord] = []
    optimized_records: list[BenchmarkRecord] = []

    t0 = time.perf_counter()
    for i, (qid, question) in enumerate(sampled.queries.items(), 1):
        # Ground truth: concatenate all relevant doc texts
        gt_doc_ids = sampled.qrels.get(qid, [])
        ground_truth = " ".join(
            sampled.corpus.get(did, "") for did in gt_doc_ids
        ).strip()

        # Retrieve from both collections
        naive_result = await retrieve_chunks(
            query=question,
            collection_name=NAIVE_COLLECTION,
            qdrant=qdrant,
            openrouter=openrouter,
            top_k=TOP_K,
        )
        optimized_result = await retrieve_chunks(
            query=question,
            collection_name=OPTIMIZED_COLLECTION,
            qdrant=qdrant,
            openrouter=openrouter,
            top_k=TOP_K,
        )

        # Generate answers using project's configured OSS LLM
        naive_answer = await generate_answer(
            question=question,
            contexts=naive_result.texts,
            llm_client=llm_client,
            chat_model=CHAT_MODEL,
        )
        optimized_answer = await generate_answer(
            question=question,
            contexts=optimized_result.texts,
            llm_client=llm_client,
            chat_model=CHAT_MODEL,
        )

        naive_records.append(BenchmarkRecord(
            question=question,
            answer=naive_answer,
            contexts=naive_result.texts,
            ground_truth=ground_truth,
        ))
        optimized_records.append(BenchmarkRecord(
            question=question,
            answer=optimized_answer,
            contexts=optimized_result.texts,
            ground_truth=ground_truth,
        ))

        # Progress
        if i % 10 == 0 or i == len(sampled.queries):
            elapsed = time.perf_counter() - t0
            print(f"  {i}/{len(sampled.queries)} queries done ({elapsed:.0f}s)")

    # Step 4: Ragas evaluation
    print(f"\n[4/4] Running Ragas evaluation...")
    results = run_ragas_evaluation(
        naive_records=naive_records,
        optimized_records=optimized_records,
        report_path=report_path,
    )

    # Print summary
    print("\n" + "=" * 80)
    print("  BENCHMARK RESULTS")
    print("=" * 80)
    print(f"\n{'Metric':<25} {'Naive RAG':>12} {'Optimized RAG':>15} {'Δ':>10}")
    print("-" * 65)
    for metric in results["naive"]:
        naive_val = results["naive"][metric]
        opt_val = results["optimized"][metric]
        if isinstance(naive_val, (int, float)) and isinstance(opt_val, (int, float)):
            delta = opt_val - naive_val
            print(f"{metric:<25} {naive_val:>12.4f} {opt_val:>15.4f} {delta:>+10.4f}")
    print("-" * 65)
    print(f"\nReport saved to: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Run RAG benchmark: Naive vs Optimized using BeIR/FiQA + Ragas"
    )
    parser.add_argument(
        "--num-queries", type=int, default=NUM_TEST_QUERIES,
        help=f"Number of test queries to evaluate (default: {NUM_TEST_QUERIES})"
    )
    parser.add_argument(
        "--skip-ingest", action="store_true",
        help="Skip ingestion step (use existing collections)"
    )
    parser.add_argument(
        "--report", default=REPORT_PATH,
        help=f"Output report path (default: {REPORT_PATH})"
    )
    args = parser.parse_args()

    asyncio.run(run_benchmark(
        num_queries=args.num_queries,
        skip_ingest=args.skip_ingest,
        report_path=args.report,
    ))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add backend/benchmark/run_benchmark.py
git commit -m "feat(benchmark): add CLI entry point for full pipeline"
```

---

### Task 10: Integration test — dry run with small sample

**Files:**
- No new files.

- [ ] **Step 1: Run the full pipeline with 5 queries**

This is the integration smoke test. It exercises data download, ingestion, retrieval, generation, and Ragas scoring end-to-end.

Run:
```bash
python -m backend.benchmark.run_benchmark --num-queries 5 --report benchmark_report_test.csv
```

Expected:
- FiQA downloads from HuggingFace (cached after first run)
- Two collections (`fiqa_naive_rag`, `fiqa_optimized_rag`) created in Qdrant
- 5 queries processed through both pipelines
- Ragas scores printed to console
- `benchmark_report_test.csv` created with metric comparison

- [ ] **Step 2: Verify the CSV report**

Run: `type benchmark_report_test.csv` (Windows) or `cat benchmark_report_test.csv`

Expected: CSV with columns `Metric, Naive RAG, Optimized RAG, Improvement` and rows for `faithfulness`, `answer_correctness`, `context_precision`, `context_recall`.

- [ ] **Step 3: Clean up test report**

Run: `del benchmark_report_test.csv` (or `rm benchmark_report_test.csv`)

- [ ] **Step 4: Commit all remaining files**

```bash
git add .
git commit -m "feat(benchmark): complete benchmark pipeline with integration verification"
```

---

### Task 11: Run full benchmark (100 queries)

- [ ] **Step 1: Run with default 100 queries**

Run:
```bash
python -m backend.benchmark.run_benchmark
```

Expected: Full pipeline runs end-to-end. Takes approximately 30-60 minutes depending on API rate limits. Results saved to `benchmark_report.csv`.

- [ ] **Step 2: Review and commit the report**

```bash
git add benchmark_report.csv
git commit -m "docs(benchmark): add benchmark results — Naive vs Optimized RAG on FiQA"
```

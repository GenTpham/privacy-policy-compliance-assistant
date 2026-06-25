# Chunking Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the basic recursive character splitter with a Context-Aware + LLM Semantic Enrichment chunking pipeline that preserves document structure and adds standalone context to every chunk.

**Architecture:** The chunker is refactored into a 2-stage pipeline: (1) a rule-based Context-Aware Splitter that tracks Markdown headers, preserves list items, and injects breadcrumb context into each chunk; (2) an async LLM Enrichment step that calls `openai/gpt-oss-120b:free` via OpenRouter to generate a concise contextual summary for each chunk. The enriched text is what gets embedded and stored. Fallback: if LLM enrichment fails after retries, the context-aware chunk (without LLM summary) is used.

**Tech Stack:** Python 3.11, tiktoken, AsyncOpenAI (openai SDK), Qdrant, pytest

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Rewrite | `backend/ingestion/chunker.py` | Context-aware splitting: header tracking, list preservation, breadcrumb injection, token budget reduced to 350 |
| Create | `backend/ingestion/llm_enricher.py` | Async LLM enrichment: prompt template, semaphore-based concurrency, retry with exponential backoff, graceful fallback |
| Modify | `backend/ingestion/ingest.py:276-314` | Wire enrichment into the bulk corpus ingestion loop between chunking and embedding |
| Modify | `backend/ingestion/ingest_doc.py:233-300` | Wire enrichment into the single-document ingestion pipeline |
| Modify | `backend/app/services/document_processor.py:56-74` | Wire enrichment into the inline document processor |
| Create | `backend/ingestion/tests/test_chunker.py` | Unit tests for Context-Aware chunker |
| Create | `backend/ingestion/tests/test_llm_enricher.py` | Unit tests for LLM enrichment with mocked API |

---

### Task 1: Rewrite the Context-Aware Chunker

**Files:**
- Rewrite: `backend/ingestion/chunker.py`
- Create: `backend/ingestion/tests/test_chunker.py`

- [ ] **Step 1: Write failing tests for the new chunker**

Create `backend/ingestion/tests/test_chunker.py`:

```python
"""Tests for the context-aware chunker."""
import pytest

from backend.ingestion.chunker import Chunk, chunk_passage, MAX_TOKENS, _count_tokens


class TestFastPath:
    """Passages that fit within MAX_TOKENS should return a single chunk."""

    def test_short_passage_returns_single_chunk(self):
        text = "This is a short passage about data collection."
        chunks = chunk_passage(
            text=text,
            passage_id="p1",
            title="Privacy Policy",
            source_doc="policy.pdf",
        )
        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].passage_id == "p1"
        assert "This is a short passage" in chunks[0].text

    def test_short_passage_token_count_accurate(self):
        text = "Short text for token counting."
        chunks = chunk_passage(
            text=text, passage_id="p2", title="T", source_doc="S"
        )
        assert chunks[0].token_count == _count_tokens(chunks[0].text)


class TestMarkdownHeaderTracking:
    """Chunks from documents with Markdown headers should include breadcrumb context."""

    def test_breadcrumb_injected_for_h1_h2(self):
        text = (
            "# Điều 1. Thu thập dữ liệu\n\n"
            "## Khoản 1. Thông tin cá nhân\n\n"
            "Chúng tôi thu thập họ tên và email của bạn.\n\n"
            "## Khoản 2. Thông tin thiết bị\n\n"
            "Chúng tôi ghi nhận địa chỉ IP mỗi lần đăng nhập."
        )
        chunks = chunk_passage(
            text=text, passage_id="md1", title="Chính sách Zalo", source_doc="zalo.pdf"
        )
        # All chunks should exist
        assert len(chunks) >= 1
        # First chunk should contain its header context
        assert "Điều 1" in chunks[0].context_header

    def test_no_headers_means_empty_context_header(self):
        text = "Plain text without any markdown headers at all."
        chunks = chunk_passage(
            text=text, passage_id="plain1", title="T", source_doc="S"
        )
        assert chunks[0].context_header == ""


class TestListPreservation:
    """List items should not be split mid-list."""

    def test_numbered_list_kept_together(self):
        # Build a list that fits in one chunk
        items = [f"{i}. Item number {i} with some description text." for i in range(1, 6)]
        text = "Introduction paragraph.\n\n" + "\n".join(items)
        chunks = chunk_passage(
            text=text, passage_id="list1", title="T", source_doc="S"
        )
        # The list should not be split across chunks if it fits
        full_text = " ".join(c.text for c in chunks)
        for item in items:
            assert item in full_text

    def test_bullet_list_not_split_mid_item(self):
        items = [f"- Bullet point {i} explaining a policy rule." for i in range(1, 4)]
        text = "## Rules\n\n" + "\n".join(items)
        chunks = chunk_passage(
            text=text, passage_id="bullet1", title="T", source_doc="S"
        )
        # Each chunk should contain complete bullet points (no partial lines)
        for chunk in chunks:
            lines = [l for l in chunk.text.split("\n") if l.strip()]
            for line in lines:
                # A line starting with "- " should not be truncated mid-word
                if line.strip().startswith("- Bullet"):
                    assert line.strip().endswith(".")


class TestLongPassageSplitting:
    """Passages exceeding MAX_TOKENS must be split."""

    def test_long_passage_splits_within_token_limit(self):
        # Generate a passage that definitely exceeds MAX_TOKENS
        long_text = "This is a sentence about data privacy. " * 200
        chunks = chunk_passage(
            text=long_text, passage_id="long1", title="T", source_doc="S"
        )
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.token_count <= MAX_TOKENS + 10  # small tolerance for edge rounding

    def test_chunk_indices_are_sequential(self):
        long_text = "Word " * 500
        chunks = chunk_passage(
            text=long_text, passage_id="seq1", title="T", source_doc="S"
        )
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i


class TestTokenBudget:
    """MAX_TOKENS should be 350 (safety buffer for Nemotron tokenizer mismatch)."""

    def test_max_tokens_is_350(self):
        assert MAX_TOKENS == 350


class TestChunkDataclass:
    """Chunk dataclass should include the new context_header field."""

    def test_chunk_has_context_header(self):
        chunk = Chunk(
            text="some text",
            title="T",
            source_doc="S",
            passage_id="p1",
            chunk_index=0,
            token_count=5,
            context_header="[Source: T | Context: H1 > H2]",
        )
        assert chunk.context_header == "[Source: T | Context: H1 > H2]"

    def test_enriched_text_combines_header_and_text(self):
        chunk = Chunk(
            text="some text",
            title="T",
            source_doc="S",
            passage_id="p1",
            chunk_index=0,
            token_count=5,
            context_header="[Source: T | Context: H1]",
        )
        assert chunk.enriched_text == "[Source: T | Context: H1]\n\nsome text"

    def test_enriched_text_without_header(self):
        chunk = Chunk(
            text="some text",
            title="T",
            source_doc="S",
            passage_id="p1",
            chunk_index=0,
            token_count=5,
            context_header="",
        )
        assert chunk.enriched_text == "some text"

    def test_enriched_text_with_llm_context(self):
        chunk = Chunk(
            text="some text",
            title="T",
            source_doc="S",
            passage_id="p1",
            chunk_index=0,
            token_count=5,
            context_header="[Source: T | Context: H1]",
            llm_context="This chunk explains data retention rules.",
        )
        expected = "[Source: T | Context: H1]\n\nThis chunk explains data retention rules.\n\nsome text"
        assert chunk.enriched_text == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/ingestion/tests/test_chunker.py -v`
Expected: FAIL — `context_header` field does not exist on `Chunk`, `enriched_text` property not defined, `MAX_TOKENS` is still 400.

- [ ] **Step 3: Rewrite `chunker.py` with context-aware logic**

Rewrite `backend/ingestion/chunker.py` with the full implementation:

```python
"""
backend/ingestion/chunker.py
Context-aware text splitting for privacy policy passages.
Tracks Markdown headers to inject breadcrumb context into each chunk.
Preserves list items as atomic units. Token budget: 350 (safe for Nemotron).
"""
import re
from dataclasses import dataclass

import tiktoken

MAX_TOKENS = 350       # reduced from 400 — safety buffer for Nemotron tokenizer mismatch
OVERLAP_TOKENS = 50    # ~14% overlap — preserves clause continuity at boundaries
SEPARATORS = ["\n\n", "\n", ". ", " "]  # priority order — paragraph → line → sentence → word

_enc = tiktoken.get_encoding("cl100k_base")

# ── Regex patterns ────────────────────────────────────────────────────────────
_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_LIST_ITEM_RE = re.compile(
    r"^\s*(\d+\.|[a-z]\)|[a-z]\.|[(][a-z][)]|\*|-)\s", re.IGNORECASE
)


@dataclass
class Chunk:
    text: str
    title: str
    source_doc: str
    passage_id: str
    chunk_index: int
    token_count: int
    context_header: str = ""
    llm_context: str = ""

    @property
    def enriched_text(self) -> str:
        """Return text with context header and LLM context prepended (if present)."""
        parts: list[str] = []
        if self.context_header:
            parts.append(self.context_header)
        if self.llm_context:
            parts.append(self.llm_context)
        parts.append(self.text)
        return "\n\n".join(parts)


def _count_tokens(text: str) -> int:
    return len(_enc.encode(text))


def _build_header_breadcrumb(header_stack: dict[int, str], title: str) -> str:
    """
    Build a breadcrumb string from the current header stack.
    Example: "[Source: Chính sách Zalo | Context: Điều 1 > Khoản 2]"
    """
    if not header_stack:
        return ""
    parts = [header_stack[level] for level in sorted(header_stack.keys())]
    context_path = " > ".join(parts)
    return f"[Source: {title} | Context: {context_path}]"


def _extract_headers(text: str) -> list[tuple[int, str, int]]:
    """
    Extract all markdown headers from text.
    Returns list of (level, header_text, char_position).
    """
    results = []
    for match in _HEADER_RE.finditer(text):
        level = len(match.group(1))  # number of '#' chars
        header_text = match.group(2).strip()
        results.append((level, header_text, match.start()))
    return results


def _is_list_item_start(text: str) -> bool:
    """Detect if text begins a numbered/lettered list item."""
    return bool(_LIST_ITEM_RE.match(text))


def _split_preserving_lists(text: str, separator: str) -> list[str]:
    """
    Split text by separator, but merge list items with their preceding
    content to avoid splitting mid-list.
    """
    if separator == " ":
        return text.split()

    raw_parts = text.split(separator)
    if len(raw_parts) <= 1:
        return [text]

    # Re-attach separator to end of each part except last
    parts = [p + separator for p in raw_parts[:-1]] + [raw_parts[-1]]

    # Merge consecutive list items into a single block
    merged: list[str] = []
    for part in parts:
        stripped = part.strip()
        if _is_list_item_start(stripped) and merged:
            # Append to previous block to keep list together
            merged[-1] += part
        else:
            merged.append(part)

    return merged


def _split_by_separator(text: str, separator: str) -> list[str]:
    """Split text by separator, keeping separators at end of left part."""
    if separator == " ":
        return text.split()
    parts = text.split(separator)
    return [p + separator for p in parts[:-1]] + [parts[-1]] if len(parts) > 1 else [text]


def chunk_passage(
    text: str,
    passage_id: str,
    title: str,
    source_doc: str,
) -> list[Chunk]:
    """
    Split a passage into chunks respecting token limits, semantic boundaries,
    and document structure (Markdown headers, lists).

    Each chunk gets a `context_header` breadcrumb derived from the nearest
    preceding Markdown headers, enabling standalone comprehension.
    """
    text = text.strip()
    if not text:
        return []

    # ── Phase 1: Extract header positions for breadcrumb tracking ─────────
    headers = _extract_headers(text)

    # ── Phase 2: Check token count ────────────────────────────────────────
    token_count = _count_tokens(text)

    # Fast path: passage fits in one chunk
    if token_count <= MAX_TOKENS:
        header_stack: dict[int, str] = {}
        for level, header_text, _ in headers:
            # Clear deeper levels when a higher-level header appears
            keys_to_remove = [k for k in header_stack if k >= level]
            for k in keys_to_remove:
                del header_stack[k]
            header_stack[level] = header_text

        breadcrumb = _build_header_breadcrumb(header_stack, title)
        return [
            Chunk(
                text=text,
                title=title,
                source_doc=source_doc,
                passage_id=passage_id,
                chunk_index=0,
                token_count=token_count,
                context_header=breadcrumb,
            )
        ]

    # ── Phase 3: Slow path — split long passages ──────────────────────────
    chunks: list[Chunk] = []
    chunk_index = 0
    remaining = text

    # Track the header context as we consume the text
    header_stack: dict[int, str] = {}
    header_idx = 0  # pointer into sorted headers list

    while remaining:
        split_done = False
        for sep in SEPARATORS:
            if sep not in remaining:
                continue

            parts = _split_preserving_lists(remaining, sep)
            current: list[str] = []
            current_tokens = 0

            for part in parts:
                # Update header stack for any headers in this part
                for h_level, h_text, h_pos in headers[header_idx:]:
                    if h_text in part:
                        keys_to_remove = [k for k in header_stack if k >= h_level]
                        for k in keys_to_remove:
                            del header_stack[k]
                        header_stack[h_level] = h_text
                        header_idx += 1
                    else:
                        break

                part_tokens = _count_tokens(part)
                if current_tokens + part_tokens <= MAX_TOKENS:
                    current.append(part)
                    current_tokens += part_tokens
                else:
                    if current:
                        chunk_text = "".join(current).strip()
                        if chunk_text:
                            breadcrumb = _build_header_breadcrumb(
                                header_stack, title
                            )
                            chunks.append(
                                Chunk(
                                    text=chunk_text,
                                    title=title,
                                    source_doc=source_doc,
                                    passage_id=passage_id,
                                    chunk_index=chunk_index,
                                    token_count=_count_tokens(chunk_text),
                                    context_header=breadcrumb,
                                )
                            )
                            chunk_index += 1

                            # Compute overlap
                            overlap_parts: list[str] = []
                            overlap_tok = 0
                            for prev_part in reversed(current):
                                pt = _count_tokens(prev_part)
                                if overlap_tok + pt <= OVERLAP_TOKENS:
                                    overlap_parts.insert(0, prev_part)
                                    overlap_tok += pt
                                else:
                                    break
                            current = overlap_parts + [part]
                            current_tokens = overlap_tok + part_tokens
                    else:
                        # Single part exceeds MAX_TOKENS — force it as a chunk
                        chunk_text = part.strip()
                        if chunk_text:
                            breadcrumb = _build_header_breadcrumb(
                                header_stack, title
                            )
                            chunks.append(
                                Chunk(
                                    text=chunk_text,
                                    title=title,
                                    source_doc=source_doc,
                                    passage_id=passage_id,
                                    chunk_index=chunk_index,
                                    token_count=_count_tokens(chunk_text),
                                    context_header=breadcrumb,
                                )
                            )
                            chunk_index += 1
                        current = []
                        current_tokens = 0

            # Flush remaining parts
            if current:
                chunk_text = "".join(current).strip()
                if chunk_text:
                    breadcrumb = _build_header_breadcrumb(header_stack, title)
                    chunks.append(
                        Chunk(
                            text=chunk_text,
                            title=title,
                            source_doc=source_doc,
                            passage_id=passage_id,
                            chunk_index=chunk_index,
                            token_count=_count_tokens(chunk_text),
                            context_header=breadcrumb,
                        )
                    )
                    chunk_index += 1
            remaining = ""
            split_done = True
            break

        if not split_done:
            chunk_text = remaining.strip()
            if chunk_text:
                breadcrumb = _build_header_breadcrumb(header_stack, title)
                chunks.append(
                    Chunk(
                        text=chunk_text,
                        title=title,
                        source_doc=source_doc,
                        passage_id=passage_id,
                        chunk_index=chunk_index,
                        token_count=_count_tokens(chunk_text),
                        context_header=breadcrumb,
                    )
                )
            remaining = ""

    return chunks if chunks else [
        Chunk(
            text=text,
            title=title,
            source_doc=source_doc,
            passage_id=passage_id,
            chunk_index=0,
            token_count=_count_tokens(text),
            context_header="",
        )
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/ingestion/tests/test_chunker.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/ingestion/chunker.py backend/ingestion/tests/test_chunker.py
git commit -m "feat(chunker): rewrite with context-aware splitting and header tracking"
```

---

### Task 2: Create the LLM Enrichment Module

**Files:**
- Create: `backend/ingestion/llm_enricher.py`
- Create: `backend/ingestion/tests/test_llm_enricher.py`

- [ ] **Step 1: Write failing tests for LLM enrichment**

Create `backend/ingestion/tests/test_llm_enricher.py`:

```python
"""Tests for LLM context enrichment with mocked OpenRouter API."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.ingestion.chunker import Chunk
from backend.ingestion.llm_enricher import (
    enrich_chunk,
    enrich_chunks_batch,
    ENRICHMENT_PROMPT_TEMPLATE,
    MAX_CONCURRENCY,
)


def _make_chunk(text: str = "Sample chunk text", context_header: str = "") -> Chunk:
    return Chunk(
        text=text,
        title="Test Policy",
        source_doc="test.pdf",
        passage_id="p1",
        chunk_index=0,
        token_count=10,
        context_header=context_header,
    )


class TestEnrichChunk:
    """Unit tests for single chunk enrichment."""

    @pytest.mark.asyncio
    async def test_enrich_prepends_llm_context(self):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="This chunk discusses data collection rules."))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        chunk = _make_chunk(text="We collect your email address.")
        result = await enrich_chunk(mock_client, chunk, full_passage="Full document text here.")

        assert result.llm_context == "This chunk discusses data collection rules."
        assert "This chunk discusses data collection rules." in result.enriched_text
        assert "We collect your email address." in result.enriched_text

    @pytest.mark.asyncio
    async def test_enrich_fallback_on_api_error(self):
        mock_client = AsyncMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        chunk = _make_chunk(text="We collect your email address.")
        result = await enrich_chunk(mock_client, chunk, full_passage="Full document text here.")

        # Should fallback gracefully — llm_context is empty, enriched_text still works
        assert result.llm_context == ""
        assert "We collect your email address." in result.enriched_text


class TestEnrichChunksBatch:
    """Tests for batch enrichment with concurrency control."""

    @pytest.mark.asyncio
    async def test_batch_enriches_all_chunks(self):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Context summary."))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        chunks = [_make_chunk(text=f"Chunk {i}") for i in range(5)]
        results = await enrich_chunks_batch(
            mock_client, chunks, full_passage="Full passage."
        )

        assert len(results) == 5
        for r in results:
            assert r.llm_context == "Context summary."

    @pytest.mark.asyncio
    async def test_batch_handles_partial_failures(self):
        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise Exception("Transient API failure")
            mock_resp = MagicMock()
            mock_resp.choices = [
                MagicMock(message=MagicMock(content="OK context."))
            ]
            return mock_resp

        mock_client = AsyncMock()
        mock_client.chat.completions.create.side_effect = side_effect

        chunks = [_make_chunk(text=f"Chunk {i}") for i in range(5)]
        results = await enrich_chunks_batch(
            mock_client, chunks, full_passage="Full passage."
        )

        assert len(results) == 5
        # The 3rd chunk (index 2) should have empty llm_context due to failure
        enriched_count = sum(1 for r in results if r.llm_context != "")
        assert enriched_count == 4  # 4 succeeded, 1 failed gracefully


class TestPromptTemplate:
    """The prompt template should contain required placeholders."""

    def test_template_has_required_placeholders(self):
        assert "{full_passage}" in ENRICHMENT_PROMPT_TEMPLATE
        assert "{chunk_text}" in ENRICHMENT_PROMPT_TEMPLATE


class TestConcurrencyLimit:
    """MAX_CONCURRENCY should be a reasonable value for OpenRouter free tier."""

    def test_max_concurrency_is_set(self):
        assert isinstance(MAX_CONCURRENCY, int)
        assert 1 <= MAX_CONCURRENCY <= 100
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/ingestion/tests/test_llm_enricher.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.ingestion.llm_enricher'`

- [ ] **Step 3: Implement `llm_enricher.py`**

Create `backend/ingestion/llm_enricher.py`:

```python
"""
backend/ingestion/llm_enricher.py
LLM-based semantic enrichment for chunks (Contextual Retrieval technique).
Calls OpenRouter LLM to generate a short standalone context for each chunk.
Graceful fallback: if the LLM call fails, the chunk is returned un-enriched.
"""
import asyncio
from copy import copy

from openai import AsyncOpenAI

from backend.ingestion.chunker import Chunk

# ── Configuration ─────────────────────────────────────────────────────────────
LLM_MODEL = "openai/gpt-oss-120b:free"
MAX_CONCURRENCY = 10       # async semaphore limit — respects OpenRouter free-tier
MAX_RETRIES = 3            # per-chunk retry limit
ENRICHMENT_TIMEOUT = 30    # seconds per LLM call

ENRICHMENT_PROMPT_TEMPLATE = """\
<document>
{full_passage}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{chunk_text}
</chunk>

Please give a short succinct context (1-2 sentences, under 30 words) to situate \
this chunk within the overall document for the purposes of improving search \
retrieval of the chunk. Answer ONLY with the context, nothing else."""


async def enrich_chunk(
    client: AsyncOpenAI,
    chunk: Chunk,
    full_passage: str,
    *,
    retries: int = MAX_RETRIES,
) -> Chunk:
    """
    Call LLM to generate standalone context for a single chunk.
    Returns a new Chunk with `llm_context` populated.
    On failure after retries, returns chunk with empty `llm_context` (graceful fallback).
    """
    prompt = ENRICHMENT_PROMPT_TEMPLATE.format(
        full_passage=full_passage,
        chunk_text=chunk.text,
    )

    for attempt in range(retries):
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=80,
                ),
                timeout=ENRICHMENT_TIMEOUT,
            )
            context = response.choices[0].message.content.strip()

            enriched = copy(chunk)
            enriched.llm_context = context
            return enriched

        except Exception as exc:
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(
                    f"[llm_enricher] Retry {attempt + 1}/{retries} for "
                    f"passage_id={chunk.passage_id} chunk={chunk.chunk_index}: {exc}"
                )
                await asyncio.sleep(wait)
            else:
                print(
                    f"[llm_enricher] FAILED after {retries} retries for "
                    f"passage_id={chunk.passage_id} chunk={chunk.chunk_index}: {exc}. "
                    "Using un-enriched chunk."
                )
                fallback = copy(chunk)
                fallback.llm_context = ""
                return fallback

    # Should not reach here, but safety net
    fallback = copy(chunk)
    fallback.llm_context = ""
    return fallback


async def enrich_chunks_batch(
    client: AsyncOpenAI,
    chunks: list[Chunk],
    full_passage: str,
) -> list[Chunk]:
    """
    Enrich all chunks concurrently with semaphore-based rate limiting.
    Returns enriched chunks in the same order as input.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async def _limited_enrich(chunk: Chunk) -> Chunk:
        async with semaphore:
            return await enrich_chunk(client, chunk, full_passage)

    tasks = [_limited_enrich(chunk) for chunk in chunks]
    return list(await asyncio.gather(*tasks))
```

- [ ] **Step 4: Run all tests to verify they pass**

Run: `python -m pytest backend/ingestion/tests/test_chunker.py backend/ingestion/tests/test_llm_enricher.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/ingestion/llm_enricher.py backend/ingestion/tests/test_llm_enricher.py backend/ingestion/chunker.py backend/ingestion/tests/test_chunker.py
git commit -m "feat(enricher): add LLM semantic enrichment module with concurrency control"
```

---

### Task 3: Wire Enrichment into Bulk Ingestion (`ingest.py`)

**Files:**
- Modify: `backend/ingestion/ingest.py`

- [ ] **Step 1: Add import for `enrich_chunks_batch`**

At the top of `backend/ingestion/ingest.py`, add after line 24:

```python
from backend.ingestion.llm_enricher import enrich_chunks_batch
```

- [ ] **Step 2: Update `MAX_TOKENS_WARN` to match new `MAX_TOKENS`**

In `backend/ingestion/ingest.py`, line 30, change:

```python
MAX_TOKENS_WARN = 400        # C6 guard: warn before embedding over-long passages
```

to:

```python
MAX_TOKENS_WARN = 350        # C6 guard: aligned with chunker MAX_TOKENS (Nemotron safety buffer)
```

- [ ] **Step 3: Update the work queue to store full passage text**

Replace the work queue type and loop (lines 277-301):

```python
    # 6. Build work queue with deduplication
    work_queue: list[tuple[Chunk, str, str]] = []  # (chunk, sha256_hash, full_passage)
    seen_hashes: set[str] = set()
    token_warnings = 0

    for record in passages:
        chunks = chunk_passage(
            text=record.context,
            passage_id=str(record.id),
            title=record.title,
            source_doc=record.title,
        )
        for chunk in chunks:
            text_hash = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()

            # C6 token count guard — warn if passage exceeds MAX_TOKENS_WARN
            if _count_tokens(chunk.text) > MAX_TOKENS_WARN:
                print(f"[warn] Token count > {MAX_TOKENS_WARN} for passage_id={chunk.passage_id} chunk_index={chunk.chunk_index}")
                token_warnings += 1

            # Skip checkpoint-completed and intra-run duplicates (D-02, D-03)
            if text_hash in completed_hashes or text_hash in seen_hashes:
                continue

            seen_hashes.add(text_hash)
            work_queue.append((chunk, text_hash, record.context))
```

- [ ] **Step 4: Add LLM enrichment step before embedding in the batch loop**

Replace the batch loop (lines 307-364):

```python
    # 7. Batch embed → enrich → upsert → checkpoint
    upserted = 0
    for batch_num, batch_start in enumerate(range(0, total, BATCH_SIZE), start=1):
        batch = work_queue[batch_start: batch_start + BATCH_SIZE]
        chunks_in_batch = [c for c, _, _ in batch]
        hashes_in_batch = [h for _, h, _ in batch]

        # LLM enrichment — enrich each chunk with its full passage context
        enriched_chunks: list[Chunk] = []
        # Group chunks by passage for efficient enrichment
        passage_groups: dict[str, list[Chunk]] = {}
        for chunk, _hash, passage in batch:
            if passage not in passage_groups:
                passage_groups[passage] = []
            passage_groups[passage].append(chunk)

        for passage_text, group_chunks in passage_groups.items():
            enriched = await enrich_chunks_batch(openrouter, group_chunks, passage_text)
            enriched_chunks.extend(enriched)

        # Use enriched_text for embedding (includes context_header + llm_context + text)
        embeddings = await embed_batch([c.enriched_text for c in enriched_chunks])

        points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{c.passage_id}:{c.chunk_index}")),
                vector=embedding,
                payload={
                    "title": c.title,
                    "source_doc": c.source_doc,
                    "passage_id": c.passage_id,
                    "text": c.text,
                    "chunk_index": c.chunk_index,
                    "token_count": c.token_count,
                    "context_header": c.context_header,
                    "llm_context": c.llm_context,
                    "enriched_text": c.enriched_text,
                },
            )
            for c, embedding in zip(enriched_chunks, embeddings)
        ]

        # Extract graphs in parallel for the batch
        print(f"[ingest] Extracting graphs for {len(enriched_chunks)} chunks...")
        graph_tasks = [extract_graph_from_chunk(c.text) for c in enriched_chunks]
        graphs = await asyncio.gather(*graph_tasks)

        neo4j_client = Neo4jClient()
        for chunk, point, graph in zip(enriched_chunks, points, graphs):
            upsert_graph_to_neo4j(
                chunk_id=point.id,
                chunk_text=chunk.text,
                passage_id=chunk.passage_id,
                graph=graph,
                neo4j_client=neo4j_client
            )

        result = await upsert_batch(points, batch_num)

        # Upsert failure hard stop (AI-SPEC §6 guardrail)
        if result.status != UpdateStatus.COMPLETED:
            raise RuntimeError(
                f"[ingest] Upsert batch {batch_num} failed with status={result.status}. "
                "Checkpoint saved up to previous batch — re-run to resume."
            )

        # Update checkpoint AFTER confirmed write (D-03)
        completed_hashes.update(hashes_in_batch)
        save_checkpoint(completed_hashes)
        upserted += len(batch)

        print(f"[ingest] Batch {batch_num}: {upserted}/{total} upserted.")

        # Rate-limit politeness delay (M7)
        await asyncio.sleep(BATCH_SLEEP_SECONDS)
```

- [ ] **Step 5: Commit**

```bash
git add backend/ingestion/ingest.py
git commit -m "feat(ingest): wire LLM enrichment into bulk ingestion pipeline"
```

---

### Task 4: Wire Enrichment into Single-Document Ingestion (`ingest_doc.py`)

**Files:**
- Modify: `backend/ingestion/ingest_doc.py`

- [ ] **Step 1: Add import for `enrich_chunks_batch`**

At the top of `backend/ingestion/ingest_doc.py`, add after line 25:

```python
from backend.ingestion.llm_enricher import enrich_chunks_batch
```

- [ ] **Step 2: Update `ingest_doc()` to enrich chunks before embedding**

After the filtering step (line 269), replace lines 282-339 with:

```python
        if not new_pairs:
            print("[ingest_doc] All chunks already indexed — nothing to do.")
            if db_session._session_factory:
                async with db_session._session_factory() as session:
                    result = await session.execute(select(Document).where(Document.title == title))
                    doc_record = result.scalars().first()
                    if doc_record:
                        doc_record.status = "completed"
                        await session.commit()
            return

        # 10. Enrich chunks with LLM context
        print(f"[ingest_doc] Enriching {len(new_pairs)} chunks with LLM context...")
        new_chunks_only = [c for c, _ in new_pairs]
        enriched_chunks = await enrich_chunks_batch(openrouter, new_chunks_only, text)
        enriched_pairs = list(zip(enriched_chunks, [uid for _, uid in new_pairs]))

        # 11. Batch embed and upsert
        total = len(enriched_pairs)
        for batch_start in range(0, total, BATCH_SIZE):
            batch = enriched_pairs[batch_start: batch_start + BATCH_SIZE]
            chunks_in_batch = [c for c, _ in batch]
            ids_in_batch = [uid for _, uid in batch]

            # Use enriched_text for embedding
            embeddings = await embed_batch(openrouter, [c.enriched_text for c in chunks_in_batch])

            points = [
                PointStruct(
                    id=uid,
                    vector=embedding,
                    payload={
                        "title": title,
                        "source_doc": title,
                        "passage_id": chunk.passage_id,
                        "text": chunk.text,
                        "chunk_index": chunk.chunk_index,
                        "token_count": chunk.token_count,
                        "context_header": chunk.context_header,
                        "llm_context": chunk.llm_context,
                        "enriched_text": chunk.enriched_text,
                        "file_type": file_type,
                    },
                )
                for chunk, uid, embedding in zip(chunks_in_batch, ids_in_batch, embeddings)
            ]

            result = await qdrant.upsert(
                collection_name=COLLECTION_NAME,
                points=points,
                wait=True,
            )

            if result.status != UpdateStatus.COMPLETED:
                raise RuntimeError(
                    f"[ingest_doc] Upsert failed with status={result.status}. "
                    "Re-run to retry failed batch."
                )

            if batch_start + BATCH_SIZE < total:
                await asyncio.sleep(BATCH_SLEEP_SECONDS)

        print(
            f"[ingest_doc] Done. Upserted {len(enriched_pairs)} new chunks "
            f"({len(existing)} skipped — already indexed)."
        )
```

- [ ] **Step 3: Commit**

```bash
git add backend/ingestion/ingest_doc.py
git commit -m "feat(ingest_doc): wire LLM enrichment into single-document pipeline"
```

---

### Task 5: Wire Enrichment into Inline Document Processor

**Files:**
- Modify: `backend/app/services/document_processor.py`

- [ ] **Step 1: Add import for `enrich_chunks_batch`**

At the top of `backend/app/services/document_processor.py`, add after line 16:

```python
from backend.ingestion.llm_enricher import enrich_chunks_batch
```

- [ ] **Step 2: Update `process_document_inline()` to enrich chunks**

In `process_document_inline()`, replace the embedding section (lines 61-117) with:

```python
        # Step 3: LLM Enrichment
        await _update_status(document_id, "enriching_chunks")
        enriched_chunks = await enrich_chunks_batch(openrouter, chunks, text)

        # Step 4: Embedding and Upserting (Batched)
        await _update_status(document_id, "embedding_and_saving")
        neo4j = Neo4jClient()
        points = []

        BATCH_SIZE = 50
        total = len(enriched_chunks)

        for batch_start in range(0, total, BATCH_SIZE):
            batch_chunks = enriched_chunks[batch_start: batch_start + BATCH_SIZE]

            # Use enriched_text for embedding
            embeddings = await embed_batch(openrouter, [c.enriched_text for c in batch_chunks])

            for chunk, embedding in zip(batch_chunks, embeddings):
                point_id = str(uuid4())
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "title": title,
                            "source_doc": title,
                            "passage_id": passage_id,
                            "text": chunk.text,
                            "chunk_index": chunk.chunk_index,
                            "token_count": chunk.token_count,
                            "context_header": chunk.context_header,
                            "llm_context": chunk.llm_context,
                            "enriched_text": chunk.enriched_text,
                            "document_id": document_id,
                            "user_id": str(user_id)
                        }
                    )
                )

                query = """
                MERGE (d:Document {id: $doc_id, title: $title})
                MERGE (c:Chunk {id: $chunk_id, user_id: $user_id})
                SET c.text = $text
                MERGE (d)-[:HAS_CHUNK]->(c)
                """
                await run_in_threadpool(
                    neo4j.execute_query,
                    query,
                    {
                        "doc_id": document_id,
                        "title": title,
                        "chunk_id": point_id,
                        "text": chunk.text,
                        "user_id": str(user_id)
                    }
                )

        if points:
            await qdrant.upsert(
                collection_name=COLLECTION_NAME,
                points=points
            )
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/document_processor.py
git commit -m "feat(document_processor): wire LLM enrichment into inline processing"
```

---

### Task 6: Final Integration Test & Verification

**Files:**
- No new files — run existing tests

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest backend/ingestion/tests/ -v`
Expected: All tests PASS. Existing tests in `test_ingest_doc.py` and `test_ingestion_evals.py` should still pass since the `Chunk` dataclass is backward-compatible (new fields have defaults).

- [ ] **Step 2: Run a quick import smoke test**

Run: `python -c "from backend.ingestion.chunker import Chunk, chunk_passage; from backend.ingestion.llm_enricher import enrich_chunks_batch; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 3: Commit any remaining fixes**

```bash
git add -A
git commit -m "test: verify full integration of chunking overhaul"
```

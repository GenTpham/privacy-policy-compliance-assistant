"""
backend/app/tests/test_rag.py
Unit tests for backend/app/services/rag.py.

Fast tests (pure functions, no API): test_system_prompt_abstain_wording,
    test_history_sliced_to_6, test_citations_have_title_and_text,
    test_done_event_shape, test_fabricated_citation_stripped
Mock tests (mocked clients):        test_embed_calls_correct_model,
    test_retrieve_params, test_no_results_early_return,
    test_prompt_contains_numbered_chunks, test_delta_before_done

Run unit tests: pytest backend/app/tests/test_rag.py -x -v
Run one test:   pytest backend/app/tests/test_rag.py::test_fabricated_citation_stripped -x
"""
import pytest


# ── RAG-01: embed calls correct model ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_embed_calls_correct_model(mock_openrouter, mock_qdrant):
    """RAG-01: embeddings.create called with model='nvidia/llama-nemotron-embed-vl-1b-v2'."""
    pytest.skip("stub — implemented in Wave 1")


# ── RAG-02: retrieve params ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retrieve_params(mock_openrouter, mock_qdrant):
    """RAG-02: qdrant.search called with limit=5, score_threshold=0.55, with_payload=True."""
    pytest.skip("stub — implemented in Wave 1")


# ── RAG-03: prompt contains numbered chunks ────────────────────────────────────

@pytest.mark.asyncio
async def test_prompt_contains_numbered_chunks(mock_openrouter, mock_qdrant, sample_scored_point):
    """RAG-03: system message contains '[1] source:' formatted numbered chunk."""
    pytest.skip("stub — implemented in Wave 1")


# ── RAG-04: abstain wording in system prompt ──────────────────────────────────

def test_system_prompt_abstain_wording(sample_scored_point):
    """
    RAG-04: _build_messages system content contains the exact D-05 abstain instruction.
    Pure function test — no mocks needed.
    """
    pytest.skip("stub — implemented in Wave 1")


# ── RAG-05: delta events arrive before done ───────────────────────────────────

@pytest.mark.asyncio
async def test_delta_before_done(mock_openrouter, mock_qdrant, sample_scored_point):
    """RAG-05: at least one delta event is yielded before the done event."""
    pytest.skip("stub — implemented in Wave 1")


# ── RAG-06: history sliced to last 6 messages ────────────────────────────────

def test_history_sliced_to_6(sample_scored_point):
    """
    RAG-06: _build_messages includes at most 6 history messages (3 turns) before user message.
    Pure function test — system(1) + history(6) + user(1) = 8 messages max.
    """
    pytest.skip("stub — implemented in Wave 1")


# ── RAG-07: no LLM call on empty retrieval ───────────────────────────────────

@pytest.mark.asyncio
async def test_no_results_early_return(mock_openrouter, mock_qdrant):
    """
    RAG-07 + D-14: when qdrant.search returns [], stream_answer yields a done event
    with answer='No matching policy found for your question.' and never calls LLM.
    """
    pytest.skip("stub — implemented in Wave 1")


# ── CITE-01: citations contain title and text ────────────────────────────────

def test_citations_have_title_and_text(sample_scored_point):
    """
    CITE-01: _build_verified_citations returns dicts with non-empty 'title' and 'text' fields.
    Pure function test.
    """
    pytest.skip("stub — implemented in Wave 1")


# ── CITE-02: done event shape ─────────────────────────────────────────────────

def test_done_event_shape(sample_scored_point):
    """
    CITE-02: done event has shape {type: 'done', answer: str, citations: [{id, qdrant_id, title, text}]}.
    Pure function test using _build_verified_citations directly.
    """
    pytest.skip("stub — implemented in Wave 1")


# ── CITE-03: fabricated citation stripped ────────────────────────────────────

def test_fabricated_citation_stripped(sample_scored_point):
    """
    CITE-03 + D-07: _build_verified_citations strips [N] where N > len(retrieved).
    Answer references [1] (valid) and [3] (fabricated — only 1 chunk). [3] must not appear in output.
    Pure function test.
    """
    pytest.skip("stub — implemented in Wave 1")

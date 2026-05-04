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
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.services.rag import (
    _build_messages,
    _build_verified_citations,
    stream_answer,
    _build_conflict_messages,
    stream_conflict_answer,
)
from backend.app.services import rag
from backend.app.core.config import get_settings


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _fake_stream(token: str):
    """Async generator simulating one real token then a final None-content chunk."""
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = token
    yield chunk
    # Final chunk with None content (stop reason)
    final = MagicMock()
    final.choices = [MagicMock()]
    final.choices[0].delta.content = None
    yield final


# ── RAG-01: embed calls correct model ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_embed_calls_correct_model(mock_openrouter, mock_qdrant):
    """RAG-01: embeddings.create called with model='nvidia/llama-nemotron-embed-vl-1b-v2'."""
    with patch.object(rag, "openrouter", mock_openrouter), \
         patch.object(rag, "qdrant", mock_qdrant):
        events = [e async for e in stream_answer("test query", [])]

    mock_openrouter.embeddings.create.assert_called_once()
    call_args = mock_openrouter.embeddings.create.call_args
    # model is always passed as keyword argument in stream_answer
    model_arg = call_args.kwargs.get("model")
    assert model_arg == "nvidia/llama-nemotron-embed-vl-1b-v2"


# ── RAG-02: retrieve params ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retrieve_params(mock_openrouter, mock_qdrant):
    """RAG-02: qdrant.search called with limit=5, score_threshold=get_settings().score_threshold, with_payload=True."""
    with patch.object(rag, "openrouter", mock_openrouter), \
         patch.object(rag, "qdrant", mock_qdrant):
        events = [e async for e in stream_answer("test query", [])]

    mock_qdrant.query_points.assert_called_once()
    call_kwargs = mock_qdrant.query_points.call_args.kwargs
    assert call_kwargs.get("limit") == 5
    assert call_kwargs.get("score_threshold") == get_settings().score_threshold
    assert call_kwargs.get("with_payload") is True


# ── RAG-03: prompt contains numbered chunks ────────────────────────────────────

@pytest.mark.asyncio
async def test_prompt_contains_numbered_chunks(mock_openrouter, mock_qdrant, sample_scored_point):
    """RAG-03: system message contains '[1] source:' formatted numbered chunk."""
    mock_resp = MagicMock(); mock_resp.points = [sample_scored_point]
    mock_qdrant.query_points = AsyncMock(return_value=mock_resp)
    mock_openrouter.chat.completions.create = AsyncMock(return_value=_fake_stream("answer"))

    with patch.object(rag, "openrouter", mock_openrouter), \
         patch.object(rag, "qdrant", mock_qdrant):
        events = [e async for e in stream_answer("test query", [])]

    # Inspect the messages passed to chat.completions.create
    chat_call_kwargs = mock_openrouter.chat.completions.create.call_args.kwargs
    messages = chat_call_kwargs["messages"]
    system_content = messages[0]["content"]
    assert "[1] source: Privacy Policy v2" in system_content


# ── RAG-04: abstain wording in system prompt ──────────────────────────────────

def test_system_prompt_abstain_wording(sample_scored_point):
    """
    RAG-04: _build_messages system content contains the exact D-05 abstain instruction.
    Pure function test — no mocks needed.
    """
    messages = _build_messages("test question", [sample_scored_point], [])
    system_content = messages[0]["content"]
    assert "The provided policies do not contain sufficient information to answer this question." in system_content
    assert "Do not infer, guess, or use outside knowledge." in system_content


# ── RAG-05: delta events arrive before done ───────────────────────────────────

@pytest.mark.asyncio
async def test_delta_before_done(mock_openrouter, mock_qdrant, sample_scored_point):
    """RAG-05: at least one delta event is yielded before the done event."""
    mock_resp = MagicMock(); mock_resp.points = [sample_scored_point]
    mock_qdrant.query_points = AsyncMock(return_value=mock_resp)
    mock_openrouter.chat.completions.create = AsyncMock(return_value=_fake_stream("Hello"))

    with patch.object(rag, "openrouter", mock_openrouter), \
         patch.object(rag, "qdrant", mock_qdrant):
        events = [e async for e in stream_answer("test query", [])]

    assert any(e["type"] == "delta" for e in events)
    assert events[-1]["type"] == "done"
    # Delta must appear before done
    delta_idx = next(i for i, e in enumerate(events) if e["type"] == "delta")
    done_idx = next(i for i, e in enumerate(events) if e["type"] == "done")
    assert delta_idx < done_idx


# ── RAG-06: history sliced to last 6 messages ────────────────────────────────

def test_history_sliced_to_6(sample_scored_point):
    """
    RAG-06: _build_messages includes at most 6 history messages (3 turns) before user message.
    Pure function test — system(1) + history(6) + user(1) = 8 messages max.
    """
    long_history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"message {i}"}
        for i in range(20)
    ]
    messages = _build_messages("new question", [sample_scored_point], long_history)
    assert len(messages) == 8
    assert messages[0]["role"] == "system"
    assert messages[-1]["content"] == "new question"


# ── RAG-07: no LLM call on empty retrieval ───────────────────────────────────

@pytest.mark.asyncio
async def test_no_results_early_return(mock_openrouter, mock_qdrant):
    """
    RAG-07 + D-14: when qdrant.search returns [], stream_answer yields a done event
    with answer='No matching policy found for your question.' and never calls LLM.
    """
    # mock_qdrant.search already returns [] by default from conftest
    with patch.object(rag, "openrouter", mock_openrouter), \
         patch.object(rag, "qdrant", mock_qdrant):
        events = [e async for e in stream_answer("test query", [])]

    assert events[-1]["type"] == "done"
    assert "No matching policy" in events[-1]["answer"]
    mock_openrouter.chat.completions.create.assert_not_called()


# ── CITE-01: citations contain title and text ────────────────────────────────

def test_citations_have_title_and_text(sample_scored_point):
    """
    CITE-01: _build_verified_citations returns dicts with non-empty 'title' and 'text' fields.
    Pure function test.
    """
    citations = _build_verified_citations("[1]", [sample_scored_point])
    assert len(citations) == 1
    assert citations[0]["title"] == "Privacy Policy v2"
    assert citations[0]["text"] == "Personal data must be retained no longer than 30 days."


# ── CITE-02: done event shape ─────────────────────────────────────────────────

def test_done_event_shape(sample_scored_point):
    """
    CITE-02: done event has shape {type: 'done', answer: str, citations: [{id, qdrant_id, title, text}]}.
    Pure function test using _build_verified_citations directly.
    """
    citations = _build_verified_citations("[1]", [sample_scored_point])
    assert len(citations) == 1
    result = citations[0]
    assert set(result.keys()) >= {"id", "qdrant_id", "title", "text"}
    assert result["id"] == 1


# ── CITE-03: fabricated citation stripped ────────────────────────────────────

def test_fabricated_citation_stripped(sample_scored_point):
    """
    CITE-03 + D-07: _build_verified_citations strips [N] where N > len(retrieved).
    Answer references [1] (valid) and [3] (fabricated — only 1 chunk). [3] must not appear in output.
    Pure function test.
    """
    citations = _build_verified_citations("Per [1], data retained. See also [3].", [sample_scored_point])
    ids = [c["id"] for c in citations]
    assert 1 in ids
    assert 3 not in ids


# ── CONFLICT-02: conflict retrieval uses limit=10 ────────────────────────────

@pytest.mark.asyncio
async def test_conflict_retrieve_params(mock_openrouter, mock_qdrant, sample_scored_points_multi):
    """CONFLICT-02: stream_conflict_answer calls query_points with limit=10, score_threshold=get_settings().score_threshold, with_payload=True."""
    mock_resp = MagicMock()
    mock_resp.points = sample_scored_points_multi
    mock_qdrant.query_points = AsyncMock(return_value=mock_resp)
    mock_openrouter.chat.completions.create = AsyncMock(return_value=_fake_stream("answer"))

    with patch.object(rag, "openrouter", mock_openrouter), \
         patch.object(rag, "qdrant", mock_qdrant):
        events = [e async for e in stream_conflict_answer("mâu thuẫn về dữ liệu", [])]

    mock_qdrant.query_points.assert_called_once()
    call_kwargs = mock_qdrant.query_points.call_args.kwargs
    assert call_kwargs.get("limit") == 10
    assert call_kwargs.get("score_threshold") == get_settings().score_threshold
    assert call_kwargs.get("with_payload") is True


# ── CONFLICT-03: conflict prompt contains verdict format ─────────────────────

def test_conflict_prompt_contains_verdict_format(sample_scored_points_multi):
    """CONFLICT-03: _build_conflict_messages system content contains 'Verdict:' instruction per D-11."""
    messages = _build_conflict_messages("so sánh hai tài liệu", sample_scored_points_multi, [])
    system_content = messages[0]["content"]
    assert "Verdict:" in system_content
    assert "<classification>" in system_content or "Contradictory" in system_content


def test_conflict_prompt_contains_classifications(sample_scored_points_multi):
    """CONFLICT-03: _build_conflict_messages system content contains all three classification terms per D-12."""
    messages = _build_conflict_messages("khác nhau giữa hai chính sách", sample_scored_points_multi, [])
    system_content = messages[0]["content"]
    assert "Contradictory" in system_content
    assert "Consistent" in system_content
    assert "One-Silent" in system_content


def test_conflict_prompt_abstain_wording(sample_scored_points_multi):
    """CONFLICT-03: _build_conflict_messages retains ABSTAIN_INSTRUCTION text per D-13."""
    messages = _build_conflict_messages("conflict on retention", sample_scored_points_multi, [])
    system_content = messages[0]["content"]
    assert "The provided policies do not contain sufficient information to answer this question." in system_content
    assert "Do not infer, guess, or use outside knowledge." in system_content


# ── CONFLICT-04: conflict done event shape unchanged ─────────────────────────

@pytest.mark.asyncio
async def test_conflict_done_event_shape(mock_openrouter, mock_qdrant, sample_scored_points_multi):
    """CONFLICT-04: done event from stream_conflict_answer has identical shape to standard path (D-14)."""
    mock_resp = MagicMock()
    mock_resp.points = sample_scored_points_multi
    mock_qdrant.query_points = AsyncMock(return_value=mock_resp)
    mock_openrouter.chat.completions.create = AsyncMock(
        return_value=_fake_stream("Policy A says [1]. Policy B says [2].")
    )

    with patch.object(rag, "openrouter", mock_openrouter), \
         patch.object(rag, "qdrant", mock_qdrant):
        events = [e async for e in stream_conflict_answer("differ in retention", [])]

    done = events[-1]
    assert done["type"] == "done"
    assert isinstance(done["answer"], str)
    assert isinstance(done["citations"], list)
    if done["citations"]:
        c = done["citations"][0]
        assert set(c.keys()) >= {"id", "qdrant_id", "title", "text"}


# ── CONFLICT-03 / Pitfall 3: history slice identical to standard path ─────────

def test_conflict_history_sliced_to_6(sample_scored_points_multi):
    """
    CONFLICT-03 / Pitfall 3: _build_conflict_messages produces at most 8 messages
    (system + 6 history + user) when history is longer than 6 items.
    Ensures conflict path uses same slicing as standard path.
    """
    long_history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"message {i}"}
        for i in range(20)
    ]
    messages = _build_conflict_messages("conflict query", sample_scored_points_multi, long_history)
    assert len(messages) == 8
    assert messages[0]["role"] == "system"
    assert messages[-1]["content"] == "conflict query"

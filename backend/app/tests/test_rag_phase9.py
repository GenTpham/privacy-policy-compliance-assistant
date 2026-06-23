"""
backend/app/tests/test_rag_phase9.py
Phase 9 Plan 01 unit tests for rag.py additions:
  - get_distinct_sources() uses facet API
  - stream_answer / stream_conflict_answer gain source_filter param + query_filter pass-through
  - All citation dicts include "score" field

Run: pytest backend/app/tests/test_rag_phase9.py -x -v
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.services import rag
from backend.app.services.rag import (
    _build_verified_citations,
    stream_answer,
    stream_conflict_answer,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_extract_entities():
    with patch("backend.app.services.rag.extract_entities_from_query", new_callable=AsyncMock, return_value=["test_entity"]) as mock:
        yield mock

@pytest.fixture(autouse=True)
def mock_search_graph():
    with patch("backend.app.services.rag.retrieve_graph_context", return_value=["graph text"]) as mock:
        yield mock

async def _fake_stream(token: str):
    """Async generator simulating one real token then a None-content final chunk."""
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = token
    yield chunk
    final = MagicMock()
    final.choices = [MagicMock()]
    final.choices[0].delta.content = None
    yield final


# ── get_distinct_sources ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_distinct_sources_calls_facet(mock_qdrant):
    """get_distinct_sources must call qdrant.facet with key='title' and limit=200."""
    # Arrange: mock facet response with two title hits
    hit1 = MagicMock()
    hit1.value = "Policy B"
    hit2 = MagicMock()
    hit2.value = "Policy A"
    facet_resp = MagicMock()
    facet_resp.hits = [hit1, hit2]
    mock_qdrant.facet = AsyncMock(return_value=facet_resp)

    with patch.object(rag, "qdrant", mock_qdrant):
        result = await rag.get_distinct_sources()

    mock_qdrant.facet.assert_called_once()
    call_kwargs = mock_qdrant.facet.call_args.kwargs
    assert call_kwargs.get("key") == "title"
    assert call_kwargs.get("limit") == 200


@pytest.mark.asyncio
async def test_get_distinct_sources_returns_sorted(mock_qdrant):
    """get_distinct_sources must return sorted list of title strings."""
    hit1 = MagicMock(); hit1.value = "Zebra Policy"
    hit2 = MagicMock(); hit2.value = "Alpha Policy"
    hit3 = MagicMock(); hit3.value = "Mango Policy"
    facet_resp = MagicMock()
    facet_resp.hits = [hit1, hit2, hit3]
    mock_qdrant.facet = AsyncMock(return_value=facet_resp)

    with patch.object(rag, "qdrant", mock_qdrant):
        result = await rag.get_distinct_sources()

    assert result == ["Alpha Policy", "Mango Policy", "Zebra Policy"]


# ── source_filter param on stream_answer ─────────────────────────────────────

@pytest.mark.asyncio
async def test_stream_answer_no_filter_passes_none_to_query_points(mock_openrouter, mock_qdrant):
    """stream_answer(source_filter=None) passes query_filter=None to query_points."""
    with patch.object(rag, "openrouter", mock_openrouter), \
         patch.object(rag, "llm_client", mock_openrouter), \
         patch.object(rag, "qdrant", mock_qdrant):
        events = [e async for e in stream_answer("test query", [], source_filter=None)]

    call_kwargs = mock_qdrant.query_points.call_args.kwargs
    assert call_kwargs.get("query_filter") is None


@pytest.mark.asyncio
async def test_stream_answer_with_filter_passes_filter_object(mock_openrouter, mock_qdrant, sample_scored_point):
    """stream_answer(source_filter='Google') passes a Qdrant Filter to query_points."""
    from qdrant_client.models import Filter
    mock_resp = MagicMock()
    mock_resp.points = [sample_scored_point]
    mock_qdrant.query_points = AsyncMock(return_value=mock_resp)
    mock_openrouter.chat.completions.create = AsyncMock(return_value=_fake_stream("[1]"))

    with patch.object(rag, "openrouter", mock_openrouter), \
         patch.object(rag, "llm_client", mock_openrouter), \
         patch.object(rag, "qdrant", mock_qdrant):
        events = [e async for e in stream_answer("test", [], source_filter="Google Privacy Policy")]

    call_kwargs = mock_qdrant.query_points.call_args.kwargs
    assert isinstance(call_kwargs.get("query_filter"), Filter)


@pytest.mark.asyncio
async def test_stream_answer_empty_string_filter_treated_as_falsy(mock_openrouter, mock_qdrant):
    """stream_answer(source_filter='') treats empty string as falsy — no filter applied."""
    with patch.object(rag, "openrouter", mock_openrouter), \
         patch.object(rag, "llm_client", mock_openrouter), \
         patch.object(rag, "qdrant", mock_qdrant):
        events = [e async for e in stream_answer("test query", [], source_filter="")]

    call_kwargs = mock_qdrant.query_points.call_args.kwargs
    assert call_kwargs.get("query_filter") is None


# ── source_filter param on stream_conflict_answer ────────────────────────────

@pytest.mark.asyncio
async def test_stream_conflict_answer_no_filter_passes_none(mock_openrouter, mock_qdrant):
    """stream_conflict_answer(source_filter=None) passes query_filter=None to query_points."""
    with patch.object(rag, "openrouter", mock_openrouter), \
         patch.object(rag, "llm_client", mock_openrouter), \
         patch.object(rag, "qdrant", mock_qdrant):
        events = [e async for e in stream_conflict_answer("conflict", [], source_filter=None)]

    call_kwargs = mock_qdrant.query_points.call_args.kwargs
    assert call_kwargs.get("query_filter") is None


@pytest.mark.asyncio
async def test_stream_conflict_answer_with_filter_passes_filter_object(mock_openrouter, mock_qdrant, sample_scored_points_multi):
    """stream_conflict_answer(source_filter='X') passes a Qdrant Filter to query_points."""
    from qdrant_client.models import Filter
    mock_resp = MagicMock()
    mock_resp.points = sample_scored_points_multi
    mock_qdrant.query_points = AsyncMock(return_value=mock_resp)
    mock_openrouter.chat.completions.create = AsyncMock(return_value=_fake_stream("[1] [2]"))

    with patch.object(rag, "openrouter", mock_openrouter), \
         patch.object(rag, "llm_client", mock_openrouter), \
         patch.object(rag, "qdrant", mock_qdrant):
        events = [e async for e in stream_conflict_answer("conflict", [], source_filter="X Policy")]

    call_kwargs = mock_qdrant.query_points.call_args.kwargs
    assert isinstance(call_kwargs.get("query_filter"), Filter)


# ── score field in citation dicts ─────────────────────────────────────────────

def test_build_verified_citations_includes_score(sample_scored_point):
    """_build_verified_citations must include 'score' field rounded to 4 decimal places."""
    citations = _build_verified_citations("[1]", [sample_scored_point])
    assert len(citations) == 1
    assert "score" in citations[0]
    assert citations[0]["score"] == round(sample_scored_point.score, 4)


@pytest.mark.asyncio
async def test_abstain_fallback_stream_answer_includes_score(mock_openrouter, mock_qdrant, sample_scored_point):
    """Abstain fallback in stream_answer (no [N] refs) must include 'score' in citation dicts."""
    mock_resp = MagicMock()
    mock_resp.points = [sample_scored_point]
    mock_qdrant.query_points = AsyncMock(return_value=mock_resp)
    # LLM returns no [N] citation references — triggers abstain fallback
    mock_openrouter.chat.completions.create = AsyncMock(return_value=_fake_stream("I cannot answer."))

    with patch.object(rag, "openrouter", mock_openrouter), \
         patch.object(rag, "llm_client", mock_openrouter), \
         patch.object(rag, "qdrant", mock_qdrant):
        events = [e async for e in stream_answer("test", [])]

    done = events[-1]
    assert done["type"] == "done"
    assert done["citations"], "Abstain fallback should have citations"
    assert "score" in done["citations"][0]
    assert done["citations"][0]["score"] == round(sample_scored_point.score, 4)


@pytest.mark.asyncio
async def test_abstain_fallback_stream_conflict_includes_score(mock_openrouter, mock_qdrant, sample_scored_points_multi):
    """Abstain fallback in stream_conflict_answer must include 'score' in citation dicts."""
    mock_resp = MagicMock()
    mock_resp.points = sample_scored_points_multi
    mock_qdrant.query_points = AsyncMock(return_value=mock_resp)
    # LLM returns no [N] citation references — triggers abstain fallback
    mock_openrouter.chat.completions.create = AsyncMock(return_value=_fake_stream("I cannot answer."))

    with patch.object(rag, "openrouter", mock_openrouter), \
         patch.object(rag, "llm_client", mock_openrouter), \
         patch.object(rag, "qdrant", mock_qdrant):
        events = [e async for e in stream_conflict_answer("conflict", [])]

    done = events[-1]
    assert done["type"] == "done"
    assert done["citations"], "Abstain fallback should have citations"
    assert "score" in done["citations"][0]
    assert done["citations"][0]["score"] == round(sample_scored_points_multi[0].score, 4)

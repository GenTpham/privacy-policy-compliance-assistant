"""
backend/app/services/rag.py
Core RAG pipeline: embed → retrieve → stream → verify citations.
Async generator — yields delta events then a final done event.
No HTTP concerns here (see backend/app/api/chat.py for the router).
"""
import logging
import re
from collections.abc import AsyncGenerator
from contextlib import nullcontext

from openai import AsyncOpenAI
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

from backend.app.core.config import get_settings
from backend.app.core.qdrant_client import make_qdrant_client
from backend.app.services.graph_search import extract_entities_from_query, retrieve_graph_context

# OTel tracer — None when opentelemetry-sdk is not installed (safe fallback)
try:
    from opentelemetry import trace as _otel_trace
    _tracer = _otel_trace.get_tracer(__name__)
except ImportError:
    _tracer = None

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
COLLECTION_NAME = "policies"
EMBEDDING_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2:free"

# D-05: Hard abstain instruction — exact wording locked in CONTEXT.md
ABSTAIN_INSTRUCTION = (
    "If the provided passages do not contain the answer, respond: "
    "'The provided policies do not contain sufficient information to answer this question.' "
    "Do not infer, guess, or use outside knowledge."
)

# ── Module-level client singletons ─────────────────────────────────────────────
# Initialized once per process from get_settings() — consistent with ingest.py pattern.
# For testing: patch "backend.app.services.rag.openrouter" and "backend.app.services.rag.qdrant".
_settings = get_settings()

if _settings.llm_backend.lower() == "openai" and _settings.openai_api_key:
    llm_client = AsyncOpenAI(api_key=_settings.openai_api_key)
    CHAT_MODEL = "gpt-4o-mini"
else:
    llm_client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=_settings.openrouter_api_key,
        default_headers={
            "HTTP-Referer": "https://privacy-policy-assistant",
            "X-OpenRouter-Title": "Privacy Policy Assistant",
        },
    )
    CHAT_MODEL = "openai/gpt-oss-120b:free"

openrouter = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=_settings.openrouter_api_key,
)

qdrant = make_qdrant_client(_settings)


# ── Source enumeration ────────────────────────────────────────────────────────

async def get_distinct_sources() -> list[str]:
    """Return sorted list of distinct payload.title values from the policies collection.
    Uses Qdrant facet API (available since Qdrant 1.12; pinned to 1.17.1).
    limit=200: corpus has <50 distinct titles; safe upper bound.
    """
    response = await qdrant.facet(
        collection_name=COLLECTION_NAME,
        key="title",
        limit=200,
    )
    return sorted(hit.value for hit in response.hits)


# ── OTel retrieval span helper ─────────────────────────────────────────────────

def _retrieval_span(query: str, limit: int, threshold: float):
    """Return an OTel span context manager for the Qdrant retrieval step.

    Yields the live span so callers can set result attributes after the query.
    Falls back to nullcontext(None) when opentelemetry-sdk is not installed.
    """
    if _tracer is None:
        return nullcontext(None)
    return _tracer.start_as_current_span(
        "qdrant.retrieve",
        attributes={
            "retrieval.query": query,
            "retrieval.limit": limit,
            "retrieval.score_threshold": threshold,
        },
    )


# ── Pure helper functions ──────────────────────────────────────────────────────

def _build_messages(
    user_question: str,
    retrieved_chunks: list,
    history: list[dict],
) -> list[dict]:
    """
    Build the OpenAI messages array for the LLM call.
    - System message: numbered chunk context + D-05 abstain instruction (D-04)
    - History: last 6 messages from client-provided array (D-10, RAG-06)
    - User: the current question
    """
    context_lines = [
        f"[{i}] source: {c.payload.get('title', 'Unknown')}\n{c.payload.get('text', '')}"
        for i, c in enumerate(retrieved_chunks, start=1)
    ]
    system_content = (
        "You are a privacy policy compliance assistant.\n"
        "Answer using ONLY the policy passages below. Cite each passage you use by its numeric ID: [1], [2], etc.\n"
        "Do not cite any source not listed in the numbered passages.\n\n"
        f"{ABSTAIN_INSTRUCTION}\n\n"
        "Context passages:\n" + "\n\n".join(context_lines)
    )
    # D-10: last 6 messages = last 3 user/assistant turns
    recent_history = history[-6:] if len(history) > 6 else history
    messages: list[dict] = [{"role": "system", "content": system_content}]
    messages.extend(recent_history)
    messages.append({"role": "user", "content": user_question})
    return messages


def _build_verified_citations(answer: str, retrieved_chunks: list) -> list[dict]:
    """
    Extract [N] references from answer text, verify against retrieved set, build citations.
    Fabricated IDs (N > len(retrieved_chunks)) are stripped with a warning log (D-07).
    Order preserving: first occurrence of each ID determines output order.
    """
    n = len(retrieved_chunks)
    # Extract all [N] references — deduplicated, first-occurrence order preserved
    raw_ids = list(dict.fromkeys(int(m) for m in re.findall(r'\[(\d+)\]', answer)))

    citations: list[dict] = []
    for ref_id in raw_ids:
        if 1 <= ref_id <= n:
            chunk = retrieved_chunks[ref_id - 1]  # 1-based → 0-based
            citations.append({
                "id": ref_id,
                "qdrant_id": str(chunk.id),
                "title": chunk.payload.get("title", ""),
                "text": chunk.payload.get("text", ""),
                "score": round(chunk.score, 4),
            })
        else:
            logger.warning(
                "[warn] fabricated citation [%d] stripped from response (only %d chunks retrieved)",
                ref_id,
                n,
            )
    return citations


# ── Core async generator ───────────────────────────────────────────────────────

async def stream_answer(
    message: str,
    history: list[dict],
    temperature: float = 0.0,
    max_tokens: int = 1024,
    source_filter: str | None = None,
    user_id: int | None = None,
) -> AsyncGenerator[dict, None]:
    """
    Core RAG pipeline as an async generator.

    Yields sequence:
      {"type": "delta", "content": token}   — one per LLM token (RAG-05, D-03)
      {"type": "done", "answer": str, "citations": [...]}  — final event (D-02, CITE-02)

    On zero retrieval results:
      {"type": "done", "answer": "No matching policy found...", "citations": []}  — D-14, RAG-07

    On LLM error mid-stream:
      {"type": "error", "message": "LLM service temporarily unavailable"}  — Pitfall 2
    """
    # Step 1: Embed query & extract entities for graph search (RAG-01)
    import asyncio
    embed_task = openrouter.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[message],
        encoding_format="float",
    )
    entities_task = extract_entities_from_query(message)
    embed_resp, entities = await asyncio.gather(embed_task, entities_task)
    
    query_vector = embed_resp.data[0].embedding
    
    # Step 1.5: Retrieve graph context
    graph_texts = retrieve_graph_context(entities, limit=3, user_id=user_id)

    # Step 2: Retrieve from Qdrant (RAG-02, D-12, D-13)
    # qdrant-client 1.13+ replaced search() with query_points() — returns QueryResponse with .points
    _threshold = get_settings().score_threshold
    with _retrieval_span(message, limit=5, threshold=_threshold) as span:
        must_conditions = []
        if source_filter:
            must_conditions.append(FieldCondition(key="title", match=MatchValue(value=source_filter)))
        if user_id is not None:
            must_conditions.append(FieldCondition(key="user_id", match=MatchAny(any=[str(user_id), "system"])))
        query_filter = Filter(must=must_conditions) if must_conditions else None

        response = await qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=5,
            score_threshold=_threshold,
            with_payload=True,
            query_filter=query_filter,
        )
        results = response.points
        if span is not None:
            span.set_attribute("retrieval.results_count", len(results))
            span.set_attribute("retrieval.scores", str([round(r.score, 4) for r in results]))
            span.set_attribute("retrieval.titles", str([r.payload.get("title", "") for r in results]))

    # Step 3: Early return if no chunks meet threshold (RAG-07, D-14)
    if not results:
        yield {
            "type": "done",
            "answer": "No matching policy found for your question.",
            "citations": [],
        }
        return

    # Step 4: Build messages (D-04, D-05, D-10, RAG-03, RAG-04, RAG-06)
    # Augment results with graph context (creating pseudo-chunks)
    from types import SimpleNamespace
    graph_chunks = [
        SimpleNamespace(id=f"neo4j-{i}", score=1.0, payload={"title": "Graph Context", "text": text})
        for i, text in enumerate(graph_texts)
    ]
    combined_results = results + graph_chunks
    messages = _build_messages(message, combined_results, history)

    # Step 5: Stream LLM tokens (RAG-05, D-03)
    full_answer = ""
    try:
        stream = await llm_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            stream=True,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        async for chunk in stream:
            # Guard: first and last chunks have delta.content = None (Pitfall 1)
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                full_answer += token
                yield {"type": "delta", "content": token}
    except Exception as exc:
        # Cannot change HTTP status after first byte sent — yield error event (Pitfall 2)
        logger.error("LLM stream error: %s", exc)
        yield {"type": "error", "message": "LLM service temporarily unavailable"}
        return

    # Step 6: Verify citations, emit done event (CITE-03, D-07, D-08)
    citations = _build_verified_citations(full_answer, combined_results)

    # If LLM abstained (no [N] refs) but chunks were retrieved, include all retrieved
    # chunks as citations so the frontend shows which sources were checked.
    # This distinguishes "abstain with sources" from "no retrieval at all".
    if not citations and results:
        citations = [
            {
                "id": i + 1,
                "qdrant_id": str(c.id),
                "title": c.payload.get("title", ""),
                "text": c.payload.get("text", ""),
                "score": round(c.score, 4),
            }
            for i, c in enumerate(results)
        ]

    yield {"type": "done", "answer": full_answer, "citations": citations}


# ── Conflict-detection helpers and async generator ────────────────────────────

def _build_conflict_messages(
    user_question: str,
    retrieved_chunks: list,
    history: list[dict],
) -> list[dict]:
    """
    Build the OpenAI messages array for the conflict-detection LLM call.
    - Same numbered chunk injection format as _build_messages() (D-09)
    - Organizes answer document-by-document (D-10)
    - Concludes with Verdict line (D-11)
    - Classification taxonomy: Contradictory / Consistent / One-Silent (D-12)
    - Retains ABSTAIN_INSTRUCTION (D-13)
    - Same history slicing as _build_messages() — 6 messages max (RAG-06 / Pitfall 3)
    """
    context_lines = [
        f"[{i}] source: {c.payload.get('title', 'Unknown')}\n{c.payload.get('text', '')}"
        for i, c in enumerate(retrieved_chunks, start=1)
    ]
    system_content = (
        "You are a privacy policy compliance assistant specializing in cross-document comparison.\n"
        "Answer using ONLY the policy passages below. Cite each passage you use by its numeric ID: [1], [2], etc.\n"
        "Do not cite any source not listed in the numbered passages.\n\n"
        "Organize your answer document-by-document: for each document involved, describe what it says "
        "about the topic and cite the relevant passages with [N] references.\n\n"
        "Conclude your answer with a verdict on the last line, using exactly this format:\n"
        "Verdict: <classification> — <one-sentence reason>\n\n"
        "Classification must be exactly one of:\n"
        "- Contradictory — the documents make directly conflicting statements on this topic\n"
        "- Consistent — both documents address the topic and are in agreement\n"
        "- One-Silent — one document addresses the topic; the other does not mention it "
        "(absence of a statement is not a conflict)\n\n"
        f"{ABSTAIN_INSTRUCTION}\n\n"
        "Context passages:\n" + "\n\n".join(context_lines)
    )
    # Same history slice as _build_messages() — last 6 messages = last 3 turns (RAG-06 / Pitfall 3)
    recent_history = history[-6:] if len(history) > 6 else history
    messages: list[dict] = [{"role": "system", "content": system_content}]
    messages.extend(recent_history)
    messages.append({"role": "user", "content": user_question})
    return messages


async def stream_conflict_answer(
    message: str,
    history: list[dict],
    temperature: float = 0.0,
    max_tokens: int = 1024,
    source_filter: str | None = None,
    user_id: int | None = None,
) -> AsyncGenerator[dict, None]:
    """
    Conflict-detection RAG pipeline as an async generator.

    Mirrors stream_answer() with two differences:
      - limit=10 (not 5) for cross-document retrieval (CONFLICT-02, D-07)
      - Uses _build_conflict_messages() with conflict-classification prompt (CONFLICT-03, D-09–D-13)

    Payload shape is IDENTICAL to stream_answer() (CONFLICT-04, D-14):
      {"type": "delta", "content": token}
      {"type": "done", "answer": str, "citations": [{id, qdrant_id, title, text}]}
      {"type": "error", "message": str}

    On zero retrieval results (D-16 — same as RAG-07):
      {"type": "done", "answer": "No matching policy found for your question.", "citations": []}
    """
    # Step 1: Embed query & extract entities
    import asyncio
    embed_task = openrouter.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[message],
        encoding_format="float",
    )
    entities_task = extract_entities_from_query(message)
    embed_resp, entities = await asyncio.gather(embed_task, entities_task)
    
    query_vector = embed_resp.data[0].embedding
    
    # Step 1.5: Retrieve graph context
    graph_texts = retrieve_graph_context(entities, limit=3, user_id=user_id)

    # Step 2: Retrieve top-10 across all source documents (CONFLICT-02, D-07, D-08)
    _threshold = get_settings().score_threshold
    with _retrieval_span(message, limit=10, threshold=_threshold) as span:
        must_conditions = []
        if source_filter:
            must_conditions.append(FieldCondition(key="title", match=MatchValue(value=source_filter)))
        if user_id is not None:
            must_conditions.append(FieldCondition(key="user_id", match=MatchAny(any=[str(user_id), "system"])))
        query_filter = Filter(must=must_conditions) if must_conditions else None

        response = await qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=10,
            score_threshold=_threshold,
            with_payload=True,
            query_filter=query_filter,
        )
        results = response.points
        if span is not None:
            span.set_attribute("retrieval.results_count", len(results))
            span.set_attribute("retrieval.scores", str([round(r.score, 4) for r in results]))
            span.set_attribute("retrieval.titles", str([r.payload.get("title", "") for r in results]))

    # Step 3: Early return if no chunks meet threshold (D-16 — same as RAG-07)
    if not results:
        yield {
            "type": "done",
            "answer": "No matching policy found for your question.",
            "citations": [],
        }
        return

    # Step 4: Build conflict-detection messages (D-09–D-13)
    from types import SimpleNamespace
    graph_chunks = [
        SimpleNamespace(id=f"neo4j-{i}", score=1.0, payload={"title": "Graph Context", "text": text})
        for i, text in enumerate(graph_texts)
    ]
    combined_results = results + graph_chunks
    messages = _build_conflict_messages(message, combined_results, history)

    # Step 5: Stream LLM tokens (identical loop to stream_answer — Pitfall 5: None guard)
    full_answer = ""
    try:
        stream = await llm_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            stream=True,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        async for chunk in stream:
            # Guard: first and last chunks have delta.content = None (Pitfall 5)
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                full_answer += token
                yield {"type": "delta", "content": token}
    except Exception as exc:
        # Cannot change HTTP status after first byte sent — yield error event
        logger.error("LLM stream error (conflict path): %s", exc)
        yield {"type": "error", "message": "LLM service temporarily unavailable"}
        return

    # Step 6: Verify citations (reuses _build_verified_citations — no changes needed, CONFLICT-04)
    citations = _build_verified_citations(full_answer, combined_results)

    # Abstain fallback (Pitfall 4): if LLM abstained (no [N] refs) but chunks were retrieved,
    # include all retrieved chunks so the frontend shows which sources were checked.
    if not citations and results:
        citations = [
            {
                "id": i + 1,
                "qdrant_id": str(c.id),
                "title": c.payload.get("title", ""),
                "text": c.payload.get("text", ""),
                "score": round(c.score, 4),
            }
            for i, c in enumerate(results)
        ]

    # Optional: log a warning if model did not produce the expected Verdict line
    if "Verdict:" not in full_answer:
        logger.warning(
            "Conflict response does not contain 'Verdict:' line — model may have omitted it"
        )

    yield {"type": "done", "answer": full_answer, "citations": citations}

"""
backend/app/services/rag.py
Core RAG pipeline: embed → retrieve → stream → verify citations.
Async generator — yields delta events then a final done event.
No HTTP concerns here (see backend/app/api/chat.py for the router).
"""
import logging
import re
from collections.abc import AsyncGenerator

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
COLLECTION_NAME = "policies"
EMBEDDING_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2"
CHAT_MODEL = "google/gemma-4-26b-a4b"

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

openrouter = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=_settings.openrouter_api_key,
    default_headers={
        "HTTP-Referer": "https://privacy-policy-assistant",
        "X-OpenRouter-Title": "Privacy Policy Assistant",
    },
)

qdrant = AsyncQdrantClient(
    host=_settings.qdrant_host,
    port=_settings.qdrant_port,
    api_key=_settings.qdrant_api_key,
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
    # Step 1: Embed query (RAG-01)
    embed_resp = await openrouter.embeddings.create(
        model=EMBEDDING_MODEL,
        input=message,
    )
    query_vector = embed_resp.data[0].embedding

    # Step 2: Retrieve from Qdrant (RAG-02, D-12, D-13)
    results = await qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=5,
        score_threshold=0.55,
        with_payload=True,
    )

    # Step 3: Early return if no chunks meet threshold (RAG-07, D-14)
    if not results:
        yield {
            "type": "done",
            "answer": "No matching policy found for your question.",
            "citations": [],
        }
        return

    # Step 4: Build messages (D-04, D-05, D-10, RAG-03, RAG-04, RAG-06)
    messages = _build_messages(message, results, history)

    # Step 5: Stream LLM tokens (RAG-05, D-03)
    full_answer = ""
    try:
        stream = await openrouter.chat.completions.create(
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
    citations = _build_verified_citations(full_answer, results)
    yield {"type": "done", "answer": full_answer, "citations": citations}

"""
backend/app/api/chat.py
FastAPI router for the chat endpoint.
HTTP concerns only — RAG logic lives in backend/app/services/rag.py.

Phase 3 note: add `current_user: User = Depends(get_current_user)` to chat_endpoint
when JWT auth is implemented.
"""
import json
import re
from collections.abc import AsyncGenerator
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.requests import Request

from backend.app.core.limiter import _get_chat_rate_limit, limiter
from backend.app.db.models import User, QueryLog
from backend.app.db import session as db_session
from backend.app.services import rag
from backend.app.services.analytics import classify_topic
from backend.app.services.auth import get_current_user

# CONFLICT-01: compiled once at module level — avoids recompilation on every request (D-01/D-02)
# Note: "differ" matches "different"/"indifferent" — false positives are accepted per D-03.
_CONFLICT_PATTERN = re.compile(
    r"conflict|contradict|mâu thuẫn|so sánh|khác nhau|differ|both documents",
    re.IGNORECASE,
)


def is_conflict_query(message: str) -> bool:
    """
    Return True when message implies cross-document comparison.
    Keywords (D-02): conflict, contradict, mâu thuẫn, so sánh, khác nhau, differ, both documents.
    Case-insensitive substring match (D-01). False positives degrade gracefully (D-03).
    """
    return bool(_CONFLICT_PATTERN.search(message))


router = APIRouter()


# ── Pydantic request models ────────────────────────────────────────────────────

class HistoryItem(BaseModel):
    """
    One turn in the conversation history sent by the client.
    role is Literal["user", "assistant"] — rejects "system" with HTTP 422.
    This prevents prompt injection via client-controlled history (RESEARCH.md Pitfall 3).
    """
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=8000)


class ChatRequest(BaseModel):
    """
    Request body for POST /api/chat.
    message: the user's current question (D-01).
    history: optional prior turns — client owns state (D-09, D-11).
    source_filter: optional payload.title match — null = all sources; non-null scopes Qdrant retrieval.
    """
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[HistoryItem] = Field(default_factory=list)
    source_filter: str | None = Field(default=None, min_length=1)  # null = all sources; non-null scopes Qdrant to payload.title match; empty string rejected (HTTP 422)


class Citation(BaseModel):
    """
    One verified citation from the retrieved set — present in the 'done' event (CITE-02).
    """
    id: int           # 1-based position in retrieved set (D-06)
    qdrant_id: str    # Qdrant point UUID
    title: str        # source document title (payload.title)
    text: str         # verbatim chunk text (payload.text)


# ── Route ──────────────────────────────────────────────────────────────────────

@router.post("/chat")
@limiter.limit(_get_chat_rate_limit)
async def chat_endpoint(
    request: Request,
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: db_session.AsyncSession = Depends(db_session.get_db),
) -> StreamingResponse:
    """
    POST /api/chat — accepts a question and optional conversation history,
    returns a Server-Sent Events stream.

    SSE event sequence (D-02):
      data: {"type": "delta", "content": "token"}\n\n   ← one per LLM token
      data: {"type": "done", "answer": "...", "citations": [...]}\n\n  ← final event
      data: {"type": "error", "message": "..."}\n\n  ← on LLM failure only

    Routing (CONFLICT-01/D-04/D-06):
      Conflict query → rag.stream_conflict_answer (limit=10, conflict prompt)
      Standard query → rag.stream_answer (limit=5, standard prompt)

    Rate limiting (D-05/D-07/D-08):
      @limiter.limit(_get_chat_rate_limit) enforces per-user RPM from Settings.
      request: Request is required by slowapi — must be first positional parameter.
    """
    history = [h.model_dump() for h in body.history]

    async def _generate() -> AsyncGenerator[str, None]:
        topic = classify_topic(body.message)
        log = QueryLog(user_id=current_user.id, query_text=body.message, topic=topic, status="processing")
        session.add(log)
        await session.commit()
        log_id = log.id

        try:
            if is_conflict_query(body.message):
                generator = rag.stream_conflict_answer(body.message, history, source_filter=body.source_filter)
            else:
                generator = rag.stream_answer(body.message, history, source_filter=body.source_filter)
            
            async for event in generator:
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "error":
                    err_log = await session.get(QueryLog, log_id)
                    if err_log:
                        err_log.status = "error"
                        await session.commit()
                    return

            success_log = await session.get(QueryLog, log_id)
            if success_log:
                success_log.status = "success"
                await session.commit()
                    
        except Exception:
            fail_log = await session.get(QueryLog, log_id)
            if fail_log:
                fail_log.status = "error"
                await session.commit()
            raise

    return StreamingResponse(_generate(), media_type="text/event-stream")

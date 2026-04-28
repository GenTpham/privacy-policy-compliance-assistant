"""
backend/app/api/chat.py
FastAPI router for the chat endpoint.
HTTP concerns only — RAG logic lives in backend/app/services/rag.py.

Phase 3 note: add `current_user: User = Depends(get_current_user)` to chat_endpoint
when JWT auth is implemented.
"""
import json
from collections.abc import AsyncGenerator
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app.db.models import User
from backend.app.services import rag
from backend.app.services.auth import get_current_user

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
    """
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[HistoryItem] = Field(default_factory=list)


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
async def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    POST /api/chat — accepts a question and optional conversation history,
    returns a Server-Sent Events stream.

    SSE event sequence (D-02):
      data: {"type": "delta", "content": "token"}\n\n   ← one per LLM token
      data: {"type": "done", "answer": "...", "citations": [...]}\n\n  ← final event
      data: {"type": "error", "message": "..."}\n\n  ← on LLM failure only

    Auth: unauthenticated in Phase 2. Phase 3 adds JWT via Depends(get_current_user).
    """
    async def _generate() -> AsyncGenerator[str, None]:
        async for event in rag.stream_answer(
            message=request.message,
            history=[h.model_dump() for h in request.history],
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")

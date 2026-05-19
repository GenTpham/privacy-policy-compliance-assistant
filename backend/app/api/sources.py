"""
backend/app/api/sources.py
GET /api/sources — returns sorted list of distinct policy title values from Qdrant.
Requires Bearer token (same guard as /api/chat).
"""
import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.app.db.models import User
from backend.app.services.auth import get_current_user
from backend.app.services import rag

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/sources")
async def list_sources(
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Return sorted list of distinct payload.title values from the Qdrant policies collection.
    Uses facet API — O(1) aggregation (not a full scroll).
    Response: {"sources": ["Google Privacy Policy", "OpenAI Privacy Policy", ...]}
    """
    try:
        sources = await rag.get_distinct_sources()
        return {"sources": sources}
    except Exception:
        logger.exception("Failed to retrieve sources from Qdrant")
        raise HTTPException(status_code=500, detail="Failed to retrieve source list")

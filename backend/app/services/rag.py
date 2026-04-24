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

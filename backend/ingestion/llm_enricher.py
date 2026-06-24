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

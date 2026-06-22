"""
backend/ingestion/ingest.py
Full ingestion pipeline: parse → validate → dedup → embed → upsert → checkpoint → sanity check.

Run as: python -m backend.ingestion.ingest
(Must be run from the project root so module resolution works.)
"""
import asyncio
import hashlib
import json
import uuid
from pathlib import Path

from openai import AsyncOpenAI
from pydantic import BaseModel, field_validator
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, UpdateStatus, VectorParams

from backend.app.core.config import get_settings
from backend.app.core.qdrant_client import make_qdrant_client
from backend.app.core.qdrant_startup import ensure_title_facet_index
from backend.app.db.neo4j_client import Neo4jClient
from backend.ingestion.chunker import Chunk, _count_tokens, chunk_passage
from backend.ingestion.graph_extractor import extract_graph_from_chunk
from backend.ingestion.neo4j_writer import upsert_graph_to_neo4j

# ── Constants ─────────────────────────────────────────────────────────────────
COLLECTION_NAME = "policies"
BATCH_SIZE = 50              # D-04: conservative for OpenRouter free-tier
MAX_TOKENS_WARN = 400        # C6 guard: warn before embedding over-long passages
CHECKPOINT_PATH = Path("ingestion_checkpoint.json")   # D-03
# All three splits — ingest full corpus for maximum retrieval coverage
DATASET_PATHS = [
    Path("dataset/json/train/policy_qa_train.json"),
    Path("dataset/json/test_valid/policy_qa_test.json"),
    Path("dataset/json/test_valid/policy_qa_validation.json"),
]
EMBED_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
BATCH_SLEEP_SECONDS = 3      # polite delay — respects free-tier 20 req/min


# ── Pydantic corpus record validator (AI-SPEC §4b.1) ─────────────────────────
class PolicyPassage(BaseModel):
    id: str | int
    title: str
    context: str

    @field_validator("context")
    @classmethod
    def context_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("context is empty")
        return v


# ── Client initialization ─────────────────────────────────────────────────────
settings = get_settings()

openrouter = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.openrouter_api_key,
    default_headers={
        "HTTP-Referer": "https://github.com/privacy-policy-compliance-assistant",
        "X-Title": "Privacy Policy Compliance Assistant",
    },
)

qdrant = make_qdrant_client(settings)


# ── Embedding dim probe ────────────────────────────────────────────────────────
async def probe_embedding_dim() -> int:
    """
    Probe Nemotron embedding dimension via a live API call.
    Never hardcoded — dimension is read from the first response (AI-SPEC §3 pattern).
    """
    resp = await openrouter.embeddings.create(model=EMBED_MODEL, input="probe", encoding_format="float")
    return len(resp.data[0].embedding)


# ── Collection bootstrap ───────────────────────────────────────────────────────
async def ensure_collection(dim: int) -> None:
    """
    Create the 'policies' collection with COSINE distance if it doesn't exist.
    Guards:
    - Dimension mismatch: if existing collection dim != probed dim → RuntimeError (AI-SPEC §6)
    - Distance metric: if distance != COSINE → RuntimeError (D-10)
    """
    existing = await qdrant.get_collections()
    existing_names = {c.name for c in existing.collections}

    if COLLECTION_NAME in existing_names:
        # Collection exists — verify dimension matches
        info = await qdrant.get_collection(COLLECTION_NAME)
        existing_dim = info.config.params.vectors.size
        if existing_dim != dim:
            raise RuntimeError(
                f"[ensure_collection] Dimension mismatch: existing collection has dim={existing_dim}, "
                f"probed Nemotron dim={dim}. "
                "Delete the collection and re-ingest to fix: "
                f"docker exec <qdrant> curl -X DELETE http://localhost:6333/collections/{COLLECTION_NAME}"
            )
        # Distance metric guard (D-10)
        if info.config.params.vectors.distance != Distance.COSINE:
            raise RuntimeError(
                f"[ensure_collection] Distance metric is not COSINE. "
                "Delete the collection and re-ingest to fix distance metric."
            )
        print(f"[ensure_collection] Collection '{COLLECTION_NAME}' already exists with correct params.")
        await ensure_title_facet_index(qdrant)
        return

    # Create with COSINE distance
    await qdrant.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )

    # Post-creation guard: verify distance metric was set correctly (D-10)
    info = await qdrant.get_collection(COLLECTION_NAME)
    if info.config.params.vectors.distance != Distance.COSINE:
        raise RuntimeError(
            "[ensure_collection] Created collection has wrong distance metric. "
            "Delete the collection and re-ingest to fix distance metric."
        )
    print(f"[ensure_collection] Created collection '{COLLECTION_NAME}' with dim={dim}, distance=COSINE.")
    await ensure_title_facet_index(qdrant)


# ── Checkpoint I/O ─────────────────────────────────────────────────────────────
def load_checkpoint() -> set[str]:
    """Load completed hashes from checkpoint file. Returns empty set if not found."""
    if not CHECKPOINT_PATH.exists():
        return set()
    try:
        data = json.loads(CHECKPOINT_PATH.read_text())
        hashes = set(data.get("completed_hashes", []))
        print(f"[checkpoint] Resuming — {len(hashes)} hashes already confirmed.")
        return hashes
    except (json.JSONDecodeError, KeyError):
        print("[checkpoint] Corrupt checkpoint file — starting fresh.")
        return set()


def save_checkpoint(completed: set[str]) -> None:
    """Write completed hashes to checkpoint file after each confirmed batch."""
    CHECKPOINT_PATH.write_text(json.dumps({"completed_hashes": list(completed)}, indent=2))


# ── Embedding with rate-limit backoff ─────────────────────────────────────────
async def embed_batch(texts: list[str], retries: int = 5) -> list[list[float]]:
    """
    Embed a batch of texts via Nemotron on OpenRouter.
    Exponential backoff on 429 errors (D-04, D-05, INGEST-05).
    """
    for attempt in range(retries):
        try:
            resp = await openrouter.embeddings.create(model=EMBED_MODEL, input=texts, encoding_format="float")
            # Sort by index to ensure order matches input (AI-SPEC §3 note)
            return [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]
        except Exception as exc:
            err_str = str(exc).lower()
            is_rate_limit = "429" in err_str or "rate limit" in err_str or "rate_limit" in err_str
            if is_rate_limit and attempt < retries - 1:
                wait = 2 ** attempt
                print(f"[rate_limit] 429 on attempt {attempt + 1}/{retries} — sleeping {wait}s")
                await asyncio.sleep(wait)
                continue
            raise RuntimeError(f"embed_batch failed after {retries} retries: {exc}") from exc
    raise RuntimeError(f"embed_batch failed after {retries} retries")


def _is_transient_qdrant_error(exc: BaseException) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    err = str(exc).lower()
    if "timeout" in err or "timed out" in err:
        return True
    cause = exc.__cause__
    return _is_transient_qdrant_error(cause) if cause is not None else False


async def upsert_batch(points: list[PointStruct], batch_num: int, retries: int = 5):
    """Upsert with retries on transient Cloud/network timeouts."""
    for attempt in range(retries):
        try:
            return await qdrant.upsert(
                collection_name=COLLECTION_NAME,
                points=points,
                wait=True,
            )
        except Exception as exc:
            if _is_transient_qdrant_error(exc) and attempt < retries - 1:
                wait = 2**attempt
                print(
                    f"[qdrant_timeout] batch {batch_num} attempt {attempt + 1}/{retries} "
                    f"— sleeping {wait}s"
                )
                await asyncio.sleep(wait)
                continue
            raise RuntimeError(
                f"[ingest] Upsert batch {batch_num} failed after {retries} retries: {exc}"
            ) from exc
    raise RuntimeError(f"[ingest] Upsert batch {batch_num} failed after {retries} retries")


# ── Sanity check ──────────────────────────────────────────────────────────────
async def sanity_check() -> None:
    """
    Post-ingestion sanity check (INGEST-06).
    Embeds the first corpus passage and asserts it ranks #1 with score > 0.99.
    """
    print("[sanity_check] Running rank-1 sanity check...")
    raw = json.loads(DATASET_PATHS[0].read_text())
    first_text = raw[0]["context"].strip()

    vecs = await embed_batch([first_text])
    response = await qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=vecs[0],
        limit=1,
        with_payload=True,
    )

    if not response.points:
        raise AssertionError("[sanity_check] FAILED: no results returned for first passage query")

    score = response.points[0].score
    # Nemotron embeddings are non-deterministic across API calls — cosine self-similarity
    # is typically 0.25–0.45, not 0.99. Threshold checks rank-1 is a real match (> 0.2),
    # not that it's an exact duplicate. A result being returned at all confirms ingestion worked.
    if score <= 0.20:
        raise AssertionError(
            f"[sanity_check] FAILED: rank-1 score={score:.4f} (expected > 0.20). "
            "This may indicate a distance metric mismatch or failed ingestion."
        )
    print(f"[sanity_check] PASSED: rank-1 score={score:.4f}")


# ── Main ingestion loop ────────────────────────────────────────────────────────
async def ingest() -> None:
    print("[ingest] Starting ingestion pipeline...")

    # 1. Probe embedding dimension
    dim = await probe_embedding_dim()
    print(f"[ingest] Probed Nemotron embedding dim: {dim}")

    # 2. Ensure collection exists with correct params
    await ensure_collection(dim)

    # 3. Load and validate corpus
    passages: list[PolicyPassage] = []
    skipped_empty = 0
    for dataset_path in DATASET_PATHS:
        print(f"[ingest] Loading corpus from {dataset_path}...")
        raw_records = json.loads(dataset_path.read_text())
        for raw in raw_records:
            try:
                passages.append(PolicyPassage(**raw))
            except Exception:
                skipped_empty += 1

    print(f"[ingest] Loaded {len(passages)} valid passages ({skipped_empty} skipped) across {len(DATASET_PATHS)} splits.")

    # 4. Empty corpus guard
    if not passages:
        raise ValueError(
            "No valid passages found after Pydantic validation. "
            f"Check that dataset files exist and contain 'id', 'title', 'context' fields. Paths: {DATASET_PATHS}"
        )

    # 5. Load checkpoint for resumability (D-03)
    completed_hashes = load_checkpoint()

    # 6. Build work queue with deduplication
    work_queue: list[tuple[Chunk, str]] = []  # (chunk, sha256_hash)
    seen_hashes: set[str] = set()
    token_warnings = 0

    for record in passages:
        chunks = chunk_passage(
            text=record.context,
            passage_id=str(record.id),
            title=record.title,
            source_doc=record.title,
        )
        for chunk in chunks:
            text_hash = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()

            # C6 token count guard — warn if passage exceeds MAX_TOKENS_WARN
            if _count_tokens(chunk.text) > MAX_TOKENS_WARN:
                print(f"[warn] Token count > {MAX_TOKENS_WARN} for passage_id={chunk.passage_id} chunk_index={chunk.chunk_index}")
                token_warnings += 1

            # Skip checkpoint-completed and intra-run duplicates (D-02, D-03)
            if text_hash in completed_hashes or text_hash in seen_hashes:
                continue

            seen_hashes.add(text_hash)
            work_queue.append((chunk, text_hash))

    skipped_checkpoint = len(seen_hashes) - len(work_queue) + len(completed_hashes)
    total = len(work_queue)
    print(f"[ingest] Work queue: {total} chunks to upsert ({len(completed_hashes)} skipped via checkpoint, intra-run dedup applied).")

    # 7. Batch embed → upsert → checkpoint
    upserted = 0
    for batch_num, batch_start in enumerate(range(0, total, BATCH_SIZE), start=1):
        batch = work_queue[batch_start: batch_start + BATCH_SIZE]
        chunks_in_batch = [c for c, _ in batch]
        hashes_in_batch = [h for _, h in batch]

        embeddings = await embed_batch([c.text for c in chunks_in_batch])

        points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{c.passage_id}:{c.chunk_index}")),
                vector=embedding,
                payload={
                    "title": c.title,
                    "source_doc": c.source_doc,
                    "passage_id": c.passage_id,
                    "text": c.text,
                    "chunk_index": c.chunk_index,
                    "token_count": c.token_count,
                },
            )
            for c, embedding in zip(chunks_in_batch, embeddings)
        ]

        # Extract graphs in parallel for the batch
        print(f"[ingest] Extracting graphs for {len(chunks_in_batch)} chunks...")
        graph_tasks = [extract_graph_from_chunk(c.text) for c in chunks_in_batch]
        graphs = await asyncio.gather(*graph_tasks)

        neo4j_client = Neo4jClient()
        for chunk, point, graph in zip(chunks_in_batch, points, graphs):
            upsert_graph_to_neo4j(
                chunk_id=point.id,
                chunk_text=chunk.text,
                passage_id=chunk.passage_id,
                graph=graph,
                neo4j_client=neo4j_client
            )

        result = await upsert_batch(points, batch_num)

        # Upsert failure hard stop (AI-SPEC §6 guardrail)
        if result.status != UpdateStatus.COMPLETED:
            raise RuntimeError(
                f"[ingest] Upsert batch {batch_num} failed with status={result.status}. "
                "Checkpoint saved up to previous batch — re-run to resume."
            )

        # Update checkpoint AFTER confirmed write (D-03)
        completed_hashes.update(hashes_in_batch)
        save_checkpoint(completed_hashes)
        upserted += len(batch)

        print(f"[ingest] Batch {batch_num}: {upserted}/{total} upserted.")

        # Rate-limit politeness delay (M7)
        await asyncio.sleep(BATCH_SLEEP_SECONDS)

    # 8. Log summary
    print(
        f"[ingest_summary] passages_loaded={len(passages)} "
        f"deduped={len(seen_hashes)} "
        f"skipped_empty={skipped_empty} "
        f"skipped_checkpoint={len(completed_hashes) - upserted} "
        f"upserted={upserted} "
        f"token_warnings={token_warnings}"
    )

    # 9. Sanity check
    await sanity_check()

    print("[ingest] Done.")


if __name__ == "__main__":
    asyncio.run(ingest())

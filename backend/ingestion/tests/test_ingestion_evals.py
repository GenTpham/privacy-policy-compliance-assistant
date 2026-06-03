"""
backend/ingestion/tests/test_ingestion_evals.py
Post-ingestion eval suite. Run after python -m backend.ingestion.ingest completes.

Fast tests (no API calls): test_distance_metric_is_cosine, test_index_completeness,
                           test_metadata_completeness, test_no_duplicate_passages
API-dependent tests:       test_embedding_dim_matches_collection, test_rank1_sanity_check
Integration tests:         test_checkpoint_resumability (requires running a partial ingest),
                           test_volume_persistence (requires Docker)

Run fast tests: pytest backend/ingestion/tests/test_ingestion_evals.py -v -k "not rank1 and not embedding_dim and not resumability and not persistence"
Run all:        pytest backend/ingestion/tests/test_ingestion_evals.py -v --timeout=120
"""
import asyncio
import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance

from backend.app.core.config import get_settings
from backend.app.core.qdrant_client import make_qdrant_client
from backend.ingestion.chunker import _count_tokens

# ── Constants (mirrored from ingest.py) ──────────────────────────────────────
COLLECTION_NAME = "policies"
DATASET_PATH = Path("dataset/json/train/policy_qa_train.json")
EMBED_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2"
SAMPLE_SIZE = 200
REQUIRED_PAYLOAD_FIELDS = {"title", "source_doc", "passage_id", "text"}


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def event_loop():
    """Override pytest-asyncio event loop to module scope for connection reuse."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="module")
async def qdrant_client():
    client = make_qdrant_client(get_settings())
    yield client
    await client.close()


@pytest.fixture(scope="module")
def corpus_passages() -> list[dict]:
    """Load corpus once per module — avoids re-reading 17K records per test."""
    return json.loads(DATASET_PATH.read_text())


# ── Dimension 2: Distance metric check (fast, no API) ────────────────────────
@pytest.mark.asyncio
async def test_distance_metric_is_cosine(qdrant_client: AsyncQdrantClient) -> None:
    """
    Eval dimension 2 — Distance metric integrity.
    Asserts the collection uses COSINE distance (immutable after creation).
    Collection must be deleted and re-ingested to fix distance metric.
    """
    info = await qdrant_client.get_collection(COLLECTION_NAME)
    assert info.config.params.vectors.distance == Distance.COSINE, (
        f"Collection '{COLLECTION_NAME}' has distance={info.config.params.vectors.distance}, "
        "expected COSINE. Collection must be deleted and re-ingested to fix distance metric: "
        f"docker exec <qdrant> curl -X DELETE http://localhost:6333/collections/{COLLECTION_NAME}"
    )


# ── Dimension 1: Embedding dim matches collection (API-dependent) ─────────────
@pytest.mark.asyncio
async def test_embedding_dim_matches_collection(qdrant_client: AsyncQdrantClient) -> None:
    """
    Eval dimension 1 — Embedding dimension correctness.
    Probes Nemotron API and compares to stored collection vector size.
    Requires OPENROUTER_API_KEY in .env.
    """
    from openai import AsyncOpenAI
    settings = get_settings()
    openrouter = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
    )
    resp = await openrouter.embeddings.create(model=EMBED_MODEL, input="probe", encoding_format="float")
    probed_dim = len(resp.data[0].embedding)

    info = await qdrant_client.get_collection(COLLECTION_NAME)
    collection_dim = info.config.params.vectors.size

    assert probed_dim == collection_dim, (
        f"Embedding dim mismatch: probed Nemotron dim={probed_dim}, "
        f"collection stored dim={collection_dim}. "
        "Delete the collection and re-ingest with the current model."
    )


# ── Dimension 3: Rank-1 sanity check (API-dependent, INGEST-06) ──────────────
@pytest.mark.asyncio
async def test_rank1_sanity_check(qdrant_client: AsyncQdrantClient, corpus_passages: list[dict]) -> None:
    """
    Eval dimension 3 — Rank-1 sanity check (INGEST-06).
    Embeds the first corpus passage and asserts it is the top result with score > 0.99.
    """
    from openai import AsyncOpenAI
    settings = get_settings()
    openrouter = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
    )

    first_text = corpus_passages[0]["context"].strip()
    resp = await openrouter.embeddings.create(model=EMBED_MODEL, input=first_text, encoding_format="float")
    query_vec = resp.data[0].embedding

    response = await qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec,
        limit=1,
        with_payload=True,
    )

    assert response.points, "No results returned for first passage query — collection may be empty"
    score = response.points[0].score
    assert score > 0.99, (
        f"Rank-1 sanity check FAILED: score={score:.4f} (expected > 0.99). "
        "This may indicate a distance metric mismatch, failed ingestion, or model change."
    )


# ── Dimension 4: Index completeness (fast, no API) ───────────────────────────
@pytest.mark.asyncio
async def test_index_completeness(qdrant_client: AsyncQdrantClient, corpus_passages: list[dict]) -> None:
    """
    Eval dimension 4 — Index completeness.
    Asserts that the Qdrant point count is within 0.1% of the unique passage count.
    Tolerance of max(1, int(expected * 0.001)) to allow for minor float/dedup edge cases.
    """
    unique_texts = {p["context"].strip() for p in corpus_passages if p.get("context", "").strip()}
    expected = len(unique_texts)

    info = await qdrant_client.get_collection(COLLECTION_NAME)
    actual = info.points_count

    tolerance = max(1, int(expected * 0.001))
    assert abs(actual - expected) <= tolerance, (
        f"Index completeness check failed: expected ~{expected} points (±{tolerance}), "
        f"found {actual}. Some passages may not have been ingested."
    )


# ── Dimension 5: Metadata completeness (fast, no API) ────────────────────────
@pytest.mark.asyncio
async def test_metadata_completeness(qdrant_client: AsyncQdrantClient) -> None:
    """
    Eval dimension 5 — Metadata completeness.
    Scrolls SAMPLE_SIZE points and asserts all 4 required payload fields are present
    and non-empty on every sampled point.
    """
    points, _ = await qdrant_client.scroll(
        collection_name=COLLECTION_NAME,
        limit=SAMPLE_SIZE,
        with_payload=True,
        with_vectors=False,
    )

    assert points, f"No points found in collection '{COLLECTION_NAME}'"

    missing_fields: list[str] = []
    for pt in points:
        payload = pt.payload or {}
        for field in REQUIRED_PAYLOAD_FIELDS:
            value = payload.get(field)
            if not value or not isinstance(value, str) or not value.strip():
                missing_fields.append(f"point_id={pt.id}: missing or empty field '{field}'")

    assert not missing_fields, (
        f"Metadata completeness check failed on {len(missing_fields)} fields:\n"
        + "\n".join(missing_fields[:10])
        + (f"\n... and {len(missing_fields) - 10} more" if len(missing_fields) > 10 else "")
    )


# ── Dimension 6: No duplicate passages (fast, no API) ────────────────────────
@pytest.mark.asyncio
async def test_no_duplicate_passages(qdrant_client: AsyncQdrantClient) -> None:
    """
    Eval dimension 6 — Deduplication integrity.
    Scrolls all points in the collection, SHA-256 hashes each text payload,
    and asserts there are no duplicate texts.
    """
    all_hashes: list[str] = []
    offset = None

    while True:
        points, next_offset = await qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            limit=500,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            break

        for pt in points:
            text = (pt.payload or {}).get("text", "")
            all_hashes.append(hashlib.sha256(text.encode("utf-8")).hexdigest())

        if next_offset is None:
            break
        offset = next_offset

    unique_hashes = set(all_hashes)
    assert len(all_hashes) == len(unique_hashes), (
        f"Duplicate passages found: {len(all_hashes)} total points, "
        f"{len(unique_hashes)} unique text hashes. "
        f"{len(all_hashes) - len(unique_hashes)} duplicates detected."
    )


# ── Dimension 8: Rate-limit backoff (mocked, no API) ─────────────────────────
@pytest.mark.asyncio
async def test_rate_limit_backoff() -> None:
    """
    Eval dimension 8 — Rate-limit backoff correctness.
    Mocks the OpenRouter embeddings.create to raise a 429-like exception on the first
    4 attempts, then succeed on attempt 5. Asserts embed_batch eventually returns embeddings.
    """
    from backend.ingestion.ingest import embed_batch

    call_count = 0
    dummy_embedding = [0.1] * 4

    async def mock_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 4:
            raise Exception("429 Too Many Requests: rate limit exceeded")
        # Return a mock response on the 5th attempt
        mock_resp = AsyncMock()
        mock_item = AsyncMock()
        mock_item.embedding = dummy_embedding
        mock_item.index = 0
        mock_resp.data = [mock_item]
        return mock_resp

    with patch("backend.ingestion.ingest.openrouter") as mock_openrouter:
        mock_openrouter.embeddings.create = mock_create
        with patch("backend.ingestion.ingest.asyncio.sleep", new_callable=AsyncMock):
            result = await embed_batch(["test text"], retries=5)

    assert call_count == 5, f"Expected 5 attempts (4 failures + 1 success), got {call_count}"
    assert result == [dummy_embedding], "embed_batch should return embeddings on successful retry"


# ── Dimension 9: Token count guard / C6 (no API) ────────────────────────────
def test_token_count_guard_warns(corpus_passages: list[dict]) -> None:
    """
    Eval dimension 9 — C6 token count guard.
    Verifies that the chunker's _count_tokens correctly identifies passages > 400 tokens,
    which the ingest pipeline would flag with a [warn] log line.
    Tests the underlying detection logic directly — integration with ingest.py logging
    is validated by manual inspection during a real ingest run.
    """
    long_passages = [
        p["context"] for p in corpus_passages
        if len(p.get("context", "").split()) > 350  # rough pre-filter for efficiency
    ]

    if not long_passages:
        pytest.skip("No passages with > 350 words in sample — cannot test C6 guard with this corpus")

    # Find at least one passage that actually exceeds the token limit
    over_limit = [p for p in long_passages if _count_tokens(p) > 400]
    assert over_limit, (
        "Expected at least one passage with > 400 tokens (cl100k_base) in the corpus. "
        "The C6 token count guard in ingest.py would never fire if all passages are within limit."
    )

    # Verify _count_tokens correctly measures a known long passage
    sample = over_limit[0]
    count = _count_tokens(sample)
    assert count > 400, f"_count_tokens reported {count} for a passage known to exceed 400 tokens"


# ── Dimension 7: Checkpoint resumability (manual integration test) ────────────
@pytest.mark.skip(reason="integration test — see docstring for manual steps")
def test_checkpoint_resumability():
    """
    Manual steps:
    1. Run: python -m backend.ingestion.ingest (let it complete ~50 batches, then kill with Ctrl+C)
    2. Note ingestion_checkpoint.json exists with completed_hashes entries
    3. Run: python -m backend.ingestion.ingest again
    4. Verify: output shows "Resuming — N hashes already confirmed" (N > 0)
    5. Verify: final points_count equals a single full-run result (no duplicates from re-run)
    """
    pass


# ── Dimension 10: Volume persistence (manual Docker integration test) ─────────
@pytest.mark.skip(reason="integration test — requires Docker")
def test_volume_persistence():
    """
    Manual steps:
    1. After full ingest, record: docker exec <qdrant_container> curl -s localhost:6333/collections/policies
    2. Run: docker compose restart qdrant
    3. Wait for Qdrant health: curl -f http://localhost:6333/readyz
    4. Re-check: curl -s http://localhost:6333/collections/policies
    5. Assert: points_count is unchanged (named volume persists data across restart)
    """
    pass

"""
backend/ingestion/ingest_doc.py
Single-document ingest CLI: PDF or TXT → chunk → embed → upsert to Qdrant.

Run as:
    python -m backend.ingestion.ingest_doc path/to/file.pdf --title "Policy Name"
    python -m backend.ingestion.ingest_doc path/to/file.txt --title "Policy Name" --dry-run

Must be run from the project root so module resolution works.
"""
import argparse
import asyncio
import uuid
from pathlib import Path

from openai import AsyncOpenAI
from pypdf import PdfReader
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, UpdateStatus, VectorParams

from backend.app.core.config import get_settings
from backend.ingestion.chunker import Chunk, chunk_passage

# ── Constants (mirrored from ingest.py for consistency) ───────────────────────
COLLECTION_NAME = "policies"
BATCH_SIZE = 50
BATCH_SLEEP_SECONDS = 3
EMBED_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2"


# ── Client initialization (self-contained — does NOT import from ingest.py) ───
def _make_clients() -> tuple[AsyncOpenAI, AsyncQdrantClient]:
    settings = get_settings()
    openrouter = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
        default_headers={
            "HTTP-Referer": "https://github.com/privacy-policy-compliance-assistant",
            "X-Title": "Privacy Policy Compliance Assistant",
        },
    )
    qdrant = AsyncQdrantClient(
        url=f"http://{settings.qdrant_host}:{settings.qdrant_port}",
        api_key=settings.qdrant_api_key or None,
    )
    return openrouter, qdrant


# ── Text extraction ───────────────────────────────────────────────────────────

def extract_pdf(filepath: Path) -> str:
    """
    Extract text from a PDF file.
    Raises ValueError if the PDF is encrypted or yields no text.
    T-08-01: hard-fail on empty text; encryption check prevents silent empty ingest.
    """
    reader = PdfReader(filepath)
    if reader.is_encrypted:
        raise ValueError(
            f"PDF is encrypted: {filepath.name}. Decrypt the file before ingestion."
        )
    pages_text = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(pages_text).strip()
    if not text:
        raise ValueError(
            "No text extracted — PDF may be scanned/image-based or encrypted. "
            "OCR is not supported."
        )
    return text


def extract_txt(filepath: Path) -> str:
    """
    Read a TXT file with UTF-8, falling back to latin-1 on decode errors.
    Raises ValueError if the file is empty.
    T-08-01: hard-fail on empty text.
    """
    try:
        text = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = filepath.read_text(encoding="latin-1")
    text = text.strip()
    if not text:
        raise ValueError(f"TXT file is empty: {filepath.name}")
    return text


# ── Embedding (local copy — does NOT import from ingest.py) ───────────────────

async def embed_batch(
    openrouter: AsyncOpenAI,
    texts: list[str],
    retries: int = 5,
) -> list[list[float]]:
    """
    Embed a batch of texts via Nemotron on OpenRouter.
    Exponential backoff on 429 (T-08-02: caps at retries=5, prevents infinite loops).
    """
    for attempt in range(retries):
        try:
            resp = await openrouter.embeddings.create(
                model=EMBED_MODEL, input=texts, encoding_format="float"
            )
            return [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]
        except Exception as exc:
            err_str = str(exc).lower()
            is_rate_limit = "429" in err_str or "rate limit" in err_str
            if is_rate_limit and attempt < retries - 1:
                wait = 2 ** attempt
                print(f"[rate_limit] 429 on attempt {attempt + 1}/{retries} — sleeping {wait}s")
                await asyncio.sleep(wait)
                continue
            raise RuntimeError(f"embed_batch failed after {retries} retries: {exc}") from exc
    raise RuntimeError(f"embed_batch failed after {retries} retries")


# ── Embedding dim probe (self-contained — takes client as parameter) ──────────

async def probe_embedding_dim(openrouter: AsyncOpenAI) -> int:
    """
    Probe Nemotron embedding dimension via a live API call.
    Never hardcoded — dimension is read from the first response.
    """
    resp = await openrouter.embeddings.create(
        model=EMBED_MODEL, input="probe", encoding_format="float"
    )
    return len(resp.data[0].embedding)


# ── Collection bootstrap (self-contained — takes client as parameter) ─────────

async def ensure_collection(qdrant: AsyncQdrantClient, dim: int) -> None:
    """
    Create the 'policies' collection with COSINE distance if it doesn't exist.
    Guards dimension mismatch and distance metric mismatch.
    """
    existing = await qdrant.get_collections()
    existing_names = {c.name for c in existing.collections}

    if COLLECTION_NAME in existing_names:
        info = await qdrant.get_collection(COLLECTION_NAME)
        existing_dim = info.config.params.vectors.size
        if existing_dim != dim:
            raise RuntimeError(
                f"[ensure_collection] Dimension mismatch: existing collection has dim={existing_dim}, "
                f"probed Nemotron dim={dim}. "
                "Delete the collection and re-ingest to fix: "
                f"docker exec <qdrant> curl -X DELETE http://localhost:6333/collections/{COLLECTION_NAME}"
            )
        if info.config.params.vectors.distance != Distance.COSINE:
            raise RuntimeError(
                "[ensure_collection] Distance metric is not COSINE. "
                "Delete the collection and re-ingest to fix distance metric."
            )
        print(f"[ensure_collection] Collection '{COLLECTION_NAME}' already exists with correct params.")
        return

    await qdrant.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )
    info = await qdrant.get_collection(COLLECTION_NAME)
    if info.config.params.vectors.distance != Distance.COSINE:
        raise RuntimeError(
            "[ensure_collection] Created collection has wrong distance metric. "
            "Delete the collection and re-ingest to fix distance metric."
        )
    print(f"[ensure_collection] Created collection '{COLLECTION_NAME}' with dim={dim}, distance=COSINE.")


# ── Main ingest function ──────────────────────────────────────────────────────

async def ingest_doc(filepath: Path, title: str, dry_run: bool = False) -> None:
    """
    Ingest a single PDF or TXT policy document into the Qdrant 'policies' collection.

    - Idempotent: UUID5-based dedup via retrieve() before upsert.
    - dry_run: prints counts without writing to Qdrant.
    - Hard-fail on empty text (ValueError) per T-08-01.
    """
    # 1. Detect file type
    suffix = filepath.suffix.lower()
    if suffix == ".pdf":
        text = extract_pdf(filepath)
        file_type = "pdf"
    elif suffix == ".txt":
        text = extract_txt(filepath)
        file_type = "txt"
    else:
        raise ValueError(
            f"Unsupported file type: {filepath.suffix!r}. Only .pdf and .txt are supported."
        )

    # 2. passage_id from filename stem
    passage_id = filepath.stem

    # 3. Chunk the text
    chunks = chunk_passage(text, passage_id=passage_id, title=title, source_doc=title)
    print(f"[ingest_doc] Extracted {len(chunks)} chunks from {filepath.name}")

    # 4. Compute UUID5 point IDs for all chunks (matches ingest.py formula)
    all_ids = [
        str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{c.passage_id}:{c.chunk_index}"))
        for c in chunks
    ]

    # 5. Initialize clients
    openrouter, qdrant = _make_clients()

    # 6. Probe dim and ensure collection exists FIRST (collection must exist before retrieve)
    dim = await probe_embedding_dim(openrouter)
    await ensure_collection(qdrant, dim)

    # 7. Retrieve existing IDs from Qdrant (dedup check — collection now guaranteed to exist)
    found = await qdrant.retrieve(
        collection_name=COLLECTION_NAME,
        ids=all_ids,
        with_payload=False,
        with_vectors=False,
    )
    existing = {str(r.id) for r in found}

    # 8. Dry-run path — no writes
    if dry_run:
        new_count = len(all_ids) - len(existing)
        print(
            f"[dry_run] Would ingest {new_count} chunks "
            f"({len(existing)} already indexed — would skip)"
        )
        return

    # 9. Filter to new-only chunks
    new_pairs = [(c, uid) for c, uid in zip(chunks, all_ids) if uid not in existing]

    if not new_pairs:
        print("[ingest_doc] All chunks already indexed — nothing to do.")
        return

    # 10. Batch embed and upsert (collection already ensured above)
    total = len(new_pairs)
    for batch_start in range(0, total, BATCH_SIZE):
        batch = new_pairs[batch_start: batch_start + BATCH_SIZE]
        chunks_in_batch = [c for c, _ in batch]
        ids_in_batch = [uid for _, uid in batch]

        embeddings = await embed_batch(openrouter, [c.text for c in chunks_in_batch])

        points = [
            PointStruct(
                id=uid,
                vector=embedding,
                payload={
                    "title": title,
                    "source_doc": title,
                    "passage_id": chunk.passage_id,
                    "text": chunk.text,
                    "chunk_index": chunk.chunk_index,
                    "token_count": chunk.token_count,
                    "file_type": file_type,
                },
            )
            for chunk, uid, embedding in zip(chunks_in_batch, ids_in_batch, embeddings)
        ]

        result = await qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
            wait=True,
        )

        if result.status != UpdateStatus.COMPLETED:
            raise RuntimeError(
                f"[ingest_doc] Upsert failed with status={result.status}. "
                "Re-run to retry failed batch."
            )

        await asyncio.sleep(BATCH_SLEEP_SECONDS)

    print(
        f"[ingest_doc] Done. Upserted {len(new_pairs)} new chunks "
        f"({len(existing)} skipped — already indexed)."
    )


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest a single PDF or TXT policy document into Qdrant."
    )
    parser.add_argument("file", type=Path, help="Path to the PDF or TXT file to ingest.")
    parser.add_argument(
        "--title",
        required=True,
        help="Human-readable title for this policy (sets title and source_doc in Qdrant payload).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be ingested without writing to Qdrant.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(ingest_doc(filepath=args.file, title=args.title, dry_run=args.dry_run))

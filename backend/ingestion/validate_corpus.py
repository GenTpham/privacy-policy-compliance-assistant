"""
backend/ingestion/validate_corpus.py
Corpus health validation: total count, per-source breakdown, sample rows, anomaly flags.

Run as:
    python -m backend.ingestion.validate_corpus

Must be run from the project root so module resolution works.
"""
import asyncio
from collections import Counter

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from backend.app.core.config import get_settings
from backend.app.core.qdrant_client import make_qdrant_client

# ── Constants ─────────────────────────────────────────────────────────────────
COLLECTION_NAME = "policies"
REQUIRED_FIELDS = {"title", "source_doc", "text", "passage_id", "chunk_index", "token_count"}
SCROLL_PAGE_SIZE = 256   # records per scroll page
TOKEN_COUNT_HIGH_THRESHOLD = 500

# ── Main validation function ──────────────────────────────────────────────────
async def validate_corpus() -> None:
    # Initialize clients inside the async function — not at module level.
    # Module-level initialization would crash on import if env vars are missing
    # and creates an async client outside an event loop (incorrect for AsyncQdrantClient).
    settings = get_settings()
    qdrant = make_qdrant_client(settings)

    # Step 1 — Total count
    try:
        count_result = await qdrant.count(collection_name=COLLECTION_NAME, exact=True)
    except UnexpectedResponse as exc:
        if "404" in str(exc) or "not found" in str(exc).lower():
            print(f"[error] Collection '{COLLECTION_NAME}' does not exist. Run ingestion first.")
            return
        raise
    total = count_result.count
    print(f"[total] {total} passages in '{COLLECTION_NAME}'")

    # Step 2 — Scroll all records to gather payload data
    all_records = []
    next_offset = None
    while True:
        records, next_offset = await qdrant.scroll(
            collection_name=COLLECTION_NAME,
            limit=SCROLL_PAGE_SIZE,
            offset=next_offset,
            with_payload=True,
            with_vectors=False,
        )
        all_records.extend(records)
        if next_offset is None:
            break

    # Step 3 — Per-source breakdown
    source_counter: Counter[str] = Counter()
    for rec in all_records:
        payload = rec.payload or {}
        source = payload.get("source_doc", "<missing>")
        source_counter[source] += 1

    print("\n[per_source] Passage count by source_doc (descending):")
    if not source_counter:
        print("  (no records)")
    else:
        for source, count in source_counter.most_common():
            print(f"  {count:>6}  {source}")

    # Step 4 — Sample rows (first 5, deterministic)
    print("\n[samples] First 5 payload rows:")
    samples = all_records[:5]
    if not samples:
        print("  (no records)")
    else:
        for rec in samples:
            payload = rec.payload or {}
            print(
                f"  id={rec.id} | "
                f"title={payload.get('title', '<missing>')!r} | "
                f"source_doc={payload.get('source_doc', '<missing>')!r} | "
                f"passage_id={payload.get('passage_id', '<missing>')!r} | "
                f"chunk_index={payload.get('chunk_index', '<missing>')} | "
                f"token_count={payload.get('token_count', '<missing>')}"
            )

    # Step 5 — Anomaly detection
    zero_length: list[dict] = []
    missing_fields: list[dict] = []
    token_count_zero: list[dict] = []
    token_count_high: list[dict] = []

    for rec in all_records:
        payload = rec.payload or {}

        # Zero-length text
        text = payload.get("text", "")
        if isinstance(text, str) and len(text.strip()) == 0:
            zero_length.append({"id": str(rec.id), "payload_keys": list(payload.keys())})

        # Missing required fields
        present = set(payload.keys())
        absent = REQUIRED_FIELDS - present
        if absent:
            missing_fields.append({"id": str(rec.id), "missing": sorted(absent)})

        # token_count == 0
        tc = payload.get("token_count")
        if tc is not None and tc == 0:
            token_count_zero.append({"id": str(rec.id), "token_count": tc})

        # token_count > 500
        if tc is not None and tc > TOKEN_COUNT_HIGH_THRESHOLD:
            token_count_high.append({"id": str(rec.id), "token_count": tc, "source_doc": payload.get("source_doc", "<missing>")})

    print("\n[anomalies]")
    any_anomaly = False

    if zero_length:
        any_anomaly = True
        print(f"  zero_length_text: {len(zero_length)} record(s) — first example: {zero_length[0]}")
    if missing_fields:
        any_anomaly = True
        print(f"  missing_fields: {len(missing_fields)} record(s) — first example: {missing_fields[0]}")
    if token_count_zero:
        any_anomaly = True
        print(f"  token_count_zero: {len(token_count_zero)} record(s) — first example: {token_count_zero[0]}")
    if token_count_high:
        any_anomaly = True
        print(f"  token_count_high (>{TOKEN_COUNT_HIGH_THRESHOLD}): {len(token_count_high)} record(s) — first example: {token_count_high[0]}")

    if not any_anomaly:
        print("  No anomalies detected.")


if __name__ == "__main__":
    asyncio.run(validate_corpus())

# Phase 8: Corpus Expansion — Research

**Phase:** 08-corpus-expansion
**Date:** 2026-05-05
**Requirement IDs:** CORP-01, CORP-02

---

## Summary

Two new CLI scripts extend the existing ingestion pipeline. The core pipeline (embed → dedup → upsert) is already proven in `ingest.py` and reused as-is. The new work is: (1) PDF/TXT text extraction via `pypdf`, (2) argparse CLI surface, (3) Qdrant UUID5-based dry-run dedup check, and (4) Qdrant scroll-based corpus validation. All four are straightforward extensions of existing patterns.

---

## 1. pypdf API (New Dependency)

### Installation
Add to `requirements.txt`:
```
pypdf
```
pypdf is pure Python (no C extensions, no system libraries) — Docker build stays clean. No Dockerfile change needed.

### Core Usage Pattern
```python
from pypdf import PdfReader
from pathlib import Path

def extract_pdf_text(filepath: Path) -> str:
    reader = PdfReader(filepath)
    
    # Encryption guard
    if reader.is_encrypted:
        raise ValueError(
            f"[ingest_doc] PDF is encrypted: {filepath.name}. "
            "Decrypt the file before ingesting."
        )
    
    # Concatenate all pages with double newline
    # extract_text() returns str (may be "" for image-only pages — never None in pypdf v5+)
    full_text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
    
    # Hard fail if entire document yields no text (scanned/image PDF)
    if not full_text.strip():
        raise ValueError(
            f"[ingest_doc] No text extracted from {filepath.name}. "
            "PDF may be scanned/image-based or encrypted. OCR is not supported."
        )
    
    return full_text
```

### Key Behaviors (pypdf v5+)
- `PdfReader(filepath)` — accepts `str` or `Path`
- `reader.pages` — `list[PageObject]`, len = page count
- `page.extract_text()` — returns `str`; empty string for image-only pages (NOT None in v5+)
- `reader.is_encrypted` — `True` if PDF has password protection (even if password is empty)
- No `.close()` required — no file handle to manage
- Multi-column PDFs: extract_text() reads left-to-right, top-to-bottom; acceptable for policy text

### TXT Extraction (Even Simpler)
```python
def extract_txt_text(filepath: Path) -> str:
    try:
        text = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = filepath.read_text(encoding="latin-1")  # fallback for Windows-encoded files
    
    if not text.strip():
        raise ValueError(f"[ingest_doc] TXT file is empty: {filepath.name}")
    
    return text
```

---

## 2. Argparse CLI Pattern

### Standard `python -m module` Pattern
The existing `ingest.py` uses `if __name__ == "__main__": asyncio.run(ingest())`. Same pattern for both new scripts.

### ingest_doc.py CLI Interface
```python
import argparse
import asyncio
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser(
        description="Ingest a single PDF or TXT policy document into Qdrant.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m backend.ingestion.ingest_doc policy.pdf --title "Google Privacy Policy"
  python -m backend.ingestion.ingest_doc policy.txt --title "ACME Terms" --dry-run
        """,
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Path to the PDF or TXT file to ingest",
    )
    parser.add_argument(
        "--title",
        required=True,
        help="Document title used as source_doc in Qdrant payload (e.g. 'Google Privacy Policy'). "
             "This value becomes the Phase 9 source filter key.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be ingested (chunk count, dedup hits) without writing to Qdrant.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
```

### validate_corpus.py CLI Interface
```python
if __name__ == "__main__":
    asyncio.run(main())
    # No arguments — validates entire 'policies' collection
```

---

## 3. Qdrant Dedup Check for Dry-Run (UUID5 Existence)

### Key Insight
The existing pipeline already produces deterministic UUID5 point IDs:
```python
id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{passage_id}:{chunk_index}"))
```

For ingest_doc.py: `passage_id = filepath.stem` (e.g., `"google-privacy-policy"`), so IDs are fully deterministic given the same filename. This lets us check existence without storing a separate hash field.

### Dry-Run Dedup Check Pattern
```python
async def check_existing_ids(qdrant: AsyncQdrantClient, point_ids: list[str]) -> set[str]:
    """Return set of point IDs that already exist in Qdrant."""
    # retrieve() fetches only found points — missing IDs are simply absent from the response
    found = await qdrant.retrieve(
        collection_name=COLLECTION_NAME,
        ids=point_ids,
        with_payload=False,
        with_vectors=False,
    )
    return {str(record.id) for record in found}
```

Usage in dry-run:
```python
all_ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{chunk.passage_id}:{chunk.chunk_index}")) for chunk in chunks]
existing_ids = await check_existing_ids(qdrant, all_ids)
new_count = len(all_ids) - len(existing_ids)
print(f"[dry_run] Would ingest {new_count} chunks ({len(existing_ids)} already indexed — would skip)")
```

**Why UUID5 over hash-based scroll:**
- UUID5 lookup is O(1) per batch via `retrieve()` — no full scroll needed
- Deterministic from `passage_id:chunk_index` — same file always produces same IDs
- Matches what the actual upsert would write — no divergence between check and write

### Actual Upsert (Same as ingest.py)
```python
points = [
    PointStruct(
        id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{chunk.passage_id}:{chunk.chunk_index}")),
        vector=embedding,
        payload={
            "title": title,        # from --title arg
            "source_doc": title,   # same as title — used for Phase 9 source filter
            "passage_id": chunk.passage_id,  # filename stem
            "text": chunk.text,
            "chunk_index": chunk.chunk_index,
            "token_count": chunk.token_count,
            "file_type": file_type,  # "pdf" or "txt" — new field
        },
    )
    for chunk, embedding in zip(chunks_in_batch, embeddings)
]
```

SHA-256 content-hash dedup is also preserved: before building the work queue, filter out chunks whose UUID5 already exists in Qdrant. This prevents re-embedding chunks that are already stored (both for live upsert and dry-run reporting).

---

## 4. Qdrant Scroll API (validate_corpus.py)

### qdrant-client 1.17.1 Scroll Signature
```python
records, next_offset = await qdrant.scroll(
    collection_name: str,
    scroll_filter: Optional[Filter] = None,
    limit: int = 10,
    offset: Optional[PointId] = None,     # None = start from beginning
    with_payload: bool | list[str] = True,
    with_vectors: bool | list[str] = False,
)
# Returns: Tuple[list[Record], Optional[PointId]]
# next_offset is None when the last page is reached
```

### Full Corpus Scan Pattern
```python
async def scroll_all(qdrant: AsyncQdrantClient, collection: str) -> list[Record]:
    records = []
    offset = None
    while True:
        batch, next_offset = await qdrant.scroll(
            collection_name=collection,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        records.extend(batch)
        if next_offset is None:
            break
        offset = next_offset
    return records
```

### Fast Count (No Scroll)
```python
count_result = await qdrant.count(collection_name=COLLECTION_NAME, exact=True)
total = count_result.count
```

### validate_corpus.py Report Structure
```python
async def main():
    # 1. Total count (fast path — no scroll)
    total = (await qdrant.count(COLLECTION_NAME, exact=True)).count
    print(f"\n[total] {total} passages in '{COLLECTION_NAME}'")

    # 2. Scroll all for per-source breakdown + anomaly detection
    all_records = await scroll_all(qdrant, COLLECTION_NAME)
    
    # 3. Per-source breakdown
    from collections import Counter
    source_counts = Counter(r.payload.get("source_doc", "<missing>") for r in all_records)
    print("\n[sources]")
    for source, count in source_counts.most_common():
        print(f"  {count:>6}  {source}")

    # 4. Sample metadata rows (first 5)
    print("\n[sample] First 5 records:")
    for record in all_records[:5]:
        p = record.payload
        print(f"  id={record.id} | source={p.get('source_doc')} | passage_id={p.get('passage_id')} | "
              f"chunk={p.get('chunk_index')} | tokens={p.get('token_count')}")

    # 5. Anomaly flags
    REQUIRED_FIELDS = {"title", "source_doc", "text", "passage_id", "chunk_index", "token_count"}
    anomalies = {
        "zero_length_text": [],
        "missing_fields": [],
        "token_count_zero": [],
        "token_count_over_500": [],
    }
    for record in all_records:
        p = record.payload
        missing = REQUIRED_FIELDS - set(p.keys())
        if missing:
            anomalies["missing_fields"].append((record.id, missing))
        text = p.get("text", "")
        if not text.strip():
            anomalies["zero_length_text"].append(record.id)
        tc = p.get("token_count", 0)
        if tc == 0:
            anomalies["token_count_zero"].append(record.id)
        elif tc > 500:
            anomalies["token_count_over_500"].append(record.id)
    
    print("\n[anomalies]")
    total_anomalies = 0
    for key, items in anomalies.items():
        if items:
            print(f"  {key}: {len(items)} — first example: {items[0]}")
            total_anomalies += len(items)
    if total_anomalies == 0:
        print("  none — corpus looks healthy")
```

---

## 5. File Structure and Module Layout

### New Files
```
backend/ingestion/
  ingest.py          ← existing, unchanged
  chunker.py         ← existing, unchanged
  ingest_doc.py      ← NEW: single-document ingest CLI (CORP-01)
  validate_corpus.py ← NEW: corpus validation CLI (CORP-02)
```

### Shared Utilities (Import from ingest.py)
- `embed_batch()` — import directly
- `ensure_collection()` — call at startup
- `probe_embedding_dim()` — call at startup
- `COLLECTION_NAME`, `BATCH_SIZE`, `BATCH_SLEEP_SECONDS`, `EMBED_MODEL` — reuse as constants

**Important:** `ingest.py` currently initializes `openrouter` and `qdrant` clients at module level (lines 55–67). Importing from `ingest.py` would trigger these module-level initializations. Two options:
1. **Factor out** — move reusable functions (embed_batch, probe_embedding_dim, ensure_collection) to a `_shared.py` module. Cleaner but requires refactoring ingest.py.
2. **Duplicate** — copy the needed functions into `ingest_doc.py`. Avoids touching ingest.py but duplicates ~40 lines.

**Recommendation: Option 1 (factor out to `_shared.py`)**. The module-level client initialization in ingest.py is a known anti-pattern when importing — it would try to load settings (and require .env) just from `import`. A shared module with functions (not module-level clients) is cleaner.

### Alternative: Keep It Self-Contained
If factoring out is deemed too risky for a small phase, `ingest_doc.py` can initialize its own clients identically to `ingest.py` (same 10 lines). validate_corpus.py similarly. The code duplication is small and isolated.

**Decision deferred to planner** — either approach is valid; planner picks based on risk preference.

---

## 6. Wave Structure Recommendation

**Wave 1 (parallel — no dependencies between them):**
- Plan 1: `ingest_doc.py` — covers CORP-01
- Plan 2: `validate_corpus.py` — covers CORP-02

Both scripts connect to the same Qdrant collection. validate_corpus.py works with whatever data is already there — no dependency on ingest_doc.py being written first (existing data from ingest.py is sufficient to test validate_corpus).

**If the planner prefers sequential:** Plan 1 (Wave 1) → Plan 2 (Wave 2, depends on Plan 1) is also valid and makes it easier to test validate_corpus after ingest_doc.

---

## 7. Technical Risks and Landmines

| Risk | Severity | Mitigation |
|------|----------|-----------|
| `ingest.py` module-level client init breaks imports | HIGH | Factor to `_shared.py` or self-contained clients in each script |
| pypdf `extract_text()` returns `""` (not `None`) in v5+ | MEDIUM | Use `or ""` guard to handle both cases safely |
| Qdrant scroll returns `(records, next_offset)` tuple — not just records | MEDIUM | Always unpack: `records, next_offset = await qdrant.scroll(...)` |
| `qdrant.count()` with `exact=False` may undercount | LOW | Always pass `exact=True` for accurate corpus count |
| UUID5 dedup ties to filename — renaming file = new IDs | LOW | Document in CLI help: "re-ingesting under different --title or filename creates new entries" |
| PDF with password but `is_encrypted=True` even with empty password | LOW | Check `is_encrypted` before reading; raise clear error |

---

## 8. Validation Architecture (Nyquist)

### CORP-01 Validation
```
# Ingest a test document
python -m backend.ingestion.ingest_doc tests/fixtures/sample_policy.pdf --title "Test Policy"
# → Expect: "upserted=N" in output

# Re-run on same document
python -m backend.ingestion.ingest_doc tests/fixtures/sample_policy.pdf --title "Test Policy"
# → Expect: "Would ingest 0 new chunks" or upserted=0

# Dry-run
python -m backend.ingestion.ingest_doc tests/fixtures/sample_policy.pdf --title "Test Policy" --dry-run
# → Expect: "[dry_run] Would ingest N chunks (M already indexed — would skip)" with no Qdrant write
```

### CORP-02 Validation
```
python -m backend.ingestion.validate_corpus
# → Expect output containing:
#   [total] N passages in 'policies'
#   [sources] with at least one source line
#   [sample] First 5 records with id/source/passage_id/chunk/tokens fields
#   [anomalies] (none OR specific counts)
```

### No pytest fixture required — CLI integration tests run against live Qdrant (same as ingest.py pattern).

---

## RESEARCH COMPLETE

**Key findings for planner:**
1. pypdf v5+ API is simple: `PdfReader(path)` → iterate pages → `extract_text()` → concatenate with `\n\n`
2. Dry-run dedup uses UUID5 existence check via `qdrant.retrieve()` — no scroll, no hash storage
3. validate_corpus.py uses `qdrant.count(exact=True)` + `qdrant.scroll()` pagination
4. Module-level clients in `ingest.py` prevent clean imports — planner should choose: factor to `_shared.py` or self-contained clients
5. Wave 1 for both plans (parallel) is recommended
6. Add `pypdf` to `requirements.txt` — pure Python, no Dockerfile change needed

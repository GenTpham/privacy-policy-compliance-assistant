---
id: 01-PLAN-04
wave: 3
depends_on:
  - 01-PLAN-03
phase: 01-infrastructure-data-ingestion
goal: Text chunker and full ingestion pipeline with dedup, checkpoint, rate-limit backoff, and sanity check
files_modified:
  - backend/ingestion/chunker.py
  - backend/ingestion/ingest.py
autonomous: true
requirements:
  - INGEST-01
  - INGEST-02
  - INGEST-03
  - INGEST-04
  - INGEST-05
  - INGEST-06
---

<objective>
Implement the text chunker (400-token target, 50-token overlap, semantic separators, metadata propagation) and the full ingestion pipeline (parse → validate → dedup → embed → upsert → checkpoint → sanity check). This is the core of Phase 1.

Purpose: After this plan executes, `python -m backend.ingestion.ingest` will read the 17K-passage train corpus, embed all passages via Nemotron on OpenRouter, upsert them into Qdrant with correct metadata, write a resumable checkpoint, and run a post-ingestion sanity check asserting the first passage ranks #1 with score > 0.99.
Output: chunker.py (text splitting logic) and ingest.py (full ingestion entry point).
</objective>

<execution_context>
@D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-AI-SPEC.md
</execution_context>

<context>
@D:\data\code\privacy-policy-compliance-assistant\.planning\ROADMAP.md
@D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-CONTEXT.md
@D:\data\code\privacy-policy-compliance-assistant\.planning\research\PITFALLS.md
@D:\data\code\privacy-policy-compliance-assistant\.planning\research\ARCHITECTURE.md

<interfaces>
<!-- From config.py (Plan 03 output): -->
<!--   from backend.app.core.config import get_settings -->
<!--   settings.openrouter_api_key: str -->
<!--   settings.qdrant_host: str (default "localhost") -->
<!--   settings.qdrant_port: int (default 6333) -->
<!--   settings.qdrant_api_key: str | None -->
<!--
<!-- Dataset record shape (confirmed from dataset/json/train/policy_qa_train.json): -->
<!--   {"id": str, "title": str, "context": str, "question": str, "answers": {...}} -->
<!--   The "context" field is the passage to embed and index. -->
<!--   The "title" field is the source document identifier. -->
<!--
<!-- From AI-SPEC §3 Entry Point Pattern (reference implementation): -->
<!--   COLLECTION_NAME = "policies" -->
<!--   BATCH_SIZE = 50  (D-04) -->
<!--   DATASET_PATH = Path("dataset/json/train/policy_qa_train.json")  (D-01) -->
<!--   CHECKPOINT_PATH = Path("ingestion_checkpoint.json") (D-03) -->
<!--
<!-- From AI-SPEC §4 Context Window Strategy — chunking: -->
<!--   Target: 400 tokens, overlap: 50 tokens -->
<!--   Separators: ["\n\n", "\n", ". ", " "] -->
<!--   Atomic units: numbered list items, table rows -->
<!--   Required payload fields: title, source_doc, passage_id, text, chunk_index -->
<!--
<!-- From AI-SPEC §6 Guardrails: -->
<!--   Dimension mismatch hard stop: if existing collection dim != probed dim → RuntimeError -->
<!--   Distance metric guard: if distance != COSINE → RuntimeError -->
<!--   Upsert failure hard stop: if status != COMPLETED → RuntimeError -->
<!--   Empty corpus guard: 0 valid passages → ValueError -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create backend/ingestion/chunker.py</name>
  <files>backend/ingestion/chunker.py</files>
  <read_first>
    - D:\data\code\privacy-policy-compliance-assistant\.planning\research\ARCHITECTURE.md (Chunking Strategy section)
    - D:\data\code\privacy-policy-compliance-assistant\.planning\research\PITFALLS.md (C3 — chunking destroys legal clause coherence)
    - D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-AI-SPEC.md (§4 Context Window Strategy — chunking decisions table; §4b.4 chunk parameters)
    - D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-CONTEXT.md (Claude's Discretion section — chunking logic)
  </read_first>
  <action>
Create `backend/ingestion/chunker.py`. The chunker takes a passage text + its metadata and returns a list of chunk dicts. For the privacy policy dataset, most `context` fields are already single passages (80–400 words) that fit within the 400-token target — the chunker only splits passages that exceed 450 tokens.

Key implementation requirements from AI-SPEC §4 and ARCHITECTURE.md:
- Token target: 400 tokens (tiktoken cl100k_base)
- Overlap: 50 tokens
- Separator priority order: `["\n\n", "\n", ". ", " "]` — always split at paragraph boundary first
- Atomic units: numbered/lettered list items (`1.`, `a)`, `(a)`) and table rows must NOT be split mid-item
- Every chunk carries metadata: `title`, `source_doc`, `text`, `chunk_index`, `passage_id`
- `source_doc` is set to `title` (from dataset record) — this is what Phase 2 uses for citations

```python
"""
backend/ingestion/chunker.py
Text splitting for privacy policy passages.
Splits passages exceeding MAX_TOKENS into semantically coherent chunks.
Most dataset passages fit within MAX_TOKENS and are returned as a single chunk.
"""
import re
from dataclasses import dataclass, field
from typing import Any

import tiktoken

MAX_TOKENS = 400      # target chunk size (AI-SPEC §4 Context Window Strategy)
OVERLAP_TOKENS = 50   # ~12.5% overlap — preserves clause continuity at boundaries
SEPARATORS = ["\n\n", "\n", ". ", " "]  # priority order — paragraph → sentence → word

_enc = tiktoken.get_encoding("cl100k_base")


@dataclass
class Chunk:
    text: str
    title: str
    source_doc: str
    passage_id: str
    chunk_index: int
    token_count: int


def _count_tokens(text: str) -> int:
    return len(_enc.encode(text))


def _split_by_separator(text: str, separator: str) -> list[str]:
    """Split text by separator, keeping separators at end of left part (preserve structure)."""
    if separator == " ":
        return text.split()
    parts = text.split(separator)
    # Re-attach the separator to the end of each part except the last
    return [p + separator for p in parts[:-1]] + [parts[-1]] if len(parts) > 1 else [text]


def _is_list_item_start(text: str) -> bool:
    """
    Detect if text begins a numbered/lettered list item.
    Atomic unit rule: list items must not be split from their context.
    """
    return bool(re.match(r"^\s*(\d+\.|[a-z]\)|[a-z]\.|[(][a-z][)]|\*|\-)\s", text, re.IGNORECASE))


def chunk_passage(
    text: str,
    passage_id: str,
    title: str,
    source_doc: str,
) -> list[Chunk]:
    """
    Split a passage into chunks respecting token limits and semantic boundaries.
    If the passage fits within MAX_TOKENS, returns a single chunk (most dataset records).
    """
    token_count = _count_tokens(text)

    # Fast path: passage fits in one chunk — most dataset records take this path
    if token_count <= MAX_TOKENS:
        return [
            Chunk(
                text=text.strip(),
                title=title,
                source_doc=source_doc,
                passage_id=passage_id,
                chunk_index=0,
                token_count=token_count,
            )
        ]

    # Slow path: split long passages using separator hierarchy
    chunks: list[Chunk] = []
    chunk_index = 0
    remaining = text.strip()

    while remaining:
        # Try each separator in priority order to find a split point within MAX_TOKENS
        split_done = False
        for sep in SEPARATORS:
            if sep not in remaining:
                continue
            parts = _split_by_separator(remaining, sep)
            current: list[str] = []
            current_tokens = 0

            for part in parts:
                part_tokens = _count_tokens(part)
                if current_tokens + part_tokens <= MAX_TOKENS:
                    current.append(part)
                    current_tokens += part_tokens
                else:
                    if current:
                        chunk_text = "".join(current).strip()
                        if chunk_text:
                            chunks.append(
                                Chunk(
                                    text=chunk_text,
                                    title=title,
                                    source_doc=source_doc,
                                    passage_id=passage_id,
                                    chunk_index=chunk_index,
                                    token_count=_count_tokens(chunk_text),
                                )
                            )
                            chunk_index += 1

                            # Compute overlap: take last OVERLAP_TOKENS of current chunk
                            overlap_parts: list[str] = []
                            overlap_tok = 0
                            for prev_part in reversed(current):
                                pt = _count_tokens(prev_part)
                                if overlap_tok + pt <= OVERLAP_TOKENS:
                                    overlap_parts.insert(0, prev_part)
                                    overlap_tok += pt
                                else:
                                    break
                            current = overlap_parts + [part]
                            current_tokens = overlap_tok + part_tokens
                    else:
                        # Single part exceeds MAX_TOKENS — force it as a chunk
                        chunk_text = part.strip()
                        if chunk_text:
                            chunks.append(
                                Chunk(
                                    text=chunk_text,
                                    title=title,
                                    source_doc=source_doc,
                                    passage_id=passage_id,
                                    chunk_index=chunk_index,
                                    token_count=_count_tokens(chunk_text),
                                )
                            )
                            chunk_index += 1
                        current = []
                        current_tokens = 0

            # Flush remaining
            if current:
                chunk_text = "".join(current).strip()
                if chunk_text:
                    chunks.append(
                        Chunk(
                            text=chunk_text,
                            title=title,
                            source_doc=source_doc,
                            passage_id=passage_id,
                            chunk_index=chunk_index,
                            token_count=_count_tokens(chunk_text),
                        )
                    )
                    chunk_index += 1
            remaining = ""
            split_done = True
            break

        if not split_done:
            # No separators found — treat entire remaining as one chunk
            chunk_text = remaining.strip()
            if chunk_text:
                chunks.append(
                    Chunk(
                        text=chunk_text,
                        title=title,
                        source_doc=source_doc,
                        passage_id=passage_id,
                        chunk_index=chunk_index,
                        token_count=_count_tokens(chunk_text),
                    )
                )
            remaining = ""

    return chunks if chunks else [
        Chunk(
            text=text.strip(),
            title=title,
            source_doc=source_doc,
            passage_id=passage_id,
            chunk_index=0,
            token_count=_count_tokens(text),
        )
    ]
```
  </action>
  <verify>
    <automated>grep "MAX_TOKENS = 400" D:/data/code/privacy-policy-compliance-assistant/backend/ingestion/chunker.py && grep "OVERLAP_TOKENS = 50" D:/data/code/privacy-policy-compliance-assistant/backend/ingestion/chunker.py && grep "SEPARATORS = " D:/data/code/privacy-policy-compliance-assistant/backend/ingestion/chunker.py && grep "source_doc" D:/data/code/privacy-policy-compliance-assistant/backend/ingestion/chunker.py && grep "chunk_index" D:/data/code/privacy-policy-compliance-assistant/backend/ingestion/chunker.py</automated>
  </verify>
  <done>chunker.py defines chunk_passage() returning list[Chunk]. MAX_TOKENS=400, OVERLAP_TOKENS=50, SEPARATORS=["\n\n", "\n", ". ", " "]. Every Chunk has text, title, source_doc, passage_id, chunk_index, token_count fields.</done>
</task>

<task type="auto">
  <name>Task 2: Create backend/ingestion/ingest.py</name>
  <files>backend/ingestion/ingest.py</files>
  <read_first>
    - D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-AI-SPEC.md (§3 Entry Point Pattern — full reference implementation; §4 Implementation Guidance; §6 Guardrails)
    - D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-CONTEXT.md (D-01 through D-14 — all decisions apply here)
    - D:\data\code\privacy-policy-compliance-assistant\.planning\research\PITFALLS.md (C6 token truncation; M7 rate limits)
    - D:\data\code\privacy-policy-compliance-assistant\backend\ingestion\chunker.py (Chunk dataclass and chunk_passage() signature)
    - D:\data\code\privacy-policy-compliance-assistant\backend\app\core\config.py (get_settings() signature)
  </read_first>
  <action>
Create `backend/ingestion/ingest.py`. This is the full ingestion entry point implementing all decisions from CONTEXT.md D-01 through D-14. Follow the AI-SPEC §3 Entry Point Pattern exactly, extended with the Pydantic corpus validation from AI-SPEC §4b.1.

Implement these components in order:

**Constants (top of file):**
```python
COLLECTION_NAME = "policies"
BATCH_SIZE = 50             # D-04: conservative for OpenRouter free-tier
MAX_TOKENS_WARN = 400       # C6 guard: warn before embedding over-long passages
CHECKPOINT_PATH = Path("ingestion_checkpoint.json")  # D-03
DATASET_PATH = Path("dataset/json/train/policy_qa_train.json")  # D-01 train split only
EMBED_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2"
BATCH_SLEEP_SECONDS = 3     # polite delay — respects free-tier 20 req/min
```

**Pydantic corpus record validator** (AI-SPEC §4b.1):
```python
from pydantic import BaseModel, field_validator

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
```

**Client initialization** (module level, after settings load):
- `AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=settings.openrouter_api_key, default_headers={...})`
- `AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port, api_key=settings.qdrant_api_key)`

**`probe_embedding_dim()` function** (AI-SPEC §3 pattern, exactly):
- One API call with `input="probe"`
- Returns `len(resp.data[0].embedding)` — never hardcoded

**`ensure_collection(dim: int)` function** (D-08, D-09, D-10):
- Check existing collections; skip if `COLLECTION_NAME` already in set
- Create with `VectorParams(size=dim, distance=Distance.COSINE)`
- Post-creation guard: `get_collection()` → assert `distance == Distance.COSINE` → raise RuntimeError if not (AI-SPEC §6 guardrail)
- **Dimension mismatch guard** (AI-SPEC §6): if collection already exists, compare `info.config.params.vectors.size` to `dim` — raise RuntimeError if mismatch

**`load_checkpoint()` / `save_checkpoint()` functions** (D-03):
- load: reads `ingestion_checkpoint.json` → returns `set[str]` of completed hashes; returns empty set if file missing
- save: writes `{"completed_hashes": list(completed)}` after every confirmed batch

**`embed_batch(texts, retries=5)` async function** (D-04, D-05, INGEST-05):
- Calls `openrouter.embeddings.create(model=EMBED_MODEL, input=texts)`
- Returns `[item.embedding for item in sorted(resp.data, key=lambda x: x.index)]`
- Exponential backoff on 429: `wait = 2 ** attempt` seconds, print `[rate_limit]`, `await asyncio.sleep(wait)`
- After `retries` exhausted: `raise RuntimeError(f"embed_batch failed after {retries} retries")`

**`ingest()` async function** — main loop:
1. `dim = await probe_embedding_dim()`
2. `await ensure_collection(dim)`
3. Load + parse dataset JSON from `DATASET_PATH` — validate each record with `PolicyPassage(**raw)`; count skipped
4. Empty corpus guard: if 0 valid passages after validation → `raise ValueError("No valid passages found...")`
5. Build work queue: for each valid passage, call `chunk_passage(record.context, str(record.id), record.title, record.title)` to get chunks; SHA-256 hash each chunk's text for dedup (D-02)
6. Skip chunks whose hash is in `completed_hashes` (checkpoint resumability, D-03) or in `seen` set (intra-run dedup, D-02)
7. C6 guard: for each chunk, if `_count_tokens(chunk.text) > MAX_TOKENS_WARN` → print `[warn]` with chunk id and token count
8. Batch the queue in groups of `BATCH_SIZE`; for each batch:
   a. `embeddings = await embed_batch([c.text for c in batch])`
   b. Build `PointStruct` list — id must be a deterministic UUID derived from `chunk.passage_id + str(chunk.chunk_index)` using `uuid.uuid5(uuid.NAMESPACE_DNS, ...)` to ensure stable IDs across re-runs
   c. `result = await qdrant.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)` (D-04 `wait=True`)
   d. Upsert failure guard: if `result.status != UpdateStatus.COMPLETED` → `raise RuntimeError(...)` (AI-SPEC §6 guardrail)
   e. Add batch hashes to `completed_hashes` → `save_checkpoint(completed_hashes)` (checkpoint AFTER confirmed write, D-03)
   f. Print progress: `[ingest] Batch N: X/total upserted.`
   g. `await asyncio.sleep(BATCH_SLEEP_SECONDS)` (M7 rate limit respect)
9. `await sanity_check()`

**`sanity_check()` async function** (INGEST-06):
- Load first record from `DATASET_PATH`
- `vecs = await embed_batch([first_text])`
- `results = await qdrant.search(collection_name=COLLECTION_NAME, query_vector=vecs[0], limit=1, with_payload=True)`
- `assert results[0].score > 0.99` — raise `AssertionError` with descriptive message if it fails

**Entry point:**
```python
if __name__ == "__main__":
    asyncio.run(ingest())
```

Run as: `python -m backend.ingestion.ingest` from project root (not `python backend/ingestion/ingest.py` — requires proper module resolution for `from backend.app.core.config import get_settings`).

Log summary line after all batches: `[ingest_summary] passages_loaded=X deduped=Y skipped_empty=Z skipped_checkpoint=W upserted=V token_warnings=U`
  </action>
  <verify>
    <automated>grep "BATCH_SIZE = 50" D:/data/code/privacy-policy-compliance-assistant/backend/ingestion/ingest.py && grep "wait=True" D:/data/code/privacy-policy-compliance-assistant/backend/ingestion/ingest.py && grep "save_checkpoint" D:/data/code/privacy-policy-compliance-assistant/backend/ingestion/ingest.py && grep "sanity_check" D:/data/code/privacy-policy-compliance-assistant/backend/ingestion/ingest.py && grep "score > 0.99" D:/data/code/privacy-policy-compliance-assistant/backend/ingestion/ingest.py && grep "Distance.COSINE" D:/data/code/privacy-policy-compliance-assistant/backend/ingestion/ingest.py && grep "UpdateStatus.COMPLETED" D:/data/code/privacy-policy-compliance-assistant/backend/ingestion/ingest.py</automated>
  </verify>
  <done>ingest.py: BATCH_SIZE=50, upsert(wait=True), save_checkpoint() after each batch, sanity_check() asserts score>0.99, dimension mismatch guard, distance metric guard, upsert failure hard stop, empty corpus guard. Entry point is `if __name__ == "__main__": asyncio.run(ingest())`.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| ingest.py → OpenRouter API | Embedding calls carry OPENROUTER_API_KEY; outbound HTTPS only |
| ingest.py → Qdrant REST | Write access to the policies collection; runs on localhost in local dev |
| dataset/json/ → ingest.py | Input corpus — read-only; no user-supplied content in Phase 1 |
| ingestion_checkpoint.json → ingest.py | Checkpoint file is read/written by the script; gitignored |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-04-01 | Information Disclosure | OPENROUTER_API_KEY in ingest.py | mitigate | Key loaded via `get_settings()` from .env — never hardcoded in source; not logged |
| T-04-02 | Tampering | ingestion_checkpoint.json corruption | accept | Checkpoint is regenerated on re-run with `--force` or by deleting the file; not a security surface — contains only SHA-256 hashes of text content |
| T-04-03 | Denial of Service | OpenRouter 429 rate limiting during bulk ingest | mitigate | Exponential backoff (2^attempt seconds, max 5 retries); 3s inter-batch sleep; script raises RuntimeError after 5 retries so operator can investigate and resume via checkpoint |
| T-04-04 | Tampering | Wrong Qdrant collection dimension after partial re-run | mitigate | Dimension mismatch guard in ensure_collection: if existing collection dim != probed dim → RuntimeError before any upsert (AI-SPEC §6 guardrail) |
| T-04-05 | Information Disclosure | corpus text in Qdrant payload | accept | Qdrant runs locally in Docker with optional API key; payload text is the same data as the source JSON corpus — no additional sensitivity introduced by indexing |
| T-04-06 | Spoofing | Malformed dataset JSON injecting unexpected fields | mitigate | PolicyPassage Pydantic validator strips unexpected fields; `context_not_empty` validator rejects empty passages; id field cast to str |
</threat_model>

<verification>
After Plan 04 completes:
- `grep "DATASET_PATH.*train" backend/ingestion/ingest.py` confirms train split only (D-01)
- `grep "sha256" backend/ingestion/ingest.py` confirms SHA-256 deduplication (D-02)
- `grep "save_checkpoint\|load_checkpoint" backend/ingestion/ingest.py` shows checkpoint functions (D-03)
- `grep "BATCH_SIZE = 50" backend/ingestion/ingest.py` confirms batch size (D-04)
- `grep "wait=True" backend/ingestion/ingest.py` confirms upsert confirmation before checkpoint (AI-SPEC §6)
- `grep "0.99" backend/ingestion/ingest.py` confirms sanity check threshold (INGEST-06)
- `python -c "from backend.ingestion.chunker import chunk_passage, Chunk"` resolves without error
</verification>

<success_criteria>
- chunker.py: chunk_passage() returns list[Chunk] with title, source_doc, passage_id, chunk_index, text, token_count; MAX_TOKENS=400, OVERLAP_TOKENS=50
- ingest.py: reads dataset/json/train/policy_qa_train.json (train split only, D-01)
- ingest.py: deduplicates by SHA-256 hash of context text (D-02)
- ingest.py: writes ingestion_checkpoint.json after each confirmed batch; resumes on re-run (D-03)
- ingest.py: batch size 50, exponential backoff on 429, 3s inter-batch sleep (D-04, INGEST-05)
- ingest.py: upsert(wait=True), raises RuntimeError if status != COMPLETED
- ingest.py: sanity_check() embeds first passage, asserts score > 0.99 (INGEST-06)
- ingest.py: all 5 required guardrails (empty corpus, dimension mismatch, distance metric, upsert failure, API key validation)
</success_criteria>

<output>
After completion, create `.planning/phases/01-infrastructure-data-ingestion/01-04-SUMMARY.md` with:
- Files created and key function signatures
- Chunker parameters (MAX_TOKENS, OVERLAP_TOKENS, SEPARATORS)
- Ingestion pipeline decisions implemented (list D-01 through D-14 with confirmation)
- Any deviations from the plan and why
</output>

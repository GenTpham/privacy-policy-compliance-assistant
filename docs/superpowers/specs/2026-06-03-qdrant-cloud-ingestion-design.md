---
title: Qdrant Cloud Ingestion
date: 2026-06-03
status: proposed
---

## Summary
Update the ingestion script to connect to Qdrant Cloud using `QDRANT_URL` and `QDRANT_API_KEY`. Ingestion will fail fast if either value is missing, ensuring all ingested vectors are stored on cloud Qdrant.

## Goals
- Ingestion uses a full Qdrant URL (`QDRANT_URL`) and API key (`QDRANT_API_KEY`).
- No silent fallback to host/port for ingestion.
- Keep the rest of the ingestion pipeline unchanged.

## Non-Goals
- Changing the runtime Qdrant configuration for the FastAPI app.
- Supporting dual-mode ingestion (URL or host/port).

## Approach
### Configuration
- Add `qdrant_url: str | None = None` to `Settings` (env: `QDRANT_URL`).
- Keep existing `qdrant_host`, `qdrant_port`, and `qdrant_api_key` for other runtime paths.

### Ingestion Client Initialization
- In `backend/ingestion/ingest.py`, validate:
  - `settings.qdrant_url` is present.
  - `settings.qdrant_api_key` is present.
- Initialize Qdrant with:
  - `AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)`

### Documentation
- Update ingestion instructions to reference `QDRANT_URL` and `QDRANT_API_KEY` as required for cloud ingestion.

## Data Flow
1. Load settings.
2. Validate `QDRANT_URL` and `QDRANT_API_KEY`.
3. Connect to Qdrant Cloud using the URL and API key.
4. Probe embedding dimension, ensure collection, embed, upsert, checkpoint, and sanity check.

## Error Handling
- Raise a clear error if `QDRANT_URL` or `QDRANT_API_KEY` is missing.
- Avoid fallback behavior that could write to a local or unintended Qdrant instance.

## Testing
- Run existing backend tests and compile checks.
- Manually verify ingestion by running the script with valid cloud credentials.

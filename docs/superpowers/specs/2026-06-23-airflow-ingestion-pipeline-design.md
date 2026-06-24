# Design Spec: Airflow-Driven PDF Ingestion Pipeline

**Date:** 2026-06-23
**Branch:** specs
**Status:** Approved

---

## 1. Overview

Replace the local CLI ingestion pipeline with a fully orchestrated, cloud-native pipeline using self-hosted Airflow on GCE VM. FastAPI acts only as an API gateway — it uploads the PDF to GCS and triggers the DAG, then returns immediately. All heavy processing (OCR, chunking, embedding, graph extraction) is owned by Airflow. Shared state is stored in Cloud SQL Postgres so both FastAPI and Airflow can read/write document status without coupling.

---

## 2. Architecture & Data Flow

```
[User]
  │ POST /api/documents/upload (PDF)
  ▼
[FastAPI — Local Docker]
  │ 1. Validate file (PDF only, max 50MB)
  │ 2. Upload PDF → GCS: uploads/{tenant_id}/{doc_id}/{filename}
  │ 3. INSERT Document (status=processing, source=upload) → Cloud SQL
  │ 4. INSERT IngestionJob (status=queued) → Cloud SQL
  │ 5. POST /api/v1/dags/pdf_ingestion/dagRuns → Airflow REST API
  │    dag_run_id = f"ingest_{job_id}"   ← idempotency key
  │ 6. UPDATE IngestionJob (dag_run_id, airflow_run_url) → Cloud SQL
  │ 7. Return 202 { doc_id, job_id, status: "queued" }
  ▼
[Airflow — GCE VM, CeleryExecutor]
  DAG: pdf_ingestion
  │ T1: download_pdf
  │ T2: extract_text
  │ T3: validate_text
  │ T4: chunk_text
  │   ├── T5: generate_embeddings → upsert_qdrant
  │   └── T6: build_graph         → upsert_neo4j
  └── T8: finalize
  (each task UPDATE ingestion_jobs.current_task → Cloud SQL)
  ▼
[Qdrant Cloud]  [Neo4j Aura]   ← Airflow upserts directly

[User polls status]
  GET /api/documents/{doc_id}/status
  → FastAPI SELECT FROM ingestion_jobs → Cloud SQL
  → { status: "running", current_task: "upsert_qdrant" }
```

**Key design principles:**
- FastAPI has **zero involvement** in ingestion processing — triggers only
- Intermediate large data (text, chunks, graph) flows through **GCS artifacts**
- Vectors are **never written to GCS** — `generate_embeddings` upserts to Qdrant directly
- Cloud SQL is the **single source of truth** for document and job status

---

## 3. DAG Structure

**DAG ID:** `pdf_ingestion`
**Executor:** CeleryExecutor (existing GCE VM setup)
**Trigger:** REST API from FastAPI

### 3.1 Conf Payload (FastAPI → Airflow)

```json
{
  "doc_id": "uuid",
  "user_id": "uuid",
  "tenant_id": "uuid",
  "gcs_path": "gs://bucket/uploads/{tenant_id}/{doc_id}/{filename}",
  "title": "Policy Name",
  "collection": "policies",
  "embedding_model": "nvidia/llama-nemotron-embed-vl-1b-v2:free"
}
```

`embedding_model` and `collection` are passed at runtime — DAG requires no code changes to switch models or target collections.

### 3.2 Task Graph

```
download_pdf
      ↓
extract_text
      ↓
validate_text
      ↓
chunk_text
  ├───────────────────────┐
  ▼                       ▼
generate_embeddings    build_graph
  ↓                       ↓
upsert_qdrant          upsert_neo4j
  └──────────┬────────────┘
             ↓
         finalize
```

`chunk_text` fans out to two parallel branches. `finalize` is the join point — runs only after both `upsert_qdrant` and `upsert_neo4j` succeed.

### 3.3 Task Details

| Task | Input (XCom in) | Output (XCom out) | GCS Artifact | Retry |
|---|---|---|---|---|
| `download_pdf` | `gcs_path` | `local_tmp_path` | — | 3×, 30s delay |
| `extract_text` | `local_tmp_path` | `gcs_text_path` | `text/{doc_id}.txt` | 2×, 60s delay |
| `validate_text` | `gcs_text_path` | `char_count` | — | 1× |
| `chunk_text` | `gcs_text_path` | `gcs_chunks_path` | `chunks/{doc_id}.json` | 2×, 30s delay |
| `generate_embeddings` + `upsert_qdrant` | `gcs_chunks_path`, `embedding_model` | `{"chunk_count": N, "collection": "..."}` | — | 3×, 60s delay |
| `build_graph` | `gcs_chunks_path` | `gcs_graph_path` | `graph/{doc_id}.json` | 3×, 60s delay |
| `upsert_neo4j` | `gcs_graph_path` | — | — | 3×, 30s delay |
| `finalize` | — | — | — | 1× |

**GCS artifact layout:**
```
gs://bucket/
└── processing/
    └── {tenant_id}/
        └── {doc_id}/
            ├── text/{doc_id}.txt
            ├── chunks/{doc_id}.json
            └── graph/{doc_id}.json   # { "entities": [], "relationships": [] }
```

### 3.4 validate_text Guard

```python
if len(text.strip()) < 100:
    raise ValueError(f"Document too short ({len(text.strip())} chars) — may be scanned/image-only PDF")
```

Halts pipeline early before wasting embedding API calls on empty content.

### 3.5 generate_embeddings → upsert_qdrant (In-Memory Pipeline)

Vectors are **never persisted to GCS**. Embed and upsert happen in the same task:

```python
# Pseudocode
chunks = load_from_gcs(gcs_chunks_path)
for batch in batched(chunks, BATCH_SIZE=50):
    embeddings = openrouter.embeddings.create(model=embedding_model, input=[c.text for c in batch])
    points = [PointStruct(id=c.id, vector=emb, payload={...}) for c, emb in zip(batch, embeddings)]
    qdrant_client.upsert(collection_name=collection, points=points)
return {"chunk_count": len(chunks), "collection": collection}
```

This avoids materializing a potentially large float32 matrix (e.g. 1000 chunks × 1536 dims × 4 bytes ≈ 6MB) as a GCS file with no operational benefit.

### 3.6 build_graph Output Schema

```json
{
  "doc_id": "uuid",
  "user_id": "uuid",
  "tenant_id": "uuid",
  "entities": [
    {"id": "uuid", "name": "GDPR Article 17", "type": "Regulation"}
  ],
  "relationships": [
    {"source": "uuid", "target": "uuid", "type": "REFERENCES"}
  ]
}
```

NER + relation extraction run in the same task via OpenRouter (Gemma 4 26B A4B).

### 3.7 Status Lifecycle

```
ingestion_jobs.status:    queued → running → completed | failed
ingestion_jobs.current_task: updated at the START of each task

Task                    current_task value
──────────────────────────────────────────
download_pdf            "download_pdf"
extract_text            "extract_text"
validate_text           "validate_text"
chunk_text              "chunk_text"
generate_embeddings     "generate_embeddings"
build_graph             "build_graph"
upsert_qdrant           "upsert_qdrant"
upsert_neo4j            "upsert_neo4j"
finalize                NULL (job done)
```

**`finalize` task:**
```sql
UPDATE ingestion_jobs
SET status = 'completed', current_task = NULL, completed_at = NOW()
WHERE id = :job_id;

UPDATE documents SET status = 'ready' WHERE id = :doc_id;
```

**`on_failure_callback` (attached to every task):**
```sql
UPDATE ingestion_jobs
SET status = 'failed', failed_task = :task_id,
    error_msg = :truncated_stacktrace, completed_at = NOW()
WHERE id = :job_id;

UPDATE documents SET status = 'failed' WHERE id = :doc_id;
```

---

## 4. FastAPI Changes

### 4.1 DB Models (Cloud SQL — `rag_platform_db`)

```python
class Document(Base):
    __tablename__ = "documents"

    id              = Column(UUID, primary_key=True, default=uuid4)
    user_id         = Column(UUID, ForeignKey("users.id"), nullable=False)
    tenant_id       = Column(UUID, nullable=False)
    title           = Column(String, nullable=False)
    filename        = Column(String, nullable=False)
    gcs_path        = Column(String, nullable=False)
    collection      = Column(String, default="policies")
    embedding_model = Column(String, nullable=False)   # stored for re-index
    status          = Column(String, default="processing")  # processing|ready|failed
    source          = Column(String, default="upload")      # upload|email|sharepoint|s3|gcs
    created_at      = Column(DateTime, default=utcnow)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id              = Column(UUID, primary_key=True, default=uuid4)
    doc_id          = Column(UUID, ForeignKey("documents.id"), nullable=False)
    dag_run_id      = Column(String, nullable=False)
    airflow_run_url = Column(String, nullable=True)   # deep-link to Airflow UI
    status          = Column(String, default="queued")  # queued|running|completed|failed
    current_task    = Column(String, nullable=True)
    retry_count     = Column(Integer, default=0)
    started_at      = Column(DateTime, nullable=True)
    completed_at    = Column(DateTime, nullable=True)
    failed_task     = Column(String, nullable=True)
    error_msg       = Column(Text, nullable=True)
```

`source` enables future ingestion from email, SharePoint, S3, GCS without schema changes.
`embedding_model` stored at ingest time enables re-indexing with a different model later.
`airflow_run_url` enables admin "View in Airflow" deep-link.

### 4.2 Upload Endpoint — Race-Condition-Safe Flow

```
POST /api/documents/upload
  multipart/form-data: { file: PDF, title: str }
  Response: 202 { doc_id, job_id, status: "queued" }

Sequence:
  1. Validate file: PDF only, max 50MB
  2. Generate doc_id, job_id (UUID)
  3. Upload PDF → GCS streaming (upload_from_file)
  4. INSERT Document → Cloud SQL
  5. INSERT IngestionJob (status=queued, dag_run_id=f"ingest_{job_id}") → Cloud SQL
  6. POST /api/v1/dags/pdf_ingestion/dagRuns → Airflow
  7. UPDATE IngestionJob (airflow_run_url) → Cloud SQL
  8. Return 202
```

If Airflow REST API times out at step 6, Document + IngestionJob records already exist (status=`queued`). No silent data loss — stuck jobs are visible and retryable.

Idempotency: `dag_run_id = f"ingest_{job_id}"`. If upload is called twice with the same job_id, Airflow returns 409 — FastAPI catches and returns existing job status.

### 4.3 API Endpoints

```
POST   /api/documents/upload        → 202 { doc_id, job_id, status }
GET    /api/documents/{doc_id}/status → { status, current_task, airflow_run_url, ... }
GET    /api/documents               → paginated list for current_user
DELETE /api/documents/{doc_id}      → 202, async cleanup (Qdrant + Neo4j + GCS)
```

### 4.4 GCS Upload — Streaming

```python
# backend/app/core/gcs_client.py
from google.cloud import storage

def upload_to_gcs(bucket: str, gcs_key: str, file_obj, content_type: str) -> str:
    client = storage.Client()   # ADC — VM Service Account in prod
    blob = client.bucket(bucket).blob(gcs_key)
    blob.upload_from_file(file_obj, content_type=content_type)  # streaming
    return f"gs://{bucket}/{gcs_key}"
```

### 4.5 Airflow Trigger — Idempotent

```python
# backend/app/core/airflow_client.py
async def trigger_dag(dag_id: str, dag_run_id: str, conf: dict) -> str:
    url = f"{settings.airflow_base_url}/api/v1/dags/{dag_id}/dagRuns"
    resp = await client.post(
        url,
        json={"dag_run_id": dag_run_id, "conf": conf},
        auth=(settings.airflow_username, settings.airflow_password),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["dag_run_id"]
```

### 4.6 DB Migration

FastAPI migrates from SQLite → Cloud SQL Postgres:
- Add `asyncpg` driver
- `DATABASE_URL` → `postgresql+asyncpg://user:pass@127.0.0.1:5432/rag_platform_db` (via Auth Proxy)
- Alembic migrations for `documents`, `ingestion_jobs` tables

---

## 5. Secrets & Configuration

### 5.1 Cloud SQL Layout

```
Cloud SQL Instance: privacy-assistant-db
├── airflow_db        ← Airflow metadata only (never touched by app code)
└── rag_platform_db   ← Application data
    ├── users
    ├── documents
    └── ingestion_jobs
```

Connectivity: **Cloud SQL Auth Proxy** on both FastAPI host and GCE VM.
GCE VM auth: **VM Service Account** with Cloud SQL Client role — no JSON key file.

### 5.2 Google Secret Manager — Source of Truth for Secrets

```
Secret Manager
├── openrouter-api-key
├── qdrant-api-key
├── neo4j-password
└── app-db-password
        ▲
        │ runtime fetch
   ┌────┴────┐
   ▼         ▼
FastAPI   Airflow DAG
```

Airflow reads via Secret Manager Backend (Airflow 2.x):
```bash
AIRFLOW__SECRETS__BACKEND=airflow.providers.google.cloud.secrets.secret_manager.CloudSecretManagerBackend
AIRFLOW__SECRETS__BACKEND_KWARGS={"project_id": "your-project-id", "prefix": "airflow"}
```

### 5.3 Airflow Connections (Endpoint Config)

| Conn ID | Type | Notes |
|---|---|---|
| `google_cloud_default` | Google Cloud | ADC via VM Service Account |
| `rag_platform_db` | Postgres | `127.0.0.1:5432/rag_platform_db` via Auth Proxy |
| `qdrant_default` | HTTP | Host: Qdrant Cloud URL; password → Secret Manager |
| `neo4j_default` | HTTP | Host: Neo4j Aura URI; password → Secret Manager |
| `openrouter_default` | HTTP | Host: `https://openrouter.ai`; password → Secret Manager |

### 5.4 Airflow Variables (Non-Secret Config Only)

```python
Variable.get("gcs_bucket")                # "privacy-assistant-uploads"
Variable.get("default_collection")         # "policies"
Variable.get("default_embedding_model")    # "nvidia/llama-nemotron-embed-vl-1b-v2:free"
```

API keys and passwords are **never** stored as Airflow Variables.

### 5.5 Airflow Authentication (FastAPI → Airflow)

| Environment | Mechanism |
|---|---|
| Dev | Basic Auth |
| Production | Identity-Aware Proxy (IAP) — port 8080 not exposed, FastAPI uses OIDC token |

### 5.6 New `.env` Keys

```bash
AIRFLOW_BASE_URL=http://<GCE-VM-IP>:8080
AIRFLOW_USERNAME=admin
AIRFLOW_PASSWORD=...
GCS_BUCKET=privacy-assistant-uploads
DATABASE_URL=postgresql+asyncpg://user:pass@127.0.0.1:5432/rag_platform_db
GCP_PROJECT_ID=your-project-id
```

---

## 6. Final Architecture

```
[User]
  ↓
[FastAPI — Local Docker]       trigger only, no processing
  ↓ upload          ↓ trigger
[GCS]            [Airflow — GCE VM]
                   ├── download_pdf
                   ├── extract_text
                   ├── validate_text
                   ├── chunk_text
                   ├── generate_embeddings → upsert_qdrant ──┐
                   ├── build_graph         → upsert_neo4j ───┤
                   └── finalize                              │
                                                             ▼
                                              [Qdrant Cloud] [Neo4j Aura]

[Cloud SQL rag_platform_db]       [Secret Manager]
├── documents                     ├── openrouter-api-key
└── ingestion_jobs                ├── qdrant-api-key
       ▲                          └── neo4j-password
       │ read/write
  ┌────┴────┐
  ▼         ▼
FastAPI   Airflow DAG
```

---

## 7. Open Questions / Future Work

- **DELETE cleanup:** async background task in FastAPI; may graduate to a dedicated cleanup DAG at scale
- **Re-indexing:** `embedding_model` stored per document enables future `reindex` DAG
- **Multi-source ingestion:** `source` column is schema-ready for email, SharePoint, S3, GCS
- **Retry orchestration:** `retry_count` tracked; retry-trigger UI/automation not yet designed

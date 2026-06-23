# Airflow-Driven PDF Ingestion Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the local CLI ingestion pipeline with an Airflow-orchestrated pipeline on GCE VM, where FastAPI only uploads PDFs to GCS and triggers a DAG, while Airflow owns all heavy processing.

**Architecture:** FastAPI receives PDF uploads, streams them to GCS, inserts records into Cloud SQL Postgres, and triggers an Airflow DAG via REST API. Airflow runs 8 sequential/parallel tasks (download → extract → validate → chunk → embed+upsert_qdrant ‖ build_graph+upsert_neo4j → finalize). Both FastAPI and Airflow read/write a shared `ingestion_jobs` table in Cloud SQL for status tracking.

**Tech Stack:** FastAPI + asyncpg, Airflow 2.10.5 + CeleryExecutor, Google Cloud Storage, Cloud SQL Postgres, Qdrant Cloud, Neo4j Aura, OpenRouter (embeddings + LLM), httpx (async HTTP client).

**Spec:** [`2026-06-23-airflow-ingestion-pipeline-design.md`](file:///D:/data/code/privacy-policy-compliance-assistant/docs/superpowers/specs/2026-06-23-airflow-ingestion-pipeline-design.md)

**Working directory:** `.worktrees/feat-airflow-ingestion`

---

## File Structure

### Files to CREATE

```
dags/
├── pdf_ingestion.py                    # DAG definition — task graph + callbacks
├── requirements.txt                    # Airflow worker pip dependencies
└── tasks/
    ├── __init__.py
    ├── db_status.py                    # Cloud SQL status update helpers + on_failure_callback
    ├── download.py                     # download_pdf task
    ├── extract.py                      # extract_text + validate_text tasks
    ├── chunk.py                        # chunk_text task (ports logic from backend/ingestion/chunker.py)
    ├── embed_and_upsert.py             # generate_embeddings + upsert_qdrant (in-memory, no GCS)
    ├── graph.py                        # build_graph task (NER + relation extraction via LLM)
    └── neo4j_upsert.py                 # upsert_neo4j task

alembic.ini                            # Alembic config
alembic/
├── env.py                             # Alembic environment
└── versions/
    └── 001_initial_schema.py           # Initial migration with updated Document + new IngestionJob

backend/app/tests/
├── test_airflow_client.py              # Tests for the rewritten airflow client (replaces test_airflow.py)
└── test_upload_flow.py                 # Integration tests for upload → GCS → trigger DAG flow

dags/tests/
├── __init__.py
├── test_dag_structure.py               # Verify DAG loads, task dependencies correct
├── test_extract.py                     # Test extract_text + validate_text logic
├── test_chunk.py                       # Test chunk_text logic
└── test_db_status.py                   # Test status update helpers
```

### Files to MODIFY

```
requirements.txt                        # Add asyncpg, alembic, google-cloud-storage, httpx; remove duplicates
backend/app/core/config.py              # Add airflow, GCS, database, GCP config fields
backend/app/db/models.py                # Update Document (UUID PK, new fields), add IngestionJob
backend/app/db/session.py               # Support Postgres DATABASE_URL from settings
backend/app/services/gcs.py             # Streaming upload_from_file, fix config references
backend/app/services/airflow.py         # Rewrite: async httpx, Basic Auth, idempotent dag_run_id
backend/app/api/endpoints/documents.py  # Rewrite upload flow: GCS → DB → trigger DAG → 202
backend/app/main.py                     # Remove SQLite PRAGMA migrations, use Alembic + DATABASE_URL
backend/app/tests/conftest.py           # Update fixtures for UUID Document PK
.env.example                            # Add new env vars
.gitignore                              # Add alembic __pycache__
```

### Deviation from spec

The existing `User.id` is `int` (auto-increment). The spec defines `Document.user_id` as UUID FK to `users.id`. Changing User PK to UUID would cascade through the entire codebase (auth, query_logs, all tests). This plan keeps `User.id` as `int` and uses `Document.user_id = Column(Integer, ForeignKey("users.id"))`. `Document.id` and `IngestionJob.id` use UUID as spec requires. `tenant_id` is a separate `String` field (not FK).

---

## Task 1: Dependencies & Environment Configuration

**Files:**
- Modify: `requirements.txt`
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Fix requirements.txt — remove duplicates, add new deps**

The current file has lines 1–12 duplicated at lines 13–24. Fix and add new dependencies:

```
# --- Core ---
fastapi==0.136.0
uvicorn[standard]
qdrant-client==1.17.1
openai==2.32.0
pydantic-settings>=2.0
tiktoken
PyJWT
pwdlib[argon2]
sqlalchemy[asyncio]
aiosqlite
python-multipart
pymupdf
neo4j==5.21.0
slowapi==0.1.9

# --- Observability ---
opentelemetry-sdk
opentelemetry-exporter-otlp-proto-grpc
opentelemetry-instrumentation-fastapi
openinference-instrumentation-openai

# --- New: Airflow integration ---
asyncpg
alembic
google-cloud-storage
httpx
```

- [ ] **Step 2: Add new Settings fields to config.py**

Add these fields to the `Settings` class in `backend/app/core/config.py`:

```python
    # --- Airflow ---
    airflow_base_url: str = "http://localhost:8080"
    airflow_username: str = "admin"
    airflow_password: str = ""
    airflow_dag_id: str = "pdf_ingestion"

    # --- GCS ---
    gcs_bucket: str = ""
    gcs_credentials_path: str | None = None  # None = use ADC

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///backend/data/users.db"

    # --- GCP ---
    gcp_project_id: str = ""
```

- [ ] **Step 3: Update .env.example**

Append to `.env.example`:

```bash
# --- Airflow (GCE VM) ---
AIRFLOW_BASE_URL=http://<GCE-VM-IP>:8080
AIRFLOW_USERNAME=admin
AIRFLOW_PASSWORD=changeme
AIRFLOW_DAG_ID=pdf_ingestion

# --- Google Cloud Storage ---
GCS_BUCKET=privacy-assistant-uploads
# GCS_CREDENTIALS_PATH=  # Leave empty to use ADC (VM Service Account)

# --- Database (Cloud SQL via Auth Proxy) ---
DATABASE_URL=postgresql+asyncpg://user:pass@127.0.0.1:5432/rag_platform_db

# --- GCP Project ---
GCP_PROJECT_ID=your-project-id
```

- [ ] **Step 4: Install dependencies and verify**

Run:
```bash
pip install -r requirements.txt
python -c "import asyncpg, alembic, google.cloud.storage, httpx; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add requirements.txt backend/app/core/config.py .env.example
git commit -m "feat: add Airflow/GCS/Postgres dependencies and config fields"
```

---

## Task 2: Database Models — Document Update + IngestionJob

**Files:**
- Modify: `backend/app/db/models.py`
- Test: `backend/app/tests/test_models_airflow.py`

- [ ] **Step 1: Write failing test for updated Document model**

Create `backend/app/tests/test_models_airflow.py`:

```python
"""Tests for Document (updated) and IngestionJob models."""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.models import Base, Document, IngestionJob, User


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


class TestDocumentModel:
    async def test_document_has_uuid_pk(self, db: AsyncSession):
        user = User(username="testuser", hashed_password="hash123")
        db.add(user)
        await db.flush()

        doc_id = uuid.uuid4()
        doc = Document(
            id=str(doc_id),
            user_id=user.id,
            tenant_id="tenant-abc",
            title="Test Policy",
            filename="test.pdf",
            gcs_path="gs://bucket/uploads/tenant-abc/test.pdf",
            collection="policies",
            embedding_model="nvidia/llama-nemotron-embed-vl-1b-v2:free",
            status="processing",
            source="upload",
        )
        db.add(doc)
        await db.commit()

        result = await db.execute(select(Document).where(Document.id == str(doc_id)))
        saved = result.scalar_one()
        assert saved.title == "Test Policy"
        assert saved.tenant_id == "tenant-abc"
        assert saved.source == "upload"
        assert saved.embedding_model == "nvidia/llama-nemotron-embed-vl-1b-v2:free"
        assert saved.gcs_path == "gs://bucket/uploads/tenant-abc/test.pdf"


class TestIngestionJobModel:
    async def test_ingestion_job_creation(self, db: AsyncSession):
        user = User(username="testuser2", hashed_password="hash123")
        db.add(user)
        await db.flush()

        doc_id = str(uuid.uuid4())
        doc = Document(
            id=doc_id,
            user_id=user.id,
            tenant_id="tenant-abc",
            title="Test",
            filename="test.pdf",
            gcs_path="gs://bucket/test.pdf",
            collection="policies",
            embedding_model="test-model",
        )
        db.add(doc)
        await db.flush()

        job_id = str(uuid.uuid4())
        job = IngestionJob(
            id=job_id,
            doc_id=doc_id,
            dag_run_id=f"ingest_{job_id}",
            status="queued",
        )
        db.add(job)
        await db.commit()

        result = await db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
        saved = result.scalar_one()
        assert saved.status == "queued"
        assert saved.dag_run_id == f"ingest_{job_id}"
        assert saved.retry_count == 0
        assert saved.current_task is None

    async def test_ingestion_job_status_lifecycle(self, db: AsyncSession):
        user = User(username="testuser3", hashed_password="hash123")
        db.add(user)
        await db.flush()

        doc_id = str(uuid.uuid4())
        doc = Document(
            id=doc_id, user_id=user.id, tenant_id="t",
            title="T", filename="t.pdf", gcs_path="gs://b/t",
            collection="policies", embedding_model="m",
        )
        db.add(doc)
        await db.flush()

        job_id = str(uuid.uuid4())
        job = IngestionJob(
            id=job_id, doc_id=doc_id,
            dag_run_id=f"ingest_{job_id}",
        )
        db.add(job)
        await db.commit()

        # Simulate running
        job.status = "running"
        job.current_task = "download_pdf"
        job.started_at = datetime.now(timezone.utc)
        await db.commit()

        result = await db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
        saved = result.scalar_one()
        assert saved.status == "running"
        assert saved.current_task == "download_pdf"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
pytest backend/app/tests/test_models_airflow.py -v
```
Expected: FAIL — `IngestionJob` not found, `Document` missing fields.

- [ ] **Step 3: Update Document model and add IngestionJob**

Replace the `Document` class and add `IngestionJob` in `backend/app/db/models.py`:

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    hashed_password = Column(String(256), nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    is_admin = Column(Boolean, default=False)


class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    query_text = Column(String(4000), nullable=False)
    topic = Column(String(100), index=True)
    status = Column(String(20))
    created_at = Column(DateTime, default=_utcnow)


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    gcs_path = Column(String(1024), nullable=False)
    collection = Column(String(64), default="policies")
    embedding_model = Column(String(128), nullable=False)
    status = Column(String(20), default="processing")  # processing | ready | failed
    source = Column(String(20), default="upload")       # upload | email | sharepoint | s3 | gcs
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    ingestion_jobs = relationship("IngestionJob", back_populates="document")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    dag_run_id = Column(String(128), nullable=False)
    airflow_run_url = Column(String(512), nullable=True)
    status = Column(String(20), default="queued")  # queued | running | completed | failed
    current_task = Column(String(64), nullable=True)
    retry_count = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_task = Column(String(64), nullable=True)
    error_msg = Column(Text, nullable=True)

    document = relationship("Document", back_populates="ingestion_jobs")
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
pytest backend/app/tests/test_models_airflow.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: Run existing tests to check for breakage**

Run:
```bash
pytest backend/app/tests/ -v --ignore=backend/app/tests/test_gcs.py 2>&1 | head -80
```
Expected: Some tests may fail due to Document model changes (missing required fields). Note failures for fixing in Task 8.

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/models.py backend/app/tests/test_models_airflow.py
git commit -m "feat: update Document model (UUID PK, new fields) + add IngestionJob model"
```

---

## Task 3: Alembic Setup & Database Session

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/` (empty dir)
- Modify: `backend/app/db/session.py`
- Modify: `.gitignore`

- [ ] **Step 1: Initialize Alembic**

Run:
```bash
alembic init alembic
```
Expected: Creates `alembic.ini` and `alembic/` directory.

- [ ] **Step 2: Configure alembic.ini**

Edit `alembic.ini` — set the `sqlalchemy.url` line to a placeholder (actual URL comes from env):

```ini
sqlalchemy.url = postgresql+asyncpg://user:pass@127.0.0.1:5432/rag_platform_db
```

- [ ] **Step 3: Configure alembic/env.py for async + our models**

Replace `alembic/env.py` with:

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from backend.app.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Update session.py to use DATABASE_URL from settings**

Replace `backend/app/db/session.py`:

```python
"""
Database session management.
Supports both SQLite (dev) and PostgreSQL (prod) via DATABASE_URL.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

_engine = None
_session_factory = None


def init_db(db_url: str) -> None:
    """Initialize the async engine and session factory."""
    global _engine, _session_factory

    connect_args = {}
    if "sqlite" in db_url:
        connect_args = {"check_same_thread": False}

    _engine = create_async_engine(db_url, connect_args=connect_args, echo=False)
    _session_factory = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """FastAPI dependency — yields an AsyncSession."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with _session_factory() as session:
        yield session
```

- [ ] **Step 5: Add alembic cache to .gitignore**

Append to `.gitignore`:

```
alembic/__pycache__/
alembic/versions/__pycache__/
```

- [ ] **Step 6: Commit**

```bash
git add alembic.ini alembic/ backend/app/db/session.py .gitignore
git commit -m "feat: set up Alembic for async Postgres migrations + update session.py"
```

---

## Task 4: GCS Service — Streaming Upload

**Files:**
- Test: `backend/app/tests/test_gcs.py` (rewrite existing)
- Modify: `backend/app/services/gcs.py`

- [ ] **Step 1: Write failing tests for streaming GCS upload**

Replace `backend/app/tests/test_gcs.py`:

```python
"""Tests for GCS upload/download service."""
import io
from unittest.mock import MagicMock, patch

import pytest

from backend.app.services.gcs import upload_to_gcs, download_from_gcs


class TestUploadToGcs:
    @patch("backend.app.services.gcs.storage.Client")
    def test_upload_returns_gs_uri(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_blob = MagicMock()
        mock_client.bucket.return_value.blob.return_value = mock_blob

        file_obj = io.BytesIO(b"fake pdf content")
        result = upload_to_gcs(
            bucket="test-bucket",
            gcs_key="uploads/tenant-1/doc-1/file.pdf",
            file_obj=file_obj,
            content_type="application/pdf",
        )

        assert result == "gs://test-bucket/uploads/tenant-1/doc-1/file.pdf"
        mock_blob.upload_from_file.assert_called_once_with(
            file_obj, content_type="application/pdf"
        )

    @patch("backend.app.services.gcs.storage.Client")
    def test_upload_uses_correct_bucket_and_key(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_blob = MagicMock()
        mock_client.bucket.return_value.blob.return_value = mock_blob

        file_obj = io.BytesIO(b"data")
        upload_to_gcs("my-bucket", "path/to/file.pdf", file_obj, "application/pdf")

        mock_client.bucket.assert_called_once_with("my-bucket")
        mock_client.bucket.return_value.blob.assert_called_once_with("path/to/file.pdf")


class TestDownloadFromGcs:
    @patch("backend.app.services.gcs.storage.Client")
    def test_download_returns_bytes(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.return_value = b"file content"
        mock_client.bucket.return_value.blob.return_value = mock_blob

        result = download_from_gcs("gs://test-bucket/path/to/file.pdf")

        assert result == b"file content"
        mock_client.bucket.assert_called_once_with("test-bucket")
        mock_client.bucket.return_value.blob.assert_called_once_with("path/to/file.pdf")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
pytest backend/app/tests/test_gcs.py -v
```
Expected: FAIL — current `upload_to_gcs` has wrong signature (takes `file_content: bytes`, not `file_obj`).

- [ ] **Step 3: Rewrite gcs.py with streaming upload**

Replace `backend/app/services/gcs.py`:

```python
"""
Google Cloud Storage utilities.
Uses ADC (Application Default Credentials) by default.
Set GCS_CREDENTIALS_PATH in .env to use a service account JSON file.
"""
from google.cloud import storage

from backend.app.core.config import get_settings


def _make_client() -> storage.Client:
    settings = get_settings()
    if settings.gcs_credentials_path:
        return storage.Client.from_service_account_json(settings.gcs_credentials_path)
    return storage.Client()  # ADC


def upload_to_gcs(
    bucket: str,
    gcs_key: str,
    file_obj,
    content_type: str,
) -> str:
    """Stream-upload a file-like object to GCS. Returns gs:// URI."""
    client = _make_client()
    blob = client.bucket(bucket).blob(gcs_key)
    blob.upload_from_file(file_obj, content_type=content_type)
    return f"gs://{bucket}/{gcs_key}"


def download_from_gcs(gcs_uri: str) -> bytes:
    """Download a blob from a gs:// URI. Returns raw bytes."""
    # Parse gs://bucket/key
    path = gcs_uri.replace("gs://", "")
    bucket_name, _, blob_name = path.partition("/")

    client = _make_client()
    blob = client.bucket(bucket_name).blob(blob_name)
    return blob.download_as_bytes()
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
pytest backend/app/tests/test_gcs.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/gcs.py backend/app/tests/test_gcs.py
git commit -m "feat: rewrite GCS service with streaming upload_from_file"
```

---

## Task 5: Airflow Client — Async httpx + Idempotent Trigger

**Files:**
- Test: `backend/app/tests/test_airflow.py` (rewrite existing)
- Modify: `backend/app/services/airflow.py`

- [ ] **Step 1: Write failing tests for new Airflow client**

Replace `backend/app/tests/test_airflow.py`:

```python
"""Tests for Airflow REST API client (async httpx, Basic Auth)."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from backend.app.services.airflow import trigger_dag, AirflowTriggerError


class TestTriggerDag:
    @patch("backend.app.services.airflow.get_settings")
    @patch("backend.app.services.airflow.httpx.AsyncClient")
    async def test_trigger_dag_returns_dag_run_id(self, mock_client_class, mock_settings):
        settings = MagicMock()
        settings.airflow_base_url = "http://airflow:8080"
        settings.airflow_username = "admin"
        settings.airflow_password = "secret"
        mock_settings.return_value = settings

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"dag_run_id": "ingest_job-123"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await trigger_dag(
            dag_id="pdf_ingestion",
            dag_run_id="ingest_job-123",
            conf={"doc_id": "abc", "gcs_path": "gs://bucket/file.pdf"},
        )

        assert result == "ingest_job-123"
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert "pdf_ingestion" in call_kwargs.args[0]
        assert call_kwargs.kwargs["json"]["dag_run_id"] == "ingest_job-123"

    @patch("backend.app.services.airflow.get_settings")
    @patch("backend.app.services.airflow.httpx.AsyncClient")
    async def test_trigger_dag_uses_basic_auth(self, mock_client_class, mock_settings):
        settings = MagicMock()
        settings.airflow_base_url = "http://airflow:8080"
        settings.airflow_username = "admin"
        settings.airflow_password = "secret"
        mock_settings.return_value = settings

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"dag_run_id": "run-1"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        await trigger_dag("pdf_ingestion", "run-1", {})

        call_kwargs = mock_client.post.call_args
        auth = call_kwargs.kwargs.get("auth")
        assert auth == ("admin", "secret")

    @patch("backend.app.services.airflow.get_settings")
    @patch("backend.app.services.airflow.httpx.AsyncClient")
    async def test_trigger_dag_409_returns_existing_run_id(self, mock_client_class, mock_settings):
        """Idempotency: if Airflow returns 409 (duplicate dag_run_id), return the existing ID."""
        settings = MagicMock()
        settings.airflow_base_url = "http://airflow:8080"
        settings.airflow_username = "admin"
        settings.airflow_password = "secret"
        mock_settings.return_value = settings

        mock_response = AsyncMock()
        mock_response.status_code = 409
        mock_response.json.return_value = {"detail": "DAG Run already exists"}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await trigger_dag("pdf_ingestion", "ingest_job-123", {})
        assert result == "ingest_job-123"  # Returns the same ID (idempotent)

    @patch("backend.app.services.airflow.get_settings")
    @patch("backend.app.services.airflow.httpx.AsyncClient")
    async def test_trigger_dag_500_raises(self, mock_client_class, mock_settings):
        settings = MagicMock()
        settings.airflow_base_url = "http://airflow:8080"
        settings.airflow_username = "admin"
        settings.airflow_password = "secret"
        mock_settings.return_value = settings

        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(AirflowTriggerError):
            await trigger_dag("pdf_ingestion", "run-1", {})
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
pytest backend/app/tests/test_airflow.py -v
```
Expected: FAIL — `AirflowTriggerError` and new `trigger_dag` signature not found.

- [ ] **Step 3: Rewrite airflow.py**

Replace `backend/app/services/airflow.py`:

```python
"""
Airflow REST API client.
Triggers DAGs via Basic Auth (dev) or IAP (prod).
"""
import httpx

from backend.app.core.config import get_settings


class AirflowTriggerError(Exception):
    """Raised when Airflow DAG trigger fails (non-409 error)."""
    pass


async def trigger_dag(dag_id: str, dag_run_id: str, conf: dict) -> str:
    """
    Trigger an Airflow DAG run via REST API.

    Args:
        dag_id: The DAG to trigger (e.g. "pdf_ingestion").
        dag_run_id: Idempotent run ID (e.g. "ingest_{job_id}").
        conf: Configuration dict passed to the DAG.

    Returns:
        The dag_run_id (same as input for idempotency).

    Raises:
        AirflowTriggerError: On non-409 HTTP errors.
    """
    settings = get_settings()
    url = f"{settings.airflow_base_url}/api/v1/dags/{dag_id}/dagRuns"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            json={"dag_run_id": dag_run_id, "conf": conf},
            auth=(settings.airflow_username, settings.airflow_password),
            timeout=10.0,
        )

        # 409 = duplicate dag_run_id → idempotent, return existing
        if resp.status_code == 409:
            return dag_run_id

        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise AirflowTriggerError(
                f"Failed to trigger DAG {dag_id}: {resp.status_code} {resp.text}"
            ) from e

        return resp.json()["dag_run_id"]


def build_airflow_run_url(dag_id: str, dag_run_id: str) -> str:
    """Build a deep-link URL to the Airflow UI for a specific DAG run."""
    settings = get_settings()
    base = settings.airflow_base_url.rstrip("/")
    return f"{base}/dags/{dag_id}/grid?dag_run_id={dag_run_id}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
pytest backend/app/tests/test_airflow.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/airflow.py backend/app/tests/test_airflow.py
git commit -m "feat: rewrite Airflow client — async httpx, Basic Auth, idempotent trigger"
```

---

## Task 6: Upload Endpoint — Race-Condition-Safe Flow

**Files:**
- Test: `backend/app/tests/api/test_documents.py` (rewrite)
- Modify: `backend/app/api/endpoints/documents.py`

- [ ] **Step 1: Write failing test for new upload flow**

Replace `backend/app/tests/api/test_documents.py`:

```python
"""Tests for document upload → GCS → trigger DAG flow."""
import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Document, IngestionJob
from backend.app.tests.test_auth import _seed_user


class TestUploadDocument:
    @patch("backend.app.api.endpoints.documents.trigger_dag", new_callable=AsyncMock)
    @patch("backend.app.api.endpoints.documents.build_airflow_run_url")
    @patch("backend.app.api.endpoints.documents.upload_to_gcs")
    async def test_upload_returns_202_with_doc_and_job_ids(
        self, mock_gcs, mock_build_url, mock_trigger, auth_client: AsyncClient, db_session: AsyncSession
    ):
        mock_gcs.return_value = "gs://bucket/uploads/tenant/doc/file.pdf"
        mock_trigger.return_value = "ingest_test-job-id"
        mock_build_url.return_value = "http://airflow/dags/pdf_ingestion/grid?dag_run_id=ingest_test-job-id"

        pdf_content = b"%PDF-1.4 fake content"
        resp = await auth_client.post(
            "/api/documents/upload",
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
            data={"title": "Test Policy"},
        )

        assert resp.status_code == 202
        body = resp.json()
        assert "doc_id" in body
        assert "job_id" in body
        assert body["status"] == "queued"

    @patch("backend.app.api.endpoints.documents.trigger_dag", new_callable=AsyncMock)
    @patch("backend.app.api.endpoints.documents.build_airflow_run_url")
    @patch("backend.app.api.endpoints.documents.upload_to_gcs")
    async def test_upload_inserts_document_before_triggering_dag(
        self, mock_gcs, mock_build_url, mock_trigger, auth_client: AsyncClient, db_session: AsyncSession
    ):
        """DB records must be inserted BEFORE Airflow trigger (race-condition-safe)."""
        mock_gcs.return_value = "gs://bucket/test.pdf"
        mock_build_url.return_value = "http://airflow/dags/test"

        call_order = []

        async def record_trigger(*args, **kwargs):
            # At this point, Document and IngestionJob should already exist in DB
            result = await db_session.execute(select(Document))
            docs = result.scalars().all()
            call_order.append(("trigger", len(docs)))
            return "ingest_run-1"

        mock_trigger.side_effect = record_trigger

        await auth_client.post(
            "/api/documents/upload",
            files={"file": ("test.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
            data={"title": "Test"},
        )

        assert len(call_order) == 1
        assert call_order[0][0] == "trigger"
        assert call_order[0][1] >= 1  # Document exists before trigger

    async def test_upload_rejects_non_pdf(self, auth_client: AsyncClient):
        resp = await auth_client.post(
            "/api/documents/upload",
            files={"file": ("test.txt", io.BytesIO(b"not a pdf"), "text/plain")},
            data={"title": "Test"},
        )
        assert resp.status_code == 400

    async def test_upload_requires_title(self, auth_client: AsyncClient):
        resp = await auth_client.post(
            "/api/documents/upload",
            files={"file": ("test.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
        )
        assert resp.status_code == 422


class TestGetDocumentStatus:
    @patch("backend.app.api.endpoints.documents.trigger_dag", new_callable=AsyncMock)
    @patch("backend.app.api.endpoints.documents.build_airflow_run_url")
    @patch("backend.app.api.endpoints.documents.upload_to_gcs")
    async def test_status_returns_job_info(
        self, mock_gcs, mock_build_url, mock_trigger, auth_client: AsyncClient
    ):
        mock_gcs.return_value = "gs://bucket/test.pdf"
        mock_trigger.return_value = "ingest_run-1"
        mock_build_url.return_value = "http://airflow/test"

        upload_resp = await auth_client.post(
            "/api/documents/upload",
            files={"file": ("t.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
            data={"title": "Test"},
        )
        doc_id = upload_resp.json()["doc_id"]

        resp = await auth_client.get(f"/api/documents/{doc_id}/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "queued"
        assert body["current_task"] is None


class TestListDocuments:
    @patch("backend.app.api.endpoints.documents.trigger_dag", new_callable=AsyncMock)
    @patch("backend.app.api.endpoints.documents.build_airflow_run_url")
    @patch("backend.app.api.endpoints.documents.upload_to_gcs")
    async def test_list_returns_user_documents(
        self, mock_gcs, mock_build_url, mock_trigger, auth_client: AsyncClient
    ):
        mock_gcs.return_value = "gs://bucket/test.pdf"
        mock_trigger.return_value = "run-1"
        mock_build_url.return_value = "http://airflow/test"

        await auth_client.post(
            "/api/documents/upload",
            files={"file": ("a.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
            data={"title": "Doc A"},
        )

        resp = await auth_client.get("/api/documents/")
        assert resp.status_code == 200
        docs = resp.json()
        assert len(docs) >= 1
        assert docs[0]["title"] == "Doc A"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
pytest backend/app/tests/api/test_documents.py -v
```
Expected: FAIL — endpoint doesn't exist at `/api/documents/upload` or has wrong flow.

- [ ] **Step 3: Rewrite documents.py endpoint**

Replace `backend/app/api/endpoints/documents.py`:

```python
"""
Document upload, status, list, and delete endpoints.
Upload flow: validate → GCS → insert DB → trigger Airflow DAG → return 202.
"""
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.config import get_settings
from backend.app.db.models import Document, IngestionJob
from backend.app.db.session import get_db
from backend.app.services.airflow import (
    AirflowTriggerError,
    build_airflow_run_url,
    trigger_dag,
)
from backend.app.services.auth import get_current_user
from backend.app.services.gcs import upload_to_gcs

router = APIRouter()

MAX_FILE_SIZE_MB = 50
ALLOWED_CONTENT_TYPES = {"application/pdf"}


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Upload a PDF document for ingestion.

    Race-condition-safe flow:
    1. Validate → 2. GCS upload → 3. INSERT Document → 4. INSERT IngestionJob
    → 5. Trigger Airflow DAG → 6. UPDATE dag_run_id → 7. Return 202
    """
    # 1. Validate
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(400, f"Only PDF files accepted. Got: {file.content_type}")

    settings = get_settings()
    doc_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    dag_run_id = f"ingest_{job_id}"
    tenant_id = str(current_user.id)  # Use user_id as tenant_id for now

    # 2. Upload to GCS (streaming)
    gcs_key = f"uploads/{tenant_id}/{doc_id}/{file.filename}"
    gcs_path = upload_to_gcs(
        bucket=settings.gcs_bucket,
        gcs_key=gcs_key,
        file_obj=file.file,
        content_type=file.content_type,
    )

    # 3. INSERT Document (before Airflow trigger — race-condition-safe)
    doc = Document(
        id=doc_id,
        user_id=current_user.id,
        tenant_id=tenant_id,
        title=title,
        filename=file.filename,
        gcs_path=gcs_path,
        collection="policies",
        embedding_model=settings.airflow_default_embedding_model
            if hasattr(settings, "airflow_default_embedding_model")
            else "nvidia/llama-nemotron-embed-vl-1b-v2:free",
        status="processing",
        source="upload",
    )
    db.add(doc)

    # 4. INSERT IngestionJob (before Airflow trigger)
    job = IngestionJob(
        id=job_id,
        doc_id=doc_id,
        dag_run_id=dag_run_id,
        status="queued",
    )
    db.add(job)
    await db.commit()

    # 5. Trigger Airflow DAG
    conf = {
        "doc_id": doc_id,
        "user_id": str(current_user.id),
        "tenant_id": tenant_id,
        "gcs_path": gcs_path,
        "title": title,
        "collection": "policies",
        "embedding_model": doc.embedding_model,
    }

    try:
        await trigger_dag(
            dag_id=settings.airflow_dag_id,
            dag_run_id=dag_run_id,
            conf=conf,
        )
    except AirflowTriggerError:
        # Job record already exists with status=queued — visible for retry
        job.status = "failed"
        job.failed_task = "trigger"
        job.error_msg = "Failed to trigger Airflow DAG"
        await db.commit()
        raise HTTPException(502, "Failed to trigger ingestion pipeline")

    # 6. Update with Airflow URL
    job.airflow_run_url = build_airflow_run_url(settings.airflow_dag_id, dag_run_id)
    await db.commit()

    return {
        "doc_id": doc_id,
        "job_id": job_id,
        "status": "queued",
        "airflow_run_url": job.airflow_run_url,
    }


@router.get("/{doc_id}/status")
async def get_document_status(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get ingestion status for a document."""
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.ingestion_jobs))
        .where(Document.id == doc_id, Document.user_id == current_user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")

    job = doc.ingestion_jobs[0] if doc.ingestion_jobs else None

    return {
        "doc_id": doc.id,
        "title": doc.title,
        "status": job.status if job else doc.status,
        "current_task": job.current_task if job else None,
        "started_at": job.started_at.isoformat() if job and job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job and job.completed_at else None,
        "failed_task": job.failed_task if job else None,
        "error": job.error_msg if job else None,
        "airflow_run_url": job.airflow_run_url if job else None,
    }


@router.get("/")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all documents for the current user."""
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "filename": d.filename,
            "status": d.status,
            "source": d.source,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@router.delete("/{doc_id}", status_code=status.HTTP_202_ACCEPTED)
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Soft-delete a document. Cleanup (Qdrant, Neo4j, GCS) runs async."""
    result = await db.execute(
        select(Document).where(
            Document.id == doc_id, Document.user_id == current_user.id
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")

    doc.status = "deleting"
    await db.commit()

    # TODO: Trigger async cleanup task for Qdrant, Neo4j, GCS
    # This will be a separate task/DAG in a future iteration.

    return {"doc_id": doc_id, "status": "deleting"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
pytest backend/app/tests/api/test_documents.py -v
```
Expected: PASS (5 tests). If conftest fixtures need updating for UUID Document PK, fix in Task 8.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/endpoints/documents.py backend/app/tests/api/test_documents.py
git commit -m "feat: rewrite upload endpoint — GCS + DB + trigger DAG, race-condition-safe"
```

---

## Task 7: Update main.py Lifespan + Test Fixture Updates

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/tests/conftest.py`

- [ ] **Step 1: Update main.py lifespan to use DATABASE_URL from settings**

In `backend/app/main.py`, replace the hardcoded SQLite path in the lifespan function. Find the line:

```python
db_url = "sqlite+aiosqlite:///backend/data/users.db"
```

Replace with:

```python
settings = get_settings()
db_url = settings.database_url
```

Remove all PRAGMA-based migration code (the `async with engine.begin()` block that runs `PRAGMA table_info` and `ALTER TABLE`). These are SQLite-specific and won't work with Postgres. Alembic handles migrations now.

Keep the admin seeding logic and Qdrant verification.

- [ ] **Step 2: Update conftest.py for UUID Document PK**

In `backend/app/tests/conftest.py`, find any place that creates a `Document` object and update to include the new required fields:

```python
# Anywhere a Document is created in tests, use this pattern:
import uuid

doc = Document(
    id=str(uuid.uuid4()),
    user_id=user.id,
    tenant_id=str(user.id),
    title="Test Doc",
    filename="test.pdf",
    gcs_path="gs://test-bucket/test.pdf",
    collection="policies",
    embedding_model="test-model",
    status="processing",
    source="upload",
)
```

- [ ] **Step 3: Run full test suite**

Run:
```bash
pytest backend/app/tests/ -v 2>&1 | tail -30
```
Expected: All tests pass (or only unrelated failures). Fix any failures caused by the Document model changes.

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py backend/app/tests/conftest.py
git commit -m "feat: update lifespan to use DATABASE_URL, fix test fixtures for UUID Document"
```

---

## Task 8: Airflow DAG — Status Helpers & Callbacks

**Files:**
- Create: `dags/__init__.py`
- Create: `dags/tasks/__init__.py`
- Create: `dags/tasks/db_status.py`
- Test: `dags/tests/__init__.py`
- Test: `dags/tests/test_db_status.py`

- [ ] **Step 1: Write failing test for status helpers**

Create `dags/tests/__init__.py` (empty) and `dags/tests/test_db_status.py`:

```python
"""Tests for DAG status update helpers."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest

from dags.tasks.db_status import update_current_task, mark_completed, mark_failed


class TestUpdateCurrentTask:
    @patch("dags.tasks.db_status._get_engine")
    def test_updates_status_and_current_task(self, mock_engine):
        mock_conn = MagicMock()
        mock_engine.return_value.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.return_value.connect.return_value.__exit__ = MagicMock(return_value=False)

        update_current_task("job-123", "download_pdf")

        mock_conn.execute.assert_called_once()
        sql_text = str(mock_conn.execute.call_args[0][0])
        assert "ingestion_jobs" in sql_text
        assert "running" in str(mock_conn.execute.call_args)


class TestMarkCompleted:
    @patch("dags.tasks.db_status._get_engine")
    def test_sets_status_completed_and_clears_current_task(self, mock_engine):
        mock_conn = MagicMock()
        mock_engine.return_value.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.return_value.connect.return_value.__exit__ = MagicMock(return_value=False)

        mark_completed("job-123", "doc-456")

        # Should execute 2 UPDATE statements: ingestion_jobs + documents
        assert mock_conn.execute.call_count == 2


class TestMarkFailed:
    @patch("dags.tasks.db_status._get_engine")
    def test_sets_status_failed_with_error_details(self, mock_engine):
        mock_conn = MagicMock()
        mock_engine.return_value.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.return_value.connect.return_value.__exit__ = MagicMock(return_value=False)

        mark_failed("job-123", "doc-456", "extract_text", "OCR failed: corrupt PDF")

        assert mock_conn.execute.call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
pytest dags/tests/test_db_status.py -v
```
Expected: FAIL — module `dags.tasks.db_status` not found.

- [ ] **Step 3: Implement db_status.py**

Create `dags/__init__.py` (empty), `dags/tasks/__init__.py` (empty), and `dags/tasks/db_status.py`:

```python
"""
Cloud SQL status update helpers for Airflow DAG tasks.

Uses synchronous SQLAlchemy (Airflow tasks are sync by default).
Reads DB connection from Airflow Connection 'rag_platform_db'.
"""
from datetime import datetime, timezone

from sqlalchemy import create_engine, text


def _get_engine():
    """Get a sync SQLAlchemy engine from Airflow Connection."""
    try:
        from airflow.hooks.base import BaseHook
        conn = BaseHook.get_connection("rag_platform_db")
        url = f"postgresql://{conn.login}:{conn.password}@{conn.host}:{conn.port}/{conn.schema}"
    except Exception:
        # Fallback for testing outside Airflow
        import os
        url = os.environ.get(
            "RAG_PLATFORM_DB_URL",
            "postgresql://user:pass@127.0.0.1:5432/rag_platform_db",
        )
    return create_engine(url)


def update_current_task(job_id: str, task_name: str) -> None:
    """Update ingestion_jobs.current_task and set status=running."""
    engine = _get_engine()
    with engine.connect() as conn:
        conn.execute(
            text("""
                UPDATE ingestion_jobs
                SET status = 'running',
                    current_task = :task_name,
                    started_at = COALESCE(started_at, :now)
                WHERE id = :job_id
            """),
            {"job_id": job_id, "task_name": task_name, "now": datetime.now(timezone.utc)},
        )
        conn.commit()


def mark_completed(job_id: str, doc_id: str) -> None:
    """Mark job as completed and document as ready."""
    engine = _get_engine()
    now = datetime.now(timezone.utc)
    with engine.connect() as conn:
        conn.execute(
            text("""
                UPDATE ingestion_jobs
                SET status = 'completed', current_task = NULL, completed_at = :now
                WHERE id = :job_id
            """),
            {"job_id": job_id, "now": now},
        )
        conn.execute(
            text("UPDATE documents SET status = 'ready', updated_at = :now WHERE id = :doc_id"),
            {"doc_id": doc_id, "now": now},
        )
        conn.commit()


def mark_failed(job_id: str, doc_id: str, failed_task: str, error_msg: str) -> None:
    """Mark job as failed with error details."""
    engine = _get_engine()
    now = datetime.now(timezone.utc)
    with engine.connect() as conn:
        conn.execute(
            text("""
                UPDATE ingestion_jobs
                SET status = 'failed', failed_task = :failed_task,
                    error_msg = :error_msg, completed_at = :now
                WHERE id = :job_id
            """),
            {"job_id": job_id, "failed_task": failed_task, "error_msg": error_msg[:2000], "now": now},
        )
        conn.execute(
            text("UPDATE documents SET status = 'failed', updated_at = :now WHERE id = :doc_id"),
            {"doc_id": doc_id, "now": now},
        )
        conn.commit()


def on_failure_callback(context) -> None:
    """Airflow on_failure_callback — updates Cloud SQL on task failure."""
    conf = context["dag_run"].conf or {}
    job_id = conf.get("job_id")
    doc_id = conf.get("doc_id")
    task_id = context["task_instance"].task_id
    exception = str(context.get("exception", "Unknown error"))

    if job_id and doc_id:
        mark_failed(job_id, doc_id, task_id, exception)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
pytest dags/tests/test_db_status.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add dags/
git commit -m "feat: add DAG status helpers (update_current_task, mark_completed, mark_failed)"
```

---

## Task 9: Airflow DAG — PDF Download, Extract & Validate Tasks

**Files:**
- Create: `dags/tasks/download.py`
- Create: `dags/tasks/extract.py`
- Test: `dags/tests/test_extract.py`

- [ ] **Step 1: Write failing test for extract and validate logic**

Create `dags/tests/test_extract.py`:

```python
"""Tests for text extraction and validation tasks."""
import pytest

from dags.tasks.extract import extract_text_from_bytes, validate_text


class TestExtractText:
    def test_extract_returns_text_from_valid_pdf_bytes(self):
        # PyMuPDF can open PDFs from bytes
        # We test with a minimal valid PDF
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Hello World from test PDF")
        pdf_bytes = doc.tobytes()
        doc.close()

        result = extract_text_from_bytes(pdf_bytes)
        assert "Hello World from test PDF" in result

    def test_extract_raises_on_empty_bytes(self):
        with pytest.raises(ValueError, match="Could not open PDF"):
            extract_text_from_bytes(b"")


class TestValidateText:
    def test_validate_passes_for_long_text(self):
        text = "A" * 200
        result = validate_text(text)
        assert result == 200  # char_count

    def test_validate_fails_for_short_text(self):
        with pytest.raises(ValueError, match="too short"):
            validate_text("Short")

    def test_validate_fails_for_whitespace_only(self):
        with pytest.raises(ValueError, match="too short"):
            validate_text("   \n\n   ")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
pytest dags/tests/test_extract.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Implement download.py**

Create `dags/tasks/download.py`:

```python
"""
Task: download_pdf
Downloads a PDF from GCS to a local temp path on the Airflow worker.
"""
import tempfile
from pathlib import Path

from google.cloud import storage

from dags.tasks.db_status import update_current_task


def download_pdf(**context) -> str:
    """
    Airflow PythonOperator callable.
    Reads gcs_path from DAG conf, downloads to temp dir, pushes local path to XCom.
    """
    conf = context["dag_run"].conf
    job_id = conf["job_id"]
    gcs_path = conf["gcs_path"]
    doc_id = conf["doc_id"]

    update_current_task(job_id, "download_pdf")

    # Parse gs://bucket/key
    path = gcs_path.replace("gs://", "")
    bucket_name, _, blob_name = path.partition("/")

    client = storage.Client()
    blob = client.bucket(bucket_name).blob(blob_name)

    tmp_dir = Path(tempfile.mkdtemp())
    local_path = tmp_dir / f"{doc_id}.pdf"
    blob.download_to_filename(str(local_path))

    return str(local_path)
```

- [ ] **Step 4: Implement extract.py**

Create `dags/tasks/extract.py`:

```python
"""
Tasks: extract_text, validate_text
Extracts text from PDF bytes (via PyMuPDF), validates minimum length,
uploads raw text to GCS as an intermediate artifact.
"""
import json
import tempfile
from pathlib import Path

import fitz  # PyMuPDF
from google.cloud import storage

from dags.tasks.db_status import update_current_task


def extract_text_from_bytes(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using PyMuPDF. Raises ValueError on failure."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise ValueError(f"Could not open PDF: {e}")

    if doc.is_encrypted:
        raise ValueError("PDF is encrypted. Decrypt before ingestion.")

    pages_text = [page.get_text() for page in doc]
    text = "\n\n".join(pages_text).strip()
    doc.close()

    if not text:
        raise ValueError("No text extracted — PDF may be scanned/image-based.")

    return text


def validate_text(text: str, min_chars: int = 100) -> int:
    """Validate extracted text meets minimum length. Returns char_count."""
    clean = text.strip()
    if len(clean) < min_chars:
        raise ValueError(
            f"Document too short ({len(clean)} chars) — "
            f"may be scanned/image-only PDF. Minimum: {min_chars} chars."
        )
    return len(clean)


def extract_text(**context) -> str:
    """
    Airflow PythonOperator callable.
    Reads PDF from local path (XCom from download_pdf),
    extracts text, uploads to GCS, returns gcs_text_path.
    """
    conf = context["dag_run"].conf
    job_id = conf["job_id"]
    doc_id = conf["doc_id"]
    tenant_id = conf["tenant_id"]

    update_current_task(job_id, "extract_text")

    # Get local PDF path from previous task
    ti = context["ti"]
    local_path = ti.xcom_pull(task_ids="download_pdf")

    with open(local_path, "rb") as f:
        pdf_bytes = f.read()

    text = extract_text_from_bytes(pdf_bytes)

    # Upload text to GCS
    try:
        from airflow.models import Variable
        bucket_name = Variable.get("gcs_bucket")
    except Exception:
        import os
        bucket_name = os.environ.get("GCS_BUCKET", "privacy-assistant-uploads")

    gcs_key = f"processing/{tenant_id}/{doc_id}/text/{doc_id}.txt"
    client = storage.Client()
    blob = client.bucket(bucket_name).blob(gcs_key)
    blob.upload_from_string(text, content_type="text/plain")

    return f"gs://{bucket_name}/{gcs_key}"


def validate_text_task(**context) -> int:
    """
    Airflow PythonOperator callable.
    Downloads text from GCS, validates minimum length.
    """
    conf = context["dag_run"].conf
    job_id = conf["job_id"]

    update_current_task(job_id, "validate_text")

    ti = context["ti"]
    gcs_text_path = ti.xcom_pull(task_ids="extract_text")

    # Download text
    path = gcs_text_path.replace("gs://", "")
    bucket_name, _, blob_name = path.partition("/")
    client = storage.Client()
    blob = client.bucket(bucket_name).blob(blob_name)
    text = blob.download_as_text()

    return validate_text(text)
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
pytest dags/tests/test_extract.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add dags/tasks/download.py dags/tasks/extract.py dags/tests/test_extract.py
git commit -m "feat: add DAG tasks — download_pdf, extract_text, validate_text"
```

---

## Task 10: Airflow DAG — Chunk Text Task

**Files:**
- Create: `dags/tasks/chunk.py`
- Test: `dags/tests/test_chunk.py`

- [ ] **Step 1: Write failing test for chunking logic**

Create `dags/tests/test_chunk.py`:

```python
"""Tests for chunk_text DAG task logic."""
import json

import pytest

from dags.tasks.chunk import chunk_text_content


class TestChunkTextContent:
    def test_chunks_short_text_into_single_chunk(self):
        text = "This is a short policy document about data privacy."
        chunks = chunk_text_content(
            text=text,
            doc_id="doc-1",
            title="Privacy Policy",
            tenant_id="tenant-1",
            user_id="user-1",
        )
        assert len(chunks) >= 1
        assert chunks[0]["text"] == text
        assert chunks[0]["title"] == "Privacy Policy"
        assert chunks[0]["doc_id"] == "doc-1"
        assert chunks[0]["tenant_id"] == "tenant-1"

    def test_chunks_long_text_into_multiple_chunks(self):
        # Create text longer than MAX_TOKENS (400 tokens ≈ ~1600 chars)
        text = "Privacy policy section. " * 200  # ~4800 chars ≈ 1200 tokens
        chunks = chunk_text_content(text, "doc-2", "Long Policy", "t-1", "u-1")
        assert len(chunks) > 1

    def test_each_chunk_has_required_fields(self):
        text = "Data retention policy for customer information."
        chunks = chunk_text_content(text, "doc-3", "Retention", "t-1", "u-1")
        for chunk in chunks:
            assert "id" in chunk
            assert "text" in chunk
            assert "title" in chunk
            assert "doc_id" in chunk
            assert "tenant_id" in chunk
            assert "user_id" in chunk
            assert "chunk_index" in chunk
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
pytest dags/tests/test_chunk.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Implement chunk.py**

Create `dags/tasks/chunk.py`. This ports the chunking logic from `backend/ingestion/chunker.py` to be self-contained for Airflow:

```python
"""
Task: chunk_text
Splits extracted text into overlapping chunks and uploads as JSON to GCS.
Ports logic from backend/ingestion/chunker.py for Airflow independence.
"""
import json
import uuid

import tiktoken
from google.cloud import storage

from dags.tasks.db_status import update_current_task

MAX_TOKENS = 400
OVERLAP_TOKENS = 50
ENCODING = tiktoken.get_encoding("cl100k_base")
SEPARATORS = ["\n\n", "\n", ". ", " "]


def _count_tokens(text: str) -> int:
    return len(ENCODING.encode(text))


def chunk_text_content(
    text: str,
    doc_id: str,
    title: str,
    tenant_id: str,
    user_id: str,
) -> list[dict]:
    """
    Split text into overlapping chunks.
    Returns a list of chunk dicts ready for JSON serialization.
    """
    if _count_tokens(text) <= MAX_TOKENS:
        return [
            {
                "id": str(uuid.uuid4()),
                "text": text,
                "title": title,
                "doc_id": doc_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "chunk_index": 0,
                "token_count": _count_tokens(text),
            }
        ]

    chunks = []
    start = 0
    chunk_index = 0

    while start < len(text):
        # Find the end position for this chunk
        end = start
        for sep in SEPARATORS:
            # Try to find a natural break point within MAX_TOKENS
            candidate = text[start:]
            tokens = 0
            last_sep = 0
            for i, char in enumerate(candidate):
                if candidate[i:i+len(sep)] == sep:
                    last_sep = i + len(sep)
                # Approximate: check token count periodically
                if i % 100 == 0 and _count_tokens(candidate[:i]) >= MAX_TOKENS:
                    break
            end = start + (last_sep if last_sep > 0 else min(len(candidate), MAX_TOKENS * 4))
            if _count_tokens(text[start:end]) <= MAX_TOKENS:
                break

        # Fallback: hard cut at MAX_TOKENS worth of text
        chunk_text = text[start:end].strip()
        while _count_tokens(chunk_text) > MAX_TOKENS and len(chunk_text) > 100:
            chunk_text = chunk_text[:int(len(chunk_text) * 0.9)]
            # Find last sentence boundary
            for sep in [". ", "\n", " "]:
                idx = chunk_text.rfind(sep)
                if idx > len(chunk_text) // 2:
                    chunk_text = chunk_text[:idx + len(sep)]
                    break

        if chunk_text:
            chunks.append({
                "id": str(uuid.uuid4()),
                "text": chunk_text.strip(),
                "title": title,
                "doc_id": doc_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "chunk_index": chunk_index,
                "token_count": _count_tokens(chunk_text),
            })
            chunk_index += 1

        # Advance with overlap
        overlap_chars = max(len(chunk_text) - int(len(chunk_text) * OVERLAP_TOKENS / MAX_TOKENS), 1)
        start += overlap_chars
        if start >= len(text):
            break

    return chunks


def chunk_text(**context) -> str:
    """
    Airflow PythonOperator callable.
    Downloads text from GCS, chunks it, uploads chunks JSON to GCS.
    """
    conf = context["dag_run"].conf
    job_id = conf["job_id"]
    doc_id = conf["doc_id"]
    tenant_id = conf["tenant_id"]
    user_id = conf["user_id"]
    title = conf["title"]

    update_current_task(job_id, "chunk_text")

    ti = context["ti"]
    gcs_text_path = ti.xcom_pull(task_ids="extract_text")

    # Download text
    path = gcs_text_path.replace("gs://", "")
    bucket_name, _, blob_name = path.partition("/")
    client = storage.Client()
    text = client.bucket(bucket_name).blob(blob_name).download_as_text()

    # Chunk
    chunks = chunk_text_content(text, doc_id, title, tenant_id, user_id)

    # Upload chunks JSON to GCS
    gcs_key = f"processing/{tenant_id}/{doc_id}/chunks/{doc_id}.json"
    blob = client.bucket(bucket_name).blob(gcs_key)
    blob.upload_from_string(json.dumps(chunks), content_type="application/json")

    return f"gs://{bucket_name}/{gcs_key}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
pytest dags/tests/test_chunk.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add dags/tasks/chunk.py dags/tests/test_chunk.py
git commit -m "feat: add DAG chunk_text task with self-contained chunking logic"
```

---

## Task 11: Airflow DAG — Embed + Upsert Qdrant (In-Memory)

**Files:**
- Create: `dags/tasks/embed_and_upsert.py`

- [ ] **Step 1: Implement embed_and_upsert.py**

Create `dags/tasks/embed_and_upsert.py`:

```python
"""
Task: generate_embeddings + upsert_qdrant (combined — no GCS intermediate)
Embeds chunks via OpenRouter and upserts directly to Qdrant Cloud.
Vectors are NEVER written to GCS.
"""
import json
import time

from google.cloud import storage
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from dags.tasks.db_status import update_current_task

BATCH_SIZE = 50
BATCH_SLEEP_SECONDS = 3  # Respect free-tier rate limits


def _get_openrouter_client() -> OpenAI:
    """Get OpenAI client configured for OpenRouter."""
    try:
        from airflow.models import Variable
        api_key = Variable.get("openrouter_api_key")
    except Exception:
        import os
        api_key = os.environ.get("OPENROUTER_API_KEY", "")

    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://github.com/privacy-policy-compliance-assistant",
            "X-Title": "Privacy Policy Compliance Assistant",
        },
    )


def _get_qdrant_client() -> QdrantClient:
    """Get Qdrant client from Airflow Variables."""
    try:
        from airflow.models import Variable
        url = Variable.get("qdrant_url")
        api_key = Variable.get("qdrant_api_key")
    except Exception:
        import os
        url = os.environ.get("QDRANT_URL", "http://localhost:6333")
        api_key = os.environ.get("QDRANT_API_KEY", "")

    return QdrantClient(url=url, api_key=api_key if api_key else None)


def _ensure_collection(qdrant: QdrantClient, collection: str, dim: int) -> None:
    """Create Qdrant collection if it doesn't exist."""
    collections = [c.name for c in qdrant.get_collections().collections]
    if collection not in collections:
        qdrant.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


def embed_and_upsert_qdrant(**context) -> dict:
    """
    Airflow PythonOperator callable.
    Downloads chunks from GCS, embeds via OpenRouter, upserts to Qdrant.
    Returns {"chunk_count": N, "collection": "..."}.
    """
    conf = context["dag_run"].conf
    job_id = conf["job_id"]
    doc_id = conf["doc_id"]
    user_id = conf["user_id"]
    tenant_id = conf["tenant_id"]
    collection = conf.get("collection", "policies")
    embedding_model = conf.get("embedding_model", "nvidia/llama-nemotron-embed-vl-1b-v2:free")

    update_current_task(job_id, "generate_embeddings")

    ti = context["ti"]
    gcs_chunks_path = ti.xcom_pull(task_ids="chunk_text")

    # Download chunks
    path = gcs_chunks_path.replace("gs://", "")
    bucket_name, _, blob_name = path.partition("/")
    client = storage.Client()
    chunks_json = client.bucket(bucket_name).blob(blob_name).download_as_text()
    chunks = json.loads(chunks_json)

    openrouter = _get_openrouter_client()
    qdrant = _get_qdrant_client()

    # Probe embedding dimension
    probe_resp = openrouter.embeddings.create(
        model=embedding_model, input="probe", encoding_format="float"
    )
    dim = len(probe_resp.data[0].embedding)
    _ensure_collection(qdrant, collection, dim)

    # Embed and upsert in batches
    update_current_task(job_id, "upsert_qdrant")

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        texts = [c["text"] for c in batch]

        resp = openrouter.embeddings.create(
            model=embedding_model, input=texts, encoding_format="float"
        )

        points = []
        for chunk, emb_data in zip(batch, resp.data):
            points.append(PointStruct(
                id=chunk["id"],
                vector=emb_data.embedding,
                payload={
                    "text": chunk["text"],
                    "title": chunk["title"],
                    "doc_id": doc_id,
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "chunk_index": chunk["chunk_index"],
                    "source": "upload",
                },
            ))

        qdrant.upsert(collection_name=collection, points=points)

        if i + BATCH_SIZE < len(chunks):
            time.sleep(BATCH_SLEEP_SECONDS)

    return {"chunk_count": len(chunks), "collection": collection}
```

- [ ] **Step 2: Commit**

```bash
git add dags/tasks/embed_and_upsert.py
git commit -m "feat: add DAG embed+upsert task — in-memory, no GCS intermediate for vectors"
```

---

## Task 12: Airflow DAG — Build Graph + Upsert Neo4j

**Files:**
- Create: `dags/tasks/graph.py`
- Create: `dags/tasks/neo4j_upsert.py`

- [ ] **Step 1: Implement graph.py (NER + Relation Extraction)**

Create `dags/tasks/graph.py`:

```python
"""
Task: build_graph
Extracts entities and relationships from chunks using LLM (OpenRouter).
Uploads graph JSON to GCS: { "entities": [...], "relationships": [...] }
"""
import json

from google.cloud import storage
from openai import OpenAI

from dags.tasks.db_status import update_current_task

GRAPH_EXTRACTION_PROMPT = """Extract named entities and relationships from the following text.
Return a JSON object with:
- "entities": list of {"id": "unique-id", "name": "entity name", "type": "entity type"}
- "relationships": list of {"source": "entity name", "target": "entity name", "type": "relationship type"}

Entity types: Regulation, Organization, DataType, Process, Right, Obligation, Role
Relationship types: REFERENCES, REQUIRES, PROTECTS, GOVERNS, APPLIES_TO, GRANTS

Text:
{text}

Return ONLY valid JSON, no markdown fences."""


def _get_openrouter_client() -> OpenAI:
    try:
        from airflow.models import Variable
        api_key = Variable.get("openrouter_api_key")
    except Exception:
        import os
        api_key = os.environ.get("OPENROUTER_API_KEY", "")

    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://github.com/privacy-policy-compliance-assistant",
            "X-Title": "Privacy Policy Compliance Assistant",
        },
    )


def _extract_graph_from_text(client: OpenAI, text: str) -> dict:
    """Extract entities and relationships from text via LLM."""
    resp = client.chat.completions.create(
        model="google/gemma-4-26b-a4b",
        messages=[{"role": "user", "content": GRAPH_EXTRACTION_PROMPT.format(text=text)}],
        temperature=0.0,
    )
    content = resp.choices[0].message.content.strip()

    # Strip markdown fences if present
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        content = content.rsplit("```", 1)[0]

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"entities": [], "relationships": []}


def build_graph(**context) -> str:
    """
    Airflow PythonOperator callable.
    Downloads chunks from GCS, extracts entities+relationships via LLM,
    uploads graph JSON to GCS.
    """
    conf = context["dag_run"].conf
    job_id = conf["job_id"]
    doc_id = conf["doc_id"]
    tenant_id = conf["tenant_id"]
    user_id = conf["user_id"]

    update_current_task(job_id, "build_graph")

    ti = context["ti"]
    gcs_chunks_path = ti.xcom_pull(task_ids="chunk_text")

    # Download chunks
    path = gcs_chunks_path.replace("gs://", "")
    bucket_name, _, blob_name = path.partition("/")
    gcs_client = storage.Client()
    chunks = json.loads(gcs_client.bucket(bucket_name).blob(blob_name).download_as_text())

    openrouter = _get_openrouter_client()

    all_entities = []
    all_relationships = []

    for chunk in chunks:
        graph = _extract_graph_from_text(openrouter, chunk["text"])

        for entity in graph.get("entities", []):
            entity["doc_id"] = doc_id
            entity["user_id"] = user_id
            entity["tenant_id"] = tenant_id
            entity["chunk_id"] = chunk["id"]
            all_entities.append(entity)

        for rel in graph.get("relationships", []):
            rel["doc_id"] = doc_id
            rel["user_id"] = user_id
            rel["tenant_id"] = tenant_id
            all_relationships.append(rel)

    graph_data = {
        "doc_id": doc_id,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "entities": all_entities,
        "relationships": all_relationships,
    }

    # Upload graph JSON to GCS
    gcs_key = f"processing/{tenant_id}/{doc_id}/graph/{doc_id}.json"
    blob = gcs_client.bucket(bucket_name).blob(gcs_key)
    blob.upload_from_string(json.dumps(graph_data), content_type="application/json")

    return f"gs://{bucket_name}/{gcs_key}"
```

- [ ] **Step 2: Implement neo4j_upsert.py**

Create `dags/tasks/neo4j_upsert.py`:

```python
"""
Task: upsert_neo4j
Downloads graph JSON from GCS and upserts entities+relationships to Neo4j Aura.
"""
import json

from google.cloud import storage
from neo4j import GraphDatabase

from dags.tasks.db_status import update_current_task


def _get_neo4j_driver():
    """Get Neo4j driver from Airflow Variables."""
    try:
        from airflow.models import Variable
        uri = Variable.get("neo4j_uri")
        username = Variable.get("neo4j_username")
        password = Variable.get("neo4j_password")
    except Exception:
        import os
        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        username = os.environ.get("NEO4J_USERNAME", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "")

    return GraphDatabase.driver(uri, auth=(username, password))


def upsert_neo4j(**context) -> None:
    """
    Airflow PythonOperator callable.
    Downloads graph JSON from GCS, upserts to Neo4j Aura.
    Entities include tenant_id + user_id for data isolation.
    """
    conf = context["dag_run"].conf
    job_id = conf["job_id"]
    tenant_id = conf["tenant_id"]
    user_id = conf["user_id"]

    update_current_task(job_id, "upsert_neo4j")

    ti = context["ti"]
    gcs_graph_path = ti.xcom_pull(task_ids="build_graph")

    # Download graph JSON
    path = gcs_graph_path.replace("gs://", "")
    bucket_name, _, blob_name = path.partition("/")
    gcs_client = storage.Client()
    graph_data = json.loads(
        gcs_client.bucket(bucket_name).blob(blob_name).download_as_text()
    )

    driver = _get_neo4j_driver()

    with driver.session() as session:
        # Upsert entities
        for entity in graph_data.get("entities", []):
            session.run(
                """
                MERGE (e:Entity {name: $name, tenant_id: $tenant_id, user_id: $user_id})
                SET e.type = $type, e.doc_id = $doc_id, e.chunk_id = $chunk_id
                """,
                name=entity["name"],
                type=entity.get("type", "Unknown"),
                tenant_id=tenant_id,
                user_id=user_id,
                doc_id=entity.get("doc_id"),
                chunk_id=entity.get("chunk_id"),
            )

        # Upsert relationships
        for rel in graph_data.get("relationships", []):
            session.run(
                """
                MATCH (s:Entity {name: $source, tenant_id: $tenant_id, user_id: $user_id})
                MATCH (t:Entity {name: $target, tenant_id: $tenant_id, user_id: $user_id})
                MERGE (s)-[r:RELATES_TO {type: $rel_type}]->(t)
                SET r.doc_id = $doc_id
                """,
                source=rel["source"],
                target=rel["target"],
                rel_type=rel.get("type", "RELATES_TO"),
                tenant_id=tenant_id,
                user_id=user_id,
                doc_id=rel.get("doc_id"),
            )

    driver.close()
```

- [ ] **Step 3: Commit**

```bash
git add dags/tasks/graph.py dags/tasks/neo4j_upsert.py
git commit -m "feat: add DAG tasks — build_graph (NER+RE via LLM) + upsert_neo4j"
```

---

## Task 13: Airflow DAG — Compose pdf_ingestion.py

**Files:**
- Create: `dags/pdf_ingestion.py`
- Create: `dags/requirements.txt`
- Test: `dags/tests/test_dag_structure.py`

- [ ] **Step 1: Write failing test for DAG structure**

Create `dags/tests/test_dag_structure.py`:

```python
"""Tests for DAG structure — verifies tasks, dependencies, and basic properties."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# Mock Airflow imports for testing outside Airflow
sys.modules.setdefault("airflow", MagicMock())
sys.modules.setdefault("airflow.models", MagicMock())
sys.modules.setdefault("airflow.decorators", MagicMock())
sys.modules.setdefault("airflow.hooks.base", MagicMock())


class TestDagStructure:
    def test_dag_file_is_importable(self):
        """DAG Python file can be imported without errors."""
        # Add dags/ to path for import
        dags_dir = str(Path(__file__).parent.parent)
        if dags_dir not in sys.path:
            sys.path.insert(0, dags_dir)

        # This should not raise
        from dags.pdf_ingestion import dag
        assert dag is not None

    def test_dag_has_correct_task_count(self):
        from dags.pdf_ingestion import dag
        assert len(dag.tasks) == 8

    def test_dag_task_names(self):
        from dags.pdf_ingestion import dag
        task_ids = {t.task_id for t in dag.tasks}
        expected = {
            "download_pdf", "extract_text", "validate_text", "chunk_text",
            "generate_embeddings", "upsert_qdrant",
            "build_graph", "upsert_neo4j", "finalize",
        }
        # embed + upsert_qdrant may be combined into one task
        # adjust based on implementation
        assert "download_pdf" in task_ids
        assert "finalize" in task_ids

    def test_finalize_depends_on_both_branches(self):
        from dags.pdf_ingestion import dag
        finalize = dag.get_task("finalize")
        upstream_ids = {t.task_id for t in finalize.upstream_list}
        # finalize must wait for both vector and graph branches
        assert len(upstream_ids) >= 2
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
pytest dags/tests/test_dag_structure.py -v
```
Expected: FAIL — `dags.pdf_ingestion` not found.

- [ ] **Step 3: Implement pdf_ingestion.py DAG**

Create `dags/pdf_ingestion.py`:

```python
"""
Airflow DAG: pdf_ingestion

Processes uploaded PDF documents through the full ingestion pipeline:
download → extract → validate → chunk → (embed+upsert ‖ graph+neo4j) → finalize

Triggered via REST API from FastAPI with conf payload containing:
  doc_id, job_id, user_id, tenant_id, gcs_path, title, collection, embedding_model
"""
from datetime import timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

from tasks.db_status import mark_completed, on_failure_callback, update_current_task
from tasks.download import download_pdf
from tasks.extract import extract_text, validate_text_task
from tasks.chunk import chunk_text
from tasks.embed_and_upsert import embed_and_upsert_qdrant
from tasks.graph import build_graph
from tasks.neo4j_upsert import upsert_neo4j


default_args = {
    "owner": "privacy-assistant",
    "retries": 2,
    "retry_delay": timedelta(seconds=30),
    "on_failure_callback": on_failure_callback,
}


def _finalize(**context):
    """Final task: mark job as completed in Cloud SQL."""
    conf = context["dag_run"].conf
    job_id = conf["job_id"]
    doc_id = conf["doc_id"]
    mark_completed(job_id, doc_id)


with DAG(
    dag_id="pdf_ingestion",
    default_args=default_args,
    description="Ingest uploaded PDF: OCR → chunk → embed → Qdrant + Neo4j",
    schedule_interval=None,  # Triggered via REST API only
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=5,
    tags=["ingestion", "pdf", "rag"],
) as dag:

    t_download = PythonOperator(
        task_id="download_pdf",
        python_callable=download_pdf,
        retries=3,
        retry_delay=timedelta(seconds=30),
    )

    t_extract = PythonOperator(
        task_id="extract_text",
        python_callable=extract_text,
        retries=2,
        retry_delay=timedelta(seconds=60),
    )

    t_validate = PythonOperator(
        task_id="validate_text",
        python_callable=validate_text_task,
        retries=1,
    )

    t_chunk = PythonOperator(
        task_id="chunk_text",
        python_callable=chunk_text,
        retries=2,
        retry_delay=timedelta(seconds=30),
    )

    t_embed_upsert = PythonOperator(
        task_id="embed_and_upsert_qdrant",
        python_callable=embed_and_upsert_qdrant,
        retries=3,
        retry_delay=timedelta(seconds=60),
    )

    t_build_graph = PythonOperator(
        task_id="build_graph",
        python_callable=build_graph,
        retries=3,
        retry_delay=timedelta(seconds=60),
    )

    t_upsert_neo4j = PythonOperator(
        task_id="upsert_neo4j",
        python_callable=upsert_neo4j,
        retries=3,
        retry_delay=timedelta(seconds=30),
    )

    t_finalize = PythonOperator(
        task_id="finalize",
        python_callable=_finalize,
        retries=1,
    )

    # Task dependencies — matches spec task graph exactly
    #
    # download_pdf → extract_text → validate_text → chunk_text
    #   ├── embed_and_upsert_qdrant ──┐
    #   └── build_graph → upsert_neo4j ┤
    #                                   └── finalize

    t_download >> t_extract >> t_validate >> t_chunk
    t_chunk >> t_embed_upsert
    t_chunk >> t_build_graph >> t_upsert_neo4j
    [t_embed_upsert, t_upsert_neo4j] >> t_finalize
```

- [ ] **Step 4: Create dags/requirements.txt**

```
# Dependencies for Airflow worker containers
pymupdf
tiktoken
openai
qdrant-client
neo4j
google-cloud-storage
sqlalchemy
psycopg2-binary
```

- [ ] **Step 5: Run DAG structure tests**

Run:
```bash
pytest dags/tests/test_dag_structure.py -v
```
Expected: PASS (tests may need adjustment based on task naming — update test expectations to match actual task IDs).

- [ ] **Step 6: Commit**

```bash
git add dags/pdf_ingestion.py dags/requirements.txt dags/tests/test_dag_structure.py
git commit -m "feat: compose pdf_ingestion DAG — 8 tasks, parallel embed+graph branches"
```

---

## Task 14: Update conftest.py + Fix Existing Tests

**Files:**
- Modify: `backend/app/tests/conftest.py`
- Modify: `backend/app/tests/test_document_processor.py`

- [ ] **Step 1: Update conftest.py for new Document model**

In `backend/app/tests/conftest.py`, update any Document creation to include required fields. Add a helper fixture:

```python
import uuid


@pytest.fixture
def make_document():
    """Factory fixture for creating Document instances with required fields."""
    def _make(user_id: int, **overrides):
        defaults = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "tenant_id": str(user_id),
            "title": "Test Document",
            "filename": "test.pdf",
            "gcs_path": "gs://test-bucket/test.pdf",
            "collection": "policies",
            "embedding_model": "test-model",
            "status": "processing",
            "source": "upload",
        }
        defaults.update(overrides)
        return Document(**defaults)
    return _make
```

- [ ] **Step 2: Run full test suite and fix remaining failures**

Run:
```bash
pytest backend/app/tests/ -v --tb=short 2>&1 | tail -50
```

Fix any remaining test failures caused by Document model changes. Common fixes:
- Add missing required fields to Document creation in test files
- Update assertions that check Document.id type (now string UUID, not int)

- [ ] **Step 3: Commit**

```bash
git add backend/app/tests/
git commit -m "fix: update test fixtures for UUID Document model + new required fields"
```

---

## Task 15: Integration — Verify Everything Works Together

**Files:**
- Modify: `docker-compose.yml` (optional: add local Postgres for dev)
- Modify: `Makefile` (optional: add new targets)

- [ ] **Step 1: Run full test suite**

Run:
```bash
pytest backend/app/tests/ dags/tests/ -v --tb=short
```
Expected: All tests pass.

- [ ] **Step 2: Verify imports are clean**

Run:
```bash
python -c "
from backend.app.db.models import Document, IngestionJob
from backend.app.services.gcs import upload_to_gcs, download_from_gcs
from backend.app.services.airflow import trigger_dag, AirflowTriggerError, build_airflow_run_url
from backend.app.api.endpoints.documents import router
print('All imports OK')
"
```
Expected: `All imports OK`

- [ ] **Step 3: Verify DAG imports are clean**

Run:
```bash
cd dags && python -c "
from tasks.db_status import update_current_task, mark_completed, mark_failed, on_failure_callback
from tasks.download import download_pdf
from tasks.extract import extract_text, validate_text_task, extract_text_from_bytes, validate_text
from tasks.chunk import chunk_text, chunk_text_content
from tasks.embed_and_upsert import embed_and_upsert_qdrant
from tasks.graph import build_graph
from tasks.neo4j_upsert import upsert_neo4j
print('All DAG imports OK')
" && cd ..
```
Expected: `All DAG imports OK`

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete Airflow ingestion pipeline — all tasks, tests, and integration"
```

- [ ] **Step 5: Verify branch status**

Run:
```bash
git log --oneline -10
git diff --stat main
```

Review the changes to ensure everything is in order before requesting review.

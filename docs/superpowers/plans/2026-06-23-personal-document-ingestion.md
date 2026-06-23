# Personal Document Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to upload personal PDF documents that are processed via Cloud Composer (Airflow) for OCR + text cleaning, then ingested into Qdrant (Vector DB) and Neo4j (Graph DB) with strict per-user data isolation.

**Architecture:** User uploads PDF → FastAPI saves to GCS and triggers a Cloud Composer DAG → Airflow performs OCR, layout parsing, text cleaning, chunking, and graph extraction → Airflow writes processed JSON to GCS → FastAPI polls for completion, downloads result, generates embeddings via OpenRouter, and upserts into Qdrant and Neo4j with `user_id` isolation. RAG retrieval queries are filtered by `user_id` so users only see their own documents plus system-wide ones.

**Tech Stack:** Python 3.11, FastAPI, Google Cloud Storage (`google-cloud-storage`), Cloud Composer REST API (`google-auth`, `requests`), Qdrant, Neo4j, OpenRouter (Nemotron embeddings), existing chunker/graph extractor modules.

---

## File Structure

### Files to Create
| File | Responsibility |
|------|---------------|
| `backend/app/api/documents.py` | FastAPI router: upload, list, status endpoints |
| `backend/app/services/gcs.py` | GCS upload/download helper (thin wrapper around `google-cloud-storage`) |
| `backend/app/services/airflow.py` | Cloud Composer DAG trigger + status polling via REST API |
| `backend/app/services/document_processor.py` | Background task: poll Airflow, download result, embed, upsert to Qdrant + Neo4j |
| `backend/app/tests/test_documents.py` | Tests for upload/list/status endpoints |
| `backend/app/tests/test_gcs.py` | Tests for GCS service |
| `backend/app/tests/test_airflow.py` | Tests for Airflow trigger + polling service |
| `backend/app/tests/test_document_processor.py` | Tests for the processing pipeline |

### Files to Modify
| File | Change |
|------|--------|
| `backend/app/db/models.py` | Add `user_id`, `gcs_path`, `task_id` columns to `Document`; remove `unique=True` on `title` |
| `backend/app/core/config.py` | Add GCS and Airflow settings |
| `backend/app/main.py` | Register documents router, add migration for new columns |
| `backend/app/services/rag.py` | Add `user_id` filter to `stream_answer` and `stream_conflict_answer` |
| `backend/app/services/graph_search.py` | Add `user_id` filter to Cypher queries |
| `backend/app/api/chat.py` | Pass `current_user.id` to RAG functions |
| `backend/ingestion/neo4j_writer.py` | Add `user_id` param to `upsert_graph_to_neo4j` |
| `requirements.txt` | Add `google-cloud-storage`, `google-auth` |

---

## Task 1: Add GCS and Airflow settings to config

**Files:**
- Modify: `backend/app/core/config.py:12-64`

- [ ] **Step 1: Add new settings fields**

In `backend/app/core/config.py`, add the following fields inside the `Settings` class, after the `phoenix_collector_endpoint` line (line 53):

```python
    # Google Cloud Storage — for temporary PDF and processed JSON storage
    gcs_bucket_name: str = ""
    gcs_credentials_path: str | None = None  # optional: path to service account JSON

    # Cloud Composer (Airflow) — for triggering and polling DAGs
    airflow_webserver_url: str = ""  # e.g. https://<env-id>-dot-us-central1.composer.googleusercontent.com
    airflow_dag_id: str = "document_processing"
```

- [ ] **Step 2: Add env vars to `.env.example`**

Append to `.env.example`:

```bash
# GCS — Personal document upload storage
GCS_BUCKET_NAME=your-bucket-name
GCS_CREDENTIALS_PATH=  # optional: path to SA JSON, empty = ADC

# Cloud Composer — PDF processing DAGs
AIRFLOW_WEBSERVER_URL=https://your-composer-env.composer.googleusercontent.com
AIRFLOW_DAG_ID=document_processing
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/config.py .env.example
git commit -m "feat: add GCS and Airflow settings to config"
```

---

## Task 2: Update Document model with user_id, gcs_path, task_id

**Files:**
- Modify: `backend/app/db/models.py:45-61`
- Test: `backend/app/tests/test_documents.py` (created in Task 5)

- [ ] **Step 1: Update the Document model**

Replace the `Document` class in `backend/app/db/models.py` (lines 45-61) with:

```python
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20))
    gcs_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
```

Key changes:
- Added `user_id` with ForeignKey to `users.id` and index.
- Removed `unique=True` from `title` (different users can upload docs with the same title).
- Added `gcs_path` (nullable) — GCS URI of the uploaded PDF.
- Added `task_id` (nullable) — Airflow DAG run ID for polling.

- [ ] **Step 2: Add migration in main.py**

In `backend/app/main.py`, add a new migration function after `_migrate_add_is_admin_column` (after line 88):

```python
async def _migrate_documents_table(engine) -> None:
    """
    Add user_id, gcs_path, task_id columns to documents table if not present.
    Safe to call on every startup; skipped if columns exist.
    """
    from sqlalchemy import text

    columns_to_add = [
        ("user_id", "INTEGER REFERENCES users(id)"),
        ("gcs_path", "VARCHAR(500)"),
        ("task_id", "VARCHAR(255)"),
    ]

    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(documents)"))
        existing_columns = {row[1] for row in result.fetchall()}

        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                await conn.execute(
                    text(f"ALTER TABLE documents ADD COLUMN {col_name} {col_type}")
                )
                print(f"[startup] Migration: added {col_name} column to documents table.")
            else:
                print(f"[startup] Migration: {col_name} column already exists — skipping.")
```

Then call it in the `lifespan` function, after line 134 (`_patch_admin_is_admin`):

```python
    await _migrate_documents_table(db_session_mod._engine)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/db/models.py backend/app/main.py
git commit -m "feat: add user_id, gcs_path, task_id to Document model"
```

---

## Task 3: Create GCS service

**Files:**
- Create: `backend/app/services/gcs.py`
- Create: `backend/app/tests/test_gcs.py`

- [ ] **Step 1: Write the failing test**

Create `backend/app/tests/test_gcs.py`:

```python
"""Tests for GCS upload/download service."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

from backend.app.services.gcs import upload_to_gcs, download_from_gcs


class TestUploadToGcs:
    def test_upload_returns_gcs_uri(self):
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        with patch("backend.app.services.gcs._get_gcs_client", return_value=mock_client):
            result = upload_to_gcs(
                file_content=b"fake pdf bytes",
                destination_blob_name="uploads/user_1/test.pdf",
                bucket_name="test-bucket",
            )

        assert result == "gs://test-bucket/uploads/user_1/test.pdf"
        mock_blob.upload_from_string.assert_called_once_with(
            b"fake pdf bytes", content_type="application/octet-stream"
        )

    def test_upload_uses_content_type(self):
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        with patch("backend.app.services.gcs._get_gcs_client", return_value=mock_client):
            upload_to_gcs(
                file_content=b"fake pdf",
                destination_blob_name="test.pdf",
                bucket_name="b",
                content_type="application/pdf",
            )

        mock_blob.upload_from_string.assert_called_once_with(
            b"fake pdf", content_type="application/pdf"
        )


class TestDownloadFromGcs:
    def test_download_returns_bytes(self):
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.download_as_bytes.return_value = b'{"chunks": []}'

        with patch("backend.app.services.gcs._get_gcs_client", return_value=mock_client):
            result = download_from_gcs(
                gcs_uri="gs://test-bucket/output/result.json",
            )

        assert result == b'{"chunks": []}'
        mock_client.bucket.assert_called_once_with("test-bucket")
        mock_bucket.blob.assert_called_once_with("output/result.json")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/app/tests/test_gcs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.services.gcs'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/services/gcs.py`:

```python
"""
backend/app/services/gcs.py
Thin wrapper around google-cloud-storage for PDF upload/download.
"""
from google.cloud import storage

from backend.app.core.config import get_settings


def _get_gcs_client() -> storage.Client:
    """Return a GCS client, optionally from a service account JSON file."""
    settings = get_settings()
    if settings.gcs_credentials_path:
        return storage.Client.from_service_account_json(settings.gcs_credentials_path)
    return storage.Client()


def upload_to_gcs(
    file_content: bytes,
    destination_blob_name: str,
    bucket_name: str,
    content_type: str = "application/octet-stream",
) -> str:
    """
    Upload bytes to GCS. Returns the gs:// URI.
    """
    client = _get_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_string(file_content, content_type=content_type)
    return f"gs://{bucket_name}/{destination_blob_name}"


def download_from_gcs(gcs_uri: str) -> bytes:
    """
    Download a blob from a gs:// URI. Returns raw bytes.
    """
    # Parse gs://bucket/path/to/blob
    parts = gcs_uri.replace("gs://", "").split("/", 1)
    bucket_name = parts[0]
    blob_name = parts[1]

    client = _get_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    return blob.download_as_bytes()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/app/tests/test_gcs.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/gcs.py backend/app/tests/test_gcs.py
git commit -m "feat: add GCS upload/download service with tests"
```

---

## Task 4: Create Airflow trigger and polling service

**Files:**
- Create: `backend/app/services/airflow.py`
- Create: `backend/app/tests/test_airflow.py`

- [ ] **Step 1: Write the failing test**

Create `backend/app/tests/test_airflow.py`:

```python
"""Tests for Cloud Composer DAG trigger and status polling."""
import pytest
from unittest.mock import patch, MagicMock

from backend.app.services.airflow import trigger_dag, get_dag_run_status


class TestTriggerDag:
    def test_trigger_dag_returns_run_id(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"dag_run_id": "manual__2026-06-23T00:00:00+00:00"}

        with patch("backend.app.services.airflow._airflow_request", return_value=mock_response):
            run_id = trigger_dag(
                gcs_uri="gs://bucket/uploads/user_1/doc.pdf",
                user_id=1,
                document_id=42,
                title="My Policy",
            )

        assert run_id == "manual__2026-06-23T00:00:00+00:00"

    def test_trigger_dag_raises_on_failure(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = Exception("500 Server Error")

        with patch("backend.app.services.airflow._airflow_request", return_value=mock_response):
            mock_response.raise_for_status.side_effect = Exception("500")
            with pytest.raises(Exception, match="500"):
                trigger_dag(
                    gcs_uri="gs://bucket/test.pdf",
                    user_id=1,
                    document_id=1,
                    title="Test",
                )


class TestGetDagRunStatus:
    @pytest.mark.parametrize("state", ["success", "failed", "running"])
    def test_returns_state(self, state):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"state": state}

        with patch("backend.app.services.airflow._airflow_request", return_value=mock_response):
            result = get_dag_run_status(dag_run_id="run-123")

        assert result == state
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/app/tests/test_airflow.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.services.airflow'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/services/airflow.py`:

```python
"""
backend/app/services/airflow.py
Cloud Composer (Airflow) DAG trigger and status polling via REST API.
Uses Google ADC (Application Default Credentials) for authentication.
"""
import json
import logging

import google.auth
import google.auth.transport.requests
import requests

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


def _get_id_token(audience: str) -> str:
    """Get a Google ID token for the given audience (Airflow webserver URL)."""
    credentials, _ = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token


def _airflow_request(method: str, endpoint: str, **kwargs) -> requests.Response:
    """Make an authenticated request to the Cloud Composer Airflow REST API."""
    settings = get_settings()
    base_url = settings.airflow_webserver_url.rstrip("/")
    url = f"{base_url}/api/v1{endpoint}"

    token = _get_id_token(base_url)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    return requests.request(method, url, headers=headers, timeout=30, **kwargs)


def trigger_dag(
    gcs_uri: str,
    user_id: int,
    document_id: int,
    title: str,
) -> str:
    """
    Trigger the document processing DAG on Cloud Composer.
    Returns the dag_run_id for status polling.
    """
    settings = get_settings()
    dag_id = settings.airflow_dag_id

    payload = {
        "conf": {
            "gcs_uri": gcs_uri,
            "user_id": user_id,
            "document_id": document_id,
            "title": title,
        }
    }

    response = _airflow_request(
        "POST",
        f"/dags/{dag_id}/dagRuns",
        data=json.dumps(payload),
    )
    response.raise_for_status()

    data = response.json()
    run_id = data.get("dag_run_id")
    logger.info("[airflow] Triggered DAG %s, run_id=%s", dag_id, run_id)
    return run_id


def get_dag_run_status(dag_run_id: str) -> str:
    """
    Poll the status of a DAG run.
    Returns one of: 'queued', 'running', 'success', 'failed'.
    """
    settings = get_settings()
    dag_id = settings.airflow_dag_id

    response = _airflow_request(
        "GET",
        f"/dags/{dag_id}/dagRuns/{dag_run_id}",
    )
    response.raise_for_status()

    state = response.json().get("state", "unknown")
    logger.info("[airflow] DAG run %s state: %s", dag_run_id, state)
    return state
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/app/tests/test_airflow.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/airflow.py backend/app/tests/test_airflow.py
git commit -m "feat: add Airflow DAG trigger and polling service with tests"
```

---

## Task 5: Create document upload/list/status API endpoints

**Files:**
- Create: `backend/app/api/documents.py`
- Create: `backend/app/tests/test_documents.py`
- Modify: `backend/app/main.py:161-165` (register router)

- [ ] **Step 1: Write the failing test**

Create `backend/app/tests/test_documents.py`:

```python
"""Tests for POST /api/documents/upload, GET /api/documents, GET /api/documents/{id}/status."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from backend.app.services.auth import create_access_token


def _make_token(username="testuser", is_admin=False, secret="a" * 32):
    return create_access_token(username, secret, expire_minutes=30, is_admin=is_admin)


@pytest.mark.asyncio
async def test_upload_requires_auth(auth_client):
    response = await auth_client.post("/api/documents/upload")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_returns_document_id(auth_client, db_session):
    from backend.app.db.models import User
    from backend.app.services.auth import hash_password

    user = User(username="uploader", hashed_password=hash_password("pass123"))
    db_session.add(user)
    await db_session.commit()

    token = _make_token("uploader")

    fake_pdf = b"%PDF-1.4 fake content"

    with (
        patch("backend.app.api.documents.upload_to_gcs", return_value="gs://bucket/uploads/1/test.pdf"),
        patch("backend.app.api.documents.trigger_dag", return_value="run-abc-123"),
        patch("backend.app.api.documents.BackgroundTasks") as mock_bg,
    ):
        response = await auth_client.post(
            "/api/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("policy.pdf", fake_pdf, "application/pdf")},
            data={"title": "My Policy"},
        )

    assert response.status_code == 201
    body = response.json()
    assert "id" in body
    assert body["status"] == "processing"
    assert body["title"] == "My Policy"


@pytest.mark.asyncio
async def test_list_documents_returns_own_only(auth_client, db_session):
    from backend.app.db.models import User, Document
    from backend.app.services.auth import hash_password

    user_a = User(username="user_a", hashed_password=hash_password("pass"))
    user_b = User(username="user_b", hashed_password=hash_password("pass"))
    db_session.add_all([user_a, user_b])
    await db_session.commit()
    await db_session.refresh(user_a)
    await db_session.refresh(user_b)

    doc_a = Document(user_id=user_a.id, title="Doc A", chunk_count=0, status="completed")
    doc_b = Document(user_id=user_b.id, title="Doc B", chunk_count=0, status="completed")
    db_session.add_all([doc_a, doc_b])
    await db_session.commit()

    token_a = _make_token("user_a")
    response = await auth_client.get(
        "/api/documents",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 200
    docs = response.json()["documents"]
    assert len(docs) == 1
    assert docs[0]["title"] == "Doc A"


@pytest.mark.asyncio
async def test_get_status(auth_client, db_session):
    from backend.app.db.models import User, Document
    from backend.app.services.auth import hash_password

    user = User(username="statususer", hashed_password=hash_password("pass"))
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    doc = Document(user_id=user.id, title="Status Doc", chunk_count=5, status="completed")
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    token = _make_token("statususer")
    response = await auth_client.get(
        f"/api/documents/{doc.id}/status",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["chunk_count"] == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/app/tests/test_documents.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.api.documents'`

- [ ] **Step 3: Write the implementation**

Create `backend/app/api/documents.py`:

```python
"""
backend/app/api/documents.py
Document upload, listing, and status endpoints.
POST /api/documents/upload — upload PDF, save to GCS, trigger Airflow DAG.
GET /api/documents — list user's documents.
GET /api/documents/{id}/status — check processing status.
"""
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.db.models import Document, User
from backend.app.db.session import get_db
from backend.app.services.auth import get_current_user
from backend.app.services.gcs import upload_to_gcs
from backend.app.services.airflow import trigger_dag

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Response models ─────────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: int
    title: str
    status: str
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentStatusResponse(BaseModel):
    id: int
    title: str
    status: str
    chunk_count: int


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.post("/documents/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Upload a PDF document for processing.
    1. Validates file is PDF.
    2. Uploads to GCS.
    3. Triggers Airflow DAG.
    4. Creates Document record with status='processing'.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported.",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    settings = get_settings()
    blob_name = f"uploads/{current_user.id}/{file.filename}"

    # Upload to GCS
    gcs_uri = upload_to_gcs(
        file_content=content,
        destination_blob_name=blob_name,
        bucket_name=settings.gcs_bucket_name,
        content_type="application/pdf",
    )

    # Create Document record first
    doc = Document(
        user_id=current_user.id,
        title=title,
        chunk_count=0,
        status="processing",
        gcs_path=gcs_uri,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Trigger Airflow DAG
    try:
        run_id = trigger_dag(
            gcs_uri=gcs_uri,
            user_id=current_user.id,
            document_id=doc.id,
            title=title,
        )
        doc.task_id = run_id
        await db.commit()
    except Exception:
        logger.exception("Failed to trigger Airflow DAG for document %d", doc.id)
        doc.status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to trigger document processing pipeline.",
        )

    # Schedule background polling
    from backend.app.services.document_processor import poll_and_ingest
    background_tasks.add_task(poll_and_ingest, doc.id)

    return DocumentResponse.model_validate(doc)


@router.get("/documents", response_model=dict)
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """GET /api/documents — list all documents owned by the current user."""
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return {
        "documents": [DocumentResponse.model_validate(d) for d in docs]
    }


@router.get("/documents/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentStatusResponse:
    """GET /api/documents/{id}/status — check processing status of a document."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return DocumentStatusResponse(
        id=doc.id,
        title=doc.title,
        status=doc.status,
        chunk_count=doc.chunk_count,
    )
```

- [ ] **Step 4: Register the router in main.py**

In `backend/app/main.py`, add the import at line 20 (after `sources_router`):

```python
from backend.app.api.documents import router as documents_router
```

And add the route registration after line 164 (after `admin_router`):

```python
    app.include_router(documents_router, prefix="/api", tags=["documents"])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest backend/app/tests/test_documents.py -v`
Expected: PASS (upload test may need `document_processor` stub — create an empty module if needed)

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/documents.py backend/app/tests/test_documents.py backend/app/main.py
git commit -m "feat: add document upload/list/status API endpoints"
```

---

## Task 6: Create document processor (poll → download → embed → upsert)

**Files:**
- Create: `backend/app/services/document_processor.py`
- Create: `backend/app/tests/test_document_processor.py`

- [ ] **Step 1: Write the failing test**

Create `backend/app/tests/test_document_processor.py`:

```python
"""Tests for the background document processing pipeline."""
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from backend.app.services.document_processor import _process_result


@pytest.mark.asyncio
async def test_process_result_upserts_to_qdrant_and_neo4j():
    """Given processed JSON, embed chunks and upsert to both Qdrant and Neo4j."""
    processed_data = {
        "chunks": [
            {
                "text": "Users have the right to delete their data.",
                "passage_id": "doc-1",
                "chunk_index": 0,
                "title": "My Policy",
                "source_doc": "My Policy",
                "token_count": 10,
            }
        ],
        "graphs": [
            {
                "chunk_index": 0,
                "entities": [{"name": "Users", "type": "Actor", "description": "App users"}],
                "relationships": [],
            }
        ],
    }

    mock_openrouter = MagicMock()
    embed_resp = MagicMock()
    embed_resp.data = [MagicMock(embedding=[0.1] * 128, index=0)]
    mock_openrouter.embeddings.create = AsyncMock(return_value=embed_resp)

    mock_qdrant = MagicMock()
    upsert_result = MagicMock()
    upsert_result.status = "completed"
    mock_qdrant.upsert = AsyncMock(return_value=upsert_result)

    mock_neo4j = MagicMock()
    mock_neo4j.execute_query = MagicMock(return_value=[])

    with (
        patch("backend.app.services.document_processor._make_openrouter", return_value=mock_openrouter),
        patch("backend.app.services.document_processor._make_qdrant", return_value=mock_qdrant),
        patch("backend.app.services.document_processor.Neo4jClient", return_value=mock_neo4j),
    ):
        await _process_result(
            processed_data=processed_data,
            user_id=1,
            document_id=42,
            title="My Policy",
        )

    # Verify embedding was called
    mock_openrouter.embeddings.create.assert_called_once()

    # Verify Qdrant upsert was called
    mock_qdrant.upsert.assert_called_once()

    # Verify Neo4j upsert was called with user_id
    mock_neo4j.execute_query.assert_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/app/tests/test_document_processor.py::test_process_result_upserts_to_qdrant_and_neo4j -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

Create `backend/app/services/document_processor.py`:

```python
"""
backend/app/services/document_processor.py
Background task: poll Airflow for completion, download processed JSON from GCS,
embed chunks via OpenRouter, upsert to Qdrant and Neo4j with user_id isolation.
"""
import asyncio
import json
import logging
import re
import uuid

from openai import AsyncOpenAI
from qdrant_client.models import PointStruct

from backend.app.core.config import get_settings
from backend.app.core.qdrant_client import make_qdrant_client
from backend.app.db.models import Document
from backend.app.db.neo4j_client import Neo4jClient
from backend.app.services.airflow import get_dag_run_status
from backend.app.services.gcs import download_from_gcs

logger = logging.getLogger(__name__)

COLLECTION_NAME = "policies"
EMBED_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
BATCH_SIZE = 50
POLL_INTERVAL_SECONDS = 30
MAX_POLL_ATTEMPTS = 120  # 30s * 120 = 1 hour max


def _make_openrouter() -> AsyncOpenAI:
    settings = get_settings()
    return AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
        default_headers={
            "HTTP-Referer": "https://github.com/privacy-policy-compliance-assistant",
            "X-Title": "Privacy Policy Compliance Assistant",
        },
    )


def _make_qdrant():
    settings = get_settings()
    return make_qdrant_client(settings)


async def _embed_texts(openrouter: AsyncOpenAI, texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts via Nemotron on OpenRouter."""
    nemotron_input = [
        {"content": [{"type": "text", "text": t}]} for t in texts
    ]
    resp = await openrouter.embeddings.create(
        model=EMBED_MODEL,
        input=["ignored"],
        extra_body={"input": nemotron_input},
        encoding_format="float",
    )
    return [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]


async def _process_result(
    processed_data: dict,
    user_id: int,
    document_id: int,
    title: str,
) -> int:
    """
    Given processed data from Airflow (chunks + graphs), embed and upsert
    to Qdrant and Neo4j with user_id isolation.
    Returns the number of chunks upserted.
    """
    chunks = processed_data.get("chunks", [])
    graphs = processed_data.get("graphs", [])

    if not chunks:
        logger.warning("[processor] No chunks in processed data for document %d", document_id)
        return 0

    openrouter = _make_openrouter()
    qdrant = _make_qdrant()
    neo4j_client = Neo4jClient()

    user_id_str = str(user_id)
    total_upserted = 0

    for batch_start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[batch_start:batch_start + BATCH_SIZE]
        texts = [c["text"] for c in batch]

        # Embed
        embeddings = await _embed_texts(openrouter, texts)

        # Build Qdrant points with user_id in payload
        points = []
        for chunk, embedding in zip(batch, embeddings):
            point_id = str(uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"{user_id}:{chunk['passage_id']}:{chunk['chunk_index']}"
            ))
            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "title": title,
                    "source_doc": title,
                    "passage_id": chunk["passage_id"],
                    "text": chunk["text"],
                    "chunk_index": chunk["chunk_index"],
                    "token_count": chunk.get("token_count", 0),
                    "user_id": user_id_str,
                    "file_type": "pdf",
                },
            ))

        await qdrant.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
        total_upserted += len(points)

    # Upsert graph data to Neo4j with user_id isolation
    graph_by_index = {g["chunk_index"]: g for g in graphs}
    for chunk in chunks:
        idx = chunk["chunk_index"]
        if idx in graph_by_index:
            graph = graph_by_index[idx]
            chunk_id = str(uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"{user_id}:{chunk['passage_id']}:{idx}"
            ))
            _upsert_graph_with_user_id(
                neo4j_client=neo4j_client,
                chunk_id=chunk_id,
                chunk_text=chunk["text"],
                passage_id=chunk["passage_id"],
                graph=graph,
                user_id=user_id_str,
            )

    return total_upserted


def _upsert_graph_with_user_id(
    neo4j_client: Neo4jClient,
    chunk_id: str,
    chunk_text: str,
    passage_id: str,
    graph: dict,
    user_id: str,
) -> None:
    """Upsert graph nodes and edges to Neo4j, tagging with user_id for isolation."""
    # Create Chunk node with user_id
    neo4j_client.execute_query(
        "MERGE (c:Chunk {id: $chunk_id}) "
        "SET c.text = $text, c.passage_id = $passage_id, c.user_id = $user_id",
        {"chunk_id": chunk_id, "text": chunk_text, "passage_id": passage_id, "user_id": user_id}
    )

    # Create Entities with user_id and link to Chunk
    for entity in graph.get("entities", []):
        if not entity.get("name"):
            continue
        neo4j_client.execute_query(
            "MATCH (c:Chunk {id: $chunk_id}) "
            "MERGE (e:Entity {name: $name, user_id: $user_id}) "
            "ON CREATE SET e.type = $type, e.description = $desc "
            "MERGE (c)-[:MENTIONS]->(e)",
            {
                "chunk_id": chunk_id,
                "name": entity.get("name"),
                "type": entity.get("type", "Unknown"),
                "desc": entity.get("description", ""),
                "user_id": user_id,
            }
        )

    # Create Relationships between Entities (scoped by user_id)
    for rel_data in graph.get("relationships", []):
        source = rel_data.get("source")
        target = rel_data.get("target")
        raw_type = rel_data.get("type", "RELATED_TO").upper()
        rel_type = re.sub(r'[^A-Z0-9_]', '_', raw_type)

        if not source or not target:
            continue

        neo4j_client.execute_query(
            "MERGE (s:Entity {name: $source, user_id: $user_id}) "
            "MERGE (t:Entity {name: $target, user_id: $user_id}) "
            f"MERGE (s)-[r:{rel_type}]->(t) "
            "SET r.description = $desc",
            {
                "source": source,
                "target": target,
                "desc": rel_data.get("description", ""),
                "user_id": user_id,
            }
        )


async def poll_and_ingest(document_id: int) -> None:
    """
    Background task: poll Airflow until DAG succeeds or fails,
    then download processed result and ingest into Qdrant + Neo4j.
    """
    from backend.app.db import session as db_session_mod

    for attempt in range(MAX_POLL_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

        # Load document from DB
        async with db_session_mod._session_factory() as session:
            doc = await session.get(Document, document_id)
            if doc is None:
                logger.error("[processor] Document %d not found — aborting", document_id)
                return

            if not doc.task_id:
                logger.error("[processor] Document %d has no task_id — aborting", document_id)
                doc.status = "failed"
                await session.commit()
                return

            # Poll Airflow
            try:
                state = get_dag_run_status(doc.task_id)
            except Exception:
                logger.exception("[processor] Failed to poll Airflow for document %d", document_id)
                continue  # retry on next poll

            if state == "running" or state == "queued":
                continue  # keep polling

            if state == "failed":
                logger.error("[processor] Airflow DAG failed for document %d", document_id)
                doc.status = "failed"
                await session.commit()
                return

            if state == "success":
                # Download processed result from GCS
                gcs_result_path = doc.gcs_path.replace("uploads/", "processed/").replace(".pdf", ".json")
                try:
                    raw = download_from_gcs(gcs_result_path)
                    processed_data = json.loads(raw)
                except Exception:
                    logger.exception("[processor] Failed to download/parse result for document %d", document_id)
                    doc.status = "failed"
                    await session.commit()
                    return

                # Ingest into Qdrant + Neo4j
                try:
                    count = await _process_result(
                        processed_data=processed_data,
                        user_id=doc.user_id,
                        document_id=doc.id,
                        title=doc.title,
                    )
                    doc.chunk_count = count
                    doc.status = "completed"
                    logger.info("[processor] Document %d completed: %d chunks", document_id, count)
                except Exception:
                    logger.exception("[processor] Ingestion failed for document %d", document_id)
                    doc.status = "failed"

                await session.commit()
                return

    # Max polling reached
    async with db_session_mod._session_factory() as session:
        doc = await session.get(Document, document_id)
        if doc and doc.status == "processing":
            doc.status = "failed"
            await session.commit()
            logger.error("[processor] Max polling reached for document %d — marking failed", document_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/app/tests/test_document_processor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/document_processor.py backend/app/tests/test_document_processor.py
git commit -m "feat: add document processor (poll, embed, upsert to Qdrant+Neo4j)"
```

---

## Task 7: Add user_id filter to RAG retrieval (Qdrant)

**Files:**
- Modify: `backend/app/services/rag.py:13` (add MatchAny import)
- Modify: `backend/app/services/rag.py:165-171` (stream_answer signature)
- Modify: `backend/app/services/rag.py:206-215` (Qdrant query_points filter)
- Modify: `backend/app/services/rag.py:328-334` (stream_conflict_answer signature)
- Modify: `backend/app/services/rag.py:370-379` (conflict Qdrant filter)
- Modify: `backend/app/api/chat.py:142-145` (pass user_id)

- [ ] **Step 1: Add MatchAny import at the top of rag.py**

Update line 13 of `backend/app/services/rag.py`:

```python
from qdrant_client.models import Filter, FieldCondition, MatchAny, MatchValue
```

- [ ] **Step 2: Update `stream_answer` signature and filter**

Update the `stream_answer` function signature (line 165) to add `user_id` parameter:

```python
async def stream_answer(
    message: str,
    history: list[dict],
    temperature: float = 0.0,
    max_tokens: int = 1024,
    source_filter: str | None = None,
    user_id: int | None = None,
) -> AsyncGenerator[dict, None]:
```

Then replace the Qdrant `query_points` call (around lines 206-215) with:

```python
        # Build Qdrant filter: user_id isolation + optional source_filter
        filter_conditions = []
        if source_filter:
            filter_conditions.append(
                FieldCondition(key="title", match=MatchValue(value=source_filter))
            )
        if user_id is not None:
            filter_conditions.append(
                FieldCondition(key="user_id", match=MatchAny(any=[str(user_id), "system"]))
            )

        response = await qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=5,
            score_threshold=_threshold,
            with_payload=True,
            query_filter=Filter(must=filter_conditions) if filter_conditions else None,
        )
```

- [ ] **Step 3: Apply the same pattern to `stream_conflict_answer`**

Update the `stream_conflict_answer` signature (line 328) to add `user_id`:

```python
async def stream_conflict_answer(
    message: str,
    history: list[dict],
    temperature: float = 0.0,
    max_tokens: int = 1024,
    source_filter: str | None = None,
    user_id: int | None = None,
) -> AsyncGenerator[dict, None]:
```

And replace its `query_points` call (around lines 370-379) with the same filter pattern:

```python
        filter_conditions = []
        if source_filter:
            filter_conditions.append(
                FieldCondition(key="title", match=MatchValue(value=source_filter))
            )
        if user_id is not None:
            filter_conditions.append(
                FieldCondition(key="user_id", match=MatchAny(any=[str(user_id), "system"]))
            )

        response = await qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=10,
            score_threshold=_threshold,
            with_payload=True,
            query_filter=Filter(must=filter_conditions) if filter_conditions else None,
        )
```

- [ ] **Step 4: Pass `current_user.id` from chat endpoint**

In `backend/app/api/chat.py`, update the `_generate` inner function (around lines 142-145) to pass `user_id`:

```python
                if is_conflict_query(body.message):
                    generator = rag.stream_conflict_answer(body.message, history, source_filter=body.source_filter, user_id=current_user.id)
                else:
                    generator = rag.stream_answer(body.message, history, source_filter=body.source_filter, user_id=current_user.id)
```

- [ ] **Step 5: Run existing tests**

Run: `python -m pytest backend/app/tests/test_rag.py backend/app/tests/test_chat_endpoint.py -v`
Expected: All existing tests PASS (they don't pass `user_id`, so the filter is not applied — backward compatible)

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/rag.py backend/app/api/chat.py
git commit -m "feat: add user_id filter to Qdrant RAG retrieval for data isolation"
```

---

## Task 8: Add user_id filter to Neo4j graph retrieval

**Files:**
- Modify: `backend/app/services/graph_search.py:58-91`
- Modify: `backend/app/services/rag.py:199-200` (pass user_id to graph_search)
- Modify: `backend/app/services/rag.py:364-365` (same for conflict path)

- [ ] **Step 1: Update `retrieve_graph_context` to accept `user_id`**

In `backend/app/services/graph_search.py`, replace the `retrieve_graph_context` function (lines 58-91) with:

```python
def retrieve_graph_context(entities: list[str], limit: int = 5, user_id: int | None = None) -> list[str]:
    if not entities:
        return []
        
    neo4j_client = Neo4jClient()

    # Build query: if user_id is provided, filter entities to user's own + system
    if user_id is not None:
        query = """
        UNWIND $entities AS entity_name
        MATCH (e:Entity {name: entity_name})
        WHERE e.user_id = $user_id_str OR e.user_id = 'system' OR NOT exists(e.user_id)
        MATCH (c:Chunk)-[:MENTIONS]->(e)
        WHERE c.user_id = $user_id_str OR c.user_id = 'system' OR NOT exists(c.user_id)
        RETURN DISTINCT c.text AS chunk_text, c.passage_id AS passage_id, c.id AS chunk_id
        LIMIT $limit
        """
        params = {"entities": entities, "limit": limit, "user_id_str": str(user_id)}
    else:
        query = """
        UNWIND $entities AS entity_name
        MATCH (e:Entity {name: entity_name})
        MATCH (c:Chunk)-[:MENTIONS]->(e)
        RETURN DISTINCT c.text AS chunk_text, c.passage_id AS passage_id, c.id AS chunk_id
        LIMIT $limit
        """
        params = {"entities": entities, "limit": limit}

    try:
        if _tracer:
            with _tracer.start_as_current_span(
                "neo4j.retrieve",
                attributes={
                    "neo4j.query.text": query.strip(),
                    "neo4j.query.entities": str(entities),
                    "neo4j.query.limit": limit,
                }
            ) as span:
                records = neo4j_client.execute_query(query, params)
                if span:
                    span.set_attribute("neo4j.results_count", len(records))
        else:
            records = neo4j_client.execute_query(query, params)
            
        return [record["chunk_text"] for record in records]
    except Exception as e:
        print(f"Neo4j retrieval error: {e}")
        return []
```

- [ ] **Step 2: Pass `user_id` from both RAG pipelines**

In `backend/app/services/rag.py`, update the `retrieve_graph_context` call in `stream_answer` (around line 200):

```python
    graph_texts = retrieve_graph_context(entities, limit=3, user_id=user_id)
```

And in `stream_conflict_answer` (around line 365):

```python
    graph_texts = retrieve_graph_context(entities, limit=3, user_id=user_id)
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest backend/app/tests/test_rag.py -v`
Expected: All tests PASS (existing calls pass `user_id=None`, preserving old behavior)

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/graph_search.py backend/app/services/rag.py
git commit -m "feat: add user_id filter to Neo4j graph retrieval for data isolation"
```

---

## Task 9: Add dependencies to requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add new dependencies**

Append to `requirements.txt`:

```
google-cloud-storage>=2.14.0
google-auth>=2.28.0
```

- [ ] **Step 2: Commit**

```bash
git add requirements.txt
git commit -m "deps: add google-cloud-storage and google-auth"
```

---

## Task 10: Update existing neo4j_writer.py with user_id support

**Files:**
- Modify: `backend/ingestion/neo4j_writer.py`

This task ensures the existing batch ingestion pipeline (`ingest.py` / `ingest_doc.py`) also writes `user_id` to Neo4j. For system-wide corpus data, `user_id` defaults to `"system"`.

- [ ] **Step 1: Update function signature and queries**

Replace the entire content of `backend/ingestion/neo4j_writer.py`:

```python
import re

from backend.app.db.neo4j_client import Neo4jClient


def upsert_graph_to_neo4j(
    chunk_id: str,
    chunk_text: str,
    passage_id: str,
    graph: dict,
    neo4j_client: Neo4jClient,
    user_id: str = "system",
):
    # 1. Create Chunk node with user_id
    neo4j_client.execute_query(
        "MERGE (c:Chunk {id: $chunk_id}) "
        "SET c.text = $text, c.passage_id = $passage_id, c.user_id = $user_id",
        {"chunk_id": chunk_id, "text": chunk_text, "passage_id": passage_id, "user_id": user_id}
    )
    
    # 2. Create Entities with user_id and link to Chunk
    for entity in graph.get("entities", []):
        if not entity.get("name"):
            continue
        neo4j_client.execute_query(
            "MATCH (c:Chunk {id: $chunk_id}) "
            "MERGE (e:Entity {name: $name, user_id: $user_id}) "
            "ON CREATE SET e.type = $type, e.description = $desc "
            "MERGE (c)-[:MENTIONS]->(e)",
            {
                "chunk_id": chunk_id,
                "name": entity.get("name"),
                "type": entity.get("type", "Unknown"),
                "desc": entity.get("description", ""),
                "user_id": user_id,
            }
        )
        
    # 3. Create Relationships between Entities (scoped by user_id)
    for rel_data in graph.get("relationships", []):
        source = rel_data.get("source")
        target = rel_data.get("target")
        raw_type = rel_data.get("type", "RELATED_TO").upper()
        rel_type = re.sub(r'[^A-Z0-9_]', '_', raw_type)
        
        if not source or not target:
            continue
            
        neo4j_client.execute_query(
            "MERGE (s:Entity {name: $source, user_id: $user_id}) "
            "MERGE (t:Entity {name: $target, user_id: $user_id}) "
            f"MERGE (s)-[r:{rel_type}]->(t) "
            "SET r.description = $desc",
            {
                "source": source,
                "target": target,
                "desc": rel_data.get("description", ""),
                "user_id": user_id,
            }
        )
```

- [ ] **Step 2: Run existing ingestion tests**

Run: `python -m pytest backend/ingestion/tests/ -v`
Expected: All PASS. The `user_id` parameter defaults to `"system"`, so existing callers are unaffected.

- [ ] **Step 3: Commit**

```bash
git add backend/ingestion/neo4j_writer.py
git commit -m "feat: add user_id param to neo4j_writer (default='system')"
```

---

## Task 11: Integration smoke test

**Files:**
- No new files — run existing and new test suites together.

- [ ] **Step 1: Run full test suite**

```bash
python -m pytest backend/ -v --tb=short
```

Expected: All tests PASS. No regressions from the new `user_id` parameter additions (all new params have defaults).

- [ ] **Step 2: Verify no import cycles**

```bash
python -c "from backend.app.api.documents import router; print('OK')"
python -c "from backend.app.services.document_processor import poll_and_ingest; print('OK')"
python -c "from backend.app.services.gcs import upload_to_gcs; print('OK')"
python -c "from backend.app.services.airflow import trigger_dag; print('OK')"
```

Expected: All print `OK`.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "test: verify integration — all tests pass, no import cycles"
```

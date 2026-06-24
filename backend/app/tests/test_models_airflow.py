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

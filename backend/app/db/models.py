"""
backend/app/db/models.py
SQLAlchemy 2.0 declarative User model.
Single table: users (id, username, hashed_password, created_at, is_admin).
D-01: is_admin bool column — existing rows default to False via ALTER TABLE migration in main.py.
Decision D-11: SQLite file at backend/data/users.db, no Alembic for v1.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String, Integer, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class QueryLog(Base):
    __tablename__ = "query_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    query_text: Mapped[str] = mapped_column(String(4000))
    topic: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


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

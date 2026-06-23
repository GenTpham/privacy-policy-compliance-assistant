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

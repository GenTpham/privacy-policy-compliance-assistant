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

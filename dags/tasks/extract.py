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

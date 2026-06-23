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

"""
Google Cloud Storage Service.
Handles streaming uploads using google-cloud-storage.
"""
import asyncio
from typing import BinaryIO

from google.cloud import storage

from backend.app.core.config import get_settings


async def upload_file_to_gcs(
    file_obj: BinaryIO,
    destination_blob_name: str,
    content_type: str = "application/pdf"
) -> str:
    """
    Uploads a file object to GCS.
    Runs the synchronous GCP client in a threadpool to avoid blocking the event loop.

    Returns:
        The gs:// URI of the uploaded file.
    """
    settings = get_settings()

    def _upload():
        if settings.gcs_credentials_path:
            client = storage.Client.from_service_account_json(
                settings.gcs_credentials_path, project=settings.gcp_project_id
            )
        else:
            # Uses Application Default Credentials (ADC)
            client = storage.Client(project=settings.gcp_project_id)

        bucket = client.bucket(settings.gcs_bucket)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_file(file_obj, content_type=content_type)
        return f"gs://{settings.gcs_bucket}/{destination_blob_name}"

    loop = asyncio.get_running_loop()
    gs_uri = await loop.run_in_executor(None, _upload)
    return gs_uri

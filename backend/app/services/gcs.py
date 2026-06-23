"""
backend/app/services/gcs.py
Thin wrapper around google-cloud-storage for PDF upload/download.
"""
from google.cloud import storage
import functools

from backend.app.core.config import get_settings


@functools.lru_cache()
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

import io
import pytest
from unittest.mock import MagicMock, patch

from backend.app.services.gcs import upload_file_to_gcs

@pytest.mark.asyncio
@patch("backend.app.services.gcs.storage")
@patch("backend.app.services.gcs.get_settings")
async def test_upload_file_to_gcs(mock_get_settings, mock_storage):
    # Setup mock settings
    mock_settings = MagicMock()
    mock_settings.gcs_bucket = "test-bucket"
    mock_settings.gcp_project_id = "test-project"
    mock_settings.gcs_credentials_path = None
    mock_get_settings.return_value = mock_settings

    # Setup mock GCS client
    mock_client = MagicMock()
    mock_storage.Client.return_value = mock_client
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob

    # Test data
    file_obj = io.BytesIO(b"dummy pdf content")
    destination_blob_name = "uploads/tenant1/doc1.pdf"

    # Execute
    result_path = await upload_file_to_gcs(file_obj, destination_blob_name, "application/pdf")

    # Assert
    assert result_path == "gs://test-bucket/uploads/tenant1/doc1.pdf"
    mock_storage.Client.assert_called_once_with(project="test-project")
    mock_client.bucket.assert_called_once_with("test-bucket")
    mock_bucket.blob.assert_called_once_with(destination_blob_name)
    mock_blob.upload_from_file.assert_called_once_with(file_obj, content_type="application/pdf")

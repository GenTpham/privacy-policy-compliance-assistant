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

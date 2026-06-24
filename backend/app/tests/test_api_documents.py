import pytest
from unittest.mock import patch, MagicMock
from backend.app.main import create_app
from backend.app.services.auth import get_current_user
from backend.app.db.models import User

@pytest.mark.asyncio
@patch("backend.app.api.endpoints.documents.upload_file_to_gcs")
@patch("backend.app.api.endpoints.documents.trigger_dag")
async def test_upload_document_endpoint(mock_trigger_dag, mock_upload_gcs, auth_client, db_session):
    # Setup mocks
    mock_upload_gcs.return_value = "gs://bucket/test.pdf"
    
    # Override auth
    app = auth_client._transport.app
    mock_user = User(id=1, username="testuser")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    
    # Execute
    with open("requirements.txt", "rb") as f:
        response = await auth_client.post(
            "/api/documents/",
            files={"file": ("test.pdf", f, "application/pdf")},
            data={"tenant_id": "tenant1"}
        )
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "document_id" in data
    assert "job_id" in data
    assert data["status"] == "processing"
    
    # Verify calls
    mock_upload_gcs.assert_called_once()
    mock_trigger_dag.assert_called_once()

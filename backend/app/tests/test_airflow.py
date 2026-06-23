import pytest
import respx
import httpx
from unittest.mock import patch, MagicMock

from backend.app.services.airflow import trigger_dag

@pytest.fixture
def mock_settings():
    with patch("backend.app.services.airflow.get_settings") as mock:
        settings = MagicMock()
        settings.airflow_base_url = "http://airflow"
        settings.airflow_username = "admin"
        settings.airflow_password = "password"
        settings.airflow_dag_id = "pdf_ingestion"
        mock.return_value = settings
        yield settings

@pytest.mark.asyncio
@respx.mock
async def test_trigger_dag_success(mock_settings):
    # Mock the Airflow API response
    dag_run_id = "ingest_123"
    route = respx.post(
        f"http://airflow/api/v1/dags/pdf_ingestion/dagRuns"
    ).mock(return_value=httpx.Response(200, json={"dag_run_id": dag_run_id, "state": "queued"}))

    conf = {"doc_id": "123", "gcs_path": "gs://bucket/test.pdf"}
    
    # Execute
    result = await trigger_dag(dag_run_id=dag_run_id, conf=conf)

    # Assert
    assert result["dag_run_id"] == dag_run_id
    assert result["state"] == "queued"
    assert route.called
    request = route.calls.last.request
    assert request.headers["authorization"].startswith("Basic ")

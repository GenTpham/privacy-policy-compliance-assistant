"""Tests for Cloud Composer DAG trigger and status polling."""
import pytest
from unittest.mock import patch, MagicMock

from backend.app.services.airflow import trigger_dag, get_dag_run_status


class TestTriggerDag:
    def test_trigger_dag_returns_run_id(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"dag_run_id": "manual__2026-06-23T00:00:00+00:00"}

        with patch("backend.app.services.airflow._airflow_request", return_value=mock_response):
            run_id = trigger_dag(
                gcs_uri="gs://bucket/uploads/user_1/doc.pdf",
                user_id=1,
                document_id=42,
                title="My Policy",
            )

        assert run_id == "manual__2026-06-23T00:00:00+00:00"

    def test_trigger_dag_raises_on_failure(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = Exception("500 Server Error")

        with patch("backend.app.services.airflow._airflow_request", return_value=mock_response):
            mock_response.raise_for_status.side_effect = Exception("500")
            with pytest.raises(Exception, match="500"):
                trigger_dag(
                    gcs_uri="gs://bucket/test.pdf",
                    user_id=1,
                    document_id=1,
                    title="Test",
                )


class TestGetDagRunStatus:
    @pytest.mark.parametrize("state", ["success", "failed", "running"])
    def test_returns_state(self, state):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"state": state}

        with patch("backend.app.services.airflow._airflow_request", return_value=mock_response):
            result = get_dag_run_status(dag_run_id="run-123")

        assert result == state

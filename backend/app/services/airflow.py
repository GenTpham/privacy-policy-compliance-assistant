"""
backend/app/services/airflow.py
Cloud Composer (Airflow) DAG trigger and status polling via REST API.
Uses Google ADC (Application Default Credentials) for authentication.
"""
import logging

import google.auth
import google.auth.transport.requests
import requests

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


def _get_access_token() -> str:
    """Get a Google OAuth 2.0 Access Token for Cloud Composer."""
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token


def _airflow_request(method: str, endpoint: str, **kwargs) -> requests.Response:
    """Make an authenticated request to the Cloud Composer Airflow REST API."""
    settings = get_settings()
    base_url = settings.airflow_webserver_url.rstrip("/")
    url = f"{base_url}/api/v1{endpoint}"

    token = _get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
    }

    return requests.request(method, url, headers=headers, timeout=30, **kwargs)


def trigger_dag(
    gcs_uri: str,
    user_id: int,
    document_id: int,
    title: str,
) -> str:
    """
    Trigger the document processing DAG on Cloud Composer.
    Returns the dag_run_id for status polling.
    """
    settings = get_settings()
    dag_id = settings.airflow_dag_id

    payload = {
        "conf": {
            "gcs_uri": gcs_uri,
            "user_id": user_id,
            "document_id": document_id,
            "title": title,
        }
    }

    response = _airflow_request(
        "POST",
        f"/dags/{dag_id}/dagRuns",
        json=payload,
    )
    response.raise_for_status()

    data = response.json()
    run_id = data.get("dag_run_id")
    logger.info("[airflow] Triggered DAG %s, run_id=%s", dag_id, run_id)
    return run_id


def get_dag_run_status(dag_run_id: str) -> str:
    """
    Poll the status of a DAG run.
    Returns one of: 'queued', 'running', 'success', 'failed'.
    """
    settings = get_settings()
    dag_id = settings.airflow_dag_id

    response = _airflow_request(
        "GET",
        f"/dags/{dag_id}/dagRuns/{dag_run_id}",
    )
    response.raise_for_status()

    state = response.json().get("state", "unknown")
    logger.info("[airflow] DAG run %s state: %s", dag_run_id, state)
    return state

"""
Airflow HTTP client.
Triggers DAGs via Airflow's REST API using httpx.
"""
from typing import Any, Dict

import httpx

from backend.app.core.config import get_settings


async def trigger_dag(dag_run_id: str, conf: Dict[str, Any]) -> dict:
    """
    Triggers the ingestion DAG idempotently.
    Airflow will reject a duplicate dag_run_id with a 409 Conflict,
    which is handled safely if it occurs.
    """
    settings = get_settings()
    url = f"{settings.airflow_base_url}/api/v1/dags/{settings.airflow_dag_id}/dagRuns"
    
    payload = {
        "dag_run_id": dag_run_id,
        "conf": conf
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json=payload,
            auth=(settings.airflow_username, settings.airflow_password),
            headers={"Content-Type": "application/json"}
        )
        
        # 409 means the dag_run_id already exists (idempotency check passed)
        if response.status_code == 409:
            return {"dag_run_id": dag_run_id, "state": "already_exists"}
            
        response.raise_for_status()
        return response.json()

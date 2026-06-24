"""
Task: upsert_neo4j
Downloads graph JSON from GCS and upserts entities+relationships to Neo4j Aura.
"""
import json

from google.cloud import storage
from neo4j import GraphDatabase

from tasks.db_status import update_current_task


def _get_neo4j_driver():
    """Get Neo4j driver from Airflow Variables."""
    try:
        from airflow.models import Variable
        uri = Variable.get("neo4j_uri")
        username = Variable.get("neo4j_username")
        password = Variable.get("neo4j_password")
    except Exception:
        import os
        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        username = os.environ.get("NEO4J_USERNAME", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "")

    return GraphDatabase.driver(uri, auth=(username, password))


def upsert_neo4j(**context) -> None:
    """
    Airflow PythonOperator callable.
    Downloads graph JSON from GCS, upserts to Neo4j Aura.
    Entities include tenant_id + user_id for data isolation.
    """
    conf = context["dag_run"].conf
    job_id = conf["job_id"]
    tenant_id = conf["tenant_id"]
    user_id = conf["user_id"]

    update_current_task(job_id, "upsert_neo4j")

    ti = context["ti"]
    gcs_graph_path = ti.xcom_pull(task_ids="build_graph")

    # Download graph JSON
    path = gcs_graph_path.replace("gs://", "")
    bucket_name, _, blob_name = path.partition("/")
    gcs_client = storage.Client()
    graph_data = json.loads(
        gcs_client.bucket(bucket_name).blob(blob_name).download_as_text()
    )

    driver = _get_neo4j_driver()

    with driver.session() as session:
        # Upsert entities
        for entity in graph_data.get("entities", []):
            session.run(
                """
                MERGE (e:Entity {name: $name, tenant_id: $tenant_id, user_id: $user_id})
                SET e.type = $type, e.doc_id = $doc_id, e.chunk_id = $chunk_id
                """,
                name=entity["name"],
                type=entity.get("type", "Unknown"),
                tenant_id=tenant_id,
                user_id=user_id,
                doc_id=entity.get("doc_id"),
                chunk_id=entity.get("chunk_id"),
            )

        # Upsert relationships
        for rel in graph_data.get("relationships", []):
            session.run(
                """
                MATCH (s:Entity {name: $source, tenant_id: $tenant_id, user_id: $user_id})
                MATCH (t:Entity {name: $target, tenant_id: $tenant_id, user_id: $user_id})
                MERGE (s)-[r:RELATES_TO {type: $rel_type}]->(t)
                SET r.doc_id = $doc_id
                """,
                source=rel["source"],
                target=rel["target"],
                rel_type=rel.get("type", "RELATES_TO"),
                tenant_id=tenant_id,
                user_id=user_id,
                doc_id=rel.get("doc_id"),
            )

    driver.close()

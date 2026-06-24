"""
Task: build_graph
Extracts entities and relationships from chunks using LLM (OpenRouter).
Uploads graph JSON to GCS: { "entities": [...], "relationships": [...] }
"""
import json

from google.cloud import storage
from openai import OpenAI

from tasks.db_status import update_current_task

GRAPH_EXTRACTION_PROMPT = """Extract named entities and relationships from the following text.
Return a JSON object with:
- "entities": list of {{"id": "unique-id", "name": "entity name", "type": "entity type"}}
- "relationships": list of {{"source": "entity name", "target": "entity name", "type": "relationship type"}}

Entity types: Regulation, Organization, DataType, Process, Right, Obligation, Role
Relationship types: REFERENCES, REQUIRES, PROTECTS, GOVERNS, APPLIES_TO, GRANTS

Text:
{text}

Return ONLY valid JSON, no markdown fences."""


def _get_openrouter_client() -> OpenAI:
    try:
        from airflow.models import Variable
        api_key = Variable.get("openrouter_api_key")
    except Exception:
        import os
        api_key = os.environ.get("OPENROUTER_API_KEY", "")

    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://github.com/privacy-policy-compliance-assistant",
            "X-Title": "Privacy Policy Compliance Assistant",
        },
    )


def _extract_graph_from_text(client: OpenAI, text: str) -> dict:
    """Extract entities and relationships from text via LLM."""
    resp = client.chat.completions.create(
        model="openai/gpt-oss-120b:free",
        messages=[{"role": "user", "content": GRAPH_EXTRACTION_PROMPT.format(text=text)}],
        temperature=0.0,
    )
    content = resp.choices[0].message.content.strip()

    # Strip markdown fences if present
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        content = content.rsplit("```", 1)[0]

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"entities": [], "relationships": []}


def build_graph(**context) -> str:
    """
    Airflow PythonOperator callable.
    Downloads chunks from GCS, extracts entities+relationships via LLM,
    uploads graph JSON to GCS.
    """
    conf = context["dag_run"].conf
    job_id = conf["job_id"]
    doc_id = conf["doc_id"]
    tenant_id = conf["tenant_id"]
    user_id = conf["user_id"]

    update_current_task(job_id, "build_graph")

    ti = context["ti"]
    gcs_chunks_path = ti.xcom_pull(task_ids="chunk_text")

    # Download chunks
    path = gcs_chunks_path.replace("gs://", "")
    bucket_name, _, blob_name = path.partition("/")
    gcs_client = storage.Client()
    chunks = json.loads(gcs_client.bucket(bucket_name).blob(blob_name).download_as_text())

    openrouter = _get_openrouter_client()

    all_entities = []
    all_relationships = []

    for chunk in chunks:
        graph = _extract_graph_from_text(openrouter, chunk["text"])

        for entity in graph.get("entities", []):
            entity["doc_id"] = doc_id
            entity["user_id"] = user_id
            entity["tenant_id"] = tenant_id
            entity["chunk_id"] = chunk["id"]
            all_entities.append(entity)

        for rel in graph.get("relationships", []):
            rel["doc_id"] = doc_id
            rel["user_id"] = user_id
            rel["tenant_id"] = tenant_id
            all_relationships.append(rel)

    graph_data = {
        "doc_id": doc_id,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "entities": all_entities,
        "relationships": all_relationships,
    }

    # Upload graph JSON to GCS
    gcs_key = f"processing/{tenant_id}/{doc_id}/graph/{doc_id}.json"
    blob = gcs_client.bucket(bucket_name).blob(gcs_key)
    blob.upload_from_string(json.dumps(graph_data), content_type="application/json")

    return f"gs://{bucket_name}/{gcs_key}"

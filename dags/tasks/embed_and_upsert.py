"""
Task: generate_embeddings + upsert_qdrant (combined — no GCS intermediate)
Embeds chunks via OpenRouter and upserts directly to Qdrant Cloud.
Vectors are NEVER written to GCS.
"""
import json
import time

from google.cloud import storage
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from dags.tasks.db_status import update_current_task

BATCH_SIZE = 50
BATCH_SLEEP_SECONDS = 3  # Respect free-tier rate limits


def _get_openrouter_client() -> OpenAI:
    """Get OpenAI client configured for OpenRouter."""
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


def _get_qdrant_client() -> QdrantClient:
    """Get Qdrant client from Airflow Variables."""
    try:
        from airflow.models import Variable
        url = Variable.get("qdrant_url")
        api_key = Variable.get("qdrant_api_key")
    except Exception:
        import os
        url = os.environ.get("QDRANT_URL", "http://localhost:6333")
        api_key = os.environ.get("QDRANT_API_KEY", "")

    return QdrantClient(url=url, api_key=api_key if api_key else None)


def _ensure_collection(qdrant: QdrantClient, collection: str, dim: int) -> None:
    """Create Qdrant collection if it doesn't exist."""
    collections = [c.name for c in qdrant.get_collections().collections]
    if collection not in collections:
        qdrant.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


def embed_and_upsert_qdrant(**context) -> dict:
    """
    Airflow PythonOperator callable.
    Downloads chunks from GCS, embeds via OpenRouter, upserts to Qdrant.
    Returns {"chunk_count": N, "collection": "..."}.
    """
    conf = context["dag_run"].conf
    job_id = conf["job_id"]
    doc_id = conf["doc_id"]
    user_id = conf["user_id"]
    tenant_id = conf["tenant_id"]
    collection = conf.get("collection", "policies")
    embedding_model = conf.get("embedding_model", "nvidia/llama-nemotron-embed-vl-1b-v2:free")

    update_current_task(job_id, "generate_embeddings")

    ti = context["ti"]
    gcs_chunks_path = ti.xcom_pull(task_ids="chunk_text")

    # Download chunks
    path = gcs_chunks_path.replace("gs://", "")
    bucket_name, _, blob_name = path.partition("/")
    client = storage.Client()
    chunks_json = client.bucket(bucket_name).blob(blob_name).download_as_text()
    chunks = json.loads(chunks_json)

    openrouter = _get_openrouter_client()
    qdrant = _get_qdrant_client()

    # Probe embedding dimension
    probe_resp = openrouter.embeddings.create(
        model=embedding_model, input="probe", encoding_format="float"
    )
    dim = len(probe_resp.data[0].embedding)
    _ensure_collection(qdrant, collection, dim)

    # Embed and upsert in batches
    update_current_task(job_id, "upsert_qdrant")

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        texts = [c["text"] for c in batch]

        resp = openrouter.embeddings.create(
            model=embedding_model, input=texts, encoding_format="float"
        )

        points = []
        for chunk, emb_data in zip(batch, resp.data):
            points.append(PointStruct(
                id=chunk["id"],
                vector=emb_data.embedding,
                payload={
                    "text": chunk["text"],
                    "title": chunk["title"],
                    "doc_id": doc_id,
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "chunk_index": chunk["chunk_index"],
                    "source": "upload",
                },
            ))

        qdrant.upsert(collection_name=collection, points=points)

        if i + BATCH_SIZE < len(chunks):
            time.sleep(BATCH_SLEEP_SECONDS)

    return {"chunk_count": len(chunks), "collection": collection}

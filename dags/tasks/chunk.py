"""
Task: chunk_text
Splits extracted text into overlapping chunks and uploads as JSON to GCS.
Ports logic from backend/ingestion/chunker.py for Airflow independence.
"""
import json
import uuid

import tiktoken
from google.cloud import storage

from dags.tasks.db_status import update_current_task

MAX_TOKENS = 400
OVERLAP_TOKENS = 50
ENCODING = tiktoken.get_encoding("cl100k_base")
SEPARATORS = ["\n\n", "\n", ". ", " "]


def _count_tokens(text: str) -> int:
    return len(ENCODING.encode(text))


def chunk_text_content(
    text: str,
    doc_id: str,
    title: str,
    tenant_id: str,
    user_id: str,
) -> list[dict]:
    """
    Split text into overlapping chunks.
    Returns a list of chunk dicts ready for JSON serialization.
    """
    if _count_tokens(text) <= MAX_TOKENS:
        return [
            {
                "id": str(uuid.uuid4()),
                "text": text,
                "title": title,
                "doc_id": doc_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "chunk_index": 0,
                "token_count": _count_tokens(text),
            }
        ]

    chunks = []
    start = 0
    chunk_index = 0

    while start < len(text):
        # Find the end position for this chunk
        end = start
        for sep in SEPARATORS:
            # Try to find a natural break point within MAX_TOKENS
            candidate = text[start:]
            tokens = 0
            last_sep = 0
            for i, char in enumerate(candidate):
                if candidate[i:i+len(sep)] == sep:
                    last_sep = i + len(sep)
                # Approximate: check token count periodically
                if i % 100 == 0 and _count_tokens(candidate[:i]) >= MAX_TOKENS:
                    break
            end = start + (last_sep if last_sep > 0 else min(len(candidate), MAX_TOKENS * 4))
            if _count_tokens(text[start:end]) <= MAX_TOKENS:
                break

        # Fallback: hard cut at MAX_TOKENS worth of text
        chunk_text = text[start:end].strip()
        while _count_tokens(chunk_text) > MAX_TOKENS and len(chunk_text) > 100:
            chunk_text = chunk_text[:int(len(chunk_text) * 0.9)]
            # Find last sentence boundary
            for sep in [". ", "\n", " "]:
                idx = chunk_text.rfind(sep)
                if idx > len(chunk_text) // 2:
                    chunk_text = chunk_text[:idx + len(sep)]
                    break

        if chunk_text:
            chunks.append({
                "id": str(uuid.uuid4()),
                "text": chunk_text.strip(),
                "title": title,
                "doc_id": doc_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "chunk_index": chunk_index,
                "token_count": _count_tokens(chunk_text),
            })
            chunk_index += 1

        # Advance with overlap
        overlap_chars = max(len(chunk_text) - int(len(chunk_text) * OVERLAP_TOKENS / MAX_TOKENS), 1)
        start += overlap_chars
        if start >= len(text):
            break

    return chunks


def chunk_text(**context) -> str:
    """
    Airflow PythonOperator callable.
    Downloads text from GCS, chunks it, uploads chunks JSON to GCS.
    """
    conf = context["dag_run"].conf
    job_id = conf["job_id"]
    doc_id = conf["doc_id"]
    tenant_id = conf["tenant_id"]
    user_id = conf["user_id"]
    title = conf["title"]

    update_current_task(job_id, "chunk_text")

    ti = context["ti"]
    gcs_text_path = ti.xcom_pull(task_ids="extract_text")

    # Download text
    path = gcs_text_path.replace("gs://", "")
    bucket_name, _, blob_name = path.partition("/")
    client = storage.Client()
    text = client.bucket(bucket_name).blob(blob_name).download_as_text()

    # Chunk
    chunks = chunk_text_content(text, doc_id, title, tenant_id, user_id)

    # Upload chunks JSON to GCS
    gcs_key = f"processing/{tenant_id}/{doc_id}/chunks/{doc_id}.json"
    blob = client.bucket(bucket_name).blob(gcs_key)
    blob.upload_from_string(json.dumps(chunks), content_type="application/json")

    return f"gs://{bucket_name}/{gcs_key}"

"""
Task: chunk_text
Splits extracted text into overlapping chunks and uploads as JSON to GCS.
Ports logic from backend/ingestion/chunker.py for Airflow independence.
"""
import json
import re
import uuid

import tiktoken
from google.cloud import storage

from tasks.db_status import update_current_task

MAX_TOKENS = 350
OVERLAP_TOKENS = 50
ENCODING = tiktoken.get_encoding("cl100k_base")
SEPARATORS = ["\n\n", "\n", ". ", " "]

_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_LIST_ITEM_RE = re.compile(
    r"^\s*(\d+\.|[a-z]\)|[a-z]\.|[(][a-z][)]|\*|-)\s", re.IGNORECASE
)


def _count_tokens(text: str) -> int:
    return len(ENCODING.encode(text))


def _build_header_breadcrumb(header_stack: dict, title: str) -> str:
    if not header_stack:
        return ""
    parts = [header_stack[level] for level in sorted(header_stack.keys())]
    context_path = " > ".join(parts)
    return f"[Source: {title} | Context: {context_path}]"


def _extract_headers(text: str) -> list:
    results = []
    for match in _HEADER_RE.finditer(text):
        level = len(match.group(1))
        header_text = match.group(2).strip()
        results.append((level, header_text, match.start()))
    return results


def _is_list_item_start(text: str) -> bool:
    return bool(_LIST_ITEM_RE.match(text))


def _split_preserving_lists(text: str, separator: str) -> list:
    if separator == " ":
        return text.split()

    raw_parts = text.split(separator)
    if len(raw_parts) <= 1:
        return [text]

    parts = [p + separator for p in raw_parts[:-1]] + [raw_parts[-1]]

    merged = []
    for part in parts:
        stripped = part.strip()
        if _is_list_item_start(stripped) and merged:
            merged[-1] += part
        else:
            merged.append(part)

    return merged


def chunk_text_content(
    text: str,
    doc_id: str,
    title: str,
    tenant_id: str,
    user_id: str,
) -> list:
    """
    Split text into overlapping chunks.
    Returns a list of chunk dicts ready for JSON serialization.
    """
    text = text.strip()
    if not text:
        return []

    headers = _extract_headers(text)
    token_count = _count_tokens(text)

    if token_count <= MAX_TOKENS:
        header_stack = {}
        for level, header_text, _ in headers:
            keys_to_remove = [k for k in header_stack if k >= level]
            for k in keys_to_remove:
                del header_stack[k]
            header_stack[level] = header_text

        breadcrumb = _build_header_breadcrumb(header_stack, title)
        enriched = f"{breadcrumb}\n\n{text}" if breadcrumb else text
        return [
            {
                "id": str(uuid.uuid4()),
                "text": enriched,
                "title": title,
                "doc_id": doc_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "chunk_index": 0,
                "token_count": _count_tokens(enriched),
            }
        ]

    chunks = []
    chunk_index = 0
    remaining = text
    header_stack = {}
    header_idx = 0

    while remaining:
        split_done = False
        for sep in SEPARATORS:
            if sep not in remaining:
                continue

            parts = _split_preserving_lists(remaining, sep)
            current = []
            current_tokens = 0

            for part in parts:
                for h_level, h_text, h_pos in headers[header_idx:]:
                    if h_text in part:
                        keys_to_remove = [k for k in header_stack if k >= h_level]
                        for k in keys_to_remove:
                            del header_stack[k]
                        header_stack[h_level] = h_text
                        header_idx += 1
                    else:
                        break

                part_tokens = _count_tokens(part)
                if current_tokens + part_tokens <= MAX_TOKENS:
                    current.append(part)
                    current_tokens += part_tokens
                else:
                    if current:
                        chunk_text = "".join(current).strip()
                        if chunk_text:
                            breadcrumb = _build_header_breadcrumb(header_stack, title)
                            enriched = f"{breadcrumb}\n\n{chunk_text}" if breadcrumb else chunk_text
                            chunks.append({
                                "id": str(uuid.uuid4()),
                                "text": enriched,
                                "title": title,
                                "doc_id": doc_id,
                                "tenant_id": tenant_id,
                                "user_id": user_id,
                                "chunk_index": chunk_index,
                                "token_count": _count_tokens(enriched),
                            })
                            chunk_index += 1

                            overlap_parts = []
                            overlap_tok = 0
                            for prev_part in reversed(current):
                                pt = _count_tokens(prev_part)
                                if overlap_tok + pt <= OVERLAP_TOKENS:
                                    overlap_parts.insert(0, prev_part)
                                    overlap_tok += pt
                                else:
                                    break
                            current = overlap_parts + [part]
                            current_tokens = overlap_tok + part_tokens
                    else:
                        chunk_text = part.strip()
                        if chunk_text:
                            breadcrumb = _build_header_breadcrumb(header_stack, title)
                            enriched = f"{breadcrumb}\n\n{chunk_text}" if breadcrumb else chunk_text
                            chunks.append({
                                "id": str(uuid.uuid4()),
                                "text": enriched,
                                "title": title,
                                "doc_id": doc_id,
                                "tenant_id": tenant_id,
                                "user_id": user_id,
                                "chunk_index": chunk_index,
                                "token_count": _count_tokens(enriched),
                            })
                            chunk_index += 1
                        current = []
                        current_tokens = 0

            if current:
                chunk_text = "".join(current).strip()
                if chunk_text:
                    breadcrumb = _build_header_breadcrumb(header_stack, title)
                    enriched = f"{breadcrumb}\n\n{chunk_text}" if breadcrumb else chunk_text
                    chunks.append({
                        "id": str(uuid.uuid4()),
                        "text": enriched,
                        "title": title,
                        "doc_id": doc_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "chunk_index": chunk_index,
                        "token_count": _count_tokens(enriched),
                    })
                    chunk_index += 1
            remaining = ""
            split_done = True
            break

        if not split_done:
            chunk_text = remaining.strip()
            if chunk_text:
                breadcrumb = _build_header_breadcrumb(header_stack, title)
                enriched = f"{breadcrumb}\n\n{chunk_text}" if breadcrumb else chunk_text
                chunks.append({
                    "id": str(uuid.uuid4()),
                    "text": enriched,
                    "title": title,
                    "doc_id": doc_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "chunk_index": chunk_index,
                    "token_count": _count_tokens(enriched),
                })
            remaining = ""

    if not chunks:
        breadcrumb = _build_header_breadcrumb(header_stack, title)
        enriched = f"{breadcrumb}\n\n{text}" if breadcrumb else text
        chunks = [{
            "id": str(uuid.uuid4()),
            "text": enriched,
            "title": title,
            "doc_id": doc_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "chunk_index": 0,
            "token_count": _count_tokens(enriched),
        }]

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

    path = gcs_text_path.replace("gs://", "")
    bucket_name, _, blob_name = path.partition("/")
    client = storage.Client()
    text = client.bucket(bucket_name).blob(blob_name).download_as_text()

    chunks = chunk_text_content(text, doc_id, title, tenant_id, user_id)

    gcs_key = f"processing/{tenant_id}/{doc_id}/chunks/{doc_id}.json"
    blob = client.bucket(bucket_name).blob(gcs_key)
    blob.upload_from_string(json.dumps(chunks), content_type="application/json")

    return f"gs://{bucket_name}/{gcs_key}"

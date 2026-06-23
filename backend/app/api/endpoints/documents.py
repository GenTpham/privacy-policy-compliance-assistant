import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.core.config import Settings, get_settings
from backend.app.db.models import Document, IngestionJob, User
from backend.app.db.session import get_db
from backend.app.services.auth import get_current_user
from backend.app.services.gcs import upload_file_to_gcs
from backend.app.services.airflow import trigger_dag

router = APIRouter()

@router.post("/")
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    tenant_id: str = Form(...),
    collection: str = Form("policies"),
    embedding_model: str = Form("nvidia/llama-nemotron-embed-vl-1b-v2:free"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    dag_run_id = f"ingest_{job_id}"
    
    # 1. Upload to GCS
    gcs_path = await upload_file_to_gcs(
        file.file, 
        f"uploads/{tenant_id}/{doc_id}_{file.filename}",
        file.content_type
    )
    
    # 2. Insert Document
    doc = Document(
        id=doc_id,
        user_id=current_user.id,
        tenant_id=tenant_id,
        title=title or file.filename,
        filename=file.filename,
        gcs_path=gcs_path,
        collection=collection,
        embedding_model=embedding_model,
        status="processing",
        source="upload"
    )
    db.add(doc)
    
    # 3. Insert IngestionJob (status=queued) BEFORE triggering Airflow
    job = IngestionJob(
        id=job_id,
        doc_id=doc_id,
        dag_run_id=dag_run_id,
        status="queued"
    )
    db.add(job)
    await db.commit()
    
    # 4. Trigger DAG (Idempotent)
    try:
        await trigger_dag(dag_run_id=dag_run_id, conf={
            "job_id": job_id,
            "doc_id": doc_id,
            "tenant_id": tenant_id,
            "gcs_path": gcs_path,
            "collection": collection,
            "embedding_model": embedding_model
        })
    except Exception as e:
        # If API fails, the DB record still exists, so we know it's stuck
        job.status = "failed"
        job.error_msg = f"Failed to trigger Airflow: {str(e)}"
        await db.commit()
        raise HTTPException(status_code=500, detail="Failed to start ingestion pipeline")
        
    return {"document_id": doc.id, "job_id": job.id, "status": "processing"}

@router.get("/")
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Document).where(Document.user_id == current_user.id))
    docs = result.scalars().all()
    return docs

@router.get("/{document_id}")
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == current_user.id)
    )
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
            
    return doc

@router.get("/{document_id}/status")
async def get_document_status(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Document.status).where(Document.id == document_id, Document.user_id == current_user.id)
    )
    status = result.scalar_one_or_none()
    
    if not status:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return {"id": document_id, "status": status}

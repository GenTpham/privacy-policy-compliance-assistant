from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.core.config import Settings, get_settings
from backend.app.db.models import Document, User
from backend.app.db.session import get_db
from backend.app.services.auth import get_current_user
from backend.app.services.document_processor import process_document_inline

router = APIRouter()

@router.post("/")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    doc = Document(
        user_id=current_user.id,
        title=title or file.filename,
        status="processing"
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    
    file_bytes = await file.read()
    
    background_tasks.add_task(
        process_document_inline,
        document_id=doc.id,
        file_bytes=file_bytes,
        filename=file.filename
    )
    
    return {
        "id": doc.id,
        "title": doc.title,
        "status": doc.status,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at
    }

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
    document_id: int,
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
    document_id: int,
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

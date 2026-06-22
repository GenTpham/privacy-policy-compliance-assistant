from fastapi import APIRouter, Depends
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import QueryLog, Document, User
from backend.app.db.session import get_db
from backend.app.services.auth import get_current_user

router = APIRouter()

@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    total_queries = await db.scalar(select(func.count()).select_from(QueryLog))
    total_documents = await db.scalar(select(func.count()).select_from(Document))
    active_users = await db.scalar(select(func.count(QueryLog.user_id.distinct())))
    success_queries = await db.scalar(select(func.count()).select_from(QueryLog).where(QueryLog.status == "success"))
    
    success_rate = 100
    if total_queries and total_queries > 0:
        success_rate = round((success_queries / total_queries) * 100, 1)

    return {
        "total_queries": total_queries or 0,
        "total_documents": total_documents or 0,
        "active_users": active_users or 0,
        "success_rate": success_rate
    }

@router.get("/topics")
async def get_dashboard_topics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(QueryLog.topic, func.count(QueryLog.id).label("count"))
        .group_by(QueryLog.topic)
        .order_by(desc("count"))
    )
    topics = result.all()
    
    return [
        {"name": topic.topic, "value": topic.count}
        for topic in topics
    ]

@router.get("/recent-queries")
async def get_recent_queries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(QueryLog.id, QueryLog.query_text, QueryLog.topic, QueryLog.status, QueryLog.created_at)
        .order_by(desc(QueryLog.created_at))
        .limit(10)
    )
    queries = result.all()
    
    return [
        {
            "id": str(q.id),
            "query": q.query_text,
            "topic": q.topic,
            "status": q.status,
            "timestamp": q.created_at.isoformat() if q.created_at else None
        }
        for q in queries
    ]

@router.get("/documents")
async def get_dashboard_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Document.id, Document.title, Document.status, Document.chunk_count, Document.updated_at)
        .order_by(desc(Document.updated_at))
    )
    docs = result.all()
    
    return [
        {
            "id": str(d.id),
            "title": d.title,
            "status": d.status,
            "chunks": d.chunk_count,
            "last_updated": d.updated_at.isoformat() if d.updated_at else None
        }
        for d in docs
    ]

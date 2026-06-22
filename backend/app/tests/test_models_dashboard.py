import pytest
from sqlalchemy import select
from backend.app.db.models import QueryLog, Document
from datetime import datetime, timezone

@pytest.mark.asyncio
async def test_create_query_log_and_document(db_session):
    # Test QueryLog
    log = QueryLog(user_id=1, query_text="What is the retention policy?", topic="Data Retention", status="processing")
    db_session.add(log)
    
    # Test Document
    doc = Document(title="Privacy Policy 2026", chunk_count=15, status="Completed")
    db_session.add(doc)
    
    await db_session.commit()
    
    saved_log = (await db_session.execute(select(QueryLog))).scalar_one()
    assert saved_log.query_text == "What is the retention policy?"
    assert saved_log.created_at is not None
    
    saved_doc = (await db_session.execute(select(Document))).scalar_one()
    assert saved_doc.title == "Privacy Policy 2026"
    assert saved_doc.updated_at is not None

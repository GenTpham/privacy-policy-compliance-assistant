import pytest
from unittest.mock import patch

from backend.app.db.models import Document
from backend.app.tests.test_auth import _seed_user


@pytest.fixture
async def authed_client(auth_client, db_session):
    user = await _seed_user(db_session)
    resp = await auth_client.post(
        "/auth/login", json={"username": user.username, "password": "password123"}
    )
    token = resp.json()["access_token"]
    auth_client.headers.update({"Authorization": f"Bearer {token}"})
    return auth_client, user


import uuid

async def test_list_documents(authed_client, db_session):
    client, user = authed_client
    
    doc = Document(
        id=str(uuid.uuid4()),
        user_id=user.id,
        tenant_id=str(user.id),
        title="Doc 1",
        filename="test.pdf",
        gcs_path="gs://bucket/test.pdf",
        collection="policies",
        embedding_model="test-model",
        status="success",
        source="upload"
    )
    db_session.add(doc)
    await db_session.commit()
    
    resp = await client.get("/api/documents/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Doc 1"

async def test_get_document_status(authed_client, db_session):
    client, user = authed_client
    
    doc = Document(
        id=str(uuid.uuid4()),
        user_id=user.id,
        tenant_id=str(user.id),
        title="Doc 1",
        filename="test.pdf",
        gcs_path="gs://bucket/test.pdf",
        collection="policies",
        embedding_model="test-model",
        status="processing",
        source="upload"
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    
    resp = await client.get(f"/api/documents/{doc.id}/status")
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "processing"

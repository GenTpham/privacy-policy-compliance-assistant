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


async def test_upload_document_unauthorized(auth_client):
    resp = await auth_client.post("/documents/")
    assert resp.status_code == 401


async def test_upload_document(authed_client, db_session):
    client, user = authed_client
    
    with patch("fastapi.BackgroundTasks.add_task") as mock_add_task:
        
        resp = await client.post(
            "/documents/",
            data={"title": "My Doc"},
            files={"file": ("test.pdf", b"pdf content", "application/pdf")},
        )
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "My Doc"
        assert data["status"] == "processing"
        
        mock_add_task.assert_called_once()
        

async def test_list_documents(authed_client, db_session):
    client, user = authed_client
    
    doc = Document(user_id=user.id, title="Doc 1", status="success")
    db_session.add(doc)
    await db_session.commit()
    
    resp = await client.get("/documents/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Doc 1"

async def test_get_document_status(authed_client, db_session):
    client, user = authed_client
    
    doc = Document(user_id=user.id, title="Doc 1", status="processing")
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    
    resp = await client.get(f"/documents/{doc.id}")
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "processing"

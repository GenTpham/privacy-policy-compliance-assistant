"""
backend/app/tests/test_admin.py
Phase 10 admin user management tests.

Test → Requirement mapping:
  test_create_user              → AUTH-05
  test_create_user_conflict     → AUTH-05
  test_list_users               → AUTH-05
  test_delete_user              → AUTH-05
  test_delete_user_not_found    → AUTH-05
  test_no_self_registration     → AUTH-05
  test_non_admin_forbidden      → AUTH-07
  test_unauthenticated_forbidden → AUTH-07
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import User
from backend.app.services.auth import create_access_token, hash_password


# ── Helpers ─────────────────────────────────────────────────────────────────────

async def _seed_user(
    db_session: AsyncSession,
    username: str = "testuser",
    password: str = "password123",
    is_admin: bool = False,
) -> User:
    """Insert a User into the test DB and return it."""
    user = User(
        username=username,
        hashed_password=hash_password(password),
        is_admin=is_admin,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _get_admin_token(admin_client, db_session) -> str:
    """Seed an admin user and return a valid Bearer token for them."""
    await _seed_user(db_session, username="adminuser", password="adminpass", is_admin=True)
    resp = await admin_client.post(
        "/auth/login",
        json={"username": "adminuser", "password": "adminpass"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


# ── Tests ────────────────────────────────────────────────────────────────────────

async def test_create_user(admin_client, db_session):
    """POST /admin/users by admin → 201 with UserResponse (AUTH-05)."""
    token = await _get_admin_token(admin_client, db_session)
    resp = await admin_client.post(
        "/admin/users",
        json={"username": "newuser", "password": "secret123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser"
    assert data["is_admin"] is False
    assert "hashed_password" not in data
    assert "id" in data
    assert "created_at" in data


async def test_create_user_conflict(admin_client, db_session):
    """POST /admin/users with duplicate username → 409 (AUTH-05)."""
    token = await _get_admin_token(admin_client, db_session)
    # Seed a user with the same username
    await _seed_user(db_session, username="duplicate")
    resp = await admin_client.post(
        "/admin/users",
        json={"username": "duplicate", "password": "secret123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Username already exists"


async def test_list_users(admin_client, db_session):
    """GET /admin/users by admin → 200 with list of users (AUTH-05)."""
    token = await _get_admin_token(admin_client, db_session)
    await _seed_user(db_session, username="user1")
    await _seed_user(db_session, username="user2")
    resp = await admin_client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    usernames = [u["username"] for u in users]
    assert "user1" in usernames
    assert "user2" in usernames
    # Verify no hashed_password in any response item
    for u in users:
        assert "hashed_password" not in u


async def test_delete_user(admin_client, db_session):
    """DELETE /admin/users/{username} by admin → 204 (AUTH-05)."""
    token = await _get_admin_token(admin_client, db_session)
    await _seed_user(db_session, username="todelete")
    resp = await admin_client.delete(
        "/admin/users/todelete",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204
    # Verify user is gone
    list_resp = await admin_client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    usernames = [u["username"] for u in list_resp.json()]
    assert "todelete" not in usernames


async def test_delete_user_not_found(admin_client, db_session):
    """DELETE /admin/users/{username} for nonexistent user → 404 (AUTH-05)."""
    token = await _get_admin_token(admin_client, db_session)
    resp = await admin_client.delete(
        "/admin/users/doesnotexist",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "User not found"


async def test_no_self_registration(admin_client):
    """No self-registration endpoint exists — POST /users and POST /register return 404 (AUTH-05)."""
    # These routes must not exist; 404 from FastAPI means the path is not registered
    resp_users = await admin_client.post(
        "/users", json={"username": "x", "password": "y"}
    )
    assert resp_users.status_code == 404

    resp_register = await admin_client.post(
        "/register", json={"username": "x", "password": "y"}
    )
    assert resp_register.status_code == 404


async def test_non_admin_forbidden(admin_client, db_session):
    """GET /admin/users by non-admin user → 403 (AUTH-07)."""
    await _seed_user(db_session, username="normaluser", is_admin=False)
    resp = await admin_client.post(
        "/auth/login",
        json={"username": "normaluser", "password": "password123"},
    )
    token = resp.json()["access_token"]
    r = await admin_client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "Admin access required"


async def test_unauthenticated_forbidden(admin_client):
    """GET /admin/users with no token → 401 (AUTH-07)."""
    r = await admin_client.get("/admin/users")
    assert r.status_code == 401

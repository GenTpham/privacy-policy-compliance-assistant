"""
backend/app/api/admin.py
Admin user management router: POST /admin/users, GET /admin/users,
DELETE /admin/users/{username}.

Decisions:
  D-04: require_admin dependency reads is_admin from JWT payload — no DB re-query.
  AUTH-05: no self-registration endpoint — all user creation is admin-gated.
  AUTH-07: require_admin enforces HTTP 403 for non-admin tokens.

Anti-patterns avoided:
  - Never return hashed_password in any response model.
  - Never allow unauthenticated or non-admin access — require_admin on every endpoint.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.services.auth import hash_password, require_admin

router = APIRouter()


# ── Pydantic models ─────────────────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    username: str
    password: str
    is_admin: bool = False


class UserResponse(BaseModel):
    """Safe response model — never includes hashed_password (AUTH-05 security requirement)."""
    id: int
    username: str
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> UserResponse:
    """POST /admin/users — create a new user account (admin only, AUTH-05)."""
    result = await db.execute(select(User).where(User.username == body.username))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )
    user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        is_admin=body.is_admin,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> list[UserResponse]:
    """GET /admin/users — list all user accounts (admin only, AUTH-05)."""
    result = await db.execute(select(User).order_by(User.id))
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.delete("/users/{username}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    username: str,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> None:
    """DELETE /admin/users/{username} — remove a user account (admin only, AUTH-05)."""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    await db.delete(user)
    await db.commit()

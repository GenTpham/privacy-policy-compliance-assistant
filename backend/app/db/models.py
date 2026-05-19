"""
backend/app/db/models.py
SQLAlchemy 2.0 declarative User model.
Single table: users (id, username, hashed_password, created_at, is_admin).
D-01: is_admin bool column — existing rows default to False via ALTER TABLE migration in main.py.
Decision D-11: SQLite file at backend/data/users.db, no Alembic for v1.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

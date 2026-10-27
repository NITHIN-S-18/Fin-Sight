"""Authentication identity model for FinSight.

Represents the user's security/login account in the `auth_users` table,
storing credentials (email, password hash), session versioning, and avatar.

Relationship with User (Financial Tenant):
    AuthUser has a 1-to-1 relationship with the `User` model via `financial_user`.
    While `AuthUser` manages authentication and JWT session validation, financial
    ledger records (transactions, commitments, goals) are bound to the `User`
    entity via its string identifier (`user_id`).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.password_reset_otp import PasswordResetOTP
    from app.database.models.password_reset_token import PasswordResetToken
    from app.database.models.user import User


class AuthUser(Base):
    __tablename__ = "auth_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    session_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    financial_user: Mapped["User | None"] = relationship(
        "User", back_populates="auth_user", uselist=False, cascade="all, delete-orphan"
    )
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        "PasswordResetToken", back_populates="auth_user", cascade="all, delete-orphan"
    )
    password_reset_otps: Mapped[list["PasswordResetOTP"]] = relationship(
        "PasswordResetOTP", back_populates="auth_user", cascade="all, delete-orphan"
    )

    @property
    def financial_user_id(self) -> str | None:
        return self.financial_user.user_id if self.financial_user is not None else None

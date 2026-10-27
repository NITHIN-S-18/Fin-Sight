"""Financial tenant identity model for FinSight.

Represents the core financial profile and tenant isolation boundary in the `users` table.
Financial ledger data—including transactions, recurring payments, financial goals,
and AI conversations—are partitioned under this entity's unique string `user_id` (e.g. "USR-...").

Relationship with AuthUser (Authentication Identity):
    Each `User` is linked 1-to-1 to an `AuthUser` via `auth_user_id` (foreign key to `auth_users.id`).
    Separating `AuthUser` (credentials, sessions) from `User` (financial capacity, demographic
    persona, ledger records) cleanly isolates authentication concerns from financial intelligence.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    auth_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="CASCADE"), unique=True, nullable=True, index=True
    )
    persona: Mapped[str | None] = mapped_column(String(150), nullable=True)
    age_group: Mapped[str | None] = mapped_column(String(50), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    income_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    monthly_financial_capacity: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=True,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )

    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="user", cascade="all, delete-orphan"
    )
    recurring_payments: Mapped[list["RecurringPayment"]] = relationship(
        "RecurringPayment", back_populates="user", cascade="all, delete-orphan"
    )
    financial_goals: Mapped[list["FinancialGoal"]] = relationship(
        "FinancialGoal", back_populates="user", cascade="all, delete-orphan"
    )
    financial_profile: Mapped["FinancialProfile"] = relationship(
        "FinancialProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    auth_user: Mapped["AuthUser | None"] = relationship(
        "AuthUser", back_populates="financial_user"
    )
    income_configuration: Mapped["UserIncomeConfiguration | None"] = relationship(
        "UserIncomeConfiguration",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

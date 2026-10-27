from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.user import User


class FinancialProfile(Base):
    __tablename__ = "financial_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id"),
        unique=True,
        nullable=False,
        index=True,
    )

    monthly_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    financial_capacity: Mapped[float | None] = mapped_column(Float, nullable=True)
    monthly_commitments: Mapped[float | None] = mapped_column(Float, nullable=True)
    subscription_burden: Mapped[float | None] = mapped_column(Float, nullable=True)
    emi_burden: Mapped[float | None] = mapped_column(Float, nullable=True)
    bnpl_burden: Mapped[float | None] = mapped_column(Float, nullable=True)
    exposure_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    health_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(50), nullable=True)

    persona: Mapped[str | None] = mapped_column(String(150), nullable=True)
    active_subscriptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_emis: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_bnpl: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_active_commitments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_transactions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transaction_success_rate: Mapped[str | None] = mapped_column(String(50), nullable=True)
    financial_health: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_leakage_user: Mapped[str | None] = mapped_column(String(20), nullable=True)
    leakage_subscription_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_heavy_bnpl_user: Mapped[str | None] = mapped_column(String(20), nullable=True)
    heavy_bnpl_providers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_heavy_emi_user: Mapped[str | None] = mapped_column(String(20), nullable=True)
    heavy_emi_providers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    special_scenario: Mapped[str | None] = mapped_column(String(255), nullable=True)

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

    user: Mapped[User] = relationship(
        "User",
        back_populates="financial_profile",
    )
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.user import User


class TrialIntelligence(Base):
    __tablename__ = "trial_intelligence"
    __table_args__ = (
        Index("ix_trial_intelligence_user_state", "user_id", "detected_state"),
        Index("ix_trial_intelligence_email_due", "email_alert_scheduled_for", "alert_sent_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    merchant_name: Mapped[str] = mapped_column(String(150), nullable=False)
    authorization_transaction_id: Mapped[str] = mapped_column(String(100), nullable=False)
    authorization_amount: Mapped[float] = mapped_column(Float, nullable=False)
    authorization_date: Mapped[date] = mapped_column(Date, nullable=False)
    detected_state: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    possible_conversion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    related_recurring_payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("recurring_payments.id", ondelete="SET NULL"), nullable=True
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    alert_sent_in_app: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    alert_sent_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_alert_scheduled_for: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    email_alert_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    user: Mapped[User] = relationship()

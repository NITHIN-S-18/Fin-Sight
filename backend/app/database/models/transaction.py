from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.user import User


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    import_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    transaction_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    merchant_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transaction_class: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payment_mode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    income_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    recurring_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    autopay_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    risk_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    transaction_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_new_subscription: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    merchant_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    commitment_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=True,
    )

    user: Mapped[User] = relationship(back_populates="transactions")

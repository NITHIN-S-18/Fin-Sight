from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.database.connection import SessionLocal
from app.database.models.transaction import Transaction
from app.repositories.transaction_repository import TransactionRepository


class PostgresTransactionRepository(TransactionRepository):
    """PostgreSQL-backed implementation of the transaction repository interface.

    The repository intentionally matches the CSV-backed public contract so the
    FastAPI responses remain identical across storage backends.
    """

    def __init__(self, session_factory: Any | None = None) -> None:
        self._session_factory = session_factory or SessionLocal

    @staticmethod
    def _as_int_or_float(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value

    @staticmethod
    def _map_yes_no(value: Any) -> str | None:
        if value is None:
            return None
        return "Yes" if bool(value) else "No"

    def _serialize_transaction(self, row: Transaction) -> dict[str, Any]:
        return {
            "transaction_id": row.transaction_id,
            "user_id": row.user_id,
            "transaction_date": row.transaction_date.date() if row.transaction_date else None,
            "merchant_name": row.merchant_name,
            "description": row.description,
            "amount": self._as_int_or_float(row.amount),
            "category": row.category,
            "transaction_class": row.transaction_class,
            "payment_mode": row.payment_mode,
            "frequency": row.frequency,
            "income_flag": self._map_yes_no(row.income_flag),
            "recurring_flag": self._map_yes_no(row.recurring_flag),
            "autopay_flag": self._map_yes_no(row.autopay_flag),
            "risk_label": row.risk_label,
            "transaction_status": row.transaction_status,
            "is_new_subscription": self._map_yes_no(row.is_new_subscription),
            "merchant_type": row.merchant_type,
            "commitment_type": row.commitment_type,
        }

    def get_by_id(self, identifier: Any) -> Any:
        return self.get_transaction(str(identifier))

    def get_all(self) -> list[Any]:
        return self.get_transactions()

    def get_transaction(self, transaction_id: str) -> Any:
        with self._session_factory() as session:
            row = session.execute(select(Transaction).where(Transaction.transaction_id == transaction_id)).scalar_one_or_none()
            if row is None:
                raise KeyError(f"Transaction not found: {transaction_id}")
            return self._serialize_transaction(row)

    def get_transactions(self) -> list[Any]:
        with self._session_factory() as session:
            rows = session.execute(select(Transaction)).scalars().all()
            return [self._serialize_transaction(row) for row in rows]

    def get_user_transactions(self, user_id: str) -> list[Any]:
        with self._session_factory() as session:
            rows = session.execute(select(Transaction).where(Transaction.user_id == user_id)).scalars().all()
            return [self._serialize_transaction(row) for row in rows]

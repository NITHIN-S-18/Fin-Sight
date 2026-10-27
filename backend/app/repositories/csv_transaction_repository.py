from __future__ import annotations

from typing import Any

from app.repositories.transaction_repository import TransactionRepository
from app.services.dataset_service import get_dataset_service


class CSVTransactionRepository(TransactionRepository):
    """CSV-backed implementation of the transaction repository interface.

    It delegates to the existing DatasetService so the API contracts remain
    byte-for-byte compatible with the current CSV-based application behavior.
    """

    def __init__(self, dataset_service: Any | None = None) -> None:
        self._dataset_service = dataset_service or get_dataset_service()

    def get_by_id(self, identifier: Any) -> Any:
        """Return a single transaction record by transaction_id."""
        return self.get_transaction(str(identifier))

    def get_all(self) -> list[Any]:
        """Return all transactions as records."""
        return self.get_transactions()

    def get_transaction(self, transaction_id: str) -> Any:
        """Return one transaction by transaction_id."""
        return self._dataset_service.get_transaction(transaction_id)

    def get_transactions(self) -> list[Any]:
        """Return all transactions with the exact dataset service shape."""
        return self._dataset_service.get_all_transactions()

    def get_user_transactions(self, user_id: str) -> list[Any]:
        """Return a user's transactions with the exact dataset service shape."""
        return self._dataset_service.get_user_transactions(user_id)

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from app.repositories.base import BaseRepository


class TransactionRepository(BaseRepository):
    """Interface for transaction data access operations."""

    @abstractmethod
    def get_transaction(self, transaction_id: str) -> Any:
        """Return a single transaction by its transaction_id."""

    @abstractmethod
    def get_transactions(self) -> list[Any]:
        """Return all transactions in the configured storage backend."""

    @abstractmethod
    def get_user_transactions(self, user_id: str) -> list[Any]:
        """Return all transactions for the requested user_id."""

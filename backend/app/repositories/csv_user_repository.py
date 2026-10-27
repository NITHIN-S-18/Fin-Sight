from __future__ import annotations

from typing import Any

from app.repositories.user_repository import UserRepository
from app.services.dataset_service import get_dataset_service


class CSVUserRepository(UserRepository):
    """CSV-backed implementation of the user repository interface.

    This adapter preserves the exact existing dataset service return values so the
    current FastAPI endpoints continue to behave identically.
    """

    def __init__(self, dataset_service: Any | None = None) -> None:
        self._dataset_service = dataset_service or get_dataset_service()

    def get_by_id(self, identifier: Any) -> Any:
        """Return a user record by its public identifier, e.g. U001."""
        return self.get_user(str(identifier))

    def get_all(self) -> list[Any]:
        """Return all users as records."""
        return self.get_users()

    def get_user(self, user_id: str) -> Any:
        """Return a single user record, including the nested financial profile."""
        return self._dataset_service.get_user(user_id)

    def get_users(self) -> list[Any]:
        """Return the complete user list with the exact dataset service shape."""
        return self._dataset_service.get_all_users()

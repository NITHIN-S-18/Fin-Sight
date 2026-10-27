from __future__ import annotations

from abc import abstractmethod
from typing import Any

from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    """Interface for user data access operations."""

    @abstractmethod
    def get_user(self, user_id: str) -> Any:
        """Return a single user by their public user_id, such as U001."""

    @abstractmethod
    def get_users(self) -> list[Any]:
        """Return all users in the configured storage backend."""

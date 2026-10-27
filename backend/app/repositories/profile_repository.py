from __future__ import annotations

from abc import abstractmethod
from typing import Any

from app.repositories.base import BaseRepository


class ProfileRepository(BaseRepository):
    """Interface for financial profile data access operations."""

    @abstractmethod
    def get_profile(self, user_id: str) -> Any:
        """Return a financial profile for the requested user_id."""

    @abstractmethod
    def get_profiles(self) -> list[Any]:
        """Return all stored financial profiles."""

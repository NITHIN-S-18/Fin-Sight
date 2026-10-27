from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseRepository(ABC):
    """Base storage interface for domain repositories."""

    @abstractmethod
    def get_by_id(self, identifier: Any) -> Any:
        """Return a single record by its identifier."""

    @abstractmethod
    def get_all(self) -> list[Any]:
        """Return all records from the repository."""

from __future__ import annotations

from app.core.config import get_settings
from app.repositories.csv_transaction_repository import CSVTransactionRepository
from app.repositories.csv_user_repository import CSVUserRepository
from app.repositories.postgres_transaction_repository import PostgresTransactionRepository
from app.repositories.postgres_user_repository import PostgresUserRepository


def get_user_repository():
    """Return the configured user repository implementation."""
    settings = get_settings()
    if settings.data_source == "postgres":
        return PostgresUserRepository()
    return CSVUserRepository()


def get_transaction_repository():
    """Return the configured transaction repository implementation."""
    settings = get_settings()
    if settings.data_source == "postgres":
        return PostgresTransactionRepository()
    return CSVTransactionRepository()

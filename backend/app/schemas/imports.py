from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TransactionImportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    uploaded_at: datetime
    transaction_start_date: datetime | None
    transaction_end_date: datetime | None
    transaction_count: int
    status: str
    error_message: str | None = None


class TransactionUploadResponse(BaseModel):
    import_record: TransactionImportResponse
    accepted_count: int
    duplicate_count: int
    rejected_count: int
    validation_errors: list[str] = Field(default_factory=list)
    reconciliation_status: str = "completed"  # completed, partial, failed


class FinancialSummaryResponse(BaseModel):
    total_transactions: int
    start_date: datetime | None = None
    end_date: datetime | None = None
    last_analyzed: datetime | None = None
    file_name: str | None = None


class SampleTransactionItem(BaseModel):
    transaction_date: str
    merchant_name: str | None = None
    description: str | None = None
    amount: float
    direction: str  # Income / Expense
    category: str | None = None
    transaction_class: str | None = None


class ImportPreviewResponse(BaseModel):
    file_type: str  # csv or pdf
    file_name: str
    total_candidate_rows: int
    valid_rows_count: int
    invalid_rows_count: int
    ambiguous_rows_count: int
    estimated_duplicate_count: int
    date_range_start: str | None = None
    date_range_end: str | None = None
    total_credits: float = 0.0
    total_debits: float = 0.0
    detected_mappings: dict[str, str] = Field(default_factory=dict)
    unmapped_columns: list[str] = Field(default_factory=list)
    sample_transactions: list[SampleTransactionItem] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    preview_token: str | None = None


class ImportConfirmationRequest(BaseModel):
    preview_token: str | None = None
    custom_mappings: dict[str, str] | None = None
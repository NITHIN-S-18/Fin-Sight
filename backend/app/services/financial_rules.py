"""Core financial business rules and normalization formulas for FinSight.

This module provides deterministic mathematical functions and lookup multipliers
to normalize financial transactions, recurring commitments, and payment statuses
into consistent monthly baselines across all downstream intelligence engines.

Commitment Frequency Normalization Multipliers:
    Recurring obligations recur on varied schedules (e.g., weekly grocery bills,
    annual insurance premiums, quarterly software subscriptions). To calculate an
    accurate monthly commitment total and exposure score, amounts are multiplied
    by standardized conversion factors derived from the annual cycle:

    - "daily"       : 365.0 / 12.0 (~30.417x) -> 365 days distributed across 12 calendar months.
    - "weekly"      : 52.0 / 12.0  (~4.333x)  -> 52 standard weeks distributed across 12 months.
    - "biweekly"    : 26.0 / 12.0  (~2.167x)  -> 26 bi-weekly periods per year.
    - "fortnightly" : 26.0 / 12.0  (~2.167x)  -> Equivalent to biweekly cadence.
    - "monthly"     : 1.0          (1.0x)     -> Standard baseline frequency.
    - "installment" : 1.0          (1.0x)     -> Standard monthly installment (EMI/BNPL).
    - "quarterly"   : 1.0 / 3.0    (~0.333x)  -> Paid once every 3 months; amortized monthly.
    - "semiannual"  : 1.0 / 6.0    (~0.167x)  -> Paid once every 6 months; amortized monthly.
    - "annual"      : 1.0 / 12.0   (~0.083x)  -> Paid once per year; amortized over 12 months.
    - "yearly"      : 1.0 / 12.0   (~0.083x)  -> Equivalent to annual cadence.
"""
from __future__ import annotations

import re
from enum import StrEnum


_MONTHLY_MULTIPLIERS = {
    "daily": 365.0 / 12.0,
    "weekly": 52.0 / 12.0,
    "biweekly": 26.0 / 12.0,
    "fortnightly": 26.0 / 12.0,
    "monthly": 1.0,
    "installment": 1.0,
    "instalment": 1.0,
    "quarterly": 1.0 / 3.0,
    "semiannual": 1.0 / 6.0,
    "annual": 1.0 / 12.0,
    "yearly": 1.0 / 12.0,
}


class TransactionStatus(StrEnum):
    SUCCESSFUL = "successful"
    FAILED = "failed"
    PENDING = "pending"
    UNKNOWN = "unknown"


_SUCCESSFUL_STATUSES = {"success", "succeeded", "successful", "completed", "paid", "settled"}
_FAILED_STATUSES = {"failed", "declined", "rejected"}
_PENDING_STATUSES = {"pending", "processing", "in_progress"}


def classify_transaction_status(value: object) -> TransactionStatus:
    normalized = "" if value is None else str(value).strip().lower()
    if normalized in _SUCCESSFUL_STATUSES:
        return TransactionStatus.SUCCESSFUL
    if normalized in _FAILED_STATUSES:
        return TransactionStatus.FAILED
    if normalized in _PENDING_STATUSES:
        return TransactionStatus.PENDING
    return TransactionStatus.UNKNOWN


def commitment_amount(value: object) -> float:
    try:
        return max(float(value or 0.0), 0.0)
    except (TypeError, ValueError):
        return 0.0


def monthly_multiplier(frequency: object) -> float:
    normalized = "" if frequency is None else str(frequency).strip().lower()
    normalized = re.sub(r"[\s_-]+", "", normalized)
    if not normalized:
        return 1.0
    if normalized in _MONTHLY_MULTIPLIERS:
        return _MONTHLY_MULTIPLIERS[normalized]
    return 1.0

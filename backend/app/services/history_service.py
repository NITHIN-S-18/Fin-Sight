from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any

from fastapi import Depends

from app.core.exceptions import ExposureDataUnavailableError
from app.schemas.history import HistoricalDashboardResponse, HistoricalMetricPoint
from app.services.dataset_service import DatasetService, get_dataset_service
from app.services.financial_rules import TransactionStatus, classify_transaction_status


class HistoryService:
    _commitment_classes = {"subscription", "emi", "bnpl"}
    def __init__(self, dataset_service: DatasetService) -> None:
        self._dataset_service = dataset_service

    def get_history(self, user_id: str) -> HistoricalDashboardResponse:
        transactions = self._dataset_service.get_user_transactions(user_id)
        if not transactions:
            raise ExposureDataUnavailableError(
                f"No transaction history available for user: {user_id}"
            )

        monthly: dict[str, dict[str, float]] = defaultdict(
            lambda: {"income": 0.0, "spending": 0.0, "commitments": 0.0}
        )
        for transaction in transactions:
            if not self._is_successful(transaction):
                continue
            transaction_month = self._month(transaction.get("transaction_date"))
            amount = self._amount(transaction.get("amount"))
            if not transaction_month or amount < 0.0:
                continue
            bucket = monthly[transaction_month]
            if self._is_income(transaction):
                bucket["income"] += amount
            elif self._transaction_class(transaction) in self._commitment_classes:
                bucket["commitments"] += amount
            else:
                bucket["spending"] += amount

        points: list[HistoricalMetricPoint] = []
        for month in sorted(monthly):
            values = monthly[month]
            income = round(values["income"], 2)
            commitments = round(values["commitments"], 2)
            if income > 0.0:
                exposure = round(commitments / income * 100.0, 2)
                available_capacity = round(income - commitments, 2)
            elif commitments == 0.0:
                exposure = 0.0
                available_capacity = 0.0
            else:
                exposure = 100.0
                available_capacity = round(-commitments, 2)
            health = self._health_score(exposure)
            points.append(
                HistoricalMetricPoint(
                    month=month,
                    income=income,
                    spending=round(values["spending"], 2),
                    commitments=commitments,
                    exposure=exposure,
                    financial_health=health,
                    available_capacity=available_capacity,
                )
            )

        if not points:
            raise ExposureDataUnavailableError(
                f"No successful transaction history available for user: {user_id}"
            )
        return HistoricalDashboardResponse(
            user_id=user_id,
            points=points,
            metric_basis=(
                "Income, spending, and commitments are aggregated from this authenticated "
                "user's successful transactions only. Exposure and available capacity use "
                "monthly income as capacity. Financial health is a transaction-only "
                "exposure approximation and is not the full current Exposure Engine score."
            ),
        )

    @classmethod
    def _is_successful(cls, transaction: dict[str, Any]) -> bool:
        return classify_transaction_status(transaction.get("transaction_status")) is TransactionStatus.SUCCESSFUL

    @staticmethod
    def _is_income(transaction: dict[str, Any]) -> bool:
        flag = transaction.get("income_flag")
        if isinstance(flag, bool):
            return flag
        normalized = str(flag or "").strip().lower()
        return normalized in {"yes", "true", "1", "income", "salary"}

    @classmethod
    def _transaction_class(cls, transaction: dict[str, Any]) -> str:
        return str(
            transaction.get("transaction_class")
            or transaction.get("category")
            or transaction.get("commitment_type")
            or ""
        ).strip().lower()

    @staticmethod
    def _amount(value: Any) -> float:
        try:
            return abs(float(value or 0.0))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _month(value: Any) -> str | None:
        if isinstance(value, datetime):
            return value.strftime("%Y-%m")
        if isinstance(value, date):
            return value.strftime("%Y-%m")
        try:
            return datetime.fromisoformat(str(value)).strftime("%Y-%m")
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _health_score(exposure: float | None) -> float | None:
        if exposure is None:
            return None
        if exposure <= 30.0:
            return 90.0
        if exposure <= 50.0:
            return 75.0
        if exposure <= 70.0:
            return 50.0
        return 25.0


def get_history_service(
    dataset_service: DatasetService = Depends(get_dataset_service),
) -> HistoryService:
    return HistoryService(dataset_service)

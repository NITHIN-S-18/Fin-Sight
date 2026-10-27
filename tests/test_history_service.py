from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.exceptions import ExposureDataUnavailableError
from app.services.history_service import HistoryService


class DatasetStub:
    def __init__(self, transactions):
        self.transactions = transactions

    def get_user_transactions(self, user_id: str):
        assert user_id == "AUTH00000001"
        return self.transactions


def test_history_aggregates_authenticated_transactions_by_month() -> None:
    service = HistoryService(
        DatasetStub(
            [
                {
                    "transaction_date": datetime(2026, 1, 5, tzinfo=timezone.utc),
                    "amount": 100000,
                    "income_flag": "Yes",
                    "transaction_status": "Success",
                },
                {
                    "transaction_date": datetime(2026, 1, 10, tzinfo=timezone.utc),
                    "amount": 20000,
                    "transaction_class": "Subscription",
                    "transaction_status": "Success",
                },
                {
                    "transaction_date": datetime(2026, 1, 15, tzinfo=timezone.utc),
                    "amount": 5000,
                    "transaction_status": "Success",
                },
                {
                    "transaction_date": datetime(2026, 2, 5, tzinfo=timezone.utc),
                    "amount": 120000,
                    "income_flag": True,
                    "transaction_status": "Success",
                },
                {
                    "transaction_date": datetime(2026, 2, 12, tzinfo=timezone.utc),
                    "amount": 30000,
                    "transaction_class": "EMI",
                    "transaction_status": "Success",
                },
                {
                    "transaction_date": datetime(2026, 2, 20, tzinfo=timezone.utc),
                    "amount": 99999,
                    "income_flag": "No",
                    "transaction_status": "Failed",
                },
            ]
        )
    )

    response = service.get_history("AUTH00000001")

    assert [point.month for point in response.points] == ["2026-01", "2026-02"]
    assert response.points[0].income == 100000.0
    assert response.points[0].spending == 5000.0
    assert response.points[0].commitments == 20000.0
    assert response.points[0].exposure == 20.0
    assert response.points[0].available_capacity == 80000.0
    assert response.points[1].spending == 0.0
    assert response.points[1].commitments == 30000.0


def test_history_does_not_fabricate_empty_months_or_values() -> None:
    service = HistoryService(DatasetStub([]))

    with pytest.raises(ExposureDataUnavailableError):
        service.get_history("AUTH00000001")


def test_history_handles_zero_income_months_consistently() -> None:
    service = HistoryService(
        DatasetStub(
            [
                {
                    "transaction_date": datetime(2026, 3, 1, tzinfo=timezone.utc),
                    "amount": 2500,
                    "transaction_class": "Shopping",
                    "transaction_status": "Success",
                },
                {
                    "transaction_date": datetime(2026, 4, 1, tzinfo=timezone.utc),
                    "amount": 3000,
                    "transaction_class": "EMI",
                    "transaction_status": "Success",
                },
            ]
        )
    )

    response = service.get_history("AUTH00000001")
    assert len(response.points) == 2
    # Month 1: 0 income, 0 commitments -> exposure 0.0, available capacity 0.0
    assert response.points[0].month == "2026-03"
    assert response.points[0].income == 0.0
    assert response.points[0].commitments == 0.0
    assert response.points[0].exposure == 0.0
    assert response.points[0].available_capacity == 0.0
    assert response.points[0].financial_health == 90.0

    # Month 2: 0 income, 3000 commitments -> exposure 100.0, available capacity -3000.0
    assert response.points[1].month == "2026-04"
    assert response.points[1].income == 0.0
    assert response.points[1].commitments == 3000.0
    assert response.points[1].exposure == 100.0
    assert response.points[1].available_capacity == -3000.0
    assert response.points[1].financial_health == 25.0



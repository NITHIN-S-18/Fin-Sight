from types import SimpleNamespace

import pandas as pd
import pytest

from app.services.bnpl_service import BnplService
from app.services.emi_service import EmiService
from app.services.exposure_service import ExposureService
from app.services.financial_rules import monthly_multiplier
from app.services.subscription_service import SubscriptionService


class EmptyDatasetService:
    def get_user_transactions(self, user_id: str) -> list[dict]:
        return []

    def get_user(self, user_id: str) -> dict:
        return {"user_id": user_id, "monthly_financial_capacity": 10000.0}


@pytest.mark.parametrize(
    "frequency, expected",
    [
        ("weekly", 52.0 / 12.0),
        ("biweekly", 26.0 / 12.0),
        ("fortnightly", 26.0 / 12.0),
        ("monthly", 1.0),
        ("quarterly", 1.0 / 3.0),
        ("annual", 1.0 / 12.0),
        ("daily", 365.0 / 12.0),
    ],
)
def test_frequency_to_monthly_multiplier(frequency, expected):
    assert monthly_multiplier(frequency) == pytest.approx(expected)


def test_subscription_detection_and_monthly_commitment():
    service = SubscriptionService(EmptyDatasetService())
    frame = service._prepare_subscription_frame(
        [
            {
                "transaction_date": "2026-01-01",
                "amount": 100,
                "merchant_name": "Stream",
                "transaction_class": "Subscription",
                "frequency": "Biweekly",
                "autopay_flag": "Yes",
                "is_new_subscription": "No",
                "transaction_status": "Success",
                "merchant_type": "OTT",
            }
        ]
    )

    row = service._build_active_subscription("Stream", frame)
    assert row["monthly_estimated_cost"] == pytest.approx(100.0 * 26.0 / 12.0, abs=0.01)
    assert row["autopay_enabled"] is True
    assert row["transaction_status_summary"]["successful_transactions"] == 1


def test_emi_detection_and_failed_payment_handling():
    service = EmiService(EmptyDatasetService())
    frame = service._prepare_emi_frame(
        [
            {
                "transaction_date": "2026-01-01",
                "amount": 1200,
                "merchant_name": "Home Loan",
                "transaction_class": "EMI",
                "frequency": "Monthly",
                "autopay_flag": "No",
                "commitment_type": "Mandatory",
                "transaction_status": "Failed",
                "merchant_type": "Loan",
                "category": "Loan EMI",
                "description": "Home loan EMI",
            },
            {
                "transaction_date": "2026-02-01",
                "amount": 1200,
                "merchant_name": "Home Loan",
                "transaction_class": "EMI",
                "frequency": "Monthly",
                "autopay_flag": "No",
                "commitment_type": "Mandatory",
                "transaction_status": "Success",
                "merchant_type": "Loan",
                "category": "Loan EMI",
                "description": "Home loan EMI",
            },
        ]
    )

    active = service._build_active_emi("Home Loan", frame)
    payment = service._build_payment_statistics([active], frame)
    assert active["monthly_emi_amount"] == 1200.0
    assert active["loan_type"] == "Home Loan"
    assert payment.failed_payments == 1
    assert payment.successful_payments == 1
    assert payment.payment_success_rate == 50.0


def test_bnpl_detection_and_installment_commitment():
    service = BnplService(EmptyDatasetService())
    frame = service._prepare_bnpl_frame(
        [
            {
                "transaction_date": "2026-01-01",
                "amount": 500,
                "merchant_name": "Paytm Postpaid",
                "transaction_class": "BNPL",
                "frequency": "Biweekly",
                "autopay_flag": "Yes",
                "commitment_type": "Mandatory",
                "transaction_status": "Success",
                "description": "Installment 2/4",
                "category": "Pay Later",
            }
        ]
    )

    active = service._build_active_bnpl("Paytm Postpaid", frame)
    assert active["monthly_bnpl_commitment"] == pytest.approx(500.0 * 26.0 / 12.0, abs=0.01)
    assert active["number_of_installments"] == 4
    assert active["autopay_enabled"] is True


def test_exposure_percentage_capacity_and_breakdown():
    service = ExposureService(
        EmptyDatasetService(),
        SubscriptionService(EmptyDatasetService()),
        EmiService(EmptyDatasetService()),
        BnplService(EmptyDatasetService()),
    )
    subscription = SimpleNamespace(
        subscription_summary=SimpleNamespace(monthly_subscription_cost=100.0),
        active_subscriptions=[],
    )
    emi = SimpleNamespace(
        emi_summary=SimpleNamespace(monthly_emi_burden=200.0),
        active_emis=[],
    )
    bnpl = SimpleNamespace(
        bnpl_summary=SimpleNamespace(monthly_bnpl_burden=200.0),
        active_bnpl_accounts=[],
    )
    service._current_frame = pd.DataFrame()

    current, summary, available, breakdown, _, _ = service._build_current_status(
        subscription,
        emi,
        bnpl,
        1000.0,
    )

    assert current.monthly_total_commitments == 500.0
    assert current.exposure_score == 50.0
    assert current.available_monthly_capacity == 500.0
    assert summary.exposure_band == "Moderate"
    assert breakdown.emis.percentage_contribution == 40.0


def test_financial_health_penalizes_failed_payments_and_missing_autopay():
    service = ExposureService(
        EmptyDatasetService(),
        SubscriptionService(EmptyDatasetService()),
        EmiService(EmptyDatasetService()),
        BnplService(EmptyDatasetService()),
    )
    item = SimpleNamespace(
        transaction_status_summary=SimpleNamespace(
            successful_transactions=1,
            failed_transactions=1,
            pending_transactions=0,
        ),
        autopay_enabled=False,
    )
    subscription = SimpleNamespace(
        subscription_summary=SimpleNamespace(monthly_subscription_cost=500.0),
        active_subscriptions=[item],
    )
    health = service._build_financial_health(
        50.0,
        subscription,
        None,
        None,
        500.0,
        1000.0,
    )

    assert health.financial_health_score < 98.0
    assert health.factor_scores["payment_behaviour"].score < 25.0
    assert health.factor_scores["autopay"].score < 15.0


def test_unknown_payment_statuses_reduce_aggregate_reliability():
    service = ExposureService(
        EmptyDatasetService(),
        SubscriptionService(EmptyDatasetService()),
        EmiService(EmptyDatasetService()),
        BnplService(EmptyDatasetService()),
    )
    subscription = SimpleNamespace(
        subscription_summary=SimpleNamespace(monthly_subscription_cost=500.0),
        active_subscriptions=[
            SimpleNamespace(
                transaction_status_summary=SimpleNamespace(
                    successful_transactions=1,
                    failed_transactions=0,
                    pending_transactions=0,
                    other_transactions=1,
                ),
                autopay_enabled=True,
            )
        ],
    )

    context = service._build_payment_health_context(subscription, None, None)

    assert context["payment_success_rate"] == 50.0
    assert context["other"] == 1.0

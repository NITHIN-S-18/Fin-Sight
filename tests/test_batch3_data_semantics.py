from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.database.models.transaction import Transaction
from app.services.bnpl_service import BnplService
from app.services.emi_service import EmiService
from app.services.financial_profile_sync_service import FinancialProfileSyncService
from app.services.financial_rules import TransactionStatus, classify_transaction_status
from app.services.subscription_service import SubscriptionService


class EmptyDatasetService:
    def get_user_transactions(self, user_id: str) -> list[dict]:
        return []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Success", TransactionStatus.SUCCESSFUL),
        ("completed", TransactionStatus.SUCCESSFUL),
        ("Failed", TransactionStatus.FAILED),
        ("pending", TransactionStatus.PENDING),
        ("mystery", TransactionStatus.UNKNOWN),
        ("", TransactionStatus.UNKNOWN),
        (None, TransactionStatus.UNKNOWN),
    ],
)
def test_transaction_status_classification_is_explicit(raw, expected):
    assert classify_transaction_status(raw) is expected


def test_profile_success_rate_uses_shared_status_semantics():
    rows = [
        SimpleNamespace(transaction_status="Success"),
        SimpleNamespace(transaction_status="Failed"),
        SimpleNamespace(transaction_status="pending"),
        SimpleNamespace(transaction_status=None),
    ]
    assert FinancialProfileSyncService._success_rate(rows) == "25.0%"


@pytest.mark.parametrize(
    ("service", "class_name"),
    [
        (SubscriptionService(EmptyDatasetService()), "Subscription"),
        (EmiService(EmptyDatasetService()), "EMI"),
        (BnplService(EmptyDatasetService()), "BNPL"),
    ],
)
def test_negative_commitment_amount_cannot_reduce_burden(service, class_name):
    transaction = {
        "transaction_date": "2026-01-01",
        "amount": -500,
        "merchant_name": "Commitment",
        "transaction_class": class_name,
        "frequency": "Monthly",
        "transaction_status": "Success",
        "description": "Installment 1/4",
        "category": "Pay Later",
        "merchant_type": "Loan",
        "autopay_flag": "No",
        "commitment_type": "Mandatory",
        "is_new_subscription": "No",
    }
    if class_name == "Subscription":
        frame = service._prepare_subscription_frame([transaction])
        row = service._build_active_subscription("Commitment", frame)
        assert row["monthly_estimated_cost"] == 0.0
    elif class_name == "EMI":
        frame = service._prepare_emi_frame([transaction])
        row = service._build_active_emi("Commitment", frame)
        assert row["monthly_emi_amount"] == 0.0
    else:
        frame = service._prepare_bnpl_frame([transaction])
        row = service._build_active_bnpl("Commitment", frame)
        assert row["monthly_bnpl_commitment"] == 0.0


def test_signed_ledger_amount_can_represent_a_refund():
    refund = Transaction(
        transaction_id="refund-example",
        user_id="AUTH00000001",
        transaction_date=datetime(2026, 1, 1),
        amount=-125.0,
    )
    assert refund.amount == -125.0


def test_example_environment_matches_settings_parser():
    example_path = Path(__file__).parents[1] / "backend" / ".env.example"
    settings = Settings(_env_file=example_path)
    assert settings.cors_allow_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]
    example = example_path.read_text(encoding="utf-8")
    assert "GEMINI_API_KEY=\n" in example
    assert "AUTH_JWT_SECRET" not in example

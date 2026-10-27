from datetime import datetime, timedelta

from app.services.recurring_payment_service import RecurringPaymentService


def transaction(
    merchant: str,
    when: datetime,
    amount: float,
    *,
    category: str = "Subscription",
    status: str = "success",
    description: str | None = None,
) -> dict[str, object]:
    return {
        "transaction_id": f"{merchant}-{when.date()}",
        "transaction_date": when,
        "merchant_name": merchant,
        "description": description,
        "amount": amount,
        "category": category,
        "transaction_class": category,
        "transaction_status": status,
    }


def test_three_monthly_occurrences_are_high_confidence() -> None:
    rows = [
        transaction("Netflix", datetime(2026, 1, 5), 649),
        transaction("Netflix", datetime(2026, 2, 4), 649),
        transaction("Netflix", datetime(2026, 3, 6), 649),
    ]

    candidates = RecurringPaymentService._candidate_groups(rows)

    assert len(candidates) == 1
    assert candidates[0]["frequency"] == "monthly"
    assert candidates[0]["confidence_level"] == "high"
    assert candidates[0]["monthly_equivalent_amount"] == 649


def test_two_occurrences_are_low_confidence_review_candidates() -> None:
    rows = [
        transaction("Spotify", datetime(2026, 1, 10), 119),
        transaction("Spotify", datetime(2026, 2, 9), 119),
    ]

    candidates = RecurringPaymentService._candidate_groups(rows)

    assert candidates[0]["confidence_level"] == "low"
    assert candidates[0]["evidence"]["low_confidence_review_required"] is True


def test_weekly_quarterly_and_annual_frequency_detection() -> None:
    cases = [
        ("Weekly", [datetime(2026, 1, 1), datetime(2026, 1, 8), datetime(2026, 1, 15)], "weekly"),
        ("Quarterly", [datetime(2026, 1, 1), datetime(2026, 4, 2)], "quarterly"),
        ("Annual", [datetime(2025, 1, 1), datetime(2026, 1, 1)], "annual"),
    ]

    for merchant, dates, expected in cases:
        rows = [transaction(merchant, when, 1000) for when in dates]
        candidates = RecurringPaymentService._candidate_groups(rows)
        assert candidates[0]["frequency"] == expected


def test_variable_utility_amounts_can_still_be_recurring() -> None:
    rows = [
        transaction("City Electricity", datetime(2026, 1, 5), 1000, category="Electricity"),
        transaction("City Electricity", datetime(2026, 2, 4), 1200, category="Electricity"),
        transaction("City Electricity", datetime(2026, 3, 6), 800, category="Electricity"),
    ]

    candidates = RecurringPaymentService._candidate_groups(rows)

    assert len(candidates) == 1
    assert candidates[0]["category"] == "electricity"


def test_failed_unknown_and_negative_transactions_are_not_evidence() -> None:
    rows = [
        transaction("Rent", datetime(2026, 1, 1), 15000, category="Rent"),
        transaction("Rent", datetime(2026, 2, 1), 15000, category="Rent", status="failed"),
        transaction("Rent", datetime(2026, 3, 1), 15000, category="Rent", status=""),
        transaction("Rent", datetime(2026, 4, 1), -15000, category="Rent"),
    ]

    assert RecurringPaymentService._candidate_groups(rows) == []


def test_different_merchants_are_not_merged() -> None:
    rows = [
        transaction("Netflix", datetime(2026, 1, 5), 649),
        transaction("Spotify", datetime(2026, 1, 5) + timedelta(days=30), 649),
    ]

    assert RecurringPaymentService._candidate_groups(rows) == []


def test_income_transactions_are_never_recurring_commitment_candidates() -> None:
    rows = [
        transaction("ACME Technologies", datetime(2026, 1, 1), 85000, category="Income"),
        transaction("ACME Technologies", datetime(2026, 2, 1), 85000, category="Income"),
        transaction("ACME Technologies", datetime(2026, 3, 1), 85000, category="Income"),
    ]

    assert RecurringPaymentService._candidate_groups(rows) == []

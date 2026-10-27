from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd

from app.ml.subscription_usage import (
    FEATURE_COLUMNS,
    baseline_predict,
    build_observation_snapshots,
    target_from_future,
    temporal_split,
)


def _row(month: str, status: str = "Success", amount: float = 500.0) -> dict[str, object]:
    return {
        "user_id": "U1",
        "merchant_name": "Netflix",
        "transaction_date": f"{month}-05",
        "amount": amount,
        "transaction_class": "Subscription",
        "transaction_status": status,
        "frequency": "Monthly",
        "category": "Subscription",
        "autopay_flag": "Yes",
        "income_flag": "No",
    }


def test_future_target_rules_are_deterministic_and_non_random() -> None:
    future = pd.DataFrame([_row("2024-07"), _row("2024-08"), _row("2024-09")])
    assert target_from_future(future) == "ACTIVE"
    assert target_from_future(future.iloc[:2]) == "MODERATE"
    assert target_from_future(pd.DataFrame(columns=future.columns)) == "UNDER_UTILIZED"


def test_snapshot_features_stop_at_cutoff_and_temporal_split_is_ordered() -> None:
    rows = [
        _row(f"{year}-{month:02d}")
        for year in (2023, 2024)
        for month in range(1, 13)
    ]
    snapshots = build_observation_snapshots(pd.DataFrame(rows))
    assert set(FEATURE_COLUMNS).issubset(snapshots.columns)
    assert snapshots["observation_month"].is_monotonic_increasing
    splits = temporal_split(snapshots)
    assert splits.train.observation_month.max() < splits.validation.observation_month.min()
    assert splits.validation.observation_month.max() < splits.test.observation_month.min()


def test_baseline_is_rule_based_and_does_not_use_target() -> None:
    frame = pd.DataFrame(
        [
            {"payment_success_rate": 1.0, "longest_payment_gap": 30, "amount_consistency": 0.95, "days_since_last_payment": 30},
            {"payment_success_rate": 0.5, "longest_payment_gap": 90, "amount_consistency": 0.5, "days_since_last_payment": 40},
            {"payment_success_rate": 0.0, "longest_payment_gap": 120, "amount_consistency": 0.0, "days_since_last_payment": 120},
        ]
    )
    assert baseline_predict(frame).tolist() == ["ACTIVE", "MODERATE", "UNDER_UTILIZED"]


def test_model3_artifact_reloads_with_frozen_feature_schema() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "app"
        / "ml"
        / "saved_models"
        / "financial_subscription_usage"
        / "v1.0"
        / "artifact.pkl"
    )
    with path.open("rb") as handle:
        artifact = pickle.load(handle)
    assert artifact["model_version"] == "financial_subscription_usage-v1.0"
    assert artifact["feature_schema"] == list(FEATURE_COLUMNS)
    assert artifact["evaluation"]["acceptance"]["decision"] == "ML_ACCEPTED"

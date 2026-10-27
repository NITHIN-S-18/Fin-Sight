"""Tests for the Phase 2 Controlled Shortfall Research Experiment Pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from research.pipeline import (
    COMMITMENT_FEATURES,
    MODEL_A_FEATURES,
    MODEL_B_FEATURES,
    TARGET,
    build_research_snapshots,
    extract_feature_row,
    temporal_split,
)

RESEARCH_DIR = Path(__file__).resolve().parents[1] / "backend" / "research"
ARTIFACTS_DIR = RESEARCH_DIR / "artifacts" / "phase2_controlled_experiment"


@pytest.fixture(scope="module")
def sample_transactions() -> pd.DataFrame:
    rows = []
    for month in range(1, 10):
        date = f"2024-{month:02d}-15"
        # Monthly salary
        rows.append(
            {
                "user_id": "U_TEST_1",
                "transaction_date": date,
                "amount": 2000.0,
                "category": "Income",
                "transaction_class": "Income",
                "income_flag": "Yes",
                "transaction_status": "Success",
            }
        )
        # Recurring rent subscription
        rows.append(
            {
                "user_id": "U_TEST_1",
                "transaction_date": date,
                "amount": 500.0 if month < 9 else 2500.0,
                "category": "Rent",
                "transaction_class": "Subscription",
                "income_flag": "No",
                "transaction_status": "Success",
            }
        )
        # Variable dining
        rows.append(
            {
                "user_id": "U_TEST_1",
                "transaction_date": date,
                "amount": 200.0,
                "category": "Food",
                "transaction_class": "Other",
                "income_flag": "No",
                "transaction_status": "Success",
            }
        )
    return pd.DataFrame(rows)


def test_feature_list_counts_and_uniqueness():
    """Verify Model A has 27, Commitment has 14, and Model B has 41 unique features."""
    assert len(MODEL_A_FEATURES) == 27
    assert len(set(MODEL_A_FEATURES)) == 27
    assert len(COMMITMENT_FEATURES) == 14
    assert len(set(COMMITMENT_FEATURES)) == 14
    assert len(MODEL_B_FEATURES) == 41
    assert len(set(MODEL_B_FEATURES)) == 41

    # Verify excluded aliases are not in either feature vector
    excluded = {"total_monthly_commitments", "active_recurring_count", "commitment_burden", "commitment_change"}
    assert not excluded.intersection(set(MODEL_A_FEATURES))
    assert not excluded.intersection(set(MODEL_B_FEATURES))


def test_target_is_observed_next_month(sample_transactions):
    """Verify target matches strictly next calendar month outcome."""
    snapshots = build_research_snapshots(sample_transactions)
    assert not snapshots.empty
    assert snapshots[TARGET].isin([0, 1]).all()

    # Outcome month must be strictly greater than feature month
    for _, row in snapshots.iterrows():
        feat_dt = pd.to_datetime(row["feature_month"] + "-01")
        out_dt = pd.to_datetime(row["outcome_month"] + "-01")
        assert out_dt > feat_dt


def test_temporal_cutoff_prevents_future_leakage(sample_transactions):
    """Mutating future month T+1 transactions must not alter cutoff T feature values."""
    snaps_orig = build_research_snapshots(sample_transactions)
    orig_features_t1 = snaps_orig.iloc[0][list(MODEL_B_FEATURES)].copy()

    # Dramatically mutate month 9 transaction amount
    mutated = sample_transactions.copy()
    mutated.loc[mutated["transaction_date"] == "2024-09-15", "amount"] = 999999.0
    snaps_mut = build_research_snapshots(mutated)
    mut_features_t1 = snaps_mut.iloc[0][list(MODEL_B_FEATURES)]

    pd.testing.assert_series_equal(orig_features_t1, mut_features_t1, check_names=False)


def test_consistent_6m_window_for_commitment_burdens():
    """Verify that subscription, EMI, and BNPL burdens are window-bounded to 6 months."""
    months = [f"2024-{m:02d}" for m in range(1, 10)]
    hist = pd.DataFrame(
        {
            "income": [2000.0] * 9,
            "committed": [600.0] * 9,
            "variable": [300.0] * 9,
        },
        index=pd.PeriodIndex(months, freq="M"),
    )

    # Synthetic raw debits for the 6-month window (months 4 through 9)
    raw_rows = []
    for m in range(4, 10):
        raw_rows.append(
            {
                "amount": 200.0,
                "transaction_class": "subscription",
                "transaction_status": "Success",
                "category": "OTT",
            }
        )
        raw_rows.append(
            {
                "amount": 400.0,
                "transaction_class": "emi",
                "transaction_status": "Success",
                "category": "Device Loan",
            }
        )
    raw_df = pd.DataFrame(raw_rows)

    row = extract_feature_row(hist, raw_df)
    # Total subscription across 6 months is 200 * 6 = 1200; mean monthly is 1200 / 6 = 200.0
    assert pytest.approx(row["subscription_burden"], 0.01) == 200.0
    # Total EMI across 6 months is 400 * 6 = 2400; mean monthly is 2400 / 6 = 400.0
    assert pytest.approx(row["emi_burden"], 0.01) == 400.0
    assert pytest.approx(row["bnpl_burden"], 0.01) == 0.0
    assert pytest.approx(row["recurring_payment_burden"], 0.01) == 600.0


def test_temporal_partition_exclusivity():
    """Verify that train, validation, and test observation sets are mutually exclusive."""
    raw_df = pd.read_csv(Path(__file__).resolve().parents[1] / "backend" / "app" / "data" / "finsight_dataset_v2.csv")
    snapshots = build_research_snapshots(raw_df)
    splits = temporal_split(snapshots)

    train_keys = set(splits.train["user_id"] + "_" + splits.train["feature_month"])
    val_keys = set(splits.validation["user_id"] + "_" + splits.validation["feature_month"])
    test_keys = set(splits.test["user_id"] + "_" + splits.test["feature_month"])

    assert not train_keys.intersection(val_keys)
    assert not train_keys.intersection(test_keys)
    assert not val_keys.intersection(test_keys)

    assert len(splits.train) == 2463
    assert len(splits.validation) == 559
    assert len(splits.test) == 422
    assert len(train_keys) + len(val_keys) + len(test_keys) == 3444


def test_saved_predictions_recalculation_parity():
    """Verify headline test metrics recalculated from test_predictions.csv match metrics_comparison.json."""
    preds_file = ARTIFACTS_DIR / "test_predictions.csv"
    metrics_file = ARTIFACTS_DIR / "metrics_comparison.json"

    assert preds_file.exists()
    assert metrics_file.exists()

    df = pd.read_csv(preds_file)
    assert len(df) == 422

    with open(metrics_file, "r", encoding="utf-8") as f:
        metrics = json.load(f)

    y_true = df["y_true"].to_numpy()

    # Recalculate Model A
    ap_a = round(average_precision_score(y_true, df["model_a_prob"]), 4)
    roc_a = round(roc_auc_score(y_true, df["model_a_prob"]), 4)
    bal_a = round(balanced_accuracy_score(y_true, df["model_a_pred"]), 4)
    f1_a = round(f1_score(y_true, df["model_a_pred"]), 4)
    brier_a = round(brier_score_loss(y_true, df["model_a_prob"]), 4)

    assert ap_a == metrics["model_a"]["test_metrics"]["average_precision"]
    assert roc_a == metrics["model_a"]["test_metrics"]["roc_auc"]
    assert bal_a == metrics["model_a"]["test_metrics"]["balanced_accuracy"]
    assert f1_a == metrics["model_a"]["test_metrics"]["f1"]
    assert brier_a == metrics["model_a"]["test_metrics"]["brier_score"]

    # Recalculate Model B
    ap_b = round(average_precision_score(y_true, df["model_b_prob"]), 4)
    roc_b = round(roc_auc_score(y_true, df["model_b_prob"]), 4)
    bal_b = round(balanced_accuracy_score(y_true, df["model_b_pred"]), 4)
    f1_b = round(f1_score(y_true, df["model_b_pred"]), 4)
    brier_b = round(brier_score_loss(y_true, df["model_b_prob"]), 4)

    assert ap_b == metrics["model_b"]["test_metrics"]["average_precision"]
    assert roc_b == metrics["model_b"]["test_metrics"]["roc_auc"]
    assert bal_b == metrics["model_b"]["test_metrics"]["balanced_accuracy"]
    assert f1_b == metrics["model_b"]["test_metrics"]["f1"]
    assert brier_b == metrics["model_b"]["test_metrics"]["brier_score"]


def test_bootstrap_paired_user_clustering_integrity():
    """Verify bootstrap confidence intervals evaluate paired user clusters."""
    metrics_file = ARTIFACTS_DIR / "metrics_comparison.json"
    with open(metrics_file, "r", encoding="utf-8") as f:
        metrics = json.load(f)

    boot = metrics["bootstrap_paired_test"]
    assert boot["bootstrap_replicates_valid"] == 1000
    assert boot["resampling_unit"] == "user_id (clustered)"

    # Verify that the 95% CI includes zero for Average Precision and ROC-AUC
    delta_ap = boot["differences"]["delta_average_precision"]
    assert delta_ap["ci_lower_2_5"] <= 0.0 <= delta_ap["ci_upper_97_5"]

    delta_roc = boot["differences"]["delta_roc_auc"]
    assert delta_roc["ci_lower_2_5"] <= 0.0 <= delta_roc["ci_upper_97_5"]

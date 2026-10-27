from __future__ import annotations

import pandas as pd

from app.ml.persistence import ModelPersistenceManager
from app.ml.shortfall import FEATURE_COLUMNS, baseline_predict, build_snapshots, current_features


def _transactions() -> pd.DataFrame:
    rows = []
    for month in range(1, 10):
        date = f"2024-{month:02d}-15"
        rows.extend(
            [
                {
                    "user_id": "U1",
                    "transaction_date": date,
                    "amount": 1000,
                    "category": "Income",
                    "transaction_class": "Income",
                    "income_flag": "Yes",
                    "transaction_status": "Success",
                },
                {
                    "user_id": "U1",
                    "transaction_date": date,
                    "amount": 400 if month < 9 else 1400,
                    "category": "Rent",
                    "transaction_class": "Subscription",
                    "income_flag": "No",
                    "transaction_status": "Success",
                },
                {
                    "user_id": "U1",
                    "transaction_date": date,
                    "amount": 100,
                    "category": "Food",
                    "transaction_class": "Other",
                    "income_flag": "No",
                    "transaction_status": "Success",
                },
            ]
        )
    return pd.DataFrame(rows)


def test_target_is_observed_next_month_and_features_are_historical_only():
    frame = _transactions()
    snapshots = build_snapshots(frame)
    assert not snapshots.empty
    assert snapshots["shortfall"].isin([0, 1]).all()
    assert (pd.to_datetime(snapshots["outcome_month"] + "-01") > pd.to_datetime(snapshots["feature_month"] + "-01")).all()

    before = snapshots.iloc[0][list(FEATURE_COLUMNS)].copy()
    changed = frame.copy()
    changed.loc[changed["transaction_date"] == "2024-09-15", "amount"] = 999999
    after = build_snapshots(changed).iloc[0][list(FEATURE_COLUMNS)]
    pd.testing.assert_series_equal(before, after, check_names=False)


def test_baseline_is_deterministic_and_independent_of_target():
    frame = build_snapshots(_transactions())
    first = baseline_predict(frame)
    second = baseline_predict(frame.drop(columns=["shortfall"]))
    assert (first == second).all()


def test_artifact_reload_matches_training_schema():
    bundle = ModelPersistenceManager().load("financial_shortfall", "v1.0")
    assert bundle.artifact.model_version == "v1.0"
    assert tuple(bundle.artifact.feature_columns) == FEATURE_COLUMNS
    assert bundle.preprocessor_state is not None


def test_current_features_include_model1_outputs_as_features_only():
    frame = _transactions()

    class Forecast:
        forecast_available = True
        expected_income = 1200
        expected_committed_expenses = 500
        expected_variable_expenses = 150
        expected_total_expenses = 650
        expected_net_cash = 550

    features, horizon = current_features(frame, Forecast())
    assert horizon == "2024-10"
    assert features is not None
    assert float(features.iloc[0]["expected_net_cash"]) == 550

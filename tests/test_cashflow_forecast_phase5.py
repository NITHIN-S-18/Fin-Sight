from __future__ import annotations

import pandas as pd

from app.ml.cashflow_forecast import CashFlowForecastDatasetBuilder
from app.ml.cashflow_forecast import CashFlowModelTrainer
from app.ml.persistence import ModelPersistenceManager
from app.services.cashflow_forecast_service import CashFlowForecastService


def _transactions() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for month in range(1, 9):
        rows.extend(
            [
                {
                    "user_id": "U1",
                    "transaction_date": f"2025-{month:02d}-01",
                    "amount": 50000 + month * 100,
                    "transaction_status": "success",
                    "income_flag": True,
                    "transaction_class": "Income",
                },
                {
                    "user_id": "U1",
                    "transaction_date": f"2025-{month:02d}-10",
                    "amount": 10000,
                    "transaction_status": "success",
                    "income_flag": False,
                    "transaction_class": "Subscription",
                },
                {
                    "user_id": "U1",
                    "transaction_date": f"2025-{month:02d}-20",
                    "amount": 5000 + month * 50,
                    "transaction_status": "success",
                    "income_flag": False,
                    "transaction_class": "Food",
                },
            ]
        )
    return pd.DataFrame(rows)


def test_cashflow_targets_are_observed_next_month_and_history_is_enforced() -> None:
    examples = CashFlowForecastDatasetBuilder().build(_transactions())

    assert examples
    assert examples[0].feature_month == "2025-06"
    assert examples[0].outcome_month == "2025-07"
    assert examples[0].income == 50700
    assert examples[0].committed == 10000
    assert examples[0].variable == 5350


def test_failed_and_negative_transactions_do_not_reduce_forecast_expenses() -> None:
    frame = _transactions()
    frame.loc[len(frame)] = {
        "user_id": "U1",
        "transaction_date": "2025-08-25",
        "amount": -9000,
        "transaction_status": "success",
        "income_flag": False,
        "transaction_class": "Subscription",
    }
    frame.loc[len(frame)] = {
        "user_id": "U1",
        "transaction_date": "2025-08-26",
        "amount": 99999,
        "transaction_status": "failed",
        "income_flag": False,
        "transaction_class": "Food",
    }
    monthly = CashFlowForecastDatasetBuilder().monthly_series(frame)
    assert monthly.loc["2025-08", "committed"] == 10000
    assert monthly.loc["2025-08", "variable"] == 5400


def test_cashflow_model_trains_persists_loads_and_derives_consistent_outputs(tmp_path) -> None:
    extended = _transactions()
    shifted = _transactions().copy()
    shifted["transaction_date"] = (
        pd.to_datetime(shifted["transaction_date"]) + pd.DateOffset(months=8)
    ).dt.strftime("%Y-%m-%d")
    examples = CashFlowForecastDatasetBuilder().build(pd.concat([extended, shifted], ignore_index=True))
    manager = ModelPersistenceManager(tmp_path)
    bundle = CashFlowModelTrainer().train(examples, manager)
    loaded = manager.load("cash_flow_forecast", "v1.0")
    prediction = CashFlowModelTrainer.predict(loaded, examples[-1])

    assert set(prediction) == {"income", "committed", "variable"}
    assert all(value >= 0 for value in prediction.values())
    assert loaded.artifact.metadata["train_period"]
    assert loaded.artifact.metadata["validation_period"]
    assert loaded.artifact.metadata["test_period"]


def test_category_forecast_is_monthly_model_1_allocation_not_raw_stress_total() -> None:
    frame = _transactions()
    frame["category"] = ["Income", "Subscription", "Shopping"] * 8
    frame.loc[len(frame)] = {
        "user_id": "U1", "transaction_date": "2025-08-22", "amount": 9_870_000,
        "transaction_status": "success", "income_flag": False,
        "transaction_class": "Food", "category": "Shopping",
    }

    forecast = CashFlowForecastService._variable_category_forecast(
        frame, expected_variable_expenses=8440
    )

    assert sum(forecast.values()) == 8440
    assert forecast["Shopping"] == 8440

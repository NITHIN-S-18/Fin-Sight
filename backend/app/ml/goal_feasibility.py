"""Isolated Model 2 dataset, labels, evaluation, and training helpers.

This module intentionally does not import or call the Model 1 forecast or goal
service.  Every target is computed from the six observed future transaction
months in a scenario.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

SUCCESS_STATUSES = {"success", "succeeded", "successful", "completed", "paid", "settled"}
COMMITTED_CLASSES = {"subscription", "emi", "bnpl"}
FEATURE_COLUMNS = [
    "history_income_mean",
    "history_income_std",
    "history_committed_mean",
    "history_variable_mean",
    "history_buffer_mean",
    "history_buffer_min",
    "history_buffer_std",
    "history_income_trend",
    "history_spending_trend",
    "history_success_rate",
    "required_monthly_saving",
]
REQUIRED_SAVING_TIERS = {
    "conservative": 0.10,
    "moderate": 0.30,
    "ambitious": 0.50,
}
TIMEFRAME_BY_TIER = {
    "conservative": 12,
    "moderate": 6,
    "ambitious": 3,
}


@dataclass(frozen=True)
class GoalScenario:
    user_id: str
    feature_month: str
    future_start_month: str
    future_end_month: str
    required_saving_tier: str
    goal_amount: float
    timeframe_months: int
    required_monthly_saving: float
    features: dict[str, float]
    future_monthly_values: tuple[dict[str, float], ...]


def _monthly_frame(transactions: pd.DataFrame) -> pd.DataFrame:
    required = {"user_id", "transaction_date", "amount"}
    missing = required - set(transactions.columns)
    if missing:
        raise ValueError(f"Transactions missing required columns: {sorted(missing)}")
    frame = transactions.copy()
    frame["user_id"] = frame["user_id"].astype(str)
    frame["transaction_date"] = pd.to_datetime(frame["transaction_date"], errors="coerce")
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce").fillna(0.0)
    frame = frame.dropna(subset=["transaction_date"])
    status = frame.get("transaction_status", pd.Series("", index=frame.index)).fillna("").astype(str).str.lower()
    success = status.isin(SUCCESS_STATUSES)
    positive = frame["amount"].clip(lower=0.0)
    income = frame.get("income_flag", pd.Series("", index=frame.index)).fillna("").astype(str).str.lower().isin(
        {"yes", "true", "1"}
    )
    classes = frame.get("transaction_class", pd.Series("", index=frame.index)).fillna("").astype(str).str.lower()
    committed = classes.isin(COMMITTED_CLASSES)
    variable = ~income & ~committed
    frame["_income"] = positive.where(success & income, 0.0)
    frame["_committed"] = positive.where(success & committed, 0.0)
    frame["_variable"] = positive.where(success & variable, 0.0)
    frame["_successful_rows"] = success.astype(int)
    frame["_valid_rows"] = status.ne("").astype(int)
    frame["month"] = frame["transaction_date"].dt.to_period("M")
    monthly = frame.groupby(["user_id", "month"], sort=True)[
        ["_income", "_committed", "_variable", "_successful_rows", "_valid_rows"]
    ].sum()
    monthly["buffer"] = monthly["_income"] - monthly["_committed"] - monthly["_variable"]
    return monthly


def _slope(values: list[float]) -> float:
    if len(values) < 2 or not any(values):
        return 0.0
    return float(np.polyfit(np.arange(len(values), dtype=float), values, 1)[0])


def generate_historical_scenarios(
    transactions: pd.DataFrame,
    *,
    min_history_months: int = 6,
    future_window_months: int = 6,
) -> list[GoalScenario]:
    """Create rolling, leakage-safe six-month-history/six-month-future scenarios."""
    if min_history_months < 6 or future_window_months != 6:
        raise ValueError("Model 2 requires at least six history and a six-month future window.")
    monthly = _monthly_frame(transactions)
    scenarios: list[GoalScenario] = []
    for user_id, user_months in monthly.groupby(level=0, sort=True):
        user_months = user_months.droplevel(0).sort_index()
        if len(user_months) < min_history_months + future_window_months:
            continue
        observed = user_months.index
        for end_index in range(min_history_months - 1, len(observed) - future_window_months):
            history_months = observed[end_index - min_history_months + 1 : end_index + 1]
            future_months = observed[end_index + 1 : end_index + 1 + future_window_months]
            # Calendar continuity prevents silently treating missing months as history.
            expected = pd.period_range(history_months[0], future_months[-1], freq="M")
            if not set(expected).issubset(set(observed)):
                continue
            history = user_months.loc[history_months]
            future = user_months.loc[future_months]
            income_mean = float(history["_income"].mean())
            buffers = history["buffer"].astype(float).tolist()
            spending = (history["_committed"] + history["_variable"]).astype(float).tolist()
            future_values = tuple(
                {
                    "income": float(row["_income"]),
                    "committed": float(row["_committed"]),
                    "variable": float(row["_variable"]),
                    "buffer": float(row["buffer"]),
                }
                for _, row in future.iterrows()
            )
            for tier, quantile in REQUIRED_SAVING_TIERS.items():
                required = round(max(float(history["buffer"].quantile(quantile)), 1.0), 2)
                timeframe_months = TIMEFRAME_BY_TIER[tier]
                features = {
                    "history_income_mean": income_mean,
                    "history_income_std": float(history["_income"].std(ddof=0)),
                    "history_committed_mean": float(history["_committed"].mean()),
                    "history_variable_mean": float(history["_variable"].mean()),
                    "history_buffer_mean": float(history["buffer"].mean()),
                    "history_buffer_min": float(history["buffer"].min()),
                    "history_buffer_std": float(history["buffer"].std(ddof=0)),
                    "history_income_trend": _slope(history["_income"].astype(float).tolist()),
                    "history_spending_trend": _slope(spending),
                    "history_success_rate": float(history["_successful_rows"].sum())
                    / max(float(history["_valid_rows"].sum()), 1.0),
                    "required_monthly_saving": required,
                }
                scenarios.append(
                    GoalScenario(
                        user_id=str(user_id),
                        feature_month=str(history_months[-1]),
                        future_start_month=str(future_months[0]),
                        future_end_month=str(future_months[-1]),
                        required_saving_tier=tier,
                        goal_amount=round(required * timeframe_months, 2),
                        timeframe_months=timeframe_months,
                        required_monthly_saving=required,
                        features=features,
                        future_monthly_values=future_values,
                    )
                )
    if not scenarios:
        raise ValueError("No complete six-month-history/six-month-future scenarios were generated.")
    return scenarios


def construct_labels(scenarios: list[GoalScenario]) -> pd.Series:
    """Label actual future behavior without rewarding commitment reductions.

    The historical committed mean is held constant during outcome evaluation.
    A lower future committed amount therefore cannot manufacture a feasible
    label; only observed future income and variable spending can support it.
    """
    labels = []
    for scenario in scenarios:
        committed_floor = scenario.features["history_committed_mean"]
        labels.append(
            int(
                all(
                    month["income"] - committed_floor - month["variable"]
                    >= scenario.required_monthly_saving
                    for month in scenario.future_monthly_values
                )
            )
        )
    return pd.Series(labels, dtype="int8", name="goal_feasible")


def build_leakage_metadata(scenarios: list[GoalScenario]) -> dict[str, Any]:
    """Return auditable metadata proving feature/future separation."""
    fingerprint = sha256(
        repr(
            [
                (row.user_id, row.feature_month, row.future_start_month, row.future_end_month)
                for row in scenarios
            ]
        ).encode("utf-8")
    ).hexdigest()
    return {
        "scenario_count": len(scenarios),
        "user_count": len({row.user_id for row in scenarios}),
        "feature_columns": FEATURE_COLUMNS,
        "future_columns_used_only_for_labels": ["income", "committed", "variable", "buffer"],
        "required_saving_tiers": {
            tier: {
                "historical_buffer_quantile": quantile,
                "interpretation": f"{tier} required savings threshold from the scenario's six-month observed buffer range",
            }
            for tier, quantile in REQUIRED_SAVING_TIERS.items()
        },
        "timeframe_months_by_tier": TIMEFRAME_BY_TIER,
        "scenario_schema": [
            "goal_amount",
            "timeframe_months",
            "required_monthly_saving",
        ],
        "goal_amount_formula": "goal_amount = required_monthly_saving * timeframe_months",
        "feature_future_boundary_rule": "features use months <= feature_month; labels use the next six calendar months only",
        "future_data_in_features": False,
        "model_1_formula_used_for_labels": False,
        "scenario_fingerprint": fingerprint,
    }


def classification_metrics(
    y_true: list[int] | pd.Series,
    predictions: list[int] | np.ndarray,
    probabilities: list[float] | np.ndarray | None = None,
) -> dict[str, Any]:
    true = np.asarray(y_true, dtype=int)
    pred = np.asarray(predictions, dtype=int)
    result: dict[str, Any] = {
        "count": int(len(true)),
        "accuracy": round(float(accuracy_score(true, pred)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(true, pred)), 4),
        "precision": round(float(precision_score(true, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(true, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(true, pred, zero_division=0)), 4),
        "positive_rate": round(float(true.mean()), 4) if len(true) else 0.0,
        "confusion_matrix": confusion_matrix(true, pred, labels=[0, 1]).tolist(),
    }
    if probabilities is not None and len(np.unique(true)) == 2:
        score = np.asarray(probabilities, dtype=float)
        result.update(
            roc_auc=round(float(roc_auc_score(true, score)), 4),
            pr_auc=round(float(average_precision_score(true, score)), 4),
            brier=round(float(brier_score_loss(true, score)), 4),
        )
    else:
        result.update(roc_auc=None, pr_auc=None, brier=None)
    return result


def split_scenarios(
    scenarios: list[GoalScenario], *,
    seed: int = 42,
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
) -> dict[str, list[GoalScenario]]:
    """Split chronologically, while assigning every user to one split only."""
    users = sorted({scenario.user_id for scenario in scenarios})
    rng = np.random.default_rng(seed)
    rng.shuffle(users)
    train_end = max(1, int(len(users) * train_fraction))
    validation_end = max(train_end + 1, int(len(users) * (train_fraction + validation_fraction)))
    groups = {
        "train": set(users[:train_end]),
        "validation": set(users[train_end:validation_end]),
        "test": set(users[validation_end:]),
    }
    if not all(groups.values()):
        raise ValueError("User-disjoint train/validation/test split is empty.")
    months = sorted({scenario.feature_month for scenario in scenarios})
    train_month_end = max(1, int(len(months) * train_fraction))
    validation_month_end = max(
        train_month_end + 1,
        int(len(months) * (train_fraction + validation_fraction)),
    )
    month_groups = {
        "train": set(months[:train_month_end]),
        "validation": set(months[train_month_end:validation_month_end]),
        "test": set(months[validation_month_end:]),
    }
    return {
        name: sorted(
            [
                scenario
                for scenario in scenarios
                if scenario.user_id in user_ids and scenario.feature_month in month_groups[name]
            ],
            key=lambda item: (item.feature_month, item.user_id),
        )
        for name, user_ids in groups.items()
    }


def baseline_predictions(scenarios: list[GoalScenario]) -> np.ndarray:
    """Deterministic history-only comparator, intentionally distinct from labels."""
    return np.asarray(
        [int(row.features["history_buffer_mean"] >= row.required_monthly_saving) for row in scenarios],
        dtype=int,
    )


def feature_frame(scenarios: list[GoalScenario]) -> pd.DataFrame:
    return pd.DataFrame([{column: row.features[column] for column in FEATURE_COLUMNS} for row in scenarios])


def train_classifier(
    model_factory: Callable[[], Any],
    train: list[GoalScenario],
    validation: list[GoalScenario],
) -> tuple[Any, dict[str, Any]]:
    model = model_factory()
    model.fit(feature_frame(train), construct_labels(train))
    probabilities = model.predict_proba(feature_frame(validation))[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    return model, classification_metrics(construct_labels(validation), predictions, probabilities)

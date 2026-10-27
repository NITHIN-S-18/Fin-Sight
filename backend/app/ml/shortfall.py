from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from app.ml.cashflow_forecast import _boolean_values, _positive_successful
from app.services.financial_rules import TransactionStatus, classify_transaction_status

TARGET = "shortfall"
FEATURE_COLUMNS = (
    "previous_income",
    "income_3m",
    "income_6m",
    "income_trend",
    "income_volatility",
    "income_stability",
    "previous_committed",
    "committed_3m",
    "committed_6m",
    "commitment_ratio",
    "commitment_count",
    "commitment_growth",
    "subscription_burden",
    "emi_burden",
    "bnpl_burden",
    "recurring_payment_burden",
    "commitment_diversity",
    "previous_variable",
    "variable_3m",
    "variable_6m",
    "variable_trend",
    "variable_volatility",
    "discretionary_spending",
    "category_growth",
    "category_volatility",
    "previous_net_cash",
    "net_cash_3m",
    "net_cash_6m",
    "minimum_net_cash",
    "net_cash_volatility",
    "positive_cash_frequency",
    "negative_cash_frequency",
    "payment_success_rate",
    "failed_transaction_rate",
    "pending_transaction_rate",
    "payment_reliability",
    "total_monthly_commitments",
    "active_recurring_count",
    "commitment_burden",
    "commitment_change",
    "expected_income",
    "expected_committed_expenses",
    "expected_variable_expenses",
    "expected_total_expenses",
    "expected_net_cash",
)


def _slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(np.polyfit(np.arange(len(values)), values, 1)[0])


def _std(values: list[float]) -> float:
    return float(np.std(values, ddof=0)) if values else 0.0


def _safe_mean(values: pd.Series) -> float:
    return float(values.mean()) if len(values) else 0.0


def monthly_cashflow(transactions: pd.DataFrame) -> pd.DataFrame:
    """Apply the same successful positive transaction semantics as Model 1."""
    if transactions.empty:
        return pd.DataFrame(columns=["income", "committed", "variable"])
    frame = transactions.copy()
    frame["transaction_date"] = pd.to_datetime(frame["transaction_date"], errors="coerce")
    frame = frame.dropna(subset=["transaction_date"]).copy()
    frame["month"] = frame["transaction_date"].dt.to_period("M")
    frame["amount_value"] = pd.to_numeric(frame.get("amount", 0), errors="coerce").fillna(0.0)
    statuses = frame.get("transaction_status", pd.Series("", index=frame.index)).fillna("")
    classes = frame.get("transaction_class", pd.Series("", index=frame.index)).fillna("").astype(str).str.lower()
    income_flag = _boolean_values(frame.get("income_flag", pd.Series(False, index=frame.index)))
    income_flag = income_flag | classes.isin({"income", "salary"})
    amount = _positive_successful(frame["amount_value"], statuses)
    committed_flag = classes.isin({"subscription", "emi", "bnpl"})
    return pd.DataFrame(
        {
            "income": amount.where(income_flag, 0.0).to_numpy(),
            "committed": amount.where(committed_flag & ~income_flag, 0.0).to_numpy(),
            "variable": amount.where(~income_flag & ~committed_flag, 0.0).to_numpy(),
        },
        index=frame["month"],
    ).groupby(level=0).sum().sort_index()


def _feature_row(history: pd.DataFrame, raw_history: pd.DataFrame) -> dict[str, float]:
    six = history.tail(6)
    three = history.tail(3)
    net = history["income"] - history["committed"] - history["variable"]
    commitment_total = float(six["committed"].mean())
    income_mean = _safe_mean(six["income"])
    variable_mean = _safe_mean(six["variable"])
    classes = raw_history.get("transaction_class", pd.Series("", index=raw_history.index)).fillna("").astype(str).str.lower()
    amounts = pd.to_numeric(raw_history.get("amount", 0), errors="coerce").fillna(0.0)
    status = raw_history.get("transaction_status", pd.Series("", index=raw_history.index)).fillna("")
    successful = status.map(classify_transaction_status).eq(TransactionStatus.SUCCESSFUL)
    failed = status.map(classify_transaction_status).eq(TransactionStatus.FAILED)
    pending = status.map(classify_transaction_status).eq(TransactionStatus.PENDING)
    positive = amounts.gt(0)
    eligible = successful & positive
    subscription = float(amounts.where(eligible & classes.eq("subscription"), 0.0).sum() / max(six.shape[0], 1))
    emi = float(amounts.where(eligible & classes.isin({"emi", "loan"}), 0.0).sum() / max(six.shape[0], 1))
    bnpl = float(amounts.where(eligible & classes.eq("bnpl"), 0.0).sum() / max(six.shape[0], 1))
    recurring = subscription + emi + bnpl
    category_monthly = (
        raw_history.assign(amount_value=amounts.where(eligible, 0.0))
        .groupby(raw_history.get("category", pd.Series("", index=raw_history.index)).fillna("").astype(str).str.lower())["amount_value"]
        .sum()
    )
    category_values = category_monthly.to_numpy(dtype=float)
    last_three_commitments = float(three["committed"].mean())
    prior_three_commitments = float(six.head(3)["committed"].mean())
    row = {
        "previous_income": float(history.iloc[-1]["income"]),
        "income_3m": _safe_mean(three["income"]),
        "income_6m": _safe_mean(six["income"]),
        "income_trend": _slope(six["income"].tolist()),
        "income_volatility": _std(six["income"].tolist()),
        "income_stability": max(0.0, 1.0 - _std(six["income"].tolist()) / max(income_mean, 1.0)),
        "previous_committed": float(history.iloc[-1]["committed"]),
        "committed_3m": _safe_mean(three["committed"]),
        "committed_6m": commitment_total,
        "commitment_ratio": commitment_total / max(income_mean, 1.0),
        "commitment_count": float((six["committed"] > 0).sum()),
        "commitment_growth": last_three_commitments - prior_three_commitments,
        "subscription_burden": subscription,
        "emi_burden": emi,
        "bnpl_burden": bnpl,
        "recurring_payment_burden": recurring,
        "commitment_diversity": float(classes[classes.isin({"subscription", "emi", "bnpl"})].nunique()),
        "previous_variable": float(history.iloc[-1]["variable"]),
        "variable_3m": _safe_mean(three["variable"]),
        "variable_6m": _safe_mean(six["variable"]),
        "variable_trend": _slope(six["variable"].tolist()),
        "variable_volatility": _std(six["variable"].tolist()),
        "discretionary_spending": variable_mean,
        "category_growth": float(category_values.max() - category_values.min()) if len(category_values) else 0.0,
        "category_volatility": _std(category_values.tolist()),
        "previous_net_cash": float(net.iloc[-1]),
        "net_cash_3m": _safe_mean(net.tail(3)),
        "net_cash_6m": _safe_mean(net.tail(6)),
        "minimum_net_cash": float(net.min()) if len(net) else 0.0,
        "net_cash_volatility": _std(net.tolist()),
        "positive_cash_frequency": float((net > 0).mean()) if len(net) else 0.0,
        "negative_cash_frequency": float((net < 0).mean()) if len(net) else 0.0,
        "payment_success_rate": float(successful.mean()) if len(status) else 0.0,
        "failed_transaction_rate": float(failed.mean()) if len(status) else 0.0,
        "pending_transaction_rate": float(pending.mean()) if len(status) else 0.0,
        "payment_reliability": float(successful.sum() / max((successful | failed).sum(), 1)),
        "total_monthly_commitments": commitment_total,
        "active_recurring_count": float(classes[classes.isin({"subscription", "emi", "bnpl"})].nunique()),
        "commitment_burden": commitment_total / max(income_mean, 1.0),
        "commitment_change": last_three_commitments - prior_three_commitments,
    }
    # These five columns are historical Model 1-style forecasts at T.
    row.update(
        {
            "expected_income": _safe_mean(six["income"]),
            "expected_committed_expenses": _safe_mean(six["committed"].tail(3)),
            "expected_variable_expenses": _safe_mean(six["variable"]),
            "expected_total_expenses": _safe_mean(six["committed"].tail(3)) + _safe_mean(six["variable"]),
            "expected_net_cash": _safe_mean(six["income"]) - _safe_mean(six["committed"].tail(3)) - _safe_mean(six["variable"]),
        }
    )
    return row


def build_snapshots(transactions: pd.DataFrame) -> pd.DataFrame:
    required = {"user_id", "transaction_date", "amount", "transaction_class", "transaction_status"}
    missing = required - set(transactions.columns)
    if missing:
        raise ValueError(f"Missing transaction columns: {sorted(missing)}")
    frame = transactions.copy()
    frame["transaction_date"] = pd.to_datetime(frame["transaction_date"], errors="coerce")
    frame = frame.dropna(subset=["transaction_date"])
    frame["user_id"] = frame["user_id"].astype(str)
    frame["month"] = frame["transaction_date"].dt.to_period("M")
    rows: list[dict[str, Any]] = []
    for user_id, group in frame.groupby("user_id", sort=False):
        monthly = monthly_cashflow(group)
        if monthly.empty:
            continue
        full_index = pd.period_range(monthly.index.min(), monthly.index.max(), freq="M")
        monthly = monthly.reindex(full_index, fill_value=0.0)
        for position in range(5, len(monthly) - 1):
            history = monthly.iloc[: position + 1]
            future = monthly.iloc[position + 1]
            raw_history = group[group["month"] <= monthly.index[position]]
            row = _feature_row(history, raw_history)
            row.update(
                {
                    "user_id": str(user_id),
                    "feature_month": str(monthly.index[position]),
                    "outcome_month": str(monthly.index[position + 1]),
                    TARGET: int(float(future["income"] - future["committed"] - future["variable"]) < 0),
                }
            )
            rows.append(row)
    return pd.DataFrame(rows, columns=["user_id", "feature_month", "outcome_month", TARGET, *FEATURE_COLUMNS])


def baseline_predict(frame: pd.DataFrame) -> np.ndarray:
    buffer = frame["net_cash_6m"] - frame["net_cash_volatility"]
    burden = frame["commitment_ratio"] + frame["variable_volatility"] / frame["income_6m"].clip(lower=1.0)
    return ((buffer < 0) | (burden > 0.85)).astype(int).to_numpy()


def feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.loc[:, FEATURE_COLUMNS].astype(float)


def current_features(transactions: pd.DataFrame, forecast: Any | None = None) -> tuple[pd.DataFrame | None, str | None]:
    """Build the current cutoff row; forecast values are Model 1 features only."""
    monthly = monthly_cashflow(transactions)
    if monthly.empty or len(monthly) < 6:
        return None, None
    row = _feature_row(monthly, transactions)
    if forecast is not None and getattr(forecast, "forecast_available", False):
        row.update(
            {
                "expected_income": float(forecast.expected_income or 0.0),
                "expected_committed_expenses": float(forecast.expected_committed_expenses or 0.0),
                "expected_variable_expenses": float(forecast.expected_variable_expenses or 0.0),
                "expected_total_expenses": float(forecast.expected_total_expenses or 0.0),
                "expected_net_cash": float(forecast.expected_net_cash or 0.0),
            }
        )
    return pd.DataFrame([row], columns=FEATURE_COLUMNS), str(monthly.index.max() + 1)


@dataclass(frozen=True)
class SplitDefinition:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame


def temporal_split(frame: pd.DataFrame) -> SplitDefinition:
    periods = sorted(frame["feature_month"].unique())
    first = max(1, int(len(periods) * 0.70))
    second = max(first + 1, int(len(periods) * 0.85))
    return SplitDefinition(
        frame[frame["feature_month"].isin(periods[:first])].copy(),
        frame[frame["feature_month"].isin(periods[first:second])].copy(),
        frame[frame["feature_month"].isin(periods[second:])].copy(),
    )

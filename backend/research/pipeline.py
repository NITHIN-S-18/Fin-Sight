"""FinSight Research Shortfall Pipeline.

Controlled, isolated feature extraction and snapshot builder for
Model A (Baseline: 27 conventional financial features) and
Model B (Commitment-Aware: 41 features = 27 baseline + 14 commitment-aware).

This module corrects the following Phase 1 audit defects:
1. Replaces lifetime transaction sums with consistent 6-month observation windows
   for commitment burdens (subscription, emi, bnpl, recurring).
2. Eliminates 4 redundant aliases (total_monthly_commitments, active_recurring_count,
   commitment_burden, commitment_change).
3. Restricts category dispersion metrics to the 6-month observation window.
4. Preserves exact chronological splitting and next-month target semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from app.ml.cashflow_forecast import _boolean_values, _positive_successful
from app.services.financial_rules import TransactionStatus, classify_transaction_status

TARGET = "shortfall"

MODEL_A_FEATURES: tuple[str, ...] = (
    # Income dynamics (6)
    "previous_income",
    "income_3m",
    "income_6m",
    "income_trend",
    "income_volatility",
    "income_stability",
    # Variable spending dynamics (8)
    "previous_variable",
    "variable_3m",
    "variable_6m",
    "variable_trend",
    "variable_volatility",
    "discretionary_spending",
    "category_growth",
    "category_volatility",
    # Cash-flow history (7)
    "previous_net_cash",
    "net_cash_3m",
    "net_cash_6m",
    "minimum_net_cash",
    "net_cash_volatility",
    "positive_cash_frequency",
    "negative_cash_frequency",
    # Payment execution & reliability (4)
    "payment_success_rate",
    "failed_transaction_rate",
    "pending_transaction_rate",
    "payment_reliability",
    # Baseline expected projections (2)
    "expected_income",
    "expected_variable_expenses",
)

COMMITMENT_FEATURES: tuple[str, ...] = (
    # Commitment history & ratios (6)
    "previous_committed",
    "committed_3m",
    "committed_6m",
    "commitment_ratio",
    "commitment_count",
    "commitment_growth",
    # Granular commitment burdens (4) - corrected 6-month window
    "subscription_burden",
    "emi_burden",
    "bnpl_burden",
    "recurring_payment_burden",
    # Diversity (1)
    "commitment_diversity",
    # Commitment-aware projections (3)
    "expected_committed_expenses",
    "expected_total_expenses",
    "expected_net_cash",
)

MODEL_B_FEATURES: tuple[str, ...] = MODEL_A_FEATURES + COMMITMENT_FEATURES


def _slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(np.polyfit(np.arange(len(values)), values, 1)[0])


def _std(values: list[float]) -> float:
    return float(np.std(values, ddof=0)) if values else 0.0


def _safe_mean(values: pd.Series | list[float]) -> float:
    if isinstance(values, pd.Series):
        return float(values.mean()) if len(values) else 0.0
    return float(np.mean(values)) if values else 0.0


def monthly_cashflow(transactions: pd.DataFrame) -> pd.DataFrame:
    """Aggregate transactions into monthly income, committed, and variable cashflow."""
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


def extract_feature_row(history: pd.DataFrame, window_raw_transactions: pd.DataFrame) -> dict[str, float]:
    """Extract features for cutoff month T using strictly the 6-month historical window [T-5, T]."""
    six = history.tail(6)
    three = history.tail(3)
    six_net = six["income"] - six["committed"] - six["variable"]
    net_lifetime = history["income"] - history["committed"] - history["variable"]

    income_mean = _safe_mean(six["income"])
    variable_mean = _safe_mean(six["variable"])
    commitment_total = float(six["committed"].mean())

    classes = window_raw_transactions.get("transaction_class", pd.Series("", index=window_raw_transactions.index)).fillna("").astype(str).str.lower()
    amounts = pd.to_numeric(window_raw_transactions.get("amount", 0), errors="coerce").fillna(0.0)
    status = window_raw_transactions.get("transaction_status", pd.Series("", index=window_raw_transactions.index)).fillna("")

    successful = status.map(classify_transaction_status).eq(TransactionStatus.SUCCESSFUL)
    failed = status.map(classify_transaction_status).eq(TransactionStatus.FAILED)
    pending = status.map(classify_transaction_status).eq(TransactionStatus.PENDING)
    positive = amounts.gt(0)
    eligible = successful & positive

    window_months_count = max(float(len(six)), 1.0)
    subscription = float(amounts.where(eligible & classes.eq("subscription"), 0.0).sum() / window_months_count)
    emi = float(amounts.where(eligible & classes.isin({"emi", "loan"}), 0.0).sum() / window_months_count)
    bnpl = float(amounts.where(eligible & classes.eq("bnpl"), 0.0).sum() / window_months_count)
    recurring = subscription + emi + bnpl

    category_grouped = (
        window_raw_transactions.assign(amount_value=amounts.where(eligible, 0.0))
        .groupby(window_raw_transactions.get("category", pd.Series("", index=window_raw_transactions.index)).fillna("").astype(str).str.lower())["amount_value"]
        .sum()
    )
    category_values = category_grouped.to_numpy(dtype=float)

    last_three_commitments = float(three["committed"].mean())
    prior_three_commitments = float(six.head(3)["committed"].mean())

    # Model A Features (27)
    row: dict[str, float] = {
        "previous_income": float(history.iloc[-1]["income"]),
        "income_3m": _safe_mean(three["income"]),
        "income_6m": income_mean,
        "income_trend": _slope(six["income"].tolist()),
        "income_volatility": _std(six["income"].tolist()),
        "income_stability": max(0.0, 1.0 - _std(six["income"].tolist()) / max(income_mean, 1.0)),
        "previous_variable": float(history.iloc[-1]["variable"]),
        "variable_3m": _safe_mean(three["variable"]),
        "variable_6m": variable_mean,
        "variable_trend": _slope(six["variable"].tolist()),
        "variable_volatility": _std(six["variable"].tolist()),
        "discretionary_spending": variable_mean,
        "category_growth": float(category_values.max() - category_values.min()) if len(category_values) else 0.0,
        "category_volatility": _std(category_values.tolist()),
        "previous_net_cash": float(net_lifetime.iloc[-1]),
        "net_cash_3m": _safe_mean(six_net.tail(3)),
        "net_cash_6m": _safe_mean(six_net),
        "minimum_net_cash": float(six_net.min()) if len(six_net) else 0.0,
        "net_cash_volatility": _std(six_net.tolist()),
        "positive_cash_frequency": float((six_net > 0).mean()) if len(six_net) else 0.0,
        "negative_cash_frequency": float((six_net < 0).mean()) if len(six_net) else 0.0,
        "payment_success_rate": float(successful.mean()) if len(status) else 0.0,
        "failed_transaction_rate": float(failed.mean()) if len(status) else 0.0,
        "pending_transaction_rate": float(pending.mean()) if len(status) else 0.0,
        "payment_reliability": float(successful.sum() / max((successful | failed).sum(), 1)),
        "expected_income": income_mean,
        "expected_variable_expenses": variable_mean,
    }

    # Model B Features (14 additional)
    row.update(
        {
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
            "expected_committed_expenses": _safe_mean(three["committed"]),
            "expected_total_expenses": _safe_mean(three["committed"]) + variable_mean,
            "expected_net_cash": income_mean - _safe_mean(three["committed"]) - variable_mean,
        }
    )
    return row


def build_research_snapshots(transactions: pd.DataFrame) -> pd.DataFrame:
    """Build controlled monthly modeling snapshots with verified next-month target alignment."""
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
    all_columns = ["user_id", "feature_month", "outcome_month", TARGET, *MODEL_B_FEATURES]

    for user_id, group in frame.groupby("user_id", sort=False):
        monthly = monthly_cashflow(group)
        if monthly.empty:
            continue
        full_index = pd.period_range(monthly.index.min(), monthly.index.max(), freq="M")
        monthly = monthly.reindex(full_index, fill_value=0.0)

        for position in range(5, len(monthly) - 1):
            history = monthly.iloc[: position + 1]
            future = monthly.iloc[position + 1]

            current_month = monthly.index[position]
            start_window_month = monthly.index[position - 5]
            window_raw = group[(group["month"] <= current_month) & (group["month"] >= start_window_month)]

            row = extract_feature_row(history, window_raw)
            row.update(
                {
                    "user_id": str(user_id),
                    "feature_month": str(current_month),
                    "outcome_month": str(monthly.index[position + 1]),
                    TARGET: int(float(future["income"] - future["committed"] - future["variable"]) < 0),
                }
            )
            rows.append(row)

    return pd.DataFrame(rows, columns=all_columns)


@dataclass(frozen=True)
class ResearchSplit:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame


def temporal_split(frame: pd.DataFrame) -> ResearchSplit:
    """Chronological split: 70% train, 15% validation, 15% test periods."""
    periods = sorted(frame["feature_month"].unique())
    train_end = max(1, int(len(periods) * 0.70))
    validation_end = max(train_end + 1, int(len(periods) * 0.85))
    return ResearchSplit(
        train=frame[frame["feature_month"].isin(periods[:train_end])].copy(),
        validation=frame[frame["feature_month"].isin(periods[train_end:validation_end])].copy(),
        test=frame[frame["feature_month"].isin(periods[validation_end:])].copy(),
    )

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

TARGET_CLASSES = ("ACTIVE", "MODERATE", "UNDER_UTILIZED")
FEATURE_COLUMNS = (
    "payment_count",
    "successful_payment_count",
    "failed_payment_count",
    "payment_success_rate",
    "average_payment_amount",
    "payment_amount_volatility",
    "amount_consistency",
    "amount_trend",
    "days_since_last_payment",
    "mean_payment_gap",
    "longest_payment_gap",
    "recurring_interval_consistency",
    "observed_billing_cycles",
    "merchant_continuity",
    "merchant_stability",
    "category_consistency",
    "monthly_equivalent_amount",
    "subscription_age_months",
    "amount_change_count",
    "autopay_signal",
    "total_active_subscriptions",
    "total_monthly_commitments",
    "subscription_burden_ratio",
    "discretionary_spending",
    "income_stability",
    "commitment_ratio",
)


def _text(value: Any) -> str:
    return "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value).strip()


def _successful(frame: pd.DataFrame) -> pd.Series:
    return frame["transaction_status"].fillna("").astype(str).str.lower().isin(
        {"success", "successful", "succeeded", "completed", "paid", "settled"}
    )


def _frequency_multiplier(value: Any) -> float:
    return {
        "weekly": 52 / 12,
        "biweekly": 26 / 12,
        "fortnightly": 26 / 12,
        "monthly": 1.0,
        "quarterly": 1 / 3,
        "semiannual": 1 / 6,
        "annual": 1 / 12,
        "yearly": 1 / 12,
    }.get(_text(value).lower(), 1.0)


def _slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(np.polyfit(np.arange(len(values)), values, 1)[0])


def _features(history: pd.DataFrame, all_history: pd.DataFrame, cutoff: pd.Period) -> dict[str, float]:
    rows = history.copy()
    rows["amount"] = pd.to_numeric(rows["amount"], errors="coerce").fillna(0.0)
    rows["transaction_date"] = pd.to_datetime(rows["transaction_date"], errors="coerce")
    success = _successful(rows)
    positive = rows["amount"].gt(0)
    paid = rows.loc[success & positive].sort_values("transaction_date")
    amounts = paid["amount"].tolist()
    dates = paid["transaction_date"].dt.date.tolist()
    intervals = [(later - earlier).days for earlier, later in zip(dates, dates[1:])]
    mean_amount = float(np.mean(amounts)) if amounts else 0.0
    std_amount = float(np.std(amounts)) if amounts else 0.0
    payment_months = paid["transaction_date"].dt.to_period("M") if not paid.empty else pd.Series(dtype="period[M]")
    cycles = int(payment_months.nunique()) if len(payment_months) else 0
    last_payment = paid["transaction_date"].max() if not paid.empty else pd.Timestamp(cutoff.end_time)
    days_since = max((pd.Timestamp(cutoff.end_time).date() - last_payment.date()).days, 0)
    user_rows = all_history.copy()
    user_rows["amount"] = pd.to_numeric(user_rows["amount"], errors="coerce").fillna(0.0)
    user_rows["class"] = user_rows.get("transaction_class", "").fillna("").astype(str).str.lower()
    user_rows["income"] = user_rows.get("income_flag", False).fillna(False).astype(str).str.lower().isin(
        {"yes", "true", "1"}
    )
    user_success = _successful(user_rows)
    commitments = user_rows.loc[
        user_success & user_rows["amount"].gt(0) & user_rows["class"].isin({"subscription", "emi", "bnpl"})
    ]
    income = user_rows.loc[user_success & user_rows["income"] & user_rows["amount"].gt(0)]
    discretionary = user_rows.loc[
        user_success
        & user_rows["amount"].gt(0)
        & ~user_rows["income"]
        & ~user_rows["class"].isin({"subscription", "emi", "bnpl"})
    ]
    income_monthly = income.groupby(income["transaction_date"].dt.to_period("M"))["amount"].sum() if not income.empty else pd.Series(dtype=float)
    income_mean = float(income_monthly.mean()) if len(income_monthly) else 0.0
    commitment_monthly = float(commitments["amount"].sum() / max(commitments["transaction_date"].dt.to_period("M").nunique(), 1)) if not commitments.empty else 0.0
    categories = rows.get("category", pd.Series("", index=rows.index)).fillna("").astype(str).str.lower()
    merchants = rows.get("merchant_name", pd.Series("", index=rows.index)).fillna("").astype(str).str.lower()
    monthly_amount = mean_amount * _frequency_multiplier(rows.get("frequency", pd.Series(["monthly"])).iloc[0] if not rows.empty else "monthly")
    return {
        "payment_count": float(len(rows)),
        "successful_payment_count": float(success.sum()),
        "failed_payment_count": float((~success).sum()),
        "payment_success_rate": float(success.mean()) if len(rows) else 0.0,
        "average_payment_amount": mean_amount,
        "payment_amount_volatility": std_amount,
        "amount_consistency": max(0.0, 1.0 - std_amount / max(mean_amount, 1.0)),
        "amount_trend": _slope(amounts),
        "days_since_last_payment": float(days_since),
        "mean_payment_gap": float(np.mean(intervals)) if intervals else 0.0,
        "longest_payment_gap": float(max(intervals)) if intervals else 0.0,
        "recurring_interval_consistency": max(0.0, 1.0 - (float(np.std(intervals)) / max(float(np.mean(intervals)), 1.0))) if intervals else 0.0,
        "observed_billing_cycles": float(cycles),
        "merchant_continuity": 1.0 if merchants.nunique() <= 1 else 0.0,
        "merchant_stability": 1.0 if merchants.nunique() <= 1 else 1.0 / merchants.nunique(),
        "category_consistency": 1.0 if categories.nunique() <= 1 else 1.0 / categories.nunique(),
        "monthly_equivalent_amount": monthly_amount,
        "subscription_age_months": float(max((cutoff - rows["transaction_date"].dt.to_period("M").min()).n, 0)) if not rows.empty else 0.0,
        "amount_change_count": float(sum(abs(b - a) > max(abs(a) * 0.1, 1.0) for a, b in zip(amounts, amounts[1:]))),
        "autopay_signal": float(rows.get("autopay_flag", pd.Series(False, index=rows.index)).fillna(False).astype(str).str.lower().isin({"yes", "true", "1"}).mean()) if len(rows) else 0.0,
        "total_active_subscriptions": float(user_rows.loc[user_rows["class"].eq("subscription"), "merchant_name"].nunique()),
        "total_monthly_commitments": commitment_monthly,
        "subscription_burden_ratio": monthly_amount / max(income_mean, 1.0),
        "discretionary_spending": float(discretionary["amount"].sum() / max(discretionary["transaction_date"].dt.to_period("M").nunique(), 1)) if not discretionary.empty else 0.0,
        "income_stability": max(0.0, 1.0 - float(income_monthly.std(ddof=0)) / max(income_mean, 1.0)) if len(income_monthly) else 0.0,
        "commitment_ratio": commitment_monthly / max(income_mean, 1.0),
    }


def target_from_future(future: pd.DataFrame, window_months: int = 3) -> str:
    if future.empty:
        return "UNDER_UTILIZED"
    future = future.copy()
    future["transaction_date"] = pd.to_datetime(future["transaction_date"], errors="coerce")
    successful = _successful(future) & future["amount"].gt(0)
    active_months = future.loc[successful, "transaction_date"].dt.to_period("M").nunique()
    if active_months >= window_months:
        return "ACTIVE"
    if active_months >= 1:
        return "MODERATE"
    return "UNDER_UTILIZED"


def build_observation_snapshots(transactions: pd.DataFrame) -> pd.DataFrame:
    required = {"user_id", "merchant_name", "transaction_date", "amount", "transaction_class", "transaction_status"}
    missing = required - set(transactions.columns)
    if missing:
        raise ValueError(f"Missing transaction columns: {sorted(missing)}")
    frame = transactions.copy()
    frame["transaction_date"] = pd.to_datetime(frame["transaction_date"], errors="coerce")
    frame = frame.dropna(subset=["transaction_date"])
    frame = frame[frame["transaction_class"].fillna("").astype(str).str.lower().eq("subscription")]
    frame = frame[frame["amount"].map(lambda value: float(value) if pd.notna(value) else 0.0).abs().gt(0)]
    frame["month"] = frame["transaction_date"].dt.to_period("M")
    if frame.empty:
        return pd.DataFrame(columns=["user_id", "merchant_name", "observation_month", "target", *FEATURE_COLUMNS])
    global_end = frame["month"].max()
    user_groups = {user_id: user_frame for user_id, user_frame in frame.groupby("user_id", sort=False)}
    samples: list[dict[str, Any]] = []
    for (user_id, merchant), group in frame.groupby(["user_id", "merchant_name"], dropna=False):
        first_month = group["month"].min()
        cutoff = first_month + 3
        while cutoff + 3 <= global_end:
            history = group[group["month"] <= cutoff]
            if history["month"].nunique() >= 3:
                user_history = user_groups[user_id]
                user_history = user_history[user_history["month"] <= cutoff]
                future = group[(group["month"] > cutoff) & (group["month"] <= cutoff + 3)]
                row = {
                    "user_id": str(user_id),
                    "merchant_name": str(merchant),
                    "observation_month": str(cutoff),
                    "target": target_from_future(future),
                }
                row.update(_features(history, user_history, cutoff))
                samples.append(row)
            cutoff += 3
    return pd.DataFrame(samples)


def baseline_predict(frame: pd.DataFrame) -> np.ndarray:
    return np.where(
        (frame["payment_success_rate"] >= 0.8)
        & (frame["longest_payment_gap"] <= 45)
        & (frame["amount_consistency"] >= 0.8),
        "ACTIVE",
        np.where(frame["days_since_last_payment"] <= 75, "MODERATE", "UNDER_UTILIZED"),
    )


def feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.loc[:, FEATURE_COLUMNS].astype(float)


def features_for_subscription(
    transactions: pd.DataFrame,
    merchant_name: str,
    cutoff: pd.Period | None = None,
) -> pd.DataFrame:
    frame = transactions.copy()
    frame["transaction_date"] = pd.to_datetime(frame["transaction_date"], errors="coerce")
    frame["month"] = frame["transaction_date"].dt.to_period("M")
    frame = frame[
        frame["transaction_class"].fillna("").astype(str).str.lower().eq("subscription")
        & frame["merchant_name"].fillna("").astype(str).eq(str(merchant_name))
    ]
    if frame.empty:
        return pd.DataFrame(columns=FEATURE_COLUMNS)
    cutoff = cutoff or frame["month"].max()
    history = frame[frame["month"] <= cutoff]
    return pd.DataFrame([_features(history, history, cutoff)], columns=FEATURE_COLUMNS)


@dataclass(frozen=True)
class SplitDefinition:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame


def temporal_split(frame: pd.DataFrame) -> SplitDefinition:
    periods = sorted(frame["observation_month"].unique())
    first = max(1, int(len(periods) * 0.70))
    second = max(first + 1, int(len(periods) * 0.85))
    return SplitDefinition(
        frame[frame["observation_month"].isin(periods[:first])].copy(),
        frame[frame["observation_month"].isin(periods[first:second])].copy(),
        frame[frame["observation_month"].isin(periods[second:])].copy(),
    )

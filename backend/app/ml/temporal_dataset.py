from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import sqrt
from typing import Any

import pandas as pd

from app.ml.base import FinancialIntelligenceSnapshot
from app.ml.feature_engineering import FeatureEngineeringPipeline
from app.ml.utils import coerce_float, normalize_text, safe_divide, truthy


@dataclass(frozen=True)
class TemporalDataset:
    features: pd.DataFrame
    distress_target: pd.Series
    exposure_target: pd.Series
    metadata: dict[str, Any]


class TemporalDatasetBuilder:
    """Build leakage-safe monthly T -> T+1 reference examples."""

    horizon_months = 1
    dataset_version = "reference-temporal-v1"

    def __init__(self, feature_pipeline: FeatureEngineeringPipeline | None = None) -> None:
        self._feature_pipeline = feature_pipeline or FeatureEngineeringPipeline()

    def build(
        self,
        user_records: list[dict[str, Any]],
        transactions: pd.DataFrame,
    ) -> TemporalDataset:
        frame = transactions.copy()
        if frame.empty:
            raise ValueError("Temporal training requires reference transactions.")
        frame["transaction_date"] = pd.to_datetime(frame["transaction_date"], errors="coerce")
        frame = frame.dropna(subset=["transaction_date"]).copy()
        frame["month"] = frame["transaction_date"].dt.to_period("M")
        valid_users = {str(record.get("user_id")): record for record in user_records}
        frame = frame[frame["user_id"].astype(str).isin(valid_users)].copy()
        frame = frame.sort_values(["user_id", "transaction_date"]).reset_index(drop=True)

        features, targets, exposure_target = self._build_aggregated_examples(frame)
        if features.empty:
            raise ValueError("Reference transactions do not contain adjacent monthly examples.")

        features.index = pd.MultiIndex.from_arrays(
            [
                features.index.get_level_values("user_id"),
                features.index.get_level_values(1).astype(str),
            ],
            names=["user_id", "snapshot_month"],
        )
        targets.index = features.index
        exposure_target.index = features.index
        example_users = features.index.get_level_values("user_id").tolist()
        example_months = features.index.get_level_values("snapshot_month").tolist()
        months = sorted(example_months)
        fingerprint = sha256(
            pd.util.hash_pandas_object(
                frame.drop(columns=["month"], errors="ignore"), index=True
            ).values.tobytes()
        ).hexdigest()
        status_distribution = (
            frame["transaction_status"].map(normalize_text).str.lower().value_counts().to_dict()
            if "transaction_status" in frame.columns
            else {}
        )
        metadata = {
            "dataset_version": self.dataset_version,
            "forecast_horizon_months": self.horizon_months,
            "target_definitions": {
                "future_distress_event": (
                    "1 when the next calendar month contains at least one failed, "
                    "declined, or rejected transaction; otherwise 0."
                ),
                "future_exposure": (
                    "Successful next-month commitment amounts divided by successful "
                    "next-month positive income amounts, multiplied by 100."
                ),
            },
            "snapshot_count": len(features),
            "user_count": len(set(example_users)),
            "snapshot_period": [months[0], months[-1]],
            "transaction_count": int(len(frame)),
            "transaction_date_range": [
                frame["transaction_date"].min().date().isoformat(),
                frame["transaction_date"].max().date().isoformat(),
            ],
            "status_distribution": {str(key): int(value) for key, value in status_distribution.items()},
            "duplicate_transaction_count": int(frame.duplicated().sum()),
            "users_with_sufficient_history": int(len(set(example_users))),
            "exposure_target_coverage": round(float(exposure_target.notna().mean()), 4),
            "target_distribution": {
                "future_distress_event": {
                    "0": int((targets == 0).sum()),
                    "1": int((targets == 1).sum()),
                },
                "future_exposure": {
                    "observed": int(exposure_target.notna().sum()),
                    "missing_no_positive_income": int(exposure_target.isna().sum()),
                },
            },
            "dataset_fingerprint": fingerprint,
            "examples": [
                {
                    "user_id": user_id,
                    "snapshot_month": month,
                    "outcome_month": str(pd.Period(month) + 1),
                }
                for user_id, month in zip(example_users[:10], example_months[:10])
            ],
        }
        return TemporalDataset(features, targets, exposure_target, metadata)

    @staticmethod
    def _build_aggregated_examples(
        frame: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
        """Build historical features with cumulative monthly aggregates."""
        work = frame.copy()
        work["user_id"] = work["user_id"].astype(str)
        work["amount_numeric"] = pd.to_numeric(work.get("amount", 0), errors="coerce").fillna(0.0)
        work["amount_positive"] = work["amount_numeric"].clip(lower=0.0)
        status = work.get("transaction_status", pd.Series("", index=work.index)).map(normalize_text).str.lower()
        transaction_class = work.get("transaction_class", pd.Series("", index=work.index)).map(normalize_text).str.lower()
        income_flag = work.get("income_flag", pd.Series("", index=work.index)).map(truthy)
        income_flag = income_flag | transaction_class.isin({"income", "salary"})
        success = status.isin({"success", "succeeded", "successful", "completed", "paid", "settled"})
        valid = status.ne("")
        commitment = transaction_class.isin({"subscription", "emi", "bnpl"})
        nonincome = ~income_flag
        autopay = work.get("autopay_flag", pd.Series("", index=work.index)).map(truthy)
        distress_status = status.isin({"failed", "declined", "rejected"})

        work["_valid"] = valid.astype("int8")
        work["_success"] = success.astype("int8")
        work["_income_success"] = (success & income_flag).astype("int8")
        work["_income_success_amount"] = work["amount_positive"].where(success & income_flag, 0.0)
        work["_income_all_amount"] = work["amount_numeric"].where(income_flag, 0.0)
        work["_commitment_amount"] = work["amount_positive"].where(commitment, 0.0)
        work["_success_commitment_amount"] = work["amount_positive"].where(success & commitment, 0.0)
        work["_success_variable_amount"] = work["amount_positive"].where(success & nonincome, 0.0)
        work["_autopay_commitment"] = (autopay & commitment).astype("int8")
        work["_distress"] = distress_status.astype("int8")
        work["_nonincome_count"] = nonincome.astype("int8")
        work["_nonincome_sum"] = work["amount_numeric"].where(nonincome, 0.0)
        work["_nonincome_sum_sq"] = work["_nonincome_sum"] ** 2
        work["_subscription_count"] = (commitment & transaction_class.eq("subscription")).astype("int8")
        work["_emi_count"] = (commitment & transaction_class.eq("emi")).astype("int8")
        work["_bnpl_count"] = (commitment & transaction_class.eq("bnpl")).astype("int8")
        work["_subscription_amount"] = work["amount_positive"].where(transaction_class.eq("subscription"), 0.0)
        work["_emi_amount"] = work["amount_positive"].where(transaction_class.eq("emi"), 0.0)
        work["_bnpl_amount"] = work["amount_positive"].where(transaction_class.eq("bnpl"), 0.0)

        grouped = work.groupby(["user_id", "month"], sort=True)
        monthly = grouped[
            [
                "_valid", "_success", "_income_success", "_income_success_amount",
                "_income_all_amount", "_commitment_amount", "_success_commitment_amount",
                "_success_variable_amount", "_autopay_commitment", "_distress",
                "_nonincome_count", "_nonincome_sum", "_nonincome_sum_sq",
                "_subscription_count", "_emi_count", "_bnpl_count",
                "_subscription_amount", "_emi_amount", "_bnpl_amount",
            ]
        ].sum()
        monthly["_income_all_present"] = (
            grouped["_income_all_amount"]
            .agg(lambda values: int((values != 0).any()))
            .reindex(monthly.index)
        )
        monthly = monthly.sort_index()

        cumulative_columns = [column for column in monthly.columns if column != "_distress"]
        cumulative = monthly.groupby(level=0, sort=False)[cumulative_columns].cumsum()
        monthly_income = monthly["_income_all_amount"]
        cumulative["_monthly_income_sum"] = monthly_income.groupby(level=0, sort=False).cumsum()
        cumulative["_monthly_income_sum_sq"] = (monthly_income ** 2).groupby(level=0, sort=False).cumsum()
        cumulative["_monthly_income_count"] = monthly["_income_all_present"].groupby(level=0, sort=False).cumsum()

        next_monthly = monthly.groupby(level=0, sort=False).shift(-1)
        next_index = pd.MultiIndex.from_arrays(
            [monthly.index.get_level_values(0), monthly.index.get_level_values(1) + 1],
            names=monthly.index.names,
        )
        adjacent = next_index.isin(monthly.index)
        current = cumulative.loc[adjacent].copy()
        future = next_monthly.loc[adjacent].copy()
        current.index = monthly.index[adjacent]
        future.index = current.index
        if current.empty:
            feature_columns = [
                "commitment_ratio", "subscription_density", "emi_burden_ratio",
                "bnpl_dependency", "exposure_utilization", "financial_flexibility",
                "commitment_diversity", "payment_reliability", "autopay_coverage",
                "spending_variance", "income_stability",
            ]
            empty_index = current.index
            return (
                pd.DataFrame(columns=feature_columns, index=empty_index),
                pd.Series(dtype="int64", index=empty_index, name="future_distress_event"),
                pd.Series(dtype="float64", index=empty_index, name="future_exposure"),
            )

        capacity = current["_income_success_amount"] / current["_income_success"].replace(0, pd.NA)
        capacity = capacity.fillna(0.0)
        commitment = current["_commitment_amount"]
        commitment_total = current["_success_commitment_amount"]
        variable_total = (current["_success_variable_amount"] - commitment_total).clip(lower=0.0)
        denominator = current["_commitment_amount"].replace(0, pd.NA)
        nonincome_count = current["_nonincome_count"]
        mean_spend = current["_nonincome_sum"] / nonincome_count.replace(0, pd.NA)
        variance = (
            current["_nonincome_sum_sq"] / nonincome_count.replace(0, pd.NA) - mean_spend ** 2
        ).clip(lower=0.0)
        spending_variance = pd.Series(
            variance.pow(0.5).to_numpy()
            / mean_spend.abs().replace(0, float("nan")).to_numpy(),
            index=current.index,
        )
        monthly_count = current["_monthly_income_count"]
        mean_income = current["_monthly_income_sum"] / monthly_count.replace(0, pd.NA)
        income_variance = (
            current["_monthly_income_sum_sq"] / monthly_count.replace(0, pd.NA) - mean_income ** 2
        ).clip(lower=0.0)
        income_stability = pd.Series(
            1.0
            / (
                1.0
                + income_variance.pow(0.5).to_numpy()
                / mean_income.abs().replace(0, float("nan")).to_numpy()
            ),
            index=current.index,
        )

        total_active = current["_subscription_count"] + current["_emi_count"] + current["_bnpl_count"]
        features = pd.DataFrame(
            {
                "commitment_ratio": (commitment / capacity.replace(0, pd.NA)).fillna(0.0),
                "subscription_density": (current["_subscription_count"] / total_active.replace(0, pd.NA)).fillna(0.0),
                "emi_burden_ratio": (current["_emi_amount"] / denominator).fillna(0.0),
                "bnpl_dependency": (current["_bnpl_amount"] / denominator).fillna(0.0),
                "exposure_utilization": (commitment / capacity.replace(0, pd.NA)).fillna(0.0),
                "financial_flexibility": (
                    (current["_income_success_amount"] - commitment_total - variable_total)
                    / capacity.replace(0, pd.NA)
                ).clip(lower=0.0, upper=1.0).fillna(0.0),
                "commitment_diversity": (
                    current["_subscription_count"].gt(0).astype(int)
                    + current["_emi_count"].gt(0).astype(int)
                    + current["_bnpl_count"].gt(0).astype(int)
                ) / 3.0,
                "payment_reliability": (current["_success"] / current["_valid"].replace(0, pd.NA)).fillna(0.0),
                "autopay_coverage": (current["_autopay_commitment"] / total_active.replace(0, pd.NA)).fillna(0.0),
                "spending_variance": spending_variance.fillna(0.0),
                "income_stability": income_stability.fillna(0.0),
            },
            index=current.index,
        ).astype(float).fillna(0.0).round(4)
        future_income = future["_income_success_amount"]
        future_exposure = pd.to_numeric(
            future["_success_commitment_amount"] * 100.0 / future_income.replace(0, float("nan")),
            errors="coerce",
        ).round(4)
        targets = pd.Series(future["_distress"].gt(0).astype(int).to_numpy(), index=current.index, name="future_distress_event")
        exposure_target = pd.Series(future_exposure.to_numpy(), index=current.index, name="future_exposure")
        return features, targets, exposure_target

    @staticmethod
    def _valid_rows(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame
        if "transaction_status" not in frame.columns:
            return frame
        valid = frame["transaction_status"].map(normalize_text).str.lower().ne("")
        return frame.loc[valid].copy()

    @classmethod
    def _successful_rows(cls, frame: pd.DataFrame) -> pd.DataFrame:
        frame = cls._valid_rows(frame)
        if "transaction_status" not in frame.columns:
            return frame
        return frame[
            frame["transaction_status"].map(normalize_text).str.lower().isin(
                {"success", "succeeded", "successful", "completed", "paid", "settled"}
            )
        ].copy()

    @classmethod
    def _profile_at_snapshot(
        cls, history: pd.DataFrame, user_id: str, user_record: dict[str, Any]
    ) -> dict[str, Any]:
        successful = cls._successful_rows(history)
        current_month = history["month"].max()
        monthly = successful[successful["month"] == current_month]
        income = cls._income(monthly)
        commitment = cls._commitments(monthly)
        monthly_incomes = [
            cls._income(group)
            for _, group in successful.groupby("month")
            if cls._income(group) > 0
        ]
        # A static reference profile may be calculated from the complete
        # ledger. Falling back to it here would leak future information.
        capacity = sum(monthly_incomes) / len(monthly_incomes) if monthly_incomes else 0.0
        profile = {
            "monthly_financial_capacity": capacity,
            "monthly_commitments": commitment,
            "exposure_score": safe_divide(commitment * 100.0, capacity, 0.0),
            "active_subscriptions": cls._active_count(history, {"subscription"}),
            "active_emis": cls._active_count(history, {"emi"}),
            "active_bnpl": cls._active_count(history, {"bnpl"}),
            "total_active_commitments": cls._active_count(history, {"subscription", "emi", "bnpl"}),
            "transaction_success_rate": safe_divide(len(successful), len(cls._valid_rows(history)), 0.0),
            "financial_health": "Unknown",
            "user_id": user_id,
        }
        return profile

    @classmethod
    def _future_distress_event(cls, outcome: pd.DataFrame) -> int:
        if "transaction_status" not in outcome.columns:
            return 0
        return int(
            outcome["transaction_status"].map(normalize_text).str.lower().isin(
                {"failed", "declined", "rejected"}
            ).any()
        )

    @classmethod
    def _monthly_exposure(cls, outcome: pd.DataFrame, profile: dict[str, Any]) -> float | None:
        successful = cls._successful_rows(outcome)
        income = cls._income(successful)
        commitments = cls._commitments(successful)
        if income <= 0:
            return None
        return round(safe_divide(commitments * 100.0, income, 0.0), 4)

    @staticmethod
    def _income(frame: pd.DataFrame) -> float:
        if frame.empty or "amount" not in frame.columns:
            return 0.0
        if "income_flag" in frame.columns:
            mask = frame["income_flag"].map(truthy)
        else:
            mask = frame.get("transaction_class", pd.Series(index=frame.index)).map(
                lambda value: normalize_text(value).lower() in {"income", "salary"}
            )
        return float(frame.loc[mask, "amount"].map(coerce_float).clip(lower=0).sum())

    @staticmethod
    def _commitments(frame: pd.DataFrame) -> float:
        if frame.empty or "amount" not in frame.columns:
            return 0.0
        if "transaction_class" in frame.columns:
            mask = frame["transaction_class"].map(normalize_text).str.lower().isin(
                {"subscription", "emi", "bnpl"}
            )
        else:
            mask = pd.Series(False, index=frame.index)
        return float(frame.loc[mask, "amount"].map(coerce_float).clip(lower=0).sum())

    @staticmethod
    def _active_count(frame: pd.DataFrame, classes: set[str]) -> int:
        if frame.empty or "transaction_class" not in frame.columns:
            return 0
        values = frame["transaction_class"].map(normalize_text).str.lower()
        return int(values.isin(classes).sum())

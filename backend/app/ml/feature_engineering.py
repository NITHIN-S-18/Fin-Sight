from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

import pandas as pd

from app.ml.base import FeatureDefinition, FeatureFrame, FinancialIntelligenceSnapshot
from app.ml.config import get_ml_config
from app.ml.utils import clamp, coerce_float, coefficient_of_variation, normalize_text, safe_divide, truthy
from app.services.dataset_service import DatasetService


FeatureCalculator = Callable[[FinancialIntelligenceSnapshot], Any]


@dataclass(frozen=True)
class RegisteredFeature:
    definition: FeatureDefinition
    calculator: FeatureCalculator


class FeatureEngineeringPipeline:
    def __init__(self, features: Sequence[RegisteredFeature] | None = None, feature_version: str | None = None) -> None:
        self._ml_config = get_ml_config()
        self._feature_version = feature_version or self._ml_config.default_feature_version
        self._features: list[RegisteredFeature] = list(features or [])
        if not self._features:
            self._register_default_features()

    @property
    def features(self) -> tuple[RegisteredFeature, ...]:
        return tuple(self._features)

    @property
    def feature_version(self) -> str:
        return self._feature_version

    def register_feature(
        self,
        name: str,
        description: str,
        calculator: FeatureCalculator,
        source_fields: tuple[str, ...] = (),
        required: bool = True,
    ) -> None:
        if any(feature.definition.name == name for feature in self._features):
            raise ValueError(f"Feature already registered: {name}")
        self._features.append(
            RegisteredFeature(
                definition=FeatureDefinition(
                    name=name,
                    description=description,
                    source_fields=source_fields,
                    category=self._feature_category(name),
                    required=required,
                ),
                calculator=calculator,
            )
        )

    def build_snapshot(
        self,
        dataset_service: DatasetService,
        user_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> FinancialIntelligenceSnapshot:
        user_record = dataset_service.get_user(user_id)
        financial_profile = user_record.get("financial_profile") or {}
        transactions = pd.DataFrame(dataset_service.get_user_transactions(user_id))
        snapshot_metadata = {
            "dataset_loaded_at": dataset_service.loaded_at.isoformat() if dataset_service.loaded_at is not None else None,
            **(metadata or {}),
        }
        return FinancialIntelligenceSnapshot(
            user_id=user_id,
            user_record=user_record,
            financial_profile=financial_profile,
            transactions=transactions,
            metadata=snapshot_metadata,
        )

    def build_feature_row(self, snapshot: FinancialIntelligenceSnapshot) -> dict[str, Any]:
        return {feature.definition.name: feature.calculator(snapshot) for feature in self._features}

    def build_feature_frame(self, snapshots: Sequence[FinancialIntelligenceSnapshot]) -> FeatureFrame:
        if not snapshots:
            raise ValueError("At least one financial snapshot is required.")

        feature_rows = [self.build_feature_row(snapshot) for snapshot in snapshots]
        frame = pd.DataFrame(feature_rows)
        return FeatureFrame(
            data=frame,
            feature_names=tuple(frame.columns),
            feature_version=self._feature_version,
            source_count=len(snapshots),
            metadata={
                "features": [feature.definition.name for feature in self._features],
                "feature_version": self._feature_version,
            },
        )

    def build_user_feature_frame(self, dataset_service: DatasetService, user_id: str) -> FeatureFrame:
        snapshot = self.build_snapshot(dataset_service, user_id)
        return self.build_feature_frame([snapshot])

    def describe_features(self) -> list[FeatureDefinition]:
        return [feature.definition for feature in self._features]

    def _register_default_features(self) -> None:
        self.register_feature(
            name="commitment_ratio",
            description="Monthly commitments divided by monthly financial capacity.",
            calculator=self._commitment_ratio,
            source_fields=("monthly_commitments", "monthly_financial_capacity"),
        )
        self.register_feature(
            name="subscription_density",
            description="Share of active subscriptions within total active commitments.",
            calculator=self._subscription_density,
            source_fields=("active_subscriptions", "total_active_commitments"),
        )
        self.register_feature(
            name="emi_burden_ratio",
            description="Monetary EMI burden relative to monthly commitments.",
            calculator=self._emi_burden_ratio,
            source_fields=("amount", "transaction_class"),
        )
        self.register_feature(
            name="bnpl_dependency",
            description="Monetary BNPL burden relative to monthly commitments.",
            calculator=self._bnpl_dependency,
            source_fields=("active_bnpl", "total_active_commitments"),
        )
        self.register_feature(
            name="exposure_utilization",
            description="Exposure score normalized to 0-1.",
            calculator=self._exposure_utilization,
            source_fields=("exposure_score",),
        )
        self.register_feature(
            name="financial_flexibility",
            description="Cash-flow headroom after current commitments and variable spending.",
            calculator=self._financial_flexibility,
            source_fields=("exposure_score",),
        )
        self.register_feature(
            name="commitment_diversity",
            description="Normalized diversity across subscriptions, EMIs and BNPL.",
            calculator=self._commitment_diversity,
            source_fields=("active_subscriptions", "active_emis", "active_bnpl"),
        )
        self.register_feature(
            name="payment_reliability",
            description="Historical transaction success rate normalized to 0-1.",
            calculator=self._payment_reliability,
            source_fields=("transaction_success_rate",),
        )
        self.register_feature(
            name="autopay_coverage",
            description="Share of commitment transactions using AutoPay.",
            calculator=self._autopay_coverage,
            source_fields=("autopay_flag",),
        )
        self.register_feature(
            name="spending_variance",
            description="Coefficient of variation across non-income transaction amounts.",
            calculator=self._spending_variance,
            source_fields=("amount", "income_flag"),
            required=False,
        )
        self.register_feature(
            name="income_stability",
            description="Stability of monthly income inflows measured through variation.",
            calculator=self._income_stability,
            source_fields=("amount", "income_flag", "transaction_date"),
            required=False,
        )

    @staticmethod
    def _feature_category(name: str) -> str | None:
        categories = {
            "commitment_ratio": "Capacity",
            "subscription_density": "Commitment",
            "emi_burden_ratio": "Commitment",
            "bnpl_dependency": "Commitment",
            "exposure_utilization": "Exposure",
            "financial_flexibility": "Capacity",
            "commitment_diversity": "Behaviour",
            "payment_reliability": "Payment",
            "autopay_coverage": "Payment",
            "spending_variance": "Behaviour",
            "income_stability": "Income",
        }
        return categories.get(name)

    @staticmethod
    def _lookup_numeric(snapshot: FinancialIntelligenceSnapshot, *keys: str, default: float = 0.0) -> float:
        for source in (snapshot.financial_profile, snapshot.user_record):
            for key in keys:
                if key in source:
                    return coerce_float(source.get(key), default=default)
        return default

    @staticmethod
    def _active_commitment_count(snapshot: FinancialIntelligenceSnapshot) -> float:
        active_subscriptions = coerce_float(snapshot.financial_profile.get("active_subscriptions") or snapshot.user_record.get("active_subscriptions"))
        active_emis = coerce_float(snapshot.financial_profile.get("active_emis") or snapshot.user_record.get("active_emis"))
        active_bnpl = coerce_float(snapshot.financial_profile.get("active_bnpl") or snapshot.user_record.get("active_bnpl"))
        return active_subscriptions + active_emis + active_bnpl

    @staticmethod
    def _profile_transaction_success_rate(snapshot: FinancialIntelligenceSnapshot) -> float:
        rate = FeatureEngineeringPipeline._lookup_numeric(snapshot, "transaction_success_rate", default=0.0)
        return clamp(rate, 0.0, 1.0)

    @staticmethod
    def _commitment_rows(snapshot: FinancialIntelligenceSnapshot) -> pd.DataFrame:
        if snapshot.transactions.empty:
            return snapshot.transactions.copy()
        frame = snapshot.transactions.copy()
        if "transaction_class" not in frame.columns and "commitment_type" not in frame.columns:
            return frame.iloc[0:0]
        source = frame["transaction_class"] if "transaction_class" in frame.columns else frame["commitment_type"]
        commitment_mask = source.map(lambda value: normalize_text(value).lower() in {"subscription", "emi", "bnpl"})
        return frame.loc[commitment_mask].copy()

    def _commitment_ratio(self, snapshot: FinancialIntelligenceSnapshot) -> float:
        monthly_commitments = self._lookup_numeric(snapshot, "monthly_commitments", default=0.0)
        monthly_capacity = self._lookup_numeric(snapshot, "monthly_financial_capacity", default=0.0)
        return round(safe_divide(monthly_commitments, monthly_capacity, 0.0), 4)

    def _subscription_density(self, snapshot: FinancialIntelligenceSnapshot) -> float:
        active_subscriptions = self._lookup_numeric(snapshot, "active_subscriptions", default=0.0)
        total_commitments = max(self._active_commitment_count(snapshot), 1.0)
        return round(safe_divide(active_subscriptions, total_commitments, 0.0), 4)

    def _emi_burden_ratio(self, snapshot: FinancialIntelligenceSnapshot) -> float:
        return self._monetary_commitment_ratio(snapshot, {"emi"})

    def _bnpl_dependency(self, snapshot: FinancialIntelligenceSnapshot) -> float:
        return self._monetary_commitment_ratio(snapshot, {"bnpl"})

    def _exposure_utilization(self, snapshot: FinancialIntelligenceSnapshot) -> float:
        exposure_score = self._lookup_numeric(snapshot, "exposure_score", default=0.0)
        return round(max(exposure_score / 100.0, 0.0), 4)

    def _financial_flexibility(self, snapshot: FinancialIntelligenceSnapshot) -> float:
        transactions = snapshot.transactions
        if transactions.empty or "amount" not in transactions.columns:
            return 0.0
        frame = transactions.copy()
        if "transaction_status" in frame.columns:
            frame = frame[
                frame["transaction_status"].map(normalize_text).str.lower().isin(
                    {"success", "succeeded", "successful", "completed", "paid", "settled"}
                )
            ]
        income = 0.0
        if "income_flag" in frame.columns:
            income = float(frame.loc[frame["income_flag"].map(truthy), "amount"].map(coerce_float).clip(lower=0).sum())
            variable = frame.loc[~frame["income_flag"].map(truthy)]
        else:
            variable = frame
        source = frame["transaction_class"] if "transaction_class" in frame.columns else pd.Series("", index=frame.index)
        commitments = frame.loc[source.map(normalize_text).str.lower().isin({"subscription", "emi", "bnpl"})]
        commitment_total = float(commitments["amount"].map(coerce_float).clip(lower=0).sum()) if not commitments.empty else 0.0
        variable_total = float(variable["amount"].map(coerce_float).clip(lower=0).sum()) - commitment_total
        capacity = self._lookup_numeric(snapshot, "monthly_financial_capacity", default=0.0)
        if capacity <= 0:
            return 0.0
        return round(clamp(safe_divide(income - commitment_total - max(variable_total, 0.0), capacity, 0.0), 0.0, 1.0), 4)

    def _commitment_diversity(self, snapshot: FinancialIntelligenceSnapshot) -> float:
        active_types = sum(
            1
            for value in (
                self._lookup_numeric(snapshot, "active_subscriptions", default=0.0),
                self._lookup_numeric(snapshot, "active_emis", default=0.0),
                self._lookup_numeric(snapshot, "active_bnpl", default=0.0),
            )
            if value > 0
        )
        return round(active_types / 3.0, 4)

    def _payment_reliability(self, snapshot: FinancialIntelligenceSnapshot) -> float:
        if not snapshot.transactions.empty and "transaction_status" in snapshot.transactions.columns:
            statuses = snapshot.transactions["transaction_status"].map(normalize_text).str.lower()
            valid = statuses.ne("")
            if valid.any():
                return round(float(statuses[valid].isin({"success", "succeeded", "successful", "completed", "paid", "settled"}).mean()), 4)

        if "transaction_success_rate" in snapshot.financial_profile or "transaction_success_rate" in snapshot.user_record:
            return round(self._profile_transaction_success_rate(snapshot), 4)
        return 0.0

    def _monetary_commitment_ratio(self, snapshot: FinancialIntelligenceSnapshot, classes: set[str]) -> float:
        commitment_rows = self._commitment_rows(snapshot)
        if commitment_rows.empty or "amount" not in commitment_rows.columns:
            return 0.0
        source = commitment_rows["transaction_class"].map(normalize_text).str.lower()
        numerator = float(commitment_rows.loc[source.isin(classes), "amount"].map(coerce_float).clip(lower=0).sum())
        denominator = float(commitment_rows["amount"].map(coerce_float).clip(lower=0).sum())
        return round(safe_divide(numerator, denominator, 0.0), 4)

    def _autopay_coverage(self, snapshot: FinancialIntelligenceSnapshot) -> float:
        commitment_rows = self._commitment_rows(snapshot)
        if commitment_rows.empty or "autopay_flag" not in commitment_rows.columns:
            return 0.0
        enabled = commitment_rows["autopay_flag"].map(truthy).sum()
        return round(safe_divide(float(enabled), float(len(commitment_rows)), 0.0), 4)

    def _spending_variance(self, snapshot: FinancialIntelligenceSnapshot) -> float:
        if snapshot.transactions.empty or "amount" not in snapshot.transactions.columns:
            return 0.0

        frame = snapshot.transactions.copy()
        if "income_flag" in frame.columns:
            income_mask = frame["income_flag"].map(truthy)
            frame = frame.loc[~income_mask]
        values = [coerce_float(value) for value in frame["amount"].tolist() if pd.notna(value)]
        return round(coefficient_of_variation(values, default=0.0), 4)

    def _income_stability(self, snapshot: FinancialIntelligenceSnapshot) -> float:
        if snapshot.transactions.empty or {"amount", "income_flag", "transaction_date"}.difference(snapshot.transactions.columns):
            return 0.0

        income_rows = snapshot.transactions.copy()
        income_rows = income_rows.loc[income_rows["income_flag"].map(truthy)]
        if income_rows.empty:
            return 0.0

        income_rows = income_rows.copy()
        income_rows["transaction_date"] = pd.to_datetime(income_rows["transaction_date"], errors="coerce")
        income_rows = income_rows.dropna(subset=["transaction_date"])
        if income_rows.empty:
            return 0.0

        monthly_inflows = (
            income_rows.assign(month=income_rows["transaction_date"].dt.to_period("M"))
            .groupby("month", dropna=False)["amount"]
            .sum()
            .tolist()
        )
        variation = coefficient_of_variation([coerce_float(value) for value in monthly_inflows], default=0.0)
        return round(clamp(1.0 / (1.0 + variation), 0.0, 1.0), 4)

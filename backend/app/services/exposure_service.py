from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

import pandas as pd
from fastapi import Depends

from app.core.exceptions import (
    BnplNotFoundError,
    BnplProcessingError,
    EmiNotFoundError,
    EmiProcessingError,
    ExposureDataUnavailableError,
    ExposureNotFoundError,
    ExposureProcessingError,
    SubscriptionNotFoundError,
    SubscriptionProcessingError,
    UserNotFoundError,
)
from app.schemas.bnpl import BnplIntelligenceResponse
from app.schemas.dataset import UserResponse
from app.schemas.emi import EmiIntelligenceResponse
from app.schemas.exposure import (
    AvailableCapacityResponse,
    CommitmentBreakdownItemResponse,
    CommitmentBreakdownResponse,
    CommitmentItemResponse,
    CurrentFinancialStatusResponse,
    ExposureIntelligenceResponse,
    ExposureMetadataResponse,
    ExposureRecommendationResponse,
    ExposureSummaryResponse,
    FinancialForecastResponse,
    FinancialHealthResponse,
    ForecastEventResponse,
)
from app.schemas.subscription import SubscriptionIntelligenceResponse, TransactionStatusSummaryResponse
from app.services.bnpl_service import BnplService
from app.services.commitment_service import UnifiedCommitmentService
from app.services.dataset_service import DatasetService, get_dataset_service
from app.services.emi_service import EmiService
from app.services.financial_rules import monthly_multiplier
from app.services.income_service import IncomeService, get_income_service
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FrequencyRule:
    label: str
    multiplier: float
    months: float
    days: int


class ExposureService:
    _frequency_rules: tuple[FrequencyRule, ...] = (
        FrequencyRule("weekly", 52.0 / 12.0, 0.0, 7),
        FrequencyRule("biweekly", 26.0 / 12.0, 0.0, 14),
        FrequencyRule("fortnightly", 26.0 / 12.0, 0.0, 14),
        FrequencyRule("monthly", 1.0, 1.0, 0),
        FrequencyRule("installment", 1.0, 1.0, 0),
        FrequencyRule("instalment", 1.0, 1.0, 0),
        FrequencyRule("quarterly", 1.0 / 3.0, 3.0, 0),
        FrequencyRule("semiannual", 1.0 / 6.0, 6.0, 0),
        FrequencyRule("annual", 1.0 / 12.0, 12.0, 0),
        FrequencyRule("yearly", 1.0 / 12.0, 12.0, 0),
        FrequencyRule("daily", 365.0 / 12.0, 0.0, 1),
    )

    def __init__(
        self,
        dataset_service: DatasetService,
        subscription_service: SubscriptionService,
        emi_service: EmiService,
        bnpl_service: BnplService,
        income_service: IncomeService | None = None,
    ) -> None:
        self._dataset_service = dataset_service
        self._subscription_service = subscription_service
        self._emi_service = emi_service
        self._bnpl_service = bnpl_service
        self._income_service = income_service or get_income_service()

    @staticmethod
    def _normalize_text(value: Any) -> str:
        if value is None or pd.isna(value):
            return ""
        return str(value).strip()

    @staticmethod
    def _normalize_lower(value: Any) -> str:
        return ExposureService._normalize_text(value).lower()

    @staticmethod
    def _to_float(value: Any) -> float:
        if value is None or pd.isna(value):
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _to_date(value: Any) -> date | None:
        if value is None or pd.isna(value):
            return None
        if isinstance(value, pd.Timestamp):
            return value.date()
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return None

    @staticmethod
    def _to_bool(value: Any) -> bool:
        return ExposureService._normalize_lower(value) in {"yes", "true", "1", "y"}

    @classmethod
    def _monthly_multiplier(cls, frequency: Any) -> float:
        return monthly_multiplier(frequency)

    @classmethod
    def _forecast_offset(cls, frequency: Any) -> pd.DateOffset:
        normalized = cls._normalize_lower(frequency)
        for rule in cls._frequency_rules:
            if rule.label in normalized:
                if rule.months > 0:
                    return pd.DateOffset(months=int(rule.months))
                return pd.DateOffset(days=rule.days)
        return pd.DateOffset(months=1)

    @staticmethod
    def _safe_divide(numerator: float, denominator: float) -> float:
        if denominator == 0:
            return 0.0
        return numerator / denominator

    @staticmethod
    def _clamp_score(score: float) -> float:
        return round(min(max(score, 0.0), 100.0), 2)

    @staticmethod
    def _factor_detail(score: float, max_score: float, description: str, evidence: list[str]) -> dict[str, Any]:
        return {
            "score": round(score, 2),
            "max_score": round(max_score, 2),
            "description": description,
            "evidence": evidence,
        }

    @classmethod
    def _transaction_status_summary(cls, frame: pd.DataFrame) -> TransactionStatusSummaryResponse:
        breakdown = {
            str(index): int(value)
            for index, value in frame["transaction_status"].fillna("Unknown").value_counts(dropna=False).sort_index().items()
        }
        successful = sum(count for status, count in breakdown.items() if cls._normalize_lower(status) == "success")
        failed = sum(count for status, count in breakdown.items() if cls._normalize_lower(status) in {"failed", "declined", "rejected"})
        pending = sum(count for status, count in breakdown.items() if cls._normalize_lower(status) in {"pending", "processing", "in_progress"})
        other = max(int(frame.shape[0]) - successful - failed - pending, 0)
        return TransactionStatusSummaryResponse(
            status_breakdown=breakdown,
            successful_transactions=successful,
            failed_transactions=failed,
            pending_transactions=pending,
            other_transactions=other,
        )

    @classmethod
    def _financial_health_label(cls, score: float) -> str:
        # Health score is intentionally harder to max out; 100 is reserved for ideal or zero-commitment cases.
        if score >= 92:
            return "Excellent"
        if score >= 80:
            return "Healthy"
        if score >= 65:
            return "Moderate"
        if score >= 45:
            return "Risky"
        return "Critical"

    @staticmethod
    def _risk_level(exposure_score: float, health_label: str) -> str:
        if exposure_score > 120 or health_label == "Critical":
            return "Critical"
        if exposure_score > 100 or health_label == "Risky":
            return "High"
        if exposure_score > 50 or health_label == "Moderate":
            return "Moderate"
        return "Low"

    def _build_transaction_frame(self, transactions: list[dict[str, Any]]) -> pd.DataFrame:
        frame = pd.DataFrame(transactions)
        if frame.empty:
            return frame

        prepared = frame.copy()
        prepared["transaction_date"] = pd.to_datetime(prepared["transaction_date"], errors="coerce")
        prepared["transaction_class_normalized"] = prepared["transaction_class"].map(self._normalize_lower)
        prepared["amount_value"] = pd.to_numeric(prepared["amount"], errors="coerce").fillna(0.0)
        prepared["frequency_normalized"] = prepared["frequency"].map(self._normalize_lower)
        prepared["monthly_amount"] = prepared["amount_value"] * prepared["frequency_normalized"].map(self._monthly_multiplier)
        prepared["autopay_enabled_flag"] = prepared["autopay_flag"].map(self._to_bool)
        prepared["commitment_type_normalized"] = prepared["commitment_type"].map(self._normalize_lower)
        return prepared

    def _latest_items(self, frame: pd.DataFrame, class_label: str) -> list[dict[str, Any]]:
        if frame.empty:
            return []
        subset = frame[frame["transaction_class_normalized"] == class_label].copy()
        if subset.empty:
            return []
        grouped = subset.sort_values("transaction_date").groupby("merchant_name", dropna=False)
        items: list[dict[str, Any]] = []
        for merchant_name, group in grouped:
            latest = group.sort_values("transaction_date").iloc[-1]
            items.append(
                {
                    "name": self._normalize_text(merchant_name),
                    "monthly_amount": self._to_float(group["monthly_amount"].mean()),
                    "total_amount": self._to_float(group["amount_value"].sum()),
                    "commitment_type": self._normalize_text(group["commitment_type"].mode().iloc[0]) if not group["commitment_type"].mode().empty else "Unknown",
                    "autopay_enabled": bool(group["autopay_enabled_flag"].any()),
                    "latest_date": self._to_date(latest["transaction_date"]),
                    "frequency": self._normalize_text(latest.get("frequency")),
                    "transaction_count": int(group.shape[0]),
                    "first_date": self._to_date(group["transaction_date"].min()),
                    "transaction_status_summary": self._transaction_status_summary(group),
                }
            )
        return items

    @staticmethod
    def _largest_optional_from_items(items: list[dict[str, Any]], source: str) -> CommitmentItemResponse | None:
        optional_items = [item for item in items if item.get("commitment_type", "").lower() == "optional"]
        if not optional_items:
            return None
        selected = max(optional_items, key=lambda item: (item.get("monthly_amount", 0.0), item.get("name", "")))
        return CommitmentItemResponse(
            commitment_name=selected["name"],
            commitment_source=source,
            monthly_amount=round(ExposureService._to_float(selected.get("monthly_amount")), 2),
            total_amount=round(ExposureService._to_float(selected.get("total_amount")), 2),
            commitment_type=selected.get("commitment_type", "Optional"),
        )

    @staticmethod
    def _largest_overall_commitment(*items: CommitmentItemResponse | None) -> CommitmentItemResponse | None:
        valid_items = [item for item in items if item is not None]
        if not valid_items:
            return None
        return max(valid_items, key=lambda item: (item.monthly_amount, item.commitment_name))

    def _build_breakdown_item(
        self,
        source: str,
        monthly_amount: float,
        active_commitments: int,
        mandatory_commitments: int,
        optional_commitments: int,
        largest_commitment: CommitmentItemResponse | None,
        largest_optional_commitment: CommitmentItemResponse | None,
        total_monthly: float,
    ) -> CommitmentBreakdownItemResponse:
        contribution = self._safe_divide(monthly_amount * 100.0, total_monthly)
        return CommitmentBreakdownItemResponse(
            commitment_source=source,
            active_commitments=active_commitments,
            mandatory_commitments=mandatory_commitments,
            optional_commitments=optional_commitments,
            monthly_amount=round(monthly_amount, 2),
            percentage_contribution=round(contribution, 2),
            largest_commitment=largest_commitment,
            largest_optional_commitment=largest_optional_commitment,
        )

    def _build_current_status(
        self,
        subscription: SubscriptionIntelligenceResponse | None,
        emi: EmiIntelligenceResponse | None,
        bnpl: BnplIntelligenceResponse | None,
        monthly_capacity: float,
        unified_total: float | None = None,
        unified_breakdown: dict[str, float] | None = None,
        unified_items: list[CommitmentItemResponse] | None = None,
        income_source: str = "Observed",
        income_mode: str = "auto",
        expected_monthly_income: float | None = None,
        manual_monthly_income: float | None = None,
    ) -> tuple[CurrentFinancialStatusResponse, ExposureSummaryResponse, AvailableCapacityResponse, CommitmentBreakdownResponse, CommitmentItemResponse | None, CommitmentItemResponse | None]:
        subscription_monthly = (
            self._to_float(unified_breakdown.get("subscription"))
            if unified_breakdown is not None
            else self._to_float(subscription.subscription_summary.monthly_subscription_cost) if subscription else 0.0
        )
        emi_monthly = (
            self._to_float(unified_breakdown.get("emi")) + self._to_float(unified_breakdown.get("loan"))
            if unified_breakdown is not None
            else self._to_float(emi.emi_summary.monthly_emi_burden) if emi else 0.0
        )
        bnpl_monthly = (
            self._to_float(unified_breakdown.get("bnpl"))
            if unified_breakdown is not None
            else self._to_float(bnpl.bnpl_summary.monthly_bnpl_burden) if bnpl else 0.0
        )
        total_monthly = round(
            unified_total if unified_total is not None else subscription_monthly + emi_monthly + bnpl_monthly,
            2,
        )
        exposure_score = round(self._safe_divide(total_monthly * 100.0, monthly_capacity), 2) if monthly_capacity > 0 else 0.0
        available_capacity = round(max(monthly_capacity - total_monthly, 0.0), 2)
        monthly_deficit = round(max(total_monthly - monthly_capacity, 0.0), 2)
        overcommitted_amount = monthly_deficit
        overcommitted_percentage = round(self._safe_divide(overcommitted_amount * 100.0, monthly_capacity), 2) if monthly_capacity > 0 else 0.0
        exposure_band = self._exposure_band(exposure_score)

        subscription_active = (
            sum(1 for item in unified_items or [] if item.category.casefold() == "subscription")
            if unified_items is not None
            else len(subscription.active_subscriptions) if subscription else 0
        )
        emi_active = (
            sum(1 for item in unified_items or [] if item.category.casefold() in {"emi", "loan"})
            if unified_items is not None
            else len(emi.active_emis) if emi else 0
        )
        bnpl_active = (
            sum(1 for item in unified_items or [] if item.category.casefold() == "bnpl")
            if unified_items is not None
            else len(bnpl.active_bnpl_accounts) if bnpl else 0
        )

        subscription_items = self._latest_items(self._current_frame, "subscription")
        emi_items = self._latest_items(self._current_frame, "emi")
        bnpl_items = self._latest_items(self._current_frame, "bnpl")

        subscription_largest = self._largest_item_from_items(subscription_items, "Subscription")
        emi_largest = self._largest_item_from_items(emi_items, "EMI")
        bnpl_largest = self._largest_item_from_items(bnpl_items, "BNPL")
        largest_overall = self._largest_overall_commitment(subscription_largest, emi_largest, bnpl_largest)

        subscription_optional = self._largest_optional_from_items(subscription_items, "Subscription")
        emi_optional = self._largest_optional_from_items(emi_items, "EMI")
        bnpl_optional = self._largest_optional_from_items(bnpl_items, "BNPL")
        largest_optional_overall = self._largest_overall_commitment(subscription_optional, emi_optional, bnpl_optional)

        current_message = (
            "No recurring financial commitments detected." if total_monthly <= 0 else
            "Commitments remain within monthly capacity." if monthly_deficit <= 0 else
            "Recurring commitments currently exceed monthly capacity."
        )

        current_status = CurrentFinancialStatusResponse(
            monthly_subscription_commitment=round(subscription_monthly, 2),
            monthly_emi_commitment=round(emi_monthly, 2),
            monthly_bnpl_commitment=round(bnpl_monthly, 2),
            monthly_total_commitments=total_monthly,
            monthly_financial_capacity=round(monthly_capacity, 2),
            available_monthly_capacity=available_capacity,
            monthly_deficit=monthly_deficit,
            overcommitted_percentage=overcommitted_percentage,
            exposure_score=exposure_score,
            exposure_formula="monthly_total_commitments / monthly_financial_capacity x 100",
            current_message=current_message,
            income_source=income_source,
            income_mode=income_mode,
            expected_monthly_income=expected_monthly_income,
            manual_monthly_income=manual_monthly_income,
        )

        exposure_summary = ExposureSummaryResponse(
            exposure_score=exposure_score,
            exposure_band=exposure_band,
            explanation=self._exposure_explanation(total_monthly, monthly_capacity, exposure_score),
            evidence=self._exposure_evidence(subscription_monthly, emi_monthly, bnpl_monthly, monthly_capacity, exposure_score),
            largest_contributor=largest_overall,
            largest_optional_commitment=largest_optional_overall,
            commitment_concentration=self._commitment_concentration_text(subscription_monthly, emi_monthly, bnpl_monthly),
        )

        available_response = AvailableCapacityResponse(
            available_monthly_capacity=available_capacity,
            remaining_capacity_percent=round(self._safe_divide(available_capacity * 100.0, monthly_capacity), 2) if monthly_capacity > 0 else 0.0,
            monthly_deficit=monthly_deficit,
            overcommitted_amount=overcommitted_amount,
            overcommitted_percentage=overcommitted_percentage,
            critical_warning=("Monthly commitments exceed monthly financial capacity." if monthly_deficit > 0 else None),
        )

        subscription_mandatory, subscription_optional_count = self._count_mandatory_optional(subscription_items)
        emi_mandatory, emi_optional_count = self._count_mandatory_optional(emi_items)
        bnpl_mandatory, bnpl_optional_count = self._count_mandatory_optional(bnpl_items)

        breakdown = CommitmentBreakdownResponse(
            subscriptions=self._build_breakdown_item(
                "Subscription",
                subscription_monthly,
                subscription_active,
                subscription_mandatory,
                subscription_optional_count,
                subscription_largest,
                subscription_optional,
                total_monthly,
            ),
            emis=self._build_breakdown_item(
                "EMI",
                emi_monthly,
                emi_active,
                emi_mandatory,
                emi_optional_count,
                emi_largest,
                emi_optional,
                total_monthly,
            ),
            bnpl=self._build_breakdown_item(
                "BNPL",
                bnpl_monthly,
                bnpl_active,
                bnpl_mandatory,
                bnpl_optional_count,
                bnpl_largest,
                bnpl_optional,
                total_monthly,
            ),
        )

        return current_status, exposure_summary, available_response, breakdown, largest_overall, largest_optional_overall

    def _count_mandatory_optional(self, items: list[dict[str, Any]]) -> tuple[int, int]:
        mandatory = sum(1 for item in items if item.get("commitment_type", "").lower() == "mandatory")
        optional = sum(1 for item in items if item.get("commitment_type", "").lower() == "optional")
        return mandatory, optional

    @staticmethod
    def _exposure_band(exposure_score: float) -> str:
        if exposure_score > 120:
            return "Critical"
        if exposure_score > 100:
            return "High"
        if exposure_score > 40:
            return "Moderate"
        if exposure_score > 0:
            return "Low"
        return "Minimal"

    @staticmethod
    def _exposure_explanation(total_monthly: float, monthly_capacity: float, exposure_score: float) -> str:
        if total_monthly <= 0:
            return "No recurring financial commitments detected."
        if monthly_capacity <= 0:
            return "Monthly financial capacity is unavailable for exposure comparison."
        if exposure_score <= 100:
            return "Monthly commitments remain within monthly financial capacity."
        return "Monthly commitments exceed monthly financial capacity."

    @staticmethod
    def _exposure_evidence(subscription_monthly: float, emi_monthly: float, bnpl_monthly: float, monthly_capacity: float, exposure_score: float) -> list[str]:
        return [
            f"subscriptions={round(subscription_monthly, 2)}",
            f"emis={round(emi_monthly, 2)}",
            f"bnpl={round(bnpl_monthly, 2)}",
            f"monthly_financial_capacity={round(monthly_capacity, 2)}",
            f"exposure_score={round(exposure_score, 2)}",
        ]

    @staticmethod
    def _commitment_concentration_text(subscription_monthly: float, emi_monthly: float, bnpl_monthly: float) -> str:
        contributions = {
            "Subscription": subscription_monthly,
            "EMI": emi_monthly,
            "BNPL": bnpl_monthly,
        }
        top_source, top_amount = max(contributions.items(), key=lambda item: item[1])
        total = sum(contributions.values())
        if total <= 0:
            return "No recurring commitments detected."
        share = round((top_amount / total) * 100.0, 1)
        return f"{top_source} contributes {share}% of total monthly commitments."

    @staticmethod
    def _item_from_group_item(item: dict[str, Any], source: str) -> CommitmentItemResponse:
        return CommitmentItemResponse(
            commitment_name=item["name"],
            commitment_source=source,
            monthly_amount=round(ExposureService._to_float(item.get("monthly_amount")), 2),
            total_amount=round(ExposureService._to_float(item.get("total_amount")), 2),
            commitment_type=item.get("commitment_type", "Unknown"),
        )

    @staticmethod
    def _largest_item_from_items(items: list[dict[str, Any]], source: str) -> CommitmentItemResponse | None:
        if not items:
            return None
        selected = max(items, key=lambda item: (ExposureService._to_float(item.get("monthly_amount")), item.get("name", "")))
        return ExposureService._item_from_group_item(selected, source)

    def _build_payment_health_context(
        self,
        subscription: SubscriptionIntelligenceResponse | None,
        emi: EmiIntelligenceResponse | None,
        bnpl: BnplIntelligenceResponse | None,
    ) -> dict[str, float]:
        successful = 0
        failed = 0
        pending = 0
        other = 0
        autopay_count = 0
        active_commitments = 0

        if subscription is not None:
            for item in subscription.active_subscriptions:
                status_summary = item.transaction_status_summary
                successful += status_summary.successful_transactions
                failed += status_summary.failed_transactions
                pending += status_summary.pending_transactions
                other += getattr(status_summary, "other_transactions", 0)
                if item.autopay_enabled:
                    autopay_count += 1
            active_commitments += len(subscription.active_subscriptions)
        if emi is not None:
            successful += emi.payment_statistics.successful_payments
            failed += emi.payment_statistics.failed_payments
            pending += emi.payment_statistics.pending_payments
            other += emi.payment_statistics.transaction_status_summary.other_transactions
            autopay_count += sum(1 for row in emi.active_emis if row.autopay_enabled)
            active_commitments += len(emi.active_emis)
        if bnpl is not None:
            successful += bnpl.payment_statistics.successful_payments
            failed += bnpl.payment_statistics.failed_payments
            pending += bnpl.payment_statistics.pending_payments
            other += bnpl.payment_statistics.transaction_status_summary.other_transactions
            autopay_count += sum(1 for row in bnpl.active_bnpl_accounts if row.autopay_enabled)
            active_commitments += len(bnpl.active_bnpl_accounts)

        total_payment_events = successful + failed + pending + other
        payment_success_rate = round(self._safe_divide(successful * 100.0, total_payment_events), 2) if total_payment_events else 100.0
        autopay_coverage = round(self._safe_divide(autopay_count * 100.0, active_commitments), 2) if active_commitments else 100.0
        return {
            "successful": float(successful),
            "failed": float(failed),
            "pending": float(pending),
            "other": float(other),
            "payment_success_rate": payment_success_rate,
            "autopay_coverage": autopay_coverage,
            "active_commitments": float(active_commitments),
        }

    def _build_financial_health(
        self,
        exposure_score: float,
        subscription: SubscriptionIntelligenceResponse | None,
        emi: EmiIntelligenceResponse | None,
        bnpl: BnplIntelligenceResponse | None,
        current_total_commitments: float,
        monthly_capacity: float,
    ) -> FinancialHealthResponse:
        # The score is built from six explainable factors. 100 is only kept for the ideal zero-commitment case,
        # while active portfolios are capped at 98 unless future rules intentionally allow a perfect score.
        payment_context = self._build_payment_health_context(subscription, emi, bnpl)
        success_rate = payment_context["payment_success_rate"]
        autopay_coverage = payment_context["autopay_coverage"]
        failed = payment_context["failed"]
        pending = payment_context["pending"]
        active_commitments = payment_context["active_commitments"]

        subscription_monthly = self._to_float(subscription.subscription_summary.monthly_subscription_cost) if subscription else 0.0
        emi_monthly = self._to_float(emi.emi_summary.monthly_emi_burden) if emi else 0.0
        bnpl_monthly = self._to_float(bnpl.bnpl_summary.monthly_bnpl_burden) if bnpl else 0.0
        source_monthlies = {
            "Subscription": subscription_monthly,
            "EMI": emi_monthly,
            "BNPL": bnpl_monthly,
        }
        active_sources = [source for source, amount in source_monthlies.items() if amount > 0]
        total_monthly = sum(source_monthlies.values())
        top_source = max(source_monthlies.items(), key=lambda item: item[1])
        top_source_share = self._safe_divide(top_source[1], total_monthly)

        if total_monthly <= 0:
            return FinancialHealthResponse(
                financial_health_score=100.0,
                financial_health_label="Excellent",
                risk_level="Low",
                rationale=["No recurring commitments are currently detected.", "The user retains maximum monthly flexibility."],
                factor_scores={
                    "exposure": self._factor_detail(35.0, 35.0, "No recurring commitments reduce exposure to zero.", ["monthly_total_commitments=0"]),
                    "payment_behaviour": self._factor_detail(25.0, 25.0, "No recurring payment burden is present.", ["No active recurring payments"]),
                    "autopay": self._factor_detail(15.0, 15.0, "No active commitments require AutoPay coverage.", ["No active commitments"]),
                    "commitment_diversity": self._factor_detail(10.0, 10.0, "No commitments means maximum portfolio flexibility.", ["No active commitments"]),
                    "financial_discipline": self._factor_detail(10.0, 10.0, "No recurring obligations keeps monthly discipline intact.", ["No active commitments"]),
                    "commitment_concentration": self._factor_detail(5.0, 5.0, "No single commitment source can dominate the portfolio.", ["No active commitments"]),
                },
            )

        exposure_factor = self._factor_exposure(exposure_score)
        payment_factor = self._factor_payment_behaviour(success_rate, failed, pending)
        autopay_factor = self._factor_autopay(autopay_coverage)
        diversity_factor = self._factor_commitment_diversity(active_sources)
        discipline_factor = self._factor_financial_discipline(success_rate, autopay_coverage, exposure_score, failed, pending)
        concentration_factor = self._factor_commitment_concentration(top_source_share)

        raw_score = exposure_factor[0] + payment_factor[0] + autopay_factor[0] + diversity_factor[0] + discipline_factor[0] + concentration_factor[0]
        score = min(round(raw_score, 2), 98.0)
        health_label = self._financial_health_label(score)
        risk_level = self._risk_level(exposure_score, health_label)

        rationale = [
            f"Exposure score is {round(exposure_score, 2)}%.",
            f"Payment success rate is {round(success_rate, 2)}%.",
            f"AutoPay coverage is {round(autopay_coverage, 2)}%.",
            f"{int(active_commitments)} active recurring commitments are being tracked.",
            f"The largest commitment source contributes {round(top_source_share * 100.0, 1)}% of monthly commitments.",
        ]

        factor_scores = {
            "exposure": self._factor_detail(exposure_factor[0], exposure_factor[1], exposure_factor[2], exposure_factor[3]),
            "payment_behaviour": self._factor_detail(payment_factor[0], payment_factor[1], payment_factor[2], payment_factor[3]),
            "autopay": self._factor_detail(autopay_factor[0], autopay_factor[1], autopay_factor[2], autopay_factor[3]),
            "commitment_diversity": self._factor_detail(diversity_factor[0], diversity_factor[1], diversity_factor[2], diversity_factor[3]),
            "financial_discipline": self._factor_detail(discipline_factor[0], discipline_factor[1], discipline_factor[2], discipline_factor[3]),
            "commitment_concentration": self._factor_detail(concentration_factor[0], concentration_factor[1], concentration_factor[2], concentration_factor[3]),
        }

        return FinancialHealthResponse(
            financial_health_score=score,
            financial_health_label=health_label,
            risk_level=risk_level,
            rationale=rationale,
            factor_scores=factor_scores,
        )

    @staticmethod
    def _factor_exposure(exposure_score: float) -> tuple[float, float, str, list[str]]:
        if exposure_score <= 5:
            return 35.0, 35.0, "Minimal recurring burden relative to capacity.", [f"exposure_score={round(exposure_score, 2)}"]
        if exposure_score <= 25:
            return 30.0, 35.0, "Low recurring burden relative to capacity.", [f"exposure_score={round(exposure_score, 2)}"]
        if exposure_score <= 50:
            return 22.0, 35.0, "Moderate recurring burden is consuming a meaningful share of capacity.", [f"exposure_score={round(exposure_score, 2)}"]
        if exposure_score <= 75:
            return 12.0, 35.0, "High recurring burden is reducing flexibility.", [f"exposure_score={round(exposure_score, 2)}"]
        if exposure_score <= 100:
            return 4.0, 35.0, "Very high recurring burden is close to capacity.", [f"exposure_score={round(exposure_score, 2)}"]
        return 0.0, 35.0, "Commitments exceed monthly capacity.", [f"exposure_score={round(exposure_score, 2)}"]

    @staticmethod
    def _factor_payment_behaviour(success_rate: float, failed: float, pending: float) -> tuple[float, float, str, list[str]]:
        evidence = [f"payment_success_rate={round(success_rate, 2)}", f"failed_payments={int(failed)}", f"pending_payments={int(pending)}"]
        if success_rate >= 99.5 and failed == 0 and pending == 0:
            return 25.0, 25.0, "Outstanding payment reliability across recurring commitments.", evidence
        if success_rate >= 97 and failed <= 1 and pending == 0:
            return 23.0, 25.0, "Very strong payment behaviour with minimal friction.", evidence
        if success_rate >= 95:
            return 20.0, 25.0, "Strong payment behaviour with occasional friction.", evidence
        if success_rate >= 90:
            return 16.0, 25.0, "Adequate payment behaviour, but the success rate leaves room for improvement.", evidence
        if success_rate >= 80:
            return 10.0, 25.0, "Mixed payment behaviour that deserves monitoring.", evidence
        return 4.0, 25.0, "Weak payment behaviour with material failure or pending patterns.", evidence

    @staticmethod
    def _factor_autopay(autopay_coverage: float) -> tuple[float, float, str, list[str]]:
        evidence = [f"autopay_coverage={round(autopay_coverage, 2)}"]
        if autopay_coverage >= 95:
            return 15.0, 15.0, "AutoPay is enabled for nearly all active commitments.", evidence
        if autopay_coverage >= 80:
            return 12.0, 15.0, "AutoPay coverage is strong across active commitments.", evidence
        if autopay_coverage >= 60:
            return 8.0, 15.0, "AutoPay coverage is moderate and can be expanded.", evidence
        if autopay_coverage > 0:
            return 3.0, 15.0, "AutoPay coverage is limited across active commitments.", evidence
        return 0.0, 15.0, "No active commitments use AutoPay.", evidence

    @staticmethod
    def _factor_commitment_diversity(active_sources: list[str]) -> tuple[float, float, str, list[str]]:
        evidence = [f"active_sources={', '.join(active_sources) if active_sources else 'none'}"]
        count = len(active_sources)
        if count >= 3:
            return 10.0, 10.0, "Commitments are spread across subscriptions, EMIs, and BNPL.", evidence
        if count == 2:
            return 7.0, 10.0, "Commitments are split across two product types.", evidence
        if count == 1:
            return 3.0, 10.0, "All recurring commitments sit in a single product type.", evidence
        return 10.0, 10.0, "No recurring commitments are active.", evidence

    @staticmethod
    def _factor_financial_discipline(success_rate: float, autopay_coverage: float, exposure_score: float, failed: float, pending: float) -> tuple[float, float, str, list[str]]:
        evidence = [f"payment_success_rate={round(success_rate, 2)}", f"autopay_coverage={round(autopay_coverage, 2)}", f"failed_payments={int(failed)}", f"pending_payments={int(pending)}"]
        if success_rate >= 98 and autopay_coverage >= 90 and failed == 0 and pending == 0 and exposure_score <= 75:
            return 10.0, 10.0, "The user shows strong payment discipline with efficient recurring payment handling.", evidence
        if success_rate >= 95 and autopay_coverage >= 75:
            return 8.0, 10.0, "The user is paying on time and using AutoPay effectively.", evidence
        if success_rate >= 90:
            return 6.0, 10.0, "The user shows acceptable discipline, but there is still room to improve reliability.", evidence
        return 2.0, 10.0, "The current payment pattern suggests weaker discipline.", evidence

    @staticmethod
    def _factor_commitment_concentration(top_source_share: float) -> tuple[float, float, str, list[str]]:
        evidence = [f"largest_source_share={round(top_source_share * 100.0, 1)}%"]
        if top_source_share <= 0.4:
            return 5.0, 5.0, "No single commitment source dominates the portfolio.", evidence
        if top_source_share <= 0.6:
            return 4.0, 5.0, "One commitment source is prominent but not overwhelming.", evidence
        if top_source_share <= 0.8:
            return 2.0, 5.0, "The portfolio is heavily concentrated in one commitment source.", evidence
        return 0.0, 5.0, "The portfolio is dominated by a single commitment source.", evidence

    @staticmethod
    def _recommendation_effort(recommendation_type: str) -> str:
        effort_map = {
            "Maintain Current Discipline": "Very Easy",
            "Exposure Rebalancing": "High",
            "Subscription Review": "Easy",
            "EMI Planning": "Medium",
            "BNPL Discipline": "Medium",
            "Financial Stability Review": "High",
            "Trial Conversion Planning": "Easy",
            "Subscription Timing": "Easy",
            "EMI Budgeting": "Medium",
            "BNPL Installment Readiness": "Medium",
            "AutoPay Coverage": "Very Easy",
            "Future Exposure Buffer": "High",
        }
        return effort_map.get(recommendation_type, "Medium")

    def _build_recommendations(
        self,
        subscription: SubscriptionIntelligenceResponse | None,
        emi: EmiIntelligenceResponse | None,
        bnpl: BnplIntelligenceResponse | None,
        current_status: CurrentFinancialStatusResponse,
        financial_health: FinancialHealthResponse,
    ) -> list[ExposureRecommendationResponse]:
        recommendations: list[ExposureRecommendationResponse] = []
        total_monthly = current_status.monthly_total_commitments
        exposure_score = current_status.exposure_score
        monthly_capacity = current_status.monthly_financial_capacity

        subscription_optional_monthly = 0.0
        if subscription is not None and hasattr(self, "_current_frame") and not self._current_frame.empty:
            optional_frame = self._current_frame[
                (self._current_frame["transaction_class_normalized"] == "subscription")
                & (self._current_frame["commitment_type_normalized"] == "optional")
            ]
            if not optional_frame.empty:
                subscription_optional_monthly = self._to_float(optional_frame.groupby("merchant_name")["monthly_amount"].mean().sum())

        def _benefit(monthly_saving: float | None) -> tuple[float | None, float | None, float | None, str | None]:
            if monthly_saving is None:
                return None, None, None, None
            annual_saving = round(monthly_saving * 12.0, 2)
            exposure_reduction = round(self._safe_divide(monthly_saving * 100.0, monthly_capacity), 2) if monthly_capacity > 0 else None
            financial_benefit = (
                f"Estimated recurring monthly saving of Rs. {monthly_saving:,.0f} "
                f"(Rs. {annual_saving:,.0f} annually)."
                if monthly_saving > 0
                else None
            )
            return round(monthly_saving, 2), annual_saving, exposure_reduction, financial_benefit

        if total_monthly <= 0:
            recommendations.append(
                ExposureRecommendationResponse(
                    recommendation_type="Maintain Current Discipline",
                    priority="Low",
                    impact_score=100.0,
                    message="Maintain the current low-commitment pattern.",
                    reason="No recurring financial commitments are currently detected.",
                    expected_benefit="Preserves maximum monthly flexibility and keeps exposure near zero.",
                    action_required="Continue monitoring new commitments before activating them.",
                    estimated_effort=self._recommendation_effort("Maintain Current Discipline"),
                    estimated_monthly_saving=None,
                    estimated_annual_saving=None,
                    estimated_exposure_reduction=None,
                    financial_benefit=None,
                )
            )
            return recommendations

        subscription_share = self._safe_divide(current_status.monthly_subscription_commitment * 100.0, total_monthly)
        emi_share = self._safe_divide(current_status.monthly_emi_commitment * 100.0, total_monthly)
        bnpl_share = self._safe_divide(current_status.monthly_bnpl_commitment * 100.0, total_monthly)

        if exposure_score > 100:
            monthly_saving, annual_saving, exposure_reduction, financial_benefit = _benefit(current_status.monthly_deficit)
            recommendations.append(
                ExposureRecommendationResponse(
                    recommendation_type="Exposure Rebalancing",
                    priority="Critical",
                    impact_score=100.0,
                    message="Rebalance recurring commitments to restore monthly flexibility.",
                    reason="Monthly commitments exceed monthly financial capacity.",
                    expected_benefit="Reduces overcommitment and improves monthly cash-flow resilience.",
                    action_required="Pause new recurring obligations and review the largest commitments first.",
                    estimated_effort=self._recommendation_effort("Exposure Rebalancing"),
                    estimated_monthly_saving=monthly_saving,
                    estimated_annual_saving=annual_saving,
                    estimated_exposure_reduction=exposure_reduction,
                    financial_benefit=financial_benefit,
                )
            )

        if subscription_share >= 20 and subscription is not None:
            monthly_saving, annual_saving, exposure_reduction, financial_benefit = _benefit(subscription_optional_monthly if subscription_optional_monthly > 0 else None)
            recommendations.append(
                ExposureRecommendationResponse(
                    recommendation_type="Subscription Review",
                    priority="High",
                    impact_score=min(round(subscription_share, 2), 95.0),
                    message="Review subscription commitments with the highest monthly contribution.",
                    reason="Subscriptions represent a material share of monthly commitments.",
                    expected_benefit="Creates room for higher-priority commitments without reducing convenience.",
                    action_required="Review recurring subscription list and keep only the subscriptions that add clear value.",
                    estimated_effort=self._recommendation_effort("Subscription Review"),
                    estimated_monthly_saving=monthly_saving,
                    estimated_annual_saving=annual_saving,
                    estimated_exposure_reduction=exposure_reduction,
                    financial_benefit=financial_benefit,
                )
            )

        if emi_share >= 25 and emi is not None:
            recommendations.append(
                ExposureRecommendationResponse(
                    recommendation_type="EMI Planning",
                    priority="High",
                    impact_score=min(round(emi_share, 2), 95.0),
                    message="Plan EMI cash flow around the largest installment commitments.",
                    reason="EMIs are a major fixed component of the monthly budget.",
                    expected_benefit="Improves repayment predictability and reduces month-end pressure.",
                    action_required="Align EMI dates with income timing and review the largest installments first.",
                    estimated_effort=self._recommendation_effort("EMI Planning"),
                    estimated_monthly_saving=None,
                    estimated_annual_saving=None,
                    estimated_exposure_reduction=None,
                    financial_benefit=None,
                )
            )

        if bnpl_share >= 10 and bnpl is not None:
            recommendations.append(
                ExposureRecommendationResponse(
                    recommendation_type="BNPL Discipline",
                    priority="Medium",
                    impact_score=min(round(bnpl_share, 2), 90.0),
                    message="Keep BNPL usage aligned with short-term cash-flow planning.",
                    reason="BNPL commitments can build up quickly when multiple instalment plans are active.",
                    expected_benefit="Reduces the chance of overlapping instalments and keeps short-term obligations manageable.",
                    action_required="Avoid adding new BNPL plans until the current cycle becomes lighter.",
                    estimated_effort=self._recommendation_effort("BNPL Discipline"),
                    estimated_monthly_saving=None,
                    estimated_annual_saving=None,
                    estimated_exposure_reduction=None,
                    financial_benefit=None,
                )
            )

        if financial_health.risk_level in {"High", "Critical"}:
            monthly_saving, annual_saving, exposure_reduction, financial_benefit = _benefit(current_status.monthly_deficit if current_status.monthly_deficit > 0 else None)
            recommendations.append(
                ExposureRecommendationResponse(
                    recommendation_type="Financial Stability Review",
                    priority="Critical" if financial_health.risk_level == "Critical" else "High",
                    impact_score=92.0 if financial_health.risk_level == "Critical" else 84.0,
                    message="Review recurring commitments with a focus on the highest monthly obligations.",
                    reason="The combined exposure and payment profile indicate elevated risk.",
                    expected_benefit="Improves resilience and supports a more stable monthly budget.",
                    action_required="Compare the top commitments against your income timing and keep only the essential ones active.",
                    estimated_effort=self._recommendation_effort("Financial Stability Review"),
                    estimated_monthly_saving=monthly_saving,
                    estimated_annual_saving=annual_saving,
                    estimated_exposure_reduction=exposure_reduction,
                    financial_benefit=financial_benefit,
                )
            )

        if not any(rec.recommendation_type == "Maintain Current Discipline" for rec in recommendations) and exposure_score <= 100 and financial_health.financial_health_label in {"Excellent", "Healthy"}:
            recommendations.append(
                ExposureRecommendationResponse(
                    recommendation_type="Maintain Current Discipline",
                    priority="Low",
                    impact_score=96.0,
                    message="Maintain the current financial rhythm and keep tracking recurring commitments.",
                    reason="The user remains within capacity and payment behaviour is stable.",
                    expected_benefit="Preserves the current healthy financial position.",
                    action_required="Continue paying on time and review new commitments before activation.",
                    estimated_effort=self._recommendation_effort("Maintain Current Discipline"),
                    estimated_monthly_saving=None,
                    estimated_annual_saving=None,
                    estimated_exposure_reduction=None,
                    financial_benefit=None,
                )
            )

        recommendations.sort(key=lambda item: (-item.impact_score, item.priority))
        return recommendations

    @staticmethod
    def _trial_like_description(description: str) -> bool:
        keywords = {"trial", "promo", "promotional", "free", "intro", "introductory"}
        lower = description.lower()
        return any(keyword in lower for keyword in keywords)

    def _forecast_items_from_group(
        self,
        group: pd.DataFrame,
        forecast_type: str,
        title: str,
        expected_amount: float,
        confidence: float,
        note: str,
        source: str,
        evidence: list[str],
        expected_date: date | None,
    ) -> ForecastEventResponse:
        return ForecastEventResponse(
            forecast_type=forecast_type,
            title=title,
            expected_date=expected_date,
            expected_amount=round(expected_amount, 2),
            confidence=confidence,
            source=source,
            evidence=evidence,
            note=note,
        )

    def _build_forecast(
        self,
        frame: pd.DataFrame,
        subscription: SubscriptionIntelligenceResponse | None,
        emi: EmiIntelligenceResponse | None,
        bnpl: BnplIntelligenceResponse | None,
        monthly_capacity: float,
        current_total_commitments: float,
    ) -> FinancialForecastResponse:
        horizon_days = 30
        today = date.today()
        horizon_end = today + timedelta(days=horizon_days)
        upcoming_trial_conversions: list[ForecastEventResponse] = []
        upcoming_paid_subscriptions: list[ForecastEventResponse] = []
        upcoming_emi_commencements: list[ForecastEventResponse] = []
        upcoming_bnpl_installments: list[ForecastEventResponse] = []
        upcoming_autopay_charges: list[ForecastEventResponse] = []
        incremental_future_commitments = 0.0

        if not frame.empty:
            subscription_frame = frame[frame["transaction_class_normalized"] == "subscription"].copy()
            emi_frame = frame[frame["transaction_class_normalized"] == "emi"].copy()
            bnpl_frame = frame[frame["transaction_class_normalized"] == "bnpl"].copy()

            for merchant_name, group in subscription_frame.groupby("merchant_name", dropna=False):
                ordered = group.sort_values("transaction_date")
                latest = ordered.iloc[-1]
                latest_date = self._to_date(latest["transaction_date"])
                if latest_date is None:
                    continue
                next_due = (pd.Timestamp(latest_date) + self._forecast_offset(latest.get("frequency"))).date()
                monthly_amount = self._to_float(group["monthly_amount"].mean())
                if today <= next_due <= horizon_end:
                    event = self._forecast_items_from_group(
                        ordered,
                        "Upcoming Paid Subscription",
                        f"{self._normalize_text(merchant_name)} recurring charge due",
                        monthly_amount,
                        0.88,
                        "Based on the latest observed subscription cadence.",
                        "Subscription",
                        [f"latest_date={latest_date}", f"next_due={next_due}", f"frequency={self._normalize_text(latest.get('frequency'))}"],
                        next_due,
                    )
                    upcoming_paid_subscriptions.append(event)
                    incremental_future_commitments += monthly_amount
                    if bool(group["autopay_enabled_flag"].any()):
                        upcoming_autopay_charges.append(event)

                if self._trial_like_description(self._normalize_text(latest.get("description"))) or self._to_float(latest.get("amount_value")) <= 0.01:
                    expected_date = (pd.Timestamp(latest_date) + pd.DateOffset(days=30)).date()
                    if today <= expected_date <= horizon_end:
                        upcoming_trial_conversions.append(
                            self._forecast_items_from_group(
                                ordered,
                                "Upcoming Trial Conversion",
                                f"{self._normalize_text(merchant_name)} trial conversion likely",
                                monthly_amount,
                                0.8,
                                "Trial-style subscription activity suggests a future paid cycle may appear soon.",
                                "Subscription",
                                [f"trial_description={self._normalize_text(latest.get('description'))}", f"latest_date={latest_date}"],
                                expected_date,
                            )
                        )
                        incremental_future_commitments += monthly_amount

            for merchant_name, group in emi_frame.groupby("merchant_name", dropna=False):
                ordered = group.sort_values("transaction_date")
                latest = ordered.iloc[-1]
                latest_date = self._to_date(latest["transaction_date"])
                if latest_date is None:
                    continue
                next_due = (pd.Timestamp(latest_date) + self._forecast_offset(latest.get("frequency"))).date()
                monthly_amount = self._to_float(group["monthly_amount"].mean())
                if self._to_bool(latest.get("is_new_subscription")) or self._to_bool(group["is_new_subscription"].iloc[0] if "is_new_subscription" in group.columns else False):
                    commencement_date = next_due if today <= next_due <= horizon_end else None
                    if commencement_date is not None:
                        upcoming_emi_commencements.append(
                            self._forecast_items_from_group(
                                ordered,
                                "Upcoming EMI Commencement",
                                f"{self._normalize_text(merchant_name)} EMI cycle has started",
                                monthly_amount,
                                0.84,
                                "A recently started EMI plan is likely to continue into the next billing cycle.",
                                "EMI",
                                [f"first_date={self._to_date(ordered['transaction_date'].min())}", f"latest_date={latest_date}"],
                                commencement_date,
                            )
                        )
                    if commencement_date is not None:
                        incremental_future_commitments += monthly_amount

                if today <= next_due <= horizon_end and bool(group["autopay_enabled_flag"].any()):
                    event = self._forecast_items_from_group(
                        ordered,
                        "Upcoming AutoPay Charge",
                        f"{self._normalize_text(merchant_name)} installment due",
                        monthly_amount,
                        0.91,
                        "Based on the observed EMI installment cadence.",
                        "EMI",
                        [f"latest_date={latest_date}", f"next_due={next_due}", f"frequency={self._normalize_text(latest.get('frequency'))}"],
                        next_due,
                    )
                    upcoming_autopay_charges.append(event)

            for provider_name, group in bnpl_frame.groupby("merchant_name", dropna=False):
                ordered = group.sort_values("transaction_date")
                latest = ordered.iloc[-1]
                latest_date = self._to_date(latest["transaction_date"])
                if latest_date is None:
                    continue
                next_due = (pd.Timestamp(latest_date) + self._forecast_offset(latest.get("frequency"))).date()
                monthly_amount = self._to_float(group["monthly_amount"].mean())
                if today <= next_due <= horizon_end:
                    event = self._forecast_items_from_group(
                        ordered,
                        "Upcoming BNPL Installment",
                        f"{self._normalize_text(provider_name)} installment due",
                        monthly_amount,
                        0.9,
                        "Based on the latest observed BNPL installment cadence.",
                        "BNPL",
                        [f"latest_date={latest_date}", f"next_due={next_due}", f"frequency={self._normalize_text(latest.get('frequency'))}"],
                        next_due,
                    )
                    upcoming_bnpl_installments.append(event)
                    incremental_future_commitments += monthly_amount
                    if bool(group["autopay_enabled_flag"].any()):
                        upcoming_autopay_charges.append(event)

        future_monthly_commitments = round(current_total_commitments + incremental_future_commitments, 2)
        future_exposure_score = round(self._safe_divide(future_monthly_commitments * 100.0, monthly_capacity), 2) if monthly_capacity > 0 else 0.0
        exposure_increase = round(max(future_exposure_score - (self._safe_divide(current_total_commitments * 100.0, monthly_capacity) if monthly_capacity > 0 else 0.0), 0.0), 2)
        future_health_label = self._financial_health_label(self._future_health_score_from_projection(future_exposure_score))
        has_forecast_events = any([upcoming_trial_conversions, upcoming_paid_subscriptions, upcoming_emi_commencements, upcoming_bnpl_installments])
        if has_forecast_events:
            forecast_explanation = "Forecasted recurring commitments were detected within the next 30 days and are excluded from the current exposure score."
        else:
            forecast_explanation = "No upcoming recurring commitments were detected within the forecast horizon."

        preventive_recommendations = self._build_preventive_recommendations(
            upcoming_trial_conversions,
            upcoming_paid_subscriptions,
            upcoming_emi_commencements,
            upcoming_bnpl_installments,
            upcoming_autopay_charges,
            future_exposure_score,
        )

        forecast_notes = [
            "Forecast items are projections based on the latest observed transaction cadence.",
            "Forecasted values are not included in the current exposure calculation.",
        ]
        forecast_notes.append(forecast_explanation)

        return FinancialForecastResponse(
            upcoming_trial_conversions=upcoming_trial_conversions,
            upcoming_paid_subscriptions=upcoming_paid_subscriptions,
            upcoming_emi_commencements=upcoming_emi_commencements,
            upcoming_bnpl_installments=upcoming_bnpl_installments,
            upcoming_autopay_charges=upcoming_autopay_charges,
            future_monthly_commitments=future_monthly_commitments,
            future_exposure_score=future_exposure_score,
            exposure_increase=exposure_increase,
            future_financial_health=future_health_label,
            has_forecast_events=has_forecast_events,
            forecast_explanation=forecast_explanation,
            preventive_recommendations=preventive_recommendations,
            forecast_notes=forecast_notes,
        )

    @staticmethod
    def _future_health_score_from_projection(future_exposure_score: float) -> float:
        if future_exposure_score <= 25:
            return 92.0
        if future_exposure_score <= 50:
            return 80.0
        if future_exposure_score <= 75:
            return 65.0
        if future_exposure_score <= 100:
            return 48.0
        return 30.0

    def _build_preventive_recommendations(
        self,
        upcoming_trial_conversions: list[ForecastEventResponse],
        upcoming_paid_subscriptions: list[ForecastEventResponse],
        upcoming_emi_commencements: list[ForecastEventResponse],
        upcoming_bnpl_installments: list[ForecastEventResponse],
        upcoming_autopay_charges: list[ForecastEventResponse],
        future_exposure_score: float,
    ) -> list[ExposureRecommendationResponse]:
        recommendations: list[ExposureRecommendationResponse] = []

        if upcoming_trial_conversions:
            recommendations.append(
                ExposureRecommendationResponse(
                    recommendation_type="Trial Conversion Planning",
                    priority="Medium",
                    impact_score=72.0,
                    message="Prepare for the next subscription charge that follows a trial-style pattern.",
                    reason="A trial-like subscription pattern has been detected in the recent transaction history.",
                    expected_benefit="Helps the user budget for the first paid cycle before it starts.",
                    action_required="Set a reminder for the predicted conversion date and review whether the service is still needed.",
                    estimated_effort=self._recommendation_effort("Trial Conversion Planning"),
                )
            )

        if upcoming_paid_subscriptions:
            recommendations.append(
                ExposureRecommendationResponse(
                    recommendation_type="Subscription Timing",
                    priority="Medium",
                    impact_score=68.0,
                    message="Plan for the next subscription renewal within the forecast horizon.",
                    reason="Recurring subscription payments are expected to continue based on the latest observed cadence.",
                    expected_benefit="Smooths monthly cash flow and reduces surprise charges.",
                    action_required="Review recurring subscriptions that will renew soon and keep the necessary ones funded.",
                    estimated_effort=self._recommendation_effort("Subscription Timing"),
                )
            )

        if upcoming_emi_commencements:
            recommendations.append(
                ExposureRecommendationResponse(
                    recommendation_type="EMI Budgeting",
                    priority="High",
                    impact_score=80.0,
                    message="Reserve cash for the next EMI cycle before it hits the account.",
                    reason="A recent EMI start suggests additional installments will continue.",
                    expected_benefit="Reduces the chance of short-term cash-flow strain.",
                    action_required="Set aside the next EMI amount alongside monthly essential spending.",
                    estimated_effort=self._recommendation_effort("EMI Budgeting"),
                )
            )

        if upcoming_bnpl_installments:
            recommendations.append(
                ExposureRecommendationResponse(
                    recommendation_type="BNPL Installment Readiness",
                    priority="Medium",
                    impact_score=74.0,
                    message="Prepare for the next BNPL installment cycle and keep balances aligned.",
                    reason="Active BNPL plans will generate near-term installment obligations.",
                    expected_benefit="Keeps short-term repayment pressure manageable.",
                    action_required="Keep a small buffer available for the upcoming BNPL due dates.",
                    estimated_effort=self._recommendation_effort("BNPL Installment Readiness"),
                )
            )

        if upcoming_autopay_charges:
            recommendations.append(
                ExposureRecommendationResponse(
                    recommendation_type="AutoPay Coverage",
                    priority="Low",
                    impact_score=61.0,
                    message="Keep AutoPay enabled for recurring charges that are expected soon.",
                    reason="Several forecasted charges will route through AutoPay.",
                    expected_benefit="Improves payment continuity and reduces manual follow-up.",
                    action_required="Check that linked payment instruments remain active and sufficiently funded.",
                    estimated_effort=self._recommendation_effort("AutoPay Coverage"),
                )
            )

        if future_exposure_score > 100:
            recommendations.append(
                ExposureRecommendationResponse(
                    recommendation_type="Future Exposure Buffer",
                    priority="Critical",
                    impact_score=98.0,
                    message="Create additional headroom before the forecasted commitments arrive.",
                    reason="Projected future exposure exceeds current monthly capacity.",
                    expected_benefit="Prevents forecasted commitments from pushing the budget into deficit.",
                    action_required="Postpone new commitments and prepare a buffer for the next cycle.",
                    estimated_effort=self._recommendation_effort("Future Exposure Buffer"),
                )
            )

        recommendations.sort(key=lambda item: (-item.impact_score, item.priority))
        return recommendations

    def _call_intelligence(self, label: str, func: Any, user_id: str) -> Any | None:
        try:
            return func(user_id)
        except (SubscriptionNotFoundError, EmiNotFoundError, BnplNotFoundError):
            logger.info("%s analysis returned no active commitments for user_id=%s", label, user_id)
            return None
        except (SubscriptionProcessingError, EmiProcessingError, BnplProcessingError):
            raise

    def get_exposure_intelligence(self, user_id: str) -> ExposureIntelligenceResponse:
        logger.info("Exposure calculation started for user_id=%s", user_id)
        started_at = time.perf_counter()

        try:
            user_record = self._dataset_service.get_user(user_id)
            transactions = self._dataset_service.get_user_transactions(user_id)
            current_user = UserResponse(**user_record)

            current_frame = self._build_transaction_frame(transactions)
            self._current_frame = current_frame
            commitment_snapshot = UnifiedCommitmentService.snapshot_for_user(user_id)
            income_config = self._income_service.get_user_income_config(user_id)
            has_commitments = bool(commitment_snapshot.commitment_items)
            has_income = income_config is not None and (
                (income_config.income_mode == "manual" and (income_config.manual_monthly_income or 0) > 0)
                or (income_config.expected_monthly_income or 0) > 0
            )

            if not user_record.get("financial_profile") and not transactions and not has_commitments and not has_income:
                raise ExposureDataUnavailableError(f"No financial data available for user: {user_id}")

            subscription = self._call_intelligence("Subscription", self._subscription_service.get_subscription_intelligence, user_id)
            logger.info("Subscription analysis loaded for user_id=%s", user_id)
            emi = self._call_intelligence("EMI", self._emi_service.get_emi_intelligence, user_id)
            logger.info("EMI analysis loaded for user_id=%s", user_id)
            bnpl = self._call_intelligence("BNPL", self._bnpl_service.get_bnpl_intelligence, user_id)
            logger.info("BNPL analysis loaded for user_id=%s", user_id)

            monthly_capacity = self._to_float(user_record.get("monthly_financial_capacity"))
            if monthly_capacity <= 0 and user_record.get("financial_profile"):
                monthly_capacity = self._to_float(user_record["financial_profile"].get("monthly_financial_capacity"))
            if monthly_capacity <= 0 and not current_frame.empty:
                income_txs = current_frame[
                    (current_frame["category"].str.lower() == "income")
                    | (current_frame["transaction_class_normalized"].isin(["income", "salary"]))
                    | (current_frame["income_flag"].astype(str).str.lower().isin(["yes", "true", "1"]))
                ]
                if not income_txs.empty:
                    dt_series = pd.to_datetime(income_txs["transaction_date"], errors="coerce")
                    periods = dt_series.dt.to_period("M")
                    month_sums = income_txs.groupby(periods)["amount_value"].sum()
                    if not month_sums.empty:
                        monthly_capacity = round(float(month_sums.mean()), 2)

            auto_capacity = monthly_capacity
            effective_capacity, income_source_label, income_mode, expected_inc, manual_inc = self._income_service.resolve_effective_income(
                user_id, auto_capacity
            )
            monthly_capacity = effective_capacity

            use_unified = user_id.startswith("AUTH") or bool(commitment_snapshot.commitment_items)
            current_status, exposure_summary, available_capacity, breakdown, largest_contributor, largest_optional = self._build_current_status(
                subscription,
                emi,
                bnpl,
                monthly_capacity,
                commitment_snapshot.total_monthly_commitments if use_unified else None,
                commitment_snapshot.breakdown_by_category if use_unified else None,
                commitment_snapshot.commitment_items if use_unified else None,
                income_source=income_source_label,
                income_mode=income_mode,
                expected_monthly_income=expected_inc,
                manual_monthly_income=manual_inc,
            )

            financial_health = self._build_financial_health(
                current_status.exposure_score,
                subscription,
                emi,
                bnpl,
                current_status.monthly_total_commitments,
                current_status.monthly_financial_capacity,
            )
            logger.info("Health score calculated for user_id=%s score=%.2f label=%s", user_id, financial_health.financial_health_score, financial_health.financial_health_label)
            payment_context = self._build_payment_health_context(subscription, emi, bnpl)

            recommendations = self._build_recommendations(subscription, emi, bnpl, current_status, financial_health)
            logger.info("Recommendations generated for user_id=%s recommendation_count=%s", user_id, len(recommendations))

            forecast = self._build_forecast(current_frame, subscription, emi, bnpl, current_status.monthly_financial_capacity, current_status.monthly_total_commitments)
            logger.info("Forecast generated for user_id=%s", user_id)

            if current_status.monthly_total_commitments <= 0:
                current_status = current_status.model_copy(
                    update={
                        "current_message": "No recurring financial commitments detected. Maximum available monthly capacity.",
                        "exposure_score": 0.0,
                        "monthly_deficit": 0.0,
                        "overcommitted_percentage": 0.0,
                    }
                )
                exposure_summary = exposure_summary.model_copy(
                    update={
                        "exposure_score": 0.0,
                        "exposure_band": "Minimal",
                        "explanation": "No recurring financial commitments detected.",
                        "commitment_concentration": "No recurring commitments detected.",
                    }
                )
                financial_health = financial_health.model_copy(
                    update={
                        "financial_health_score": 100.0,
                        "financial_health_label": "Excellent",
                        "risk_level": "Low",
                    }
                )
                recommendations = [
                    ExposureRecommendationResponse(
                        recommendation_type="Maintain Current Discipline",
                        priority="Low",
                        impact_score=100.0,
                        message="Maintain the current no-commitment profile.",
                        reason="No recurring financial commitments are currently detected.",
                        expected_benefit="Preserves maximum available monthly capacity.",
                        action_required="Continue monitoring new recurring commitments before activating them.",
                        estimated_effort="Very Easy",
                        estimated_monthly_saving=None,
                        estimated_annual_saving=None,
                        estimated_exposure_reduction=None,
                        financial_benefit=None,
                    )
                ]
                forecast = FinancialForecastResponse(
                    upcoming_trial_conversions=[],
                    upcoming_paid_subscriptions=[],
                    upcoming_emi_commencements=[],
                    upcoming_bnpl_installments=[],
                    upcoming_autopay_charges=[],
                    future_monthly_commitments=0.0,
                    future_exposure_score=0.0,
                    exposure_increase=0.0,
                    future_financial_health="Excellent",
                    has_forecast_events=False,
                    forecast_explanation="No upcoming recurring commitments were detected within the forecast horizon.",
                    preventive_recommendations=[],
                    forecast_notes=[
                        "No recurring commitments detected.",
                        "Maximum available monthly capacity remains intact.",
                        "No upcoming recurring commitments were detected within the forecast horizon.",
                    ],
                )

            execution_time = time.perf_counter() - started_at

            return ExposureIntelligenceResponse(
                user_id=user_id,
                payment_reliability=round(payment_context["payment_success_rate"] / 100.0, 4),
                user_profile=current_user,
                current_financial_status=current_status,
                exposure_summary=exposure_summary,
                financial_health=financial_health,
                commitment_breakdown=breakdown,
                available_capacity=available_capacity,
                recommendations=recommendations,
                financial_forecast=forecast,
                metadata=ExposureMetadataResponse(
                    generated_at=datetime.now(timezone.utc),
                    execution_time_seconds=round(execution_time, 3),
                    data_sources=["Subscription Intelligence", "EMI Intelligence", "BNPL Intelligence"],
                    forecast_horizon_days=30,
                    engine_version="1.0.0",
                    rules_version="2026.1",
                    api_version="v1",
                ),
            )
        except UserNotFoundError as exc:
            raise ExposureNotFoundError(str(exc)) from exc
        except ExposureDataUnavailableError:
            raise
        except (SubscriptionProcessingError, EmiProcessingError, BnplProcessingError):
            raise
        except Exception as exc:  # pragma: no cover - defensive wrap for runtime issues
            logger.exception("Exposure calculation failed for user_id=%s", user_id)
            raise ExposureProcessingError(f"Unable to process financial exposure for user: {user_id}") from exc
        finally:
            elapsed_seconds = time.perf_counter() - started_at
            logger.info("Exposure calculation finished for user_id=%s execution_time_seconds=%.3f", user_id, elapsed_seconds)


@lru_cache(maxsize=1)
def get_exposure_service(dataset_service: DatasetService = Depends(get_dataset_service)) -> ExposureService:
    if not isinstance(dataset_service, DatasetService):
        dataset_service = get_dataset_service()
    return ExposureService(
        dataset_service=dataset_service,
        subscription_service=SubscriptionService(dataset_service),
        emi_service=EmiService(dataset_service),
        bnpl_service=BnplService(dataset_service),
        income_service=get_income_service(),
    )
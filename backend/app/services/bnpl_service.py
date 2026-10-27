from __future__ import annotations

import logging
import re
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any

import pandas as pd
from fastapi import Depends

from app.core.exceptions import BnplNotFoundError, BnplProcessingError, UserNotFoundError
from app.schemas.bnpl import (
    ActiveBnplResponse,
    BnplCostItemResponse,
    BnplInsightResponse,
    BnplIntelligenceResponse,
    BnplSummaryResponse,
    FinancialStatisticsResponse,
    PaymentStatisticsResponse,
)
from app.schemas.subscription import TransactionStatusSummaryResponse
from app.services.dataset_service import DatasetService, get_dataset_service
from app.services.financial_rules import (
    TransactionStatus,
    classify_transaction_status,
    commitment_amount,
    monthly_multiplier,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FrequencyRule:
    label: str
    monthly_multiplier: float


class BnplService:
    _frequency_rules: tuple[FrequencyRule, ...] = (
        FrequencyRule("weekly", 52.0 / 12.0),
        FrequencyRule("biweekly", 26.0 / 12.0),
        FrequencyRule("fortnightly", 26.0 / 12.0),
        FrequencyRule("monthly", 1.0),
        FrequencyRule("installment", 1.0),
        FrequencyRule("instalment", 1.0),
        FrequencyRule("quarterly", 1.0 / 3.0),
        FrequencyRule("semiannual", 1.0 / 6.0),
        FrequencyRule("annual", 1.0 / 12.0),
        FrequencyRule("yearly", 1.0 / 12.0),
    )

    def __init__(self, dataset_service: DatasetService) -> None:
        self._dataset_service = dataset_service

    @staticmethod
    def _normalize_text(value: Any) -> str:
        if value is None or pd.isna(value):
            return ""
        return str(value).strip()

    @staticmethod
    def _normalize_lower(value: Any) -> str:
        return BnplService._normalize_text(value).lower()

    @staticmethod
    def _to_float(value: Any) -> float:
        if value is None or pd.isna(value):
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _to_bool(value: Any) -> bool:
        return BnplService._normalize_lower(value) in {"yes", "true", "1", "y"}

    @staticmethod
    def _to_date(value: Any) -> Any:
        if isinstance(value, pd.Timestamp):
            return value.date()
        if hasattr(value, "date") and callable(value.date):
            return value.date()
        return value

    @classmethod
    def _monthly_multiplier(cls, frequency: Any) -> float:
        return monthly_multiplier(frequency)

    @classmethod
    def _dominant_value(cls, values: pd.Series, default: str = "Mixed") -> str:
        normalized = [cls._normalize_text(value) for value in values if cls._normalize_text(value)]
        if not normalized:
            return default
        counts = Counter(normalized)
        most_common = counts.most_common()
        if len(most_common) == 1:
            return most_common[0][0]
        if most_common[0][1] == most_common[1][1]:
            return default
        return most_common[0][0]

    @classmethod
    def _dominant_commitment_type(cls, values: pd.Series) -> str:
        normalized = [cls._normalize_lower(value) for value in values if cls._normalize_text(value)]
        if not normalized:
            return "Unknown"
        if "mandatory" in normalized:
            return "Mandatory"
        if "optional" in normalized:
            return "Optional"
        return cls._dominant_value(values, default="Unknown")

    @classmethod
    def _status_summary(cls, frame: pd.DataFrame) -> TransactionStatusSummaryResponse:
        breakdown = {
            str(index): int(value)
            for index, value in frame["transaction_status"].fillna("Unknown").value_counts(dropna=False).sort_index().items()
        }
        successful = sum(count for status, count in breakdown.items() if classify_transaction_status(status) is TransactionStatus.SUCCESSFUL)
        failed = sum(count for status, count in breakdown.items() if classify_transaction_status(status) is TransactionStatus.FAILED)
        pending = sum(count for status, count in breakdown.items() if classify_transaction_status(status) is TransactionStatus.PENDING)
        other = max(int(frame.shape[0]) - successful - failed - pending, 0)
        return TransactionStatusSummaryResponse(
            status_breakdown=breakdown,
            successful_transactions=successful,
            failed_transactions=failed,
            pending_transactions=pending,
            other_transactions=other,
        )

    @staticmethod
    def _parse_installment_count(description: Any) -> int:
        text = BnplService._normalize_lower(description)
        if not text:
            return 0
        match = re.search(r"(?:installment|instalment)?\s*(\d+)\s*/\s*(\d+)", text)
        if match:
            return int(match.group(2))
        match = re.search(r"(?:installment|instalment)\s*(\d+)", text)
        if match:
            return int(match.group(1))
        return 0

    @classmethod
    def _infer_provider_type(cls, provider_name: str, category: Any, description: Any) -> str:
        text = " ".join(
            part
            for part in (
                cls._normalize_text(provider_name),
                cls._normalize_text(category),
                cls._normalize_text(description),
            )
            if part
        ).lower()
        rules: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("Pay Later", ("pay later", "postpaid", "credit line", "zip", "post pay")),
            ("Merchant BNPL", ("amazon", "flipkart", "lazy", "simpl", "slice", "kreditbee", "cashe", "zestmoney", "mobikwik", "paytm", "navi", "phonepe", "moneyview")),
            ("Utility BNPL", ("utility", "bill", "recharge")),
        )
        for label, keywords in rules:
            if any(keyword in text for keyword in keywords):
                return label
        return "BNPL"

    @classmethod
    def _prepare_bnpl_frame(cls, transactions: list[dict[str, Any]]) -> pd.DataFrame:
        frame = pd.DataFrame(transactions)
        if frame.empty:
            return frame

        prepared = frame.copy()
        prepared["transaction_date"] = pd.to_datetime(prepared["transaction_date"], errors="coerce")
        prepared["transaction_class_normalized"] = prepared["transaction_class"].map(cls._normalize_lower)
        prepared = prepared[prepared["transaction_class_normalized"] == "bnpl"].copy()
        if prepared.empty:
            return prepared

        prepared["amount_value"] = pd.to_numeric(prepared["amount"], errors="coerce").fillna(0.0).map(commitment_amount)
        prepared["frequency_normalized"] = prepared["frequency"].map(cls._normalize_lower)
        prepared["payment_frequency"] = prepared["frequency"].map(lambda value: cls._normalize_text(value).title() if cls._normalize_text(value) else "Unknown")
        prepared["autopay_enabled_flag"] = prepared["autopay_flag"].map(cls._to_bool)
        prepared["commitment_type_normalized"] = prepared["commitment_type"].map(cls._normalize_text)
        prepared["monthly_multiplier"] = prepared["frequency_normalized"].map(cls._monthly_multiplier)
        prepared["monthly_bnpl_commitment_row"] = prepared["amount_value"] * prepared["monthly_multiplier"]
        prepared["provider_name_normalized"] = prepared["merchant_name"].map(cls._normalize_text)
        prepared["installment_count"] = prepared["description"].map(cls._parse_installment_count)
        prepared["provider_type"] = prepared.apply(
            lambda row: cls._infer_provider_type(row["provider_name_normalized"], row.get("category"), row.get("description")),
            axis=1,
        )
        return prepared

    @staticmethod
    def _safe_divide(numerator: float, denominator: float) -> float:
        if denominator == 0:
            return 0.0
        return numerator / denominator

    def _build_active_bnpl(self, provider_name: str, frame: pd.DataFrame) -> dict[str, Any]:
        average_commitment = self._to_float(frame["monthly_bnpl_commitment_row"].mean())
        total_paid = self._to_float(frame["amount_value"].sum())
        inferred_installments = int(frame["installment_count"].max()) if int(frame["installment_count"].max()) > 0 else int(frame.shape[0])
        total_borrowed = round(max(total_paid, average_commitment * inferred_installments), 2)
        return {
            "provider_name": provider_name,
            "first_transaction_date": self._to_date(frame["transaction_date"].min()),
            "latest_transaction_date": self._to_date(frame["transaction_date"].max()),
            "number_of_installments": inferred_installments,
            "monthly_bnpl_commitment": round(average_commitment, 2),
            "total_amount_borrowed": total_borrowed,
            "total_amount_paid": round(total_paid, 2),
            "autopay_enabled": bool(frame["autopay_enabled_flag"].any()),
            "payment_frequency": self._dominant_value(frame["payment_frequency"], default="Unknown"),
            "commitment_type": self._dominant_commitment_type(frame["commitment_type_normalized"]),
            "transaction_status_summary": self._status_summary(frame).model_dump(),
        }

    def _build_bnpl_summary(self, active_rows: list[dict[str, Any]]) -> BnplSummaryResponse:
        if not active_rows:
            return BnplSummaryResponse(
                active_provider_count=0,
                total_active_bnpl_accounts=0,
                monthly_bnpl_burden=0.0,
                annual_bnpl_burden=0.0,
                average_bnpl_amount=0.0,
                highest_provider_exposure=None,
                lowest_provider_exposure=None,
            )

        monthly_burden = sum(row["monthly_bnpl_commitment"] for row in active_rows)
        ordered = sorted(active_rows, key=lambda row: (row["monthly_bnpl_commitment"], row["provider_name"]))
        average_monthly_amount = monthly_burden / len(active_rows)
        return BnplSummaryResponse(
            active_provider_count=len(active_rows),
            total_active_bnpl_accounts=len(active_rows),
            monthly_bnpl_burden=round(monthly_burden, 2),
            annual_bnpl_burden=round(monthly_burden * 12.0, 2),
            average_bnpl_amount=round(average_monthly_amount, 2),
            highest_provider_exposure=BnplCostItemResponse(
                provider_name=ordered[-1]["provider_name"],
                monthly_bnpl_commitment=round(ordered[-1]["monthly_bnpl_commitment"], 2),
                total_amount_borrowed=round(ordered[-1]["total_amount_borrowed"], 2),
            ),
            lowest_provider_exposure=BnplCostItemResponse(
                provider_name=ordered[0]["provider_name"],
                monthly_bnpl_commitment=round(ordered[0]["monthly_bnpl_commitment"], 2),
                total_amount_borrowed=round(ordered[0]["total_amount_borrowed"], 2),
            ),
        )

    def _build_payment_statistics(self, active_rows: list[dict[str, Any]], frame: pd.DataFrame) -> PaymentStatisticsResponse:
        status_summary = self._status_summary(frame)
        total_payments = int(frame.shape[0])
        successful_payments = status_summary.successful_transactions
        failed_payments = status_summary.failed_transactions
        pending_payments = status_summary.pending_transactions
        success_rate = round(self._safe_divide(successful_payments * 100.0, total_payments), 2)
        autopay_count = sum(1 for row in active_rows if row["autopay_enabled"])
        autopay_coverage = round(self._safe_divide(autopay_count * 100.0, len(active_rows)), 2)
        return PaymentStatisticsResponse(
            successful_payments=successful_payments,
            failed_payments=failed_payments,
            pending_payments=pending_payments,
            success_rate=success_rate,
            autopay_coverage=autopay_coverage,
            transaction_status_summary=status_summary,
        )

    def _build_financial_statistics(self, monthly_burden: float, monthly_capacity: float) -> FinancialStatisticsResponse:
        ratio = self._safe_divide(monthly_burden, monthly_capacity)
        burden_percent = round(ratio * 100.0, 2)
        exposure_contribution = round(self._safe_divide(monthly_burden * 100.0, monthly_burden + monthly_capacity), 2)
        return FinancialStatisticsResponse(
            monthly_financial_capacity=round(monthly_capacity, 2),
            bnpl_to_capacity_ratio=round(ratio, 4),
            monthly_bnpl_burden_percent=burden_percent,
            bnpl_contribution_towards_financial_exposure=exposure_contribution,
        )

    @staticmethod
    def _severity_rank(severity: str) -> int:
        return {"high": 0, "medium": 1, "low": 2}.get(severity.lower(), 3)

    def _build_insights(
        self,
        active_rows: list[dict[str, Any]],
        monthly_burden: float,
        monthly_capacity: float,
        payment_statistics: PaymentStatisticsResponse,
        frame: pd.DataFrame,
    ) -> list[BnplInsightResponse]:
        if not active_rows:
            return []

        insights: list[BnplInsightResponse] = []
        ratio = self._safe_divide(monthly_burden, monthly_capacity)
        active_count = len(active_rows)
        total_transactions = int(frame.shape[0])
        total_installments = sum(row["number_of_installments"] for row in active_rows)
        provider_shares = {row["provider_name"]: row["monthly_bnpl_commitment"] for row in active_rows}
        top_provider = max(provider_shares.items(), key=lambda item: item[1])
        top_provider_share = self._safe_divide(top_provider[1], monthly_burden)
        repeated_bnpl_usage = total_transactions >= 6 or total_installments >= 8

        if ratio >= 0.25:
            insights.append(
                BnplInsightResponse(
                    insight_type="High BNPL To Capacity Ratio",
                    message=f"BNPL obligations consume {round(ratio * 100.0, 1)}% of monthly financial capacity.",
                    severity="high",
                    confidence=0.96,
                    evidence=[f"monthly_bnpl_burden={round(monthly_burden, 2)}", f"monthly_financial_capacity={round(monthly_capacity, 2)}", f"ratio={round(ratio, 4)}"],
                )
            )
        elif ratio >= 0.15:
            insights.append(
                BnplInsightResponse(
                    insight_type="High BNPL Burden",
                    message=f"Monthly BNPL burden uses {round(ratio * 100.0, 1)}% of monthly financial capacity.",
                    severity="medium",
                    confidence=0.93,
                    evidence=[f"monthly_bnpl_burden={round(monthly_burden, 2)}", f"monthly_financial_capacity={round(monthly_capacity, 2)}"],
                )
            )

        if active_count >= 3 or monthly_burden >= monthly_capacity * 0.1:
            insights.append(
                BnplInsightResponse(
                    insight_type="Heavy BNPL User",
                    message="The BNPL portfolio is broad enough to require close monitoring of fixed commitments.",
                    severity="medium",
                    confidence=0.91,
                    evidence=[f"active_provider_count={active_count}", f"monthly_bnpl_burden={round(monthly_burden, 2)}"],
                )
            )

        if active_count >= 2:
            insights.append(
                BnplInsightResponse(
                    insight_type="Multiple BNPL Providers",
                    message="The user is using BNPL across multiple providers, which increases repayment complexity.",
                    severity="medium",
                    confidence=0.9,
                    evidence=sorted(row["provider_name"] for row in active_rows),
                )
            )

        if repeated_bnpl_usage:
            insights.append(
                BnplInsightResponse(
                    insight_type="Repeated BNPL Usage",
                    message="The transaction pattern shows repeated BNPL instalments or sustained BNPL use.",
                    severity="medium",
                    confidence=0.88,
                    evidence=[f"total_transactions={total_transactions}", f"total_installments={total_installments}"],
                )
            )

        if any(self._normalize_lower(row["commitment_type"]) == "mandatory" and not row["autopay_enabled"] for row in active_rows):
            non_autopay_providers = sorted(
                row["provider_name"]
                for row in active_rows
                if self._normalize_lower(row["commitment_type"]) == "mandatory" and not row["autopay_enabled"]
            )
            insights.append(
                BnplInsightResponse(
                    insight_type="Mandatory BNPL Without AutoPay",
                    message="At least one mandatory BNPL provider is not protected by autopay.",
                    severity="high",
                    confidence=0.95,
                    evidence=non_autopay_providers,
                )
            )

        if active_count == 1:
            insights.append(
                BnplInsightResponse(
                    insight_type="Single Provider Concentration",
                    message="The BNPL portfolio is concentrated in a single provider.",
                    severity="medium",
                    confidence=0.9,
                    evidence=[active_rows[0]["provider_name"]],
                )
            )

        if active_count >= 3 and top_provider_share >= 0.5:
            insights.append(
                BnplInsightResponse(
                    insight_type="Provider Diversification Risk",
                    message="A single BNPL provider dominates the portfolio despite multiple active providers.",
                    severity="medium",
                    confidence=0.89,
                    evidence=[f"dominant_provider={top_provider[0]}", f"share={round(top_provider_share, 2)}"],
                )
            )

        small_bNpl_rows = [row for row in active_rows if row["monthly_bnpl_commitment"] <= 2500.0]
        if len(small_bNpl_rows) >= 3:
            insights.append(
                BnplInsightResponse(
                    insight_type="Frequent Small Purchases Using BNPL",
                    message="The portfolio is composed of several small BNPL commitments that can accumulate quickly.",
                    severity="low",
                    confidence=0.87,
                    evidence=sorted(row["provider_name"] for row in small_bNpl_rows),
                )
            )

        if total_installments >= 10 and active_count >= 2:
            insights.append(
                BnplInsightResponse(
                    insight_type="BNPL Dependency Increasing",
                    message="Multiple installment commitments suggest growing dependence on BNPL for cash-flow smoothing.",
                    severity="medium",
                    confidence=0.86,
                    evidence=[f"total_installments={total_installments}", f"active_provider_count={active_count}"],
                )
            )

        if monthly_capacity > 0 and monthly_burden <= monthly_capacity * 0.1 and payment_statistics.success_rate >= 90.0:
            insights.append(
                BnplInsightResponse(
                    insight_type="Healthy BNPL Portfolio",
                    message="The BNPL burden is contained relative to monthly financial capacity and payment performance is strong.",
                    severity="low",
                    confidence=0.94,
                    evidence=[f"monthly_bnpl_burden={round(monthly_burden, 2)}", f"monthly_financial_capacity={round(monthly_capacity, 2)}", f"success_rate={payment_statistics.success_rate}"],
                )
            )

        insights.sort(key=lambda item: (self._severity_rank(item.severity), item.insight_type))
        return insights

    def get_bnpl_intelligence(self, user_id: str) -> BnplIntelligenceResponse:
        logger.info("BNPL analysis started for user_id=%s", user_id)
        started_at = time.perf_counter()

        try:
            user_record = self._dataset_service.get_user(user_id)
            transactions = self._dataset_service.get_user_transactions(user_id)
            logger.info("Transactions loaded for user_id=%s total_transactions=%s", user_id, len(transactions))

            if not transactions:
                raise BnplNotFoundError(f"No BNPL transactions found for user: {user_id}")

            bnpl_frame = self._prepare_bnpl_frame(transactions)
            if bnpl_frame.empty:
                raise BnplNotFoundError(f"No BNPL transactions found for user: {user_id}")

            bnpl_frame = bnpl_frame.dropna(subset=["transaction_date"]).copy()
            if bnpl_frame.empty:
                raise BnplNotFoundError(f"No BNPL transactions found for user: {user_id}")

            bnpl_frame = bnpl_frame.sort_values(["provider_name_normalized", "transaction_date"])
            active_rows = [self._build_active_bnpl(provider_name, group) for provider_name, group in bnpl_frame.groupby("provider_name_normalized", dropna=False)]
            active_rows = sorted(active_rows, key=lambda row: (row["monthly_bnpl_commitment"], row["provider_name"]), reverse=True)

            bnpl_summary = self._build_bnpl_summary(active_rows)
            logger.info("BNPL accounts detected for user_id=%s active_provider_count=%s monthly_bnpl_burden=%.2f", user_id, bnpl_summary.active_provider_count, bnpl_summary.monthly_bnpl_burden)

            payment_statistics = self._build_payment_statistics(active_rows, bnpl_frame)
            monthly_capacity = self._to_float(user_record.get("monthly_financial_capacity"))
            financial_statistics = self._build_financial_statistics(bnpl_summary.monthly_bnpl_burden, monthly_capacity)
            bnpl_insights = self._build_insights(active_rows, bnpl_summary.monthly_bnpl_burden, monthly_capacity, payment_statistics, bnpl_frame)
            logger.info("Insights generated for user_id=%s insight_count=%s", user_id, len(bnpl_insights))

            return BnplIntelligenceResponse(
                user_id=user_id,
                bnpl_summary=bnpl_summary,
                active_bnpl_accounts=[ActiveBnplResponse(**row) for row in active_rows],
                payment_statistics=payment_statistics,
                financial_statistics=financial_statistics,
                bnpl_insights=bnpl_insights,
            )
        except UserNotFoundError:
            raise
        except BnplNotFoundError:
            raise
        except Exception as exc:  # pragma: no cover - defensive wrap for runtime issues
            logger.exception("BNPL intelligence processing failed for user_id=%s", user_id)
            raise BnplProcessingError(f"Unable to process BNPL intelligence for user: {user_id}") from exc
        finally:
            elapsed_seconds = time.perf_counter() - started_at
            logger.info("BNPL analysis finished for user_id=%s execution_time_seconds=%.3f", user_id, elapsed_seconds)


def get_bnpl_service(dataset_service: DatasetService = Depends(get_dataset_service)) -> BnplService:
    return BnplService(dataset_service)
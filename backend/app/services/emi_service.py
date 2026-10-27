from __future__ import annotations

import logging
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any

import pandas as pd
from fastapi import Depends

from app.core.exceptions import EmiNotFoundError, EmiProcessingError, UserNotFoundError
from app.schemas.emi import (
    ActiveEmiResponse,
    EmiCostItemResponse,
    EmiInsightResponse,
    EmiIntelligenceResponse,
    EmiSummaryResponse,
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


class EmiService:
    _frequency_rules: tuple[FrequencyRule, ...] = (
        FrequencyRule("weekly", 52.0 / 12.0),
        FrequencyRule("biweekly", 26.0 / 12.0),
        FrequencyRule("fortnightly", 26.0 / 12.0),
        FrequencyRule("monthly", 1.0),
        FrequencyRule("quarterly", 1.0 / 3.0),
        FrequencyRule("semiannual", 1.0 / 6.0),
        FrequencyRule("annual", 1.0 / 12.0),
        FrequencyRule("yearly", 1.0 / 12.0),
        FrequencyRule("daily", 365.0 / 12.0),
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
        return EmiService._normalize_text(value).lower()

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
        return EmiService._normalize_lower(value) in {"yes", "true", "1", "y"}

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
    def _frequency_label(cls, value: Any) -> str:
        text = cls._normalize_text(value)
        if not text:
            return "Unknown"
        return text.title()

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

    @classmethod
    def _loan_type_from_text(cls, text: str) -> str:
        normalized = cls._normalize_lower(text)
        rules: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("Home Loan", ("home loan", "housing loan", "house loan", "mortgage")),
            ("Car Loan", ("car loan", "car emi", "sedan", "hatchback")),
            ("Bike Loan", ("bike loan", "two wheeler", "scooter", "motorcycle")),
            ("Phone Loan", ("phone loan", "mobile loan", "smartphone", "phone emi", "mobile emi")),
            ("Laptop Loan", ("laptop loan", "notebook", "macbook", "ultrabook")),
            ("Education Loan", ("education loan", "student loan", "study loan", "tuition")),
            ("Gold Loan", ("gold loan", "gold emi")),
            ("Consumer Durable Loan", ("consumer durable", "device loan", "electronics emi", "appliance emi", "gadget loan", "home appliance")),
            ("Personal Loan", ("personal loan",)),
            ("Medical Loan", ("medical loan", "medical emi", "hospital loan", "health loan")),
            ("Wedding Loan", ("wedding loan", "marriage loan")),
            ("Land Loan", ("land loan", "plot loan")),
            ("Vehicle Loan", ("vehicle loan", "vehicle emi", "auto loan", "ev emi", "ev loan")),
            ("Lifestyle Loan", ("lifestyle", "lifestyle emi")),
            ("Consumer Durable Loan", ("furniture", "electronics emi", "home appliance emi")),
        )
        for loan_type, keywords in rules:
            if any(keyword in normalized for keyword in keywords):
                return loan_type
        return "Other Loan"

    @classmethod
    def _loan_type_for_row(cls, row: pd.Series) -> str:
        raw_fields = [
            row.get("merchant_type"),
            row.get("category"),
            row.get("merchant_name"),
            row.get("description"),
        ]
        raw_text = " ".join(field for field in (cls._normalize_text(value) for value in raw_fields) if field)
        loan_type = cls._loan_type_from_text(raw_text)
        if loan_type != "Other Loan":
            return loan_type

        merchant_type = cls._normalize_text(row.get("merchant_type"))
        if merchant_type and cls._normalize_lower(merchant_type) != "loans":
            return merchant_type.title()

        category = cls._normalize_text(row.get("category"))
        if category:
            category_lower = cls._normalize_lower(category)
            if category_lower in {"loan emi", "loans"}:
                return "Other Loan"
            if category_lower.endswith(" emi"):
                return category[:-4].strip().title() + " Loan"
            return category.title()

        return "Other Loan"

    @classmethod
    def _prepare_emi_frame(cls, transactions: list[dict[str, Any]]) -> pd.DataFrame:
        frame = pd.DataFrame(transactions)
        if frame.empty:
            return frame

        prepared = frame.copy()
        prepared["transaction_date"] = pd.to_datetime(prepared["transaction_date"], errors="coerce")
        prepared["transaction_class_normalized"] = prepared["transaction_class"].map(cls._normalize_lower)
        prepared = prepared[prepared["transaction_class_normalized"] == "emi"].copy()
        if prepared.empty:
            return prepared

        prepared["amount_value"] = pd.to_numeric(prepared["amount"], errors="coerce").fillna(0.0).map(commitment_amount)
        prepared["frequency_normalized"] = prepared["frequency"].map(cls._normalize_lower)
        prepared["payment_frequency"] = prepared["frequency"].map(cls._frequency_label)
        prepared["autopay_enabled_flag"] = prepared["autopay_flag"].map(cls._to_bool)
        prepared["commitment_type_normalized"] = prepared["commitment_type"].map(cls._normalize_text)
        prepared["monthly_multiplier"] = prepared["frequency_normalized"].map(cls._monthly_multiplier)
        prepared["monthly_emi_amount_row"] = prepared["amount_value"] * prepared["monthly_multiplier"]
        prepared["merchant_name_normalized"] = prepared["merchant_name"].map(cls._normalize_text)
        prepared["loan_type"] = prepared.apply(lambda row: cls._loan_type_for_row(row), axis=1)
        return prepared

    @staticmethod
    def _safe_divide(numerator: float, denominator: float) -> float:
        if denominator == 0:
            return 0.0
        return numerator / denominator

    def _build_active_emi(self, merchant_name: str, frame: pd.DataFrame) -> dict[str, Any]:
        monthly_amount = self._to_float(frame["monthly_emi_amount_row"].mean())
        total_paid = self._to_float(frame["amount_value"].sum())
        loan_type = self._dominant_value(frame["loan_type"], default="Other Loan")
        commitment_type = self._dominant_commitment_type(frame["commitment_type_normalized"])
        return {
            "merchant_name": merchant_name,
            "loan_type": loan_type,
            "first_emi_date": self._to_date(frame["transaction_date"].min()),
            "latest_emi_date": self._to_date(frame["transaction_date"].max()),
            "number_of_emi_payments": int(frame.shape[0]),
            "monthly_emi_amount": round(monthly_amount, 2),
            "total_amount_paid": round(total_paid, 2),
            "autopay_enabled": bool(frame["autopay_enabled_flag"].any()),
            "payment_frequency": self._dominant_value(frame["payment_frequency"], default="Unknown"),
            "commitment_type": commitment_type,
            "transaction_status_summary": self._status_summary(frame).model_dump(),
        }

    def _build_emi_summary(self, active_rows: list[dict[str, Any]]) -> EmiSummaryResponse:
        if not active_rows:
            return EmiSummaryResponse(
                active_emi_count=0,
                monthly_emi_burden=0.0,
                annual_emi_burden=0.0,
                average_emi_amount=0.0,
                highest_emi=None,
                lowest_emi=None,
                mandatory_emi_count=0,
                optional_emi_count=0,
            )

        monthly_burden = sum(row["monthly_emi_amount"] for row in active_rows)
        ordered = sorted(active_rows, key=lambda row: (row["monthly_emi_amount"], row["merchant_name"]))
        average_monthly_amount = monthly_burden / len(active_rows)
        mandatory_count = sum(1 for row in active_rows if self._normalize_lower(row["commitment_type"]) == "mandatory")
        optional_count = sum(1 for row in active_rows if self._normalize_lower(row["commitment_type"]) == "optional")
        return EmiSummaryResponse(
            active_emi_count=len(active_rows),
            monthly_emi_burden=round(monthly_burden, 2),
            annual_emi_burden=round(monthly_burden * 12.0, 2),
            average_emi_amount=round(average_monthly_amount, 2),
            highest_emi=EmiCostItemResponse(
                merchant_name=ordered[-1]["merchant_name"],
                loan_type=ordered[-1]["loan_type"],
                monthly_emi_amount=round(ordered[-1]["monthly_emi_amount"], 2),
                total_amount_paid=round(ordered[-1]["total_amount_paid"], 2),
            ),
            lowest_emi=EmiCostItemResponse(
                merchant_name=ordered[0]["merchant_name"],
                loan_type=ordered[0]["loan_type"],
                monthly_emi_amount=round(ordered[0]["monthly_emi_amount"], 2),
                total_amount_paid=round(ordered[0]["total_amount_paid"], 2),
            ),
            mandatory_emi_count=mandatory_count,
            optional_emi_count=optional_count,
        )

    def _build_payment_statistics(self, active_rows: list[dict[str, Any]], frame: pd.DataFrame) -> PaymentStatisticsResponse:
        status_summary = self._status_summary(frame)
        total_payments = int(frame.shape[0])
        successful_payments = status_summary.successful_transactions
        failed_payments = status_summary.failed_transactions
        pending_payments = status_summary.pending_transactions
        payment_success_rate = round(self._safe_divide(successful_payments * 100.0, total_payments), 2)
        autopay_count = sum(1 for row in active_rows if row["autopay_enabled"])
        autopay_coverage = round(self._safe_divide(autopay_count * 100.0, len(active_rows)), 2)
        return PaymentStatisticsResponse(
            successful_payments=successful_payments,
            failed_payments=failed_payments,
            pending_payments=pending_payments,
            payment_success_rate=payment_success_rate,
            autopay_coverage=autopay_coverage,
            transaction_status_summary=status_summary,
        )

    def _build_financial_statistics(self, monthly_burden: float, monthly_capacity: float) -> FinancialStatisticsResponse:
        ratio = self._safe_divide(monthly_burden, monthly_capacity)
        burden_percent = round(ratio * 100.0, 2)
        exposure_contribution = round(self._safe_divide(monthly_burden * 100.0, monthly_burden + monthly_capacity), 2)
        return FinancialStatisticsResponse(
            monthly_financial_capacity=round(monthly_capacity, 2),
            monthly_emi_burden=round(monthly_burden, 2),
            annual_emi_burden=round(monthly_burden * 12.0, 2),
            emi_to_monthly_capacity_ratio=round(ratio, 4),
            monthly_emi_burden_percent=burden_percent,
            contribution_of_emi_towards_financial_exposure=exposure_contribution,
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
    ) -> list[EmiInsightResponse]:
        if not active_rows:
            return []

        insights: list[EmiInsightResponse] = []
        active_count = len(active_rows)
        ratio = self._safe_divide(monthly_burden, monthly_capacity)
        loan_types = {row["loan_type"] for row in active_rows}
        top_loan_type = max(
            ((loan_type, sum(row["monthly_emi_amount"] for row in active_rows if row["loan_type"] == loan_type)) for loan_type in loan_types),
            key=lambda item: item[1],
            default=("Other Loan", 0.0),
        )
        top_loan_share = self._safe_divide(top_loan_type[1], monthly_burden)

        if ratio >= 0.25:
            insights.append(
                EmiInsightResponse(
                    insight_type="High EMI To Financial Capacity Ratio",
                    message=f"EMI obligations consume {round(ratio * 100.0, 1)}% of monthly financial capacity.",
                    severity="high",
                    confidence=0.96,
                    evidence=[f"monthly_emi_burden={round(monthly_burden, 2)}", f"monthly_financial_capacity={round(monthly_capacity, 2)}", f"ratio={round(ratio, 4)}"],
                )
            )
        elif ratio >= 0.15:
            insights.append(
                EmiInsightResponse(
                    insight_type="High Monthly EMI Burden",
                    message=f"Monthly EMI burden uses {round(ratio * 100.0, 1)}% of monthly financial capacity.",
                    severity="medium",
                    confidence=0.93,
                    evidence=[f"monthly_emi_burden={round(monthly_burden, 2)}", f"monthly_financial_capacity={round(monthly_capacity, 2)}"],
                )
            )

        if active_count >= 5 or ratio >= 0.2:
            insights.append(
                EmiInsightResponse(
                    insight_type="Heavy EMI User",
                    message="The EMI portfolio is broad enough to warrant close monitoring of fixed monthly obligations.",
                    severity="medium",
                    confidence=0.9,
                    evidence=[f"active_emi_count={active_count}", f"monthly_emi_burden={round(monthly_burden, 2)}"],
                )
            )

        if active_count >= 3:
            insights.append(
                EmiInsightResponse(
                    insight_type="Multiple Simultaneous EMIs",
                    message="The user has multiple active EMI commitments running in parallel.",
                    severity="medium",
                    confidence=0.9,
                    evidence=[f"active_emi_count={active_count}"],
                )
            )

        if any(self._normalize_lower(row["commitment_type"]) == "mandatory" and not row["autopay_enabled"] for row in active_rows):
            non_autopay_merchants = sorted(
                row["merchant_name"]
                for row in active_rows
                if self._normalize_lower(row["commitment_type"]) == "mandatory" and not row["autopay_enabled"]
            )
            insights.append(
                EmiInsightResponse(
                    insight_type="Mandatory EMI Without AutoPay",
                    message="At least one mandatory EMI is not protected by autopay and may require manual tracking.",
                    severity="high",
                    confidence=0.95,
                    evidence=non_autopay_merchants,
                )
            )

        if any("education loan" in self._normalize_lower(row["loan_type"]) for row in active_rows):
            education_merchants = sorted(row["merchant_name"] for row in active_rows if "education loan" in self._normalize_lower(row["loan_type"]))
            insights.append(
                EmiInsightResponse(
                    insight_type="Education Loan Active",
                    message="The EMI portfolio includes an active education loan commitment.",
                    severity="low",
                    confidence=0.92,
                    evidence=education_merchants,
                )
            )

        if any("gold loan" in self._normalize_lower(row["loan_type"]) for row in active_rows):
            gold_merchants = sorted(row["merchant_name"] for row in active_rows if "gold loan" in self._normalize_lower(row["loan_type"]))
            insights.append(
                EmiInsightResponse(
                    insight_type="Gold Loan Active",
                    message="The EMI portfolio includes an active gold loan commitment.",
                    severity="medium",
                    confidence=0.92,
                    evidence=gold_merchants,
                )
            )

        if top_loan_share >= 0.4:
            top_loan_label = top_loan_type[0]
            if any(keyword in self._normalize_lower(top_loan_label) for keyword in ("vehicle", "car", "bike")):
                insights.append(
                    EmiInsightResponse(
                        insight_type="Vehicle Loan Dominates Commitments",
                        message="Vehicle-related EMI obligations dominate the monthly EMI burden.",
                        severity="medium",
                        confidence=0.88,
                        evidence=[f"dominant_loan_type={top_loan_label}", f"share={round(top_loan_share, 2)}"],
                    )
                )
            elif any(keyword in self._normalize_lower(top_loan_label) for keyword in ("home", "housing", "land")):
                insights.append(
                    EmiInsightResponse(
                        insight_type="Home Loan Dominates Commitments",
                        message="Housing-related EMI obligations dominate the monthly EMI burden.",
                        severity="medium",
                        confidence=0.88,
                        evidence=[f"dominant_loan_type={top_loan_label}", f"share={round(top_loan_share, 2)}"],
                    )
                )

        consumer_loan_keywords = {"consumer durable loan", "personal loan", "medical loan", "phone loan", "laptop loan", "wedding loan", "lifestyle loan"}
        consumer_loan_types = sorted({row["loan_type"] for row in active_rows if self._normalize_lower(row["loan_type"]) in consumer_loan_keywords})
        if len(consumer_loan_types) >= 2:
            insights.append(
                EmiInsightResponse(
                    insight_type="Multiple Consumer Loans",
                    message="The EMI portfolio includes multiple consumer-oriented loans that may overlap in budget impact.",
                    severity="medium",
                    confidence=0.87,
                    evidence=consumer_loan_types,
                )
            )

        if monthly_capacity > 0 and monthly_burden <= monthly_capacity * 0.1 and payment_statistics.payment_success_rate >= 90.0:
            insights.append(
                EmiInsightResponse(
                    insight_type="Healthy EMI Portfolio",
                    message="The EMI burden is contained relative to monthly financial capacity and payment performance is strong.",
                    severity="low",
                    confidence=0.94,
                    evidence=[f"monthly_emi_burden={round(monthly_burden, 2)}", f"monthly_financial_capacity={round(monthly_capacity, 2)}", f"payment_success_rate={payment_statistics.payment_success_rate}"],
                )
            )

        insights.sort(key=lambda item: (self._severity_rank(item.severity), item.insight_type))
        return insights

    def get_emi_intelligence(self, user_id: str) -> EmiIntelligenceResponse:
        logger.info("EMI analysis started for user_id=%s", user_id)
        started_at = time.perf_counter()

        try:
            user_record = self._dataset_service.get_user(user_id)
            transactions = self._dataset_service.get_user_transactions(user_id)
            logger.info("Transactions loaded for user_id=%s total_transactions=%s", user_id, len(transactions))

            if not transactions:
                raise EmiNotFoundError(f"No EMI transactions found for user: {user_id}")

            emi_frame = self._prepare_emi_frame(transactions)
            if emi_frame.empty:
                raise EmiNotFoundError(f"No EMI transactions found for user: {user_id}")

            emi_frame = emi_frame.dropna(subset=["transaction_date"]).copy()
            if emi_frame.empty:
                raise EmiNotFoundError(f"No EMI transactions found for user: {user_id}")

            emi_frame = emi_frame.sort_values(["merchant_name_normalized", "transaction_date"])
            active_rows = [self._build_active_emi(merchant_name, group) for merchant_name, group in emi_frame.groupby("merchant_name_normalized", dropna=False)]
            active_rows = sorted(active_rows, key=lambda row: (row["monthly_emi_amount"], row["merchant_name"]), reverse=True)

            emi_summary = self._build_emi_summary(active_rows)
            logger.info("EMIs detected for user_id=%s active_emi_count=%s monthly_emi_burden=%.2f", user_id, emi_summary.active_emi_count, emi_summary.monthly_emi_burden)

            payment_statistics = self._build_payment_statistics(active_rows, emi_frame)
            monthly_capacity = self._to_float(user_record.get("monthly_financial_capacity"))
            financial_statistics = self._build_financial_statistics(emi_summary.monthly_emi_burden, monthly_capacity)
            emi_insights = self._build_insights(active_rows, emi_summary.monthly_emi_burden, monthly_capacity, payment_statistics)
            logger.info("Insights generated for user_id=%s insight_count=%s", user_id, len(emi_insights))

            return EmiIntelligenceResponse(
                user_id=user_id,
                emi_summary=emi_summary,
                active_emis=[ActiveEmiResponse(**row) for row in active_rows],
                payment_statistics=payment_statistics,
                financial_statistics=financial_statistics,
                emi_insights=emi_insights,
            )
        except UserNotFoundError:
            raise
        except EmiNotFoundError:
            raise
        except Exception as exc:  # pragma: no cover - defensive wrap for runtime issues
            logger.exception("EMI intelligence processing failed for user_id=%s", user_id)
            raise EmiProcessingError(f"Unable to process EMI intelligence for user: {user_id}") from exc
        finally:
            elapsed_seconds = time.perf_counter() - started_at
            logger.info("EMI analysis finished for user_id=%s execution_time_seconds=%.3f", user_id, elapsed_seconds)


def get_emi_service(dataset_service: DatasetService = Depends(get_dataset_service)) -> EmiService:
    return EmiService(dataset_service)
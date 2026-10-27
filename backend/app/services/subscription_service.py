from __future__ import annotations

import logging
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any

import pandas as pd
from fastapi import Depends

from app.core.exceptions import SubscriptionNotFoundError, SubscriptionProcessingError, UserNotFoundError
from app.schemas.subscription import (
    ActiveSubscriptionResponse,
    AutopayStatisticsResponse,
    NewSubscriptionResponse,
    SubscriptionCostItemResponse,
    SubscriptionInsightResponse,
    SubscriptionIntelligenceResponse,
    SubscriptionSummaryResponse,
    TransactionStatusSummaryResponse,
    TrialConversionCandidateResponse,
)
from app.services.dataset_service import DatasetService, get_dataset_service
from app.services.financial_rules import (
    TransactionStatus,
    classify_transaction_status,
    commitment_amount,
    monthly_multiplier,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SubscriptionFrequencyRule:
    label: str
    monthly_multiplier: float


class SubscriptionService:
    _frequency_rules: tuple[SubscriptionFrequencyRule, ...] = (
        SubscriptionFrequencyRule("weekly", 52.0 / 12.0),
        SubscriptionFrequencyRule("biweekly", 26.0 / 12.0),
        SubscriptionFrequencyRule("fortnightly", 26.0 / 12.0),
        SubscriptionFrequencyRule("monthly", 1.0),
        SubscriptionFrequencyRule("quarterly", 1.0 / 3.0),
        SubscriptionFrequencyRule("semiannual", 1.0 / 6.0),
        SubscriptionFrequencyRule("annual", 1.0 / 12.0),
        SubscriptionFrequencyRule("yearly", 1.0 / 12.0),
        SubscriptionFrequencyRule("daily", 365.0 / 12.0),
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
        return SubscriptionService._normalize_text(value).lower()

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
        return SubscriptionService._normalize_lower(value) in {"yes", "true", "1", "y"}

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
    def _prepare_subscription_frame(cls, transactions: list[dict[str, Any]]) -> pd.DataFrame:
        frame = pd.DataFrame(transactions)
        if frame.empty:
            return frame

        prepared = frame.copy()
        prepared["transaction_date"] = pd.to_datetime(prepared["transaction_date"], errors="coerce")
        prepared["transaction_class_normalized"] = prepared["transaction_class"].map(cls._normalize_lower)
        prepared = prepared[prepared["transaction_class_normalized"] == "subscription"].copy()
        if prepared.empty:
            return prepared

        prepared["amount_value"] = pd.to_numeric(prepared["amount"], errors="coerce").fillna(0.0).map(commitment_amount)
        prepared["frequency_normalized"] = prepared["frequency"].map(cls._normalize_lower)
        prepared["merchant_type_normalized"] = prepared["merchant_type"].map(cls._normalize_lower)
        prepared["autopay_enabled_flag"] = prepared["autopay_flag"].map(cls._to_bool)
        prepared["is_new_subscription_flag"] = prepared["is_new_subscription"].map(cls._to_bool)
        prepared["monthly_multiplier"] = prepared["frequency_normalized"].map(cls._monthly_multiplier)
        prepared["monthly_estimated_cost_row"] = prepared["amount_value"] * prepared["monthly_multiplier"]
        return prepared

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

    @staticmethod
    def _most_recent_paid_row(frame: pd.DataFrame, first_amount: float) -> pd.Series | None:
        paid_rows = frame[frame["amount_value"] > 0.0]
        if paid_rows.empty:
            return None
        eligible_rows = paid_rows[paid_rows["amount_value"] >= max(first_amount, 0.01)]
        if eligible_rows.empty:
            return None
        return eligible_rows.sort_values("transaction_date").iloc[0]

    @staticmethod
    def _ordered_rows(frame: pd.DataFrame, column: str) -> list[dict[str, Any]]:
        return frame.sort_values(column, ascending=False).to_dict(orient="records")

    def _build_active_subscription(self, merchant_name: str, frame: pd.DataFrame) -> dict[str, Any]:
        average_amount = self._to_float(frame["amount_value"].mean())
        monthly_cost = self._to_float(frame["monthly_estimated_cost_row"].mean())
        return {
            "merchant_name": merchant_name,
            "first_subscription_date": self._to_date(frame["transaction_date"].min()),
            "latest_subscription_date": self._to_date(frame["transaction_date"].max()),
            "number_of_payments": int(frame.shape[0]),
            "average_subscription_amount": round(average_amount, 2),
            "total_amount_paid": round(self._to_float(frame["amount_value"].sum()), 2),
            "autopay_enabled": bool(frame["autopay_enabled_flag"].any()),
            "recurring_frequency": self._dominant_value(frame["frequency"]),
            "merchant_type": self._dominant_value(frame["merchant_type"]),
            "monthly_estimated_cost": round(monthly_cost, 2),
            "transaction_status_summary": self._status_summary(frame).model_dump(),
        }

    def _build_new_subscriptions(self, frame: pd.DataFrame) -> list[NewSubscriptionResponse]:
        new_rows = frame[frame["is_new_subscription_flag"]].sort_values("transaction_date")
        return [
            NewSubscriptionResponse(
                merchant_name=self._normalize_text(row["merchant_name"]),
                subscription_date=self._to_date(row["transaction_date"]),
                amount=round(self._to_float(row["amount_value"]), 2),
            )
            for _, row in new_rows.iterrows()
        ]

    @staticmethod
    def _trial_keyword_match(description: str) -> bool:
        keywords = {"trial", "promo", "promotional", "free", "intro", "introductory"}
        lower_description = description.lower()
        return any(keyword in lower_description for keyword in keywords)

    def _build_trial_candidates(self, frame: pd.DataFrame) -> list[TrialConversionCandidateResponse]:
        candidates: list[TrialConversionCandidateResponse] = []
        for merchant_name, group in frame.groupby("merchant_name", dropna=False):
            ordered = group.sort_values("transaction_date")
            if ordered.empty:
                continue

            first_row = ordered.iloc[0]
            first_amount = self._to_float(first_row["amount_value"])
            first_description = self._normalize_text(first_row.get("description"))

            if not (first_amount <= 0.01 or self._trial_keyword_match(first_description)):
                continue

            paid_row = self._most_recent_paid_row(ordered, first_amount)
            if paid_row is None:
                continue

            recurring_paid_rows = ordered[ordered["amount_value"] >= max(first_amount, 0.01)]
            if recurring_paid_rows.shape[0] < 2:
                continue

            confidence = 0.74
            evidence = "Initial low-value or promotional transaction followed by recurring paid subscription charges."
            if first_amount <= 0.01:
                confidence = 0.9
                evidence = "Zero or near-zero initial charge followed by recurring paid subscription charges."
            elif self._trial_keyword_match(first_description):
                confidence = 0.82
                evidence = "Trial or promotional wording in the first transaction followed by paid recurrence."

            candidates.append(
                TrialConversionCandidateResponse(
                    merchant_name=self._normalize_text(merchant_name),
                    possible_trial_conversion=True,
                    confidence_level=round(confidence, 2),
                    trial_start_date=self._to_date(first_row["transaction_date"]),
                    paid_subscription_date=self._to_date(paid_row["transaction_date"]),
                    initial_amount=round(first_amount, 2),
                    recurring_paid_amount=round(self._to_float(paid_row["amount_value"]), 2),
                    evidence=evidence,
                )
            )
        return candidates

    def _merchant_cost_item(self, merchant_name: str, monthly_cost: float, average_amount: float) -> SubscriptionCostItemResponse:
        return SubscriptionCostItemResponse(
            merchant_name=merchant_name,
            average_subscription_amount=round(average_amount, 2),
            monthly_estimated_cost=round(monthly_cost, 2),
        )

    def _build_summary(self, active_rows: list[dict[str, Any]]) -> SubscriptionSummaryResponse:
        if not active_rows:
            return SubscriptionSummaryResponse(
                subscription_count=0,
                monthly_subscription_cost=0.0,
                annual_subscription_cost=0.0,
                average_subscription_cost=0.0,
                most_expensive_subscription=None,
                least_expensive_subscription=None,
            )

        monthly_costs = [row["monthly_estimated_cost"] for row in active_rows]
        ordered = sorted(active_rows, key=lambda row: (row["monthly_estimated_cost"], row["merchant_name"]))
        average_monthly_cost = sum(monthly_costs) / len(monthly_costs)
        return SubscriptionSummaryResponse(
            subscription_count=len(active_rows),
            monthly_subscription_cost=round(sum(monthly_costs), 2),
            annual_subscription_cost=round(sum(monthly_costs) * 12.0, 2),
            average_subscription_cost=round(average_monthly_cost, 2),
            most_expensive_subscription=self._merchant_cost_item(
                ordered[-1]["merchant_name"], ordered[-1]["monthly_estimated_cost"], ordered[-1]["average_subscription_amount"]
            ),
            least_expensive_subscription=self._merchant_cost_item(
                ordered[0]["merchant_name"], ordered[0]["monthly_estimated_cost"], ordered[0]["average_subscription_amount"]
            ),
        )

    def _build_autopay_statistics(self, active_rows: list[dict[str, Any]]) -> AutopayStatisticsResponse:
        autopay_rows = [row for row in active_rows if row["autopay_enabled"]]
        total_autopay = len(autopay_rows)
        monthly_commitment = sum(row["monthly_estimated_cost"] for row in autopay_rows)
        annual_commitment = monthly_commitment * 12.0
        share = (total_autopay / len(active_rows)) if active_rows else 0.0
        return AutopayStatisticsResponse(
            total_autopay_subscriptions=total_autopay,
            monthly_autopay_commitment=round(monthly_commitment, 2),
            annual_autopay_commitment=round(annual_commitment, 2),
            autopay_share_of_subscriptions=round(share, 2),
        )

    def _build_insights(
        self,
        active_rows: list[dict[str, Any]],
        user_record: dict[str, Any],
    ) -> list[SubscriptionInsightResponse]:
        insights: list[SubscriptionInsightResponse] = []
        monthly_capacity = self._to_float(user_record.get("monthly_financial_capacity"))
        monthly_cost = sum(row["monthly_estimated_cost"] for row in active_rows)

        if monthly_capacity > 0 and monthly_cost <= monthly_capacity * 0.05:
            insights.append(
                SubscriptionInsightResponse(
                    insight_type="Low Subscription Burden",
                    message="Monthly subscription spend is a small share of the user's monthly financial capacity.",
                    severity="low",
                    confidence=0.95,
                    evidence=[f"monthly_subscription_cost={round(monthly_cost, 2)}", f"monthly_financial_capacity={round(monthly_capacity, 2)}"],
                )
            )
        elif monthly_capacity > 0 and monthly_cost <= monthly_capacity * 0.1:
            insights.append(
                SubscriptionInsightResponse(
                    insight_type="Healthy Subscription Portfolio",
                    message="Subscription spending is moderate relative to monthly financial capacity.",
                    severity="low",
                    confidence=0.91,
                    evidence=[f"monthly_subscription_cost={round(monthly_cost, 2)}", f"monthly_financial_capacity={round(monthly_capacity, 2)}"],
                )
            )

        if monthly_capacity > 0 and monthly_cost >= monthly_capacity * 0.15:
            insights.append(
                SubscriptionInsightResponse(
                    insight_type="High Subscription Spending",
                    message=f"Subscription spending uses {round((monthly_cost / monthly_capacity) * 100, 1)}% of monthly financial capacity.",
                    severity="high",
                    confidence=0.93,
                    evidence=[f"monthly_subscription_cost={round(monthly_cost, 2)}", f"monthly_financial_capacity={round(monthly_capacity, 2)}"],
                )
            )

        ott_merchants = sorted({row["merchant_name"] for row in active_rows if self._normalize_lower(row["merchant_type"]) == "ott"})
        if len(ott_merchants) >= 2:
            insights.append(
                SubscriptionInsightResponse(
                    insight_type="Multiple OTT Platforms",
                    message="The subscription portfolio contains multiple OTT merchants, which can create overlapping entertainment spend.",
                    severity="medium",
                    confidence=0.88,
                    evidence=ott_merchants,
                )
            )

        ai_keywords = {"chatgpt", "openai", "claude", "gemini", "copilot", "perplexity", "midjourney", "notion ai"}
        ai_merchants = sorted(
            {
                row["merchant_name"]
                for row in active_rows
                if any(keyword in self._normalize_lower(row["merchant_name"]) for keyword in ai_keywords)
                or "ai" in self._normalize_lower(row["merchant_type"])
                or "ai" in self._normalize_lower(row["merchant_name"])
            }
        )
        ai_cost = sum(row["monthly_estimated_cost"] for row in active_rows if row["merchant_name"] in ai_merchants)
        if len(ai_merchants) >= 2:
            insights.append(
                SubscriptionInsightResponse(
                    insight_type="Multiple AI Tools",
                    message="The subscription portfolio includes multiple AI tools, which can overlap in capability and cost.",
                    severity="medium",
                    confidence=0.86,
                    evidence=ai_merchants,
                )
            )
        elif ai_merchants and ai_cost >= 500.0:
            insights.append(
                SubscriptionInsightResponse(
                    insight_type="High AI Tool Spending",
                    message="AI tooling spend is material and should be monitored alongside productivity subscriptions.",
                    severity="medium",
                    confidence=0.84,
                    evidence=ai_merchants,
                )
            )

        productivity_rows = [row for row in active_rows if self._normalize_lower(row["merchant_type"]) == "productivity"]
        productivity_cost = sum(row["monthly_estimated_cost"] for row in productivity_rows)
        if productivity_rows and productivity_cost >= 1000.0:
            insights.append(
                SubscriptionInsightResponse(
                    insight_type="High Productivity Tool Spending",
                    message="Productivity subscriptions represent a meaningful recurring expense.",
                    severity="medium",
                    confidence=0.88,
                    evidence=sorted({row["merchant_name"] for row in productivity_rows}),
                )
            )

        if active_rows and all(row["autopay_enabled"] for row in active_rows):
            insights.append(
                SubscriptionInsightResponse(
                    insight_type="AutoPay Enabled For All Subscriptions",
                    message="Every active subscription in the portfolio is enabled for autopay.",
                    severity="low",
                    confidence=0.97,
                    evidence=[row["merchant_name"] for row in active_rows],
                )
            )

        if len(active_rows) >= 5:
            insights.append(
                SubscriptionInsightResponse(
                    insight_type="Heavy Subscription User",
                    message="The user has a broad subscription portfolio and may benefit from consolidation review.",
                    severity="low",
                    confidence=0.9,
                    evidence=[f"subscription_count={len(active_rows)}"],
                )
            )

        return insights

    def get_subscription_intelligence(self, user_id: str) -> SubscriptionIntelligenceResponse:
        logger.info("Subscription detection started for user_id=%s", user_id)
        started_at = time.perf_counter()

        try:
            user_record = self._dataset_service.get_user(user_id)
            transactions = self._dataset_service.get_user_transactions(user_id)
            if not transactions:
                raise SubscriptionNotFoundError(f"No subscription transactions found for user: {user_id}")

            subscription_frame = self._prepare_subscription_frame(transactions)
            logger.info("Transactions analyzed for user_id=%s total_transactions=%s", user_id, len(transactions))
            if subscription_frame.empty:
                raise SubscriptionNotFoundError(f"No subscription transactions found for user: {user_id}")

            subscription_frame = subscription_frame.dropna(subset=["transaction_date"])
            subscription_frame = subscription_frame.sort_values(["merchant_name", "transaction_date"])

            active_rows = []
            for merchant_name, group in subscription_frame.groupby("merchant_name", dropna=False):
                active_rows.append(self._build_active_subscription(self._normalize_text(merchant_name), group))

            active_rows = sorted(active_rows, key=lambda row: row["monthly_estimated_cost"], reverse=True)
            summary = self._build_summary(active_rows)
            autopay_statistics = self._build_autopay_statistics(active_rows)
            new_subscriptions = self._build_new_subscriptions(subscription_frame)
            trial_candidates = self._build_trial_candidates(subscription_frame)
            insights = self._build_insights(active_rows, user_record)

            logger.info("Subscriptions detected for user_id=%s subscription_count=%s", user_id, summary.subscription_count)
            return SubscriptionIntelligenceResponse(
                user_id=user_id,
                subscription_summary=summary,
                active_subscriptions=[ActiveSubscriptionResponse(**row) for row in active_rows],
                new_subscriptions=new_subscriptions,
                trial_conversion_candidates=trial_candidates,
                subscription_insights=insights,
                autopay_statistics=autopay_statistics,
            )
        except UserNotFoundError:
            raise
        except SubscriptionNotFoundError:
            raise
        except Exception as exc:  # pragma: no cover - defensive wrap for runtime issues
            logger.exception("Subscription intelligence processing failed for user_id=%s", user_id)
            raise SubscriptionProcessingError(f"Unable to process subscription intelligence for user: {user_id}") from exc
        finally:
            elapsed_seconds = time.perf_counter() - started_at
            logger.info("Subscription detection finished for user_id=%s execution_time_seconds=%.3f", user_id, elapsed_seconds)


def get_subscription_service(dataset_service: DatasetService = Depends(get_dataset_service)) -> SubscriptionService:
    return SubscriptionService(dataset_service)
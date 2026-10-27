from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.digital_twin.twin_engine import DigitalTwin, FinancialSnapshot


@dataclass(frozen=True)
class ComparisonMetric:
    """
    Quantitative metric comparison output representing before, after, difference,
    and percentage difference.
    """

    metric_name: str
    before: float
    after: float
    difference: float
    percentage_difference: float


@dataclass
class FinancialComparison:
    """
    Enriched metadata and metric comparison results comparing original vs simulated snapshots.
    """

    comparison_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    scenario_type: str | None = None
    metrics_compared: list[str] = field(default_factory=list)
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, ComparisonMetric] = field(default_factory=dict)
    before_snapshot: FinancialSnapshot | None = None
    after_snapshot: FinancialSnapshot | None = None


class ComparisonEngine:
    """
    Comparison Engine.
    Compares two financial snapshots (or Digital Twins) across key financial metrics.
    Enriches comparison metadata without calling ML models or generating recommendations.
    """

    @staticmethod
    def _extract_snapshot(target: FinancialSnapshot | DigitalTwin) -> FinancialSnapshot:
        if isinstance(target, DigitalTwin):
            return target.snapshot
        if isinstance(target, FinancialSnapshot):
            return target
        raise TypeError(f"Expected FinancialSnapshot or DigitalTwin, got {type(target).__name__}")

    @staticmethod
    def _extract_scenario_type(target: FinancialSnapshot | DigitalTwin) -> str | None:
        if isinstance(target, DigitalTwin):
            return target.metadata.scenario_applied
        return None

    @staticmethod
    def _calculate_metric(name: str, before_val: float, after_val: float) -> ComparisonMetric:
        diff = round(after_val - before_val, 2)
        if before_val != 0.0:
            pct = round((diff / abs(before_val)) * 100.0, 2)
        elif after_val != 0.0:
            pct = 100.0
        else:
            pct = 0.0

        return ComparisonMetric(
            metric_name=name,
            before=round(float(before_val), 2),
            after=round(float(after_val), 2),
            difference=diff,
            percentage_difference=pct,
        )

    def compare(
        self,
        original: FinancialSnapshot | DigitalTwin,
        modified: FinancialSnapshot | DigitalTwin,
    ) -> FinancialComparison:
        """
        Compares original vs modified financial status across the 8 required metrics:
        1. Income
        2. Monthly Commitments
        3. Exposure
        4. Financial Health
        5. Subscription Count
        6. EMI Count
        7. BNPL Count
        8. Savings
        """
        before_snap = self._extract_snapshot(original)
        after_snap = self._extract_snapshot(modified)
        scenario_type = self._extract_scenario_type(modified)

        metrics_map: dict[str, ComparisonMetric] = {
            "income": self._calculate_metric(
                "Income", before_snap.monthly_income, after_snap.monthly_income
            ),
            "monthly_commitments": self._calculate_metric(
                "Monthly Commitments",
                before_snap.monthly_commitments,
                after_snap.monthly_commitments,
            ),
            "exposure": self._calculate_metric(
                "Exposure", before_snap.exposure_score, after_snap.exposure_score
            ),
            "financial_health": self._calculate_metric(
                "Financial Health",
                before_snap.financial_health_score,
                after_snap.financial_health_score,
            ),
            "subscription_count": self._calculate_metric(
                "Subscription Count",
                float(before_snap.active_subscriptions_count),
                float(after_snap.active_subscriptions_count),
            ),
            "emi_count": self._calculate_metric(
                "EMI Count",
                float(before_snap.active_emis_count),
                float(after_snap.active_emis_count),
            ),
            "bnpl_count": self._calculate_metric(
                "BNPL Count",
                float(before_snap.active_bnpl_count),
                float(after_snap.active_bnpl_count),
            ),
            "savings": self._calculate_metric(
                "Savings", before_snap.monthly_savings, after_snap.monthly_savings
            ),
        }

        commit_diff = metrics_map["monthly_commitments"].difference
        health_diff = metrics_map["financial_health"].difference
        exp_diff = metrics_map["exposure"].difference

        summary = (
            f"Comparison completed: Commitments changed by {commit_diff:+.2f}, "
            f"Exposure changed by {exp_diff:+.2f}%, Health Score changed by {health_diff:+.2f} points."
        )

        comparison_id = str(uuid.uuid4())
        generated_at = datetime.now(timezone.utc).isoformat()
        metrics_compared_list = list(metrics_map.keys())

        return FinancialComparison(
            comparison_id=comparison_id,
            generated_at=generated_at,
            scenario_type=scenario_type,
            metrics_compared=metrics_compared_list,
            summary=summary,
            metadata={
                "before_user_id": before_snap.user_id,
                "after_user_id": after_snap.user_id,
                "metrics_count": len(metrics_compared_list),
            },
            metrics=metrics_map,
            before_snapshot=before_snap,
            after_snapshot=after_snap,
        )

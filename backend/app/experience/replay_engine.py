from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.decision.decision_engine import Recommendation
from app.digital_twin.comparison_engine import FinancialComparison
from app.digital_twin.twin_engine import FinancialSnapshot


@dataclass(frozen=True)
class ReplayOutcome:
    """
    Comparison metric comparing expected simulation prediction vs actual financial outcome.
    """

    metric_name: str
    expected_value: float
    actual_value: float
    difference: float
    accuracy_percentage: float


@dataclass
class DecisionReplay:
    """
    Decision Replay analysis evaluating historical recommendation accuracy and key lessons learned.
    """

    replay_id: str
    original_recommendation_title: str
    decision_date: str
    replay_date: str
    outcomes: dict[str, ReplayOutcome] = field(default_factory=dict)
    overall_accuracy: float = 100.0
    lessons_learned: list[str] = field(default_factory=list)
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ReplayEngine:
    """
    Replay Engine.

    Replays historical financial recommendations by comparing simulated/predicted outcomes
    with actual financial snapshot results. Does NOT trigger machine learning retraining.
    """

    def replay_decision(
        self,
        original_recommendation: Recommendation,
        expected_comparison: FinancialComparison,
        current_snapshot: FinancialSnapshot,
        decision_date: str | None = None,
    ) -> DecisionReplay:
        """
        Replays a historical recommendation by evaluating expected simulated deltas
        against current actual snapshot metrics.
        """
        outcomes: dict[str, ReplayOutcome] = {}
        accuracy_scores: list[float] = []
        lessons_learned: list[str] = []

        # 1. Compare Exposure Metric
        exp_comp = expected_comparison.metrics.get("exposure")
        if exp_comp:
            expected_exp = exp_comp.after
            actual_exp = current_snapshot.exposure_score
            exp_diff = round(actual_exp - expected_exp, 2)
            exp_acc = max(0.0, round(100.0 - (abs(exp_diff) / max(1.0, expected_exp) * 100.0), 2))
            accuracy_scores.append(exp_acc)

            outcomes["exposure"] = ReplayOutcome(
                metric_name="Exposure Score",
                expected_value=expected_exp,
                actual_value=actual_exp,
                difference=exp_diff,
                accuracy_percentage=exp_acc,
            )

            if abs(exp_diff) <= 2.0:
                lessons_learned.append("Exposure projection matched actual financial behavior accurately.")
            elif actual_exp < expected_exp:
                lessons_learned.append("Financial exposure improved even more than initially projected.")
            else:
                lessons_learned.append("Actual exposure was slightly higher than expected due to additional commitments.")

        # 2. Compare Commitments Metric
        commit_comp = expected_comparison.metrics.get("monthly_commitments")
        if commit_comp:
            expected_commit = commit_comp.after
            actual_commit = current_snapshot.monthly_commitments
            commit_diff = round(actual_commit - expected_commit, 2)
            commit_acc = max(0.0, round(100.0 - (abs(commit_diff) / max(1.0, expected_commit) * 100.0), 2))
            accuracy_scores.append(commit_acc)

            outcomes["monthly_commitments"] = ReplayOutcome(
                metric_name="Monthly Commitments",
                expected_value=expected_commit,
                actual_value=actual_commit,
                difference=commit_diff,
                accuracy_percentage=commit_acc,
            )

            if abs(commit_diff) <= 500.0:
                lessons_learned.append("Monthly commitment reduction target was successfully achieved.")

        # 3. Compare Financial Health Metric
        health_comp = expected_comparison.metrics.get("financial_health")
        if health_comp:
            expected_health = health_comp.after
            actual_health = current_snapshot.financial_health_score
            health_diff = round(actual_health - expected_health, 2)
            health_acc = max(0.0, round(100.0 - (abs(health_diff) / max(1.0, expected_health) * 100.0), 2))
            accuracy_scores.append(health_acc)

            outcomes["financial_health"] = ReplayOutcome(
                metric_name="Financial Health Score",
                expected_value=expected_health,
                actual_value=actual_health,
                difference=health_diff,
                accuracy_percentage=health_acc,
            )

        overall_accuracy = round(sum(accuracy_scores) / len(accuracy_scores), 2) if accuracy_scores else 100.0

        if overall_accuracy >= 90.0:
            lessons_learned.append("High recommendation accuracy confirms decision engine effectiveness.")

        replay_id = f"replay_{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        dec_date_str = decision_date or (datetime.now(timezone.utc)).isoformat()

        summary = (
            f"Decision Replay completed for '{original_recommendation.title}': Overall Accuracy {overall_accuracy:.1f}%."
        )

        return DecisionReplay(
            replay_id=replay_id,
            original_recommendation_title=original_recommendation.title,
            decision_date=dec_date_str,
            replay_date=now_iso,
            outcomes=outcomes,
            overall_accuracy=overall_accuracy,
            lessons_learned=lessons_learned,
            summary=summary,
            metadata={
                "recommendation_type": original_recommendation.recommendation_type.value,
                "user_id": current_snapshot.user_id,
            },
        )

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConfidenceLevel(str, Enum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


@dataclass(frozen=True)
class DecisionConfidence:
    """
    Data structure representing recommendation confidence and supporting rationale.
    """

    score: float
    level: ConfidenceLevel
    explanation: str
    positive_factors: list[str] = field(default_factory=list)
    negative_factors: list[str] = field(default_factory=list)
    sub_scores: dict[str, float] = field(default_factory=dict)


class DecisionConfidenceEngine:
    """
    Decision Confidence Engine.

    Calculates recommendation confidence deterministically based on rule agreement,
    simulation stability, exposure improvement, financial health, and action risk.
    Does NOT depend on AI or ML models.
    """

    def calculate_confidence(
        self,
        recommendation_type: str,
        financial_health_score: float,
        exposure_score: float,
        exposure_delta: float = 0.0,
        commitments_delta: float = 0.0,
        simulation_applied: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionConfidence:
        """
        Calculates deterministic confidence for a recommendation.
        """
        positive_factors: list[str] = []
        negative_factors: list[str] = []
        sub_scores: dict[str, float] = {}

        # 1. Financial Health Score Base (Weight: 25%)
        health_base = min(100.0, max(0.0, float(financial_health_score)))
        sub_scores["financial_health"] = health_base
        if health_base >= 75.0:
            positive_factors.append(f"Strong baseline financial health score ({health_base:.1f}/100)")
        elif health_base < 50.0:
            negative_factors.append(f"Low baseline financial health score ({health_base:.1f}/100)")

        # 2. Exposure Score Impact (Weight: 25%)
        # Lower exposure score is safer
        exposure_sub = max(0.0, 100.0 - float(exposure_score))
        sub_scores["exposure_alignment"] = exposure_sub
        if exposure_score <= 40.0:
            positive_factors.append(f"Managed financial exposure score ({exposure_score:.1f}%)")
        elif exposure_score > 60.0:
            negative_factors.append(f"High financial exposure score ({exposure_score:.1f}%)")

        # 3. Simulation & Exposure Delta Impact (Weight: 25%)
        if simulation_applied:
            if exposure_delta < 0.0:
                delta_score = min(100.0, 70.0 + abs(exposure_delta) * 3.0)
                positive_factors.append(f"Simulation confirms exposure reduction of {abs(exposure_delta):.1f}%")
            elif exposure_delta == 0.0:
                delta_score = 60.0
                positive_factors.append("Simulation indicates stable exposure level")
            else:
                delta_score = max(0.0, 50.0 - exposure_delta * 2.0)
                negative_factors.append(f"Simulation projects exposure increase of {exposure_delta:.1f}%")
        else:
            delta_score = 65.0
            positive_factors.append("Baseline rule agreement without simulation delta")

        sub_scores["simulation_stability"] = delta_score

        # 4. Action Risk & Recommendation Consistency (Weight: 25%)
        rec_type_lower = str(recommendation_type).lower()
        if any(kw in rec_type_lower for kw in ["cancel", "close", "reduce", "increase_savings"]):
            risk_score = 90.0
            positive_factors.append("Low-risk corrective financial action")
        elif "delay" in rec_type_lower:
            risk_score = 80.0
            positive_factors.append("Prudent purchase delay recommendation")
        elif "proceed" in rec_type_lower:
            if exposure_score <= 40.0 and health_base >= 70.0:
                risk_score = 85.0
                positive_factors.append("Purchase supported by available capacity and health")
            else:
                risk_score = 55.0
                negative_factors.append("Purchase approval carries moderate risk under current commitment load")
        else:
            risk_score = 70.0

        sub_scores["action_risk"] = risk_score

        # Weighted aggregate calculation
        aggregate_score = (
            (sub_scores["financial_health"] * 0.25)
            + (sub_scores["exposure_alignment"] * 0.25)
            + (sub_scores["simulation_stability"] * 0.25)
            + (sub_scores["action_risk"] * 0.25)
        )

        final_score = round(min(100.0, max(0.0, aggregate_score)), 2)

        if final_score >= 90.0:
            level = ConfidenceLevel.VERY_HIGH
            explanation = "Recommendation is backed by strong financial health, stable exposure metrics, and low risk."
        elif final_score >= 75.0:
            level = ConfidenceLevel.HIGH
            explanation = "Recommendation aligns well with business rules and current financial stability."
        elif final_score >= 50.0:
            level = ConfidenceLevel.MODERATE
            explanation = "Recommendation is moderately supported; minor financial exposure or commitment risks exist."
        else:
            level = ConfidenceLevel.LOW
            explanation = "Recommendation carries low confidence due to high commitment burden or limited buffer."

        return DecisionConfidence(
            score=final_score,
            level=level,
            explanation=explanation,
            positive_factors=positive_factors,
            negative_factors=negative_factors,
            sub_scores=sub_scores,
        )

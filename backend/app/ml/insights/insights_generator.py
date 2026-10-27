from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class AIInsightItem:
    prediction: Any
    confidence: float | None
    explanation: str
    recommendation: str
    supporting_factors: list[str]


@dataclass(frozen=True)
class InsightContext:
    snapshot_metrics: Mapping[str, Any]
    prediction_metadata: Mapping[str, Any]
    persona_name: str | None = None


class AIInsightsLayer:
    def build_distress_insight(self, prediction: Any, confidence: float | None, supporting_factors: list[str], context: InsightContext) -> AIInsightItem:
        label = str(prediction)
        metrics = context.snapshot_metrics
        exposure_score = self._format_percent(metrics.get("exposure_score"))
        commitment_ratio = self._format_percent(metrics.get("commitment_ratio"))
        payment_reliability = self._format_percent(metrics.get("payment_reliability"))
        bnpl_dependency = self._format_percent(metrics.get("bnpl_dependency"))

        if label.lower().startswith("high"):
            explanation = (
                f"The next-month failed-transaction event prediction is elevated. Current exposure is {exposure_score}, "
                f"monthly commitments consume {commitment_ratio} of capacity, current payment reliability is {payment_reliability}, "
                f"and BNPL dependence remains at {bnpl_dependency}."
            )
            pressures = []
            if float(metrics.get("bnpl_dependency", 0.0) or 0.0) > 0.0:
                pressures.append("BNPL reliance")
            if float(metrics.get("emi_burden_ratio", 0.0) or 0.0) > 0.0:
                pressures.append("EMI burden")
            pressure_text = " and ".join(pressures) if pressures else "recurring commitment pressure"
            recommendation = f"Pause new recurring commitments and review {pressure_text} before taking on additional obligations."
        elif label.lower().startswith("medium"):
            explanation = (
                f"The next-month failed-transaction event prediction is moderate. Current exposure is {exposure_score}, "
                f"commitments consume {commitment_ratio} of capacity, and current payment reliability is {payment_reliability}."
            )
            recommendation = "Slow down new commitments, prioritise payments with the highest recorded fixed burden, and monitor only the BNPL usage shown in your financial data."
        else:
            explanation = (
                f"The next-month failed-transaction event prediction is low risk. The current exposure is {exposure_score}, "
                f"current payment reliability is {payment_reliability}, and recurring commitments use a manageable share of capacity."
            )
            recommendation = "Maintain the current payment discipline and review any new recurring commitment before activation."

        return AIInsightItem(
            prediction=prediction,
            confidence=confidence,
            explanation=explanation,
            recommendation=recommendation,
            supporting_factors=supporting_factors,
        )

    def build_exposure_insight(self, prediction: Any, confidence: float | None, supporting_factors: list[str], context: InsightContext) -> AIInsightItem:
        metrics = context.snapshot_metrics
        current_exposure = self._format_number(metrics.get("exposure_score"), suffix="%")
        projected_exposure = self._format_number(prediction, suffix="%")
        delta = self._safe_delta(metrics.get("exposure_score"), prediction)
        if delta > 0:
            explanation = (
                f"Next-month exposure is projected to rise from current exposure {current_exposure} to forecast exposure {projected_exposure}, "
                f"indicating higher future commitment pressure."
            )
            recommendation = "Delay optional commitments and review recurring charges that can be deferred or reduced."
        elif delta < 0:
            explanation = (
                f"Next-month exposure is projected to ease from current exposure {current_exposure} to forecast exposure {projected_exposure}, "
                f"which suggests improving capacity headroom."
            )
            recommendation = "Preserve the current discipline and use the extra headroom to avoid overcommitment."
        else:
            explanation = f"Next-month exposure is projected to remain broadly stable around forecast exposure {projected_exposure}; current exposure is {current_exposure}."
            recommendation = "Keep monitoring fixed commitments and avoid adding unnecessary recurring obligations."
        return AIInsightItem(prediction=prediction, confidence=confidence, explanation=explanation, recommendation=recommendation, supporting_factors=supporting_factors)

    def build_persona_insight(self, prediction: Any, confidence: float | None, supporting_factors: list[str], context: InsightContext) -> AIInsightItem:
        persona_name = context.persona_name or str(prediction)
        profile = context.prediction_metadata.get("cluster_profile", {})
        dominant_features = list(profile.get("top_features", []))
        feature_text = self._join_phrases(dominant_features[:3])
        if not feature_text:
            feature_text = "balanced commitment patterns"
        explanation = f"The user's current financial profile belongs to a descriptive {persona_name.lower()} cluster, characterised by {feature_text}; this is not a future-behaviour prediction."
        if persona_name == "Saver":
            recommendation = "Keep the low-burden pattern intact and continue prioritising payment discipline over new recurring spend."
        elif persona_name == "Subscription Heavy User":
            recommendation = "Review subscription overlap and remove low-value recurring services to protect monthly flexibility."
        elif persona_name == "EMI Focused User":
            recommendation = "Plan cash flow around EMI dates and avoid taking additional fixed instalment commitments."
        elif persona_name == "BNPL Dependent User":
            recommendation = "Reduce BNPL reliance and prioritise clearing short-term instalments before taking on new deferred payments."
        else:
            recommendation = "Use this behavioural profile as a benchmark and keep commitments diversified and predictable."
        return AIInsightItem(prediction=prediction, confidence=confidence, explanation=explanation, recommendation=recommendation, supporting_factors=supporting_factors)

    def build_anomaly_insight(self, prediction: Any, confidence: float | None, supporting_factors: list[str], context: InsightContext) -> AIInsightItem:
        metrics = context.snapshot_metrics
        score = self._format_number(context.prediction_metadata.get("decision_score"))
        spending_variance = self._format_number(metrics.get("spending_variance"))
        payment_reliability = self._format_percent(metrics.get("payment_reliability"))
        autopay_coverage = self._format_percent(metrics.get("autopay_coverage"))
        if bool(prediction):
            explanation = (
                f"The current feature snapshot is unusual relative to the reference population, with anomaly score {score}; "
                f"spending variance is {spending_variance}, payment reliability is {payment_reliability}, "
                f"and autopay coverage is {autopay_coverage}. This is not fraud or transaction-level detection."
            )
            recommendation = "Review recent large transactions, payment failures, and changes in recurring commitments for unusual activity."
        else:
            explanation = (
                f"The current feature snapshot is typical relative to the reference population because the score is {score} "
                f"and the payment pattern remains broadly consistent. This is not fraud or transaction-level detection."
            )
            recommendation = "Continue monitoring the account and re-check the score if spending variance or payment failures increase."
        return AIInsightItem(prediction=prediction, confidence=confidence, explanation=explanation, recommendation=recommendation, supporting_factors=supporting_factors)

    @staticmethod
    def _format_number(value: Any, suffix: str = "") -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "unknown"
        if suffix == "%":
            return f"{number:.2f}%"
        return f"{number:.2f}{suffix}"

    @staticmethod
    def _format_percent(value: Any) -> str:
        if value is None:
            return "Unavailable"
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "Unavailable"
        if number <= 1.0:
            number *= 100.0
        return f"{number:.1f}%"

    @staticmethod
    def _join_phrases(values: list[str]) -> str:
        if not values:
            return ""
        if len(values) == 1:
            return values[0]
        if len(values) == 2:
            return f"{values[0]} and {values[1]}"
        return f"{', '.join(values[:-1])}, and {values[-1]}"

    @staticmethod
    def _safe_delta(current: Any, projected: Any) -> float:
        try:
            return float(projected) - float(current)
        except (TypeError, ValueError):
            return 0.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ml.base import FinancialIntelligenceSnapshot
from app.ml.utils import clamp, coerce_float, safe_divide, truthy


@dataclass(frozen=True)
class PseudoLabelSet:
    distress_label: str
    future_exposure: float
    distress_score: float
    rationale: tuple[str, ...]


class LabelGenerator:
    """Generate reusable pseudo labels from deterministic financial intelligence."""

    def build(self, snapshot: FinancialIntelligenceSnapshot) -> PseudoLabelSet:
        context = self._context(snapshot)
        distress_score = self._distress_score(context)
        distress_label = self._distress_label(distress_score, context)
        future_exposure = self._future_exposure(context)
        rationale = self._rationale(context, distress_label, distress_score, future_exposure)
        return PseudoLabelSet(
            distress_label=distress_label,
            future_exposure=future_exposure,
            distress_score=round(distress_score, 4),
            rationale=tuple(rationale),
        )

    @staticmethod
    def _context(snapshot: FinancialIntelligenceSnapshot) -> dict[str, float | str]:
        profile = snapshot.financial_profile or {}
        user = snapshot.user_record or {}
        monthly_capacity = coerce_float(profile.get("monthly_financial_capacity") or user.get("monthly_financial_capacity"), default=0.0)
        monthly_commitments = coerce_float(profile.get("monthly_commitments"), default=0.0)
        exposure_score = coerce_float(profile.get("exposure_score"), default=0.0)
        commitment_ratio = safe_divide(monthly_commitments, monthly_capacity, 0.0)
        payment_reliability = LabelGenerator._transaction_success_rate(profile, user)
        active_bnpl = coerce_float(profile.get("active_bnpl"), default=0.0)
        total_active_commitments = max(coerce_float(profile.get("total_active_commitments"), default=0.0), 1.0)
        bnpl_dependency = safe_divide(active_bnpl, total_active_commitments, 0.0)
        financial_health = str(profile.get("financial_health") or "").strip().lower()
        financial_flexibility = clamp(1.0 - clamp(exposure_score / 100.0, 0.0, 1.0), 0.0, 1.0)
        return {
            "monthly_capacity": monthly_capacity,
            "monthly_commitments": monthly_commitments,
            "exposure_score": exposure_score,
            "commitment_ratio": commitment_ratio,
            "payment_reliability": payment_reliability,
            "bnpl_dependency": bnpl_dependency,
            "financial_health": financial_health,
            "financial_flexibility": financial_flexibility,
        }

    @staticmethod
    def _transaction_success_rate(profile: dict[str, Any], user: dict[str, Any]) -> float:
        raw_rate = profile.get("transaction_success_rate") or user.get("transaction_success_rate") or 0.0
        if isinstance(raw_rate, str) and raw_rate.endswith("%"):
            raw_rate = raw_rate.rstrip("%")
        rate = coerce_float(raw_rate, default=0.0)
        if rate > 1.0:
            rate /= 100.0
        return clamp(rate, 0.0, 1.0)

    @staticmethod
    def _distress_score(context: dict[str, float | str]) -> float:
        exposure_ratio = clamp(float(context["exposure_score"]) / 100.0, 0.0, 2.0)
        commitment_ratio = clamp(float(context["commitment_ratio"]), 0.0, 2.0)
        payment_risk = 1.0 - float(context["payment_reliability"])
        bnpl_dependency = clamp(float(context["bnpl_dependency"]), 0.0, 1.0)
        financial_health = str(context["financial_health"])
        health_penalty = 0.15 if financial_health in {"moderate", "risky"} else (0.3 if financial_health == "critical" else 0.0)
        return clamp(0.34 * exposure_ratio + 0.26 * commitment_ratio + 0.2 * payment_risk + 0.2 * bnpl_dependency + health_penalty, 0.0, 1.0)

    @staticmethod
    def _distress_label(distress_score: float, context: dict[str, float | str]) -> str:
        financial_health = str(context["financial_health"])
        if distress_score >= 0.62 or financial_health == "critical":
            return "High Risk"
        if distress_score >= 0.34 or financial_health in {"risky", "moderate"}:
            return "Medium Risk"
        return "Low Risk"

    @staticmethod
    def _future_exposure(context: dict[str, float | str]) -> float:
        exposure_score = float(context["exposure_score"])
        commitment_ratio = float(context["commitment_ratio"])
        bnpl_dependency = float(context["bnpl_dependency"])
        payment_reliability = float(context["payment_reliability"])
        financial_flexibility = float(context["financial_flexibility"])
        adjustment = 1.0 + (0.18 * commitment_ratio) + (0.12 * bnpl_dependency) + (0.08 * (1.0 - payment_reliability)) - (0.1 * financial_flexibility)
        return round(max(exposure_score * adjustment, 0.0), 4)

    @staticmethod
    def _rationale(context: dict[str, float | str], distress_label: str, distress_score: float, future_exposure: float) -> list[str]:
        return [
            f"Exposure score is {float(context['exposure_score']):.2f}%.",
            f"Commitment ratio is {float(context['commitment_ratio']) * 100.0:.1f}% of monthly capacity.",
            f"Payment reliability is {float(context['payment_reliability']) * 100.0:.1f}%.",
            f"BNPL dependency is {float(context['bnpl_dependency']) * 100.0:.1f}% of active commitments.",
            f"Distress score maps to {distress_label} at {distress_score:.2f}.",
            f"Projected exposure score is {future_exposure:.2f}.",
        ]

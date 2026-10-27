from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.digital_twin.twin_engine import FinancialSnapshot


class FinancialArchetype(str, Enum):
    STRATEGIC_PLANNER = "strategic_planner"
    SMART_SAVER = "smart_saver"
    BALANCED_SPENDER = "balanced_spender"
    SUBSCRIPTION_EXPLORER = "subscription_explorer"
    CREDIT_DEPENDENT = "credit_dependent"
    OPPORTUNITY_OPTIMIZER = "opportunity_optimizer"
    RISK_TAKER = "risk_taker"
    FINANCIAL_BUILDER = "financial_builder"


@dataclass(frozen=True)
class DNATrait:
    """
    Data structure representing a single behavioral dimension score (0-100) and factors.
    """

    name: str
    score: float
    description: str
    influencing_factors: list[str] = field(default_factory=list)


@dataclass
class FinancialDNA:
    """
    Complete Financial DNA profile containing 7 behavioral traits, primary archetype,
    secondary traits, improvement suggestions, and explainability summary.
    """

    user_id: str
    primary_archetype: FinancialArchetype
    traits: dict[str, DNATrait] = field(default_factory=dict)
    secondary_traits: list[str] = field(default_factory=list)
    improvement_suggestions: list[str] = field(default_factory=list)
    explainability: str = ""
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict[str, Any] = field(default_factory=dict)


class DNAEngine:
    """
    Financial DNA Engine.

    Generates a unique behavioral financial profile from financial snapshot intelligence.
    Evaluates 7 core dimensions (0-100 scale) and assigns a dynamic archetype without
    hardcoding rules or relying on ML persistence.
    """

    def generate_dna(self, snapshot: FinancialSnapshot) -> FinancialDNA:
        """
        Generates a FinancialDNA instance derived dynamically from a FinancialSnapshot.
        """
        income = max(0.0, snapshot.monthly_income)
        commitments = max(0.0, snapshot.monthly_commitments)
        savings = max(0.0, snapshot.monthly_savings)
        exposure = max(0.0, snapshot.exposure_score)
        health = max(0.0, snapshot.financial_health_score)
        sub_count = max(0, snapshot.active_subscriptions_count)
        emi_count = max(0, snapshot.active_emis_count)
        bnpl_count = max(0, snapshot.active_bnpl_count)

        # 1. Risk Appetite Score (0 - 100)
        # Higher exposure score and higher credit load indicate higher risk appetite
        risk_appetite_score = round(min(100.0, (exposure * 0.7) + ((emi_count + bnpl_count) * 5.0)), 2)
        risk_appetite = DNATrait(
            name="Risk Appetite",
            score=risk_appetite_score,
            description="Measures willingness to leverage debt and recurring commitments.",
            influencing_factors=[f"Exposure score at {exposure:.1f}%", f"Active loans count: {emi_count + bnpl_count}"],
        )

        # 2. Savings Behaviour Score (0 - 100)
        savings_ratio = (savings / income * 100.0) if income > 0 else 0.0
        savings_score = round(min(100.0, savings_ratio * 2.0), 2)
        savings_behaviour = DNATrait(
            name="Savings Behaviour",
            score=savings_score,
            description="Measures monthly savings rate relative to gross income.",
            influencing_factors=[f"Monthly savings ratio of {savings_ratio:.1f}%"],
        )

        # 3. Subscription Dependency Score (0 - 100)
        sub_score = round(min(100.0, (sub_count * 20.0)), 2)
        subscription_dependency = DNATrait(
            name="Subscription Dependency",
            score=sub_score,
            description="Evaluates reliance on recurring digital services and AutoPay obligations.",
            influencing_factors=[f"Active subscription count: {sub_count}"],
        )

        # 4. Credit Dependency Score (0 - 100)
        credit_score = round(min(100.0, ((emi_count * 25.0) + (bnpl_count * 20.0))), 2)
        credit_dependency = DNATrait(
            name="Credit Dependency",
            score=credit_score,
            description="Evaluates reliance on EMIs, BNPL, and short-term credit options.",
            influencing_factors=[f"Active EMIs: {emi_count}", f"Active BNPLs: {bnpl_count}"],
        )

        # 5. Financial Stability Score (0 - 100)
        stability_score = round(min(100.0, (health * 0.6) + ((100.0 - exposure) * 0.4)), 2)
        financial_stability = DNATrait(
            name="Financial Stability",
            score=stability_score,
            description="Overall resilience against financial distress and over-leverage.",
            influencing_factors=[f"Financial health score: {health:.1f}/100", f"Exposure score: {exposure:.1f}%"],
        )

        # 6. Payment Reliability Score (0 - 100)
        reliability_score = round(min(100.0, max(0.0, health * 0.9 + (10.0 if exposure <= 50.0 else -10.0))), 2)
        payment_reliability = DNATrait(
            name="Payment Reliability",
            score=reliability_score,
            description="Consistency and capacity to fulfill recurring payment commitments.",
            influencing_factors=[f"Health status: {snapshot.financial_health_status}"],
        )

        # 7. Emergency Preparedness Score (0 - 100)
        months_buffer = (savings / commitments) if commitments > 0 else 3.0
        emergency_score = round(min(100.0, months_buffer * 33.3), 2)
        emergency_preparedness = DNATrait(
            name="Emergency Preparedness",
            score=emergency_score,
            description="Calculates emergency buffer multiplier based on monthly commitments.",
            influencing_factors=[f"Monthly buffer multiplier: {months_buffer:.1f}x commitments"],
        )

        traits = {
            "risk_appetite": risk_appetite,
            "savings_behaviour": savings_behaviour,
            "subscription_dependency": subscription_dependency,
            "credit_dependency": credit_dependency,
            "financial_stability": financial_stability,
            "payment_reliability": payment_reliability,
            "emergency_preparedness": emergency_preparedness,
        }

        # Dynamic Archetype Assignment based on dominant traits
        primary_archetype = FinancialArchetype.BALANCED_SPENDER
        secondary_traits: list[str] = []
        suggestions: list[str] = []

        if savings_score >= 70.0 and credit_score <= 30.0:
            primary_archetype = FinancialArchetype.SMART_SAVER
            secondary_traits.append("High Savings Accumulator")
            suggestions.append("Consider allocating excess liquid savings into higher-yield growth instruments.")

        elif credit_score >= 60.0 or risk_appetite_score >= 65.0:
            primary_archetype = FinancialArchetype.CREDIT_DEPENDENT
            secondary_traits.append("Credit & EMI Reliant")
            suggestions.append("Prioritize closing high-cost BNPL or EMI obligations to lower financial exposure.")

        elif sub_score >= 60.0:
            primary_archetype = FinancialArchetype.SUBSCRIPTION_EXPLORER
            secondary_traits.append("High Digital AutoPay Burden")
            suggestions.append("Audit monthly active subscriptions and cancel non-essential AutoPay services.")

        elif stability_score >= 80.0 and savings_score >= 50.0:
            primary_archetype = FinancialArchetype.STRATEGIC_PLANNER
            secondary_traits.append("Resilient Capital Planner")
            suggestions.append("Maintain disciplined commitment ratios while building long-term wealth goals.")

        elif emergency_score <= 40.0:
            primary_archetype = FinancialArchetype.FINANCIAL_BUILDER
            secondary_traits.append("Building Liquid Reserve")
            suggestions.append("Focus on expanding emergency savings buffer to cover at least 3 months of commitments.")

        elif risk_appetite_score >= 50.0 and savings_score >= 40.0:
            primary_archetype = FinancialArchetype.OPPORTUNITY_OPTIMIZER
            secondary_traits.append("Active Capacity Deployer")
            suggestions.append("Keep debt growth controlled while maintaining investment flexibility.")

        else:
            primary_archetype = FinancialArchetype.BALANCED_SPENDER
            secondary_traits.append("Moderate Commitment Burden")
            suggestions.append("Maintain current balanced spending pattern.")

        explainability = (
            f"User profile classified as '{primary_archetype.value}' based on financial stability score of "
            f"{stability_score:.1f}/100, savings score of {savings_score:.1f}/100, and credit dependency of {credit_score:.1f}/100."
        )

        return FinancialDNA(
            user_id=snapshot.user_id,
            primary_archetype=primary_archetype,
            traits=traits,
            secondary_traits=secondary_traits,
            improvement_suggestions=suggestions,
            explainability=explainability,
            generated_at=datetime.now(timezone.utc).isoformat(),
            metadata={"exposure_score": exposure, "financial_health_score": health},
        )

    def generate_profile(self, snapshot: FinancialSnapshot) -> FinancialDNA:
        """Convenience alias for generate_dna."""
        return self.generate_dna(snapshot)

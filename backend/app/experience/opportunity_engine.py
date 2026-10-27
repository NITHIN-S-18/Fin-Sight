from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.decision.decision_engine import DecisionResult
from app.digital_twin.twin_engine import DigitalTwin, FinancialSnapshot
from app.dna.dna_engine import FinancialDNA


class OpportunityType(str, Enum):
    SAVINGS_OPPORTUNITY = "savings_opportunity"
    EXPOSURE_REDUCTION = "exposure_reduction"
    FINANCIAL_PLANNING = "financial_planning"
    RISK_ALERT = "risk_alert"
    OPTIMIZATION_SUGGESTION = "optimization_suggestion"


class OpportunityPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Opportunity:
    """
    Structured financial opportunity card.
    """

    opportunity_id: str
    title: str
    opportunity_type: OpportunityType
    priority: OpportunityPriority
    description: str
    expected_benefit: str
    estimated_monthly_savings: float = 0.0
    exposure_reduction: float = 0.0
    confidence_score: float = 85.0
    reason: str = ""
    simulation_available: bool = True
    suggested_action: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OpportunityFeed:
    """
    Collection of prioritized financial opportunities generated for a user.
    """

    user_id: str
    opportunities: list[Opportunity] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class OpportunityEngine:
    """
    Opportunity Engine.

    Generates proactive financial opportunities by consuming financial snapshot intelligence,
    Decision Engine recommendations, Financial DNA profiles, and Digital Twin simulations.
    Does NOT calculate machine learning predictions or raw business rules directly.
    """

    def generate_opportunities(
        self,
        snapshot: FinancialSnapshot,
        decision_result: DecisionResult | None = None,
        dna: FinancialDNA | None = None,
        twin: DigitalTwin | None = None,
    ) -> OpportunityFeed:
        """
        Generates a prioritized OpportunityFeed for the user.
        """
        opportunities: list[Opportunity] = []
        user_id = snapshot.user_id

        # 1. Evaluate Subscription Savings Opportunities
        if snapshot.active_subscriptions_count > 0:
            sub_list = snapshot.subscriptions
            if sub_list:
                top_sub = max(sub_list, key=lambda s: float(s.get("monthly_cost", 0.0)))
                sub_cost = float(top_sub.get("monthly_cost", 0.0))
                sub_name = top_sub.get("name", "Subscription")
                opp_id = f"opp_sub_{uuid.uuid4().hex[:8]}"

                opportunities.append(
                    Opportunity(
                        opportunity_id=opp_id,
                        title=f"Cancel Unused {sub_name}",
                        opportunity_type=OpportunityType.SAVINGS_OPPORTUNITY,
                        priority=OpportunityPriority.HIGH if sub_cost > 300.0 else OpportunityPriority.MEDIUM,
                        description=f"Cancel {sub_name} to cut recurring AutoPay commitments.",
                        expected_benefit=f"Saves {sub_cost:.2f} monthly, boosting monthly liquidity.",
                        estimated_monthly_savings=sub_cost,
                        exposure_reduction=round((sub_cost / snapshot.monthly_income * 100.0) if snapshot.monthly_income > 0 else 1.0, 2),
                        confidence_score=92.0,
                        reason=f"High recurring cost relative to active subscriptions.",
                        simulation_available=True,
                        suggested_action=f"Simulate cancelling {sub_name} subscription.",
                        metadata={"subscription_name": sub_name, "monthly_cost": sub_cost},
                    )
                )

        # 2. Evaluate Exposure & Credit Reduction Opportunities
        if snapshot.active_emis_count > 0 or snapshot.active_bnpl_count > 0:
            total_loans = snapshot.active_emis_count + snapshot.active_bnpl_count
            opp_id = f"opp_loan_{uuid.uuid4().hex[:8]}"
            prio = OpportunityPriority.HIGH if snapshot.exposure_score > 50.0 else OpportunityPriority.MEDIUM

            opportunities.append(
                Opportunity(
                    opportunity_id=opp_id,
                    title="Pre-close Active Credit Obligation",
                    opportunity_type=OpportunityType.EXPOSURE_REDUCTION,
                    priority=prio,
                    description=f"Consolidate or pay off one of your {total_loans} active loan/BNPL obligations early.",
                    expected_benefit="Lowers overall financial exposure and improves financial health status.",
                    estimated_monthly_savings=0.0,
                    exposure_reduction=5.0,
                    confidence_score=88.0,
                    reason=f"Current exposure score stands at {snapshot.exposure_score:.1f}%.",
                    simulation_available=True,
                    suggested_action="Simulate early EMI pre-closure scenario.",
                    metadata={"active_loans_count": total_loans},
                )
            )

        # 3. Risk Alert Opportunity
        if snapshot.exposure_score > 60.0:
            opp_id = f"opp_risk_{uuid.uuid4().hex[:8]}"
            opportunities.append(
                Opportunity(
                    opportunity_id=opp_id,
                    title="High Financial Exposure Alert",
                    opportunity_type=OpportunityType.RISK_ALERT,
                    priority=OpportunityPriority.CRITICAL,
                    description="Your monthly commitments exceed 60% of monthly income.",
                    expected_benefit="Prevents potential liquidity shortfall and financial distress.",
                    estimated_monthly_savings=0.0,
                    exposure_reduction=10.0,
                    confidence_score=95.0,
                    reason="Exposure ratio exceeds recommended safety threshold.",
                    simulation_available=True,
                    suggested_action="Review and defer any upcoming major purchases.",
                    metadata={"exposure_score": snapshot.exposure_score},
                )
            )

        # 4. Integrate Decision Engine Recommendation as Opportunity
        if decision_result and decision_result.recommendation:
            rec = decision_result.recommendation
            opp_id = f"opp_dec_{uuid.uuid4().hex[:8]}"
            conf_val = rec.confidence.score if rec.confidence else 80.0

            opportunities.append(
                Opportunity(
                    opportunity_id=opp_id,
                    title=f"AI Decision: {rec.title}",
                    opportunity_type=OpportunityType.OPTIMIZATION_SUGGESTION,
                    priority=OpportunityPriority.HIGH,
                    description=rec.action_summary,
                    expected_benefit=rec.reason.primary_reason,
                    estimated_monthly_savings=float(rec.expected_financial_impact.get("savings_change", 0.0)),
                    exposure_reduction=abs(float(rec.expected_financial_impact.get("exposure_change", 0.0))),
                    confidence_score=conf_val,
                    reason=rec.reason.primary_reason,
                    simulation_available=True,
                    suggested_action=rec.suggested_next_action,
                    metadata={"recommendation_type": rec.recommendation_type.value},
                )
            )

        # 5. Integrate Financial DNA Suggestions as Opportunities
        if dna and dna.improvement_suggestions:
            for idx, sugg in enumerate(dna.improvement_suggestions[:2]):
                opp_id = f"opp_dna_{idx}_{uuid.uuid4().hex[:6]}"
                opportunities.append(
                    Opportunity(
                        opportunity_id=opp_id,
                        title=f"DNA Insight: {dna.primary_archetype.value.replace('_', ' ').title()}",
                        opportunity_type=OpportunityType.FINANCIAL_PLANNING,
                        priority=OpportunityPriority.MEDIUM,
                        description=sugg,
                        expected_benefit="Aligns spending habits with long-term financial stability.",
                        confidence_score=85.0,
                        reason=f"Derived from behavioral fingerprint analysis for {user_id}.",
                        simulation_available=False,
                        suggested_action="Review behavioral trait scores in dashboard.",
                        metadata={"archetype": dna.primary_archetype.value},
                    )
                )

        # Sort opportunities by priority
        prio_order = {
            OpportunityPriority.CRITICAL: 1,
            OpportunityPriority.HIGH: 2,
            OpportunityPriority.MEDIUM: 3,
            OpportunityPriority.LOW: 4,
        }
        opportunities.sort(key=lambda o: prio_order.get(o.priority, 99))

        summary = (
            f"Generated {len(opportunities)} proactive financial opportunities for user {user_id}."
        )

        return OpportunityFeed(
            user_id=user_id,
            opportunities=opportunities,
            generated_at=datetime.now(timezone.utc).isoformat(),
            summary=summary,
            metadata={"opportunity_count": len(opportunities)},
        )

    def generate_feed(
        self,
        snapshot: FinancialSnapshot,
        decision_result: DecisionResult | None = None,
        dna: FinancialDNA | None = None,
        twin: DigitalTwin | None = None,
    ) -> OpportunityFeed:
        """Convenience alias for generate_opportunities."""
        return self.generate_opportunities(snapshot, decision_result, dna, twin)

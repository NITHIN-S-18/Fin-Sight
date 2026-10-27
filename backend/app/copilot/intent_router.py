from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.copilot.intent_detector import IntentMatch, IntentType


@dataclass(frozen=True)
class RoutingDecision:
    """
    Structured routing information output by the IntentRouter.
    Includes placeholder fields for future decision pipeline chaining.
    """

    intent: IntentType
    target_engine: str
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)
    requires_simulation: bool = False
    routing_metadata: dict[str, Any] = field(default_factory=dict)
    # Placeholder fields for future decision pipeline chaining (Wave 2 readiness)
    next_engine: str | None = None
    pipeline_stage: str = "intent_routing"
    requires_decision_engine: bool = False


class IntentRouter:
    """
    Intent Router for decision intelligence pipeline.
    Determines target engine for an IntentMatch without executing downstream engines.
    """

    _ROUTING_MAP: dict[IntentType, tuple[str, bool]] = {
        IntentType.AFFORDABILITY_ANALYSIS: ("digital_twin", True),
        IntentType.WHAT_IF_SIMULATION: ("digital_twin", True),
        IntentType.RISK_EXPLANATION: ("ml_explainability", False),
        IntentType.FINANCIAL_HEALTH: ("business_intelligence", False),
        IntentType.SPENDING_ANALYSIS: ("spending_intelligence", False),
        IntentType.FINANCIAL_RECOMMENDATION: ("recommendation_engine", False),
        IntentType.FINANCIAL_GOALS: ("goals_engine", False),
        IntentType.FINANCIAL_ANOMALY: ("ml_anomaly", False),
        IntentType.UNKNOWN: ("default_handler", False),
    }

    def route(self, intent_match: IntentMatch) -> RoutingDecision:
        """
        Maps an IntentMatch to a structured RoutingDecision.
        Pure decision routing — no execution is performed.
        """
        target_engine, requires_simulation = self._ROUTING_MAP.get(
            intent_match.intent, ("default_handler", False)
        )

        return RoutingDecision(
            intent=intent_match.intent,
            target_engine=target_engine,
            confidence=intent_match.confidence,
            matched_keywords=list(intent_match.matched_keywords),
            requires_simulation=requires_simulation,
            routing_metadata={
                "source_metadata": dict(intent_match.metadata),
                "routed_by": "IntentRouter",
            },
            next_engine=None,
            pipeline_stage="intent_routing",
            requires_decision_engine=requires_simulation,
        )

    def route_intent(self, intent_match: IntentMatch) -> RoutingDecision:
        """Convenience alias for route."""
        return self.route(intent_match)

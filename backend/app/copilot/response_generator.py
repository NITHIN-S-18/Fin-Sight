from __future__ import annotations

from typing import Any

from app.copilot.intent_detector import IntentType
from app.decision.decision_engine import DecisionResult
from app.digital_twin.comparison_engine import FinancialComparison
from app.experience.opportunity_engine import OpportunityFeed


class ResponseGenerator:
    """
    Response Generator.

    Converts structured intelligence outputs (DecisionResult, FinancialComparison,
    OpportunityFeed, etc.) into deterministic, natural language responses.
    Does NOT use LLMs or non-deterministic natural language generation APIs.
    """

    def generate_response(
        self,
        decision_result: DecisionResult,
        comparison: FinancialComparison | None = None,
        opportunity_feed: OpportunityFeed | None = None,
    ) -> dict[str, Any]:
        """
        Formats a structured DecisionResult and context into a clean response dictionary.
        """
        rec = decision_result.recommendation
        reason = rec.reason
        conf = rec.confidence

        intent_str = decision_result.context_summary.get("intent", IntentType.FINANCIAL_HEALTH.value)
        conf_score = conf.score if conf else 80.0
        conf_level = conf.level.value if conf else "high"

        # Build natural language summary template
        summary_lines: list[str] = [
            f"Based on your financial analysis for {rec.title}:",
            f"{rec.action_summary}",
            f"Primary Reason: {reason.primary_reason}",
        ]

        if comparison:
            summary_lines.append(f"Simulation Outcome: {comparison.summary}")

        if conf:
            summary_lines.append(f"Decision Confidence: {conf.explanation}")

        full_summary = " ".join(summary_lines)

        all_supporting = list(reason.supporting_factors)
        if conf and conf.positive_factors:
            for factor in conf.positive_factors:
                if factor not in all_supporting:
                    all_supporting.append(factor)

        sim_available = decision_result.context_summary.get("simulation_compared", False) or comparison is not None or "digital_twin" in decision_result.context_summary.get("target_engine", "")

        metadata = dict(decision_result.metadata)
        metadata.update({
            "decision_id": decision_result.decision_id,
            "target_engine": decision_result.context_summary.get("target_engine", "none"),
            "user_id": decision_result.context_summary.get("user_id", ""),
            "generated_by": "ResponseGenerator",
        })

        return {
            "intent": intent_str,
            "recommendation": rec.title,
            "confidence": conf_score,
            "confidence_level": conf_level,
            "summary": full_summary,
            "supporting_factors": all_supporting,
            "simulation_available": sim_available,
            "suggested_next_action": rec.suggested_next_action,
            "metadata": metadata,
        }

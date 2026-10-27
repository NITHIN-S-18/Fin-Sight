from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IntentType(str, Enum):
    FINANCIAL_HEALTH = "financial_health"
    RISK_EXPLANATION = "risk_explanation"
    AFFORDABILITY_ANALYSIS = "affordability_analysis"
    WHAT_IF_SIMULATION = "what_if_simulation"
    SPENDING_ANALYSIS = "spending_analysis"
    FINANCIAL_RECOMMENDATION = "financial_recommendation"
    FINANCIAL_GOALS = "financial_goals"
    FINANCIAL_ANOMALY = "financial_anomaly"
    UNKNOWN = "unknown"


# Deterministic priority resolution mapping (1 = Highest Priority)
INTENT_PRIORITY: dict[IntentType, int] = {
    IntentType.WHAT_IF_SIMULATION: 1,
    IntentType.AFFORDABILITY_ANALYSIS: 2,
    IntentType.RISK_EXPLANATION: 3,
    IntentType.FINANCIAL_RECOMMENDATION: 4,
    IntentType.FINANCIAL_GOALS: 5,
    IntentType.FINANCIAL_ANOMALY: 6,
    IntentType.SPENDING_ANALYSIS: 7,
    IntentType.FINANCIAL_HEALTH: 8,
    IntentType.UNKNOWN: 9,
}


@dataclass(frozen=True)
class IntentMatch:
    """
    Data structure containing intent classification results.
    """

    intent: IntentType
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class IntentDetector:
    """
    Keyword-based Intent Detection Engine.

    Provides deterministic, rule-based financial intent classification without
    dependencies on ML models, NLP libraries, LLMs, or external APIs. Supports
    priority-based tie-breaking for multi-keyword matches.
    """

    def __init__(
        self,
        custom_keyword_map: dict[IntentType, list[str]] | None = None,
    ) -> None:
        self._keyword_map: dict[IntentType, list[str]] = custom_keyword_map or {
            IntentType.WHAT_IF_SIMULATION: [
                "what if",
                "what happens if",
                "simulate",
                "if i cancel",
                "if my salary",
                "if i close",
                "if i add",
                "suppose i",
                "scenario if",
            ],
            IntentType.AFFORDABILITY_ANALYSIS: [
                "can i afford",
                "can i buy",
                "can i purchase",
                "affordable",
                "can i get",
                "can i take a loan",
                "is it affordable",
                "can i pay for",
                "buy on emi",
            ],
            IntentType.RISK_EXPLANATION: [
                "why is my risk",
                "risk explanation",
                "why exposure increased",
                "why risk high",
                "risk factor",
                "exposure score high",
                "explain risk",
                "risk level",
                "why is exposure",
            ],
            IntentType.FINANCIAL_RECOMMENDATION: [
                "how can i reduce",
                "recommendation",
                "which emi should i close",
                "how to improve health",
                "advice to save",
                "what should i pay first",
                "financial advice",
                "suggest action",
                "how to cut exposure",
            ],
            IntentType.FINANCIAL_GOALS: [
                "goal",
                "saving goal",
                "afford a house next year",
                "target savings",
                "future goal",
                "financial plan",
                "long term goal",
                "save for house",
                "save for vehicle",
            ],
            IntentType.FINANCIAL_ANOMALY: [
                "transaction flagged",
                "unusual payment",
                "anomaly",
                "suspicious spend",
                "why was this flagged",
                "unexpected charge",
                "unusual transaction",
                "flagged payment",
                "spending alert",
            ],
            IntentType.SPENDING_ANALYSIS: [
                "where am i overspending",
                "spending analysis",
                "unnecessary subscriptions",
                "spending breakdown",
                "where is my money going",
                "spending pattern",
                "excessive spend",
                "top expenses",
                "spending profile",
            ],
            IntentType.FINANCIAL_HEALTH: [
                "financial health",
                "health score",
                "how am i doing",
                "financial status",
                "overall health",
                "health rating",
                "financial condition",
                "am i doing well",
                "how is my health",
            ],
        }

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalizes input text by lowercasing, stripping punctuation, and condensing spaces.
        """
        if not text:
            return ""
        lowered = text.lower()
        cleaned = re.sub(r"[^\w\s]", " ", lowered)
        return " ".join(cleaned.split())

    def detect_intent(self, text: str) -> IntentMatch:
        """
        Detects user financial intent from text using keyword matching and
        deterministic priority ordering for tie-breaking. Always returns exactly ONE intent.
        """
        normalized_text = self.normalize_text(text)
        if not normalized_text:
            return IntentMatch(
                intent=IntentType.UNKNOWN,
                confidence=0.0,
                matched_keywords=[],
                metadata={"raw_text": text, "normalized_text": "", "priority": INTENT_PRIORITY[IntentType.UNKNOWN]},
            )

        candidate_matches: list[tuple[float, int, IntentType, list[str]]] = []

        for intent, keywords in self._keyword_map.items():
            matched: list[str] = []
            for kw in keywords:
                normalized_kw = self.normalize_text(kw)
                if normalized_kw and normalized_kw in normalized_text:
                    matched.append(kw)

            if matched:
                match_count = len(matched)
                confidence = min(1.0, 0.5 + (match_count * 0.2))
                priority = INTENT_PRIORITY.get(intent, 99)
                # Sort key: confidence descending, priority ascending (1 is highest priority)
                candidate_matches.append((confidence, priority, intent, matched))

        if not candidate_matches:
            return IntentMatch(
                intent=IntentType.UNKNOWN,
                confidence=0.0,
                matched_keywords=[],
                metadata={"raw_text": text, "normalized_text": normalized_text, "priority": INTENT_PRIORITY[IntentType.UNKNOWN]},
            )

        # Sort candidate matches: highest confidence first, then lowest priority rank (highest priority)
        candidate_matches.sort(key=lambda x: (x[0], -x[1]), reverse=True)
        winning_confidence, winning_priority, winning_intent, winning_keywords = candidate_matches[0]

        return IntentMatch(
            intent=winning_intent,
            confidence=round(winning_confidence, 2),
            matched_keywords=winning_keywords,
            metadata={
                "raw_text": text,
                "normalized_text": normalized_text,
                "match_count": len(winning_keywords),
                "priority_rank": winning_priority,
                "candidates_evaluated": len(candidate_matches),
            },
        )

    def detect(self, text: str) -> IntentMatch:
        """Convenience alias for detect_intent."""
        return self.detect_intent(text)

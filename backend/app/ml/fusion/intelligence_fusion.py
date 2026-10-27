from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Mapping


@dataclass(frozen=True)
class EnginePredictionEnvelope:
    engine_name: str
    prediction: Any
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FinancialIntelligenceResponse:
    user_id: str
    predictions: dict[str, EnginePredictionEnvelope]
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


class FinancialIntelligenceFusionLayer:
    def __init__(self, weights: Mapping[str, float] | None = None, default_weight: float = 0.1) -> None:
        self._weights = dict(weights or {
            "distress": 0.40,
            "exposure_forecast": 0.25,
            "persona": 0.20,
            "anomaly": 0.15,
        })
        self._default_weight = default_weight

    def fuse(self, user_id: str, predictions: list[EnginePredictionEnvelope], metadata: dict[str, Any] | None = None) -> FinancialIntelligenceResponse:
        if not user_id:
            raise ValueError("Fusion requires a user identifier.")
        if not predictions:
            raise ValueError("Fusion requires at least one engine prediction.")

        weighted_confidence = 0.0
        total_weight = 0.0
        payload: dict[str, EnginePredictionEnvelope] = {}
        weight_breakdown: dict[str, float] = {}
        confidence_contributions: dict[str, float] = {}
        for item in predictions:
            if not item.engine_name:
                raise ValueError("Every fused prediction requires an engine name.")
            if item.engine_name in payload:
                raise ValueError(f"Duplicate fused engine prediction: {item.engine_name}")
            payload[item.engine_name] = item
            weight = float(self._weights.get(item.engine_name, self._default_weight))
            if not isfinite(weight) or weight <= 0.0:
                raise ValueError(f"Fusion weight must be positive and finite: {item.engine_name}")
            weight_breakdown[item.engine_name] = weight
            if item.confidence is not None:
                confidence = float(item.confidence)
                if not isfinite(confidence) or not 0.0 <= confidence <= 1.0:
                    raise ValueError(f"Engine confidence must be between 0 and 1: {item.engine_name}")
                weighted_confidence += confidence * weight
                total_weight += weight
                confidence_contributions[item.engine_name] = round(confidence * weight, 6)
        fused_confidence = weighted_confidence / total_weight if total_weight else 0.0
        return FinancialIntelligenceResponse(
            user_id=user_id,
            predictions=payload,
            confidence=round(fused_confidence, 4),
            metadata={
                **(metadata or {}),
                "weights": weight_breakdown,
                "confidence_contributions": confidence_contributions,
                "aggregation": "weighted_average",
                "confidence_basis": "weighted average of finite engine confidence values in the inclusive range 0 to 1",
            },
        )

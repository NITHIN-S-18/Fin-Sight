from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from app.core.exceptions import ExposureDataUnavailableError
from app.ml.fusion.intelligence_fusion import (
    EnginePredictionEnvelope,
    FinancialIntelligenceFusionLayer,
)
from app.ml.insights.insights_generator import AIInsightsLayer, InsightContext
from app.services.ml_service import MLService


def test_fusion_uses_only_present_valid_confidences() -> None:
    result = FinancialIntelligenceFusionLayer().fuse(
        "AUTH00000001",
        [
            EnginePredictionEnvelope("distress", "Low Risk", 0.8),
            EnginePredictionEnvelope("anomaly", False, None),
        ],
    )

    assert result.user_id == "AUTH00000001"
    assert result.predictions["distress"].prediction == "Low Risk"
    assert result.confidence == 0.8
    assert result.metadata["confidence_contributions"] == {"distress": 0.32}


def test_fusion_metadata_does_not_claim_universal_probability() -> None:
    result = FinancialIntelligenceFusionLayer().fuse(
        "AUTH00000001",
        [
            EnginePredictionEnvelope("distress", "Low Risk", 0.8),
            EnginePredictionEnvelope("persona", "Saver", 0.7),
        ],
    )

    assert result.confidence == 0.7667
    assert result.metadata["confidence_basis"].startswith("weighted average")
    assert "probability" not in result.metadata["confidence_basis"]


def test_current_state_contract_keeps_current_exposure_separate() -> None:
    state = MLService._current_state(
        {
            "exposure_score": 24.26,
            "monthly_commitments": 20621.0,
            "monthly_financial_capacity": 85000.0,
            "financial_health": "Healthy",
            "payment_reliability": 1.0,
        }
    )

    assert state.current_exposure == 24.26
    assert state.available_capacity == 64379.0
    assert state.payment_reliability == 1.0


def test_intelligence_current_state_comes_from_authoritative_exposure_service() -> None:
    authoritative = SimpleNamespace(
        current_financial_status=SimpleNamespace(
            exposure_score=24.26,
            monthly_total_commitments=20621.0,
            monthly_financial_capacity=85000.0,
            available_monthly_capacity=64379.0,
        ),
        financial_health=SimpleNamespace(financial_health_label="Healthy"),
        payment_reliability=1.0,
    )
    service = object.__new__(MLService)
    service._exposure_service = SimpleNamespace(get_exposure_intelligence=lambda user_id: authoritative)

    state = service._authoritative_current_state("AUTH00000317")

    assert state.current_exposure == 24.26
    assert state.monthly_commitments == 20621.0
    assert state.monthly_capacity == 85000.0
    assert state.available_capacity == 64379.0
    assert state.financial_health == "Healthy"
    assert state.payment_reliability == 1.0


def test_fusion_rejects_invalid_or_duplicate_engine_outputs() -> None:
    fusion = FinancialIntelligenceFusionLayer()

    with pytest.raises(ValueError, match="between 0 and 1"):
        fusion.fuse("user", [EnginePredictionEnvelope("distress", "High Risk", 1.2)])

    with pytest.raises(ValueError, match="Duplicate"):
        fusion.fuse(
            "user",
            [
                EnginePredictionEnvelope("distress", "Low Risk", 0.5),
                EnginePredictionEnvelope("distress", "High Risk", 0.5),
            ],
        )


def test_empty_snapshot_is_not_given_fabricated_intelligence() -> None:
    snapshot = SimpleNamespace(
        user_id="AUTH00000001",
        financial_profile={},
        transactions=pd.DataFrame(),
    )

    with pytest.raises(ExposureDataUnavailableError):
        MLService._ensure_snapshot_has_data(snapshot)


def test_anomaly_explanation_uses_decision_score_not_boolean_flag() -> None:
    insight = AIInsightsLayer().build_anomaly_insight(
        False,
        0.9,
        ["Anomaly score is 0.1234."],
        InsightContext(
            snapshot_metrics={
                "spending_variance": 0.2,
                "payment_reliability": 1.0,
                "autopay_coverage": 0.5,
            },
            prediction_metadata={"decision_score": 0.1234},
        ),
    )

    assert "0.12" in insight.explanation
    assert "False" not in insight.explanation

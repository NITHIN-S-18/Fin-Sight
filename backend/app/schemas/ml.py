from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EngineInsightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    prediction: Any = Field(description="Engine prediction value, normalized for presentation.", examples=["High Risk", 18.4])
    confidence: float | None = Field(default=None, description="Prediction confidence score.", examples=[0.91])
    explanation: str = Field(description="Business-friendly explanation.")
    recommendation: str = Field(description="Recommended next action.")
    supporting_factors: list[str] = Field(description="Supporting evidence used to generate the insight.")


class CurrentFinancialState(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    current_exposure: float = Field(description="Authoritative current commitment exposure as a percentage of monthly capacity.")
    monthly_commitments: float = Field(description="Authoritative current monthly commitment amount.")
    monthly_capacity: float = Field(description="Authoritative current monthly financial capacity.")
    available_capacity: float = Field(description="Authoritative current capacity remaining after commitments.")
    financial_health: str = Field(description="Authoritative current deterministic financial-health label.")
    payment_reliability: float | None = Field(description="Authoritative current payment reliability, or null when unavailable.")


class FinancialDistressResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "user_id": "U001",
                    "prediction": "Low Risk",
                    "confidence": 1.0,
                    "supporting_metadata": {"model_name": "financial_distress", "model_version": "v1.0"},
                    "insight": {
                        "prediction": "Low Risk",
                        "confidence": 1.0,
                        "explanation": "Financial distress risk remains low because exposure is only 1.28%, payment reliability is 100.0%, and recurring commitments use a manageable share of capacity.",
                        "recommendation": "Maintain the current payment discipline and review any new recurring commitment before activation.",
                        "supporting_factors": [
                            "Exposure score is 1.28%.",
                            "Commitment ratio is 1.3% of monthly capacity."
                        ],
                    },
                    "generated_at": "2026-08-03T13:11:52.874866Z",
                }
            ]
        },
    )

    user_id: str = Field(description="Unique user identifier.", examples=["U001"])
    prediction: str = Field(description="Predicted distress risk band.", examples=["High Risk"])
    confidence: float | None = Field(default=None, description="Prediction confidence.", examples=[0.91])
    probabilities: dict[str, float] | list[float] | None = Field(default=None, description="Next-month event class probabilities when available; not calibrated unless explicitly stated.")
    prediction_target: str = Field(description="Next-month failed, declined, or rejected transaction event.")
    forecast_horizon_months: int = Field(default=1, description="Prediction horizon in calendar months.")
    confidence_semantics: str = Field(description="Meaning and calibration limitations of the model confidence value.")
    current_state: CurrentFinancialState = Field(description="Authoritative deterministic current financial state.")
    is_current_risk_score: bool = Field(default=False, description="Always false: this is not a current financial-risk score.")
    supporting_metadata: dict[str, str] = Field(description="Metadata that supports the prediction.")
    insight: EngineInsightResponse = Field(description="Business-friendly insight derived from the model output.")
    generated_at: datetime = Field(description="Timestamp of the response generation.")


class ShortfallFactorDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    factor: str = Field(description="Factor identifier or key phrase.")
    severity: str = Field(description="Severity classification: HIGH, MEDIUM, or LOW.")
    description: str = Field(description="Data-grounded description of the factor.")


class FinancialShortfallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(description="Authenticated financial user identifier.")
    available: bool = Field(description="Whether sufficient history and a shortfall model are available.")
    model_version: str = Field(description="Shortfall model version.")
    prediction: str = Field(description="Categorical next-month shortfall prediction.")
    shortfall_risk: str = Field(description="LOW, MODERATE, or HIGH categorical risk.")
    next_month_horizon: str = Field(description="Calendar month being evaluated.")
    expected_net_cash: float | None = Field(default=None, description="Authoritative Model 1 expected next-month net cash.")
    expected_income: float | None = Field(default=None, description="Authoritative Model 1 expected next-month income.")
    expected_total_expenses: float | None = Field(default=None, description="Authoritative Model 1 expected next-month total expenses.")
    contributing_factors: list[str] = Field(default_factory=list, description="Historical factors influencing the prediction.")
    factor_details: list[ShortfallFactorDetail] = Field(default_factory=list, description="Detailed factors with calculated severity.")
    risk_explanation: str | None = Field(default=None, description="Honest synthesis of Model 4 classification and Model 1 cash-flow forecast.")
    recommended_actions: list[str] = Field(default_factory=list, description="Deterministic actions based on observed factors.")
    availability_status: str = Field(description="available or insufficient_history.")

class ExposureForecastResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "user_id": "U001",
                    "future_exposure": 1.272898,
                    "confidence": 0.9867,
                    "insight": {
                        "prediction": 1.272898,
                        "confidence": 0.9867,
                        "explanation": "Exposure is projected to remain broadly stable around 1.27%.",
                        "recommendation": "Keep monitoring fixed commitments and avoid adding unnecessary recurring obligations.",
                        "supporting_factors": ["Current exposure score is 1.28%."]
                    },
                    "generated_at": "2026-08-03T13:11:52.935530Z",
                }
            ]
        },
    )

    user_id: str = Field(description="Unique user identifier.", examples=["U001"])
    future_exposure: float = Field(description="Forecast future exposure score.", examples=[18.4])
    forecast_exposure: float = Field(description="One-month-ahead exposure forecast; never the current exposure.", examples=[18.4])
    forecast_horizon_months: int = Field(default=1, description="Forecast horizon in calendar months.")
    target_definition: str = Field(description="Observed next-month successful commitments divided by successful positive next-month income, multiplied by 100.")
    forecast_available: bool = Field(description="Whether a model forecast is available for this response.")
    availability_status: str = Field(description="Availability status for the forecast and its training target coverage.")
    observed_target_coverage: float = Field(description="Share of reference snapshots with an observed positive-income next-month target.")
    confidence: float | None = Field(default=None, description="Forecast confidence.", examples=[0.87])
    confidence_semantics: str = Field(description="Meaning and calibration limitations of the forecast confidence value.")
    current_state: CurrentFinancialState = Field(description="Authoritative deterministic current financial state.")
    insight: EngineInsightResponse = Field(description="Business-friendly insight derived from the forecast.")
    generated_at: datetime = Field(description="Timestamp of the response generation.")

class PersonaResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "user_id": "U001",
                    "cluster": 0,
                    "persona_name": "Saver",
                    "confidence": 0.82,
                    "insight": {
                        "prediction": 0,
                        "confidence": 0.82,
                        "explanation": "This cluster behaves like a saver profile, characterised by low commitment pressure and strong payment discipline.",
                        "recommendation": "Keep the low-burden pattern intact and continue prioritising payment discipline over new recurring spend.",
                        "supporting_factors": ["Saver profile", "Low commitment pressure", "High payment discipline"]
                    },
                    "generated_at": "2026-08-03T13:11:53.102586Z",
                }
            ]
        },
    )

    user_id: str = Field(description="Unique user identifier.", examples=["U001"])
    cluster: int | str = Field(description="Cluster identifier from the behaviour engine.", examples=[2])
    current_profile_cluster: int | str = Field(description="Current financial-profile cluster; not a future-behaviour prediction.", examples=[2])
    persona_name: str = Field(description="Readable persona label.", examples=["Balanced"])
    descriptive_only: bool = Field(default=True, description="True because the persona is a descriptive current-profile cluster.")
    cluster_semantics: str = Field(description="Current-profile cluster semantics.")
    confidence: float | None = Field(default=None, description="Cluster confidence.", examples=[0.78])
    current_state: CurrentFinancialState = Field(description="Authoritative deterministic current financial state.")
    insight: EngineInsightResponse = Field(description="Business-friendly insight derived from the persona.")
    generated_at: datetime = Field(description="Timestamp of the response generation.")

class AnomalyResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "user_id": "U001",
                    "anomaly": False,
                    "score": 0.030978352599703052,
                    "confidence": 0.969,
                    "insight": {
                        "prediction": False,
                        "confidence": 0.969,
                        "explanation": "No strong anomaly is visible because the score is 0.03 and the payment pattern remains broadly consistent.",
                        "recommendation": "Continue monitoring the account and re-check the score if spending variance or payment failures increase.",
                        "supporting_factors": ["Anomaly score is 0.0310.", "Spending variance is 0.15."]
                    },
                    "generated_at": "2026-08-03T13:11:53.161466Z",
                }
            ]
        },
    )

    user_id: str = Field(description="Unique user identifier.", examples=["U001"])
    anomaly: bool = Field(description="Whether unusual behaviour was detected.", examples=[False])
    score: float = Field(description="Anomaly score from the model.", examples=[0.12])
    reference_population_anomaly: bool = Field(description="Whether the current feature snapshot is anomalous relative to the reference population.")
    anomaly_score: float = Field(description="Isolation Forest reference-population decision score.")
    anomaly_status: str = Field(description="Reference-population anomaly status.")
    comparison_population: str = Field(description="Population against which the feature snapshot is compared.")
    not_fraud_detection: bool = Field(default=True, description="True because this is not fraud or transaction-level anomaly detection.")
    confidence: float | None = Field(
        default=None,
        description="Heuristic anomaly-strength value; not a calibrated probability.",
        examples=[0.81],
    )
    confidence_semantics: str = Field(description="Heuristic anomaly-strength meaning; not a calibrated probability.")
    current_state: CurrentFinancialState = Field(description="Authoritative deterministic current financial state.")
    insight: EngineInsightResponse = Field(description="Business-friendly insight derived from the anomaly score.")
    generated_at: datetime = Field(description="Timestamp of the response generation.")

class FinancialIntelligenceResponseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "user_id": "U001",
                    "distress": {
                        "user_id": "U001",
                        "prediction": "Low Risk",
                        "confidence": 1.0,
                        "supporting_metadata": {"model_name": "financial_distress", "model_version": "v1.0"},
                        "insight": {
                            "prediction": "Low Risk",
                            "confidence": 1.0,
                            "explanation": "Financial distress risk remains low because exposure is only 1.28%, payment reliability is 100.0%, and recurring commitments use a manageable share of capacity.",
                            "recommendation": "Maintain the current payment discipline and review any new recurring commitment before activation.",
                            "supporting_factors": ["Exposure score is 1.28%.", "Commitment ratio is 1.3% of monthly capacity."]
                        },
                        "generated_at": "2026-08-03T13:11:53.212289Z",
                    },
                    "exposure_forecast": {
                        "user_id": "U001",
                        "future_exposure": 1.272898,
                        "confidence": 0.9867,
                        "insight": {
                            "prediction": 1.272898,
                            "confidence": 0.9867,
                            "explanation": "Exposure is projected to remain broadly stable around 1.27%.",
                            "recommendation": "Keep monitoring fixed commitments and avoid adding unnecessary recurring obligations.",
                            "supporting_factors": ["Current exposure score is 1.28%."]
                        },
                        "generated_at": "2026-08-03T13:11:53.251797Z",
                    },
                    "persona": {
                        "user_id": "U001",
                        "cluster": 0,
                        "persona_name": "Saver",
                        "confidence": 0.82,
                        "insight": {
                            "prediction": 0,
                            "confidence": 0.82,
                            "explanation": "This cluster behaves like a saver profile, characterised by low commitment pressure and strong payment discipline.",
                            "recommendation": "Keep the low-burden pattern intact and continue prioritising payment discipline over new recurring spend.",
                            "supporting_factors": ["Saver profile", "Low commitment pressure", "High payment discipline"]
                        },
                        "generated_at": "2026-08-03T13:11:53.280310Z",
                    },
                    "anomaly": {
                        "user_id": "U001",
                        "anomaly": False,
                        "score": 0.030978352599703052,
                        "confidence": 0.969,
                        "insight": {
                            "prediction": False,
                            "confidence": 0.969,
                            "explanation": "No strong anomaly is visible because the score is 0.03 and the payment pattern remains broadly consistent.",
                            "recommendation": "Continue monitoring the account and re-check the score if spending variance or payment failures increase.",
                            "supporting_factors": ["Anomaly score is 0.0310.", "Spending variance is 0.15."]
                        },
                        "generated_at": "2026-08-03T13:11:53.328523Z",
                    },
                    "fused_confidence": 0.9517,
                    "generated_at": "2026-08-03T13:11:53.328657Z",
                }
            ]
        },
    )

    user_id: str = Field(description="Unique user identifier.", examples=["U001"])
    distress: FinancialDistressResponse = Field(description="Distress engine result.")
    exposure_forecast: ExposureForecastResponse = Field(description="Exposure forecast engine result.")
    persona: PersonaResponse = Field(description="Behaviour engine result.")
    anomaly: AnomalyResponse = Field(description="Anomaly engine result.")
    current_state: CurrentFinancialState = Field(description="Authoritative deterministic current financial state.")
    model_signals: dict[str, dict[str, Any]] = Field(description="Per-model predictions, availability, and confidence semantics.")
    signal_quality: dict[str, Any] = Field(description="Per-model signal quality metadata; not a universal probability.")
    fused_confidence: float | None = Field(default=None, description="Deprecated weighted signal summary. Not a probability, risk score, or universal AI confidence.", examples=[0.84])
    generated_at: datetime = Field(description="Timestamp of the fused response generation.")

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SimulationRequest(BaseModel):
    scenario_type: str = Field(
        description="Scenario type accepted by the Digital Twin ScenarioBuilder.",
        examples=["add_subscription"],
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Scenario parameters. The user's baseline is always taken from JWT-authenticated data.",
    )


class SimulationMetric(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    baseline: float = Field(description="Baseline metric value.")
    projected: float = Field(description="Projected metric value after the scenario.")
    change: float = Field(description="Projected minus baseline.")


class SimulationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    scenario_type: str
    baseline_health: str
    projected_health: str
    baseline_exposure: float
    projected_exposure: float
    baseline_commitments: float
    projected_commitments: float
    available_capacity: float
    change: dict[str, SimulationMetric]
    risk_interpretation: str
    recommendation: str
    applied_changes: dict[str, Any]
    monthly_capacity: float | None = Field(default=None, description="Total monthly financial capacity.")
    monthly_deficit: float = Field(default=0.0, description="Monthly deficit if commitments exceed capacity.")

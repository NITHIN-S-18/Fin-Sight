from __future__ import annotations

from typing import Any

from fastapi import Depends

from app.core.exceptions import ExposureDataUnavailableError
from app.digital_twin.comparison_engine import ComparisonEngine
from app.digital_twin.scenario_builder import Scenario, ScenarioBuilder, ScenarioType
from app.digital_twin.twin_engine import DigitalTwinEngine, FinancialSnapshot
from app.schemas.simulator import SimulationMetric, SimulationRequest, SimulationResponse
from app.services.exposure_service import ExposureService, get_exposure_service


class SimulatorService:
    def __init__(self, exposure_service: ExposureService) -> None:
        self._exposure_service = exposure_service
        self._twin_engine = DigitalTwinEngine()
        self._scenario_builder = ScenarioBuilder(self._twin_engine)
        self._comparison_engine = ComparisonEngine()

    def simulate(self, user_id: str, request: SimulationRequest) -> SimulationResponse:
        try:
            scenario_type = ScenarioType(request.scenario_type)
        except ValueError as exc:
            raise ValueError(f"Unsupported scenario type: {request.scenario_type}") from exc

        intelligence = self._exposure_service.get_exposure_intelligence(user_id)
        status = intelligence.current_financial_status
        health = intelligence.financial_health
        snapshot = FinancialSnapshot(
            user_id=user_id,
            monthly_income=float(status.monthly_financial_capacity),
            monthly_commitments=float(status.monthly_total_commitments),
            exposure_score=float(status.exposure_score),
            financial_health_score=float(health.financial_health_score),
            financial_health_status=health.financial_health_label,
            active_subscriptions_count=int(getattr(intelligence.commitment_breakdown.subscriptions, "active_commitments", 0)),
            active_emis_count=int(getattr(intelligence.commitment_breakdown.emis, "active_commitments", 0)),
            active_bnpl_count=int(getattr(intelligence.commitment_breakdown.bnpl, "active_commitments", 0)),
            monthly_savings=max(0.0, float(status.monthly_financial_capacity) - float(status.monthly_total_commitments)),
            subscriptions=self._largest_item(intelligence.commitment_breakdown.subscriptions, "monthly_cost"),
            emis=self._largest_item(intelligence.commitment_breakdown.emis, "monthly_emi"),
            bnpl_items=self._largest_item(intelligence.commitment_breakdown.bnpl, "monthly_installment"),
            metadata={"source": "authenticated_exposure_service"},
        )
        twin = self._twin_engine.create_twin(snapshot)
        result = self._scenario_builder.apply_scenario(
            twin,
            Scenario(scenario_type=scenario_type, parameters=request.parameters),
        )
        if not result.success or result.modified_twin is None:
            raise ValueError(result.message or "Scenario could not be applied.")

        comparison = self._comparison_engine.compare(twin, result.modified_twin)
        projected = comparison.after_snapshot
        assert projected is not None
        commitment_delta = comparison.metrics["monthly_commitments"].difference
        exposure_delta = comparison.metrics["exposure"].difference
        health_delta = comparison.metrics["financial_health"].difference
        risk = self._risk_interpretation(exposure_delta, health_delta, projected.financial_health_status)
        recommendation = self._recommendation(exposure_delta, projected.financial_health_status)
        return SimulationResponse(
            user_id=user_id,
            scenario_type=scenario_type.value,
            baseline_health=snapshot.financial_health_status,
            projected_health=projected.financial_health_status,
            baseline_exposure=snapshot.exposure_score,
            projected_exposure=projected.exposure_score,
            baseline_commitments=snapshot.monthly_commitments,
            projected_commitments=projected.monthly_commitments,
            available_capacity=round(max(0.0, projected.monthly_income - projected.monthly_commitments), 2),
            change={
                "commitments": SimulationMetric(
                    baseline=snapshot.monthly_commitments,
                    projected=projected.monthly_commitments,
                    change=commitment_delta,
                ),
                "exposure": SimulationMetric(
                    baseline=snapshot.exposure_score,
                    projected=projected.exposure_score,
                    change=exposure_delta,
                ),
                "health": SimulationMetric(
                    baseline=snapshot.financial_health_score,
                    projected=projected.financial_health_score,
                    change=health_delta,
                ),
            },
            risk_interpretation=risk,
            recommendation=recommendation,
            applied_changes=result.applied_changes,
            monthly_capacity=round(projected.monthly_income, 2),
            monthly_deficit=round(max(0.0, projected.monthly_commitments - projected.monthly_income), 2),
        )

    @staticmethod
    def _largest_item(bucket: Any, amount_key: str) -> list[dict[str, Any]]:
        item = getattr(bucket, "largest_commitment", None)
        if item is None:
            return []
        name = getattr(item, "commitment_name", "")
        amount = float(getattr(item, "monthly_amount", 0.0))
        return [{"id": name, "name": name, amount_key: amount}]

    @staticmethod
    def _risk_interpretation(exposure_delta: float, health_delta: float, health: str) -> str:
        if exposure_delta > 0 or health_delta < 0:
            return f"Risk increases under this scenario; projected health is {health}."
        if exposure_delta < 0 or health_delta > 0:
            return f"Risk improves under this scenario; projected health is {health}."
        return f"Risk is broadly unchanged; projected health is {health}."

    @staticmethod
    def _recommendation(exposure_delta: float, health: str) -> str:
        if exposure_delta > 0:
            return "Review the projected commitment before applying it and preserve enough monthly capacity for existing obligations."
        if exposure_delta < 0:
            return "This scenario improves projected capacity; preserve the reduction rather than adding an equivalent new obligation."
        return f"Monitor the scenario impact and keep projected commitments consistent with the {health} health level."


def get_simulator_service(
    exposure_service: ExposureService = Depends(get_exposure_service),
) -> SimulatorService:
    return SimulatorService(exposure_service)

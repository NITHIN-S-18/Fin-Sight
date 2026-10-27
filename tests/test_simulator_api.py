from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.digital_twin.scenario_builder import Scenario, ScenarioBuilder, ScenarioType
from app.digital_twin.twin_engine import DigitalTwinEngine, FinancialSnapshot
from app.schemas.simulator import SimulationRequest
from app.services.simulator_service import SimulatorService


def _snapshot() -> FinancialSnapshot:
    return FinancialSnapshot(
        user_id="AUTH00000001",
        monthly_income=100000.0,
        monthly_commitments=20000.0,
        exposure_score=20.0,
        financial_health_score=90.0,
        financial_health_status="Excellent",
        monthly_savings=80000.0,
    )


def test_scenario_builder_does_not_mutate_original_snapshot() -> None:
    original = _snapshot()
    twin = DigitalTwinEngine().create_twin(original)
    result = ScenarioBuilder().apply_scenario(
        twin,
        Scenario(ScenarioType.ADD_SUBSCRIPTION, {"monthly_cost": 500.0}),
    )

    assert result.success is True
    assert original.monthly_commitments == 20000.0
    assert result.modified_twin is not None
    assert result.modified_twin.snapshot.monthly_commitments == 20500.0


def test_simulator_uses_authenticated_exposure_state_and_returns_deltas() -> None:
    class ExposureStub:
        def get_exposure_intelligence(self, user_id: str):
            assert user_id == "AUTH00000001"
            bucket = SimpleNamespace(
                active_commitments=1,
                largest_commitment=SimpleNamespace(commitment_name="Existing", monthly_amount=20000.0),
            )
            return SimpleNamespace(
                current_financial_status=SimpleNamespace(
                    monthly_financial_capacity=100000.0,
                    monthly_total_commitments=20000.0,
                    exposure_score=20.0,
                ),
                financial_health=SimpleNamespace(
                    financial_health_score=90.0,
                    financial_health_label="Excellent",
                ),
                commitment_breakdown=SimpleNamespace(
                    subscriptions=bucket,
                    emis=bucket,
                    bnpl=bucket,
                ),
            )

    response = SimulatorService(ExposureStub()).simulate(
        "AUTH00000001",
        SimulationRequest(scenario_type="add_subscription", parameters={"monthly_cost": 500.0}),
    )

    assert response.user_id == "AUTH00000001"
    assert response.baseline_commitments == 20000.0
    assert response.projected_commitments == 20500.0
    assert response.change["commitments"].change == 500.0
    assert response.available_capacity == 79500.0
    assert response.projected_exposure == 20.5


def test_simulator_preserves_exposure_above_100_percent() -> None:
    class ExposureStub:
        def get_exposure_intelligence(self, user_id: str):
            assert user_id == "AUTH00000001"
            bucket = SimpleNamespace(
                active_commitments=1,
                largest_commitment=SimpleNamespace(commitment_name="Existing", monthly_amount=49000.0),
            )
            return SimpleNamespace(
                current_financial_status=SimpleNamespace(
                    monthly_financial_capacity=50000.0,
                    monthly_total_commitments=49000.0,
                    exposure_score=98.0,
                ),
                financial_health=SimpleNamespace(
                    financial_health_score=25.0,
                    financial_health_label="High Risk",
                ),
                commitment_breakdown=SimpleNamespace(
                    subscriptions=bucket,
                    emis=bucket,
                    bnpl=bucket,
                ),
            )

    response = SimulatorService(ExposureStub()).simulate(
        "AUTH00000001",
        SimulationRequest(scenario_type="add_subscription", parameters={"monthly_cost": 2000.0}),
    )

    assert response.projected_commitments == 51000.0
    assert response.projected_exposure == 102.0


def test_simulator_rejects_unsupported_scenarios() -> None:
    with pytest.raises(ValueError, match="Unsupported scenario type"):
        SimulatorService(object()).simulate(
            "AUTH00000001",
            SimulationRequest(scenario_type="invented_scenario"),
        )


def test_simulator_handles_add_other_and_tenure_metadata() -> None:
    class ExposureStub:
        def get_exposure_intelligence(self, user_id: str):
            bucket = SimpleNamespace(
                active_commitments=1,
                largest_commitment=SimpleNamespace(commitment_name="Existing", monthly_amount=20000.0),
            )
            return SimpleNamespace(
                current_financial_status=SimpleNamespace(
                    monthly_financial_capacity=100000.0,
                    monthly_total_commitments=20000.0,
                    exposure_score=20.0,
                ),
                financial_health=SimpleNamespace(
                    financial_health_score=85.0,
                    financial_health_label="Healthy",
                ),
                commitment_breakdown=SimpleNamespace(
                    subscriptions=bucket,
                    emis=bucket,
                    bnpl=bucket,
                ),
            )

    response = SimulatorService(ExposureStub()).simulate(
        "AUTH00000001",
        SimulationRequest(
            scenario_type="add_other",
            parameters={"monthly_amount": 5000.0, "name": "Custom Obligation", "duration_months": 12},
        ),
    )

    assert response.projected_commitments == 25000.0
    assert response.projected_exposure == 25.0
    assert response.applied_changes["duration_months"] == 12
    assert response.applied_changes["total_commitment"] == 60000.0
    assert response.available_capacity == 75000.0
    assert response.monthly_deficit == 0.0


def test_simulator_health_transition_never_inverts_labels() -> None:
    class ExposureStub:
        def get_exposure_intelligence(self, user_id: str):
            bucket = SimpleNamespace(
                active_commitments=2,
                largest_commitment=SimpleNamespace(commitment_name="Existing", monthly_amount=48992.83),
            )
            return SimpleNamespace(
                current_financial_status=SimpleNamespace(
                    monthly_financial_capacity=170000.0,
                    monthly_total_commitments=48992.83,
                    exposure_score=28.82,
                ),
                financial_health=SimpleNamespace(
                    financial_health_score=79.0,
                    financial_health_label="Moderate",
                ),
                commitment_breakdown=SimpleNamespace(
                    subscriptions=bucket,
                    emis=bucket,
                    bnpl=bucket,
                ),
            )

    response = SimulatorService(ExposureStub()).simulate(
        "AUTH00000001",
        SimulationRequest(scenario_type="add_bnpl", parameters={"monthly_installment": 5000.0, "installments": 6}),
    )

    assert response.baseline_health == "Moderate"
    assert response.change["health"].change <= 0.0
    assert response.projected_health in ("Moderate", "Risky", "Critical")
    assert response.projected_health != "Healthy"
    assert response.applied_changes["total_commitment"] == 30000.0


def test_simulator_endpoint_requires_auth_and_rejects_unauthenticated() -> None:
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    unauth_resp = client.post(
        "/api/v1/simulator/simulate",
        json={"scenario_type": "add_subscription", "parameters": {"monthly_cost": 500.0}},
    )
    assert unauth_resp.status_code == 401

from types import SimpleNamespace

import pytest

from app.copilot.copilot_service import CopilotService


def exposure_intelligence():
    commitment = SimpleNamespace(
        commitment_name="Streaming",
        monthly_amount=500.0,
    )
    bucket = SimpleNamespace(
        active_commitments=1,
        largest_commitment=commitment,
    )
    return SimpleNamespace(
        current_financial_status=SimpleNamespace(
            monthly_financial_capacity=50000.0,
            monthly_total_commitments=500.0,
            exposure_score=1.0,
            available_monthly_capacity=49500.0,
        ),
        financial_health=SimpleNamespace(
            financial_health_score=92.0,
            financial_health_label="Excellent",
        ),
        commitment_breakdown=SimpleNamespace(
            subscriptions=bucket,
            emis=SimpleNamespace(active_commitments=0, largest_commitment=None),
            bnpl=SimpleNamespace(active_commitments=0, largest_commitment=None),
        ),
    )


class ExposureServiceStub:
    def get_exposure_intelligence(self, user_id: str):
        assert user_id == "AUTH00000001"
        return exposure_intelligence()


def test_copilot_uses_authoritative_financial_context():
    service = CopilotService(exposure_service=ExposureServiceStub())

    snapshot = service._build_financial_snapshot("AUTH00000001")
    response = service.query_copilot("AUTH00000001", "What is my financial health?")

    assert snapshot.monthly_income == 50000.0
    assert snapshot.monthly_commitments == 500.0
    assert response.confidence >= 0
    assert response.metadata["user_id"] == "AUTH00000001"


def test_copilot_does_not_fabricate_snapshot_when_exposure_fails():
    class FailingExposureService:
        def get_exposure_intelligence(self, user_id: str):
            raise RuntimeError("backend unavailable")

    service = CopilotService(exposure_service=FailingExposureService())

    with pytest.raises(RuntimeError, match="backend unavailable"):
        service.query_copilot("AUTH00000001", "What is my exposure?")


def test_copilot_requires_exposure_service():
    with pytest.raises(RuntimeError, match="requires an exposure service"):
        CopilotService().query_copilot("AUTH00000001", "What is my exposure?")


def test_scenario_parameters_are_not_mutated():
    service = CopilotService(exposure_service=ExposureServiceStub())
    parameters = {"percentage": 10.0}

    service.query_copilot("AUTH00000001", "What if my salary increases?", parameters)

    assert parameters == {"percentage": 10.0}

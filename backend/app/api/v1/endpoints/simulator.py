from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import get_current_financial_user
from app.database.models.user import User
from app.schemas.simulator import SimulationRequest, SimulationResponse
from app.services.simulator_service import SimulatorService, get_simulator_service

router = APIRouter(prefix="/simulator", tags=["What-If Simulator"])


@router.post(
    "/simulate",
    response_model=SimulationResponse,
    status_code=status.HTTP_200_OK,
    summary="Simulate a financial scenario",
    description="Runs an in-memory scenario against the authenticated user's current financial state without modifying stored transactions.",
)
def simulate(
    request: SimulationRequest,
    current_user: User = Depends(get_current_financial_user),
    service: SimulatorService = Depends(get_simulator_service),
) -> SimulationResponse:
    try:
        return service.simulate(current_user.user_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

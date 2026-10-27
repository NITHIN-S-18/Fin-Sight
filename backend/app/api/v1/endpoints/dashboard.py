from fastapi import APIRouter, Depends, Path, status

from app.schemas.dashboard import DashboardOnboardingResponse, DashboardResponse
from app.core.security import get_current_financial_user, require_financial_user
from app.database.models.user import User
from app.services.dashboard_service import DashboardService, get_dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard Intelligence"])


@router.get(
    "/{user_id}",
    response_model=DashboardResponse | DashboardOnboardingResponse,
    summary="Get dashboard intelligence",
    description="Orchestrate and compile a frontend-friendly unified financial dashboard for the user.",
    response_description="Unified dashboard intelligence including profiles, health, exposure, highlights, recommendations, alerts, and statistics.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "User not found or no financial data available.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Validation error.",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Dashboard compilation or processing error.",
        },
    },
)
async def get_dashboard_intelligence(
    user_id: str = Path(..., description="Unique user identifier such as U001.", examples=["U001"]),
    current_user: User = Depends(get_current_financial_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardResponse:
    return service.get_dashboard_intelligence(require_financial_user(user_id, current_user))

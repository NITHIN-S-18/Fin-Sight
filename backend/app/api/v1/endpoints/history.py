from fastapi import APIRouter, Depends

from app.core.security import get_current_financial_user
from app.database.models.user import User
from app.schemas.history import HistoricalDashboardResponse
from app.services.history_service import HistoryService, get_history_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard Intelligence"])


@router.get(
    "/history",
    response_model=HistoricalDashboardResponse,
    summary="Get authenticated historical dashboard metrics",
    description="Returns monthly metrics calculated only from the authenticated user's successful transaction history.",
)
def get_dashboard_history(
    current_user: User = Depends(get_current_financial_user),
    service: HistoryService = Depends(get_history_service),
) -> HistoricalDashboardResponse:
    return service.get_history(current_user.user_id)

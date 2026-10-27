from fastapi import APIRouter, Depends, Path

from app.core.security import get_current_financial_user, require_financial_user
from app.database.models.user import User
from app.schemas.forecast import CashFlowForecastResponse
from app.services.cashflow_forecast_service import CashFlowForecastService, get_cashflow_forecast_service

router = APIRouter(prefix="/forecast", tags=["Forecasting"])


@router.get(
    "/cash-flow/{user_id}",
    response_model=CashFlowForecastResponse,
    summary="Forecast next-month cash flow",
    description="Forecasts next-month income, committed expenses, variable expenses, total expenses, and net cash from observed authenticated transaction history.",
)
def get_cash_flow_forecast(
    user_id: str = Path(..., description="Authenticated financial user identifier."),
    current_user: User = Depends(get_current_financial_user),
    service: CashFlowForecastService = Depends(get_cashflow_forecast_service),
) -> CashFlowForecastResponse:
    return service.forecast(require_financial_user(user_id, current_user))

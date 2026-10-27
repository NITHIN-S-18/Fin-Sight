from fastapi import APIRouter, Depends, status

from app.core.security import get_current_financial_user
from app.database.models.user import User
from app.schemas.income import (
    IncomeConfigurationResponse,
    IncomeConfigurationUpdateRequest,
)
from app.services.income_service import IncomeService, get_income_service

router = APIRouter(prefix="/income", tags=["Income Configuration"])


@router.get("/config", response_model=IncomeConfigurationResponse)
def get_income_configuration(
    user: User = Depends(get_current_financial_user),
    service: IncomeService = Depends(get_income_service),
) -> IncomeConfigurationResponse:
    return service.get_income_configuration_response(user.user_id)


@router.put("/config", response_model=IncomeConfigurationResponse)
def update_income_configuration(
    request: IncomeConfigurationUpdateRequest,
    user: User = Depends(get_current_financial_user),
    service: IncomeService = Depends(get_income_service),
) -> IncomeConfigurationResponse:
    return service.update_income_configuration(user.user_id, request)

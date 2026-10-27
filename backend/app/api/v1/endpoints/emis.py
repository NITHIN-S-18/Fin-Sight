from fastapi import APIRouter, Depends, Path, status

from app.schemas.emi import EmiIntelligenceResponse
from app.core.security import get_current_financial_user, require_financial_user
from app.database.models.user import User
from app.services.emi_service import EmiService, get_emi_service

router = APIRouter(prefix="/emis", tags=["EMI Intelligence"])


@router.get(
    "/{user_id}",
    response_model=EmiIntelligenceResponse,
    summary="Get EMI intelligence",
    description="Analyze the user's EMI transactions and return EMI intelligence instead of raw transaction data.",
    response_description="Derived EMI intelligence for the user.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "User not found or no EMI transactions available.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Validation error.",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "EMI intelligence processing error.",
        },
    },
)
async def get_emi_intelligence(
    user_id: str = Path(..., description="Unique user identifier such as U001.", examples=["U001"]),
    current_user: User = Depends(get_current_financial_user),
    service: EmiService = Depends(get_emi_service),
) -> EmiIntelligenceResponse:
    return service.get_emi_intelligence(require_financial_user(user_id, current_user))
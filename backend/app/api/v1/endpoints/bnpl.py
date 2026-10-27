from fastapi import APIRouter, Depends, Path, status

from app.schemas.bnpl import BnplIntelligenceResponse
from app.core.security import get_current_financial_user, require_financial_user
from app.database.models.user import User
from app.services.bnpl_service import BnplService, get_bnpl_service

router = APIRouter(prefix="/bnpl", tags=["BNPL Intelligence"])


@router.get(
    "/{user_id}",
    response_model=BnplIntelligenceResponse,
    summary="Get BNPL intelligence",
    description="Analyze the user's BNPL transactions and return BNPL intelligence instead of raw transaction data.",
    response_description="Derived BNPL intelligence for the user.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "User not found or no BNPL transactions available.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Validation error.",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "BNPL intelligence processing error.",
        },
    },
)
async def get_bnpl_intelligence(
    user_id: str = Path(..., description="Unique user identifier such as U001.", examples=["U001"]),
    current_user: User = Depends(get_current_financial_user),
    service: BnplService = Depends(get_bnpl_service),
) -> BnplIntelligenceResponse:
    return service.get_bnpl_intelligence(require_financial_user(user_id, current_user))
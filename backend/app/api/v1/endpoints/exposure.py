from fastapi import APIRouter, Depends, Path, status

from app.schemas.exposure import ExposureIntelligenceResponse
from app.core.security import get_current_financial_user, require_financial_user
from app.database.models.user import User
from app.services.exposure_service import ExposureService, get_exposure_service

router = APIRouter(prefix="/exposure", tags=["Financial Exposure Intelligence"])


@router.get(
    "/{user_id}",
    response_model=ExposureIntelligenceResponse,
    summary="Get financial exposure intelligence",
    description="Combine Subscription, EMI, and BNPL intelligence into a unified financial exposure report.",
    response_description="Unified financial exposure intelligence for the user.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Unknown user or no financial data.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Validation error.",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Financial exposure processing error.",
        },
    },
)
async def get_exposure_intelligence(
    user_id: str = Path(..., description="Unique user identifier such as U001.", examples=["U001"]),
    current_user: User = Depends(get_current_financial_user),
    service: ExposureService = Depends(get_exposure_service),
) -> ExposureIntelligenceResponse:
    return service.get_exposure_intelligence(require_financial_user(user_id, current_user))
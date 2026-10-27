from fastapi import APIRouter, Depends, Path, status

from app.schemas.subscription import SubscriptionIntelligenceResponse
from app.core.security import get_current_financial_user, require_financial_user
from app.database.models.user import User
from app.services.subscription_service import SubscriptionService, get_subscription_service

router = APIRouter(prefix="/subscriptions", tags=["Subscription Intelligence"])


@router.get(
    "/{user_id}",
    response_model=SubscriptionIntelligenceResponse,
    summary="Get subscription intelligence",
    description="Analyze the user's transactions and return subscription intelligence instead of raw transaction data.",
    response_description="Derived subscription intelligence for the user.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "User not found or no subscription transactions available.",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Subscription intelligence processing error.",
        },
    },
)
async def get_subscription_intelligence(
    user_id: str = Path(..., description="Unique user identifier such as U001.", examples=["U001"]),
    current_user: User = Depends(get_current_financial_user),
    service: SubscriptionService = Depends(get_subscription_service),
) -> SubscriptionIntelligenceResponse:
    return service.get_subscription_intelligence(require_financial_user(user_id, current_user))
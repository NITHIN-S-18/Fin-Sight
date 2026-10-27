from fastapi import APIRouter, Depends, Path

from app.core.security import get_current_financial_user
from app.database.models.user import User
from app.schemas.trial_intelligence import TrialIntelligenceListResponse, TrialIntelligenceResponse
from app.services.trial_intelligence_service import TrialIntelligenceService

router = APIRouter(prefix="/trial-intelligence", tags=["Trial Intelligence"])


@router.get(
    "",
    response_model=TrialIntelligenceListResponse,
    summary="List trial and authorization alerts",
    description="Return informational authorization and possible-trial alerts for the authenticated user.",
)
def list_trial_intelligence(
    user: User = Depends(get_current_financial_user),
) -> TrialIntelligenceListResponse:
    results = TrialIntelligenceService.list_for_user(user.user_id)
    if not results.items:
        TrialIntelligenceService.reconcile(user.user_id)
        results = TrialIntelligenceService.list_for_user(user.user_id)
    return results


@router.get("/{trial_id}", response_model=TrialIntelligenceResponse, summary="Get a trial alert")
def get_trial_intelligence(
    trial_id: int = Path(..., ge=1),
    user: User = Depends(get_current_financial_user),
) -> TrialIntelligenceResponse:
    return TrialIntelligenceService.get_for_user(user.user_id, trial_id)

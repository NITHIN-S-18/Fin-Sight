from fastapi import APIRouter, Depends

from app.core.security import get_current_financial_user
from app.database.models.user import User
from app.schemas.commitment import CommitmentSnapshotResponse
from app.services.commitment_service import UnifiedCommitmentService

router = APIRouter(prefix="/commitments", tags=["Commitments"])


@router.get(
    "",
    response_model=CommitmentSnapshotResponse,
    summary="Get the authoritative commitment snapshot",
    description="Return active high-confidence detected and user-added commitments for the authenticated user.",
)
def get_commitment_snapshot(
    user: User = Depends(get_current_financial_user),
) -> CommitmentSnapshotResponse:
    return UnifiedCommitmentService.snapshot_for_user(user.user_id)

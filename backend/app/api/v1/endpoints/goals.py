from fastapi import APIRouter, Depends, Path, status

from app.core.security import get_current_financial_user
from app.database.models.user import User
from app.schemas.goals import (
    FinancialGoalResponse,
    GoalCreateRequest,
    GoalEvaluation,
    GoalListResponse,
    GoalRequest,
    GoalUpdateRequest,
)
from app.services.goal_feasibility_service import (
    GoalFeasibilityService,
    get_goal_feasibility_service,
)

router = APIRouter(prefix="/goals", tags=["Financial Goals"])


@router.post("/feasibility", response_model=GoalEvaluation)
def evaluate_goal_feasibility(
    request: GoalRequest,
    user: User = Depends(get_current_financial_user),
    service: GoalFeasibilityService = Depends(get_goal_feasibility_service),
) -> GoalEvaluation:
    return service.evaluate(user.user_id, request)


@router.post("", response_model=FinancialGoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(
    request: GoalCreateRequest,
    user: User = Depends(get_current_financial_user),
    service: GoalFeasibilityService = Depends(get_goal_feasibility_service),
) -> FinancialGoalResponse:
    return service.create(user.user_id, request)


@router.get("", response_model=GoalListResponse)
def list_goals(
    user: User = Depends(get_current_financial_user),
    service: GoalFeasibilityService = Depends(get_goal_feasibility_service),
) -> GoalListResponse:
    return GoalListResponse(items=service.list_for_user(user.user_id))


@router.get("/{goal_id}", response_model=FinancialGoalResponse)
def get_goal(
    goal_id: int = Path(..., ge=1),
    user: User = Depends(get_current_financial_user),
    service: GoalFeasibilityService = Depends(get_goal_feasibility_service),
) -> FinancialGoalResponse:
    return service.get_for_user(user.user_id, goal_id)


@router.patch("/{goal_id}", response_model=FinancialGoalResponse)
def update_goal(
    request: GoalUpdateRequest,
    goal_id: int = Path(..., ge=1),
    user: User = Depends(get_current_financial_user),
    service: GoalFeasibilityService = Depends(get_goal_feasibility_service),
) -> FinancialGoalResponse:
    return service.update(user.user_id, goal_id, request)


@router.delete("/{goal_id}", response_model=FinancialGoalResponse)
def deactivate_goal(
    goal_id: int = Path(..., ge=1),
    user: User = Depends(get_current_financial_user),
    service: GoalFeasibilityService = Depends(get_goal_feasibility_service),
) -> FinancialGoalResponse:
    return service.deactivate(user.user_id, goal_id)

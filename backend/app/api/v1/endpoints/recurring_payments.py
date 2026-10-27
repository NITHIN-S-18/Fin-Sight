from fastapi import APIRouter, Depends, Path, Query, status

from app.core.security import get_current_financial_user
from app.database.models.user import User
from app.schemas.recurring_payment import (
    BatchCancellationSimulationRequest,
    BatchCancellationSimulationResponse,
    CancellationSimulationRequest,
    CancellationSimulationResponse,
    RecurringPaymentListResponse,
    RecurringPaymentResponse,
    UserRecurringPaymentCreate,
    UserRecurringPaymentUpdate,
)
from app.services.recurring_payment_service import RecurringPaymentService, get_recurring_payment_service

router = APIRouter(prefix="/recurring-payments", tags=["Recurring Payments"])


@router.post(
    "/simulate-cancellation",
    response_model=BatchCancellationSimulationResponse,
    summary="Simulate cancellation of multiple recurring payments",
    description="Calculates the financial effect of cancelling one or more subscriptions without changing stored records.",
)
def simulate_batch_cancellation(
    request: BatchCancellationSimulationRequest,
    user: User = Depends(get_current_financial_user),
    service: RecurringPaymentService = Depends(get_recurring_payment_service),
) -> BatchCancellationSimulationResponse:
    return service.simulate_batch_cancellation(user.user_id, request)


@router.get(
    "",
    response_model=RecurringPaymentListResponse,
    summary="List detected recurring payments",
    description="Return detected and user-added recurring payments owned by the authenticated user.",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Authentication is required."}},
)
def list_recurring_payments(
    category: str | None = Query(default=None, description="Optional recurring-payment category."),
    confidence_level: str | None = Query(default=None, description="Optional confidence filter: high or low."),
    payment_status: str | None = Query(default=None, alias="status", description="Optional lifecycle status."),
    user: User = Depends(get_current_financial_user),
    service: RecurringPaymentService = Depends(get_recurring_payment_service),
) -> RecurringPaymentListResponse:
    results = service.list_for_user(user.user_id, category, confidence_level, payment_status)
    if not results.items and category is None and confidence_level is None and payment_status is None:
        service.reconcile(user.user_id)
        results = service.list_for_user(user.user_id, category, confidence_level, payment_status)
    return results


@router.post("", response_model=RecurringPaymentResponse, status_code=status.HTTP_201_CREATED)
def create_recurring_payment(
    request: UserRecurringPaymentCreate,
    user: User = Depends(get_current_financial_user),
    service: RecurringPaymentService = Depends(get_recurring_payment_service),
) -> RecurringPaymentResponse:
    return service.create_user_added(user.user_id, request)


@router.get(
    "/{recurring_payment_id}",
    response_model=RecurringPaymentResponse,
    summary="Get a detected recurring payment",
)
def get_recurring_payment(
    recurring_payment_id: int = Path(..., ge=1),
    user: User = Depends(get_current_financial_user),
    service: RecurringPaymentService = Depends(get_recurring_payment_service),
) -> RecurringPaymentResponse:
    return service.get_for_user(user.user_id, recurring_payment_id)


@router.post(
    "/{recurring_payment_id}/simulate-cancellation",
    response_model=CancellationSimulationResponse,
    summary="Simulate cancellation of a recurring payment",
    description="Calculates the financial effect of cancellation without changing stored records.",
)
def simulate_cancellation(
    request: CancellationSimulationRequest,
    recurring_payment_id: int = Path(..., ge=1),
    user: User = Depends(get_current_financial_user),
    service: RecurringPaymentService = Depends(get_recurring_payment_service),
) -> CancellationSimulationResponse:
    return service.simulate_cancellation(user.user_id, recurring_payment_id, request)


@router.patch("/{recurring_payment_id}", response_model=RecurringPaymentResponse)
def update_recurring_payment(
    request: UserRecurringPaymentUpdate,
    recurring_payment_id: int = Path(..., ge=1),
    user: User = Depends(get_current_financial_user),
    service: RecurringPaymentService = Depends(get_recurring_payment_service),
) -> RecurringPaymentResponse:
    return service.update_user_added(user.user_id, recurring_payment_id, request)


@router.delete("/{recurring_payment_id}", response_model=RecurringPaymentResponse)
def deactivate_recurring_payment(
    recurring_payment_id: int = Path(..., ge=1),
    user: User = Depends(get_current_financial_user),
    service: RecurringPaymentService = Depends(get_recurring_payment_service),
) -> RecurringPaymentResponse:
    return service.deactivate_user_added(user.user_id, recurring_payment_id)

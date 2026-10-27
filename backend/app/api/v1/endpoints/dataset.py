from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.core.security import get_current_financial_user, require_financial_user
from app.database.models.user import User
from app.core.exceptions import TransactionNotFoundError, UserNotFoundError
from app.schemas.dataset import (
    DatasetHealthResponse,
    TransactionResponse,
    UserResponse,
)
from app.services.dataset_service import DatasetService, get_dataset_service

router = APIRouter(prefix="/dataset", tags=["Dataset"])


@router.get(
    "/user/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
    description="Return a single user record and the matching financial profile when available.",
    response_description="A user record with embedded financial profile data.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "User not found",
        }
    },
)
async def get_user(
    user_id: str = Path(..., description="Unique user identifier such as U001.", examples=["U007"]),
    current_user: User = Depends(get_current_financial_user),
    service: DatasetService = Depends(get_dataset_service),
) -> UserResponse:
    return service.get_user(require_financial_user(user_id, current_user))


@router.get(
    "/transaction/{transaction_id}",
    response_model=TransactionResponse,
    summary="Get transaction by ID",
    description="Return a single transaction record from the dataset.",
    response_description="A transaction record.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Transaction not found",
        }
    },
)
async def get_transaction(
    transaction_id: str = Path(..., description="Unique transaction identifier such as TXN000001.", examples=["TXN000001"]),
    current_user: User = Depends(get_current_financial_user),
    service: DatasetService = Depends(get_dataset_service),
) -> TransactionResponse:
    transaction = service.get_transaction(transaction_id)
    if transaction["user_id"] != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access another user's transaction")
    return transaction


@router.get(
    "/user/{user_id}/transactions",
    response_model=list[TransactionResponse],
    summary="List transactions for a user",
    description="Return all transactions associated with the supplied user identifier.",
    response_description="A list of transactions for the user.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "User not found",
        }
    },
)
async def get_user_transactions(
    user_id: str = Path(..., description="Unique user identifier such as U001.", examples=["U007"]),
    current_user: User = Depends(get_current_financial_user),
    service: DatasetService = Depends(get_dataset_service),
) -> list[TransactionResponse]:
    return service.get_user_transactions(require_financial_user(user_id, current_user))


@router.get(
    "/health",
    response_model=DatasetHealthResponse,
    summary="Dataset health",
    description="Check whether the datasets were loaded correctly at application startup.",
    response_description="Dataset module health and record counts.",
)
async def get_dataset_health(service: DatasetService = Depends(get_dataset_service)) -> DatasetHealthResponse:
    return service.get_health()

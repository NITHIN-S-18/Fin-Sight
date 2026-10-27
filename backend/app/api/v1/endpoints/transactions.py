from fastapi import APIRouter, Depends, File, UploadFile

from app.core.security import get_current_financial_user
from app.database.connection import SessionLocal
from app.database.models.transaction import Transaction
from app.database.models.transaction_import import TransactionImport
from app.database.models.user import User
from app.schemas.imports import (
    FinancialSummaryResponse,
    ImportConfirmationRequest,
    ImportPreviewResponse,
    TransactionImportResponse,
    TransactionUploadResponse,
)
from app.services.transaction_import_service import (
    TransactionImportService,
    get_transaction_import_service,
)
from sqlalchemy import func

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("/preview", response_model=ImportPreviewResponse, status_code=200, summary="Dry-run preview of CSV or PDF bank statement")
async def preview_transactions(
    file: UploadFile = File(...),
    user: User = Depends(get_current_financial_user),
    service: TransactionImportService = Depends(get_transaction_import_service),
) -> ImportPreviewResponse:
    """Pre-flight parsing, schema detection, duplicate estimation and row validation without committing."""
    return await service.generate_preview(user.auth_user_id, user.user_id, file)


@router.post("/confirm", response_model=TransactionUploadResponse, status_code=201, summary="Confirm and persist validated import preview")
def confirm_import(
    request: ImportConfirmationRequest,
    user: User = Depends(get_current_financial_user),
    service: TransactionImportService = Depends(get_transaction_import_service),
) -> TransactionUploadResponse:
    """Commits validated transactions from an active preview session."""
    if not request.preview_token:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="preview_token is required to confirm import",
        )
    return service.confirm_preview_import(user.auth_user_id, user.user_id, request.preview_token)


@router.post("/upload", response_model=TransactionUploadResponse, status_code=201, summary="Direct upload of CSV or PDF bank statement")
async def upload_transactions(
    file: UploadFile = File(...),
    user: User = Depends(get_current_financial_user),
    service: TransactionImportService = Depends(get_transaction_import_service),
) -> TransactionUploadResponse:
    """Direct upload supporting CSV and PDF formats with automatic normalization and deduplication."""
    return await service.import_csv(user.auth_user_id, user.user_id, file)


@router.get("/imports", response_model=list[TransactionImportResponse])
def list_transaction_imports(user: User = Depends(get_current_financial_user)) -> list[TransactionImportResponse]:
    with SessionLocal() as session:
        rows = (
            session.query(TransactionImport)
            .filter(TransactionImport.auth_user_id == user.auth_user_id)
            .order_by(TransactionImport.uploaded_at.desc())
            .all()
        )
        return [TransactionImportResponse.model_validate(row) for row in rows]


@router.get("/summary", response_model=FinancialSummaryResponse, summary="Get authenticated user's financial summary")
def get_financial_summary(user: User = Depends(get_current_financial_user)) -> FinancialSummaryResponse:
    with SessionLocal() as session:
        stats = session.query(
            func.count(Transaction.id),
            func.min(Transaction.transaction_date),
            func.max(Transaction.transaction_date),
        ).filter(Transaction.user_id == user.user_id).one()

        count, min_date, max_date = stats

        latest_import = (
            session.query(TransactionImport)
            .filter(TransactionImport.auth_user_id == user.auth_user_id)
            .order_by(TransactionImport.uploaded_at.desc())
            .first()
        )

        return FinancialSummaryResponse(
            total_transactions=int(count or 0),
            start_date=min_date,
            end_date=max_date,
            last_analyzed=latest_import.uploaded_at if latest_import else None,
            file_name=latest_import.file_name if latest_import else None,
        )
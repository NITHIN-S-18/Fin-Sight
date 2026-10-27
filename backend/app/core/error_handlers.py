import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import (
    BnplNotFoundError,
    BnplProcessingError,
    DashboardProcessingError,
    ExposureDataUnavailableError,
    ExposureNotFoundError,
    ExposureProcessingError,
    EmiNotFoundError,
    EmiProcessingError,
    DatasetLoadError,
    DatasetValidationError,
    SubscriptionNotFoundError,
    SubscriptionProcessingError,
    TransactionNotFoundError,
    UserNotFoundError,
)
from app.schemas.error import ErrorResponse

logger = logging.getLogger(__name__)


def _error_payload(
    *,
    error: str,
    message: str,
    path: str,
    details: object | None = None,
) -> dict[str, object]:
    return ErrorResponse(
        error=error,
        message=message,
        details=details,
        path=path,
        timestamp=datetime.now(timezone.utc),
    ).model_dump(mode="json")


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    message = detail if isinstance(detail, str) else "The request could not be completed."
    details = detail if isinstance(detail, (dict, list)) else None
    payload = _error_payload(
        error="http_exception",
        message=message,
        path=request.url.path,
        details=details,
    )
    return JSONResponse(status_code=exc.status_code, content=payload)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {
            "location": list(error["loc"]),
            "message": error["msg"],
            "error_type": error["type"],
        }
        for error in exc.errors()
    ]
    malformed_json = any(
        error["type"] in {"json_invalid", "model_attributes_type"}
        for error in exc.errors()
    )
    payload = _error_payload(
        error="malformed_request" if malformed_json else "validation_error",
        message="The request body contains malformed JSON." if malformed_json else "The request payload is invalid.",
        path=request.url.path,
        details=details,
    )
    response_status = status.HTTP_400_BAD_REQUEST if malformed_json else status.HTTP_422_UNPROCESSABLE_CONTENT
    return JSONResponse(status_code=response_status, content=payload)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error on %s %s", request.method, request.url.path)
    payload = _error_payload(
        error="internal_server_error",
        message="An unexpected error occurred.",
        path=request.url.path,
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)


async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("Database error on %s %s", request.method, request.url.path)
    payload = _error_payload(
        error="database_error",
        message="The request could not be completed because of a database error.",
        path=request.url.path,
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)


async def dataset_error_handler(request: Request, exc: DatasetValidationError | DatasetLoadError) -> JSONResponse:
    payload = _error_payload(
        error="dataset_error",
        message=str(exc),
        path=request.url.path,
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)


async def not_found_error_handler(request: Request, exc: UserNotFoundError | TransactionNotFoundError) -> JSONResponse:
    payload = _error_payload(
        error="not_found",
        message=str(exc),
        path=request.url.path,
    )
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=payload)


async def subscription_not_found_error_handler(request: Request, exc: SubscriptionNotFoundError) -> JSONResponse:
    payload = _error_payload(
        error="not_found",
        message=str(exc),
        path=request.url.path,
    )
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=payload)


async def subscription_processing_error_handler(request: Request, exc: SubscriptionProcessingError) -> JSONResponse:
    payload = _error_payload(
        error="subscription_processing_error",
        message=str(exc),
        path=request.url.path,
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)


async def emi_not_found_error_handler(request: Request, exc: EmiNotFoundError) -> JSONResponse:
    payload = _error_payload(
        error="not_found",
        message=str(exc),
        path=request.url.path,
    )
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=payload)


async def emi_processing_error_handler(request: Request, exc: EmiProcessingError) -> JSONResponse:
    payload = _error_payload(
        error="emi_processing_error",
        message=str(exc),
        path=request.url.path,
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)


async def bnpl_not_found_error_handler(request: Request, exc: BnplNotFoundError) -> JSONResponse:
    payload = _error_payload(
        error="not_found",
        message=str(exc),
        path=request.url.path,
    )
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=payload)


async def bnpl_processing_error_handler(request: Request, exc: BnplProcessingError) -> JSONResponse:
    payload = _error_payload(
        error="bnpl_processing_error",
        message=str(exc),
        path=request.url.path,
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)


async def exposure_not_found_error_handler(request: Request, exc: ExposureNotFoundError | ExposureDataUnavailableError) -> JSONResponse:
    payload = _error_payload(
        error="not_found",
        message=str(exc),
        path=request.url.path,
    )
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=payload)


async def exposure_processing_error_handler(request: Request, exc: ExposureProcessingError) -> JSONResponse:
    payload = _error_payload(
        error="exposure_processing_error",
        message=str(exc),
        path=request.url.path,
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)


async def dashboard_processing_error_handler(request: Request, exc: DashboardProcessingError) -> JSONResponse:
    payload = _error_payload(
        error="dashboard_processing_error",
        message=str(exc),
        path=request.url.path,
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(DatasetValidationError, dataset_error_handler)
    app.add_exception_handler(DatasetLoadError, dataset_error_handler)
    app.add_exception_handler(UserNotFoundError, not_found_error_handler)
    app.add_exception_handler(TransactionNotFoundError, not_found_error_handler)
    app.add_exception_handler(SubscriptionNotFoundError, subscription_not_found_error_handler)
    app.add_exception_handler(SubscriptionProcessingError, subscription_processing_error_handler)
    app.add_exception_handler(EmiNotFoundError, emi_not_found_error_handler)
    app.add_exception_handler(EmiProcessingError, emi_processing_error_handler)
    app.add_exception_handler(BnplNotFoundError, bnpl_not_found_error_handler)
    app.add_exception_handler(BnplProcessingError, bnpl_processing_error_handler)
    app.add_exception_handler(ExposureNotFoundError, exposure_not_found_error_handler)
    app.add_exception_handler(ExposureDataUnavailableError, exposure_not_found_error_handler)
    app.add_exception_handler(ExposureProcessingError, exposure_processing_error_handler)
    app.add_exception_handler(DashboardProcessingError, dashboard_processing_error_handler)
    app.add_exception_handler(SQLAlchemyError, database_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

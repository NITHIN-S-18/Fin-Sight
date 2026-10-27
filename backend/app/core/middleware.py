import logging
from datetime import datetime, timezone

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.schemas.error import ErrorResponse
from app.services.dataset_service import begin_dataset_request_cache, end_dataset_request_cache

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cache_token = begin_dataset_request_cache()
        try:
            return await call_next(request)
        except HTTPException:
            raise
        except Exception:
            logger.exception("Unhandled exception while processing %s %s", request.method, request.url.path)
            payload = ErrorResponse(
                error="internal_server_error",
                message="An unexpected error occurred.",
                path=request.url.path,
                timestamp=datetime.now(timezone.utc),
            ).model_dump(mode="json")
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)
        finally:
            end_dataset_request_cache(cache_token)

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.health import HealthResponse
from app.services.health_service import HealthService, get_health_service

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health_check(
    settings: Settings = Depends(get_settings),
    service: HealthService = Depends(get_health_service),
) -> HealthResponse:
    return service.build_status(settings)

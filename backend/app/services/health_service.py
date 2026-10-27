from datetime import datetime, timezone

from app.core.config import Settings
from app.schemas.health import HealthResponse


class HealthService:
    def build_status(self, settings: Settings) -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=settings.app_name,
            version=settings.app_version,
            environment=settings.environment,
            timestamp=datetime.now(timezone.utc),
        )


def get_health_service() -> HealthService:
    return HealthService()

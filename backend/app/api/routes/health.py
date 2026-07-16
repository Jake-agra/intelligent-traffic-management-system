from fastapi import APIRouter

from app.core.config import get_settings
from app.core.database import get_database_status
from app.schemas.health import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    settings = get_settings()

    return HealthResponse(
        service_name=settings.service_name,
        api_version=settings.api_version,
        environment=settings.environment,
        api_status="ok",
        database_status=get_database_status(),
    )

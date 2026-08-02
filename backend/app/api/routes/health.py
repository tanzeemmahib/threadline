from fastapi import APIRouter, Request

from app.schemas.models import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(
        application_version=settings.app_version,
        provider_mode=settings.provider_mode,
        credentials_configured=settings.credentials_configured,
        provider_configured=settings.provider_configured,
        configured_model=settings.openai_model if settings.provider_mode != "mock" else None,
    )

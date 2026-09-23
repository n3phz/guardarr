from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse

from app.core.config import get_settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", summary="Health check")
def health_check() -> JSONResponse:
    settings = get_settings()
    return JSONResponse(
        content={
            "status": "ok",
            "service": "guardarr",
            "version": "0.1.0",
            "environment": settings.environment if hasattr(settings, 'environment') else "development",
        },
        status_code=200,
    )

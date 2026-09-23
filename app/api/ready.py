from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.filesystem import check_filesystem_health

router = APIRouter(prefix="/api", tags=["ready"])


@router.get("/ready", summary="Readiness check with filesystem")
def readiness_check() -> JSONResponse:
    settings = get_settings()
    health = check_filesystem_health(settings)

    if not health["ready"]:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "reason": health.get("reason"),
            },
        )

    return JSONResponse(
        content={
            "status": "ready",
            "service": "guardarr",
            "data_dir": str(settings.guardarr_data_dir),
            "storage_path": str(settings.guardarr_storage_path),
        },
        status_code=200,
    )

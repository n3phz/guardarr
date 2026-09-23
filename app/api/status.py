from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.filesystem import get_filesystem_status

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status", summary="Full status with thresholds and inodes")
def status_endpoint() -> JSONResponse:
    settings = get_settings()
    fs_status = get_filesystem_status(settings)

    # Determine current threshold state
    total_bytes = fs_status["total_bytes"]
    available_bytes = fs_status["available_bytes"]
    warning = settings.warning_threshold_bytes
    admission_floor = settings.admission_floor_bytes
    emergency = settings.emergency_threshold_bytes
    critical = settings.critical_threshold_bytes

    # Determine threshold state - check from most severe to least severe
    if available_bytes <= critical:
        threshold_state = "CRITICAL"
    elif available_bytes <= emergency:
        threshold_state = "EMERGENCY"
    elif available_bytes <= admission_floor:
        threshold_state = "BLOCKED"
    elif available_bytes <= warning:
        threshold_state = "WARNING"
    else:
        threshold_state = "NORMAL"

    return JSONResponse(
        content={
            "total_bytes": total_bytes,
            "available_bytes": available_bytes,
            "configured_admission_floor_bytes": admission_floor,
            "warning_threshold_bytes": warning,
            "emergency_threshold_bytes": emergency,
            "critical_threshold_bytes": critical,
            "current_threshold_state": threshold_state,
            "inode_total": fs_status["total_inodes"],
            "inode_available": fs_status["available_inodes"],
            "inode_usage_percent": fs_status.get("inode_usage_percent"),
            "filesystem_identity": str(fs_status["filesystem_identity"]),
            "device_identity": str(fs_status["device_identity"]),
            "ready": fs_status["ready"],
        },
        status_code=200,
    )

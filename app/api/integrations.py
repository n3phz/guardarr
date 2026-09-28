from typing import List, Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.db.base import get_db
from app.integrations.arr.base import get_arr_client
from app.integrations.seerr.base import get_seerr_client
from app.services.qbittorrent import QBittorrentClient
from app.core.config import get_settings

router = APIRouter(prefix="/api", tags=["integrations"])


class IntegrationHealthResponse(BaseModel):
    provider: str
    type: Literal["arr", "seerr", "qbittorrent"]
    status: str  # connected, disconnected, degraded
    version: Optional[str] = None
    reason: Optional[str] = None
    latency_ms: Optional[int] = None


@router.get("/integrations/health", response_model=List[IntegrationHealthResponse])
def get_integrations_health(db: Session = Depends(get_db)):
    settings = get_settings()
    results = []

    # qBittorrent
    qb_client = QBittorrentClient()
    qb_res = qb_client.test_connectivity()
    results.append(IntegrationHealthResponse(
        provider="qbittorrent",
        type="qbittorrent",
        status=qb_res.get("status", "disconnected"),
        version=qb_res.get("version"),
        reason=qb_res.get("reason"),
    ))

    # Sonarr
    try:
        sonarr_client = get_arr_client("sonarr")
        sonarr_res = sonarr_client.test_connectivity()
        results.append(IntegrationHealthResponse(
            provider="sonarr",
            type="arr",
            status=sonarr_res.get("status", "disconnected"),
            version=sonarr_res.get("version"),
            reason=sonarr_res.get("reason"),
        ))
    except Exception as e:
        results.append(IntegrationHealthResponse(
            provider="sonarr",
            type="arr",
            status="disconnected",
            reason=str(e),
        ))

    # Radarr
    try:
        radarr_client = get_arr_client("radarr")
        radarr_res = radarr_client.test_connectivity()
        results.append(IntegrationHealthResponse(
            provider="radarr",
            type="arr",
            status=radarr_res.get("status", "disconnected"),
            version=radarr_res.get("version"),
            reason=radarr_res.get("reason"),
        ))
    except Exception as e:
        results.append(IntegrationHealthResponse(
            provider="radarr",
            type="arr",
            status="disconnected",
            reason=str(e),
        ))

    # Seerr
    try:
        seerr_client = get_seerr_client("seerr")
        seerr_res = seerr_client.test_connectivity()
        results.append(IntegrationHealthResponse(
            provider="seerr",
            type="seerr",
            status=seerr_res.get("status", "disconnected"),
            version=seerr_res.get("version"),
            reason=seerr_res.get("reason"),
        ))
    except Exception as e:
        results.append(IntegrationHealthResponse(
            provider="seerr",
            type="seerr",
            status="disconnected",
            reason=str(e),
        ))

    # Jellyseerr
    try:
        jellyseerr_client = get_seerr_client("jellyseerr")
        jellyseerr_res = jellyseerr_client.test_connectivity()
        results.append(IntegrationHealthResponse(
            provider="jellyseerr",
            type="seerr",
            status=jellyseerr_res.get("status", "disconnected"),
            version=jellyseerr_res.get("version"),
            reason=jellyseerr_res.get("reason"),
        ))
    except Exception as e:
        results.append(IntegrationHealthResponse(
            provider="jellyseerr",
            type="seerr",
            status="disconnected",
            reason=str(e),
        ))

    return results
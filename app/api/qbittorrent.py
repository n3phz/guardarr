from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.schemas.qbittorrent import (
    TorrentAssociateRequest,
    QBittorrentStatusResponse,
    TorrentReconcileResponse,
    UnreservedTorrentResponse,
)
from app.services.qbittorrent import QBittorrentClient
from app.services.qbittorrent_reconciliation import QBittorrentReconciliationService

router = APIRouter(prefix="/api/qbittorrent", tags=["qbittorrent"])


@router.get("/status", response_model=QBittorrentStatusResponse)
def get_qbittorrent_status():
    client = QBittorrentClient()
    res = client.test_connectivity()
    return QBittorrentStatusResponse(
        status=res.get("status", "disconnected"),
        version=res.get("version"),
        reason=res.get("reason")
    )


@router.post("/reservations/{reservation_id}/associate", status_code=status.HTTP_200_OK)
def associate_torrent(reservation_id: str, req: TorrentAssociateRequest, db: Session = Depends(get_db)):
    try:
        reservation = QBittorrentReconciliationService.associate_torrent(db, reservation_id, req.torrent_hash)
        return {
            "status": "success",
            "reservation_id": reservation.id,
            "torrent_metadata_hash": reservation.torrent_metadata_hash,
            "torrent_tag": reservation.torrent_tag,
            "state": reservation.state,
            "observed_materialized_bytes": reservation.observed_materialized_bytes,
            "remaining_unfulfilled_bytes": reservation.remaining_unfulfilled_bytes
        }
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))


@router.post("/reconcile", response_model=TorrentReconcileResponse)
def reconcile_qbittorrent(db: Session = Depends(get_db)):
    try:
        result = QBittorrentReconciliationService.reconcile_torrents(db)
        return TorrentReconcileResponse(
            status=result["status"],
            reconciled_reservations_count=result["reconciled_reservations_count"],
            recovered_reservations_count=result["recovered_reservations_count"],
            unreserved_torrents_count=result["unreserved_torrents_count"],
            unreserved_torrents=result["unreserved_torrents"],
            details=result.get("details"),
            timestamp=result["timestamp"]
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/unreserved", response_model=List[UnreservedTorrentResponse])
def list_unreserved_torrents(db: Session = Depends(get_db)):
    try:
        result = QBittorrentReconciliationService.reconcile_torrents(db)
        return result["unreserved_torrents"]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

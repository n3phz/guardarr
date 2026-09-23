from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.schemas.seerr import (
    SeerrEstimateRequest,
    SeerrEstimateResponse,
    SeerrAdmitRequest,
    SeerrAdmitResponse,
    SeerrImportedRequest,
    SeerrImportedResponse,
    SeerrReleaseRequest,
    SeerrReservationDetail,
    SeerrHealthResponse,
)
from app.services.seerr_orchestration import SeerrOrchestrationService
from app.integrations.seerr.base import get_seerr_client
from app.db.models import ReservationModel

router = APIRouter(prefix="/api/seerr", tags=["seerr"])


@router.get("/health/{provider}", response_model=SeerrHealthResponse)
def get_seerr_health(provider: str):
    try:
        client = get_seerr_client(provider)
        res = client.test_connectivity()
        return SeerrHealthResponse(
            provider=provider.lower(),
            status=res.get("status", "disconnected"),
            version=res.get("version"),
            reason=res.get("reason")
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        return SeerrHealthResponse(
            provider=provider.lower(),
            status="disconnected",
            reason=str(e)
        )


@router.post("/estimate", response_model=SeerrEstimateResponse)
def estimate_seerr_storage(req: SeerrEstimateRequest, db: Session = Depends(get_db)):
    try:
        return SeerrOrchestrationService.estimate(db, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/admit", response_model=SeerrAdmitResponse, status_code=status.HTTP_201_CREATED)
def admit_seerr_storage(req: SeerrAdmitRequest, db: Session = Depends(get_db)):
    if req.provider.lower() not in ["seerr", "jellyseerr"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid provider: {req.provider}")
    try:
        return SeerrOrchestrationService.admit(db, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{reservation_id}/imported", response_model=SeerrImportedResponse)
def confirm_seerr_imported(reservation_id: str, req: SeerrImportedRequest, db: Session = Depends(get_db)):
    try:
        return SeerrOrchestrationService.confirm_imported(db, reservation_id, req)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{reservation_id}/release", response_model=SeerrReservationDetail)
def release_seerr_reservation(reservation_id: str, req: Optional[SeerrReleaseRequest] = None, db: Session = Depends(get_db)):
    try:
        reason = req.reason if req else None
        reservation = SeerrOrchestrationService.release_owned(db, reservation_id, reason)
        return SeerrReservationDetail(
            reservation_id=reservation.id,
            idempotency_key=reservation.idempotency_key,
            adapter_name=reservation.adapter_name,
            content_id=reservation.content_id,
            arr_item_id=reservation.arr_item_id,
            torrent_metadata_hash=reservation.torrent_metadata_hash,
            associated_path=reservation.associated_path,
            target_device=reservation.target_device,
            max_bytes=reservation.max_bytes,
            expected_bytes=reservation.expected_bytes,
            observed_materialized_bytes=reservation.observed_materialized_bytes,
            remaining_unfulfilled_bytes=reservation.remaining_unfulfilled_bytes,
            import_mode=reservation.import_mode,
            priority=reservation.priority,
            owner=reservation.owner,
            torrent_tag=reservation.torrent_tag,
            state=reservation.state,
            created_at=reservation.created_at,
            updated_at=reservation.updated_at,
            expires_at=reservation.expires_at
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{reservation_id}", response_model=SeerrReservationDetail)
def get_seerr_reservation(reservation_id: str, db: Session = Depends(get_db)):
    reservation = db.query(ReservationModel).filter(ReservationModel.id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")
    return SeerrReservationDetail(
        reservation_id=reservation.id,
        idempotency_key=reservation.idempotency_key,
        adapter_name=reservation.adapter_name,
        content_id=reservation.content_id,
        arr_item_id=reservation.arr_item_id,
        torrent_metadata_hash=reservation.torrent_metadata_hash,
        associated_path=reservation.associated_path,
        target_device=reservation.target_device,
        max_bytes=reservation.max_bytes,
        expected_bytes=reservation.expected_bytes,
        observed_materialized_bytes=reservation.observed_materialized_bytes,
        remaining_unfulfilled_bytes=reservation.remaining_unfulfilled_bytes,
        import_mode=reservation.import_mode,
        priority=reservation.priority,
        owner=reservation.owner,
        torrent_tag=reservation.torrent_tag,
        state=reservation.state,
        created_at=reservation.created_at,
        updated_at=reservation.updated_at,
        expires_at=reservation.expires_at
    )
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.schemas.arr import (
    ArrEstimateRequest,
    ArrEstimateResponse,
    ArrAdmitRequest,
    ArrAdmitResponse,
    ArrImportedRequest,
    ArrImportedResponse,
    ArrReleaseRequest,
    ArrReservationDetail,
    ArrHealthResponse,
)
from app.services.arr_orchestration import ArrOrchestrationService
from app.integrations.arr.base import get_arr_client
from app.db.models import ReservationModel

router = APIRouter(prefix="/api/arr", tags=["arr"])


@router.get("/health/{provider}", response_model=ArrHealthResponse)
def get_arr_health(provider: str):
    try:
        client = get_arr_client(provider)
        res = client.test_connectivity()
        return ArrHealthResponse(
            provider=provider.lower(),
            status=res.get("status", "disconnected"),
            version=res.get("version"),
            reason=res.get("reason")
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        return ArrHealthResponse(
            provider=provider.lower(),
            status="disconnected",
            reason=str(e)
        )


@router.post("/estimate", response_model=ArrEstimateResponse)
def estimate_arr_storage(req: ArrEstimateRequest, db: Session = Depends(get_db)):
    try:
        return ArrOrchestrationService.estimate(db, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/admit", response_model=ArrAdmitResponse, status_code=status.HTTP_201_CREATED)
def admit_arr_storage(req: ArrAdmitRequest, db: Session = Depends(get_db)):
    try:
        return ArrOrchestrationService.admit(db, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{reservation_id}/imported", response_model=ArrImportedResponse)
def confirm_arr_imported(reservation_id: str, req: ArrImportedRequest, db: Session = Depends(get_db)):
    try:
        return ArrOrchestrationService.confirm_imported(db, reservation_id, req)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{reservation_id}/release", response_model=ArrReservationDetail)
def release_arr_reservation(reservation_id: str, req: Optional[ArrReleaseRequest] = None, db: Session = Depends(get_db)):
    try:
        reason = req.reason if req else None
        reservation = ArrOrchestrationService.release_owned(db, reservation_id, reason)
        return ArrReservationDetail(
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


@router.get("/{reservation_id}", response_model=ArrReservationDetail)
def get_arr_reservation(reservation_id: str, db: Session = Depends(get_db)):
    reservation = db.query(ReservationModel).filter(ReservationModel.id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")
    return ArrReservationDetail(
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

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import ReservationModel
from app.schemas.reservation import (
    EstimateRequest,
    EstimateResponse,
    AdmitRequest,
    ReservationResponse,
    ReleaseRequest,
    ReconcileResponse,
)
from app.services.admission import AdmissionService
from app.services.reconciliation import ReconciliationService

router = APIRouter(prefix="/api", tags=["reservations"])


@router.post("/estimate", response_model=EstimateResponse)
def estimate_storage(req: EstimateRequest, db: Session = Depends(get_db)):
    try:
        return AdmissionService.estimate(db, req)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))


@router.post("/admit", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED)
def admit_storage(req: AdmitRequest, db: Session = Depends(get_db)):
    try:
        reservation, created, message = AdmissionService.admit(db, req)
        return reservation
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/reservations/{reservation_id}/release", response_model=ReservationResponse)
def release_reservation(reservation_id: str, req: Optional[ReleaseRequest] = None, db: Session = Depends(get_db)):
    try:
        reason = req.reason if req else None
        return AdmissionService.release(db, reservation_id, reason)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/reservations", response_model=List[ReservationResponse])
def list_reservations(
    state: Optional[str] = Query(None),
    adapter_name: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(ReservationModel)
    if state:
        query = query.filter(ReservationModel.state == state)
    if adapter_name:
        query = query.filter(ReservationModel.adapter_name == adapter_name)
    return query.all()


@router.get("/reservations/{reservation_id}", response_model=ReservationResponse)
def get_reservation(reservation_id: str, db: Session = Depends(get_db)):
    reservation = db.query(ReservationModel).filter(ReservationModel.id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")
    return reservation


@router.post("/reconcile", response_model=ReconcileResponse)
def reconcile_reservations(db: Session = Depends(get_db)):
    try:
        result = ReconciliationService.reconcile(db)
        return ReconcileResponse(
            status=result["status"],
            expired_count=result["expired_count"],
            details=f"Expired {result['expired_count']} reservations, fixed {result['inconsistencies_fixed']} inconsistencies"
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

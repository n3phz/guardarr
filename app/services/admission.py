import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import get_settings
from app.core.filesystem import get_filesystem_stats
from app.db.models import ReservationModel, AuditLogModel, ReservationState, ImportMode
from app.schemas.reservation import AdmitRequest, EstimateRequest, EstimateResponse


def calculate_remaining_unfulfilled(max_bytes: int, observed_materialized_bytes: int, import_mode: ImportMode) -> int:
    if import_mode == ImportMode.HARDLINK:
        # hardlink reservations remain reserved until explicitly released/owned
        # but account for materialized bytes if any
        return max(0, max_bytes - observed_materialized_bytes)
    elif import_mode == ImportMode.COPY:
        return max(0, max_bytes - observed_materialized_bytes)
    else:
        # unknown / conservative
        return max(0, max_bytes - observed_materialized_bytes)


class AdmissionService:
    @staticmethod
    def calculate_outstanding_unfulfilled(db: Session, target_device: str = "/data") -> int:
        # Sum remaining_unfulfilled_bytes for all active/reserved/pending reservations on target_device
        active_states = [
            ReservationState.PENDING,
            ReservationState.RESERVED,
            ReservationState.ACTIVE,
        ]
        res = db.query(ReservationModel).filter(
            ReservationModel.target_device == target_device,
            ReservationModel.state.in_(active_states)
        ).all()
        
        total = sum(r.remaining_unfulfilled_bytes for r in res)
        return total

    @staticmethod
    def estimate(db: Session, req: EstimateRequest) -> EstimateResponse:
        settings = get_settings()
        stats = get_filesystem_stats(req.target_device)
        
        if not stats or stats.get("available_bytes") is None:
            raise RuntimeError(f"Failed to inspect filesystem for device {req.target_device}")
            
        available_bytes = stats["available_bytes"]
        outstanding_unfulfilled = AdmissionService.calculate_outstanding_unfulfilled(db, req.target_device)
        
        requested = calculate_remaining_unfulfilled(req.max_bytes, 0, req.import_mode)
        projected_available = available_bytes - outstanding_unfulfilled - requested
        
        floor = settings.admission_floor_bytes
        admissible = projected_available >= floor
        
        reason = None
        if not admissible:
            reason = f"Projected available bytes ({projected_available}) would fall below admission floor ({floor})"

        return EstimateResponse(
            available_bytes=available_bytes,
            outstanding_unfulfilled_bytes=outstanding_unfulfilled,
            requested_bytes=requested,
            projected_available_bytes=projected_available,
            admission_floor_bytes=floor,
            admissible=admissible,
            reason=reason
        )

    @staticmethod
    def admit(db: Session, req: AdmitRequest) -> Tuple[ReservationModel, bool, str]:
        # BEGIN IMMEDIATE to ensure transaction serialization and contention control
        db.execute(text("BEGIN IMMEDIATE"))
        
        settings = get_settings()
        
        # 1. Check idempotency first
        existing = db.query(ReservationModel).filter(
            ReservationModel.adapter_name == req.adapter_name,
            ReservationModel.idempotency_key == req.idempotency_key
        ).first()
        
        if existing:
            return existing, False, "Idempotent match: returned existing reservation"

        # 2. Validate target device and basic bytes
        if req.max_bytes <= 0 or req.expected_bytes <= 0:
            raise ValueError("Reservation bytes must be greater than zero")

        stats = get_filesystem_stats(req.target_device)
        if not stats or stats.get("available_bytes") is None:
            raise RuntimeError(f"Failed to obtain storage stats for {req.target_device}. Failing closed.")

        available_bytes = stats["available_bytes"]
        outstanding_unfulfilled = AdmissionService.calculate_outstanding_unfulfilled(db, req.target_device)
        
        remaining_unfulfilled = calculate_remaining_unfulfilled(
            req.max_bytes, req.observed_materialized_bytes, req.import_mode
        )
        
        projected_available = available_bytes - outstanding_unfulfilled - remaining_unfulfilled
        floor = settings.admission_floor_bytes

        if projected_available < floor:
            # Record denied audit event or raise error
            raise ValueError(f"Admission denied: Projected available {projected_available} below admission floor {floor}")

        # 3. Create reservation
        reservation_id = str(uuid.uuid4())
        expires_at = None
        if req.ttl_seconds and req.ttl_seconds > 0:
            expires_at = datetime.utcnow() + timedelta(seconds=req.ttl_seconds)

        reservation = ReservationModel(
            id=reservation_id,
            idempotency_key=req.idempotency_key,
            adapter_name=req.adapter_name,
            content_id=req.content_id,
            torrent_metadata_hash=req.torrent_metadata_hash,
            target_device=req.target_device,
            max_bytes=req.max_bytes,
            expected_bytes=req.expected_bytes,
            observed_materialized_bytes=req.observed_materialized_bytes,
            remaining_unfulfilled_bytes=remaining_unfulfilled,
            import_mode=req.import_mode,
            priority=req.priority,
            owner=req.owner,
            torrent_tag=req.torrent_tag,
            state=ReservationState.RESERVED,
            expires_at=expires_at
        )

        db.add(reservation)
        
        # Audit log
        audit = AuditLogModel(
            reservation_id=reservation_id,
            event_type="admitted",
            details=f"Admitted {remaining_unfulfilled} unfulfilled bytes (max={req.max_bytes}, mode={req.import_mode})"
        )
        db.add(audit)
        db.commit()
        db.refresh(reservation)

        return reservation, True, "Successfully admitted"

    @staticmethod
    def release(db: Session, reservation_id: str, reason: Optional[str] = None) -> ReservationModel:
        db.execute(text("BEGIN IMMEDIATE"))
        reservation = db.query(ReservationModel).filter(ReservationModel.id == reservation_id).first()
        if not reservation:
            raise KeyError(f"Reservation {reservation_id} not found")

        if reservation.state in [ReservationState.RELEASED, ReservationState.EXPIRED]:
            return reservation

        reservation.state = ReservationState.RELEASED
        reservation.remaining_unfulfilled_bytes = 0
        reservation.updated_at = datetime.utcnow()

        audit = AuditLogModel(
            reservation_id=reservation_id,
            event_type="released",
            details=reason or "Explicitly released"
        )
        db.add(audit)
        db.commit()
        db.refresh(reservation)
        return reservation

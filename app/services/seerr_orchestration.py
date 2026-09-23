import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import get_settings
from app.core.filesystem import get_filesystem_stats
from app.db.models import ReservationModel, AuditLogModel, ReservationState, ImportMode
from app.services.admission import AdmissionService, calculate_remaining_unfulfilled
from app.integrations.seerr.base import get_seerr_client
from app.schemas.seerr import (
    SeerrEstimateRequest,
    SeerrEstimateResponse,
    SeerrAdmitRequest,
    SeerrAdmitResponse,
    SeerrImportedRequest,
    SeerrImportedResponse,
)

logger = logging.getLogger("guardarr.seerr_orchestration")


class SeerrOrchestrationService:
    @staticmethod
    def estimate(db: Session, req: SeerrEstimateRequest) -> SeerrEstimateResponse:
        if req.provider.lower() not in ["seerr", "jellyseerr"]:
            raise ValueError(f"Invalid provider: {req.provider}")

        settings = get_settings()
        stats = get_filesystem_stats(req.target_device)
        if not stats or stats.get("available_bytes") is None:
            raise RuntimeError(f"Failed to inspect filesystem for {req.target_device}")

        available_bytes = stats["available_bytes"]
        outstanding_unfulfilled = AdmissionService.calculate_outstanding_unfulfilled(db, req.target_device)
        requested = calculate_remaining_unfulfilled(req.estimated_size_bytes, 0, ImportMode.COPY)
        projected_available = available_bytes - outstanding_unfulfilled - requested
        floor = settings.admission_floor_bytes
        admissible = projected_available >= floor

        reason = None
        if not admissible:
            reason = f"Projected available bytes ({projected_available}) below admission floor ({floor})"

        return SeerrEstimateResponse(
            available_bytes=available_bytes,
            outstanding_unfulfilled_bytes=outstanding_unfulfilled,
            requested_bytes=requested,
            projected_available_bytes=projected_available,
            admission_floor_bytes=floor,
            admissible=admissible,
            reason=reason
        )

    @staticmethod
    def admit(db: Session, req: SeerrAdmitRequest) -> SeerrAdmitResponse:
        db.execute(text("BEGIN IMMEDIATE"))
        provider = req.provider.lower()
        if provider not in ["seerr", "jellyseerr"]:
            raise ValueError(f"Invalid provider: {provider}")

        settings = get_settings()
        adapter_name = provider
        idempotency_key = f"{provider}:{req.request_id}:{req.media_id or 'default'}"

        existing = db.query(ReservationModel).filter(
            ReservationModel.adapter_name == adapter_name,
            ReservationModel.idempotency_key == idempotency_key
        ).first()

        if existing:
            return SeerrAdmitResponse(
                reservation_id=existing.id,
                state=existing.state,
                max_bytes=existing.max_bytes,
                expected_bytes=existing.expected_bytes,
                target_device=existing.target_device,
                idempotency_key=existing.idempotency_key,
                created_at=existing.created_at,
                expires_at=existing.expires_at,
                note="Reservation created in RESERVED state. Controlled qBittorrent admission is required to transition RESERVED -> ACTIVE."
            )

        stats = get_filesystem_stats(req.target_device)
        if not stats or stats.get("available_bytes") is None:
            raise RuntimeError("Failed to obtain storage stats. Failing closed.")

        available_bytes = stats["available_bytes"]
        outstanding_unfulfilled = AdmissionService.calculate_outstanding_unfulfilled(db, req.target_device)
        
        import_mode_enum = ImportMode.COPY
        if req.import_mode.lower() == "hardlink":
            import_mode_enum = ImportMode.HARDLINK

        remaining_unfulfilled = calculate_remaining_unfulfilled(req.max_bytes, 0, import_mode_enum)
        projected_available = available_bytes - outstanding_unfulfilled - remaining_unfulfilled
        floor = settings.admission_floor_bytes

        if projected_available < floor:
            raise ValueError(f"Admission denied: Projected available {projected_available} below admission floor {floor}")

        reservation_id = str(uuid.uuid4())
        expires_at = None
        if req.ttl_seconds and req.ttl_seconds > 0:
            expires_at = datetime.utcnow() + timedelta(seconds=req.ttl_seconds)

        reservation = ReservationModel(
            id=reservation_id,
            idempotency_key=idempotency_key,
            adapter_name=adapter_name,
            content_id=req.request_id,
            arr_item_id=req.media_id,
            target_device=req.target_device,
            max_bytes=req.max_bytes,
            expected_bytes=req.expected_bytes,
            observed_materialized_bytes=0,
            remaining_unfulfilled_bytes=remaining_unfulfilled,
            import_mode=import_mode_enum,
            priority=req.priority,
            state=ReservationState.RESERVED,
            expires_at=expires_at
        )

        db.add(reservation)
        db.add(AuditLogModel(
            reservation_id=reservation_id,
            event_type="seerr_admitted",
            details=f"Admitted via {provider} for request {req.request_id} (media={req.media_id}) in RESERVED state"
        ))
        db.commit()
        db.refresh(reservation)

        return SeerrAdmitResponse(
            reservation_id=reservation.id,
            state=reservation.state,
            max_bytes=reservation.max_bytes,
            expected_bytes=reservation.expected_bytes,
            target_device=reservation.target_device,
            idempotency_key=reservation.idempotency_key,
            created_at=reservation.created_at,
            expires_at=reservation.expires_at,
            note="Reservation created in RESERVED state. Controlled qBittorrent admission is required to transition RESERVED -> ACTIVE."
        )

    @staticmethod
    def confirm_imported(db: Session, reservation_id: str, req: SeerrImportedRequest) -> SeerrImportedResponse:
        db.execute(text("BEGIN IMMEDIATE"))
        now = datetime.utcnow()

        reservation = db.query(ReservationModel).filter(ReservationModel.id == reservation_id).first()
        if not reservation:
            raise KeyError(f"Reservation {reservation_id} not found")

        # Idempotency: if already OWNED or RELEASED, return success safely without altering state
        if reservation.state == ReservationState.OWNED:
            return SeerrImportedResponse(
                reservation_id=reservation.id,
                state=reservation.state,
                ownership_verified=True,
                message="Reservation is already OWNED (idempotent return)",
                released=False
            )
        if reservation.state == ReservationState.RELEASED:
            return SeerrImportedResponse(
                reservation_id=reservation.id,
                state=reservation.state,
                ownership_verified=True,
                message="Reservation is already RELEASED (idempotent return)",
                released=True
            )

        # State transition validation: must be ACTIVE (ACTIVE -> OWNED)
        # Requirement: RELEASED cannot become OWNED, RESERVED cannot become OWNED directly without ACTIVE/controlled add.
        if reservation.state != ReservationState.ACTIVE:
            raise ValueError(f"Cannot confirm import for reservation in state {reservation.state}; must be ACTIVE")

        # Ownership Identity Verification
        if req.provider.lower() != reservation.adapter_name.lower():
            db.add(AuditLogModel(
                reservation_id=reservation.id,
                event_type="ownership_verification_failed",
                details=f"Provider mismatch: requested {req.provider}, reservation adapter is {reservation.adapter_name}"
            ))
            db.commit()
            raise ValueError(f"Provider mismatch: expected {reservation.adapter_name}, got {req.provider}")

        if req.request_id and reservation.content_id and req.request_id != reservation.content_id:
            db.add(AuditLogModel(
                reservation_id=reservation.id,
                event_type="ownership_verification_failed",
                details=f"Request ID mismatch: requested {req.request_id}, reservation has {reservation.content_id}"
            ))
            db.commit()
            raise ValueError("Request ID identity mismatch")

        if reservation.arr_item_id and req.media_id and req.media_id != reservation.arr_item_id:
            db.add(AuditLogModel(
                reservation_id=reservation.id,
                event_type="ownership_verification_failed",
                details=f"Media ID mismatch: requested {req.media_id}, reservation has {reservation.arr_item_id}"
            ))
            db.commit()
            raise ValueError("Media ID identity mismatch")

        if req.torrent_hash and reservation.torrent_metadata_hash:
            if req.torrent_hash.lower() != reservation.torrent_metadata_hash.lower():
                db.add(AuditLogModel(
                    reservation_id=reservation.id,
                    event_type="ownership_verification_failed",
                    details=f"Torrent hash mismatch: requested {req.torrent_hash}, reservation has {reservation.torrent_metadata_hash}"
                ))
                db.commit()
                raise ValueError("Torrent hash identity mismatch")

        if req.torrent_hash and not reservation.torrent_metadata_hash:
            reservation.torrent_metadata_hash = req.torrent_hash.lower()

        if req.imported_path:
            reservation.associated_path = req.imported_path

        # Transition ACTIVE -> OWNED and persist OWNED state explicitly
        reservation.state = ReservationState.OWNED
        reservation.remaining_unfulfilled_bytes = 0
        reservation.updated_at = now

        db.add(AuditLogModel(
            reservation_id=reservation.id,
            event_type="ownership_confirmed",
            details=f"Explicit import ownership verified for {reservation.adapter_name} request {req.request_id}. Transitioned ACTIVE -> OWNED."
        ))
        db.commit()
        db.refresh(reservation)

        return SeerrImportedResponse(
            reservation_id=reservation.id,
            state=reservation.state,
            ownership_verified=True,
            message="Import ownership verified successfully and persisted in OWNED state",
            released=False
        )

    @staticmethod
    def release_owned(db: Session, reservation_id: str, reason: Optional[str] = None) -> ReservationModel:
        db.execute(text("BEGIN IMMEDIATE"))
        now = datetime.utcnow()

        reservation = db.query(ReservationModel).filter(ReservationModel.id == reservation_id).first()
        if not reservation:
            raise KeyError(f"Reservation {reservation_id} not found")

        # Idempotency for OWNED -> RELEASED: if already RELEASED, return safely
        if reservation.state == ReservationState.RELEASED:
            return reservation

        # State transition validation: must be OWNED
        if reservation.state != ReservationState.OWNED:
            raise ValueError(f"Cannot release reservation in state {reservation.state}; must be OWNED")

        reservation.state = ReservationState.RELEASED
        reservation.remaining_unfulfilled_bytes = 0
        reservation.updated_at = now

        db.add(AuditLogModel(
            reservation_id=reservation.id,
            event_type="released",
            details=reason or "Explicit release from OWNED state"
        ))
        db.commit()
        db.refresh(reservation)
        return reservation

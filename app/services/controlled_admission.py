import logging
import re
from datetime import datetime
from typing import Tuple, Dict, Any, Optional
from urllib.parse import parse_qs, urlparse
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import get_settings
from app.core.filesystem import get_filesystem_stats
from app.db.models import ReservationModel, AuditLogModel, ReservationState
from app.services.admission import AdmissionService, calculate_remaining_unfulfilled
from app.services.qbittorrent import QBittorrentClient
from app.schemas.controlled_add import ControlledAddRequest

logger = logging.getLogger("guardarr.controlled_admission")


def extract_magnet_hash(url_or_magnet: str) -> Optional[str]:
    """Extract standard 40-char hex or 32-char base32 btih hash from a magnet URI."""
    if not url_or_magnet or not url_or_magnet.startswith("magnet:?"):
        return None
    try:
        parsed = urlparse(url_or_magnet)
        qs = parse_qs(parsed.query)
        xts = qs.get("xt", [])
        for xt in xts:
            # urn:btih:<hash>
            if xt.startswith("urn:btih:"):
                h = xt.replace("urn:btih:", "").strip().lower()
                if len(h) == 40 or len(h) == 32:
                    return h
    except Exception as e:
        logger.error(f"Failed to extract magnet hash: {e}")
    return None


class ControlledAdmissionService:
    @staticmethod
    def controlled_add(db: Session, reservation_id: str, req: ControlledAddRequest) -> Dict[str, Any]:
        db.execute(text("BEGIN IMMEDIATE"))
        now = datetime.utcnow()
        settings = get_settings()

        # 1. Fetch reservation
        reservation = db.query(ReservationModel).filter(ReservationModel.id == reservation_id).first()
        if not reservation:
            raise KeyError(f"Reservation {reservation_id} not found")

        # 2. State validation
        if reservation.state not in [ReservationState.RESERVED, ReservationState.ACTIVE]:
            raise ValueError(f"Reservation {reservation_id} is in state {reservation.state}; must be RESERVED or ACTIVE")

        # 3. Expiration check
        if reservation.expires_at and reservation.expires_at < now:
            reservation.state = ReservationState.EXPIRED
            reservation.remaining_unfulfilled_bytes = 0
            db.add(AuditLogModel(
                reservation_id=reservation.id,
                event_type="torrent_add_failed",
                details="Controlled add failed: reservation expired"
            ))
            db.commit()
            raise ValueError("Reservation has expired")

        # 4. Filesystem capacity check
        stats = get_filesystem_stats(reservation.target_device)
        if not stats or stats.get("available_bytes") is None:
            db.add(AuditLogModel(
                reservation_id=reservation.id,
                event_type="torrent_add_failed",
                details=f"Controlled add failed: unable to inspect filesystem for {reservation.target_device}"
            ))
            db.commit()
            raise RuntimeError(f"Failed to inspect storage device {reservation.target_device}. Failing closed.")

        available_bytes = stats["available_bytes"]
        outstanding_unfulfilled = AdmissionService.calculate_outstanding_unfulfilled(db, reservation.target_device)
        projected_available = available_bytes - outstanding_unfulfilled
        floor = settings.admission_floor_bytes

        if projected_available < floor:
            db.add(AuditLogModel(
                reservation_id=reservation.id,
                event_type="torrent_add_failed",
                details=f"Controlled add denied: projected available {projected_available} below admission floor {floor}"
            ))
            db.commit()
            raise ValueError(f"Admission denied: Projected available {projected_available} below admission floor {floor}")

        tag = f"{settings.qbittorrent_torrent_tag_prefix}{reservation.id}"
        client = QBittorrentClient()

        conn = client.test_connectivity()
        if conn.get("status") != "connected":
            db.add(AuditLogModel(
                reservation_id=reservation.id,
                event_type="torrent_add_failed",
                details="Controlled add failed: qBittorrent unavailable"
            ))
            db.commit()
            raise RuntimeError("qBittorrent is unavailable; aborting controlled add safely.")

        # Extract requested identity hash if magnet
        requested_hash = extract_magnet_hash(req.url_or_magnet)

        # 5. RETRY SAFETY & IDENTITY AUDIT (Requirement 1 & 2)
        # Check if any torrents with this deterministic tag already exist in qBittorrent
        tagged_torrents = client.get_torrents(tag=tag)
        
        # Safety check: if multiple distinct torrents carry this reservation tag, fail safely without choosing arbitrarily (Requirement 1.D & 6)
        if len(tagged_torrents) > 1:
            db.add(AuditLogModel(
                reservation_id=reservation.id,
                event_type="torrent_add_failed",
                details=f"Conflict: Multiple torrents ({len(tagged_torrents)}) carry tag {tag}. Manual resolution / reconciliation required."
            ))
            db.commit()
            raise ValueError(f"Conflict: Multiple torrents carry reservation tag {tag}. Refusing ambiguous association.")

        existing_torrent = tagged_torrents[0] if tagged_torrents else None
        target_torrent = None

        if existing_torrent:
            existing_hash = existing_torrent.get("hash", "").lower()
            
            # Case A: Same reservation + same idempotency key + same magnet/URL (or same identity hash) -> safe reuse
            # Case B: Same reservation + same idempotency key + DIFFERENT magnet/URL -> MUST NOT silently reuse (Requirement 1.B)
            if requested_hash and existing_hash and requested_hash != existing_hash:
                db.add(AuditLogModel(
                    reservation_id=reservation.id,
                    event_type="torrent_add_failed",
                    details=f"Idempotency conflict: Reservation {reservation.id} is already tagged to torrent hash {existing_hash}, but request specifies a different torrent hash {requested_hash}."
                ))
                db.commit()
                raise ValueError(f"Idempotency conflict: Reservation already bound to hash {existing_hash}; cannot silently replace with different torrent hash {requested_hash}.")

            # If already bound to this hash, reuse safely
            target_torrent = existing_torrent
            db.add(AuditLogModel(
                reservation_id=reservation.id,
                event_type="torrent_added",
                details=f"Idempotent retry: reused existing qBittorrent torrent {existing_hash} bound to tag {tag}"
            ))
        else:
            # 6. Add torrent PAUSED as per safety requirement 3
            db.add(AuditLogModel(
                reservation_id=reservation.id,
                event_type="torrent_add_requested",
                details=f"Controlled add requested with idempotency key {req.idempotency_key}"
            ))

            add_success = client.add_torrent(
                url_or_magnet=req.url_or_magnet,
                savepath=req.savepath,
                category=req.category,
                tags=tag,
                paused=True
            )

            if not add_success:
                db.add(AuditLogModel(
                    reservation_id=reservation.id,
                    event_type="torrent_add_failed",
                    details="qBittorrent add_torrent API call returned failure status"
                ))
                db.commit()
                raise RuntimeError("Failed to add torrent to qBittorrent")

            db.add(AuditLogModel(
                reservation_id=reservation.id,
                event_type="torrent_added",
                details="Successfully added torrent to qBittorrent in PAUSED state"
            ))

            # Fetch newly added torrent by tag
            torrents_with_tag = client.get_torrents(tag=tag)
            if len(torrents_with_tag) > 1:
                db.add(AuditLogModel(
                    reservation_id=reservation.id,
                    event_type="torrent_add_failed",
                    details=f"Conflict: Multiple torrents ({len(torrents_with_tag)}) appeared with tag {tag} after add. Refusing ambiguous selection."
                ))
                db.commit()
                raise ValueError(f"Conflict: Multiple torrents appeared with tag {tag}. Refusing ambiguous selection.")

            if torrents_with_tag:
                target_torrent = torrents_with_tag[0]

        # 7. Identity verification & Hash extraction (Requirement 2)
        torrent_hash = None
        if target_torrent and isinstance(target_torrent, dict):
            torrent_hash = target_torrent.get("hash")

        if not torrent_hash and requested_hash:
            # Fallback identity verification if qBittorrent listing lag occurs but magnet hash is known
            # Query by hash or verify
            hash_torrent = client.get_torrent_by_hash(requested_hash)
            if hash_torrent:
                torrent_hash = requested_hash
                target_torrent = hash_torrent

        if not torrent_hash:
            # Ambiguous add / Hash pending (Requirement 6)
            reservation.torrent_tag = tag
            reservation.updated_at = now
            db.add(AuditLogModel(
                reservation_id=reservation.id,
                event_type="torrent_association_pending",
                details=f"Torrent added successfully but hash could not be retrieved; marked ASSOCIATION_PENDING with tag {tag}"
            ))
            db.commit()
            return {
                "reservation_id": reservation.id,
                "torrent_hash": None,
                "torrent_tag": tag,
                "state": reservation.state,
                "qbittorrent_status": "success_add_hash_pending",
                "association_status": "association_pending",
                "recovery_info": f"Torrent added with tag {tag} but hash acquisition pending. Reconciliation will recover."
            }

        normalized_hash = torrent_hash.lower()

        # If requested_hash was provided in magnet, verify it matches the resolved torrent hash strictly
        if requested_hash and requested_hash != normalized_hash:
            db.add(AuditLogModel(
                reservation_id=reservation.id,
                event_type="torrent_add_failed",
                details=f"Identity verification failed: requested magnet hash {requested_hash} does not match qBittorrent resolved hash {normalized_hash}"
            ))
            db.commit()
            raise ValueError(f"Torrent identity mismatch: requested hash {requested_hash} != resolved hash {normalized_hash}")

        # 8. Check if returned hash is already claimed by another active reservation (Conflict check - Requirement 1.C)
        active_states = [ReservationState.RESERVED, ReservationState.ACTIVE]
        existing_claim = db.query(ReservationModel).filter(
            ReservationModel.torrent_metadata_hash == normalized_hash,
            ReservationModel.state.in_(active_states),
            ReservationModel.id != reservation.id
        ).first()

        if existing_claim:
            db.add(AuditLogModel(
                reservation_id=reservation.id,
                event_type="torrent_association_conflict",
                details=f"Conflict: Torrent hash {normalized_hash} already claimed by reservation {existing_claim.id}"
            ))
            db.commit()
            raise ValueError(f"Torrent hash {normalized_hash} is already claimed by reservation {existing_claim.id}")

        # 9. TAG & PERSISTENCE ORDER (Requirement 3 & 5)
        # Apply/Verify Guardarr tag in qBittorrent
        tag_success = client.add_torrent_tags([normalized_hash], [tag])
        if not tag_success:
            # Tag failure: torrent remains paused, reservation is NOT ACTIVE (Requirement 5)
            reservation.torrent_tag = tag
            reservation.updated_at = now
            db.add(AuditLogModel(
                reservation_id=reservation.id,
                event_type="torrent_association_pending",
                details="Torrent added and hash obtained, but tag application failed. Torrent remains paused, reservation not active. Reconciliation will recover."
            ))
            db.commit()
            return {
                "reservation_id": reservation.id,
                "torrent_hash": normalized_hash,
                "torrent_tag": tag,
                "state": reservation.state,
                "qbittorrent_status": "success_add_tag_failed",
                "association_status": "tag_application_failed_pending",
                "recovery_info": "Tag application failed; torrent left paused, reconciliation will retry tagging."
            }

        db.add(AuditLogModel(
            reservation_id=reservation.id,
            event_type="torrent_tagged",
            details=f"Successfully applied deterministic tag {tag} to torrent {normalized_hash}"
        ))

        # Persist association in database BEFORE transition & resume (Requirement 3)
        reservation.torrent_metadata_hash = normalized_hash
        reservation.torrent_tag = tag

        db.add(AuditLogModel(
            reservation_id=reservation.id,
            event_type="torrent_associated",
            details=f"Associated torrent hash {normalized_hash} with reservation {reservation.id}"
        ))

        # Transition reservation state to ACTIVE
        reservation.state = ReservationState.ACTIVE

        # Update materialized bytes
        completed = target_torrent.get("completed", 0) if target_torrent else 0
        materialized = min(completed, reservation.max_bytes)
        reservation.observed_materialized_bytes = materialized
        reservation.remaining_unfulfilled_bytes = calculate_remaining_unfulfilled(
            reservation.max_bytes, materialized, reservation.import_mode
        )
        reservation.updated_at = now

        # Commit association & ACTIVE state before resume call
        db.commit()

        # 10. RESUME WITH RESUME FAILURE HANDLING (Requirement 4)
        # Association succeeded and reservation is ACTIVE. Now attempt resume.
        resume_success = client.resume_torrents([normalized_hash])
        if resume_success:
            db.add(AuditLogModel(
                reservation_id=reservation.id,
                event_type="torrent_started",
                details=f"Successfully resumed torrent {normalized_hash} after safety verification"
            ))
            db.commit()
            qb_status = "success_resumed"
        else:
            # Resume failure (Requirement 4): Reservation remains ACTIVE with known association. DO NOT roll back to RESERVED.
            db.add(AuditLogModel(
                reservation_id=reservation.id,
                event_type="torrent_resume_failed",
                details=f"Associated successfully and reservation is ACTIVE, but qBittorrent resume call failed for hash {normalized_hash}. Left in paused state for reconciliation."
            ))
            db.commit()
            qb_status = "success_associated_resume_failed"

        db.refresh(reservation)

        return {
            "reservation_id": reservation.id,
            "torrent_hash": normalized_hash,
            "torrent_tag": tag,
            "state": reservation.state,
            "qbittorrent_status": qb_status,
            "association_status": "associated",
            "recovery_info": None if resume_success else "Resume failed; reservation remains ACTIVE with known association, pending reconciliation resume retry."
        }

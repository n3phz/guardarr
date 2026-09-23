import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import get_settings
from app.db.models import ReservationModel, AuditLogModel, ReconcileStateModel, ReservationState
from app.services.qbittorrent import QBittorrentClient
from app.services.admission import calculate_remaining_unfulfilled

logger = logging.getLogger("guardarr.qbittorrent_reconciliation")


class QBittorrentReconciliationService:
    @staticmethod
    def associate_torrent(db: Session, reservation_id: str, torrent_hash: str) -> ReservationModel:
        db.execute(text("BEGIN IMMEDIATE"))
        reservation = db.query(ReservationModel).filter(ReservationModel.id == reservation_id).first()
        if not reservation:
            raise KeyError(f"Reservation {reservation_id} not found")

        if reservation.torrent_metadata_hash and reservation.torrent_metadata_hash.lower() != torrent_hash.lower():
            raise ValueError(f"Reservation {reservation_id} is already associated with torrent hash {reservation.torrent_metadata_hash}")

        normalized_hash = torrent_hash.lower()
        active_states = [ReservationState.RESERVED, ReservationState.ACTIVE]
        existing_claim = db.query(ReservationModel).filter(
            ReservationModel.torrent_metadata_hash == normalized_hash,
            ReservationModel.state.in_(active_states),
            ReservationModel.id != reservation_id
        ).first()

        if existing_claim:
            raise ValueError(f"Torrent hash {torrent_hash} is already claimed by another active reservation ({existing_claim.id})")

        settings = get_settings()
        tag = f"{settings.qbittorrent_torrent_tag_prefix}{reservation.id}"

        client = QBittorrentClient()
        torrent = client.get_torrent_by_hash(normalized_hash)
        if not torrent:
            raise ValueError(f"Torrent with hash {torrent_hash} not found in qBittorrent")

        fetched_hash = torrent.get("hash", "").lower()
        if fetched_hash != normalized_hash:
            raise ValueError(f"Torrent hash mismatch: requested {normalized_hash}, fetched {fetched_hash}")

        client.add_torrent_tags([normalized_hash], [tag])

        reservation.torrent_metadata_hash = normalized_hash
        reservation.torrent_tag = tag
        
        if reservation.state == ReservationState.RESERVED:
            reservation.state = ReservationState.ACTIVE

        completed = torrent.get("completed", 0)
        materialized = min(completed, reservation.max_bytes)
        reservation.observed_materialized_bytes = materialized
        reservation.remaining_unfulfilled_bytes = calculate_remaining_unfulfilled(
            reservation.max_bytes, materialized, reservation.import_mode
        )
        reservation.updated_at = datetime.utcnow()

        audit = AuditLogModel(
            reservation_id=reservation.id,
            event_type="torrent_associated",
            details=f"Associated torrent hash {normalized_hash} with deterministic tag {tag}"
        )
        db.add(audit)
        db.commit()
        db.refresh(reservation)
        return reservation

    @staticmethod
    def reconcile_torrents(db: Session) -> Dict[str, Any]:
        db.execute(text("BEGIN IMMEDIATE"))
        now = datetime.utcnow()
        settings = get_settings()
        client = QBittorrentClient()

        try:
            version_res = client.test_connectivity()
            if version_res.get("status") != "connected":
                return {
                    "status": "warning_qbittorrent_unavailable",
                    "reconciled_reservations_count": 0,
                    "unreserved_torrents_count": 0,
                    "unreserved_torrents": [],
                    "details": "qBittorrent is unavailable; skipped torrent reconciliation safely.",
                    "timestamp": now
                }
        except Exception as e:
            return {
                "status": "warning_qbittorrent_unavailable",
                "reconciled_reservations_count": 0,
                "unreserved_torrents_count": 0,
                "unreserved_torrents": [],
                "details": f"qBittorrent unavailable ({e}); skipped reconciliation safely.",
                "timestamp": now
            }

        all_torrents = client.get_torrents()
        torrent_map = {t.get("hash", "").lower(): t for t in all_torrents if t.get("hash")}

        # 1. Reconcile associated reservations & recover ASSOCIATION_PENDING reservations (Requirement 8)
        # Find reservations that lack torrent_metadata_hash but have a reservation tag in qBittorrent or reservation.torrent_tag
        active_states = [ReservationState.RESERVED, ReservationState.ACTIVE]
        reservations = db.query(ReservationModel).filter(
            ReservationModel.state.in_(active_states)
        ).all()

        reconciled_count = 0
        recovered_count = 0

        for r in reservations:
            tag = r.torrent_tag or f"{settings.qbittorrent_torrent_tag_prefix}{r.id}"
            
            # Check if reservation needs association recovery (ASSOCIATION_PENDING)
            if not r.torrent_metadata_hash:
                # Query qBittorrent for torrents carrying this tag
                tagged_torrents = client.get_torrents(tag=tag)
                if tagged_torrents:
                    t_item = tagged_torrents[0]
                    t_hash = t_item.get("hash", "").lower()
                    if t_hash:
                        # Recover association!
                        r.torrent_metadata_hash = t_hash
                        r.torrent_tag = tag
                        r.state = ReservationState.ACTIVE
                        completed = t_item.get("completed", 0)
                        materialized = min(completed, r.max_bytes)
                        r.observed_materialized_bytes = materialized
                        r.remaining_unfulfilled_bytes = calculate_remaining_unfulfilled(
                            r.max_bytes, materialized, r.import_mode
                        )
                        r.updated_at = now

                        db.add(AuditLogModel(
                            reservation_id=r.id,
                            event_type="torrent_association_recovered",
                            details=f"Reconciliation recovered association with torrent hash {t_hash} via tag {tag}"
                        ))
                        recovered_count += 1
                        torrent_map[t_hash] = t_item

            if r.torrent_metadata_hash:
                thash = r.torrent_metadata_hash.lower()
                torrent = torrent_map.get(thash)
                
                if not torrent:
                    db.add(AuditLogModel(
                        reservation_id=r.id,
                        event_type="torrent_missing",
                        details=f"Associated torrent hash {thash} was not found in qBittorrent during reconciliation"
                    ))
                    continue

                completed = torrent.get("completed", 0)
                materialized = min(completed, r.max_bytes)
                
                r.observed_materialized_bytes = materialized
                r.remaining_unfulfilled_bytes = calculate_remaining_unfulfilled(
                    r.max_bytes, materialized, r.import_mode
                )
                r.updated_at = now
                reconciled_count += 1

        # 2. Detect unreserved / bypass torrents
        prefix = settings.qbittorrent_torrent_tag_prefix
        valid_reservation_ids = {r.id for r in db.query(ReservationModel.id).all()}
        valid_tags = {f"{prefix}{rid}" for rid in valid_reservation_ids}
        
        unreserved_torrents = []
        for t in all_torrents:
            tags_str = t.get("tags", "")
            tags_list = [tag.strip() for tag in tags_str.split(",") if tag.strip()]
            
            guardarr_tags = [tag for tag in tags_list if tag.startswith(prefix)]
            if guardarr_tags:
                has_invalid_tag = any(gt not in valid_tags for gt in guardarr_tags)
                if has_invalid_tag:
                    unreserved_torrents.append({
                        "hash": t.get("hash", ""),
                        "name": t.get("name", ""),
                        "size": t.get("size", 0),
                        "progress": t.get("progress", 0.0),
                        "state": t.get("state", ""),
                        "tags": tags_list,
                        "save_path": t.get("save_path", "")
                    })
                    
                    db.add(AuditLogModel(
                        reservation_id="SYSTEM",
                        event_type="unreserved_torrent_detected",
                        details=f"Detected unreserved/bypass torrent hash {t.get('hash')} with invalid/orphaned Guardarr tag(s) {guardarr_tags}"
                    ))

        rec_state = db.query(ReconcileStateModel).filter(ReconcileStateModel.component == "qbittorrent").first()
        details_str = f"Reconciled {reconciled_count} reservations, recovered {recovered_count}, detected {len(unreserved_torrents)} unreserved torrents"
        if not rec_state:
            rec_state = ReconcileStateModel(
                component="qbittorrent",
                last_run_at=now,
                status="success",
                details=details_str
            )
            db.add(rec_state)
        else:
            rec_state.last_run_at = now
            rec_state.status = "success"
            rec_state.details = details_str

        db.commit()

        return {
            "status": "success",
            "reconciled_reservations_count": reconciled_count,
            "recovered_reservations_count": recovered_count,
            "unreserved_torrents_count": len(unreserved_torrents),
            "unreserved_torrents": unreserved_torrents,
            "details": details_str,
            "timestamp": now
        }

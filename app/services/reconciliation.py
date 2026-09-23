from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.models import ReservationModel, AuditLogModel, ReconcileStateModel, ReservationState


class ReconciliationService:
    @staticmethod
    def reconcile(db: Session) -> dict:
        db.execute(text("BEGIN IMMEDIATE"))
        now = datetime.utcnow()
        
        # 1. Detect expired reservations
        expired_res = db.query(ReservationModel).filter(
            ReservationModel.state.in_([ReservationState.PENDING, ReservationState.RESERVED, ReservationState.ACTIVE]),
            ReservationModel.expires_at.isnot(None),
            ReservationModel.expires_at < now
        ).all()
        
        expired_count = 0
        for r in expired_res:
            r.state = ReservationState.EXPIRED
            r.remaining_unfulfilled_bytes = 0
            r.updated_at = now
            
            audit = AuditLogModel(
                reservation_id=r.id,
                event_type="expired",
                details="Reservation expired past TTL during reconciliation"
            )
            db.add(audit)
            expired_count += 1

        # 2. Verify database consistency (ensure no negative remaining unfulfilled bytes)
        inconsistent = db.query(ReservationModel).filter(
            ReservationModel.remaining_unfulfilled_bytes < 0
        ).all()
        
        for r in inconsistent:
            r.remaining_unfulfilled_bytes = 0
            r.updated_at = now

        # 3. Update reconcile state log
        rec_state = db.query(ReconcileStateModel).filter(ReconcileStateModel.component == "reservations").first()
        if not rec_state:
            rec_state = ReconcileStateModel(
                component="reservations",
                last_run_at=now,
                status="success",
                details=f"Expired {expired_count} reservations, fixed {len(inconsistent)} inconsistencies"
            )
            db.add(rec_state)
        else:
            rec_state.last_run_at = now
            rec_state.status = "success"
            rec_state.details = f"Expired {expired_count} reservations, fixed {len(inconsistent)} inconsistencies"

        db.commit()
        
        return {
            "status": "success",
            "expired_count": expired_count,
            "inconsistencies_fixed": len(inconsistent),
            "timestamp": now
        }

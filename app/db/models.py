from datetime import datetime
from sqlalchemy import Column, String, Integer, BigInteger, DateTime, Text, Enum as SQLEnum, Index
import enum
from app.db.base import Base


class ReservationState(str, enum.Enum):
    PENDING = "PENDING"
    RESERVED = "RESERVED"
    ACTIVE = "ACTIVE"
    OWNED = "OWNED"
    RELEASED = "RELEASED"
    STALE = "STALE"
    EXPIRED = "EXPIRED"


class ImportMode(str, enum.Enum):
    HARDLINK = "hardlink"
    COPY = "copy"
    UNKNOWN = "unknown"


class ReservationModel(Base):
    __tablename__ = "reservations"

    id = Column(String(36), primary_key=True)
    idempotency_key = Column(String(255), nullable=False)
    adapter_name = Column(String(100), nullable=False)
    content_id = Column(String(255), nullable=True)
    torrent_metadata_hash = Column(String(64), nullable=True, index=True)
    target_device = Column(String(255), nullable=False, default="/data")
    max_bytes = Column(BigInteger, nullable=False)
    expected_bytes = Column(BigInteger, nullable=False)
    observed_materialized_bytes = Column(BigInteger, nullable=False, default=0)
    remaining_unfulfilled_bytes = Column(BigInteger, nullable=False)
    import_mode = Column(SQLEnum(ImportMode), nullable=False, default=ImportMode.UNKNOWN)
    priority = Column(Integer, nullable=False, default=0)
    owner = Column(String(100), nullable=True)
    torrent_tag = Column(String(100), nullable=True, index=True)
    state = Column(SQLEnum(ReservationState), nullable=False, default=ReservationState.RESERVED)
    # Arr integration fields
    arr_item_id = Column(String(255), nullable=True, index=True)
    associated_path = Column(String(1024), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_reservations_adapter_idempotency", "adapter_name", "idempotency_key", unique=True),
        Index("ix_reservations_state_target", "state", "target_device"),
    )


class AuditLogModel(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reservation_id = Column(String(36), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ReconcileStateModel(Base):
    __tablename__ = "reconcile_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    component = Column(String(100), nullable=False, unique=True)
    last_run_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)

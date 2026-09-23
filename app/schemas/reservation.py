from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator
from app.db.models import ReservationState, ImportMode


class EstimateRequest(BaseModel):
    max_bytes: int = Field(..., gt=0)
    expected_bytes: int = Field(..., gt=0)
    import_mode: ImportMode = ImportMode.UNKNOWN
    target_device: str = "/data"


class EstimateResponse(BaseModel):
    available_bytes: int
    outstanding_unfulfilled_bytes: int
    requested_bytes: int
    projected_available_bytes: int
    admission_floor_bytes: int
    admissible: bool
    reason: Optional[str] = None


class AdmitRequest(BaseModel):
    adapter_name: str = Field(..., min_length=1, max_length=100)
    idempotency_key: str = Field(..., min_length=1, max_length=255)
    content_id: Optional[str] = Field(None, max_length=255)
    torrent_metadata_hash: Optional[str] = Field(None, max_length=64)
    max_bytes: int = Field(..., gt=0)
    expected_bytes: int = Field(..., gt=0)
    observed_materialized_bytes: int = Field(0, ge=0)
    target_device: str = "/data"
    import_mode: ImportMode = ImportMode.UNKNOWN
    priority: int = Field(0, ge=0)
    owner: Optional[str] = Field(None, max_length=100)
    torrent_tag: Optional[str] = Field(None, max_length=100)
    ttl_seconds: Optional[int] = Field(None, gt=0)

    @field_validator("max_bytes", "expected_bytes")
    @classmethod
    def validate_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Bytes must be greater than zero")
        return v


class ReleaseRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=255)


class ReservationResponse(BaseModel):
    id: str
    idempotency_key: str
    adapter_name: str
    content_id: Optional[str]
    torrent_metadata_hash: Optional[str]
    target_device: str
    max_bytes: int
    expected_bytes: int
    observed_materialized_bytes: int
    remaining_unfulfilled_bytes: int
    import_mode: ImportMode
    priority: int
    owner: Optional[str]
    torrent_tag: Optional[str]
    state: ReservationState
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


class ReconcileResponse(BaseModel):
    status: str
    expired_count: int
    details: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

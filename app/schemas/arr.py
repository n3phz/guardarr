from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator
from app.db.models import ReservationState


# Python 3.11 compatible: use Literal as annotation, not base class
ArrProvider = Literal["sonarr", "radarr"]


class ArrEstimateRequest(BaseModel):
    provider: ArrProvider
    content_id: str = Field(..., min_length=1, max_length=255)
    arr_item_id: Optional[str] = Field(None, max_length=255)
    estimated_size_bytes: int = Field(..., gt=0)
    target_device: str = "/data"


class ArrEstimateResponse(BaseModel):
    available_bytes: int
    outstanding_unfulfilled_bytes: int
    requested_bytes: int
    projected_available_bytes: int
    admission_floor_bytes: int
    admissible: bool
    reason: Optional[str] = None


class ArrAdmitRequest(BaseModel):
    provider: ArrProvider
    content_id: str = Field(..., min_length=1, max_length=255)
    arr_item_id: Optional[str] = Field(None, max_length=255)
    max_bytes: int = Field(..., gt=0)
    expected_bytes: int = Field(..., gt=0)
    target_device: str = "/data"
    import_mode: str = "copy"
    priority: int = Field(0, ge=0)
    ttl_seconds: Optional[int] = Field(None, gt=0)

    @field_validator("max_bytes", "expected_bytes")
    @classmethod
    def validate_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Bytes must be greater than zero")
        return v


class ArrAdmitResponse(BaseModel):
    reservation_id: str
    state: ReservationState
    max_bytes: int
    expected_bytes: int
    target_device: str
    idempotency_key: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    note: str = "Reservation created in RESERVED state. Controlled qBittorrent admission is required to transition RESERVED -> ACTIVE."


class ArrImportedRequest(BaseModel):
    provider: ArrProvider
    content_id: str = Field(..., min_length=1, max_length=255)
    arr_item_id: str = Field(..., min_length=1, max_length=255)
    torrent_hash: Optional[str] = Field(None, min_length=1, max_length=64)
    imported_path: Optional[str] = Field(None, max_length=1024)


class ArrImportedResponse(BaseModel):
    reservation_id: str
    state: ReservationState
    ownership_verified: bool
    message: str
    released: bool = False


class ArrReleaseRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=255)


class ArrReservationDetail(BaseModel):
    reservation_id: str
    idempotency_key: str
    adapter_name: str
    content_id: Optional[str]
    arr_item_id: Optional[str]
    torrent_metadata_hash: Optional[str]
    associated_path: Optional[str]
    target_device: str
    max_bytes: int
    expected_bytes: int
    observed_materialized_bytes: int
    remaining_unfulfilled_bytes: int
    import_mode: str
    priority: int
    owner: Optional[str]
    torrent_tag: Optional[str]
    state: ReservationState
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]


class ArrHealthResponse(BaseModel):
    provider: ArrProvider
    status: str
    version: Optional[str] = None
    reason: Optional[str] = None

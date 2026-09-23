from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class StorageStatusBase(BaseModel):
    total_bytes: int
    available_bytes: int
    free_bytes: int
    total_inodes: int
    available_inodes: int
    filesystem_identity: str
    device_identity: str


class StorageStatusCreate(StorageStatusBase):
    pass


class StorageStatusResponse(StorageStatusBase):
    inode_usage_percent: Optional[float] = None
    warning_threshold: int = 1_000_000_000_000
    admission_floor_threshold: int = 750_000_000_000
    emergency_threshold: int = 500_000_000_000
    critical_threshold: int = 250_000_000_000
    threshold_state: str = "NORMAL"
    is_blocked: bool = False
    timestamp: Optional[datetime] = None


class ThresholdState(str):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"
    EMERGENCY = "EMERGENCY"
    CRITICAL = "CRITICAL"

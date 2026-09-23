from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


class TorrentAssociateRequest(BaseModel):
    torrent_hash: str = Field(..., min_length=1, max_length=64)


class QBittorrentStatusResponse(BaseModel):
    status: str
    version: Optional[str] = None
    reason: Optional[str] = None


class UnreservedTorrentResponse(BaseModel):
    hash: str
    name: str
    size: int
    progress: float
    state: str
    tags: List[str]
    save_path: str


class TorrentReconcileResponse(BaseModel):
    status: str
    reconciled_reservations_count: int
    recovered_reservations_count: int
    unreserved_torrents_count: int
    unreserved_torrents: List[UnreservedTorrentResponse]
    details: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from urllib.parse import urlparse


class ControlledAddRequest(BaseModel):
    url_or_magnet: str = Field(..., min_length=4, max_length=2048)
    savepath: Optional[str] = Field(None, max_length=1024)
    category: Optional[str] = Field(None, max_length=255)
    idempotency_key: str = Field(..., min_length=1, max_length=255)

    @field_validator("url_or_magnet")
    @classmethod
    def validate_url_or_magnet(cls, v: str) -> str:
        v = v.strip()
        if v.startswith("magnet:?"):
            return v
        parsed = urlparse(v)
        if parsed.scheme not in ["http", "https"]:
            raise ValueError("Torrent source must be a valid http://, https:// URL or magnet:? URI")
        return v

    @field_validator("savepath")
    @classmethod
    def validate_savepath(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            # Path traversal safety checks
            if ".." in v or v.startswith("~") or not v.startswith("/"):
                raise ValueError("Savepath must be an absolute path and cannot contain path traversal sequences ('..')")
        return v


class ControlledAddResponse(BaseModel):
    reservation_id: str
    torrent_hash: Optional[str] = None
    torrent_tag: str
    state: str
    qbittorrent_status: str
    association_status: str
    recovery_info: Optional[str] = None

class ControlledAddRequestV2(BaseModel):
    url_or_magnet: str = Field(..., min_length=4, max_length=2048)
    savepath: Optional[str] = Field(None, max_length=1024)
    category: Optional[str] = Field(None, max_length=255)
    idempotency_key: str = Field(..., min_length=1, max_length=255)

    @field_validator("url_or_magnet")
    @classmethod
    def validate_url_or_magnet(cls, v: str) -> str:
        v = v.strip()
        if v.startswith("magnet:?"):
            return v
        parsed = urlparse(v)
        if parsed.scheme not in ["http", "https"]:
            raise ValueError("Torrent source must be a valid http://, https:// URL or magnet:? URI")
        return v

    @field_validator("savepath")
    @classmethod
    def validate_savepath(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            # Absolute path validation and container storage containment
            if ".." in v or v.startswith("~") or not v.startswith("/"):
                raise ValueError("Savepath must be an absolute path and cannot contain path traversal sequences ('..')")
            # Storage root security containment check against /data or configured data storage path
            if not v.startswith("/data") and not v.startswith("/config") and not v.startswith("/workspace"):
                raise ValueError("Savepath must reside within authorized container storage boundaries (/data or /config)")
        return v

from pathlib import Path
from typing import Any, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.core.thresholds import ThresholdConfig


class Settings(BaseSettings):
    guardarr_data_dir: Path = Field(default=Path("/config"))
    guardarr_storage_path: Path = Field(default=Path("/data"))
    
    warning_threshold_bytes: int = Field(default=1_000_000_000_000)
    admission_floor_bytes: int = Field(default=750_000_000_000)
    emergency_threshold_bytes: int = Field(default=500_000_000_000)
    critical_threshold_bytes: int = Field(default=250_000_000_000)
    
    database_url: str = Field(default="sqlite:////config/guardarr.db")

    # qBittorrent Configuration (Phase 3)
    qbittorrent_url: str = Field(default="http://localhost:8080")
    qbittorrent_username: str = Field(default="admin")
    qbittorrent_password: str = Field(default="adminadmin")
    qbittorrent_timeout_seconds: int = Field(default=10)
    qbittorrent_verify_tls: bool = Field(default=True)
    qbittorrent_torrent_tag_prefix: str = Field(default="guardarr:")

    # Sonarr Configuration (Phase 5)
    sonarr_url: str = Field(default="http://localhost:8989")
    sonarr_api_key: str = Field(default="sonarr_mock_key")
    sonarr_timeout_seconds: int = Field(default=10)
    sonarr_verify_tls: bool = Field(default=True)

    # Radarr Configuration (Phase 5)
    radarr_url: str = Field(default="http://localhost:7878")
    radarr_api_key: str = Field(default="radarr_mock_key")
    radarr_timeout_seconds: int = Field(default=10)
    radarr_verify_tls: bool = Field(default=True)

    # Seerr Configuration (Phase 6)
    seerr_url: str = Field(default="http://localhost:8990")
    seerr_api_key: str = Field(default="seerr_mock_key")
    seerr_timeout_seconds: int = Field(default=10)
    seerr_verify_tls: bool = Field(default=True)

    # Jellyseerr Configuration (Phase 6)
    jellyseerr_url: str = Field(default="http://localhost:8991")
    jellyseerr_api_key: str = Field(default="jellyseerr_mock_key")
    jellyseerr_timeout_seconds: int = Field(default=10)
    jellyseerr_verify_tls: bool = Field(default=True)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("guardarr_data_dir", "guardarr_storage_path", mode="before")
    @classmethod
    def ensure_absolute_path(cls, v: Any) -> Path:
        if isinstance(v, str):
            return Path(v).resolve()
        return v

    @staticmethod
    def validate_threshold_order() -> None:
        """Validate threshold ordering at startup."""
        settings = _settings or Settings()
        if settings.warning_threshold_bytes <= settings.admission_floor_bytes:
            raise ValueError("warning threshold must be greater than admission floor")
        if settings.admission_floor_bytes <= settings.emergency_threshold_bytes:
            raise ValueError("admission floor must be greater than emergency threshold")
        if settings.emergency_threshold_bytes <= settings.critical_threshold_bytes:
            raise ValueError("emergency threshold must be greater than critical threshold")

    @property
    def thresholds(self) -> ThresholdConfig:
        return ThresholdConfig(
            warning=self.warning_threshold_bytes,
            admission_floor=self.admission_floor_bytes,
            emergency=self.emergency_threshold_bytes,
            critical=self.critical_threshold_bytes
        )


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

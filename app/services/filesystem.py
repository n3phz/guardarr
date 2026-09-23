import os
import errno
from typing import Optional, Tuple

from app.core.config import Settings
from app.core.filesystem import get_filesystem_stats


class FilesystemMonitor:
    def __init__(self, settings: Optional[Settings] = None):
        from app.core.config import get_settings
        self.settings = settings or get_settings()

    def scan(self) -> dict:
        return get_filesystem_stats(self.settings.guardarr_storage_path)

    def check_thresholds(self, available_bytes: int) -> str:
        critical = self.settings.critical_threshold_bytes
        emergency = self.settings.emergency_threshold_bytes
        admission_floor = self.settings.admission_floor_bytes
        warning = self.settings.warning_threshold_bytes

        if available_bytes <= critical:
            return "CRITICAL"
        elif available_bytes <= emergency:
            return "EMERGENCY"
        elif available_bytes <= admission_floor:
            return "BLOCKED"
        elif available_bytes <= warning:
            return "WARNING"
        return "NORMAL"

    def is_admission_blocked(self, available_bytes: Optional[int] = None) -> bool:
        if available_bytes is None:
            stats = self.scan()
            available_bytes = stats["available_bytes"]
        admission_floor = self.settings.admission_floor_bytes
        return available_bytes <= admission_floor

    def to_bytes(self, value) -> int:
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            value = value.strip().upper()
            multipliers = {
                "B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3,
                "TB": 1024**4, "KIB": 1024, "MIB": 1024**2, "GIB": 1024**3,
                "TIB": 1024**4,
            }
            # Sort suffixes by length descending so longer suffixes match first
            # (e.g. "GB" before "B", "GIB" before "MIB")
            sorted_multipliers = sorted(multipliers.items(), key=lambda x: len(x[0]), reverse=True)
            for suffix, mult in sorted_multipliers:
                if value.endswith(suffix):
                    number = value[:-len(suffix)]
                    try:
                        return int(float(number) * mult)
                    except ValueError:
                        raise ValueError(f"Invalid size value: {value}")
            try:
                return int(value)
            except ValueError:
                raise ValueError(f"Invalid size value: {value}")
        raise TypeError(f"Cannot convert {type(value)} to bytes")

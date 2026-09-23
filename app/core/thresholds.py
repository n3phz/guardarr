from dataclasses import dataclass
from enum import StrEnum


class ThresholdState(StrEnum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"
    EMERGENCY = "EMERGENCY"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class ThresholdConfig:
    warning: int
    admission_floor: int
    emergency: int
    critical: int


@dataclass(frozen=True, slots=True)
class ThresholdResult:
    state: ThresholdState
    available_bytes: int
    admission_blocked: bool


def classify_storage(available_bytes: int, thresholds: ThresholdConfig) -> ThresholdResult:
    if available_bytes <= thresholds.critical:
        state = ThresholdState.CRITICAL
    elif available_bytes <= thresholds.emergency:
        state = ThresholdState.EMERGENCY
    elif available_bytes <= thresholds.admission_floor:
        state = ThresholdState.BLOCKED
    elif available_bytes <= thresholds.warning:
        state = ThresholdState.WARNING
    else:
        state = ThresholdState.NORMAL

    return ThresholdResult(
        state=state,
        available_bytes=available_bytes,
        admission_blocked=(
            available_bytes <= thresholds.admission_floor
        ),
    )

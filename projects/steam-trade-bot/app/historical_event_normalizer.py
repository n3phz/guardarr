"""Normalization layer between MarketHistoryEvent and the future importer.

This module is a pure, read-only transformation. It does NOT touch the
database, inventory, Steam, or perform any HTTP requests. It does NOT
calculate profit, ROI, margin, or fabricate fees/timestamps.

Flow:

    Steam Community Market response
        -> MarketHistoryAdapter (client + parser)
        -> MarketHistoryEvent
        -> HistoricalEventNormalizer  (this module)
        -> NormalizedHistoricalEvent
        -> future transaction importer
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Literal, Optional

from market_history_adapter import MarketHistoryEvent

CostStatus = Literal["TRACKED", "UNKNOWN"]


class HistoricalEventNormalizationError(ValueError):
    """Raised when a MarketHistoryEvent cannot be normalized safely."""


@dataclass(frozen=True)
class NormalizedHistoricalEvent:
    """Normalized historical event for downstream import.

    Historical Steam market-history events carry no trusted acquisition
    cost at this stage, so cost_status is always UNKNOWN.
    """

    type: Literal["BUY", "SELL"]
    market_hash_name: str
    quantity: int
    unit_price: Decimal
    fees: Optional[Decimal]
    total_value: Decimal
    timestamp: Optional[str]
    external_ref: str
    cost_status: CostStatus

    # V0.5.9 fields for downstream projection (preserved from raw event)
    event_type: str = "BUY"          # Alias for type
    listingid: str = ""               # Parsed from external_ref
    purchaseid: str = ""              # Parsed from external_ref
    time_event: Optional[str] = None  # Alias for timestamp
    asset_amount: str = "1"           # Quantity as string for asset_amount field
    unit_cost: Optional[Decimal] = None  # Historical cost = UNKNOWN


def normalize_market_history_event(
    event: MarketHistoryEvent,
) -> NormalizedHistoricalEvent:
    """Normalize a single MarketHistoryEvent.

    All monetary values are preserved as Decimal. ``fees=None`` and
    ``timestamp=None`` are preserved as None rather than being coerced
    to synthetic values. ``cost_status`` is always UNKNOWN because
    historical Steam events carry no trusted acquisition cost.
    """

    if event.type not in ("BUY", "SELL"):
        raise HistoricalEventNormalizationError(
            f"invalid event type: {event.type!r}"
        )

    if not isinstance(event.market_hash_name, str) or not event.market_hash_name.strip():
        raise HistoricalEventNormalizationError(
            "market_hash_name must be a non-empty string"
        )

    if isinstance(event.quantity, bool) or not isinstance(event.quantity, int):
        raise HistoricalEventNormalizationError(
            "quantity must be an integer"
        )

    if event.quantity <= 0:
        raise HistoricalEventNormalizationError(
            "quantity must be greater than zero"
        )

    if not isinstance(event.unit_price, Decimal) or event.unit_price < 0:
        raise HistoricalEventNormalizationError(
            "unit_price must be non-negative"
        )

    if event.fees is not None:
        if not isinstance(event.fees, Decimal) or event.fees < 0:
            raise HistoricalEventNormalizationError(
                "fees must be non-negative when present"
            )

    if not isinstance(event.total_value, Decimal) or event.total_value < 0:
        raise HistoricalEventNormalizationError(
            "total_value must be non-negative"
        )

    if event.timestamp is not None:
        if not isinstance(event.timestamp, str) or not event.timestamp.strip():
            raise HistoricalEventNormalizationError(
                "timestamp must be a non-empty string when present"
            )

    if not isinstance(event.external_ref, str) or not event.external_ref.strip():
        raise HistoricalEventNormalizationError(
            "external_ref must be a non-empty string"
        )

    # Parse listingid and purchaseid from external_ref
    # external_ref format: "listing-XXXX:purchase-XXXX" or "history_row_XXX_YYY:12345"
    if ":" in event.external_ref and event.external_ref.count(":") >= 1:
        parts = event.external_ref.split(":")
        listingid = parts[0]
        purchaseid = parts[1] if len(parts) > 1 else ""
    else:
        listingid = event.external_ref
        purchaseid = ""

    return NormalizedHistoricalEvent(
        type=event.type,
        market_hash_name=event.market_hash_name,
        quantity=event.quantity,
        unit_price=event.unit_price,
        fees=event.fees,
        total_value=event.total_value,
        timestamp=event.timestamp,
        external_ref=event.external_ref,
        cost_status="UNKNOWN",
        event_type=event.type,
        listingid=listingid,
        purchaseid=purchaseid,
        time_event=event.timestamp,
        asset_amount=str(event.quantity),
        unit_cost=None,
    )


def normalize_market_history_events(
    events: List[MarketHistoryEvent],
) -> List[NormalizedHistoricalEvent]:
    """Normalize a sequence of MarketHistoryEvents.

    This simply normalizes each event in order. No additional business
    logic is introduced.
    """

    return [normalize_market_history_event(e) for e in events]

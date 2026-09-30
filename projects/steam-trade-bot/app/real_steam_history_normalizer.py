"""Real Steam Market History normalizer for captured JSON pages.

Reads authenticated TradeBridge-style pages from local JSON files
(produced by an external capture) and normalizes them to
MarketHistoryEvent without any HTTP, DB, or Steam writes.

Classification uses the strict V0.5.8 rules the real dataset was
audited against:
    event_type == 4
    account == steamid_actor == steamid_purchaser
    purchase exists with failed == 0 and needs_rollback == 0
Any event not meeting all conditions becomes UNKNOWN.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from market_history_adapter import MarketHistoryEvent


class RealHistoryError(ValueError):
    """Raised when a captured page cannot be normalized safely."""


@dataclass(frozen=True)
class NormalizedRealEvent:
    """Normalized event from a captured Steam history page."""

    event_type: str  # BUY | UNKNOWN
    market_hash_name: Optional[str]
    quantity: int
    unit_price: Decimal
    fees: Optional[Decimal]
    total_value: Decimal
    timestamp: Optional[str]
    external_ref: str
    time_event_raw: Any
    listingid: str
    purchaseid: str
    steamid_actor: str
    steamid_purchaser: str
    paid_amount: int
    paid_fee: int
    steam_fee: int
    publisher_fee: int
    publisher_fee_percent: Optional[str]
    publisher_fee_app: Optional[int]
    funds_returned: int
    received_amount: int
    currencyid: int
    received_currencyid: int
    added_tax: int
    asset_appid: str
    asset_contextid: str
    asset_id: str
    asset_classid: str
    asset_instanceid: str
    asset_amount: str


def _decimal(value: Any, default: Decimal) -> Decimal:
    try:
        d = Decimal(str(value))
        return d if d.is_finite() and d >= 0 else default
    except (InvalidOperation, TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        iv = int(value)
        return iv if iv >= 0 else default
    except (TypeError, ValueError):
        return default


def _validate_event_shape(event: Any, index: int) -> Mapping[str, Any]:
    if not isinstance(event, Mapping):
        raise RealHistoryError(f"event[{index}] is not a mapping")
    for key in ("listingid", "purchaseid", "event_type", "steamid_actor", "steamid_purchaser"):
        if key not in event:
            raise RealHistoryError(f"event[{index}] missing {key}")
    return event


def _classify(
    event: Mapping[str, Any],
    purchase: Optional[Mapping[str, Any]],
    listing: Optional[Mapping[str, Any]],
    account_steamid: str,
) -> str:
    actor = (event.get("steamid_actor") or "").strip()
    purchaser = (event.get("steamid_purchaser") or "").strip()
    acct = (account_steamid or "").strip()
    has_purchase = isinstance(purchase, Mapping) and bool(purchase)
    has_listing = isinstance(listing, Mapping) and bool(listing)
    if (
        event.get("event_type") == 4
        and actor == acct
        and purchaser == acct
        and acct
        and has_listing
        and has_purchase
        and int(purchase.get("failed", 0)) == 0
        and int(purchase.get("needs_rollback", 0)) == 0
    ):
        return "BUY"
    return "UNKNOWN"


def _resolve_market_hash_name(
    assets: Mapping[str, Any],
    asset_id: str,
) -> Optional[str]:
    if not asset_id or not isinstance(assets, Mapping):
        return None
    # Steam nests assets as assets[appid][contextid][assetid].
    for appid, contexts in assets.items():
        if not isinstance(contexts, Mapping):
            continue
        for contextid, leaf_map in contexts.items():
            if not isinstance(leaf_map, Mapping):
                continue
            leaf = leaf_map.get(asset_id)
            if isinstance(leaf, Mapping):
                mhn = leaf.get("market_hash_name")
                if isinstance(mhn, str) and mhn.strip():
                    return mhn.strip()
    return None


def _resolve_asset_metadata(
    assets: Mapping[str, Any],
    asset_id: str,
) -> Optional[Dict[str, str]]:
    if not asset_id or not isinstance(assets, Mapping):
        return None
    for appid, contexts in assets.items():
        if not isinstance(contexts, Mapping):
            continue
        for contextid, leaf_map in contexts.items():
            if not isinstance(leaf_map, Mapping):
                continue
            leaf = leaf_map.get(asset_id)
            if isinstance(leaf, Mapping):
                return {
                    "appid": str(appid),
                    "contextid": str(contextid),
                    "assetid": asset_id,
                    "classid": str(leaf.get("classid", "")),
                    "instanceid": str(leaf.get("instanceid", "")),
                    "amount": str(leaf.get("amount", "")),
                }
    return None


def _timestamp_from_event(event: Mapping[str, Any]) -> Optional[str]:
    value = event.get("time_event")
    if value is None:
        return None
    # Real captured pages use integer epoch seconds, sometimes with fraction.
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        except (ValueError, OSError, OverflowError):
            return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _normalize_event(
    event: Mapping[str, Any],
    purchase: Optional[Mapping[str, Any]],
    listing: Optional[Mapping[str, Any]],
    assets: Mapping[str, Any],
    account_steamid: str,
) -> Optional[NormalizedRealEvent]:
    event = _validate_event_shape(event, 0)
    listingid = str(event.get("listingid") or "")
    purchaseid = str(event.get("purchaseid") or "")
    if not listingid or not purchaseid:
        return None

    classification = _classify(event, purchase, listing, account_steamid)

    asset_id = ""
    if isinstance(listing, Mapping):
        asset_ref = listing.get("asset")
        if isinstance(asset_ref, Mapping):
            asset_id = str(asset_ref.get("assetid") or "")
        if not asset_id:
            asset_id = str(listing.get("assetid") or "")

    market_hash_name = _resolve_market_hash_name(assets, asset_id) if asset_id else None
    meta = _resolve_asset_metadata(assets, asset_id) if asset_id else None

    paid_amount = _safe_int(purchase.get("paid_amount") if isinstance(purchase, Mapping) else None)
    paid_fee = _safe_int(purchase.get("paid_fee") if isinstance(purchase, Mapping) else None)
    steam_fee = _safe_int(purchase.get("steam_fee") if isinstance(purchase, Mapping) else None)
    publisher_fee = _safe_int(purchase.get("publisher_fee") if isinstance(purchase, Mapping) else None)
    funds_returned = _safe_int(purchase.get("funds_returned") if isinstance(purchase, Mapping) else None)
    received_amount = _safe_int(purchase.get("received_amount") if isinstance(purchase, Mapping) else None)
    currencyid = _safe_int(purchase.get("currencyid") if isinstance(purchase, Mapping) else None)
    received_currencyid = _safe_int(purchase.get("received_currencyid") if isinstance(purchase, Mapping) else None)
    added_tax = _safe_int(purchase.get("added_tax") if isinstance(purchase, Mapping) else None)

    unit_price = Decimal(str(paid_amount))
    fees = Decimal(str(paid_fee))
    total_value = unit_price  # each captured BUY event represents one item received

    return NormalizedRealEvent(
        event_type=classification,
        market_hash_name=market_hash_name,
        quantity=_safe_int(str(purchase.get("asset", {}).get("amount", "1") if isinstance(purchase, Mapping) else "1")),
        unit_price=unit_price,
        fees=fees,
        total_value=total_value,
        timestamp=_timestamp_from_event(event),
        external_ref=f"{listingid}:{purchaseid}",
        time_event_raw=event.get("time_event"),
        listingid=listingid,
        purchaseid=purchaseid,
        steamid_actor=str(event.get("steamid_actor") or ""),
        steamid_purchaser=str(event.get("steamid_purchaser") or ""),
        paid_amount=paid_amount,
        paid_fee=paid_fee,
        steam_fee=steam_fee,
        publisher_fee=publisher_fee,
        publisher_fee_percent=(purchase.get("publisher_fee_percent") if isinstance(purchase, Mapping) else None),
        publisher_fee_app=(purchase.get("publisher_fee_app") if isinstance(purchase, Mapping) else None),
        funds_returned=funds_returned,
        received_amount=received_amount,
        currencyid=currencyid,
        received_currencyid=received_currencyid,
        added_tax=added_tax,
        asset_appid=str(meta.get("appid", "")) if meta else "",
        asset_contextid=str(meta.get("contextid", "")) if meta else "",
        asset_id=str(meta.get("assetid", "")) if meta else "",
        asset_classid=str(meta.get("classid", "")) if meta else "",
        asset_instanceid=str(meta.get("instanceid", "")) if meta else "",
        asset_amount=str(meta.get("amount", "")) if meta else "",
    )


def load_pages(paths: Sequence[Path]) -> Tuple[Mapping[str, Any], List[str]]:
    """Merge multiple captured pages into one validated response-like mapping."""
    events: List[Any] = []
    purchases: Dict[str, Any] = {}
    listings: Dict[str, Any] = {}
    assets: Dict[str, Any] = {}
    errors: List[str] = []
    total_count: Optional[int] = None

    for path in paths:
        if not path.is_file():
            errors.append(f"{path}: not found")
            continue
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"{path}: invalid JSON: {exc}")
            continue
        if not isinstance(data, Mapping):
            errors.append(f"{path}: top-level is not an object")
            continue
        if total_count is None:
            total_count = data.get("total_count")
        elif data.get("total_count") != total_count:
            errors.append(f"{path}: total_count changed during pagination")
        events.extend(data.get("events", []))
        purchases.update(data.get("purchases", {}))
        listings.update(data.get("listings", {}))
        for appid, contexts in data.get("assets", {}).items():
            assets.setdefault(appid, {})
            if isinstance(contexts, Mapping):
                assets[appid].update(contexts)

    if errors:
        raise RealHistoryError("; ".join(errors))
    if not events:
        raise RealHistoryError("no events loaded")
    if total_count is None:
        raise RealHistoryError("no total_count present")

    return (
        {
            "success": True,
            "pagesize": len(events),
            "total_count": total_count,
            "start": 0,
            "assets": assets,
            "events": events,
            "purchases": purchases,
            "listings": listings,
        },
        errors,
    )


def normalize_real_events(
    data: Mapping[str, Any],
    account_steamid: str,
) -> Tuple[List[NormalizedRealEvent], List[str]]:
    """Normalize every event in a merged captured page response."""
    assets = data.get("assets", {})
    if not isinstance(assets, Mapping):
        assets = {}
    purchases = data.get("purchases", {})
    if not isinstance(purchases, Mapping):
        purchases = {}
    listings = data.get("listings", {})
    if not isinstance(listings, Mapping):
        listings = {}
    events = data.get("events", [])
    if not isinstance(events, list):
        events = []

    normalized: List[NormalizedRealEvent] = []
    errors: List[str] = []
    for index, raw in enumerate(events):
        try:
            event = _normalize_event(
                raw,
                purchases.get(f"{raw.get('listingid')}_{raw.get('purchaseid')}") if isinstance(raw, Mapping) else None,
                listings.get(raw.get("listingid")) if isinstance(raw, Mapping) else None,
                assets,
                account_steamid,
            )
        except RealHistoryError as exc:
            errors.append(f"event[{index}]: {exc}")
            continue
        if event is None:
            errors.append(f"event[{index}]: could not normalize")
            continue
        normalized.append(event)
    return normalized, errors


def to_market_history_event(event: NormalizedRealEvent) -> MarketHistoryEvent:
    """Map a normalized real event to the existing MarketHistoryEvent contract."""
    return MarketHistoryEvent(
        type=event.event_type,
        market_hash_name=event.market_hash_name or "",
        quantity=event.quantity,
        unit_price=event.unit_price,
        fees=event.fees,
        total_value=event.total_value,
        timestamp=event.timestamp,
        external_ref=event.external_ref,
        steam_fee=Decimal(str(event.steam_fee)),
        publisher_fee=Decimal(str(event.publisher_fee)),
        publisher_fee_percent=event.publisher_fee_percent,
        publisher_fee_app=event.publisher_fee_app,
        funds_returned=Decimal(str(event.funds_returned)),
        received_amount=Decimal(str(event.received_amount)),
        currencyid=event.currencyid,
        received_currencyid=event.received_currencyid,
        added_tax=Decimal(str(event.added_tax)),
        cost_status="UNKNOWN",
        unit_cost=None,
    )

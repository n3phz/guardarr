"""V0.6.1 projection from V0.5.9 normalized BUY events.

This is a pure DRY-RUN projection layer that operates on already-normalized
V0.5.9 BUY events and projects them into the existing V0.5.0 Transaction and
AcquisitionLot domain model WITHOUT PERFORMING ANY DATABASE WRITES.

The entire implementation is side-effect free, with no imports to the
SQLite persistence layer, no HTTP requests, and no external state changes.

Pipeline:
    NormalizedBuyEvent (V0.5.9) → Project Transaction → Project AcquisitionLot
                                      ↓
                            DryRunReport (aggregation of all projections)

Economic Rule:
    Historical cost is UNKNOWN.
    All acquisition lots must have cost_status = "UNKNOWN" and unit_cost = None.

Raw Value Preservation:
    - publisher_fee_percent is preserved as exact Steam string "0.100000001490116119"
    - publisher_fee_app is preserved as exact Steam integer 730
    - All other monetary fields preserved as raw integers where applicable
    - NO currency conversion, NO EUR-cents assumption
    - Decimal conversion for Transaction compatibility documented as type coercion only

External Reference:
    Deterministic source identity derived from:
        external_ref = f"{listingid}:{purchaseid}"
    (same input always produces same output)

Duplicate Handling:
    - Duplicate listingid+purchaseid events are detected and counted
    - Duplicates are NOT silently created as separate transactions
    - Reported in duplicate_events count

No Economic Calculations:
    - No profit or ROI calculations
    - No acquisition cost derivation from paid_amount, fees, etc.
    - No currency conversion or EUR-cents assumption

Implementation Constraints:
    - The existing V0.5.0 Transaction model requires Decimal for monetary fields
    - V0.5.9 provides raw integers
    - Projection uses Decimal(str(int_value)) type coercion (documented)
    - Do not alter V0.5.0 domain models
    - Do not perform any database operations

Warning:
    This implementation is designed for projection and validation ONLY.
    It should NEVER be used in production with actual database writes
    without significant architectural considerations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any
from decimal import Decimal

from transactions import Transaction, CostStatus, AcquisitionLot


@dataclass(frozen=True)
class DryRunReport:
    """Immutable report of V0.6.1 dry-run projection results."""

    total_input_events: int
    valid_buy_events: int
    unknown_events: int
    invalid_events: int
    duplicate_events: int
    projected_transactions: List[Transaction]
    projected_acquisition_lots: List[Any]
    validation_errors: List[Dict[str, Any]]


def _parse_quantity(asset_amount: Any) -> int:
    """
    Parse and validate quantity from asset_amount.

    Args:
        asset_amount: The asset_amount field from normalized event (str, int, or None)

    Returns:
        int: Validated positive quantity

    Raises:
        ValueError: If quantity is invalid (missing, empty, non-numeric, zero, or negative)
    """
    if asset_amount is None:
        raise ValueError("Invalid quantity")

    # Handle string values
    if isinstance(asset_amount, str):
        asset_amount = asset_amount.strip()
        if not asset_amount:
            raise ValueError("Invalid quantity")
        try:
            quantity = int(asset_amount)
        except (ValueError, TypeError):
            raise ValueError("Invalid quantity")
    elif isinstance(asset_amount, int) and not isinstance(asset_amount, bool):
        quantity = asset_amount
    else:
        raise ValueError("Invalid quantity")

    if quantity <= 0:
        raise ValueError("Invalid quantity")

    return quantity


def _validate_timestamp(time_event: Any) -> str:
    """
    Validate timestamp from time_event.

    Args:
        time_event: The time_event field from normalized event

    Returns:
        str: Validated timestamp

    Raises:
        ValueError: If timestamp is missing or empty
    """
    if time_event is None:
        raise ValueError("timestamp is missing")

    if isinstance(time_event, str) and not time_event.strip():
        raise ValueError("timestamp is missing")

    return str(time_event)


def project_transaction(
    normalized_buy_event: Any,
    bot_name: str,
) -> Transaction:
    """
    Project a V0.5.9 normalized BUY event to a V0.5.0 Transaction.

    Args:
        normalized_buy_event: NormalizedEvent from steam_market_history_json
        bot_name: Bot name for the projection

    Returns:
        Transaction: V0.5.0 Transaction instance

    Raises:
        ValueError: If event cannot be projected
    """
    if not hasattr(normalized_buy_event, 'event_type'):
        raise ValueError("Event missing required attributes")

    if getattr(normalized_buy_event, 'event_type', None) != 'BUY':
        raise ValueError(f"Event type is not BUY: {normalized_buy_event.event_type}")

    market_hash_name = getattr(normalized_buy_event, 'market_hash_name', None)
    if not isinstance(market_hash_name, str) or not market_hash_name.strip():
        raise ValueError("market_hash_name is missing or empty")

    if not isinstance(bot_name, str) or not bot_name.strip():
        raise ValueError("bot_name must be a non-empty string")

    # Parse and validate quantity from asset_amount
    asset_amount = getattr(normalized_buy_event, 'asset_amount', None)
    quantity = _parse_quantity(asset_amount)

    # Validate timestamp
    timestamp = getattr(normalized_buy_event, 'time_event', None)
    timestamp = _validate_timestamp(timestamp)

    listingid = getattr(normalized_buy_event, 'listingid', None)
    purchaseid = getattr(normalized_buy_event, 'purchaseid', None)
    if not listingid or not purchaseid:
        raise ValueError("listingid or purchaseid is missing")

    external_ref = f"{listingid}:{purchaseid}"

    paid_amount = getattr(normalized_buy_event, 'paid_amount', 0)
    paid_fee = getattr(normalized_buy_event, 'paid_fee', 0)

    unit_price = Decimal(str(paid_amount))
    fees = Decimal(str(paid_fee))

    transaction = Transaction.create_buy(
        market_hash_name=market_hash_name,
        quantity=quantity,
        unit_price=unit_price,
        fees=fees,
        bot_name=bot_name,
        timestamp=timestamp,
        external_ref=external_ref,
    )

    return transaction


def project_acquisition_lot(
    normalized_buy_event: Any,
    transaction_projection_id: int,
    bot_name: str,
) -> AcquisitionLot:
    """
    Project a V0.5.9 normalized BUY event to a V0.5.0 AcquisitionLot.

    Args:
        normalized_buy_event: NormalizedEvent from steam_market_history_json
        transaction_projection_id: Temporary projection ID (NOT a real DB ID)
        bot_name: Bot name for the projection

    Returns:
        AcquisitionLot: V0.5.0 AcquisitionLot instance
    """
    if getattr(normalized_buy_event, 'event_type', None) != 'BUY':
        raise ValueError(f"Event type is not BUY: {normalized_buy_event.event_type}")

    acquired_at = getattr(normalized_buy_event, 'time_event', None)
    acquired_at = _validate_timestamp(acquired_at)

    # Parse quantity from asset_amount (same logic as project_transaction)
    asset_amount = getattr(normalized_buy_event, 'asset_amount', None)
    quantity = _parse_quantity(asset_amount)

    market_hash_name = getattr(normalized_buy_event, 'market_hash_name', '')
    if not isinstance(market_hash_name, str) or not market_hash_name.strip():
        raise ValueError("market_hash_name is missing for acquisition lot")

    if not isinstance(bot_name, str) or not bot_name.strip():
        raise ValueError("bot_name must be a non-empty string")

    acquisition_lot = AcquisitionLot(
        source_transaction_id=transaction_projection_id,
        market_hash_name=market_hash_name,
        bot_name=bot_name,
        original_quantity=quantity,
        remaining_quantity=quantity,
        unit_cost=None,
        acquired_at=acquired_at,
        cost_status=CostStatus.UNKNOWN,
    )

    return acquisition_lot


def dry_run_projection(
    normalized_buy_events: List[Any],
    bot_name: str,
) -> DryRunReport:
    """
    Perform a complete DRY-RUN projection of V0.5.9 normalized BUY events.

    Args:
        normalized_buy_events: List of NormalizedEvent objects
        bot_name: Bot name for the projection

    Returns:
        DryRunReport: Complete projection report
    """
    total_input_events = len(normalized_buy_events)
    valid_buy_events = 0
    unknown_events = 0
    invalid_events = 0
    duplicate_events = 0
    projected_transactions: List[Transaction] = []
    projected_acquisition_lots: List[Any] = []
    validation_errors: List[Dict[str, Any]] = []

    seen_external_refs: Dict[str, bool] = {}

    for i, event in enumerate(normalized_buy_events):
        try:
            if not hasattr(event, 'event_type'):
                validation_errors.append({
                    "index": i,
                    "error": "Missing required attributes",
                    "type": "validation_error",
                })
                invalid_events += 1
                continue

            event_type = getattr(event, 'event_type', None)
            market_hash_name = getattr(event, 'market_hash_name', None)
            listingid = getattr(event, 'listingid', None)
            purchaseid = getattr(event, 'purchaseid', None)
            timestamp = getattr(event, 'time_event', None)

            if event_type != 'BUY':
                unknown_events += 1
                continue

            if not market_hash_name:
                validation_errors.append({
                    "index": i,
                    "error": "market_hash_name is missing",
                    "type": "validation_error",
                })
                invalid_events += 1
                continue

            if not listingid or not purchaseid:
                validation_errors.append({
                    "index": i,
                    "error": "listingid or purchaseid is missing",
                    "type": "validation_error",
                })
                invalid_events += 1
                continue

            external_ref = f"{listingid}:{purchaseid}"
            if external_ref in seen_external_refs:
                duplicate_events += 1
                continue

            seen_external_refs[external_ref] = True

            transaction = project_transaction(event, bot_name)
            projected_transactions.append(transaction)

            # Keep the temporary projection ID outside the immutable Transaction.
            transaction_projection_id = i + 1
            acquisition_lot = project_acquisition_lot(
                event,
                transaction_projection_id,
                bot_name,
            )
            projected_acquisition_lots.append(acquisition_lot)

            valid_buy_events += 1

        except ValueError as e:
            validation_errors.append({
                "index": i,
                "error": str(e),
                "type": "validation_error",
            })
            invalid_events += 1
        except Exception as e:
            validation_errors.append({
                "index": i,
                "error": f"Unexpected error: {str(e)}",
                "type": "system_error",
            })
            invalid_events += 1

    return DryRunReport(
        total_input_events=total_input_events,
        valid_buy_events=valid_buy_events,
        unknown_events=unknown_events,
        invalid_events=invalid_events,
        duplicate_events=duplicate_events,
        projected_transactions=projected_transactions,
        projected_acquisition_lots=projected_acquisition_lots,
        validation_errors=validation_errors,
    )

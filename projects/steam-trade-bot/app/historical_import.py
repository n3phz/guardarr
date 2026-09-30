"""Deterministic import layer for historical BUY events.

This module provides an atomic batch import of historical BUY events
using the existing V0.5.0 domain and transaction-store modules.
The entire import runs in a single SQLite transaction. If any event
is invalid or causes a constraint violation (e.g. duplicate
external_ref), the whole import is rolled back and no data from this
import remains in the database.
"""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Tuple, Union

from transactions import (
    Transaction,
    TransactionValidationError,
    create_transaction,
)


def _validate_event(event: Dict[str, Any], idx: int) -> Tuple[bool, Union[Transaction, str]]:
    """Validate one event and construct a Transaction if valid.

    Returns (True, transaction) on success, or (False, error_message) on
    failure. No database writes are performed.
    """
    try:
        event_type = event.get("type", "BUY")
        if event_type != "BUY":
            raise TransactionValidationError("type must be BUY")

        transaction = create_transaction(
            type=event_type,
            market_hash_name=event.get("market_hash_name"),
            quantity=event.get("quantity"),
            unit_price=event.get("unit_price"),
            fees=event.get("fees", Decimal("0")),
            timestamp=event.get("timestamp"),
            bot_name=event.get("bot_name"),
            external_ref=event.get("external_ref"),
        )
        return True, transaction
    except (TransactionValidationError, ValueError) as exc:
        return False, str(exc)


def _insert_buy_with_lot_in_transaction(
    conn: sqlite3.Connection,
    transaction,
) -> Tuple[int, int]:
    """Insert a BUY transaction and its acquisition lot within an
    existing transaction (no BEGIN/COMMIT wrapper).

    This mirrors the logic of ``insert_buy_with_lot`` from
    ``app.transaction_store`` but assumes the caller has already
    started a transaction.
    """
    if transaction.type != "BUY":
        raise ValueError("insert_buy_with_lot requires a BUY transaction")

    cursor = conn.execute(
        """
        INSERT INTO transactions (
            type,
            market_hash_name,
            quantity,
            unit_price,
            fees,
            total_value,
            timestamp,
            bot_name,
            external_ref
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            transaction.type,
            transaction.market_hash_name,
            transaction.quantity,
            str(transaction.unit_price),
            str(transaction.fees),
            str(transaction.total_value),
            transaction.timestamp,
            transaction.bot_name,
            transaction.external_ref,
        ),
    )

    transaction_id = cursor.lastrowid
    if transaction_id is None:
        raise RuntimeError("failed to obtain transaction id")

    cursor = conn.execute(
        """
        INSERT INTO acquisition_lots (
            source_transaction_id,
            market_hash_name,
            bot_name,
            original_quantity,
            remaining_quantity,
            unit_cost,
            acquired_at,
            cost_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            transaction_id,
            transaction.market_hash_name,
            transaction.bot_name,
            transaction.quantity,
            transaction.quantity,
            str(transaction.unit_price),
            transaction.timestamp,
            "TRACKED",
        ),
    )

    lot_id = cursor.lastrowid
    if lot_id is None:
        raise RuntimeError("failed to obtain acquisition lot id")

    return transaction_id, lot_id


def import_historical_buys(
    conn: sqlite3.Connection,
    events: Iterable[Dict[str, Any]],
) -> Dict[str, Union[int, List[Dict[str, str]]]]:
    """Import one or more historical BUY events atomically.

    Each event mapping must contain at least the fields required by
    the domain transaction model: market_hash_name, quantity,
    unit_price, fees, timestamp, bot_name, and optional external_ref.
    Events with a type other than "BUY" will be rejected.

    The function validates every event using the existing transaction
    domain and persists each valid BUY via the existing economic-event
    / store path. The entire operation is atomic — if any event fails
    validation or causes a constraint violation, the whole import
    is rolled back and no data from this import remains in the
    database.

    Args:
        conn: SQLite connection with the V0.5.0 economic ledger schema.
        events: Iterable of event mappings to import.

    Returns:
        A dict with three keys:
            imported  — number of events successfully imported.
            rejected  — number of events that were rejected (invalid or
                        duplicate).
            errors     — list of error entries, each with "index" and "error".

    Raises:
        ValueError: If any event is invalid or causes a persistence error;
                    the exception message contains the list of errors.
    """
    event_list: List[Dict[str, Any]] = list(events)

    # Empty input is a valid, no-op return.
    if not event_list:
        return {"imported": 0, "rejected": 0, "errors": []}

    # Phase 1: Validate all events upfront using the domain validator.
    # This catches invalid type, quantity, unit_price, fees, etc.
    # without touching the database. Each valid event's Transaction
    # object is retained for Phase 2.
    validated_events: List[Tuple[Transaction, int]] = []
    error_list: List[Dict[str, str]] = []
    idx = 0

    for event in event_list:
        idx += 1
        ok, result = _validate_event(event, idx)
        if ok:
            validated_events.append((result, idx))
        else:
            error_list.append({"index": idx, "error": result})

    # If any validation failed, raise with collected errors — atomic rollback
    # (no DB writes have happened yet).
    if error_list:
        raise ValueError(error_list)

    # Phase 2: Persist all validated events in a single transaction.
    # This provides atomicity for the persistence phase.
    try:
        conn.execute("BEGIN")

        for transaction, event_idx in validated_events:
            _insert_buy_with_lot_in_transaction(conn, transaction)

        conn.commit()
    except sqlite3.IntegrityError as exc:
        # Duplicate external_ref or other constraint violation.
        conn.rollback()
        error_list.append({"index": event_idx, "error": str(exc)})
        raise ValueError(error_list) from exc
    except Exception:
        conn.rollback()
        raise

    return {"imported": len(validated_events), "rejected": 0, "errors": []}

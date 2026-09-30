"""Ingestion service for completed BUY economic events."""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from typing import Mapping, Tuple

from transactions import create_transaction, TransactionValidationError
from transaction_store import insert_buy_with_lot

BUY_TYPE = "BUY"


def ingest_completed_buy(
    conn: sqlite3.Connection,
    event: Mapping[str, object],
) -> Tuple[int, int]:
    """Ingest an already-confirmed external BUY event.

    Args:
        conn: SQLite connection with the V0.5.0 economic ledger schema.
        event: Mapping containing market_hash_name, quantity, unit_price,
            fees, timestamp, bot_name, optional external_ref, and optional type.

    Returns:
        A tuple of ``(transaction_id, acquisition_lot_id)``.

    Raises:
        TransactionValidationError: If the BUY event is invalid or the type is not BUY.
        sqlite3.IntegrityError: If a duplicate external_ref is inserted.
    """
    event_type = event.get("type", BUY_TYPE)
    if event_type != BUY_TYPE:
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
    return insert_buy_with_lot(conn, transaction)

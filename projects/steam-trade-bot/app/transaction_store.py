"""SQLite persistence for the V0.5.0 economic ledger."""

from __future__ import annotations

import sqlite3

from transactions import Transaction


def insert_buy_with_lot(
    conn: sqlite3.Connection,
    transaction: Transaction,
) -> tuple[int, int]:
    """Persist a BUY transaction and its acquisition lot atomically.

    Args:
        conn: SQLite connection used for the transaction.
        transaction: Authoritative BUY transaction to persist.

    Returns:
        A tuple of ``(transaction_id, acquisition_lot_id)``.

    Raises:
        ValueError: If ``transaction`` is not a BUY.
        RuntimeError: If the inserted row id cannot be obtained.
        Exception: Re-raises any persistence error after rolling back.
    """
    if transaction.type != "BUY":
        raise ValueError("insert_buy_with_lot requires a BUY transaction")

    try:
        conn.execute("BEGIN")

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

        transaction_id: int = cursor.lastrowid
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

        lot_id: int = cursor.lastrowid
        if lot_id is None:
            raise RuntimeError("failed to obtain acquisition lot id")

        conn.commit()
        return transaction_id, lot_id

    except Exception:
        conn.rollback()
        raise


def read_transaction(
    conn: sqlite3.Connection,
    transaction_id: int,
) -> sqlite3.Row | None:
    """Read a persisted transaction by id.

    Args:
        conn: SQLite connection used for the query.
        transaction_id: Primary key of the transaction.

    Returns:
        The persisted row, or ``None`` if not found.
    """
    return conn.execute(
        """
        SELECT
            id,
            type,
            market_hash_name,
            quantity,
            unit_price,
            fees,
            total_value,
            timestamp,
            bot_name,
            external_ref
        FROM transactions
        WHERE id = ?
        """,
        (transaction_id,),
    ).fetchone()


def read_acquisition_lot(
    conn: sqlite3.Connection,
    lot_id: int,
) -> sqlite3.Row | None:
    """Read a persisted acquisition lot by id.

    Args:
        conn: SQLite connection used for the query.
        lot_id: Primary key of the acquisition lot.

    Returns:
        The persisted row, or ``None`` if not found.
    """
    return conn.execute(
        """
        SELECT
            id,
            source_transaction_id,
            market_hash_name,
            bot_name,
            original_quantity,
            remaining_quantity,
            unit_cost,
            acquired_at,
            cost_status
        FROM acquisition_lots
        WHERE id = ?
        """,
        (lot_id,),
    ).fetchone()

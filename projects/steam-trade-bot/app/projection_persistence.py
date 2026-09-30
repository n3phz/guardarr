"""V0.6.2 atomic persistence for V0.6.1 dry-run BUY projections.

This module is explicitly invoked by tests or a future import command. It is
not imported by the production startup path and does not open a database
connection itself.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from collections.abc import Sequence
from typing import Any, Dict, List, Tuple

from buy_projection import DryRunReport
from transactions import (
    AcquisitionLot,
    CostStatus,
    Transaction,
    TransactionType,
)


@dataclass(frozen=True)
class PersistenceReport:
    """Result of an atomic V0.6.2 persistence operation."""

    attempted: int
    inserted_transactions: int
    inserted_lots: int
    skipped_duplicates: int
    errors: List[Dict[str, Any]]


class ProjectionPersistenceError(ValueError):
    """Raised when a projection cannot be persisted consistently."""

    def __init__(self, message: str, report: PersistenceReport) -> None:
        super().__init__(message)
        self.report = report


def create_schema(conn: sqlite3.Connection) -> None:
    """Create the current V0.5.0 ledger schema in a caller-owned database.

    This helper is intended for isolated tests. It executes DDL only against
    the supplied connection and never opens or discovers a production DB.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL CHECK(type IN ('BUY', 'SELL')),
            market_hash_name TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            unit_price TEXT NOT NULL,
            fees TEXT NOT NULL DEFAULT '0',
            total_value TEXT NOT NULL DEFAULT '0',
            timestamp TEXT NOT NULL,
            bot_name TEXT NOT NULL,
            external_ref TEXT
        );

        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_transactions_bot_external_ref
        ON transactions(bot_name, external_ref)
        WHERE external_ref IS NOT NULL;

        CREATE TABLE IF NOT EXISTS acquisition_lots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_transaction_id INTEGER NOT NULL,
            market_hash_name TEXT NOT NULL,
            bot_name TEXT NOT NULL,
            original_quantity INTEGER NOT NULL CHECK(original_quantity > 0),
            remaining_quantity INTEGER NOT NULL
                CHECK(
                    remaining_quantity >= 0
                    AND remaining_quantity <= original_quantity
                ),
            unit_cost TEXT,
            acquired_at TEXT NOT NULL,
            cost_status TEXT NOT NULL
                CHECK(cost_status IN ('TRACKED', 'UNKNOWN')),
            FOREIGN KEY(source_transaction_id)
                REFERENCES transactions(id)
        );
        """
    )
    conn.commit()


def _decimal_equal(stored: Any, expected: Decimal) -> bool:
    try:
        return Decimal(stored) == expected
    except (InvalidOperation, TypeError, ValueError):
        return False


def _validate_report_pairs(
    report: DryRunReport,
) -> List[Tuple[Transaction, AcquisitionLot]]:
    """Validate the complete batch before opening a write transaction."""
    if not isinstance(report, DryRunReport):
        raise TypeError("report must be a DryRunReport")

    transactions = report.projected_transactions
    lots = report.projected_acquisition_lots
    if len(transactions) != len(lots):
        raise ProjectionPersistenceError(
            "DryRunReport transaction and acquisition-lot counts differ",
            PersistenceReport(
                attempted=len(transactions),
                inserted_transactions=0,
                inserted_lots=0,
                skipped_duplicates=0,
                errors=[
                    {
                        "error": (
                            "projected transaction and acquisition-lot "
                            "counts differ"
                        )
                    }
                ],
            ),
        )

    pairs: List[Tuple[Transaction, AcquisitionLot]] = []
    seen_external_refs = set()

    for index, (transaction, lot) in enumerate(zip(transactions, lots)):
        if not isinstance(transaction, Transaction):
            raise ProjectionPersistenceError(
                f"Projected item {index} is not a Transaction",
                PersistenceReport(
                    attempted=len(transactions),
                    inserted_transactions=0,
                    inserted_lots=0,
                    skipped_duplicates=0,
                    errors=[
                        {"index": index, "error": "not a Transaction object"}
                    ],
                ),
            )
        if not isinstance(lot, AcquisitionLot):
            raise ProjectionPersistenceError(
                f"Projected item {index} is not an AcquisitionLot",
                PersistenceReport(
                    attempted=len(transactions),
                    inserted_transactions=0,
                    inserted_lots=0,
                    skipped_duplicates=0,
                    errors=[
                        {"index": index, "error": "not an AcquisitionLot object"}
                    ],
                ),
            )
        if transaction.type is not TransactionType.BUY:
            raise ProjectionPersistenceError(
                f"Projected item {index} is not a BUY transaction",
                PersistenceReport(
                    attempted=len(transactions),
                    inserted_transactions=0,
                    inserted_lots=0,
                    skipped_duplicates=0,
                    errors=[
                        {"index": index, "error": "transaction type is not BUY"}
                    ],
                ),
            )
        if transaction.id is not None:
            raise ProjectionPersistenceError(
                f"Projected item {index} already has a database transaction ID",
                PersistenceReport(
                    attempted=len(transactions),
                    inserted_transactions=0,
                    inserted_lots=0,
                    skipped_duplicates=0,
                    errors=[
                        {"index": index, "error": "transaction ID is already set"}
                    ],
                ),
            )
        if lot.id is not None:
            raise ProjectionPersistenceError(
                f"Projected item {index} already has a database lot ID",
                PersistenceReport(
                    attempted=len(transactions),
                    inserted_transactions=0,
                    inserted_lots=0,
                    skipped_duplicates=0,
                    errors=[
                        {"index": index, "error": "acquisition-lot ID is already set"}
                    ],
                ),
            )
        if not isinstance(transaction.external_ref, str) or not transaction.external_ref:
            raise ProjectionPersistenceError(
                f"Projected item {index} has no external_ref",
                PersistenceReport(
                    attempted=len(transactions),
                    inserted_transactions=0,
                    inserted_lots=0,
                    skipped_duplicates=0,
                    errors=[{"index": index, "error": "external_ref is missing"}],
                ),
            )
        if transaction.external_ref in seen_external_refs:
            raise ProjectionPersistenceError(
                f"Duplicate external_ref within one batch: {transaction.external_ref}",
                PersistenceReport(
                    attempted=len(transactions),
                    inserted_transactions=0,
                    inserted_lots=0,
                    skipped_duplicates=0,
                    errors=[
                        {
                            "index": index,
                            "external_ref": transaction.external_ref,
                            "error": "duplicate external_ref within batch",
                        }
                    ],
                ),
            )
        seen_external_refs.add(transaction.external_ref)

        if lot.cost_status is not CostStatus.UNKNOWN:
            raise ProjectionPersistenceError(
                f"Projected item {index} must use UNKNOWN cost status",
                PersistenceReport(
                    attempted=len(transactions),
                    inserted_transactions=0,
                    inserted_lots=0,
                    skipped_duplicates=0,
                    errors=[
                        {"index": index, "error": "cost_status is not UNKNOWN"}
                    ],
                ),
            )
        if lot.unit_cost is not None:
            raise ProjectionPersistenceError(
                f"Projected item {index} has a non-NULL unit_cost",
                PersistenceReport(
                    attempted=len(transactions),
                    inserted_transactions=0,
                    inserted_lots=0,
                    skipped_duplicates=0,
                    errors=[
                        {"index": index, "error": "unit_cost must be None"}
                    ],
                ),
            )
        if not isinstance(lot.source_transaction_id, int) or lot.source_transaction_id <= 0:
            raise ProjectionPersistenceError(
                f"Projected item {index} has an invalid temporary source ID",
                PersistenceReport(
                    attempted=len(transactions),
                    inserted_transactions=0,
                    inserted_lots=0,
                    skipped_duplicates=0,
                    errors=[
                        {"index": index, "error": "temporary source ID is invalid"}
                    ],
                ),
            )

        if (
            lot.market_hash_name != transaction.market_hash_name
            or lot.bot_name != transaction.bot_name
            or lot.original_quantity != transaction.quantity
            or lot.remaining_quantity != transaction.quantity
            or lot.acquired_at != transaction.timestamp
        ):
            raise ProjectionPersistenceError(
                f"Projected transaction and lot differ for {transaction.external_ref}",
                PersistenceReport(
                    attempted=len(transactions),
                    inserted_transactions=0,
                    inserted_lots=0,
                    skipped_duplicates=0,
                    errors=[
                        {
                            "index": index,
                            "external_ref": transaction.external_ref,
                            "error": "projected transaction and lot fields differ",
                        }
                    ],
                ),
            )

        pairs.append((transaction, lot))

    return pairs


# Column positions from: SELECT id, type, market_hash_name, quantity, unit_price, fees,
#                       total_value, timestamp, bot_name, external_ref FROM transactions
_TRANSACTION_COL_ID = 0
_TRANSACTION_COL_TYPE = 1
_TRANSACTION_COL_MARKET_HASH_NAME = 2
_TRANSACTION_COL_QUANTITY = 3
_TRANSACTION_COL_UNIT_PRICE = 4
_TRANSACTION_COL_FEES = 5
_TRANSACTION_COL_TOTAL_VALUE = 6
_TRANSACTION_COL_TIMESTAMP = 7
_TRANSACTION_COL_BOT_NAME = 8
_TRANSACTION_COL_EXTERNAL_REF = 9


def _get_field(row: Sequence[Any], index: int) -> Any:
    """Return a selected column from either tuple or sqlite3.Row rows."""
    return tuple(row)[index]


def _transactions_match(row, transaction: Transaction) -> bool:
    return (
        _get_field(row, _TRANSACTION_COL_TYPE) == transaction.type.value
        and _get_field(row, _TRANSACTION_COL_MARKET_HASH_NAME) == transaction.market_hash_name
        and _get_field(row, _TRANSACTION_COL_QUANTITY) == transaction.quantity
        and _decimal_equal(_get_field(row, _TRANSACTION_COL_UNIT_PRICE), transaction.unit_price)
        and _decimal_equal(_get_field(row, _TRANSACTION_COL_FEES), transaction.fees)
        and _decimal_equal(_get_field(row, _TRANSACTION_COL_TOTAL_VALUE), transaction.total_value)
        and _get_field(row, _TRANSACTION_COL_TIMESTAMP) == transaction.timestamp
        and _get_field(row, _TRANSACTION_COL_BOT_NAME) == transaction.bot_name
        and _get_field(row, _TRANSACTION_COL_EXTERNAL_REF) == transaction.external_ref
    )


# Column positions from: SELECT id, source_transaction_id, market_hash_name, bot_name,
#                       original_quantity, remaining_quantity, unit_cost, acquired_at, cost_status
#                       FROM acquisition_lots WHERE source_transaction_id = ? ORDER BY id
_LOT_COL_MARKET_HASH_NAME = 2
_LOT_COL_BOT_NAME = 3
_LOT_COL_ORIGINAL_QUANTITY = 4
_LOT_COL_REMAINING_QUANTITY = 5
_LOT_COL_UNIT_COST = 6
_LOT_COL_ACQUIRED_AT = 7
_LOT_COL_COST_STATUS = 8


def _lot_matches(row, transaction: Transaction, projected_lot: AcquisitionLot) -> bool:
    return (
        _get_field(row, _LOT_COL_MARKET_HASH_NAME) == transaction.market_hash_name
        and _get_field(row, _LOT_COL_BOT_NAME) == transaction.bot_name
        and _get_field(row, _LOT_COL_ORIGINAL_QUANTITY) == transaction.quantity
        and _get_field(row, _LOT_COL_REMAINING_QUANTITY) == transaction.quantity
        and _get_field(row, _LOT_COL_UNIT_COST) is None
        and _get_field(row, _LOT_COL_ACQUIRED_AT) == transaction.timestamp
        and _get_field(row, _LOT_COL_COST_STATUS) == CostStatus.UNKNOWN.value
        and _get_field(row, _LOT_COL_ORIGINAL_QUANTITY) == projected_lot.original_quantity
        and _get_field(row, _LOT_COL_REMAINING_QUANTITY) == projected_lot.remaining_quantity
    )


def _find_transaction(
    conn: sqlite3.Connection,
    transaction: Transaction,
) -> tuple[Any, ...] | None:
    return conn.execute(
        """
        SELECT id, type, market_hash_name, quantity, unit_price, fees,
               total_value, timestamp, bot_name, external_ref
        FROM transactions
        WHERE bot_name = ? AND external_ref = ?
        LIMIT 1
        """,
        (transaction.bot_name, transaction.external_ref),
    ).fetchone()


def _find_lots(
    conn: sqlite3.Connection,
    transaction_id: int,
) -> List[Sequence[Any]]:
    return list(
        conn.execute(
            """
            SELECT id, source_transaction_id, market_hash_name, bot_name,
                   original_quantity, remaining_quantity, unit_cost,
                   acquired_at, cost_status
            FROM acquisition_lots
            WHERE source_transaction_id = ?
            ORDER BY id
            """,
            (transaction_id,),
        ).fetchall()
    )


def _validate_existing_state(
    conn: sqlite3.Connection,
    transaction: Transaction,
    projected_lot: AcquisitionLot,
) -> bool:
    """Return True for a consistent duplicate, otherwise raise explicitly."""
    existing = _find_transaction(conn, transaction)
    if existing is None:
        return False

    if not _transactions_match(existing, transaction):
        raise ProjectionPersistenceError(
            "Conflicting existing state for "
            f"bot={transaction.bot_name} external_ref={transaction.external_ref}: "
            "existing transaction data differs from projection",
            PersistenceReport(
                attempted=0,
                inserted_transactions=0,
                inserted_lots=0,
                skipped_duplicates=0,
                errors=[
                    {
                        "external_ref": transaction.external_ref,
                        "error": "conflicting existing transaction",
                    }
                ],
            ),
        )

    lots = _find_lots(conn, existing[0])
    if len(lots) != 1:
        state = "missing" if not lots else "duplicated"
        raise ProjectionPersistenceError(
            "Inconsistent existing state for "
            f"bot={transaction.bot_name} external_ref={transaction.external_ref}: "
            f"acquisition lot is {state}",
            PersistenceReport(
                attempted=0,
                inserted_transactions=0,
                inserted_lots=0,
                skipped_duplicates=0,
                errors=[
                    {
                        "external_ref": transaction.external_ref,
                        "error": f"acquisition lot is {state}",
                    }
                ],
            ),
        )

    if not _lot_matches(lots[0], transaction, projected_lot):
        raise ProjectionPersistenceError(
            "Inconsistent existing state for "
            f"bot={transaction.bot_name} external_ref={transaction.external_ref}: "
            "existing acquisition lot differs from UNKNOWN-cost projection",
            PersistenceReport(
                attempted=0,
                inserted_transactions=0,
                inserted_lots=0,
                skipped_duplicates=0,
                errors=[
                    {
                        "external_ref": transaction.external_ref,
                        "error": "inconsistent existing acquisition lot",
                    }
                ],
            ),
        )

    return True


def _insert_transaction(
    conn: sqlite3.Connection,
    transaction: Transaction,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO transactions (
            type, market_hash_name, quantity, unit_price, fees,
            total_value, timestamp, bot_name, external_ref
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            transaction.type.value,
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
        raise RuntimeError("failed to obtain transaction ID")
    return transaction_id


def _insert_acquisition_lot(
    conn: sqlite3.Connection,
    transaction_id: int,
    transaction: Transaction,
    projected_lot: AcquisitionLot,
) -> None:
    """Persist a projected lot with its real DB source transaction ID."""
    conn.execute(
        """
        INSERT INTO acquisition_lots (
            source_transaction_id, market_hash_name, bot_name,
            original_quantity, remaining_quantity, unit_cost,
            acquired_at, cost_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            transaction_id,  # replaces the temporary dry-run source ID
            transaction.market_hash_name,
            transaction.bot_name,
            projected_lot.original_quantity,
            projected_lot.remaining_quantity,
            None,  # UNKNOWN historical cost
            transaction.timestamp,
            CostStatus.UNKNOWN.value,
        ),
    )


def persist_projection(
    report: DryRunReport,
    conn: sqlite3.Connection,
) -> PersistenceReport:
    """Atomically persist a V0.6.1 report into a caller-owned SQLite DB.

    The caller supplies the connection, which may point only to an explicitly
    selected isolated database. This function never opens a connection or
    imports the production startup path.
    """
    pairs = _validate_report_pairs(report)
    attempted = len(pairs)

    if attempted == 0:
        return PersistenceReport(
            attempted=0,
            inserted_transactions=0,
            inserted_lots=0,
            skipped_duplicates=0,
            errors=[],
        )
    if conn.in_transaction:
        raise ProjectionPersistenceError(
            "SQLite connection already has an active transaction",
            PersistenceReport(
                attempted=attempted,
                inserted_transactions=0,
                inserted_lots=0,
                skipped_duplicates=0,
                errors=[{"error": "connection already has an active transaction"}],
            ),
        )

    inserted_transactions = 0
    inserted_lots = 0
    skipped_duplicates = 0

    try:
        conn.execute("BEGIN IMMEDIATE")

        for transaction, projected_lot in pairs:
            if _validate_existing_state(conn, transaction, projected_lot):
                skipped_duplicates += 1
                continue

            transaction_id = _insert_transaction(conn, transaction)
            inserted_transactions += 1
            try:
                _insert_acquisition_lot(
                    conn,
                    transaction_id,
                    transaction,
                    projected_lot,
                )
                inserted_lots += 1
            except Exception:
                # A transaction without its lot must never become visible.
                conn.rollback()
                raise

        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        if isinstance(exc, ProjectionPersistenceError):
            raise
        raise ProjectionPersistenceError(
            f"Atomic persistence failed: {exc}",
            PersistenceReport(
                attempted=attempted,
                inserted_transactions=inserted_transactions,
                inserted_lots=inserted_lots,
                skipped_duplicates=skipped_duplicates,
                errors=[{"error": str(exc)}],
            ),
        ) from exc

    return PersistenceReport(
        attempted=attempted,
        inserted_transactions=inserted_transactions,
        inserted_lots=inserted_lots,
        skipped_duplicates=skipped_duplicates,
        errors=[],
    )


__all__ = [
    "PersistenceReport",
    "ProjectionPersistenceError",
    "create_schema",
    "persist_projection",
]

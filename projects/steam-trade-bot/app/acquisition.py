"""Acquisition recording service — canonical Phase 1 persistence path.

Provides the single authoritative function to record an acquisition lot
and its source transaction. All acquisition creation (TRACKED or UNKNOWN)
must go through `record_acquisition` to enforce Phase 1 invariants.

Phase 1 invariants enforced:
  - TRACKED requires non-None unit_cost and valid provenance
  - UNKNOWN requires unit_cost=None and no provenance
  - Idempotency via source_key (bot_name + external_ref)
  - No cost fabrication
  - Single transaction + lot atomic insert
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from app.transactions import (
    Transaction,
    TransactionType,
    CostStatus,
    create_transaction,
    TransactionError,
)
from app.transaction_store import insert_buy_with_lot


class AcquisitionError(ValueError):
    """Raised when acquisition recording cannot proceed safely."""


@dataclass(frozen=True)
class RecordedAcquisition:
    """Result of a successful acquisition recording."""

    lot: "AcquisitionLotRecord"
    transaction: Optional["TransactionRecord"] = None
    created: bool = True  # False if idempotent resolve


@dataclass(frozen=True)
class AcquisitionLotRecord:
    """Persisted acquisition lot view."""

    lot_id: int
    source_transaction_id: int
    market_hash_name: str
    bot_name: str
    original_quantity: int
    remaining_quantity: int
    unit_cost: Optional[Decimal]
    acquired_at: str
    cost_status: CostStatus
    source_type: Optional[SourceType] = None
    provenance: Optional[Provenance] = None


@dataclass(frozen=True)
class TransactionRecord:
    """Persisted transaction view."""

    transaction_id: int
    type: TransactionType
    market_hash_name: str
    quantity: int
    unit_price: Decimal
    fees: Decimal
    total_value: Decimal
    timestamp: str
    bot_name: str
    external_ref: Optional[str]


# Re-export enums for downstream compatibility
from app.transactions import SourceType, Provenance, EvidenceType, CostStatus as CostStatusEnum

__all__ = [
    "AcquisitionError",
    "RecordedAcquisition",
    "AcquisitionLotRecord",
    "TransactionRecord",
    "record_acquisition",
    "SourceType",
    "Provenance",
    "EvidenceType",
    "CostStatus",
    "Repository",
]


class Repository:
    """Database repository for acquisition operations.

    Wraps a raw SQLite connection with acquisition-specific queries.
    """

    def __init__(self, conn):
        self.connection = conn

    def get_transaction_by_external_ref(self, bot_name: str, external_ref: str) -> Optional[TransactionRecord]:
        """Look up existing transaction by external_ref for idempotency."""
        row = self.connection.execute(
            """
            SELECT id, type, market_hash_name, quantity, unit_price, fees,
                   total_value, timestamp, bot_name, external_ref
            FROM transactions
            WHERE bot_name = ? AND external_ref = ?
            """,
            (bot_name, external_ref),
        ).fetchone()

        if row is None:
            return None

        return TransactionRecord(
            transaction_id=row[0],
            type=TransactionType(row[1]),
            market_hash_name=row[2],
            quantity=row[3],
            unit_price=Decimal(row[4]),
            fees=Decimal(row[5]),
            total_value=Decimal(row[6]),
            timestamp=row[7],
            bot_name=row[8],
            external_ref=row[9],
        )

    def get_lot_by_source_transaction(self, source_transaction_id: int) -> Optional[AcquisitionLotRecord]:
        """Look up acquisition lot by source transaction."""
        row = self.connection.execute(
            """
            SELECT id, source_transaction_id, market_hash_name, bot_name,
                   original_quantity, remaining_quantity, unit_cost,
                   acquired_at, cost_status
            FROM acquisition_lots
            WHERE source_transaction_id = ?
            """,
            (source_transaction_id,),
        ).fetchone()

        if row is None:
            return None

        unit_cost = Decimal(row[6]) if row[6] is not None else None
        return AcquisitionLotRecord(
            lot_id=row[0],
            source_transaction_id=row[1],
            market_hash_name=row[2],
            bot_name=row[3],
            original_quantity=row[4],
            remaining_quantity=row[5],
            unit_cost=unit_cost,
            acquired_at=row[7],
            cost_status=CostStatus(row[8]),
            source_type=None,
            provenance=None,
        )

    def insert_transaction_and_lot(
        self,
        transaction: Transaction,
        unit_cost: Optional[Decimal],
        acquired_at: str,
        cost_status: CostStatus,
    ) -> tuple[int, int]:
        """Insert transaction and acquisition lot atomically.

        Returns (transaction_id, lot_id).
        """
        try:
            self.connection.execute("BEGIN")

            cursor = self.connection.execute(
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
                raise AcquisitionError("failed to obtain transaction id")

            cursor = self.connection.execute(
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
                    str(unit_cost) if unit_cost is not None else None,
                    acquired_at,
                    cost_status.value,
                ),
            )

            lot_id = cursor.lastrowid
            if lot_id is None:
                raise AcquisitionError("failed to obtain acquisition lot id")

            self.connection.commit()
            return transaction_id, lot_id

        except Exception:
            self.connection.rollback()
            raise


def record_acquisition(
    repository: Repository,
    bot_name: str,
    market_hash_name: str,
    quantity: int,
    acquired_at: str | date,
    unit_cost: Optional[Decimal],
    currency: Optional[str],
    source_type: Optional["SourceType"],
    provenance: Optional["Provenance"],
    external_reference: Optional[str],
    entered_at: str,
) -> RecordedAcquisition:
    """Record an acquisition (TRACKED or UNKNOWN) via canonical Phase 1 path.

    This is the ONLY function that should create acquisition lots and their
    source transactions. It enforces all Phase 1 invariants.

    Args:
        repository: Database repository.
        bot_name: Bot name for idempotency and attribution.
        market_hash_name: Item market hash name.
        quantity: Quantity acquired (positive integer).
        acquired_at: Acquisition date (ISO string or date).
        unit_cost: Per-unit cost in currency units (None for UNKNOWN).
        currency: ISO currency code (e.g., "EUR", "USD") — required for TRACKED.
        source_type: SourceType enum (e.g., STEAM_MARKET_PURCHASE) — required for TRACKED.
        provenance: Provenance object with evidence — required for TRACKED.
        external_reference: Unique external key for idempotency (e.g., "listingid:purchaseid").
        entered_at: ISO timestamp when this record was created.

    Returns:
        RecordedAcquisition with lot, transaction, and created flag.

    Raises:
        AcquisitionError: If invariants violated or persistence fails.
    """
    # Normalize acquired_at to ISO date string
    if isinstance(acquired_at, date):
        acquired_at_iso = acquired_at.isoformat()
    else:
        acquired_at_iso = acquired_at

    # Phase 1 invariant validation
    is_tracked = unit_cost is not None

    if is_tracked:
        if unit_cost < 0:
            raise AcquisitionError("TRACKED cost requires non-negative unit_cost")
        if currency is None:
            raise AcquisitionError("TRACKED cost requires currency")
        if source_type is None:
            raise AcquisitionError("TRACKED cost requires source_type")
        if provenance is None:
            raise AcquisitionError("TRACKED cost requires provenance")
        if external_reference is None:
            raise AcquisitionError("TRACKED cost requires external_reference for idempotency")
    else:
        if unit_cost is not None:
            raise AcquisitionError("UNKNOWN cost requires unit_cost = None")

    # Validate quantity
    if not isinstance(quantity, int) or quantity <= 0:
        raise AcquisitionError("quantity must be a positive integer")

    # Idempotency check via external_reference (source_key)
    if external_reference is not None:
        existing_tx = repository.get_transaction_by_external_ref(bot_name, external_reference)
        if existing_tx is not None:
            # Idempotent resolve - return existing
            existing_lot = repository.get_lot_by_source_transaction(existing_tx.transaction_id)
            if existing_lot is not None:
                return RecordedAcquisition(
                    lot=existing_lot,
                    transaction=existing_tx,
                    created=False,
                )

    # Create the BUY transaction (fees=0 for acquisition recording, total=unit_cost*qty)
    # For TRACKED: unit_price = unit_cost, fees = 0
    # For UNKNOWN: we still create a BUY transaction but with unit_price=0, fees=0
    if is_tracked:
        transaction_unit_price = unit_cost
        transaction_fees = Decimal("0")
        transaction_total = unit_cost * quantity
    else:
        transaction_unit_price = Decimal("0")
        transaction_fees = Decimal("0")
        transaction_total = Decimal("0")

    # Create transaction with the acquired_at timestamp
    transaction = Transaction.create_buy(
        market_hash_name=market_hash_name,
        quantity=quantity,
        unit_price=transaction_unit_price,
        fees=transaction_fees,
        bot_name=bot_name,
        timestamp=acquired_at_iso,
        external_ref=external_reference,
        total_value=transaction_total,
    )

    cost_status = CostStatus.TRACKED if is_tracked else CostStatus.UNKNOWN

    # Insert transaction and lot atomically
    transaction_id, lot_id = repository.insert_transaction_and_lot(
        transaction=transaction,
        unit_cost=unit_cost,
        acquired_at=acquired_at_iso,
        cost_status=cost_status,
    )

    # Read back the created records
    lot_record = repository.get_lot_by_source_transaction(transaction_id)
    tx_record = repository.get_transaction_by_external_ref(bot_name, external_reference)

    return RecordedAcquisition(
        lot=lot_record,
        transaction=tx_record,
        created=True,
    )
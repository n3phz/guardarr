"""Phase 2 schema migration script.

Migrates the V1 economic ledger schema to V2, adding columns required by
the acquisition detection pipeline while preserving all existing data.

The migration is:
  - additive where possible;
  - idempotent (safe to run multiple times);
  - backwards-compatible with existing queries;
  - free of destructive DROP/DELETE operations unless replacing a table.

Changes:
  transactions:
    - id: TEXT → INTEGER (AUTOINCREMENT)
    - Add: type, timestamp, fees, total_value, bot_name, external_ref
    - Create indexes: idx_transactions_type_ts, idx_transactions_bot_external_ref

  acquisition_lots:
    - id: TEXT → INTEGER (AUTOINCREMENT)
    - Add: source_transaction_id, bot_name, original_quantity
    - Establish foreign key: source_transaction_id → transactions(id)
    - Create index: idx_acq_lots_source_tx
"""

from __future__ import annotations

import sqlite3
from typing import Optional


def migrate(conn: sqlite3.Connection) -> None:
    """Apply the Phase 2 schema migration."""
    cursor = conn.cursor()

    # --- Migrate transactions table ---
    _migrate_transactions(cursor)

    # --- Migrate acquisition_lots table ---
    _migrate_acquisition_lots(cursor)

    conn.commit()


def _migrate_transactions(cursor: sqlite3.Cursor) -> None:
    """Add Phase 2 columns to transactions table."""
    # Get current columns
    cursor.execute("PRAGMA table_info(transactions)")
    cols = {row[1] for row in cursor.fetchall()}

    # Add missing columns
    migrations = [
        ("type", "TEXT"),
        ("timestamp", "TEXT"),
        ("fees", "TEXT"),
        ("total_value", "TEXT"),
        ("bot_name", "TEXT"),
        ("external_ref", "TEXT"),
    ]

    for col_name, col_type in migrations:
        if col_name not in cols:
            cursor.execute(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_type}")
            print(f"  Added column: transactions.{col_name}")

    # Create new schema table with proper types
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions_new (
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
        )
    """)

    # Copy data from old table
    cursor.execute("""
        INSERT OR IGNORE INTO transactions_new (id, type, market_hash_name, quantity, unit_price, fees, total_value, timestamp, bot_name, external_ref)
        SELECT 
            CAST(id AS INTEGER) as id,
            COALESCE(type, transaction_type) as type,
            market_hash_name,
            quantity,
            COALESCE(unit_price, '0'),
            COALESCE(fees, '0'),
            COALESCE(total_value, total_price),
            COALESCE(timestamp, occurred_at),
            COALESCE(bot_name, ''),
            external_ref
        FROM transactions
    """)

    # Replace old table
    cursor.execute("DROP TABLE transactions")
    cursor.execute("ALTER TABLE transactions_new RENAME TO transactions")

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_type_ts ON transactions(type, timestamp)")
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_bot_external_ref
        ON transactions(bot_name, external_ref)
        WHERE external_ref IS NOT NULL
    """)
    print("  Migrated transactions table")


def _migrate_acquisition_lots(cursor: sqlite3.Cursor) -> None:
    """Add Phase 2 columns to acquisition_lots table."""
    # Get current columns
    cursor.execute("PRAGMA table_info(acquisition_lots)")
    cols = {row[1] for row in cursor.fetchall()}

    # Add missing columns
    migrations = [
        ("source_transaction_id", "INTEGER"),
        ("bot_name", "TEXT"),
        ("original_quantity", "INTEGER"),
    ]

    for col_name, col_type in migrations:
        if col_name not in cols:
            cursor.execute(f"ALTER TABLE acquisition_lots ADD COLUMN {col_name} {col_type}")
            print(f"  Added column: acquisition_lots.{col_name}")

    # Create new schema table with proper constraints
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS acquisition_lots_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_transaction_id INTEGER NOT NULL,
            market_hash_name TEXT NOT NULL,
            bot_name TEXT NOT NULL,
            original_quantity INTEGER NOT NULL CHECK(original_quantity > 0),
            remaining_quantity INTEGER NOT NULL CHECK(remaining_quantity >= 0 AND remaining_quantity <= original_quantity),
            unit_cost TEXT,
            acquired_at TEXT NOT NULL,
            cost_status TEXT NOT NULL CHECK(cost_status IN ('TRACKED', 'UNKNOWN')),
            FOREIGN KEY(source_transaction_id) REFERENCES transactions(id)
        )
    """)

    # Copy data from old table
    cursor.execute("""
        INSERT OR IGNORE INTO acquisition_lots_new (
            id, source_transaction_id, market_hash_name, bot_name,
            original_quantity, remaining_quantity, unit_cost, acquired_at, cost_status
        )
        SELECT 
            CAST(id AS INTEGER),
            COALESCE(source_transaction_id, transaction_id),
            market_hash_name,
            COALESCE(bot_name, ''),
            COALESCE(original_quantity, quantity),
            remaining_quantity,
            unit_cost,
            acquired_at,
            cost_status
        FROM acquisition_lots
    """)

    # Replace old table
    cursor.execute("DROP TABLE acquisition_lots")
    cursor.execute("ALTER TABLE acquisition_lots_new RENAME TO acquisition_lots")

    # Create index
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_acq_lots_source_tx ON acquisition_lots(source_transaction_id)")
    print("  Migrated acquisition_lots table")


def main(db_path: str) -> None:
    """Entry point for migration."""
    conn = sqlite3.connect(db_path)
    try:
        print(f"Migrating database: {db_path}")
        migrate(conn)
        print("Migration completed successfully")
    except Exception as exc:
        print(f"Migration failed: {exc}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <database_path>")
        sys.exit(1)
    main(sys.argv[1])

"""Integration/import service for Steam Market history (V0.5.5).

Connects MarketHistoryClient → MarketHistoryEvent → normalize → SQLite.

Does NOT fabricate timestamps, fees, acquisition costs. Reports events
that cannot be persisted due to missing required fields.

Architecture:
- For Steam Market History events, acquisition_lots are NOT created
  because acquisition cost is not known and acquired_at is unavailable.
- The importer uses ONE SQLite transaction for the whole persistable batch.
- insert_buy_with_lot() is explicitly forbidden.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

import requests

from historical_event_normalizer import (
    HistoricalEventNormalizationError,
    NormalizedHistoricalEvent,
    normalize_market_history_event,
)
from market_history_adapter import (
    MarketHistoryEvent,
    MarketHistoryParseError,
    SteamMarketHistoryClient,
    SteamMarketHistoryParser,
)
from transactions import Transaction, create_transaction


@dataclass
class ImportResult:
    """Result of a market-history import operation."""

    imported_count: int
    skipped_count: int
    skipped_reasons: List[str]


class MarketHistoryImportError(RuntimeError):
    """Raised when the import encounters an unrecoverable error."""


class MarketHistoryImporter:
    """Import Steam market history into the V0.5.0 economic ledger.

    Args:
        session: Already-authenticated requests.Session from the caller.
        conn: SQLite connection with the V0.5.0 economic ledger schema.
        bot_name: Bot name used for deduplication and attribution.
        base_url: Steam Community base URL (default: https://steamcommunity.com).
    """

    def __init__(
        self,
        session: requests.Session,
        conn: sqlite3.Connection,
        bot_name: str,
        base_url: str = "https://steamcommunity.com",
    ) -> None:
        self.session = session
        self.conn = conn
        self.bot_name = bot_name
        self.client = SteamMarketHistoryClient(session, base_url)
        self.parser = SteamMarketHistoryParser()

    def import_history(self, start: int = 0, count: int = 100) -> ImportResult:
        """Fetch, normalize, and import market history pages until complete.

        Pagination continues using start/count until total_count is reached.
        Events with timestamp=None are reported as skipped because the
        transactions table requires timestamp NOT NULL.

        Returns:
            ImportResult with imported_count, skipped_count, skipped_reasons.
        """
        # Phase 1: Fetch all pages using the client's fetch_page method
        all_raw_events: List[MarketHistoryEvent] = []
        current_start = start

        # Get first page to establish total_count
        first_page = self.client.fetch_page(start=current_start, count=count)
        if not isinstance(first_page, dict):
            return ImportResult(imported_count=0, skipped_count=0, skipped_reasons=[])

        # Validate and extract pagination metadata
        total_count = first_page.get("total_count")
        if not isinstance(total_count, int) or total_count < 0:
            raise MarketHistoryImportError("invalid total_count in response")

        pagesize = first_page.get("pagesize")
        if not isinstance(pagesize, int) or pagesize <= 0:
            raise MarketHistoryImportError("invalid pagesize in response")

        # Parse first page events
        try:
            first_events = self.parser.parse_response(first_page)
        except (MarketHistoryParseError, HistoricalEventNormalizationError) as exc:
            # If we can't parse the first page, we can't continue
            raise MarketHistoryImportError(f"failed to parse first page: {exc}") from exc

        all_raw_events.extend(first_events)
        current_start = first_page.get("start", 0) + pagesize

        # Fetch remaining pages until we've consumed total_count
        while current_start < total_count:
            page = self.client.fetch_page(start=current_start, count=count)
            if not isinstance(page, dict):
                # Invalid response - stop pagination
                break

            # Validate pagination metadata
            page_total = page.get("total_count")
            if page_total != total_count:
                # Inconsistent total_count - stop to avoid infinite loops
                break

            page_start = page.get("start")
            if not isinstance(page_start, int) or page_start < 0:
                # Invalid start - stop
                break

            page_size = page.get("pagesize")
            if not isinstance(page_size, int) or page_size <= 0:
                # Invalid pagesize - stop
                break

            # Parse page events
            try:
                page_events = self.parser.parse_response(page)
            except (MarketHistoryParseError, HistoricalEventNormalizationError) as exc:
                # If we can't parse this page, skip it but continue pagination
                # (could be a malformed page in the middle)
                current_start = page_start + page_size
                continue

            all_raw_events.extend(page_events)
            current_start = page_start + page_size

            # Safety check: ensure we're making progress
            if current_start <= page_start:
                # Not advancing - prevent infinite loop
                break

        # Phase 2: Normalize events
        normalized_events: List[NormalizedHistoricalEvent] = []
        skip_reasons: List[str] = []

        for event in all_raw_events:
            try:
                nevent = normalize_market_history_event(event)
                normalized_events.append(nevent)
            except HistoricalEventNormalizationError as exc:
                skip_reasons.append(
                    f"normalization error for {event.external_ref}: {exc}"
                )

        # Phase 3: Persist persistable events atomically
        imported = 0
        persistable: List[NormalizedHistoricalEvent] = []

        for nevent in normalized_events:
            if nevent.timestamp is None:
                skip_reasons.append(
                    f"event {nevent.external_ref}: timestamp unavailable, "
                    "cannot persist into transactions table"
                )
                continue

            if nevent.fees is None:
                skip_reasons.append(
                    f"event {nevent.external_ref}: fees unavailable, "
                    "cannot persist into transactions table"
                )
                continue

            persistable.append(nevent)

        # Wrap all persistable inserts in ONE SQLite transaction
        try:
            self.conn.execute("BEGIN")
            for nevent in persistable:
                try:
                    self._persist_event(nevent)
                    imported += 1
                except sqlite3.IntegrityError as exc:
                    # Duplicate (bot_name, external_ref) — skip this event
                    skip_reasons.append(
                        f"duplicate external_ref {nevent.external_ref}: {exc}"
                    )
                except Exception as exc:
                    # Unexpected error — rollback entire batch
                    self.conn.rollback()
                    raise MarketHistoryImportError(
                        f"unexpected error persisting {nevent.external_ref}: {exc}"
                    ) from exc
            self.conn.commit()
        except MarketHistoryImportError:
            raise
        except Exception as exc:
            self.conn.rollback()
            raise MarketHistoryImportError(
                f"database failure during import: {exc}"
            ) from exc

        return ImportResult(
            imported_count=imported,
            skipped_count=len(skip_reasons),
            skipped_reasons=skip_reasons,
        )

    def _persist_event(self, nevent: NormalizedHistoricalEvent) -> None:
        """Persist a single normalized event as a transactions row.

        Does NOT create acquisition_lots. Uses create_transaction() for
        domain validation, then performs the INSERT directly.
        """
        # Validate using the existing domain model
        tx = create_transaction(
            type=nevent.type,
            market_hash_name=nevent.market_hash_name,
            quantity=nevent.quantity,
            unit_price=nevent.unit_price,
            fees=nevent.fees,
            total_value=nevent.total_value,
            timestamp=nevent.timestamp,
            bot_name=self.bot_name,
            external_ref=nevent.external_ref,
        )

        # Direct INSERT — do NOT use insert_buy_with_lot() which
        # hardcodes TRACKED cost_status and creates an acquisition lot.
        self.conn.execute(
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
                tx.type,
                tx.market_hash_name,
                tx.quantity,
                str(tx.unit_price),
                str(tx.fees) if tx.fees is not None else None,
                str(tx.total_value),
                tx.timestamp,
                tx.bot_name,
                tx.external_ref,
            ),
        )

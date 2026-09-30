"""Orchestration layer for Steam Market history ingestion (V0.5.6).

Thin orchestration layer connecting:
SteamMarketHistoryClient → MarketHistoryParser → normalize_market_history_events() → MarketHistoryImporter

Does NOT implement:
- Steam login, authentication, or cookie handling
- P&L, ROI, margin, profit, or cost-basis allocation
- Inventory mutation, acquisition-lot creation, buying/selling/execution
- Economic scoring or decision-engine changes

Implements:
- Dependency injection for client/parser/importer
- HTTP using existing SteamMarketHistoryClient
- Parsing using existing MarketHistoryParser
- Normalization using existing historical event normalizer
- Persistence delegated to existing MarketHistoryImporter
- BUY/SELL transaction creation only (no acquisition lots)
- Pagination preserving existing returned-pagesize behavior
- Idempotency relying on external_ref uniqueness
- Error propagation preserving importer rollback behavior
- Result object with fetched_event_count, imported_count, skipped_count, skipped_reasons
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

import requests

from historical_event_normalizer import (
    HistoricalEventNormalizationError,
    normalize_market_history_events,
)
from market_history_adapter import (
    MarketHistoryEvent,
    MarketHistoryParseError,
    SteamMarketHistoryClient,
    SteamMarketHistoryParser,
)
from market_history_importer import (
    ImportResult,
    MarketHistoryImportError,
    MarketHistoryImporter,
)
from transactions import create_transaction


@dataclass(frozen=True)
class IngestionResult:
    """Immutable result of a market-history ingestion operation."""

    fetched_event_count: int
    imported_count: int
    skipped_count: int
    skipped_reasons: List[str]


class MarketHistoryIngestionError(RuntimeError):
    """Raised when ingestion encounters an unrecoverable error."""


def _persist_event(
    conn: Any,
    bot_name: str,
    nevent,
) -> None:
    """Persist a single normalized event as a transactions row.

    Mirrors MarketHistoryImporter._persist_event: validates via
    create_transaction, then performs a direct INSERT without
    creating acquisition lots.
    """
    tx = create_transaction(
        type=nevent.type,
        market_hash_name=nevent.market_hash_name,
        quantity=nevent.quantity,
        unit_price=nevent.unit_price,
        fees=nevent.fees,
        total_value=nevent.total_value,
        timestamp=nevent.timestamp,
        bot_name=bot_name,
        external_ref=nevent.external_ref,
    )

    conn.execute(
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


class MarketHistoryIngestionService:
    """Orchestrate Steam market history ingestion.

    Args:
        client: SteamMarketHistoryClient instance (for dependency injection)
        parser: SteamMarketHistoryParser instance (for dependency injection)
        importer: MarketHistoryImporter instance (for dependency injection;
                  provides conn and bot_name for persistence)
    """

    def __init__(
        self,
        client: SteamMarketHistoryClient,
        parser: SteamMarketHistoryParser,
        importer: MarketHistoryImporter,
    ) -> None:
        self.client = client
        self.parser = parser
        self.importer = importer

    def ingest_history(self, start: int = 0, count: int = 100) -> IngestionResult:
        """Fetch, parse, normalize, and import market history pages.

        Returns:
            IngestionResult with counts and skip reasons.
        """
        all_raw_events: List[MarketHistoryEvent] = []
        current_start = start

        try:
            first_page = self.client.fetch_page(start=current_start, count=count)
            if not isinstance(first_page, dict):
                return IngestionResult(
                    fetched_event_count=0,
                    imported_count=0,
                    skipped_count=0,
                    skipped_reasons=[],
                )

            total_count = first_page.get("total_count")
            if not isinstance(total_count, int) or total_count < 0:
                raise MarketHistoryIngestionError("invalid total_count in response")

            pagesize = first_page.get("pagesize")
            if not isinstance(pagesize, int) or pagesize <= 0:
                raise MarketHistoryIngestionError("invalid pagesize in response")

            try:
                first_events = self.parser.parse_response(first_page)
            except (MarketHistoryParseError, HistoricalEventNormalizationError) as exc:
                raise MarketHistoryIngestionError(f"failed to parse first page: {exc}") from exc

            all_raw_events.extend(first_events)
            current_start = first_page.get("start", 0) + pagesize

            while current_start < total_count:
                page = self.client.fetch_page(start=current_start, count=count)
                if not isinstance(page, dict):
                    break

                page_total = page.get("total_count")
                if page_total != total_count:
                    break

                page_start = page.get("start")
                if not isinstance(page_start, int) or page_start < 0:
                    break

                page_size = page.get("pagesize")
                if not isinstance(page_size, int) or page_size <= 0:
                    break

                try:
                    page_events = self.parser.parse_response(page)
                except (MarketHistoryParseError, HistoricalEventNormalizationError):
                    current_start = page_start + page_size
                    continue

                all_raw_events.extend(page_events)
                current_start = page_start + page_size

                if current_start <= page_start:
                    break

        except MarketHistoryImportError:
            raise
        except Exception as exc:
            raise MarketHistoryIngestionError(f"fetch/parse failure: {exc}") from exc

        try:
            normalized_events = normalize_market_history_events(all_raw_events)
        except HistoricalEventNormalizationError as exc:
            raise MarketHistoryIngestionError(f"normalization failure: {exc}") from exc

        imported = 0
        skip_reasons: List[str] = []
        conn = self.importer.conn
        bot_name = self.importer.bot_name

        try:
            conn.execute("BEGIN")
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

                try:
                    _persist_event(conn, bot_name, nevent)
                    imported += 1
                except Exception as exc:
                    err_str = str(exc).lower()
                    if "unique" in err_str and "external_ref" in err_str:
                        skip_reasons.append(
                            f"duplicate external_ref {nevent.external_ref}: {exc}"
                        )
                    else:
                        conn.rollback()
                        raise MarketHistoryIngestionError(
                            f"unexpected error persisting {nevent.external_ref}: {exc}"
                        ) from exc
            conn.commit()
        except MarketHistoryIngestionError:
            raise
        except Exception as exc:
            conn.rollback()
            raise MarketHistoryIngestionError(
                f"database failure during import: {exc}"
            ) from exc

        return IngestionResult(
            fetched_event_count=len(all_raw_events),
            imported_count=imported,
            skipped_count=len(skip_reasons),
            skipped_reasons=skip_reasons,
        )

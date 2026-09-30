"""Read-only adapter for Steam Community Market personal history."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, Mapping, Optional

try:
    import requests
except ImportError:
    requests = None


MarketHistoryType = Literal["BUY", "SELL"]


class MarketHistoryParseError(ValueError):
    """Raised when Steam market-history data cannot be parsed safely."""


class MarketHistoryRequestError(RuntimeError):
    """Raised when the Steam market-history request fails."""


@dataclass(frozen=True)
class MarketHistoryEvent:
    type: MarketHistoryType
    market_hash_name: str
    quantity: int
    unit_price: Decimal
    fees: Optional[Decimal]
    total_value: Decimal
    timestamp: Optional[str]
    external_ref: Optional[str] = None

    # V0.5.9 raw monetary/currency fields (preserved from Steam responses)
    steam_fee: Optional[Decimal] = None
    publisher_fee: Optional[Decimal] = None
    publisher_fee_percent: Optional[str] = None
    publisher_fee_app: Optional[int] = None
    funds_returned: Optional[Decimal] = None
    received_amount: Optional[Decimal] = None
    currencyid: Optional[int] = None
    received_currencyid: Optional[int] = None
    added_tax: Optional[Decimal] = None

    # Historical cost remains UNKNOWN; no acquisition cost is derived.
    cost_status: Literal["TRACKED", "UNKNOWN"] = "UNKNOWN"
    unit_cost: Optional[Decimal] = None


class SteamMarketHistoryClient:
    """Read-only HTTP client using an already-authenticated Session."""

    def __init__(
        self,
        session: requests.Session,
        base_url: str = "https://steamcommunity.com",
    ) -> None:
        self.session = session
        self.base_url = base_url.rstrip("/")

    def fetch_page(self, start: int = 0, count: int = 100) -> Any:
        if isinstance(start, bool) or not isinstance(start, int) or start < 0:
            raise ValueError("start must be a non-negative integer")

        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ValueError("count must be a positive integer")

        response = self.session.get(
            f"{self.base_url}/market/myhistory/render/",
            params={
                "start": start,
                "count": count,
                "norender": 1,
            },
        )

        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            raise MarketHistoryRequestError(
                "Steam market-history request failed"
            ) from exc

        try:
            return response.json()
        except ValueError as exc:
            raise MarketHistoryParseError(
                "Steam market-history response is not valid JSON"
            ) from exc


class SteamMarketHistoryParser:
    """Parse the actual Steam market-history response shape.

    The endpoint returns:
      - results_html: rendered market-history rows
      - assets: item metadata indexed by app/context/asset id

    We only extract values explicitly present in the response.
    """

    _ROW_RE = re.compile(
        r'<div\s+class="market_listing_row[^"]*"'
        r'\s+id="(history_row_[^"]+)"'
        r'>(.*?)</div>\s*(?=<div\s+class="market_listing_row|$)',
        re.DOTALL,
    )

    _GAIN_RE = re.compile(
        r'<div\s+class="market_listing_left_cell\s+market_listing_gainorloss">'
        r'\s*([+-])\s*</div>',
        re.DOTALL,
    )

    _PRICE_RE = re.compile(
        r'<span\s+class="market_listing_price">\s*([^<]+?)\s*</span>',
        re.DOTALL,
    )

    _NAME_RE = re.compile(
        r'<span\s+class="market_listing_item_name"[^>]*>\s*'
        r'([^<]+?)\s*</span>',
        re.DOTALL,
    )

    _ACTION_RE = re.compile(
        r'<div\s+class="market_listing_listed_date_combined">\s*'
        r'(Purchased|Sold):\s*([^<]+?)\s*</div>',
        re.DOTALL | re.IGNORECASE,
    )

    _ASSET_ID_RE = re.compile(
        r"^history_row_[^_]+_[^_]+$"
    )

    @staticmethod
    def _parse_price(value: str) -> Decimal:
        """Parse Steam localized price text such as '0,04€'."""

        cleaned = html.unescape(value).strip()
        cleaned = cleaned.replace("\xa0", "").replace(" ", "")
        cleaned = cleaned.replace("€", "").replace("$", "").replace("£", "")

        if "," in cleaned and "." in cleaned:
            # Conservative handling of localized thousands/decimal separators.
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")

        try:
            price = Decimal(cleaned)
        except (InvalidOperation, ValueError) as exc:
            raise MarketHistoryParseError(
                f"invalid Steam price: {value!r}"
            ) from exc

        if not price.is_finite() or price < 0:
            raise MarketHistoryParseError(
                f"invalid Steam price: {value!r}"
            )

        return price

    @staticmethod
    def _extract_asset_id(row_id: str) -> str:
        """Extract the asset id encoded in the Steam history row id.

        Steam currently renders IDs like:
        history_row_<listing-id>_<asset-id>

        We deliberately do not call this a transaction ID.
        """

        parts = row_id.split("_")

        if len(parts) != 4 or parts[0] != "history" or parts[1] != "row":
            raise MarketHistoryParseError(
                f"unrecognized Steam history row id: {row_id}"
            )

        asset_id = parts[3]

        if not asset_id.isdigit():
            raise MarketHistoryParseError(
                f"invalid asset id in history row: {row_id}"
            )

        return asset_id

    @staticmethod
    def _build_history_asset_map(
        hovers: str,
    ) -> dict[str, tuple[str, str, str]]:
        """Build history-row -> (appid, contextid, asset_id) mappings.

        The Steam response embeds CreateItemHoverFromContainer calls in
        JavaScript. Only the row identifier and asset coordinates are
        relevant here; quoting style and whitespace are intentionally
        treated as presentation details.
        """
        if not isinstance(hovers, str):
            raise MarketHistoryParseError(
                "response hovers must be a string"
            )

        pattern = re.compile(
            r"CreateItemHoverFromContainer\s*\(\s*"
            r"g_rgAssets\s*,\s*"
            r"""['"]?(history_row_[^'"\s]+)_name['"]?\s*,\s*"""
            r"""['"]?(\d+)['"]?\s*,\s*"""
            r"""['"]?([^'",\s]+)['"]?\s*,\s*"""
            r"""['"]?([^'",\s]+)['"]?\s*,\s*"""
            r"0\s*\)"
        )

        result: dict[str, tuple[str, str, str]] = {}

        for match in pattern.finditer(hovers):
            row_id = match.group(1)
            appid = match.group(2)
            contextid = match.group(3)
            asset_id = match.group(4)

            result[row_id] = (appid, contextid, asset_id)

        return result

    @staticmethod
    def _lookup_asset(
        assets: Mapping[str, Any],
        appid: str,
        contextid: str,
        asset_id: str,
    ) -> Mapping[str, Any]:
        """Resolve an asset from the Steam assets mapping."""

        app_assets = assets.get(appid)

        if not isinstance(app_assets, Mapping):
            raise MarketHistoryParseError(
                f"appid {appid} referenced by history row was not found"
            )

        context_assets = app_assets.get(contextid)

        if not isinstance(context_assets, Mapping):
            raise MarketHistoryParseError(
                f"context {contextid} referenced by history row was not found"
            )

        asset = context_assets.get(asset_id)

        if not isinstance(asset, Mapping):
            raise MarketHistoryParseError(
                f"asset {asset_id} referenced by history row was not found"
            )

        return asset

    def parse_response(
        self,
        response: Mapping[str, Any],
    ) -> list[MarketHistoryEvent]:
        if not isinstance(response, Mapping):
            raise MarketHistoryParseError("response must be a mapping")

        results_html = response.get("results_html")
        assets = response.get("assets")
        hovers = response.get("hovers")

        if not isinstance(results_html, str):
            raise MarketHistoryParseError(
                "response must contain results_html"
            )

        if not isinstance(assets, Mapping):
            raise MarketHistoryParseError(
                "response must contain assets mapping"
            )

        rows = list(self._ROW_RE.finditer(results_html))

        # An empty page is valid and needs no asset/hover resolution.
        if not rows:
            if results_html.strip():
                raise MarketHistoryParseError(
                    "results_html contains no recognizable market history rows"
                )
            return []

        if not isinstance(hovers, str):
            raise MarketHistoryParseError(
                "response must contain hovers"
            )

        history_asset_map = self._build_history_asset_map(hovers)

        if not rows and results_html.strip():
            raise MarketHistoryParseError(
                "results_html contains no recognizable market-history rows"
            )

        events: list[MarketHistoryEvent] = []

        for row_match in rows:
            row_id = row_match.group(1)
            row_html = row_match.group(2)

            events.append(
                self._parse_row(
                    row_id=row_id,
                    row_html=row_html,
                    assets=assets,
                    history_asset_map=history_asset_map,
                )
            )

        return events

    def _parse_row(
        self,
        *,
        row_id: str,
        row_html: str,
        assets: Mapping[str, Any],
        history_asset_map: Mapping[str, tuple[str, str, str]],
    ) -> MarketHistoryEvent:
        gain_match = self._GAIN_RE.search(row_html)

        if not gain_match:
            raise MarketHistoryParseError(
                f"{row_id}: missing BUY/SELL indicator"
            )

        event_type: MarketHistoryType = (
            "BUY" if gain_match.group(1) == "+" else "SELL"
        )

        price_match = self._PRICE_RE.search(row_html)

        if not price_match:
            raise MarketHistoryParseError(
                f"{row_id}: missing price"
            )

        unit_price = self._parse_price(price_match.group(1))

        name_match = self._NAME_RE.search(row_html)

        if not name_match:
            raise MarketHistoryParseError(
                f"{row_id}: missing item name"
            )

        displayed_name = html.unescape(name_match.group(1)).strip()

        action_match = self._ACTION_RE.search(row_html)

        if not action_match:
            raise MarketHistoryParseError(
                f"{row_id}: missing Purchased/Sold action"
            )

        action = action_match.group(1).upper()

        if (event_type == "BUY" and action != "PURCHASED") or (
            event_type == "SELL" and action != "SOLD"
        ):
            raise MarketHistoryParseError(
                f"{row_id}: gain/loss indicator and action disagree"
            )

        asset_ref = history_asset_map.get(row_id)

        if asset_ref is None:
            raise MarketHistoryParseError(
                f"{row_id}: no asset mapping in hovers"
            )

        appid, contextid, asset_id = asset_ref

        asset = self._lookup_asset(
            assets,
            appid,
            contextid,
            asset_id,
        )

        market_hash_name = asset.get("market_hash_name")

        if not isinstance(market_hash_name, str) or not market_hash_name.strip():
            raise MarketHistoryParseError(
                f"{row_id}: asset has no market_hash_name"
            )

        # Each rendered history row represents the item represented by that
        # row. The current response does not expose a separate quantity field.
        # We therefore preserve the observed row semantics as quantity=1.
        quantity = 1

        return MarketHistoryEvent(
            type=event_type,
            market_hash_name=market_hash_name.strip(),
            quantity=quantity,
            unit_price=unit_price,
            fees=None,
            total_value=unit_price,
            timestamp=None,
            external_ref=row_id,
            steam_fee=None,
            publisher_fee=None,
            publisher_fee_percent=None,
            publisher_fee_app=None,
            funds_returned=None,
            received_amount=None,
            currencyid=None,
            received_currencyid=None,
            added_tax=None,
            cost_status="UNKNOWN",
            unit_cost=None,
        )

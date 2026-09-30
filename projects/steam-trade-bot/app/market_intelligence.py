"""
V0.4.2 — Market Intelligence

Pure functions exposing market price intelligence from the Steam Market
price cache and HTML page parsing.

Fields exposed:
    - lowest_price          : raw Steam lowest price text
    - median_price          : raw Steam median price text
    - lowest_price_value    : normalized decimal value of lowest price
    - median_price_value    : normalized decimal value of median price
    - active_listing_count  : number of active sell listings (existing `volume` field)
    - freshness_seconds     : age of last fetch in seconds (from fetched_at_unix)

Missing values are returned as None. No fabricated data.
No daily_volume, liquidity, volatility, price history, or arbitrary scores.
"""

import time
from decimal import Decimal

from economic import _money
from main import (
    extract_prices_from_html,
    fetch_market_price,
    get_cached_market_price,
    parse_price_text,
)


def _get_market_data(market_hash_name):
    """
    Retrieve market data for a single market_hash_name via one path.

    Prefers the cached record; falls back to a single fresh fetch.
    Returns the market data dict or None.
    """
    cached = get_cached_market_price(market_hash_name)
    if cached is not None:
        return cached

    return fetch_market_price(market_hash_name)


def _freshness_from(data):
    """
    Compute freshness in seconds from a market data record's
    fetched_at_unix. Returns None if the timestamp is missing or
    invalid. Does not fabricate or create any timestamps.
    """
    fetched_at_unix = data.get("fetched_at_unix")
    if fetched_at_unix is None:
        return None

    try:
        fetched = int(fetched_at_unix)
    except (TypeError, ValueError):
        return None

    return int(time.time()) - fetched


def get_lowest_price(market_hash_name: str):
    """Return the raw Steam lowest price text, or None if unavailable."""
    data = _get_market_data(market_hash_name)
    if data is None:
        return None
    return data.get("lowest_price")


def get_median_price(market_hash_name: str):
    """Return the raw Steam median price text, or None if unavailable."""
    data = _get_market_data(market_hash_name)
    if data is None:
        return None
    return data.get("median_price")


def get_active_listing_count(market_hash_name: str):
    """
    Return the number of active sell listings.

    This is exactly the existing `volume` field from the market_prices
    table / Steam page parser. It represents the count of currently
    listed items, NOT daily volume or monetary volume.

    Returns None if the volume field is missing.
    """
    data = _get_market_data(market_hash_name)
    if data is None:
        return None
    return data.get("volume")


def get_lowest_price_value(market_hash_name: str):
    """Return the normalized decimal value of the lowest price, or None."""
    data = _get_market_data(market_hash_name)
    if data is None:
        return None
    value = data.get("lowest_price_value")
    if value is None:
        return None
    return _money(Decimal(str(value)))


def get_median_price_value(market_hash_name: str):
    """Return the normalized decimal value of the median price, or None."""
    data = _get_market_data(market_hash_name)
    if data is None:
        return None
    value = data.get("median_price_value")
    if value is None:
        return None
    return _money(Decimal(str(value)))


def get_market_freshness(market_hash_name: str):
    """
    Return the age of the cached market data in seconds.

    Uses ONLY the persisted fetched_at_unix timestamp.
    Returns None if the timestamp is missing or invalid.
    """
    data = _get_market_data(market_hash_name)
    if data is None:
        return None
    return _freshness_from(data)


def get_market_price_info(market_hash_name: str):
    """
    Return all market price fields from a single data retrieval.

    Derives every field from one call to _get_market_data so that
    no helper is invoked more than once per public call.
    """
    data = _get_market_data(market_hash_name)
    if data is None:
        return None

    lowest_price_value = data.get("lowest_price_value")
    median_price_value = data.get("median_price_value")

    return {
        "lowest_price": data.get("lowest_price"),
        "median_price": data.get("median_price"),
        "active_listing_count": data.get("volume"),
        "lowest_price_value": (
            _money(Decimal(str(lowest_price_value)))
            if lowest_price_value is not None
            else None
        ),
        "median_price_value": (
            _money(Decimal(str(median_price_value)))
            if median_price_value is not None
            else None
        ),
        "freshness_seconds": _freshness_from(data),
    }

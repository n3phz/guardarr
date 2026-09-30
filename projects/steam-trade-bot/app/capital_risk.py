"""V0.4.3 — Capital and risk calculator primitives.

These functions calculate market-value estimates only. They do not track
account balances, acquisition costs, invested capital, positions, exposure, or
risk scores.
"""

from decimal import Decimal

import market_intelligence as market_intelligence
from economic import calculate_total_fees


FRESHNESS_FRESH = 300
FRESHNESS_STALE = 1800


def _decimal(value) -> Decimal:
    """Convert a supplied value to Decimal without treating missing data as zero."""
    return Decimal(str(value))


def potential_proceeds(median_price_value, inventory_amount) -> Decimal | None:
    """Return the estimated market proceeds from the median price and quantity.

    This is a market-value estimate based on the median market price, not an
    acquisition cost or invested capital figure. Returns None when either the
    median price or inventory quantity is missing.
    """
    if median_price_value is None or inventory_amount is None:
        return None
    return _decimal(median_price_value) * _decimal(inventory_amount)


def potential_net_proceeds(
    median_price_value,
    inventory_amount,
    game_fee_rate=None,
) -> Decimal | None:
    """Return estimated proceeds after the existing transaction fee calculation.

    The gross amount is the market-value estimate from :func:`potential_proceeds`.
    Transaction fees are calculated using :func:`app.economic.calculate_total_fees`;
    this function does not duplicate Steam fee logic. Returns None when the
    gross estimate is unavailable.
    """
    proceeds = potential_proceeds(median_price_value, inventory_amount)
    if proceeds is None:
        return None

    total_fees = calculate_total_fees(proceeds, game_fee_rate)
    if total_fees is None:
        return None
    return proceeds - total_fees


def inventory_value_estimate(median_price_value, inventory_amount) -> Decimal | None:
    """Return the estimated market value of the inventory.

    This is a MARKET VALUE ESTIMATE based on the median market price, not
    acquisition cost and not invested capital. Returns None when either the
    median price or inventory quantity is missing.
    """
    return potential_proceeds(median_price_value, inventory_amount)


def price_freshness_status(market_hash_name: str) -> str:
    """Classify market-data freshness using the existing market intelligence data."""
    freshness = market_intelligence.get_market_freshness(market_hash_name)
    if freshness is None:
        return "UNKNOWN"

    try:
        freshness_seconds = int(freshness)
    except (TypeError, ValueError):
        return "UNKNOWN"

    if freshness_seconds < FRESHNESS_FRESH:
        return "FRESH"
    if freshness_seconds < FRESHNESS_STALE:
        return "STALE"
    return "VERY_STALE"

"""V0.4.4 — Decision Primitives.

Pure, deterministic decision helpers for current inventory-sale conditions.

This module does not determine acquisition profitability, invested capital,
account balance, portfolio exposure, future prices, or trade execution.

SELL means the current data satisfies the existing economic_score baseline
and the market data is fresh. It does not mean that a purchase should be made.
"""

from typing import Any


ACTION_SELL = "SELL"
ACTION_WATCH = "WATCH"
ACTION_IGNORE = "IGNORE"

CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_LOW = "LOW"

ACTIONABLE_SCORE_BASELINE = 50

FRESH = "FRESH"
STALE = "STALE"
VERY_STALE = "VERY_STALE"
UNKNOWN = "UNKNOWN"


def decide_inventory_action(
    *,
    quantity: Any,
    median_price_value: Any,
    freshness_status: str,
    economic_score: Any,
) -> dict[str, str]:
    """Return a deterministic SELL/WATCH/IGNORE decision.

    The existing economic_score baseline of 50 is used as the actionable
    threshold. No new profitability or scoring formula is introduced.

    Market-data quality takes precedence over the economic score:
    stale, very-stale, unknown, or missing market data can never produce SELL.
    """

    if quantity is None:
        return {
            "action": ACTION_WATCH,
            "reason": "inventory quantity missing",
            "confidence": CONFIDENCE_LOW,
        }

    if median_price_value is None:
        return {
            "action": ACTION_WATCH,
            "reason": "market price missing",
            "confidence": CONFIDENCE_LOW,
        }

    try:
        if quantity <= 0:
            return {
                "action": ACTION_IGNORE,
                "reason": "inventory quantity is zero or negative",
                "confidence": CONFIDENCE_HIGH,
            }
    except TypeError:
        return {
            "action": ACTION_WATCH,
            "reason": "inventory quantity is invalid",
            "confidence": CONFIDENCE_LOW,
        }

    if freshness_status == UNKNOWN:
        return {
            "action": ACTION_WATCH,
            "reason": "market freshness unknown",
            "confidence": CONFIDENCE_LOW,
        }

    if freshness_status == VERY_STALE:
        return {
            "action": ACTION_WATCH,
            "reason": "market data is very stale",
            "confidence": CONFIDENCE_LOW,
        }

    if freshness_status == STALE:
        return {
            "action": ACTION_WATCH,
            "reason": "market data is stale",
            "confidence": CONFIDENCE_MEDIUM,
        }

    if freshness_status != FRESH:
        return {
            "action": ACTION_WATCH,
            "reason": "market freshness unknown",
            "confidence": CONFIDENCE_LOW,
        }

    try:
        actionable = economic_score >= ACTIONABLE_SCORE_BASELINE
    except TypeError:
        return {
            "action": ACTION_WATCH,
            "reason": "economic score is invalid",
            "confidence": CONFIDENCE_LOW,
        }

    if actionable:
        return {
            "action": ACTION_SELL,
            "reason": "fresh market data and existing economic_score is actionable",
            "confidence": CONFIDENCE_HIGH,
        }

    return {
        "action": ACTION_IGNORE,
        "reason": "fresh market data but existing economic_score is below actionable baseline",
        "confidence": CONFIDENCE_HIGH,
    }

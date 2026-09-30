"""
V0.4.1 — Economic Calculation Module

Centralized fee and economic calculations for the Steam Trade Bot.

Steam transaction fee: 5%, minimum €0.01 (applies only when gross > 0)
Optional game-specific fee: default 0%

All monetary values are Decimal rounded to cents (2 decimal places).

Acquisition cost semantics:
  acquisition_cost is the TOTAL acquisition cost for the entire quantity
  being calculated, NOT the unit cost. When quantity > 1, the caller
  must supply the aggregate cost. Unknown acquisition cost is represented
  as None — never coerced to zero.

Margin semantics:
  margin = profit / net_proceeds
  expressed as a decimal ratio.

  Unknown or non-positive net proceeds yield None.
"""

from decimal import Decimal, ROUND_HALF_UP

STEAM_FEE_RATE = Decimal("0.05")
STEAM_FEE_MINIMUM = Decimal("0.01")
GAME_FEE_DEFAULT = Decimal("0.00")
CENTS = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    """Round a Decimal monetary value to 2 decimal places (cents)."""
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def _rate_to_decimal(rate) -> Decimal:
    """Convert a float or Decimal rate to Decimal safely."""
    if rate is None:
        return GAME_FEE_DEFAULT
    if isinstance(rate, float):
        return Decimal(str(rate))
    return Decimal(rate)


def calculate_gross(unit_price, quantity) -> Decimal | None:
    """
    Calculate gross proceeds = unit_price * quantity.

    Returns None if unit_price is missing (None or not provided).
    """
    if unit_price is None:
        return None
    price = _rate_to_decimal(unit_price)
    qty = Decimal(str(quantity))
    return _money(price * qty)


def calculate_steam_fee(gross_proceeds: Decimal) -> Decimal | None:
    """
    Calculate Steam transaction fee = 5% of gross, minimum €0.01.

    gross_proceeds == 0  → fee €0.00 (no minimum on zero-value transactions)
    gross_proceeds is None → None (missing price data, fee unavailable)
    gross_proceeds > 0  → max(5% of gross, €0.01)
    """
    if gross_proceeds is None:
        return None
    if gross_proceeds == 0:
        return Decimal("0.00")
    fee = gross_proceeds * STEAM_FEE_RATE
    return max(_money(fee), STEAM_FEE_MINIMUM)


def calculate_game_fee(gross_proceeds: Decimal, game_fee_rate=None) -> Decimal | None:
    """
    Calculate optional game-specific fee.

    game_fee_rate defaults to 0%. Never assume 10% or 15% unless explicitly supplied.
    Returns None if gross_proceeds is None (missing price data).
    """
    if gross_proceeds is None:
        return None
    if gross_proceeds == 0:
        return Decimal("0.00")
    rate = _rate_to_decimal(game_fee_rate)
    fee = gross_proceeds * rate
    return _money(fee)


def calculate_total_fees(gross_proceeds: Decimal, game_fee_rate=None) -> Decimal | None:
    """
    Calculate total fees = Steam fee + optional game fee.

    Returns None if gross_proceeds is None (missing price data).
    """
    if gross_proceeds is None:
        return None
    steam = calculate_steam_fee(gross_proceeds)
    game = calculate_game_fee(gross_proceeds, game_fee_rate)
    return _money(steam + game)


def calculate_net(gross_proceeds: Decimal, game_fee_rate=None) -> Decimal | None:
    """
    Calculate net proceeds = gross - total_fees.

    Returns None if gross_proceeds is None.
    """
    if gross_proceeds is None:
        return None
    fees = calculate_total_fees(gross_proceeds, game_fee_rate)
    return _money(gross_proceeds - fees)


def calculate_profit(net_proceeds: Decimal | None, acquisition_cost) -> Decimal | None:
    """
    Calculate profit = net_proceeds - acquisition_cost.

    acquisition_cost is the TOTAL acquisition cost for the quantity
    being calculated, not the unit cost.

    Returns None if:
      - net_proceeds is None
      - acquisition_cost is None (unknown)

    Known positive, explicit zero, and unknown acquisition costs are handled.
    """
    if net_proceeds is None:
        return None
    if acquisition_cost is None:
        return None
    cost = _rate_to_decimal(acquisition_cost)
    return _money(net_proceeds - cost)


def calculate_roi(profit: Decimal | None, acquisition_cost) -> Decimal | None | str:
    """
    Calculate ROI = profit / acquisition_cost.

    acquisition_cost is the TOTAL acquisition cost for the quantity
    being calculated, not the unit cost.

    Returns:
      - None if profit is None or acquisition_cost is None (unknown)
      - None if acquisition_cost is zero (avoid division by zero)
      - Decimal ROI if acquisition_cost > 0
    """
    if profit is None:
        return None
    if acquisition_cost is None:
        return None
    cost = _rate_to_decimal(acquisition_cost)
    if cost <= 0:
        return None
    roi = profit / cost
    return _money(roi)


def calculate_margin(profit: Decimal | None, net_proceeds: Decimal | None) -> Decimal | None:
    """
    Calculate profit margin = profit / net_proceeds.

    expressed as a decimal ratio.

    Returns None if:
      - profit is None
      - net_proceeds is None
      - net_proceeds <= 0
    """
    if profit is None or net_proceeds is None:
        return None
    if net_proceeds <= 0:
        return None
    margin = profit / net_proceeds
    return _money(margin)


def calculate_economics(unit_price, quantity, acquisition_cost=None, game_fee_rate=None) -> dict:
    """
    Calculate all economic metrics in one call.

    acquisition_cost is the TOTAL acquisition cost for the quantity
    being calculated, not the unit cost.

    Returns a dict with:
      - gross_proceeds
      - steam_fee
      - game_fee
      - total_fees
      - net_proceeds
      - profit
      - roi
      - margin

    Missing unit_price yields None for all derived values.
    """
    gross = calculate_gross(unit_price, quantity)
    steam_fee = calculate_steam_fee(gross) if gross is not None else None
    game_fee = calculate_game_fee(gross, game_fee_rate) if gross is not None else None
    total_fees = calculate_total_fees(gross, game_fee_rate) if gross is not None else None
    net = calculate_net(gross, game_fee_rate) if gross is not None else None
    profit = calculate_profit(net, acquisition_cost) if net is not None else None
    roi = calculate_roi(profit, acquisition_cost) if profit is not None else None
    margin = calculate_margin(profit, net) if profit is not None and net is not None else None

    return {
        "gross_proceeds": gross,
        "steam_fee": steam_fee,
        "game_fee": game_fee,
        "total_fees": total_fees,
        "net_proceeds": net,
        "profit": profit,
        "roi": roi,
        "margin": margin,
    }

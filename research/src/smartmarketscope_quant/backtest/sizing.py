from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR

from .types import InstrumentScenario, PositionSizeResult, ZERO, money


class PositionSizingError(ValueError):
    pass


def _floor_step(value: Decimal, step: Decimal) -> Decimal:
    return (value / step).to_integral_value(rounding=ROUND_FLOOR) * step


def size_for_risk(
    scenario: InstrumentScenario,
    entry_price: Decimal,
    stop_distance_points: Decimal,
    risk_budget_usd: Decimal,
    available_equity_usd: Decimal,
) -> PositionSizeResult:
    if min(entry_price, stop_distance_points, risk_budget_usd, available_equity_usd) <= ZERO:
        raise PositionSizingError("Entry, stop distance, risk budget, and equity must be positive")

    round_trip_execution_points = scenario.spread_points + Decimal("2") * scenario.slippage_points_per_side
    price_and_execution_risk = (
        stop_distance_points + round_trip_execution_points
    ) * scenario.point_value_usd_per_unit
    commission = Decimal("2") * scenario.commission_usd_per_unit_per_side
    risk_per_unit = money(price_and_execution_risk + commission)
    if risk_per_unit <= ZERO:
        raise PositionSizingError("Risk per unit must be positive")

    risk_quantity = _floor_step(risk_budget_usd / risk_per_unit, scenario.quantity_step)
    margin_per_unit = money(entry_price * scenario.contract_size_per_unit / scenario.leverage)
    margin_quantity = _floor_step(available_equity_usd / margin_per_unit, scenario.quantity_step)
    quantity = min(risk_quantity, margin_quantity, scenario.max_quantity)
    quantity = _floor_step(quantity, scenario.quantity_step)
    if quantity < scenario.min_quantity:
        raise PositionSizingError("No permitted quantity satisfies risk and margin constraints")

    if quantity == scenario.max_quantity:
        limiting = "MAX_QUANTITY"
    elif quantity == margin_quantity and margin_quantity <= risk_quantity:
        limiting = "MARGIN"
    else:
        limiting = "RISK_BUDGET"
    return PositionSizeResult(
        quantity=quantity,
        risk_per_unit_usd=risk_per_unit,
        total_risk_usd=money(quantity * risk_per_unit),
        required_margin_usd=money(quantity * margin_per_unit),
        limiting_constraint=limiting,
    )

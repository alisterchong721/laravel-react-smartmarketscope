from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from .types import Fill, InstrumentScenario, MarketBar, Position, Side, TradeIntent, ZERO, money


class ExecutionError(ValueError):
    pass


def _transaction_for_entry(side: Side) -> str:
    return "BUY" if side is Side.LONG else "SELL"


def _transaction_for_exit(side: Side) -> str:
    return "SELL" if side is Side.LONG else "BUY"


def make_fill(
    timestamp,
    reason: str,
    transaction: str,
    reference_price: Decimal,
    quantity: Decimal,
    scenario: InstrumentScenario,
    evidence_class: str,
    ambiguity: bool = False,
) -> Fill:
    half_spread = scenario.spread_points / Decimal("2")
    direction = Decimal("1") if transaction == "BUY" else Decimal("-1")
    fill_price = reference_price + direction * (half_spread + scenario.slippage_points_per_side)
    return Fill(
        timestamp=timestamp,
        reason=reason,
        transaction=transaction,
        reference_price=reference_price,
        fill_price=fill_price,
        quantity=quantity,
        spread_cost_usd=money(half_spread * scenario.point_value_usd_per_unit * quantity),
        slippage_cost_usd=money(
            scenario.slippage_points_per_side * scenario.point_value_usd_per_unit * quantity
        ),
        commission_usd=money(scenario.commission_usd_per_unit_per_side * quantity),
        evidence_class=evidence_class,
        ambiguity=ambiguity,
    )


def resolve_entry(intent: TradeIntent, bar: MarketBar, scenario: InstrumentScenario) -> Fill | None:
    transaction = _transaction_for_entry(intent.side)
    if intent.entry_order_type.value == "MARKET":
        reference = bar.open
    elif intent.entry_order_type.value == "LIMIT":
        assert intent.entry_order_price is not None
        touched = bar.low <= intent.entry_order_price if transaction == "BUY" else bar.high >= intent.entry_order_price
        if not touched:
            return None
        reference = intent.entry_order_price
    elif intent.entry_order_type.value == "STOP":
        assert intent.entry_order_price is not None
        touched = bar.high >= intent.entry_order_price if transaction == "BUY" else bar.low <= intent.entry_order_price
        if not touched:
            return None
        if transaction == "BUY" and bar.open >= intent.entry_order_price:
            reference = bar.open
        elif transaction == "SELL" and bar.open <= intent.entry_order_price:
            reference = bar.open
        else:
            reference = intent.entry_order_price
    else:
        raise ExecutionError("Unsupported entry order")
    return make_fill(
        bar.timestamp,
        "ENTRY",
        transaction,
        reference,
        intent.quantity,
        scenario,
        "SCENARIO_BAR_FILL",
    )


def _barrier_hits(side: Side, stop: Decimal, target: Decimal, bar: MarketBar) -> tuple[bool, bool]:
    if side is Side.LONG:
        return bar.low <= stop, bar.high >= target
    return bar.high >= stop, bar.low <= target


def _first_lower_timeframe_barrier(
    side: Side,
    stop: Decimal,
    target: Decimal,
    parent_bar: MarketBar,
    lower_bars: Iterable[MarketBar],
) -> str | None:
    bars = list(lower_bars)
    if not bars:
        raise ExecutionError("Lower-timeframe evidence is empty")
    if bars[0].timestamp != parent_bar.timestamp or bars[-1].available_at != parent_bar.available_at:
        raise ExecutionError("Lower-timeframe evidence does not cover the complete parent bar")
    previous_timestamp = None
    previous_bar = None
    for bar in bars:
        if previous_timestamp is not None and bar.timestamp <= previous_timestamp:
            raise ExecutionError("Lower-timeframe bars must be strictly ordered")
        if previous_bar is not None:
            if bar.timestamp != previous_bar.available_at:
                raise ExecutionError("Lower-timeframe evidence contains a gap")
        if bar.timestamp < parent_bar.timestamp or bar.available_at > parent_bar.available_at:
            raise ExecutionError("Lower-timeframe evidence escapes the parent bar")
        previous_timestamp = bar.timestamp
        previous_bar = bar
        stop_hit, target_hit = _barrier_hits(side, stop, target, bar)
        if stop_hit and target_hit:
            return "STOP_AMBIGUOUS_LOWER_BAR"
        if stop_hit:
            return "STOP_LOWER_TIMEFRAME"
        if target_hit:
            return "TARGET_LOWER_TIMEFRAME"
    return None


def resolve_exit(
    position: Position,
    bar: MarketBar,
    scenario: InstrumentScenario,
    lower_bars: Iterable[MarketBar] | None = None,
) -> Fill | None:
    intent = position.intent
    side = intent.side
    transaction = _transaction_for_exit(side)
    stop = intent.stop_price
    target = intent.target_price

    if side is Side.LONG and bar.open <= stop:
        return make_fill(bar.timestamp, "STOP_GAP", transaction, bar.open, intent.quantity, scenario, "GAP_OPEN")
    if side is Side.SHORT and bar.open >= stop:
        return make_fill(bar.timestamp, "STOP_GAP", transaction, bar.open, intent.quantity, scenario, "GAP_OPEN")

    stop_hit, target_hit = _barrier_hits(side, stop, target, bar)
    if stop_hit and target_hit:
        if lower_bars is not None:
            first = _first_lower_timeframe_barrier(side, stop, target, bar, lower_bars)
            if first and first.startswith("TARGET"):
                return make_fill(
                    bar.timestamp,
                    "TARGET",
                    transaction,
                    target,
                    intent.quantity,
                    scenario,
                    "ELIGIBLE_LOWER_TIMEFRAME_ORDERING",
                    ambiguity=False,
                )
            if first and first.startswith("STOP"):
                return make_fill(
                    bar.timestamp,
                    "STOP",
                    transaction,
                    stop,
                    intent.quantity,
                    scenario,
                    "ELIGIBLE_LOWER_TIMEFRAME_ORDERING_ADVERSE_OR_AMBIGUOUS",
                    ambiguity="AMBIGUOUS" in first,
                )
        return make_fill(
            bar.timestamp,
            "STOP",
            transaction,
            stop,
            intent.quantity,
            scenario,
            "ADVERSE_FIRST_NO_ELIGIBLE_LOWER_TIMEFRAME_EVIDENCE",
            ambiguity=True,
        )
    if stop_hit:
        return make_fill(bar.timestamp, "STOP", transaction, stop, intent.quantity, scenario, "BAR_TOUCH")
    if target_hit:
        return make_fill(bar.timestamp, "TARGET", transaction, target, intent.quantity, scenario, "BAR_TOUCH")
    return None


def mark_to_market_exit_cost(position: Position, scenario: InstrumentScenario) -> Decimal:
    quantity = position.intent.quantity
    return money(
        quantity
        * (
            (scenario.spread_points / Decimal("2") + scenario.slippage_points_per_side)
            * scenario.point_value_usd_per_unit
            + scenario.commission_usd_per_unit_per_side
        )
    )

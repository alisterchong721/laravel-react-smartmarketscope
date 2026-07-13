from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Iterable, Sequence

from .models import (
    Bar,
    Breaker,
    Confluence,
    Direction,
    EntryDecision,
    FairValueGap,
    GateDecision,
    MacroBiasRecord,
    MacroState,
    OrderBlock,
    Sweep,
    Zone,
)


def _require_complete(*bars: Bar) -> None:
    if not all(bar.complete for bar in bars):
        raise ValueError("MLR_INCOMPLETE_BAR")


def actionable_time(d1_confirmation: datetime, h4_confirmation: datetime) -> datetime:
    return max(d1_confirmation, h4_confirmation)


def macro_gate(record: MacroBiasRecord | None, decision_time: datetime) -> GateDecision:
    """Consume a certified PIT bias; every missing or non-directional state fails closed."""
    if record is None:
        return GateDecision(False, None, "BLOCKED_BY_UNCERTIFIED_MACRO_BIAS")
    timestamps = (decision_time, record.effective_at, record.expires_at, *record.first_received_at)
    if any(value.tzinfo is None or value.utcoffset() is None for value in timestamps):
        return GateDecision(False, None, "MLR_INPUT_INVALID_TIMEZONE_NAIVE_MACRO")
    required_text = (
        record.bias_id,
        record.model_or_rule_version,
        record.model_or_rule_sha256,
        record.validator_artifact_id,
        record.validator_sha256,
    )
    lineage_complete = (
        all(required_text)
        and bool(record.source_observation_ids)
        and bool(record.source_run_ids)
        and len(record.first_received_at) == len(record.source_observation_ids)
    )
    if record.certification_status != "CERTIFIED_POINT_IN_TIME" or not lineage_complete:
        return GateDecision(False, None, "BLOCKED_BY_UNCERTIFIED_MACRO_BIAS")
    if any(received > decision_time for received in record.first_received_at):
        return GateDecision(False, None, "MLR_TIMING_LEAKAGE")
    if not record.effective_at <= decision_time < record.expires_at:
        return GateDecision(False, None, "MACRO_NOT_EFFECTIVE_OR_EXPIRED")
    if record.state is MacroState.BULLISH:
        return GateDecision(True, Direction.BULLISH, "CERTIFIED_DIRECTIONAL_MACRO")
    if record.state is MacroState.BEARISH:
        return GateDecision(True, Direction.BEARISH, "CERTIFIED_DIRECTIONAL_MACRO")
    return GateDecision(False, None, f"MACRO_{record.state.value}_NO_TRADE")


def ema_completed(values: Sequence[float], period: int) -> list[float | None]:
    """EMA with an SMA seed and alpha=2/(period+1)."""
    if period <= 0:
        raise ValueError("period must be positive")
    output: list[float | None] = [None] * len(values)
    if len(values) < period:
        return output
    seed = sum(values[:period]) / period
    output[period - 1] = seed
    alpha = 2.0 / (period + 1.0)
    current = seed
    for index in range(period, len(values)):
        current = alpha * values[index] + (1.0 - alpha) * current
        output[index] = current
    return output


def ema_from_completed_bars(bars: Sequence[Bar], period: int) -> list[float | None]:
    _require_complete(*bars)
    return ema_completed([bar.close for bar in bars], period)


def atr_wilder(bars: Sequence[Bar], period: int = 14) -> list[float | None]:
    """Completed-bar Wilder ATR with an SMA true-range seed."""
    if period <= 0:
        raise ValueError("period must be positive")
    output: list[float | None] = [None] * len(bars)
    if not bars:
        return output
    true_ranges: list[float] = []
    for index, bar in enumerate(bars):
        _require_complete(bar)
        if index == 0:
            true_ranges.append(bar.high - bar.low)
        else:
            previous_close = bars[index - 1].close
            true_ranges.append(max(bar.high - bar.low, abs(bar.high - previous_close), abs(bar.low - previous_close)))
    if len(true_ranges) < period:
        return output
    current = sum(true_ranges[:period]) / period
    output[period - 1] = current
    for index in range(period, len(true_ranges)):
        current = ((period - 1) * current + true_ranges[index]) / period
        output[index] = current
    return output


def trend_context(close: float, ema20: float, ema50: float, direction: Direction) -> bool:
    if direction is Direction.BULLISH:
        return close < ema20 < ema50
    return close > ema20 > ema50


def detect_sweep(
    candle1: Bar,
    candle2: Bar,
    direction: Direction,
    body_ratio_limit: float = 0.50,
    full_body_above_below: bool = False,
    candle1_index: int = 0,
    candle2_index: int = 1,
) -> Sweep | None:
    _require_complete(candle1, candle2)
    if candle1.body == 0:
        return None
    ratio = candle2.body / candle1.body
    if ratio > body_ratio_limit:
        return None
    if direction is Direction.BULLISH:
        if candle1.close >= candle1.open:
            return None
        if not (candle2.low < candle1.low and candle2.close > candle1.low):
            return None
        if full_body_above_below and not candle2.open > candle1.low:
            return None
        reference = candle1.low
    else:
        if candle1.close <= candle1.open:
            return None
        if not (candle2.high > candle1.high and candle2.close < candle1.high):
            return None
        if full_body_above_below and not candle2.open < candle1.high:
            return None
        reference = candle1.high
    return Sweep(direction, candle1_index, candle2_index, reference, ratio, candle2.available_at)


def find_h4_confirmation(
    d1_candle2: Bar,
    d1_candle3: Bar,
    h4_bars: Sequence[Bar],
    direction: Direction,
    body_ratio_limit: float = 0.50,
    extension_bars: int = 3,
    contained_only: bool = False,
    through_d1_candle3: bool = False,
) -> Sweep | None:
    """Find the first native-adjacent H4 sweep in the configured D1 window."""
    _require_complete(d1_candle2, d1_candle3, *h4_bars)
    if contained_only:
        search_end = d1_candle2.available_at
    elif through_d1_candle3:
        search_end = d1_candle3.available_at
    else:
        if extension_bars not in {2, 3}:
            raise ValueError("H4 extension must be two or three completed bars")
        post_close = [bar for bar in h4_bars if bar.available_at > d1_candle2.available_at]
        if len(post_close) < extension_bars:
            return None
        search_end = post_close[extension_bars - 1].available_at
    candidates = [
        (index, bar)
        for index, bar in enumerate(h4_bars)
        if bar.start >= d1_candle2.start and bar.available_at <= search_end
    ]
    for pair in range(1, len(candidates)):
        first_index, first = candidates[pair - 1]
        second_index, second = candidates[pair]
        if second_index != first_index + 1:
            continue
        sweep = detect_sweep(first, second, direction, body_ratio_limit, candle1_index=first_index, candle2_index=second_index)
        if sweep is not None:
            return sweep
    return None


def detect_fvgs(bars: Sequence[Bar], direction: Direction) -> list[FairValueGap]:
    found: list[FairValueGap] = []
    for index in range(len(bars) - 2):
        first, _, third = bars[index : index + 3]
        _require_complete(first, bars[index + 1], third)
        if direction is Direction.BULLISH and first.high < third.low:
            found.append(FairValueGap(direction, index, index + 2, Zone(first.high, third.low), third.available_at))
        elif direction is Direction.BEARISH and first.low > third.high:
            found.append(FairValueGap(direction, index, index + 2, Zone(third.high, first.low), third.available_at))
    return found


def detect_order_blocks(
    bars: Sequence[Bar],
    direction: Direction,
    structure_lookback: int = 10,
    displacement_window: int = 3,
    displacement_atr: float = 1.0,
) -> list[OrderBlock]:
    """Select the latest opposite candle within K; never duplicate a candidate."""
    atr = atr_wilder(bars, 14)
    found: list[OrderBlock] = []
    used_candidates: set[int] = set()
    for displacement_index in range(structure_lookback, len(bars)):
        displacement = bars[displacement_index]
        _require_complete(displacement)
        atr_value = atr[displacement_index]
        if atr_value is None:
            continue
        previous = bars[displacement_index - structure_lookback : displacement_index]
        if direction is Direction.BULLISH:
            structure_break = displacement.close > max(bar.high for bar in previous)
        else:
            structure_break = displacement.close < min(bar.low for bar in previous)
        if not structure_break:
            continue
        candidates = range(max(0, displacement_index - displacement_window), displacement_index)
        opposite = [
            index
            for index in candidates
            if (bars[index].close < bars[index].open if direction is Direction.BULLISH else bars[index].close > bars[index].open)
        ]
        if not opposite:
            continue
        candidate_index = opposite[-1]
        if candidate_index in used_candidates:
            continue
        candidate = bars[candidate_index]
        displacement_size = (
            displacement.close - candidate.high
            if direction is Direction.BULLISH
            else candidate.low - displacement.close
        )
        if displacement_size < displacement_atr * atr_value:
            continue
        found.append(
            OrderBlock(
                direction,
                candidate_index,
                displacement_index,
                Zone(candidate.low, candidate.high),
                displacement.available_at,
            )
        )
        used_candidates.add(candidate_index)
    return found


def is_unmitigated_before(block: OrderBlock, bars: Sequence[Bar], before_index: int) -> bool:
    return not any(block.zone.intersects_bar(bar) for bar in bars[block.displacement_index + 1 : before_index])


def detect_breakers(bars: Sequence[Bar], source_blocks: Iterable[OrderBlock]) -> list[Breaker]:
    found: list[Breaker] = []
    for block in source_blocks:
        breaker_direction = Direction.BULLISH if block.direction is Direction.BEARISH else Direction.BEARISH
        break_index: int | None = None
        for index in range(block.displacement_index + 1, len(bars)):
            close = bars[index].close
            if (breaker_direction is Direction.BULLISH and close > block.zone.upper) or (
                breaker_direction is Direction.BEARISH and close < block.zone.lower
            ):
                break_index = index
                break
        if break_index is None:
            continue
        for index in range(break_index + 1, len(bars)):
            bar = bars[index]
            if not block.zone.intersects_bar(bar):
                continue
            previous = bars[index - 1]
            approach_valid = (
                breaker_direction is Direction.BULLISH
                and previous.close > block.zone.upper
            ) or (
                breaker_direction is Direction.BEARISH
                and previous.close < block.zone.lower
            )
            closes_valid = bar.close > block.zone.midpoint if breaker_direction is Direction.BULLISH else bar.close < block.zone.midpoint
            if approach_valid and closes_valid:
                found.append(Breaker(breaker_direction, block, break_index, index, block.zone, bar.available_at))
            break
    return found


def confluence(
    direction: Direction,
    family: str,
    first_zone: Zone,
    second_zone: Zone,
    first_available: datetime,
    second_available: datetime,
) -> Confluence | None:
    lower = max(first_zone.lower, second_zone.lower)
    upper = min(first_zone.upper, second_zone.upper)
    if upper <= lower:
        return None
    return Confluence(direction, family, Zone(lower, upper), max(first_available, second_available))


def component_confluence(
    family: str,
    first: FairValueGap | OrderBlock | Breaker,
    second: FairValueGap | OrderBlock | Breaker,
) -> Confluence | None:
    if first.direction is not second.direction:
        return None
    return confluence(first.direction, family, first.zone, second.zone, first.available_at, second.available_at)


def hierarchical_confluence(
    m15: Sequence[Confluence],
    m5: Sequence[Confluence],
    m1: Sequence[Confluence],
    direction: Direction,
    expiry: datetime,
) -> Confluence | None:
    """Return first ordered same-family three-stage strict intersection."""
    for broad in sorted(m15, key=lambda item: item.available_at):
        if broad.direction is not direction or broad.available_at >= expiry:
            continue
        for middle in sorted(m5, key=lambda item: item.available_at):
            if middle.direction is not direction or middle.family != broad.family or not broad.available_at < middle.available_at < expiry:
                continue
            refined = confluence(direction, broad.family, broad.zone, middle.zone, broad.available_at, middle.available_at)
            if refined is None:
                continue
            for trigger in sorted(m1, key=lambda item: item.available_at):
                if trigger.direction is not direction or trigger.family != broad.family or not middle.available_at < trigger.available_at < expiry:
                    continue
                final = confluence(direction, broad.family, refined.zone, trigger.zone, refined.available_at, trigger.available_at)
                if final is not None:
                    return final
    return None


def midpoint_entry(
    setup_id: str,
    candidate: Confluence,
    trade_time: datetime,
    trade_price: float,
    expiry: datetime,
    filled_setup_ids: set[str],
    executable_trade_proven: bool,
) -> EntryDecision:
    if setup_id in filled_setup_ids:
        return EntryDecision(False, None, "ONE_TRADE_PER_D1_SETUP", trade_time)
    if trade_time <= candidate.available_at:
        return EntryDecision(False, None, "COMPONENT_NOT_AVAILABLE", trade_time)
    if trade_time >= expiry:
        return EntryDecision(False, None, "SETUP_EXPIRED", trade_time)
    if trade_price != candidate.zone.midpoint:
        return EntryDecision(False, None, "MIDPOINT_NOT_TRADED", trade_time)
    if not executable_trade_proven:
        return EntryDecision(False, None, "MLR_FILL_UNPROVEN", trade_time)
    return EntryDecision(True, candidate.zone.midpoint, "ELIGIBLE_EXECUTABLE_MIDPOINT", trade_time)


def is_expired(at: datetime, expiry: datetime) -> bool:
    return at >= expiry


def protective_stop(
    direction: Direction,
    block_zone: Zone,
    point: float,
    pit_spread: float,
    units_documented: bool = True,
) -> float:
    if not units_documented:
        raise ValueError("MLR_COST_UNRESOLVED")
    buffer = max(Decimal(str(point)), Decimal(str(pit_spread)))
    boundary = Decimal(str(block_zone.lower if direction is Direction.BULLISH else block_zone.upper))
    return float(boundary - buffer if direction is Direction.BULLISH else boundary + buffer)


def exact_target(direction: Direction, fill: float, stop: float, total_cost_per_unit: float = 0.0) -> float:
    fill_decimal = Decimal(str(fill))
    stop_decimal = Decimal(str(stop))
    risk = abs(fill_decimal - stop_decimal) + Decimal(str(total_cost_per_unit))
    target = fill_decimal + 2 * risk if direction is Direction.BULLISH else fill_decimal - 2 * risk
    return float(target)


def frequency_permission(effective_setup_count: int) -> str:
    if effective_setup_count < 30:
        return "INSUFFICIENT_COMPLETE_SETUP_FREQUENCY"
    if effective_setup_count < 100:
        return "RULE_BASED_ONLY_ML_PROHIBITED"
    if effective_setup_count < 250:
        return "LOGISTIC_AND_SHALLOW_TREE_PERMITTED"
    return "XGBOOST_MAY_BE_CONSIDERED_UNDER_FROZEN_BUDGET"


def barrier_outcome(
    direction: Direction,
    bar: Bar,
    stop: float,
    target: float,
    valid_lower_timeframe_order: str | None = None,
) -> str:
    """Resolve one bar; unresolved dual reach is always adverse-first."""
    _require_complete(bar)
    stop_hit = bar.low <= stop if direction is Direction.BULLISH else bar.high >= stop
    target_hit = bar.high >= target if direction is Direction.BULLISH else bar.low <= target
    if stop_hit and target_hit:
        if valid_lower_timeframe_order == "TARGET_FIRST":
            return "TARGET"
        return "STOP"
    if stop_hit:
        return "STOP"
    if target_hit:
        return "TARGET"
    return "OPEN"

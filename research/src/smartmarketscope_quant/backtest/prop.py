from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from zoneinfo import ZoneInfo

from .types import AccountPoint, ZERO, money


class DrawdownMode(str, Enum):
    STATIC = "STATIC"
    TRAILING = "TRAILING"


class ValueBasis(str, Enum):
    BALANCE = "BALANCE"
    EQUITY = "EQUITY"


class PropOutcome(str, Enum):
    TARGET_REACHED = "TARGET_REACHED"
    DRAWDOWN_BREACH = "DRAWDOWN_BREACH"
    DAILY_DRAWDOWN_BREACH = "DAILY_DRAWDOWN_BREACH"
    TIMEOUT = "ONE_MONTH_TIMEOUT"
    INSUFFICIENT_COVERAGE = "INSUFFICIENT_ONE_MONTH_COVERAGE"


@dataclass(frozen=True, slots=True)
class PropRuleSpec:
    scenario_id: str
    rule_source: str
    starting_equity_usd: Decimal
    profit_target_usd: Decimal
    maximum_drawdown_usd: Decimal
    drawdown_mode: DrawdownMode
    drawdown_basis: ValueBasis
    target_basis: ValueBasis
    daily_drawdown_usd: Decimal | None = None
    daily_reset_timezone: str | None = None

    def __post_init__(self) -> None:
        if self.rule_source != "HYPOTHETICAL_GENERIC_NOT_PROP_FIRM_RULES":
            raise ValueError("Incomplete rules cannot be represented as a named prop-firm specification")
        if min(self.starting_equity_usd, self.profit_target_usd, self.maximum_drawdown_usd) <= ZERO:
            raise ValueError("Starting equity, target, and drawdown must be positive")
        if self.daily_drawdown_usd is not None and self.daily_drawdown_usd <= ZERO:
            raise ValueError("Daily drawdown must be positive")
        if (self.daily_drawdown_usd is None) != (self.daily_reset_timezone is None):
            raise ValueError("Daily drawdown and reset timezone must be specified together")


@dataclass(frozen=True, slots=True)
class PropPathResult:
    scenario_id: str
    outcome: PropOutcome
    event_timestamp: datetime
    ending_balance_usd: Decimal
    ending_equity_usd: Decimal
    active_drawdown_boundary_usd: Decimal
    peak_value_usd: Decimal
    points_evaluated: int


def add_calendar_month(timestamp: datetime) -> datetime:
    if timestamp.month == 12:
        year, month = timestamp.year + 1, 1
    else:
        year, month = timestamp.year, timestamp.month + 1
    day = min(timestamp.day, calendar.monthrange(year, month)[1])
    return timestamp.replace(year=year, month=month, day=day)


def _value(point: AccountPoint, basis: ValueBasis) -> Decimal:
    return point.balance_usd if basis is ValueBasis.BALANCE else point.equity_usd


def _local_day(timestamp: datetime, timezone_name: str) -> object:
    if timestamp.tzinfo is None:
        raise ValueError("Daily rule evaluation requires timezone-aware account points")
    return timestamp.astimezone(ZoneInfo(timezone_name)).date()


def evaluate_prop_path(points: list[AccountPoint], rules: PropRuleSpec) -> PropPathResult:
    if not points:
        raise ValueError("At least one account point is required")
    for previous, current in zip(points, points[1:]):
        if current.timestamp <= previous.timestamp:
            raise ValueError("Account points must be strictly chronological")
    if points[0].balance_usd != rules.starting_equity_usd or points[0].equity_usd != rules.starting_equity_usd:
        raise ValueError("Path must begin flat at scenario starting equity")

    horizon_end = add_calendar_month(points[0].timestamp)
    target = rules.starting_equity_usd + rules.profit_target_usd
    peak = rules.starting_equity_usd
    static_boundary = rules.starting_equity_usd - rules.maximum_drawdown_usd
    daily_key = None
    daily_start_balance = rules.starting_equity_usd
    last = points[0]
    evaluated = 0

    for point in points:
        if point.timestamp > horizon_end:
            break
        evaluated += 1
        last = point
        trailing_value = _value(point, rules.drawdown_basis)
        peak = max(peak, trailing_value)
        boundary = (
            static_boundary
            if rules.drawdown_mode is DrawdownMode.STATIC
            else peak - rules.maximum_drawdown_usd
        )

        if rules.daily_drawdown_usd is not None:
            assert rules.daily_reset_timezone is not None
            key = _local_day(point.timestamp, rules.daily_reset_timezone)
            if key != daily_key:
                daily_key = key
                daily_start_balance = point.balance_usd
            daily_boundary = daily_start_balance - rules.daily_drawdown_usd
            if point.equity_usd <= daily_boundary:
                return PropPathResult(
                    rules.scenario_id,
                    PropOutcome.DAILY_DRAWDOWN_BREACH,
                    point.timestamp,
                    point.balance_usd,
                    point.equity_usd,
                    money(daily_boundary),
                    money(peak),
                    evaluated,
                )

        if _value(point, rules.drawdown_basis) <= boundary:
            return PropPathResult(
                rules.scenario_id,
                PropOutcome.DRAWDOWN_BREACH,
                point.timestamp,
                point.balance_usd,
                point.equity_usd,
                money(boundary),
                money(peak),
                evaluated,
            )
        if _value(point, rules.target_basis) >= target:
            return PropPathResult(
                rules.scenario_id,
                PropOutcome.TARGET_REACHED,
                point.timestamp,
                point.balance_usd,
                point.equity_usd,
                money(boundary),
                money(peak),
                evaluated,
            )

    final_boundary = (
        static_boundary if rules.drawdown_mode is DrawdownMode.STATIC else peak - rules.maximum_drawdown_usd
    )
    if last.timestamp < horizon_end:
        return PropPathResult(
            rules.scenario_id,
            PropOutcome.INSUFFICIENT_COVERAGE,
            last.timestamp,
            last.balance_usd,
            last.equity_usd,
            money(final_boundary),
            money(peak),
            evaluated,
        )
    return PropPathResult(
        rules.scenario_id,
        PropOutcome.TIMEOUT,
        horizon_end,
        last.balance_usd,
        last.equity_usd,
        money(final_boundary),
        money(peak),
        evaluated,
    )


def rolling_one_month_evaluations(
    account_path: list[AccountPoint],
    rules: PropRuleSpec,
    start_indices: list[int],
) -> list[PropPathResult]:
    results = []
    for start_index in start_indices:
        if start_index < 0 or start_index >= len(account_path):
            raise ValueError("Rolling start index is out of range")
        base = account_path[start_index]
        if base.balance_usd != base.equity_usd:
            raise ValueError("Rolling window must start from a flat account point")
        horizon = add_calendar_month(base.timestamp)
        normalized = []
        for point in account_path[start_index:]:
            if point.timestamp > horizon:
                break
            normalized.append(
                AccountPoint(
                    point.timestamp,
                    money(rules.starting_equity_usd + point.balance_usd - base.balance_usd),
                    money(rules.starting_equity_usd + point.equity_usd - base.equity_usd),
                    point.event,
                )
            )
        results.append(evaluate_prop_path(normalized, rules))
    return results

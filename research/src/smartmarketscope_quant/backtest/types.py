from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


ZERO = Decimal("0")


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.00000001"))


class Side(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"

    @property
    def direction(self) -> Decimal:
        return Decimal("1") if self is Side.LONG else Decimal("-1")


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


@dataclass(frozen=True, slots=True)
class MarketBar:
    timestamp: datetime
    available_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    missing_before: bool = False

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo != self.available_at.tzinfo:
            raise ValueError("Bar timestamp and availability must use the same clock contract")
        if self.available_at < self.timestamp:
            raise ValueError("Bar availability cannot precede its label")
        if min(self.open, self.high, self.low, self.close) <= ZERO:
            raise ValueError("Prices must be positive")
        if self.high < self.low or not (self.low <= self.open <= self.high) or not (
            self.low <= self.close <= self.high
        ):
            raise ValueError("OHLC invariant failed")


@dataclass(frozen=True, slots=True)
class InstrumentScenario:
    scenario_id: str
    evidence_class: str
    currency: str
    point_value_usd_per_unit: Decimal
    contract_size_per_unit: Decimal
    min_quantity: Decimal
    quantity_step: Decimal
    max_quantity: Decimal
    leverage: Decimal
    spread_points: Decimal
    slippage_points_per_side: Decimal
    commission_usd_per_unit_per_side: Decimal
    financing_usd_per_unit_per_bar: Decimal = ZERO

    def __post_init__(self) -> None:
        if self.currency != "USD":
            raise ValueError("Current harness monetary accounting is USD-only")
        if self.evidence_class != "HYPOTHETICAL_SCENARIO_NOT_BROKER_FACT":
            raise ValueError("Unknown broker terms may only be represented as a labeled scenario")
        positive = (
            self.point_value_usd_per_unit,
            self.contract_size_per_unit,
            self.min_quantity,
            self.quantity_step,
            self.max_quantity,
            self.leverage,
        )
        if any(value <= ZERO for value in positive):
            raise ValueError("Point value, contract size, quantity rules, and leverage must be positive")
        if self.min_quantity > self.max_quantity:
            raise ValueError("Minimum quantity exceeds maximum")
        if any(
            value < ZERO
            for value in (
                self.spread_points,
                self.slippage_points_per_side,
                self.commission_usd_per_unit_per_side,
                self.financing_usd_per_unit_per_bar,
            )
        ):
            raise ValueError("Costs cannot be negative")


@dataclass(frozen=True, slots=True)
class TradeIntent:
    intent_id: str
    decision_timestamp: datetime
    activation_timestamp: datetime
    side: Side
    quantity: Decimal
    entry_order_type: OrderType
    entry_order_price: Decimal | None
    stop_price: Decimal
    target_price: Decimal
    max_holding_bars: int

    def __post_init__(self) -> None:
        if self.activation_timestamp < self.decision_timestamp:
            raise ValueError("Activation cannot precede decision")
        if self.quantity <= ZERO or self.stop_price <= ZERO or self.target_price <= ZERO:
            raise ValueError("Quantity and barriers must be positive")
        if self.entry_order_type is not OrderType.MARKET and self.entry_order_price is None:
            raise ValueError("Limit and stop entries require an order price")
        if self.max_holding_bars < 1:
            raise ValueError("max_holding_bars must be positive")


@dataclass(frozen=True, slots=True)
class Fill:
    timestamp: datetime
    reason: str
    transaction: str
    reference_price: Decimal
    fill_price: Decimal
    quantity: Decimal
    spread_cost_usd: Decimal
    slippage_cost_usd: Decimal
    commission_usd: Decimal
    evidence_class: str
    ambiguity: bool = False

    @property
    def total_cost_usd(self) -> Decimal:
        return money(self.spread_cost_usd + self.slippage_cost_usd + self.commission_usd)


@dataclass(slots=True)
class Position:
    intent: TradeIntent
    entry_fill: Fill
    bars_held: int = 0
    financing_cost_usd: Decimal = ZERO
    margin_used_usd: Decimal = ZERO


@dataclass(frozen=True, slots=True)
class TradeResult:
    intent_id: str
    side: Side
    quantity: Decimal
    entry: Fill
    exit: Fill
    gross_pnl_usd: Decimal
    spread_cost_usd: Decimal
    slippage_cost_usd: Decimal
    commission_usd: Decimal
    financing_cost_usd: Decimal
    net_pnl_usd: Decimal
    ambiguity: bool
    bars_held: int


@dataclass(frozen=True, slots=True)
class AccountPoint:
    timestamp: datetime
    balance_usd: Decimal
    equity_usd: Decimal
    event: str
    margin_used_usd: Decimal = ZERO
    free_margin_usd: Decimal = ZERO


@dataclass(slots=True)
class BacktestResult:
    starting_balance_usd: Decimal
    ending_balance_usd: Decimal
    trades: list[TradeResult] = field(default_factory=list)
    account_path: list[AccountPoint] = field(default_factory=list)
    event_log: list[dict] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class PositionSizeResult:
    quantity: Decimal
    risk_per_unit_usd: Decimal
    total_risk_usd: Decimal
    required_margin_usd: Decimal
    limiting_constraint: str

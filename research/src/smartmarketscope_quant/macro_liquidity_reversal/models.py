from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Direction(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class MacroState(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"
    CONFLICTING = "CONFLICTING"


@dataclass(frozen=True)
class MacroBiasRecord:
    bias_id: str
    state: MacroState
    effective_at: datetime
    expires_at: datetime
    source_observation_ids: tuple[str, ...]
    source_run_ids: tuple[str, ...]
    first_received_at: tuple[datetime, ...]
    revision_status: str
    model_or_rule_version: str
    model_or_rule_sha256: str
    validator_artifact_id: str
    validator_sha256: str
    certification_status: str
    score: float | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    direction: Direction | None
    reason: str


@dataclass(frozen=True)
class EntryDecision:
    eligible: bool
    price: float | None
    reason: str
    trade_time: datetime | None = None


@dataclass(frozen=True)
class Bar:
    start: datetime
    available_at: datetime
    open: float
    high: float
    low: float
    close: float
    complete: bool = True

    def __post_init__(self) -> None:
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("bar high violates OHLC range")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("bar low violates OHLC range")
        if self.available_at < self.start:
            raise ValueError("bar availability precedes start")

    @property
    def body(self) -> float:
        return abs(self.close - self.open)


@dataclass(frozen=True)
class Zone:
    lower: float
    upper: float

    def __post_init__(self) -> None:
        if self.upper < self.lower:
            raise ValueError("zone upper must be at least lower")

    @property
    def width(self) -> float:
        return self.upper - self.lower

    @property
    def midpoint(self) -> float:
        return (self.lower + self.upper) / 2.0

    def intersects_bar(self, bar: Bar) -> bool:
        return bar.high >= self.lower and bar.low <= self.upper


@dataclass(frozen=True)
class Sweep:
    direction: Direction
    candle1_index: int
    candle2_index: int
    reference_level: float
    body_ratio: float
    confirmation_time: datetime


@dataclass(frozen=True)
class FairValueGap:
    direction: Direction
    first_index: int
    third_index: int
    zone: Zone
    available_at: datetime


@dataclass(frozen=True)
class OrderBlock:
    direction: Direction
    candle_index: int
    displacement_index: int
    zone: Zone
    available_at: datetime


@dataclass(frozen=True)
class Breaker:
    direction: Direction
    source_order_block: OrderBlock
    break_index: int
    retest_index: int
    zone: Zone
    available_at: datetime


@dataclass(frozen=True)
class Confluence:
    direction: Direction
    family: str
    zone: Zone
    available_at: datetime

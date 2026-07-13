from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Sequence

import pandas as pd

from smartmarketscope_quant.backtest.config import load_execution_scenarios
from smartmarketscope_quant.backtest.types import InstrumentScenario

from .detectors import exact_target, protective_stop
from .frequency import TIMEFRAME_PATHS, _bars, _load_completed, _load_m1_windows
from .models import Bar, Direction, Zone


PROGRAM_ID = "QRP-MACRO-LIQUIDITY-REVERSAL-001"
MODE = "TECHNICAL_ONLY_ABLATION"
EXPOSURE_LABEL = "PREVIOUSLY_EXPOSED_WINDOW"
PRIMARY_SCENARIO = "NORMALIZED_MEDIUM_COST"
SOURCE_POINT = Decimal("0.1")
FAMILIES = ("C1_OB_FVG", "C2_FVG_BREAKER")
TIMEFRAMES = ("M15", "M5", "M1")
PRIMARY_STRATEGIES = (
    "M15_C1_OB_FVG",
    "M5_C1_OB_FVG",
    "M1_C1_OB_FVG",
    "M15_C2_FVG_BREAKER",
    "M5_C2_FVG_BREAKER",
    "M1_C2_FVG_BREAKER",
    "HIERARCHICAL_M15_M5_M1",
)


class TechnicalEconomicError(ValueError):
    pass


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _iso(value: datetime | None) -> str | None:
    return value.isoformat(sep=" ") if value is not None else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_hash(previous_hash: str | None, payload: dict[str, Any]) -> str:
    content = json.dumps(
        {"previous_event_hash": previous_hash, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(content).hexdigest()


def validate_hash_registry(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="ascii").splitlines() if line.strip()]
    previous: str | None = None
    for row in rows:
        if row["previous_event_hash"] != previous:
            raise TechnicalEconomicError("MLR_TECHNICAL_REGISTRY_CHAIN_BROKEN")
        expected = _canonical_hash(previous, row["payload"])
        if row["event_hash"] != expected:
            raise TechnicalEconomicError("MLR_TECHNICAL_REGISTRY_HASH_INVALID")
        previous = expected
    return rows


def validate_frequency_checkpoint(repo_root: Path, checkpoint_path: Path) -> dict[str, Any]:
    checkpoint = json.loads(checkpoint_path.read_text(encoding="ascii"))
    for relative, expected in checkpoint["sha256"].items():
        actual = _sha256(repo_root / relative)
        if actual != expected:
            raise TechnicalEconomicError(f"MLR_FROZEN_FREQUENCY_ARTIFACT_CHANGED:{relative}")
    summary = json.loads(
        (repo_root / "research/artifacts/macro_liquidity_reversal/frequency_summary.json").read_text()
    )
    counts = checkpoint["verified_counts"]
    if sum(summary["d1_trend_sweep_counts"].values()) != counts["trend_matched_d1_sweeps"]:
        raise TechnicalEconomicError("MLR_FROZEN_D1_SWEEP_COUNT_CHANGED")
    if sum(summary["d1_h4_confirmation_counts"].values()) != counts["d1_h4_confirmations"]:
        raise TechnicalEconomicError("MLR_FROZEN_D1_H4_COUNT_CHANGED")
    expected_timeframes = {
        "M15": counts["m15_midpoint_reach_diagnostics"],
        "M5": counts["m5_midpoint_reach_diagnostics"],
        "M1": counts["m1_midpoint_reach_diagnostics"],
        "HIERARCHICAL_M15_M5_M1": counts["hierarchical_midpoint_reach_diagnostics"],
    }
    for timeframe, expected in expected_timeframes.items():
        if summary["per_timeframe"][timeframe]["technical_complete_setups"] != expected:
            raise TechnicalEconomicError(f"MLR_FROZEN_SETUP_COUNT_CHANGED:{timeframe}")
    return checkpoint


@dataclass(frozen=True, slots=True)
class FrozenEvent:
    event_id: str
    direction: Direction
    d1_candle1_start: datetime
    d1_candle2_start: datetime
    d1_confirmation_time: datetime
    actionable_time: datetime
    expiry_time: datetime
    h4_confirmation_time: datetime


@dataclass(frozen=True, slots=True)
class Component:
    component_id: str
    event_id: str
    timeframe: str
    direction: Direction
    kind: str
    zone: Zone
    available_at: datetime


@dataclass(frozen=True, slots=True)
class TechnicalSetup:
    setup_id: str
    strategy_id: str
    event_id: str
    timeframe: str
    family: str
    direction: Direction
    available_at: datetime
    expiry_time: datetime
    confluence_zone: Zone
    block_zone: Zone
    block_kind: str
    component_ids: tuple[str, ...]
    entry_mode: str = "LIMIT_MIDPOINT"

    @property
    def entry_reference(self) -> Decimal:
        return _decimal(self.confluence_zone.midpoint)


@dataclass(frozen=True, slots=True)
class FillProof:
    status: str
    reason: str
    entry_reference: Decimal | None
    entry_bar_start: datetime | None
    entry_bar_available: datetime | None
    entry_bar_index: int | None
    evidence_class: str


@dataclass(frozen=True, slots=True)
class SimulatedPath:
    outcome: str
    exit_reference: Decimal | None
    exit_time: datetime | None
    exit_reason: str
    ambiguous: bool
    bars_held: int


class BarIndex:
    def __init__(self, bars: Sequence[Bar]) -> None:
        ordered = sorted(bars, key=lambda item: item.start)
        if len({bar.start for bar in ordered}) != len(ordered):
            raise TechnicalEconomicError("MLR_DUPLICATE_PATH_BAR")
        self.bars = ordered
        self.starts = [bar.start for bar in ordered]

    def window(self, start: datetime, end: datetime, include_start: bool = True) -> list[Bar]:
        first = bisect.bisect_left(self.starts, start) if include_start else bisect.bisect_right(self.starts, start)
        last = bisect.bisect_left(self.starts, end)
        return [bar for bar in self.bars[first:last] if bar.available_at <= end]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_frozen_events(artifact_root: Path) -> tuple[list[FrozenEvent], list[dict[str, str]]]:
    all_rows = _read_csv(artifact_root / "MLR_EVENT_REGISTRY.csv")
    confirmed = []
    for row in all_rows:
        if not (row["trend_context"] == "True" and row["d1_sweep"] == "True" and row["h4_sweep"] == "True"):
            continue
        confirmed.append(
            FrozenEvent(
                event_id=row["event_id"],
                direction=Direction(row["direction"]),
                d1_candle1_start=datetime.fromisoformat(row["d1_candle1_start"]),
                d1_candle2_start=datetime.fromisoformat(row["d1_candle2_start"]),
                d1_confirmation_time=datetime.fromisoformat(row["d1_confirmation_time"]),
                actionable_time=datetime.fromisoformat(row["actionable_time"]),
                expiry_time=datetime.fromisoformat(row["expiry_time"]),
                h4_confirmation_time=datetime.fromisoformat(row["h4_confirmation_time"]),
            )
        )
    if len(confirmed) != 89:
        raise TechnicalEconomicError(f"MLR_EXPECTED_89_FROZEN_EVENTS_GOT_{len(confirmed)}")
    return sorted(confirmed, key=lambda item: (item.actionable_time, item.event_id)), all_rows


def load_components(artifact_root: Path) -> dict[tuple[str, str, str], list[Component]]:
    sources = {
        "FVG": "MLR_FVG_REGISTRY.csv",
        "OB": "MLR_OB_REGISTRY.csv",
        "BREAKER": "MLR_BREAKER_REGISTRY.csv",
    }
    grouped: dict[tuple[str, str, str], list[Component]] = defaultdict(list)
    for kind, filename in sources.items():
        for row_number, row in enumerate(_read_csv(artifact_root / filename), start=1):
            component = Component(
                component_id=f"{kind}-{row_number:06d}",
                event_id=row["event_id"],
                timeframe=row["timeframe"],
                direction=Direction(row["direction"]),
                kind=kind,
                zone=Zone(float(row["lower"]), float(row["upper"])),
                available_at=datetime.fromisoformat(row["available_at"]),
            )
            grouped[(component.event_id, component.timeframe, kind)].append(component)
    for values in grouped.values():
        values.sort(key=lambda item: (item.available_at, item.component_id))
    return grouped


def _intersection(first: Zone, second: Zone) -> Zone | None:
    lower = max(first.lower, second.lower)
    upper = min(first.upper, second.upper)
    return Zone(lower, upper) if upper > lower else None


def _zone_touched_between(
    bars: BarIndex,
    zone: Zone,
    after: datetime,
    through: datetime,
) -> bool:
    return any(zone.intersects_bar(bar) for bar in bars.window(after, through, include_start=True) if bar.available_at > after)


def build_family_candidates(
    event: FrozenEvent,
    timeframe: str,
    family: str,
    components: dict[tuple[str, str, str], list[Component]],
    timeframe_bars: BarIndex,
) -> list[TechnicalSetup]:
    fvgs = components.get((event.event_id, timeframe, "FVG"), [])
    block_kind = "OB" if family == "C1_OB_FVG" else "BREAKER"
    blocks = components.get((event.event_id, timeframe, block_kind), [])
    candidates: list[TechnicalSetup] = []
    for fvg in fvgs:
        for block in blocks:
            overlap = _intersection(fvg.zone, block.zone)
            if overlap is None:
                continue
            available = max(fvg.available_at, block.available_at)
            if not (event.actionable_time <= available < event.expiry_time):
                continue
            if family == "C1_OB_FVG" and _zone_touched_between(
                timeframe_bars, block.zone, block.available_at, available
            ):
                continue
            candidates.append(
                TechnicalSetup(
                    setup_id=f"{event.event_id}-{timeframe}-{family}-{fvg.component_id}-{block.component_id}",
                    strategy_id=f"{timeframe}_{family}",
                    event_id=event.event_id,
                    timeframe=timeframe,
                    family=family,
                    direction=event.direction,
                    available_at=available,
                    expiry_time=event.expiry_time,
                    confluence_zone=overlap,
                    block_zone=block.zone,
                    block_kind=block_kind,
                    component_ids=(fvg.component_id, block.component_id),
                )
            )
    candidates.sort(
        key=lambda item: (
            item.available_at,
            item.confluence_zone.lower,
            item.confluence_zone.upper,
            item.component_ids,
        )
    )
    return candidates


def build_primary_setups(
    events: Sequence[FrozenEvent],
    components: dict[tuple[str, str, str], list[Component]],
    timeframe_indices: dict[str, BarIndex],
) -> tuple[list[TechnicalSetup], dict[tuple[str, str, str], list[TechnicalSetup]]]:
    all_candidates: dict[tuple[str, str, str], list[TechnicalSetup]] = {}
    primary: list[TechnicalSetup] = []
    for event in events:
        for timeframe in TIMEFRAMES:
            for family in FAMILIES:
                candidates = build_family_candidates(
                    event,
                    timeframe,
                    family,
                    components,
                    timeframe_indices[timeframe],
                )
                all_candidates[(event.event_id, timeframe, family)] = candidates
                if candidates:
                    primary.append(candidates[0])
    for event in events:
        hierarchical: list[TechnicalSetup] = []
        for family in FAMILIES:
            m15 = all_candidates[(event.event_id, "M15", family)]
            m5 = all_candidates[(event.event_id, "M5", family)]
            m1 = all_candidates[(event.event_id, "M1", family)]
            found: TechnicalSetup | None = None
            for broad in m15:
                for middle in m5:
                    if middle.available_at <= broad.available_at:
                        continue
                    refined = _intersection(broad.confluence_zone, middle.confluence_zone)
                    if refined is None:
                        continue
                    for trigger in m1:
                        if trigger.available_at <= middle.available_at:
                            continue
                        final = _intersection(refined, trigger.confluence_zone)
                        if final is None:
                            continue
                        found = TechnicalSetup(
                            setup_id=f"{event.event_id}-HIER-{family}",
                            strategy_id="HIERARCHICAL_M15_M5_M1",
                            event_id=event.event_id,
                            timeframe="HIERARCHICAL_M15_M5_M1",
                            family=family,
                            direction=event.direction,
                            available_at=trigger.available_at,
                            expiry_time=event.expiry_time,
                            confluence_zone=final,
                            block_zone=trigger.block_zone,
                            block_kind=trigger.block_kind,
                            component_ids=(*broad.component_ids, *middle.component_ids, *trigger.component_ids),
                        )
                        break
                    if found is not None:
                        break
                if found is not None:
                    break
            if found is not None:
                hierarchical.append(found)
        if hierarchical:
            primary.append(sorted(hierarchical, key=lambda item: (item.available_at, item.family))[0])
    return sorted(primary, key=lambda item: (item.strategy_id, item.available_at, item.event_id)), all_candidates


def prove_limit_fill(setup: TechnicalSetup, path: BarIndex) -> FillProof:
    bars = path.window(setup.available_at, setup.expiry_time, include_start=True)
    if not bars:
        return FillProof("INVALID_DATA", "NO_M1_PATH_BARS", None, None, None, None, "NO_PATH")
    limit = setup.entry_reference
    for absolute_offset, bar in enumerate(bars):
        crossed = _decimal(bar.low) < limit if setup.direction is Direction.BULLISH else _decimal(bar.high) > limit
        if crossed:
            return FillProof(
                "FILLED",
                "STRICT_M1_LIMIT_PENETRATION",
                limit,
                bar.start,
                bar.available_at,
                bisect.bisect_left(path.starts, bar.start),
                "M1_STRICT_PENETRATION_NO_FAVORABLE_IMPROVEMENT",
            )
        if setup.family == "C1_OB_FVG" and setup.block_zone.intersects_bar(bar):
            return FillProof(
                "NO_FILL",
                "OB_MITIGATED_BEFORE_MIDPOINT",
                None,
                None,
                None,
                None,
                "M1_BLOCK_TOUCH",
            )
    return FillProof("NO_FILL", "MIDPOINT_NOT_STRICTLY_PENETRATED", None, None, None, None, "M1_PATH")


def prove_next_open_fill(setup: TechnicalSetup, path: BarIndex) -> FillProof:
    bars = path.window(setup.available_at, setup.expiry_time, include_start=True)
    if not bars:
        return FillProof("INVALID_DATA", "NO_M1_PATH_BARS", None, None, None, None, "NO_PATH")
    bar = bars[0]
    return FillProof(
        "FILLED",
        "FIRST_SUBSEQUENT_M1_OPEN",
        _decimal(bar.open),
        bar.start,
        bar.available_at,
        bisect.bisect_left(path.starts, bar.start),
        "M1_NEXT_OPEN_CONTROL",
    )


def _barrier_hits(direction: Direction, bar: Bar, stop: Decimal, target: Decimal) -> tuple[bool, bool]:
    if direction is Direction.BULLISH:
        return _decimal(bar.low) <= stop, _decimal(bar.high) >= target
    return _decimal(bar.high) >= stop, _decimal(bar.low) <= target


def simulate_path(
    setup: TechnicalSetup,
    proof: FillProof,
    scenario: InstrumentScenario,
    path: BarIndex,
) -> tuple[SimulatedPath, dict[str, Decimal]]:
    if proof.status != "FILLED" or proof.entry_reference is None or proof.entry_bar_index is None:
        return (
            SimulatedPath(proof.status, None, None, proof.reason, False, 0),
            {},
        )
    spread = scenario.spread_points
    stop = _decimal(
        protective_stop(
            setup.direction,
            setup.block_zone,
            float(SOURCE_POINT),
            float(spread),
            units_documented=True,
        )
    )
    commission_points = (
        Decimal("2")
        * scenario.commission_usd_per_unit_per_side
        / scenario.point_value_usd_per_unit
    )
    spread_points = scenario.spread_points
    slippage_points = Decimal("2") * scenario.slippage_points_per_side
    known_cost_points = spread_points + slippage_points + commission_points
    risk_points = abs(proof.entry_reference - stop) + known_cost_points
    if (
        setup.direction is Direction.BULLISH
        and proof.entry_reference <= stop
    ) or (
        setup.direction is Direction.BEARISH
        and proof.entry_reference >= stop
    ):
        return (
            SimulatedPath(
                "NO_FILL",
                None,
                proof.entry_bar_available,
                "PROTECTIVE_STOP_BREACHED_BEFORE_CONTROL_ENTRY",
                False,
                0,
            ),
            {},
        )
    target = _decimal(exact_target(setup.direction, float(proof.entry_reference), float(stop), float(known_cost_points)))
    if setup.direction is Direction.BULLISH and not stop < proof.entry_reference < target:
        raise TechnicalEconomicError("MLR_INVALID_LONG_BARRIERS")
    if setup.direction is Direction.BEARISH and not target < proof.entry_reference < stop:
        raise TechnicalEconomicError("MLR_INVALID_SHORT_BARRIERS")

    bars = [
        bar
        for bar in path.bars[proof.entry_bar_index :]
        if bar.start < setup.expiry_time and bar.available_at <= setup.expiry_time
    ]
    if not bars:
        return SimulatedPath("INVALID_DATA", None, None, "NO_POST_FILL_PATH", False, 0), {}
    entry_bar = bars[0]
    stop_hit, target_hit = _barrier_hits(setup.direction, entry_bar, stop, target)
    entry_order_ambiguous = (
        setup.direction is Direction.BULLISH and _decimal(entry_bar.open) <= proof.entry_reference
    ) or (
        setup.direction is Direction.BEARISH and _decimal(entry_bar.open) >= proof.entry_reference
    )
    if stop_hit:
        ambiguous = target_hit or entry_order_ambiguous
        outcome = "AMBIGUOUS_ADVERSE_FIRST" if ambiguous else "LOSS_1R"
        simulated = SimulatedPath(outcome, stop, entry_bar.available_at, "ENTRY_BAR_STOP_ADVERSE", ambiguous, 1)
        return simulated, {"stop": stop, "target": target, "risk_points": risk_points}

    for bars_held, bar in enumerate(bars[1:], start=2):
        if setup.direction is Direction.BULLISH and _decimal(bar.open) <= stop:
            return (
                SimulatedPath("LOSS_1R", _decimal(bar.open), bar.start, "STOP_GAP_OPEN", False, bars_held),
                {"stop": stop, "target": target, "risk_points": risk_points},
            )
        if setup.direction is Direction.BEARISH and _decimal(bar.open) >= stop:
            return (
                SimulatedPath("LOSS_1R", _decimal(bar.open), bar.start, "STOP_GAP_OPEN", False, bars_held),
                {"stop": stop, "target": target, "risk_points": risk_points},
            )
        stop_hit, target_hit = _barrier_hits(setup.direction, bar, stop, target)
        if stop_hit and target_hit:
            return (
                SimulatedPath(
                    "AMBIGUOUS_ADVERSE_FIRST",
                    stop,
                    bar.available_at,
                    "M1_DUAL_BARRIER_ADVERSE_FIRST",
                    True,
                    bars_held,
                ),
                {"stop": stop, "target": target, "risk_points": risk_points},
            )
        if stop_hit:
            return (
                SimulatedPath("LOSS_1R", stop, bar.available_at, "STOP", False, bars_held),
                {"stop": stop, "target": target, "risk_points": risk_points},
            )
        if target_hit:
            return (
                SimulatedPath("WIN_2R", target, bar.available_at, "TARGET_2R", False, bars_held),
                {"stop": stop, "target": target, "risk_points": risk_points},
            )
    final = bars[-1]
    return (
        SimulatedPath("TIMEOUT", _decimal(final.close), final.available_at, "D1_CANDLE_3_EXPIRY", False, len(bars)),
        {"stop": stop, "target": target, "risk_points": risk_points},
    )


def _economic_row(
    setup: TechnicalSetup,
    proof: FillProof,
    simulated: SimulatedPath,
    barriers: dict[str, Decimal],
    scenario: InstrumentScenario,
    event: FrozenEvent,
) -> dict[str, Any]:
    base = {
        "program_id": PROGRAM_ID,
        "mode": MODE,
        "exposure_label": EXPOSURE_LABEL,
        "strategy_id": setup.strategy_id,
        "setup_id": setup.setup_id,
        "event_id": setup.event_id,
        "timeframe": setup.timeframe,
        "family": setup.family,
        "direction": setup.direction.value,
        "scenario_id": scenario.scenario_id,
        "cost_evidence_class": scenario.evidence_class,
        "d1_candle2_start": _iso(event.d1_candle2_start),
        "decision_time": _iso(setup.available_at),
        "expiry_time": _iso(setup.expiry_time),
        "confluence_lower": setup.confluence_zone.lower,
        "confluence_upper": setup.confluence_zone.upper,
        "block_lower": setup.block_zone.lower,
        "block_upper": setup.block_zone.upper,
        "block_kind": setup.block_kind,
        "component_ids": "|".join(setup.component_ids),
        "fill_status": simulated.outcome if simulated.outcome in {"NO_FILL", "INVALID_DATA"} else proof.status,
        "fill_reason": (
            simulated.exit_reason if simulated.outcome in {"NO_FILL", "INVALID_DATA"} else proof.reason
        ),
        "fill_evidence_class": proof.evidence_class,
        "entry_reference_points": proof.entry_reference,
        "entry_bar_start": _iso(proof.entry_bar_start),
        "entry_path_available_at": _iso(proof.entry_bar_available),
        "outcome": simulated.outcome,
        "exit_reason": simulated.exit_reason,
        "exit_reference_points": simulated.exit_reference,
        "exit_time": _iso(simulated.exit_time),
        "ambiguous_adverse_first": simulated.ambiguous,
        "bars_held_m1": simulated.bars_held,
        "protected_data_accesses": 0,
        "final_holdout_accesses": 0,
    }
    if simulated.outcome in {"NO_FILL", "INVALID_DATA"} or proof.entry_reference is None or simulated.exit_reference is None:
        return {
            **base,
            "stop_reference_points": None,
            "target_reference_points": None,
            "risk_points": None,
            "gross_movement_points": None,
            "spread_cost_points": 0,
            "slippage_cost_points": 0,
            "commission_cost_points": 0,
            "financing_cost_points": 0,
            "net_points": None,
            "gross_r": None,
            "net_r": None,
            "holding_hours": None,
            "actual_entry_fill_points": None,
            "actual_exit_fill_points": None,
            "cost_adjusted_entry_points": None,
            "cost_adjusted_exit_points": None,
        }
    direction = Decimal("1") if setup.direction is Direction.BULLISH else Decimal("-1")
    gross = direction * (simulated.exit_reference - proof.entry_reference)
    spread_cost = scenario.spread_points
    slippage_cost = Decimal("2") * scenario.slippage_points_per_side
    commission_cost = (
        Decimal("2") * scenario.commission_usd_per_unit_per_side / scenario.point_value_usd_per_unit
    )
    holding_seconds = max(0.0, (simulated.exit_time - proof.entry_bar_available).total_seconds())
    financing_intervals = int(holding_seconds // 86400)
    financing_cost = (
        Decimal(financing_intervals)
        * scenario.financing_usd_per_unit_per_bar
        / scenario.point_value_usd_per_unit
    )
    net = gross - spread_cost - slippage_cost - commission_cost - financing_cost
    risk = barriers["risk_points"]
    half_spread_slippage = scenario.spread_points / Decimal("2") + scenario.slippage_points_per_side
    cost_adjusted_entry = proof.entry_reference + direction * half_spread_slippage
    cost_adjusted_exit = simulated.exit_reference - direction * half_spread_slippage
    reconciled = direction * (cost_adjusted_exit - cost_adjusted_entry) - commission_cost - financing_cost
    if abs(reconciled - net) > Decimal("0.00000001"):
        raise TechnicalEconomicError("MLR_GROSS_COST_NET_RECONCILIATION_FAILED")
    return {
        **base,
        "stop_reference_points": barriers["stop"],
        "target_reference_points": barriers["target"],
        "risk_points": risk,
        "gross_movement_points": gross,
        "spread_cost_points": spread_cost,
        "slippage_cost_points": slippage_cost,
        "commission_cost_points": commission_cost,
        "financing_cost_points": financing_cost,
        "net_points": net,
        "gross_r": gross / risk,
        "net_r": net / risk,
        "holding_hours": Decimal(str(holding_seconds / 3600.0)),
        # The frozen source has no bid/ask quotes. The conservatively proven
        # midpoint limit is therefore the simulated fill, while hypothetical
        # spread and slippage remain separately reported scenario costs.
        "actual_entry_fill_points": proof.entry_reference,
        "actual_exit_fill_points": simulated.exit_reference,
        "cost_adjusted_entry_points": cost_adjusted_entry,
        "cost_adjusted_exit_points": cost_adjusted_exit,
    }


def simulate_setup(
    setup: TechnicalSetup,
    path: BarIndex,
    scenarios: Sequence[InstrumentScenario],
    event: FrozenEvent,
) -> list[dict[str, Any]]:
    proof = prove_limit_fill(setup, path) if setup.entry_mode == "LIMIT_MIDPOINT" else prove_next_open_fill(setup, path)
    rows = []
    for scenario in scenarios:
        simulated, barriers = simulate_path(setup, proof, scenario, path)
        rows.append(_economic_row(setup, proof, simulated, barriers, scenario, event))
    return rows


def _d1_bar_map(d1_frame: pd.DataFrame) -> dict[datetime, Bar]:
    return {bar.start: bar for bar in _bars(d1_frame)}


def build_generic_control(setup: TechnicalSetup) -> TechnicalSetup:
    return TechnicalSetup(
        setup_id=f"CONTROL-GENERIC-{setup.setup_id}",
        strategy_id=f"CONTROL_DIRECTION_GENERIC__{setup.strategy_id}",
        event_id=setup.event_id,
        timeframe=setup.timeframe,
        family=setup.family,
        direction=setup.direction,
        available_at=setup.available_at,
        expiry_time=setup.expiry_time,
        confluence_zone=setup.confluence_zone,
        block_zone=setup.block_zone,
        block_kind=setup.block_kind,
        component_ids=setup.component_ids,
        entry_mode="MARKET_NEXT_M1_OPEN",
    )


def build_event_control(
    event_id: str,
    direction: Direction,
    available_at: datetime,
    expiry: datetime,
    candle2: Bar,
    strategy_id: str,
) -> TechnicalSetup:
    boundary = candle2.low if direction is Direction.BULLISH else candle2.high
    return TechnicalSetup(
        setup_id=f"{strategy_id}-{event_id}",
        strategy_id=strategy_id,
        event_id=event_id,
        timeframe="M1_CONTROL",
        family="GENERIC_DIRECTIONAL_ENTRY",
        direction=direction,
        available_at=available_at,
        expiry_time=expiry,
        confluence_zone=Zone(boundary, boundary),
        block_zone=Zone(boundary, boundary),
        block_kind="D1_CANDLE2_EXTREME",
        component_ids=(),
        entry_mode="MARKET_NEXT_M1_OPEN",
    )


def _to_serializable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _to_serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_serializable(item) for item in value]
    return value


def _max_drawdown(values: Sequence[Decimal]) -> Decimal:
    equity = Decimal("0")
    peak = Decimal("0")
    worst = Decimal("0")
    for value in values:
        equity += value
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return worst


def _longest_negative_streak(values: Sequence[Decimal]) -> int:
    longest = current = 0
    for value in values:
        if value < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def summarize_rows(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "eligible_setups": 0,
            "filled_trades": 0,
            "no_fills": 0,
            "invalid_data": 0,
            "wins": 0,
            "losses": 0,
            "timeouts": 0,
            "ambiguous_adverse_first": 0,
        }
    unique_setups = {row["setup_id"] for row in rows}
    filled = [row for row in rows if row["outcome"] not in {"NO_FILL", "INVALID_DATA"}]
    ordered = sorted(filled, key=lambda row: (row["exit_time"], row["setup_id"]))
    net_values = [_decimal(row["net_r"]) for row in ordered]
    gross_values = [_decimal(row["gross_r"]) for row in ordered]
    wins = [row for row in filled if row["outcome"] == "WIN_2R"]
    losses = [row for row in filled if row["outcome"] == "LOSS_1R"]
    ambiguous = [row for row in filled if row["outcome"] == "AMBIGUOUS_ADVERSE_FIRST"]
    resolved_count = len(wins) + len(losses) + len(ambiguous)
    positive = [value for value in net_values if value > 0]
    negative = [value for value in net_values if value < 0]
    yearly: dict[str, dict[str, Any]] = {}
    for row in ordered:
        year = row["d1_candle2_start"][:4]
        data = yearly.setdefault(year, {"trades": 0, "net_r": Decimal("0")})
        data["trades"] += 1
        data["net_r"] += _decimal(row["net_r"])
    direction: dict[str, dict[str, Any]] = {}
    for side in Direction:
        side_rows = [row for row in filled if row["direction"] == side.value]
        side_values = [_decimal(row["net_r"]) for row in side_rows]
        direction[side.value] = {
            "filled_trades": len(side_rows),
            "total_net_r": sum(side_values, Decimal("0")),
            "average_net_r": sum(side_values, Decimal("0")) / len(side_values) if side_values else None,
            "wins": sum(row["outcome"] == "WIN_2R" for row in side_rows),
        }
    observed_years = {str(year) for year in range(2017, 2027)}
    active_years = set(yearly)
    profitable_years = sum(item["net_r"] > 0 for item in yearly.values())
    avg_win = sum(positive, Decimal("0")) / len(positive) if positive else None
    avg_loss = abs(sum(negative, Decimal("0")) / len(negative)) if negative else None
    break_even = avg_loss / (avg_win + avg_loss) if avg_win is not None and avg_loss is not None else None
    gross_profit = sum(positive, Decimal("0"))
    gross_loss = abs(sum(negative, Decimal("0")))
    return {
        "eligible_setups": len(unique_setups),
        "filled_trades": len(filled),
        "no_fills": sum(row["outcome"] == "NO_FILL" for row in rows),
        "invalid_data": sum(row["outcome"] == "INVALID_DATA" for row in rows),
        "wins": len(wins),
        "losses": len(losses),
        "timeouts": sum(row["outcome"] == "TIMEOUT" for row in filled),
        "ambiguous_adverse_first": len(ambiguous),
        "win_rate_filled_resolved": Decimal(len(wins)) / resolved_count if resolved_count else None,
        "target_before_stop_rate": Decimal(len(wins)) / resolved_count if resolved_count else None,
        "average_gross_r": sum(gross_values, Decimal("0")) / len(gross_values) if gross_values else None,
        "average_net_r": sum(net_values, Decimal("0")) / len(net_values) if net_values else None,
        "median_net_r": _decimal(statistics.median(net_values)) if net_values else None,
        "expectancy_net_r": sum(net_values, Decimal("0")) / len(net_values) if net_values else None,
        "profit_factor": gross_profit / gross_loss if gross_loss > 0 else None,
        "total_net_r": sum(net_values, Decimal("0")),
        "maximum_closed_equity_drawdown_r": _max_drawdown(net_values),
        "longest_losing_streak": _longest_negative_streak(net_values),
        "average_holding_hours": (
            sum((_decimal(row["holding_hours"]) for row in filled), Decimal("0")) / len(filled)
            if filled
            else None
        ),
        "profitable_year_fraction": Decimal(profitable_years) / len(yearly) if yearly else None,
        "profitable_years": profitable_years,
        "active_years": len(yearly),
        "years_without_trades": sorted(observed_years - active_years),
        "by_year": yearly,
        "by_direction": direction,
        "average_positive_net_r": avg_win,
        "average_negative_net_r_magnitude": avg_loss,
        "minimum_break_even_win_rate_observed_net_r": break_even,
    }


def summarize_all(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    strategies = sorted({row["strategy_id"] for row in rows})
    scenarios = sorted({row["scenario_id"] for row in rows})
    return {
        strategy: {
            scenario: summarize_rows(
                [row for row in rows if row["strategy_id"] == strategy and row["scenario_id"] == scenario]
            )
            for scenario in scenarios
        }
        for strategy in strategies
    }


def _write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row}) if rows else ["status"]
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        if rows:
            writer.writerows(_to_serializable(dict(row)) for row in rows)
        else:
            writer.writerow({"status": "NO_ROWS"})


def _percentage(value: Any) -> str:
    return "N/A" if value is None else f"{float(value) * 100:.2f}%"


def _number(value: Any, digits: int = 3) -> str:
    return "N/A" if value is None else f"{float(value):.{digits}f}"


def write_primary_report(repo_root: Path, summary: dict[str, Any], frozen_counts: dict[str, Any]) -> None:
    lines = [
        "# MLR Technical Primary Backtest",
        "",
        "Status: `TECHNICAL_ONLY_ABLATION`",
        "",
        "This is the frozen first economic pass of the mechanical technical structure. It is not the intended macro-first strategy, not broker-calibrated, and not evidence of FTMO or Lucid readiness. Every historical row is `PREVIOUSLY_EXPOSED_WINDOW`.",
        "",
        "## Preservation Check",
        "",
        f"The frozen detector/frequency checkpoint passed: {frozen_counts['trend_matched_d1_sweeps']} D1 sweeps, {frozen_counts['d1_h4_confirmations']} D1+H4 confirmations, and midpoint-reach diagnostics {frozen_counts['m15_midpoint_reach_diagnostics']}/{frozen_counts['m5_midpoint_reach_diagnostics']}/{frozen_counts['m1_midpoint_reach_diagnostics']}/{frozen_counts['hierarchical_midpoint_reach_diagnostics']} for M15/M5/M1/hierarchical.",
        "",
        "Economic eligible setup counts may differ because this pass prospectively selects the first confirmed confluence before knowing whether its midpoint fills; the earlier diagnostics searched for a later midpoint reach. No frozen file was regenerated.",
        "",
        "## Medium-Cost Primary Results",
        "",
        "| Strategy | Eligible | Filled | No fill | Wins | Losses | Timeout | Ambiguous | Win rate | Avg net R | Total net R | Max DD R |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for strategy in PRIMARY_STRATEGIES:
        item = summary.get(strategy, {}).get(PRIMARY_SCENARIO, {})
        lines.append(
            "| "
            + " | ".join(
                [
                    strategy,
                    str(item.get("eligible_setups", 0)),
                    str(item.get("filled_trades", 0)),
                    str(item.get("no_fills", 0)),
                    str(item.get("wins", 0)),
                    str(item.get("losses", 0)),
                    str(item.get("timeouts", 0)),
                    str(item.get("ambiguous_adverse_first", 0)),
                    _percentage(item.get("win_rate_filled_resolved")),
                    _number(item.get("average_net_r")),
                    _number(item.get("total_net_r")),
                    _number(item.get("maximum_closed_equity_drawdown_r")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Cost Sensitivity",
            "",
            "| Strategy | Scenario | Filled | Wins | Losses | Timeout | Ambiguous | Avg gross R | Avg net R | Median net R | Profit factor | Total net R | Max DD R | Break-even win rate |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for strategy in PRIMARY_STRATEGIES:
        for scenario in (
            "NORMALIZED_LOW_COST",
            "NORMALIZED_MEDIUM_COST",
            "NORMALIZED_HIGH_COST",
        ):
            item = summary.get(strategy, {}).get(scenario, {})
            lines.append(
                "| "
                + " | ".join(
                    [
                        strategy,
                        scenario,
                        str(item.get("filled_trades", 0)),
                        str(item.get("wins", 0)),
                        str(item.get("losses", 0)),
                        str(item.get("timeouts", 0)),
                        str(item.get("ambiguous_adverse_first", 0)),
                        _number(item.get("average_gross_r")),
                        _number(item.get("average_net_r")),
                        _number(item.get("median_net_r")),
                        _number(item.get("profit_factor")),
                        _number(item.get("total_net_r")),
                        _number(item.get("maximum_closed_equity_drawdown_r")),
                        _percentage(item.get("minimum_break_even_win_rate_observed_net_r")),
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Medium-Cost Stability Detail",
            "",
            "| Strategy | Avg hold hours | Profitable years | Active years | Years without trades | Bull fills / net R | Bear fills / net R |",
            "| --- | ---: | ---: | ---: | --- | ---: | ---: |",
        ]
    )
    for strategy in PRIMARY_STRATEGIES:
        item = summary.get(strategy, {}).get(PRIMARY_SCENARIO, {})
        sides = item.get("by_direction", {})
        bull = sides.get("BULLISH", {})
        bear = sides.get("BEARISH", {})
        lines.append(
            f"| {strategy} | {_number(item.get('average_holding_hours'))} | "
            f"{item.get('profitable_years', 0)} | {item.get('active_years', 0)} | "
            f"{', '.join(item.get('years_without_trades', [])) or 'None'} | "
            f"{bull.get('filled_trades', 0)} / {_number(bull.get('total_net_r'))} | "
            f"{bear.get('filled_trades', 0)} / {_number(bear.get('total_net_r'))} |"
        )
    lines.extend(
        [
            "",
            "## Accounting",
            "",
            "Stops use `max(0.1 source-file quantum, scenario spread)` beyond the selected OB/breaker. Targets use the frozen exact-2R function with known round-trip spread, slippage, and commission points. Path-dependent hypothetical financing is charged to realized net R per full 24 source-clock hours and does not move the ex-ante barrier.",
            "",
            "M1 strict penetration proves a conservative limit reach with no favorable price improvement. Equality alone is no fill. Entry-bar favorable targets are ignored; unresolved M1 dual barriers are adverse-first and separately flagged.",
            "",
            "The low/medium/high costs are sensitivity scenarios, not Pepperstone facts. Dollar PnL is not claimed.",
        ]
    )
    (repo_root / "MLR_TECHNICAL_PRIMARY_BACKTEST.md").write_text("\n".join(lines) + "\n", encoding="ascii")


def write_control_report(repo_root: Path, primary: dict[str, Any], controls: dict[str, Any]) -> None:
    lines = [
        "# MLR Technical Control Comparison",
        "",
        "Status: `TECHNICAL_ONLY_ABLATION`",
        "",
        "All comparisons use normalized medium-cost R on previously exposed history.",
        "",
        "| Strategy | Avg net R | Matched generic avg net R | Increment | D1+H4 generic avg net R |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    d1h4 = controls.get("CONTROL_D1_H4_GENERIC", {}).get(PRIMARY_SCENARIO, {})
    for strategy in PRIMARY_STRATEGIES:
        result = primary.get(strategy, {}).get(PRIMARY_SCENARIO, {})
        generic = controls.get(f"CONTROL_DIRECTION_GENERIC__{strategy}", {}).get(PRIMARY_SCENARIO, {})
        result_avg = result.get("average_net_r")
        generic_avg = generic.get("average_net_r")
        increment = _decimal(result_avg) - _decimal(generic_avg) if result_avg is not None and generic_avg is not None else None
        lines.append(
            f"| {strategy} | {_number(result_avg)} | {_number(generic_avg)} | {_number(increment)} | {_number(d1h4.get('average_net_r'))} |"
        )
    d1 = controls.get("CONTROL_D1_ONLY_GENERIC", {}).get(PRIMARY_SCENARIO, {})
    lines.extend(
        [
            "",
            f"No-trade control: 0 trades, 0 R. D1-only generic: {d1.get('filled_trades', 0)} fills, {_number(d1.get('average_net_r'))} average net R. D1+H4 generic: {d1h4.get('filled_trades', 0)} fills, {_number(d1h4.get('average_net_r'))} average net R.",
            "",
            "The matched generic control preserves each setup's direction, activation, block, stop, target, expiry, and costs but enters at the next M1 open. It tests the midpoint-mitigation entry increment. D1-only and D1+H4 controls use the D1 candle-2 reversal extreme as the protective block and therefore are broader directional controls, not identical-trade counterfactuals.",
        ]
    )
    (repo_root / "MLR_TECHNICAL_CONTROL_COMPARISON.md").write_text("\n".join(lines) + "\n", encoding="ascii")


def run_primary(repo_root: Path) -> dict[str, Any]:
    artifact_root = repo_root / "research/artifacts/macro_liquidity_reversal"
    checkpoint_path = artifact_root / "governance/MLR_FREQUENCY_CHECKPOINT_20260713T123112+0800.json"
    checkpoint = validate_frequency_checkpoint(repo_root, checkpoint_path)
    registry = validate_hash_registry(artifact_root / "MLR_TECHNICAL_ECONOMIC_EXPERIMENT_REGISTRY.jsonl")
    if registry[-1]["payload"]["status"] not in {"PREREGISTERED", "STARTED", "STARTED_RETRY"}:
        raise TechnicalEconomicError("MLR_TECHNICAL_PRIMARY_NOT_PREREGISTERED")

    events, all_event_rows = load_frozen_events(artifact_root)
    event_by_id = {event.event_id: event for event in events}
    frames = {name: _load_completed(repo_root / relative) for name, relative in TIMEFRAME_PATHS.items()}
    d1_sweep_rows = [
        row for row in all_event_rows if row["trend_context"] == "True" and row["d1_sweep"] == "True"
    ]
    m1_request_rows = [
        {
            "actionable_time": row["actionable_time"] or row["d1_confirmation_time"],
            "expiry_time": row["expiry_time"],
        }
        for row in d1_sweep_rows
    ]
    m1_path = next((repo_root / "dataset").glob("NAS100_M1_*.csv"))
    frames["M1"] = _load_m1_windows(m1_path, m1_request_rows)
    indices = {timeframe: BarIndex(_bars(frames[timeframe])) for timeframe in TIMEFRAMES}
    components = load_components(artifact_root)
    setups, _ = build_primary_setups(events, components, indices)
    scenarios = load_execution_scenarios(repo_root / "research/config/execution_scenarios.json")

    primary_rows: list[dict[str, Any]] = []
    generic_rows: list[dict[str, Any]] = []
    for setup in setups:
        event = event_by_id[setup.event_id]
        primary_rows.extend(simulate_setup(setup, indices["M1"], scenarios, event))
        generic_rows.extend(simulate_setup(build_generic_control(setup), indices["M1"], scenarios, event))

    d1_map = _d1_bar_map(frames["D1"])
    d1_control_rows: list[dict[str, Any]] = []
    for row in d1_sweep_rows:
        direction = Direction(row["direction"])
        candle2_start = datetime.fromisoformat(row["d1_candle2_start"])
        event = FrozenEvent(
            event_id=row["event_id"],
            direction=direction,
            d1_candle1_start=datetime.fromisoformat(row["d1_candle1_start"]),
            d1_candle2_start=candle2_start,
            d1_confirmation_time=datetime.fromisoformat(row["d1_confirmation_time"]),
            actionable_time=datetime.fromisoformat(row["d1_confirmation_time"]),
            expiry_time=datetime.fromisoformat(row["expiry_time"]),
            h4_confirmation_time=(
                datetime.fromisoformat(row["h4_confirmation_time"])
                if row["h4_confirmation_time"]
                else datetime.fromisoformat(row["d1_confirmation_time"])
            ),
        )
        setup = build_event_control(
            event.event_id,
            direction,
            event.d1_confirmation_time,
            event.expiry_time,
            d1_map[candle2_start],
            "CONTROL_D1_ONLY_GENERIC",
        )
        d1_control_rows.extend(simulate_setup(setup, indices["M1"], scenarios, event))

    d1h4_control_rows: list[dict[str, Any]] = []
    for event in events:
        setup = build_event_control(
            event.event_id,
            event.direction,
            event.actionable_time,
            event.expiry_time,
            d1_map[event.d1_candle2_start],
            "CONTROL_D1_H4_GENERIC",
        )
        d1h4_control_rows.extend(simulate_setup(setup, indices["M1"], scenarios, event))

    control_rows = [*generic_rows, *d1_control_rows, *d1h4_control_rows]
    primary_summary = summarize_all(primary_rows)
    control_summary = summarize_all(control_rows)
    summary = {
        "schema_version": "1.0.0",
        "program_id": PROGRAM_ID,
        "experiment_id": "MLR-TECH-ECO-001",
        "status": MODE,
        "full_macro_strategy_status": "BLOCKED_BY_UNCERTIFIED_MACRO_BIAS",
        "historical_exposure": EXPOSURE_LABEL,
        "cost_evidence_class": "HYPOTHETICAL_SCENARIO_NOT_BROKER_FACT",
        "frozen_frequency_checkpoint_sha256": _sha256(checkpoint_path),
        "primary_results": primary_summary,
        "control_results": {
            "NO_TRADE_CONTROL": {
                scenario.scenario_id: {
                    "eligible_setups": 0,
                    "filled_trades": 0,
                    "total_net_r": "0",
                    "maximum_closed_equity_drawdown_r": "0",
                }
                for scenario in scenarios
            },
            **control_summary,
        },
        "counts": {
            "frozen_d1_sweeps": len(d1_sweep_rows),
            "frozen_d1_h4_events": len(events),
            "primary_setup_rows": len(setups),
            "primary_trade_scenario_rows": len(primary_rows),
            "control_trade_scenario_rows": len(control_rows),
        },
        "prohibitions": {
            "post_2026_06_28_access": False,
            "final_holdout_access": False,
            "dollar_pnl_claim": False,
            "macro_strategy_claim": False,
            "automatic_promotion": False,
        },
    }
    serializable = _to_serializable(summary)
    (artifact_root / "MLR_TECHNICAL_PRIMARY_SUMMARY.json").write_text(
        json.dumps(serializable, indent=2, ensure_ascii=True) + "\n", encoding="ascii"
    )
    _write_csv(artifact_root / "MLR_TECHNICAL_PRIMARY_TRADES.csv", primary_rows)
    _write_csv(artifact_root / "MLR_TECHNICAL_CONTROL_TRADES.csv", control_rows)
    _write_csv(
        artifact_root / "MLR_TECHNICAL_PATH_AMBIGUITIES.csv",
        [row for row in primary_rows if row["ambiguous_adverse_first"]],
    )
    write_primary_report(artifact_root, serializable["primary_results"], checkpoint["verified_counts"])
    write_control_report(
        artifact_root,
        serializable["primary_results"],
        serializable["control_results"],
    )
    return serializable


def main() -> int:
    parser = argparse.ArgumentParser(description="Frozen MLR technical-only economic simulation")
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args()
    result = run_primary(args.repo_root.resolve())
    print(json.dumps(result["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

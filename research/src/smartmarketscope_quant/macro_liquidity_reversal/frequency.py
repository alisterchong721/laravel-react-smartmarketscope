from __future__ import annotations

import argparse
import csv
import gzip
import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .detectors import (
    actionable_time,
    confluence,
    detect_breakers,
    detect_fvgs,
    detect_order_blocks,
    detect_sweep,
    ema_from_completed_bars,
    find_h4_confirmation,
    frequency_permission,
    is_unmitigated_before,
    trend_context,
)
from .models import Bar, Breaker, Confluence, Direction, FairValueGap, OrderBlock, Zone


TIMEFRAME_PATHS = {
    "M15": "research/artifacts/processed_data/v1/NAS100_M15_completed_v1.csv.gz",
    "M5": "research/artifacts/processed_data/v1/NAS100_M5_canonical_v1.csv.gz",
    "H4": "research/artifacts/processed_data/v1/NAS100_H4_completed_v1.csv.gz",
    "D1": "research/artifacts/processed_data/v1/NAS100_Daily_completed_v1.csv.gz",
}


def _load_completed(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, compression="gzip")
    frame = frame.loc[frame["research_eligible"].astype(str).str.lower().eq("true")].copy()
    frame["bar_start_source"] = pd.to_datetime(frame["bar_start_source"])
    frame["available_at_source"] = pd.to_datetime(frame["available_at_source"])
    frame.sort_values("bar_start_source", inplace=True)
    frame.reset_index(drop=True, inplace=True)
    return frame


def _bars(frame: pd.DataFrame) -> list[Bar]:
    return [
        Bar(
            row.bar_start_source.to_pydatetime(),
            row.available_at_source.to_pydatetime(),
            float(row.open_completed),
            float(row.high_completed),
            float(row.low_completed),
            float(row.close_completed),
        )
        for row in frame.itertuples(index=False)
    ]


def _d1_events(d1: pd.DataFrame, h4: pd.DataFrame) -> list[dict[str, Any]]:
    d1_bars = _bars(d1)
    h4_bars = _bars(h4)
    ema20 = ema_from_completed_bars(d1_bars, 20)
    ema50 = ema_from_completed_bars(d1_bars, 50)
    events: list[dict[str, Any]] = []
    for candle2_index in range(1, len(d1_bars) - 1):
        if ema20[candle2_index] is None or ema50[candle2_index] is None:
            continue
        candle1 = d1_bars[candle2_index - 1]
        candle2 = d1_bars[candle2_index]
        for direction in Direction:
            in_trend = trend_context(candle2.close, float(ema20[candle2_index]), float(ema50[candle2_index]), direction)
            sweep = detect_sweep(candle1, candle2, direction, candle1_index=candle2_index - 1, candle2_index=candle2_index)
            if sweep is None and not in_trend:
                continue
            event: dict[str, Any] = {
                "event_id": f"D1-{candle2.start:%Y%m%d}-{direction.value}",
                "direction": direction.value,
                "d1_candle1_start": candle1.start.isoformat(sep=" "),
                "d1_candle2_start": candle2.start.isoformat(sep=" "),
                "d1_confirmation_time": candle2.available_at.isoformat(sep=" "),
                "trend_context": in_trend,
                "d1_sweep": sweep is not None,
                "d1_body_ratio": sweep.body_ratio if sweep else None,
                "h4_sweep": False,
                "h4_confirmation_time": None,
                "actionable_time": None,
                "expiry_time": d1_bars[candle2_index + 1].available_at.isoformat(sep=" "),
                "higher_timeframe_data_complete": True,
                "macro_certified": False,
                "full_strategy_eligible": False,
                "block_reason": "BLOCKED_BY_UNCERTIFIED_MACRO_BIAS",
            }
            if in_trend and sweep is not None:
                post_close = [bar for bar in h4_bars if bar.available_at > candle2.available_at]
                if len(post_close) < 3:
                    event["higher_timeframe_data_complete"] = False
                else:
                    h4_sweep = find_h4_confirmation(candle2, d1_bars[candle2_index + 1], h4_bars, direction)
                    if h4_sweep:
                        event["h4_sweep"] = True
                        event["h4_confirmation_time"] = h4_sweep.confirmation_time.isoformat(sep=" ")
                        event["actionable_time"] = actionable_time(candle2.available_at, h4_sweep.confirmation_time).isoformat(sep=" ")
            events.append(event)
    return events


def _slice_with_warmup(frame: pd.DataFrame, start: datetime, end: datetime, warmup: int = 50) -> pd.DataFrame:
    available = frame["available_at_source"].to_numpy()
    first = max(0, int(available.searchsorted(pd.Timestamp(start).to_datetime64(), side="left")) - warmup)
    last = int(available.searchsorted(pd.Timestamp(end).to_datetime64(), side="right"))
    return frame.iloc[first:last].copy().reset_index(drop=True)


def _component_candidates(
    bars: list[Bar], direction: Direction, actionable: datetime, expiry: datetime
) -> tuple[list[FairValueGap], list[OrderBlock], list[Breaker]]:
    fvgs = [x for x in detect_fvgs(bars, direction) if actionable <= x.available_at <= expiry]
    blocks = [x for x in detect_order_blocks(bars, direction) if actionable <= x.available_at <= expiry]
    opposite_blocks = detect_order_blocks(bars, Direction.BEARISH if direction is Direction.BULLISH else Direction.BULLISH)
    breakers = [x for x in detect_breakers(bars, opposite_blocks) if x.direction is direction and actionable <= x.available_at <= expiry]
    return fvgs, blocks, breakers


def _first_touch_index(bars: list[Bar], level: float, after: datetime, expiry: datetime) -> int | None:
    for index, bar in enumerate(bars):
        if bar.available_at <= after or bar.available_at > expiry:
            continue
        if bar.low <= level <= bar.high:
            return index
    return None


def _confluences(
    bars: list[Bar],
    direction: Direction,
    fvgs: list[FairValueGap],
    blocks: list[OrderBlock],
    breakers: list[Breaker],
    expiry: datetime,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for fvg in fvgs:
        for block in blocks:
            candidate = confluence(direction, "C1_OB_FVG", fvg.zone, block.zone, fvg.available_at, block.available_at)
            if candidate is None:
                continue
            touch_index = _first_touch_index(bars, candidate.zone.midpoint, candidate.available_at, expiry)
            if touch_index is None or not is_unmitigated_before(block, bars, touch_index):
                continue
            candidates.append({"confluence": candidate, "block": block, "touch_index": touch_index})
    for fvg in fvgs:
        for breaker in breakers:
            candidate = confluence(direction, "C2_FVG_BREAKER", fvg.zone, breaker.zone, fvg.available_at, breaker.available_at)
            if candidate is None:
                continue
            touch_index = _first_touch_index(bars, candidate.zone.midpoint, candidate.available_at, expiry)
            if touch_index is not None:
                candidates.append({"confluence": candidate, "block": breaker, "touch_index": touch_index})
    candidates.sort(key=lambda item: (item["confluence"].available_at, item["touch_index"], item["confluence"].family))
    return candidates


def _study_timeframe(event: dict[str, Any], frame: pd.DataFrame, timeframe: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    actionable = datetime.fromisoformat(event["actionable_time"])
    expiry = datetime.fromisoformat(event["expiry_time"])
    window = _slice_with_warmup(frame, actionable, expiry)
    bars = _bars(window)
    direction = Direction(event["direction"])
    fvgs, blocks, breakers = _component_candidates(bars, direction, actionable, expiry)
    confluences = _confluences(bars, direction, fvgs, blocks, breakers, expiry)
    first_by_family: dict[str, dict[str, Any]] = {}
    for item in confluences:
        first_by_family.setdefault(item["confluence"].family, item)
    result = {
        "event_id": event["event_id"],
        "timeframe": timeframe,
        "direction": direction.value,
        "fvg_count": len(fvgs),
        "ob_count": len(blocks),
        "breaker_count": len(breakers),
        "c1_midpoint_reach_count": int("C1_OB_FVG" in first_by_family),
        "c2_midpoint_reach_count": int("C2_FVG_BREAKER" in first_by_family),
        "first_family": confluences[0]["confluence"].family if confluences else None,
        "first_confluence_time": confluences[0]["confluence"].available_at.isoformat(sep=" ") if confluences else None,
        "first_midpoint_reach_time": bars[confluences[0]["touch_index"]].available_at.isoformat(sep=" ") if confluences else None,
        "technical_complete_setup": bool(confluences),
        "execution_status": "MIDPOINT_REACHED_NOT_FILL_PROOF" if confluences else "NO_COMPLETE_TECHNICAL_SETUP",
    }
    zones: list[dict[str, Any]] = []
    for kind, components in (("FVG", fvgs), ("OB", blocks), ("BREAKER", breakers)):
        for component in components:
            zones.append(
                {
                    "event_id": event["event_id"],
                    "timeframe": timeframe,
                    "direction": direction.value,
                    "zone_type": kind,
                    "lower": component.zone.lower,
                    "upper": component.zone.upper,
                    "available_at": component.available_at.isoformat(sep=" "),
                }
            )
    for item in confluences:
        component = item["confluence"]
        zones.append(
            {
                "event_id": event["event_id"],
                "timeframe": timeframe,
                "direction": direction.value,
                "zone_type": component.family,
                "lower": component.zone.lower,
                "upper": component.zone.upper,
                "available_at": component.available_at.isoformat(sep=" "),
            }
        )
    return result, zones


def _load_m1_windows(path: Path, events: list[dict[str, Any]]) -> pd.DataFrame:
    intervals = sorted(
        (datetime.fromisoformat(event["actionable_time"]) - timedelta(minutes=60), datetime.fromisoformat(event["expiry_time"]))
        for event in events
    )
    merged: list[list[datetime]] = []
    for start, end in intervals:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    pieces: list[pd.DataFrame] = []
    for chunk in pd.read_csv(path, sep="\t", chunksize=250_000):
        timestamps = pd.to_datetime(chunk["<DATE>"] + " " + chunk["<TIME>"])
        mask = pd.Series(False, index=chunk.index)
        for start, end in merged:
            mask |= (timestamps >= start) & (timestamps < end)
        if not mask.any():
            continue
        selected = chunk.loc[mask].copy()
        selected["bar_start_source"] = timestamps.loc[mask]
        selected["available_at_source"] = selected["bar_start_source"] + pd.Timedelta(minutes=1)
        selected.rename(
            columns={"<OPEN>": "open_completed", "<HIGH>": "high_completed", "<LOW>": "low_completed", "<CLOSE>": "close_completed"},
            inplace=True,
        )
        selected["research_eligible"] = True
        pieces.append(selected[["bar_start_source", "available_at_source", "open_completed", "high_completed", "low_completed", "close_completed", "research_eligible"]])
    if not pieces:
        return pd.DataFrame(columns=["bar_start_source", "available_at_source", "open_completed", "high_completed", "low_completed", "close_completed", "research_eligible"])
    return pd.concat(pieces, ignore_index=True).sort_values("bar_start_source").drop_duplicates("bar_start_source").reset_index(drop=True)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("status\nNO_ROWS\n", encoding="utf-8")
        return
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _hierarchical_result(
    event: dict[str, Any], zone_rows: list[dict[str, Any]], m1_frame: pd.DataFrame
) -> dict[str, Any]:
    family_names = {"C1_OB_FVG", "C2_FVG_BREAKER"}
    candidates = [
        dict(row)
        for row in zone_rows
        if row["event_id"] == event["event_id"] and row["zone_type"] in family_names
    ]
    for row in candidates:
        row["_available"] = datetime.fromisoformat(row["available_at"])
        row["_zone"] = Zone(float(row["lower"]), float(row["upper"]))
    m15 = sorted((row for row in candidates if row["timeframe"] == "M15"), key=lambda row: row["_available"])
    m5 = sorted((row for row in candidates if row["timeframe"] == "M5"), key=lambda row: row["_available"])
    m1 = sorted((row for row in candidates if row["timeframe"] == "M1"), key=lambda row: row["_available"])
    for broad in m15:
        for middle in m5:
            if middle["zone_type"] != broad["zone_type"] or middle["_available"] <= broad["_available"]:
                continue
            middle_overlap = confluence(
                Direction(event["direction"]),
                broad["zone_type"],
                broad["_zone"],
                middle["_zone"],
                broad["_available"],
                middle["_available"],
            )
            if middle_overlap is None:
                continue
            for trigger in m1:
                if trigger["zone_type"] != broad["zone_type"] or trigger["_available"] <= middle["_available"]:
                    continue
                final = confluence(
                    Direction(event["direction"]),
                    broad["zone_type"],
                    middle_overlap.zone,
                    trigger["_zone"],
                    middle_overlap.available_at,
                    trigger["_available"],
                )
                if final is None:
                    continue
                expiry = datetime.fromisoformat(event["expiry_time"])
                bars = _bars(_slice_with_warmup(m1_frame, final.available_at, expiry, warmup=0))
                touch = _first_touch_index(bars, final.zone.midpoint, final.available_at, expiry)
                if touch is not None:
                    return {
                        "event_id": event["event_id"],
                        "timeframe": "HIERARCHICAL_M15_M5_M1",
                        "direction": event["direction"],
                        "fvg_count": 0,
                        "ob_count": 0,
                        "breaker_count": 0,
                        "c1_midpoint_reach_count": int(final.family == "C1_OB_FVG"),
                        "c2_midpoint_reach_count": int(final.family == "C2_FVG_BREAKER"),
                        "first_family": final.family,
                        "first_confluence_time": final.available_at.isoformat(sep=" "),
                        "first_midpoint_reach_time": bars[touch].available_at.isoformat(sep=" "),
                        "technical_complete_setup": True,
                        "execution_status": "HIERARCHICAL_MIDPOINT_REACHED_NOT_FILL_PROOF",
                    }
    return {
        "event_id": event["event_id"],
        "timeframe": "HIERARCHICAL_M15_M5_M1",
        "direction": event["direction"],
        "fvg_count": 0,
        "ob_count": 0,
        "breaker_count": 0,
        "c1_midpoint_reach_count": 0,
        "c2_midpoint_reach_count": 0,
        "first_family": None,
        "first_confluence_time": None,
        "first_midpoint_reach_time": None,
        "technical_complete_setup": False,
        "execution_status": "NO_HIERARCHICAL_TECHNICAL_SETUP",
    }


def _effective_nonoverlap(rows: list[dict[str, Any]], events_by_id: dict[str, dict[str, Any]]) -> int:
    eligible = sorted(
        (events_by_id[row["event_id"]] for row in rows if row["technical_complete_setup"]),
        key=lambda event: event["actionable_time"],
    )
    count = 0
    last_expiry: datetime | None = None
    for event in eligible:
        start = datetime.fromisoformat(event["actionable_time"])
        expiry = datetime.fromisoformat(event["expiry_time"])
        if last_expiry is None or start > last_expiry:
            count += 1
            last_expiry = expiry
    return count


def _gap_and_cluster_metrics(rows: list[dict[str, Any]], events_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    completed = [row for row in rows if row["technical_complete_setup"]]
    reach_times = sorted(datetime.fromisoformat(row["first_midpoint_reach_time"]) for row in completed)
    gaps = [(later - earlier).total_seconds() / 3600.0 for earlier, later in zip(reach_times, reach_times[1:])]
    intervals = sorted(
        (
            datetime.fromisoformat(events_by_id[row["event_id"]]["actionable_time"]),
            datetime.fromisoformat(events_by_id[row["event_id"]]["expiry_time"]),
        )
        for row in completed
    )
    cluster_sizes: list[int] = []
    cluster_end: datetime | None = None
    cluster_size = 0
    for start, end in intervals:
        if cluster_end is None or start > cluster_end:
            if cluster_size:
                cluster_sizes.append(cluster_size)
            cluster_end = end
            cluster_size = 1
        else:
            cluster_end = max(cluster_end, end)
            cluster_size += 1
    if cluster_size:
        cluster_sizes.append(cluster_size)
    overlapping = [size for size in cluster_sizes if size > 1]
    return {
        "average_gap_hours": sum(gaps) / len(gaps) if gaps else None,
        "maximum_gap_hours": max(gaps) if gaps else None,
        "overlapping_cluster_count": len(overlapping),
        "setups_in_overlapping_clusters": sum(overlapping),
    }


def _write_blocked_outputs(output_root: Path) -> None:
    _write_csv(
        output_root / "MLR_MACRO_BIAS_REGISTRY.csv",
        [
            {
                "registry_id": "MLR-MACRO-GATE-001",
                "certification_status": "NOT_CERTIFIED",
                "eligible_bias_days": 0,
                "coverage_start": None,
                "coverage_end": None,
                "state": "UNKNOWN",
                "failure_code": "BLOCKED_BY_UNCERTIFIED_MACRO_BIAS",
            }
        ],
    )
    (output_root / "MLR_SPLIT_MANIFEST.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "status": "NOT_RUN_BLOCKED_BY_UNCERTIFIED_MACRO_BIAS",
                "splits": [],
                "purging": "NOT_APPLICABLE",
                "embargo": "NOT_APPLICABLE",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_csv(output_root / "MLR_PREDICTIONS.csv", [{"status": "NOT_RUN_BLOCKED_BY_UNCERTIFIED_MACRO_BIAS"}])
    _write_csv(output_root / "MLR_TRADE_LOG.csv", [{"status": "NOT_RUN_BLOCKED_BY_UNCERTIFIED_MACRO_BIAS"}])


def _write_layer_registry(
    output_root: Path,
    summary: dict[str, Any],
    setup_rows: list[dict[str, Any]],
    events_by_id: dict[str, dict[str, Any]],
) -> None:
    economic_not_run = {
        "trade_count": "NOT_RUN",
        "gross_result": "NOT_RUN",
        "spread": "NOT_RUN",
        "slippage": "NOT_RUN",
        "commission": "NOT_RUN",
        "net_result": "NOT_RUN",
        "drawdown": "NOT_RUN",
        "lower_tail_fold_result": "NOT_RUN",
        "incremental_economic_contribution": "NOT_RUN",
    }
    rows: list[dict[str, Any]] = []
    trend_total = sum(summary["trend_context_days"].values())
    d1_total = sum(summary["d1_trend_sweep_counts"].values())
    h4_total = sum(summary["d1_h4_confirmation_counts"].values())
    controls = [
        ("TECHNICAL_ONLY_TREND_CONTEXT", trend_total, trend_total, summary["trend_context_days"], {}),
        ("TECHNICAL_ONLY_D1_SWEEP", trend_total, d1_total, summary["d1_trend_sweep_counts"], {}),
        ("TECHNICAL_ONLY_D1_H4", d1_total, h4_total, summary["d1_h4_confirmation_counts"], {}),
    ]
    for name, before, after, direction, years in controls:
        rows.append(
            {
                "layer": name,
                "mode": "TECHNICAL_ONLY_ABLATION",
                "setups_before": before,
                "setups_after": after,
                "frequency_retention": after / before if before else None,
                "direction_dependence": json.dumps(direction, sort_keys=True),
                "year_dependence": json.dumps(years, sort_keys=True),
                "apparent_change_only_frequency": True,
                **economic_not_run,
            }
        )
    for timeframe in ("M15", "M5", "M1", "HIERARCHICAL_M15_M5_M1"):
        metrics = summary["per_timeframe"][timeframe]
        for family, key, count_field in (
            ("OB_FVG", "c1_midpoint_reaches", "c1_midpoint_reach_count"),
            ("FVG_BREAKER", "c2_midpoint_reaches", "c2_midpoint_reach_count"),
        ):
            after = metrics[key]
            family_rows = [
                row
                for row in setup_rows
                if row["timeframe"] == timeframe and row[count_field] == 1
            ]
            family_direction = {direction.value: 0 for direction in Direction}
            family_year: dict[str, int] = {}
            for row in family_rows:
                family_direction[row["direction"]] += 1
                year = events_by_id[row["event_id"]]["d1_candle2_start"][:4]
                family_year[year] = family_year.get(year, 0) + 1
            rows.append(
                {
                    "layer": f"TECHNICAL_ONLY_D1_H4_{timeframe}_{family}",
                    "mode": "TECHNICAL_ONLY_ABLATION",
                    "setups_before": h4_total,
                    "setups_after": after,
                    "frequency_retention": after / h4_total if h4_total else None,
                    "direction_dependence": json.dumps(family_direction, sort_keys=True),
                    "year_dependence": json.dumps(family_year, sort_keys=True),
                    "apparent_change_only_frequency": True,
                    **economic_not_run,
                }
            )
    rows.extend(
        [
            {"layer": "MACRO_ONLY_DIRECTIONAL_CONTROL", "mode": "FULL_STRATEGY_CONTROL", "setups_before": 0, "setups_after": 0, "frequency_retention": None, "direction_dependence": "{}", "year_dependence": "{}", "apparent_change_only_frequency": True, **economic_not_run},
            {"layer": "DIRECTION_MATCHED_GENERIC_ENTRY", "mode": "FULL_STRATEGY_CONTROL", "setups_before": 0, "setups_after": 0, "frequency_retention": None, "direction_dependence": "{}", "year_dependence": "{}", "apparent_change_only_frequency": True, **economic_not_run},
            {"layer": "NO_TRADE_CONTROL", "mode": "CONTROL", "setups_before": 0, "setups_after": 0, "frequency_retention": None, "direction_dependence": "{}", "year_dependence": "{}", "apparent_change_only_frequency": True, **economic_not_run},
        ]
    )
    _write_csv(output_root / "MLR_TECHNICAL_LAYER_REGISTRY.csv", rows)


def run(repo_root: Path) -> dict[str, Any]:
    output_root = repo_root / "research/artifacts/macro_liquidity_reversal"
    frames = {name: _load_completed(repo_root / relative) for name, relative in TIMEFRAME_PATHS.items()}
    all_events = _d1_events(frames["D1"], frames["H4"])
    confirmed = [row for row in all_events if row["trend_context"] and row["d1_sweep"] and row["h4_sweep"]]
    m1_path = next((repo_root / "dataset").glob("NAS100_M1_*.csv"))
    frames["M1"] = _load_m1_windows(m1_path, confirmed)
    setup_rows: list[dict[str, Any]] = []
    zone_rows: list[dict[str, Any]] = []
    for event in confirmed:
        for timeframe in ("M15", "M5", "M1"):
            result, zones = _study_timeframe(event, frames[timeframe], timeframe)
            setup_rows.append(result)
            zone_rows.extend(zones)
    for event in confirmed:
        setup_rows.append(_hierarchical_result(event, zone_rows, frames["M1"]))
    _write_csv(output_root / "MLR_EVENT_REGISTRY.csv", all_events)
    _write_csv(output_root / "MLR_SETUP_REGISTRY.csv", setup_rows)
    _write_csv(output_root / "MLR_ZONE_REGISTRY.csv", zone_rows)
    _write_csv(output_root / "MLR_FVG_REGISTRY.csv", [row for row in zone_rows if row["zone_type"] == "FVG"])
    _write_csv(output_root / "MLR_OB_REGISTRY.csv", [row for row in zone_rows if row["zone_type"] == "OB"])
    _write_csv(output_root / "MLR_BREAKER_REGISTRY.csv", [row for row in zone_rows if row["zone_type"] == "BREAKER"])
    _write_csv(
        output_root / "MLR_CONFLUENCE_REGISTRY.csv",
        [row for row in zone_rows if row["zone_type"] in {"C1_OB_FVG", "C2_FVG_BREAKER"}],
    )
    _write_blocked_outputs(output_root)
    trend_days = {
        direction.value: sum(1 for row in all_events if row["direction"] == direction.value and row["trend_context"])
        for direction in Direction
    }
    sweep_counts = {
        direction.value: sum(1 for row in all_events if row["direction"] == direction.value and row["d1_sweep"])
        for direction in Direction
    }
    d1_trend_sweeps = {
        direction.value: sum(
            1 for row in all_events if row["direction"] == direction.value and row["trend_context"] and row["d1_sweep"]
        )
        for direction in Direction
    }
    h4_confirmed = {
        direction.value: sum(
            1
            for row in all_events
            if row["direction"] == direction.value and row["trend_context"] and row["d1_sweep"] and row["h4_sweep"]
        )
        for direction in Direction
    }
    per_timeframe = {}
    events_by_id = {event["event_id"]: event for event in confirmed}
    for timeframe in ("M15", "M5", "M1", "HIERARCHICAL_M15_M5_M1"):
        rows = [row for row in setup_rows if row["timeframe"] == timeframe]
        by_year: dict[str, int] = {}
        by_direction: dict[str, int] = {direction.value: 0 for direction in Direction}
        for row in rows:
            if not row["technical_complete_setup"]:
                continue
            year = events_by_id[row["event_id"]]["d1_candle2_start"][:4]
            by_year[year] = by_year.get(year, 0) + 1
            by_direction[row["direction"]] += 1
        per_timeframe[timeframe] = {
            "d1_h4_windows": len(rows),
            "fvg_count": sum(row["fvg_count"] for row in rows),
            "ob_count": sum(row["ob_count"] for row in rows),
            "breaker_count": sum(row["breaker_count"] for row in rows),
            "c1_midpoint_reaches": sum(row["c1_midpoint_reach_count"] for row in rows),
            "c2_midpoint_reaches": sum(row["c2_midpoint_reach_count"] for row in rows),
            "technical_complete_setups": sum(bool(row["technical_complete_setup"]) for row in rows),
            "effective_nonoverlapping_setups": _effective_nonoverlap(rows, events_by_id),
            "technical_complete_by_year": by_year,
            "technical_complete_by_direction": by_direction,
            "frequency_permission": frequency_permission(_effective_nonoverlap(rows, events_by_id)),
            **_gap_and_cluster_metrics(rows, events_by_id),
        }
    delays = [
        (datetime.fromisoformat(event["actionable_time"]) - datetime.fromisoformat(event["d1_confirmation_time"])).total_seconds() / 3600.0
        for event in confirmed
    ]
    summary = {
        "schema_version": "1.0.0",
        "program_id": "QRP-MACRO-LIQUIDITY-REVERSAL-001",
        "status": "BLOCKED_BY_UNCERTIFIED_MACRO_BIAS",
        "certified_macro_bias_days": 0,
        "trend_context_days": trend_days,
        "d1_sweep_counts_unfiltered": sweep_counts,
        "d1_trend_sweep_counts": d1_trend_sweeps,
        "d1_h4_confirmation_counts": h4_confirmed,
        "d1_sweeps_matching_certified_macro_bias": {direction.value: 0 for direction in Direction},
        "actionable_delay_hours": {
            "average": sum(delays) / len(delays) if delays else None,
            "maximum": max(delays) if delays else None,
        },
        "per_timeframe": per_timeframe,
        "full_strategy_complete_setups": 0,
        "setups_blocked_by_missing_macro_bias": len(confirmed),
        "setups_blocked_by_stale_macro_bias": 0,
        "d1_sweeps_without_h4_pattern": sum(d1_trend_sweeps.values()) - sum(h4_confirmed.values()),
        "setups_blocked_by_incomplete_higher_timeframe_data": sum(
            1
            for row in all_events
            if row["trend_context"] and row["d1_sweep"] and not row["higher_timeframe_data_complete"]
        ),
        "full_strategy_frequency_permission": frequency_permission(0),
        "economic_results": "NOT_RUN",
        "m1_rows_loaded_in_setup_windows": len(frames["M1"]),
        "limitations": [
            "Macro coverage is uncertified and contributes no eligible strategy day.",
            "Midpoint reach is a technical diagnostic, not proof of limit fill.",
            "Source timezone, broker identity, and spread units are unresolved.",
            "No economic outcome, target/stop result, or model was computed.",
        ],
    }
    _write_layer_registry(output_root, summary, setup_rows, events_by_id)
    (output_root / "frequency_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.repo_root.resolve()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

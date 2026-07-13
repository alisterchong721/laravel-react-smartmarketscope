from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .detectors import detect_order_blocks, detect_sweep, ema_from_completed_bars, trend_context
from .frequency import TIMEFRAME_PATHS, _bars, _d1_events, _load_completed, _load_m1_windows, _slice_with_warmup
from .models import Direction


def _h4_end(h4_bars, candle2, candle3, mode: str):
    if mode == "CONTAINED_D1_CANDLE_2":
        return candle2.available_at
    if mode == "THROUGH_D1_CANDLE_3_CLOSE":
        return candle3.available_at
    count = 2 if mode == "TWO_POST_CLOSE_H4" else 3
    post = [bar for bar in h4_bars if bar.available_at > candle2.available_at]
    return post[count - 1].available_at if len(post) >= count else None


def measure(d1_bars, h4_bars, ratio: float, full_body: bool, trend_required: bool, h4_mode: str) -> dict[str, Any]:
    ema20 = ema_from_completed_bars(d1_bars, 20)
    ema50 = ema_from_completed_bars(d1_bars, 50)
    counts = {direction.value: {"d1_sweeps": 0, "d1_h4_confirmations": 0} for direction in Direction}
    by_year: dict[str, int] = {}
    for i in range(1, len(d1_bars) - 1):
        if trend_required and (ema20[i] is None or ema50[i] is None):
            continue
        candle1, candle2, candle3 = d1_bars[i - 1], d1_bars[i], d1_bars[i + 1]
        for direction in Direction:
            trend_ok = not trend_required or trend_context(candle2.close, float(ema20[i]), float(ema50[i]), direction)
            sweep = detect_sweep(candle1, candle2, direction, ratio, full_body)
            if not trend_ok or sweep is None:
                continue
            counts[direction.value]["d1_sweeps"] += 1
            end = _h4_end(h4_bars, candle2, candle3, h4_mode)
            if end is None:
                continue
            candidates = [
                (index, bar)
                for index, bar in enumerate(h4_bars)
                if bar.start >= candle2.start and bar.available_at <= end
            ]
            matched = any(
                candidates[j][0] == candidates[j - 1][0] + 1
                and detect_sweep(candidates[j - 1][1], candidates[j][1], direction, ratio, full_body) is not None
                for j in range(1, len(candidates))
            )
            if matched:
                counts[direction.value]["d1_h4_confirmations"] += 1
                year = str(candle2.start.year)
                by_year[year] = by_year.get(year, 0) + 1
    return {"counts": counts, "d1_h4_by_year": by_year}


def measure_ob_frequency(frames, events, structure_lookback: int, displacement_atr: float) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for timeframe in ("M15", "M5", "M1"):
        direction_counts = {direction.value: 0 for direction in Direction}
        windows_with_ob = 0
        for event in events:
            actionable = datetime.fromisoformat(event["actionable_time"])
            expiry = datetime.fromisoformat(event["expiry_time"])
            bars = _bars(_slice_with_warmup(frames[timeframe], actionable, expiry))
            direction = Direction(event["direction"])
            blocks = [
                block
                for block in detect_order_blocks(
                    bars,
                    direction,
                    structure_lookback=structure_lookback,
                    displacement_atr=displacement_atr,
                )
                if actionable <= block.available_at <= expiry
            ]
            direction_counts[direction.value] += len(blocks)
            windows_with_ob += int(bool(blocks))
        output[timeframe] = {
            "ob_count": sum(direction_counts.values()),
            "ob_count_by_direction": direction_counts,
            "d1_h4_windows_with_ob": windows_with_ob,
        }
    return output


def run(repo_root: Path) -> dict[str, Any]:
    frames = {name: _load_completed(repo_root / relative) for name, relative in TIMEFRAME_PATHS.items()}
    d1 = _bars(frames["D1"])
    h4 = _bars(frames["H4"])
    variants = [
        ("MLR-TECH-001", "RATIO_0_25", 0.25, False, True, "THREE_POST_CLOSE_H4_PRIMARY"),
        ("MLR-TECH-001", "RATIO_0_50_PRIMARY", 0.50, False, True, "THREE_POST_CLOSE_H4_PRIMARY"),
        ("MLR-TECH-001", "RATIO_0_75", 0.75, False, True, "THREE_POST_CLOSE_H4_PRIMARY"),
        ("MLR-TECH-002", "CLOSE_ONLY_PRIMARY", 0.50, False, True, "THREE_POST_CLOSE_H4_PRIMARY"),
        ("MLR-TECH-002", "FULL_BODY_ACROSS_LEVEL", 0.50, True, True, "THREE_POST_CLOSE_H4_PRIMARY"),
        ("MLR-TECH-003", "EMA20_EMA50_PRIMARY", 0.50, False, True, "THREE_POST_CLOSE_H4_PRIMARY"),
        ("MLR-TECH-003", "NO_TREND_FILTER", 0.50, False, False, "THREE_POST_CLOSE_H4_PRIMARY"),
        ("MLR-TECH-004", "CONTAINED_D1_CANDLE_2", 0.50, False, True, "CONTAINED_D1_CANDLE_2"),
        ("MLR-TECH-004", "TWO_POST_CLOSE_H4", 0.50, False, True, "TWO_POST_CLOSE_H4"),
        ("MLR-TECH-004", "THREE_POST_CLOSE_H4_PRIMARY", 0.50, False, True, "THREE_POST_CLOSE_H4_PRIMARY"),
        ("MLR-TECH-004", "THROUGH_D1_CANDLE_3_CLOSE", 0.50, False, True, "THROUGH_D1_CANDLE_3_CLOSE"),
    ]
    results = []
    for experiment_id, name, ratio, full_body, trend_required, window in variants:
        results.append(
            {
                "experiment_id": experiment_id,
                "variant": name,
                "mode": "TECHNICAL_ONLY_ABLATION",
                "ratio": ratio,
                "full_body": full_body,
                "trend_required": trend_required,
                "h4_window": window,
                **measure(d1, h4, ratio, full_body, trend_required, window),
                "economic_result": "NOT_RUN",
            }
        )
    events = [
        event
        for event in _d1_events(frames["D1"], frames["H4"])
        if event["trend_context"] and event["d1_sweep"] and event["h4_sweep"]
    ]
    m1_path = next((repo_root / "dataset").glob("NAS100_M1_*.csv"))
    frames["M1"] = _load_m1_windows(m1_path, events)
    for experiment_id, variant_name, lookback, threshold in (
        ("MLR-TECH-005", "OB_LOOKBACK_5", 5, 1.0),
        ("MLR-TECH-005", "OB_LOOKBACK_10_PRIMARY", 10, 1.0),
        ("MLR-TECH-005", "OB_LOOKBACK_20", 20, 1.0),
        ("MLR-TECH-006", "OB_DISPLACEMENT_0_ATR", 10, 0.0),
        ("MLR-TECH-006", "OB_DISPLACEMENT_0_5_ATR", 10, 0.5),
        ("MLR-TECH-006", "OB_DISPLACEMENT_1_ATR_PRIMARY", 10, 1.0),
    ):
        results.append(
            {
                "experiment_id": experiment_id,
                "variant": variant_name,
                "mode": "TECHNICAL_ONLY_ABLATION",
                "structure_lookback": lookback,
                "displacement_atr": threshold,
                "ob_frequency": measure_ob_frequency(frames, events, lookback, threshold),
                "economic_result": "NOT_RUN",
            }
        )
    artifact = {
        "schema_version": "1.0.0",
        "program_id": "QRP-MACRO-LIQUIDITY-REVERSAL-001",
        "status": "BLOCKED_BY_UNCERTIFIED_MACRO_BIAS",
        "results": results,
    }
    path = repo_root / "research/artifacts/macro_liquidity_reversal/technical_ablation_results.json"
    path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.repo_root.resolve()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

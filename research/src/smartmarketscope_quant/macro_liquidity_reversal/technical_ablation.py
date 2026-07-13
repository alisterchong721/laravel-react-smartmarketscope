from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

from smartmarketscope_quant.backtest.config import load_execution_scenarios
from smartmarketscope_quant.backtest.types import InstrumentScenario

from .detectors import protective_stop
from .frequency import TIMEFRAME_PATHS, _bars, _load_completed, _load_m1_windows
from .models import Direction
from .technical_economic import (
    EXPOSURE_LABEL,
    MODE,
    PRIMARY_SCENARIO,
    PRIMARY_STRATEGIES,
    PROGRAM_ID,
    SOURCE_POINT,
    BarIndex,
    FillProof,
    FrozenEvent,
    SimulatedPath,
    TechnicalEconomicError,
    TechnicalSetup,
    _decimal,
    _economic_row,
    _read_csv,
    _to_serializable,
    _write_csv,
    build_primary_setups,
    load_components,
    load_frozen_events,
    prove_limit_fill,
    summarize_all,
    validate_frequency_checkpoint,
    validate_hash_registry,
)
from .technical_validation import (
    MINIMUM_EFFECTIVE,
    build_samples,
    evaluate_cpcv,
    evaluate_walk_forward,
    validate_primary_lock,
)


TARGET_MULTIPLE = Decimal("1.5")
WIN_OUTCOME = "WIN_TARGET_1_5R"


def _barrier_hits(
    direction: Direction,
    bar,
    stop: Decimal,
    target: Decimal,
) -> tuple[bool, bool]:
    if direction is Direction.BULLISH:
        return _decimal(bar.low) <= stop, _decimal(bar.high) >= target
    return _decimal(bar.high) >= stop, _decimal(bar.low) <= target


def simulate_path_at_target(
    setup: TechnicalSetup,
    proof: FillProof,
    scenario: InstrumentScenario,
    path: BarIndex,
    target_multiple: Decimal = TARGET_MULTIPLE,
) -> tuple[SimulatedPath, dict[str, Decimal]]:
    if proof.status != "FILLED" or proof.entry_reference is None or proof.entry_bar_index is None:
        return SimulatedPath(proof.status, None, None, proof.reason, False, 0), {}
    stop = _decimal(
        protective_stop(
            setup.direction,
            setup.block_zone,
            float(SOURCE_POINT),
            float(scenario.spread_points),
            units_documented=True,
        )
    )
    commission_points = (
        Decimal("2")
        * scenario.commission_usd_per_unit_per_side
        / scenario.point_value_usd_per_unit
    )
    known_cost_points = (
        scenario.spread_points
        + Decimal("2") * scenario.slippage_points_per_side
        + commission_points
    )
    risk_points = abs(proof.entry_reference - stop) + known_cost_points
    if (
        setup.direction is Direction.BULLISH and proof.entry_reference <= stop
    ) or (
        setup.direction is Direction.BEARISH and proof.entry_reference >= stop
    ):
        return (
            SimulatedPath(
                "NO_FILL",
                None,
                proof.entry_bar_available,
                "PROTECTIVE_STOP_BREACHED_BEFORE_ENTRY",
                False,
                0,
            ),
            {},
        )
    direction = Decimal("1") if setup.direction is Direction.BULLISH else Decimal("-1")
    target = proof.entry_reference + direction * target_multiple * risk_points
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
        return (
            SimulatedPath(outcome, stop, entry_bar.available_at, "ENTRY_BAR_STOP_ADVERSE", ambiguous, 1),
            {"stop": stop, "target": target, "risk_points": risk_points},
        )
    for bars_held, bar in enumerate(bars[1:], start=2):
        gap_stop = (
            setup.direction is Direction.BULLISH and _decimal(bar.open) <= stop
        ) or (
            setup.direction is Direction.BEARISH and _decimal(bar.open) >= stop
        )
        if gap_stop:
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
                SimulatedPath(WIN_OUTCOME, target, bar.available_at, "TARGET_1_5R", False, bars_held),
                {"stop": stop, "target": target, "risk_points": risk_points},
            )
    final = bars[-1]
    return (
        SimulatedPath("TIMEOUT", _decimal(final.close), final.available_at, "D1_CANDLE_3_EXPIRY", False, len(bars)),
        {"stop": stop, "target": target, "risk_points": risk_points},
    )


def simulate_setup_at_target(
    setup: TechnicalSetup,
    path: BarIndex,
    scenarios: Sequence[InstrumentScenario],
    event: FrozenEvent,
) -> list[dict[str, Any]]:
    proof = prove_limit_fill(setup, path)
    rows = []
    for scenario in scenarios:
        simulated, barriers = simulate_path_at_target(setup, proof, scenario, path)
        row = _economic_row(setup, proof, simulated, barriers, scenario, event)
        row["experiment_id"] = "MLR-TECH-ABL-001"
        row["target_multiple"] = TARGET_MULTIPLE
        rows.append(row)
    return rows


def _effective_rows(rows: Sequence[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["scenario_id"] != PRIMARY_SCENARIO or row["outcome"] in {"NO_FILL", "INVALID_DATA"}:
            continue
        grouped[row["strategy_id"]].append(row)
    effective: dict[str, list[dict[str, Any]]] = {}
    for strategy, strategy_rows in grouped.items():
        ordered = sorted(
            strategy_rows,
            key=lambda row: (row["entry_path_available_at"], row["exit_time"], row["setup_id"]),
        )
        selected = []
        prior_exit: datetime | None = None
        for row in ordered:
            entry = datetime.fromisoformat(str(row["entry_path_available_at"]))
            exit_time = datetime.fromisoformat(str(row["exit_time"]))
            if prior_exit is None or entry > prior_exit:
                selected.append(row)
                prior_exit = exit_time
        effective[strategy] = selected
    return effective


def _validation(
    rows: Sequence[dict[str, Any]],
    event_starts: dict[str, datetime],
) -> dict[str, Any]:
    results = {}
    for strategy, strategy_rows in sorted(_effective_rows(rows).items()):
        string_rows = [{key: str(value) if value is not None else "" for key, value in row.items()} for row in strategy_rows]
        samples, by_id = build_samples(string_rows, event_starts)
        if len(samples) < MINIMUM_EFFECTIVE:
            results[strategy] = {
                "effective_filled_trades": len(samples),
                "status": "INSUFFICIENT_FOR_RELIABLE_MODEL_SELECTION",
                "cpcv": None,
                "outer_walk_forward": None,
            }
        else:
            results[strategy] = {
                "effective_filled_trades": len(samples),
                "status": "RULE_BASED_VALIDATION_PERMITTED",
                "cpcv": evaluate_cpcv(samples, by_id),
                "outer_walk_forward": evaluate_walk_forward(samples, by_id),
            }
    return results


def run(repo_root: Path) -> dict[str, Any]:
    validate_primary_lock(repo_root)
    artifact_root = repo_root / "research/artifacts/macro_liquidity_reversal"
    checkpoint_path = artifact_root / "governance/MLR_FREQUENCY_CHECKPOINT_20260713T123112+0800.json"
    validate_frequency_checkpoint(repo_root, checkpoint_path)
    registry = validate_hash_registry(artifact_root / "MLR_TECHNICAL_ECONOMIC_EXPERIMENT_REGISTRY.jsonl")
    if registry[-1]["payload"].get("experiment_id") != "MLR-TECH-ABL-001" or registry[-1]["payload"].get("status") not in {"PREREGISTERED", "STARTED"}:
        raise TechnicalEconomicError("MLR_TECHNICAL_ABLATION_NOT_STARTED")

    events, all_event_rows = load_frozen_events(artifact_root)
    frames = {name: _load_completed(repo_root / relative) for name, relative in TIMEFRAME_PATHS.items()}
    d1_sweep_rows = [row for row in all_event_rows if row["trend_context"] == "True" and row["d1_sweep"] == "True"]
    m1_requests = [
        {
            "actionable_time": row["actionable_time"] or row["d1_confirmation_time"],
            "expiry_time": row["expiry_time"],
        }
        for row in d1_sweep_rows
    ]
    m1_path = next((repo_root / "dataset").glob("NAS100_M1_*.csv"))
    frames["M1"] = _load_m1_windows(m1_path, m1_requests)
    indices = {timeframe: BarIndex(_bars(frames[timeframe])) for timeframe in ("M15", "M5", "M1")}
    setups, _ = build_primary_setups(events, load_components(artifact_root), indices)
    event_by_id = {event.event_id: event for event in events}
    scenarios = load_execution_scenarios(repo_root / "research/config/execution_scenarios.json")
    rows = [
        row
        for setup in setups
        for row in simulate_setup_at_target(setup, indices["M1"], scenarios, event_by_id[setup.event_id])
    ]
    summary_rows = [
        {**row, "outcome": "WIN_2R" if row["outcome"] == WIN_OUTCOME else row["outcome"]}
        for row in rows
    ]
    event_starts = {
        row["event_id"]: datetime.fromisoformat(row["d1_candle1_start"])
        for row in all_event_rows
    }
    validation = _validation(rows, event_starts)
    summary = {
        "schema_version": "1.0.0",
        "program_id": PROGRAM_ID,
        "experiment_id": "MLR-TECH-ABL-001",
        "mode": MODE,
        "historical_exposure": EXPOSURE_LABEL,
        "change": "TARGET_MULTIPLE_2R_TO_1_5R_DIAGNOSTIC",
        "intended_final_target": "2R",
        "primary_results": summarize_all(summary_rows),
        "validation": validation,
        "machine_learning_permission": "PROHIBITED_MAXIMUM_PRIMARY_EFFECTIVE_SAMPLE_BELOW_100",
        "prohibitions": {
            "automatic_promotion": False,
            "post_2026_06_28_access": False,
            "final_holdout_access": False,
        },
    }
    serializable = _to_serializable(summary)
    _write_csv(artifact_root / "MLR_TECHNICAL_ABLATION_001_TRADES.csv", rows)
    (artifact_root / "MLR_TECHNICAL_ABLATION_001_SUMMARY.json").write_text(
        json.dumps(serializable, indent=2, ensure_ascii=True) + "\n",
        encoding="ascii",
    )
    _write_report(artifact_root, serializable)
    return serializable


def _number(value: Any) -> str:
    return "N/A" if value is None else f"{float(value):.3f}"


def _write_report(artifact_root: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# MLR Technical Ablation Report",
        "",
        "Experiment: `MLR-TECH-ABL-001`",
        "",
        "Status: `TECHNICAL_ONLY_ABLATION` on `PREVIOUSLY_EXPOSED_WINDOW`.",
        "",
        "The only change is a diagnostic 1.5R target. The intended strategy target remains 2R and this result cannot be promoted automatically.",
        "",
        "| Strategy | Filled | Wins | Avg net R | Total net R | CPCV positive splits | Outer positive folds |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for strategy in PRIMARY_STRATEGIES:
        primary = summary["primary_results"].get(strategy, {}).get(PRIMARY_SCENARIO, {})
        validation = summary["validation"].get(strategy, {})
        cpcv = validation.get("cpcv") or {}
        outer = validation.get("outer_walk_forward") or {}
        lines.append(
            f"| {strategy} | {primary.get('filled_trades', 0)} | {primary.get('wins', 0)} | "
            f"{_number(primary.get('average_net_r'))} | {_number(primary.get('total_net_r'))} | "
            f"{_number(cpcv.get('positive_split_fraction'))} | {_number(outer.get('positive_fold_fraction'))} |"
        )
    (artifact_root / "MLR_TECHNICAL_ABLATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the preregistered MLR 1.5R target diagnostic")
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.repo_root.resolve())
    print(json.dumps({"strategies": len(result["primary_results"]), "target_multiple": str(TARGET_MULTIPLE)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

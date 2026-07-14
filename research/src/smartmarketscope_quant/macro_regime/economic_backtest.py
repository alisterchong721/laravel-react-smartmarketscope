from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import pyarrow as pa
import pyarrow.parquet as pq

from smartmarketscope_quant.governance.registry import validate_registry


PROGRAM_ID = "SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001"
EXPERIMENT_ID = "SMMS-MACRO-REGIME-R9-001"
ROLE8 = Path("research/artifacts/macro_regime/role8")
ROLE9 = Path("research/artifacts/macro_regime/role9")
CONFIG = Path("research/config/MACRO_REGIME_ROLE9_BACKTEST_CONFIG.json")
PREREGISTRATION = Path("research/preregistrations/SMMS-MACRO-REGIME-R9-001.json")
TRADE_REGISTRY = ROLE8 / "MACRO_REGIME_TECHNICAL_TRADE_REGISTRY.parquet"
LINKS = ROLE8 / "MACRO_TECHNICAL_LINKS.parquet"
ROLE8_MANIFEST = ROLE8 / "ROLE8_ALIGNMENT_MANIFEST.json"
ROLE8_HASHES = ROLE8 / "ROLE8_OUTPUT_HASHES.json"
CODE_PATH = Path("research/src/smartmarketscope_quant/macro_regime/economic_backtest.py")
TEST_PATH = Path("research/tests/test_macro_regime_economic_backtest.py")
CREATED_AT_UTC = "2026-07-14T06:00:00Z"
SCENARIOS = ("NORMALIZED_LOW_COST", "NORMALIZED_MEDIUM_COST", "NORMALIZED_HIGH_COST")
JOIN_MODES = ("J0", "J1", "J2")
MACRO_VARIANTS = ("M1_LOOSE", "M2_PRIMARY", "M3_STRONG_ONLY", "M4_HIGH_COVERAGE")
STRATEGIES = (
    "M15_C1_OB_FVG", "M15_C2_FVG_BREAKER", "M5_C1_OB_FVG", "M5_C2_FVG_BREAKER",
    "M1_C1_OB_FVG", "M1_C2_FVG_BREAKER", "HIERARCHICAL_M15_M5_M1",
)


class BacktestError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="ascii"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="ascii")


def write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = tuple(rows[0]) if rows else ()
    with path.open("w", newline="", encoding="ascii") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_parquet(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    columns = {field: ["" if row.get(field) is None else str(row.get(field, "")) for row in rows] for field in fields}
    table = pa.table({field: pa.array(columns[field], type=pa.string()) for field in fields})
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path, compression="zstd", use_dictionary=False, write_statistics=True)


def as_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_inputs(root: Path) -> dict[str, str]:
    manifest_path = root / ROLE8_MANIFEST
    manifest = read_json(manifest_path)
    if manifest["status"] != "PASS_ROLE8_ALIGNMENT_COMPLETE_ROLE9_PERMITTED":
        raise BacktestError("BACKTEST_ENGINE_BUILDER_MISSING_INPUT:ROLE8_STATUS")
    hashes = read_json(root / ROLE8_HASHES)
    for relative, expected in hashes.items():
        path = root / relative
        if not path.exists() or sha256_file(path) != expected:
            raise BacktestError(f"BACKTEST_ENGINE_BUILDER_INVARIANT_FAILED:ROLE8_HASH:{relative}")
    for relative, expected in manifest["inputs"].items():
        path = root / relative
        if not path.exists() or sha256_file(path) != expected:
            raise BacktestError(f"BACKTEST_ENGINE_BUILDER_INVARIANT_FAILED:ROLE8_INPUT_HASH:{relative}")
    validation = validate_registry(root / "EXPERIMENT_REGISTRY.jsonl")
    if EXPERIMENT_ID in validation["states"]:
        raise BacktestError("BACKTEST_ENGINE_BUILDER_INVARIANT_FAILED:GLOBAL_REGISTRY_FROZEN_CONSUMER_CONFLICT")
    return {
        "role8_manifest_sha256": sha256_file(manifest_path),
        "role8_output_hashes_sha256": sha256_file(root / ROLE8_HASHES),
        "technical_registry_sha256": sha256_file(root / TRADE_REGISTRY),
        "macro_links_sha256": sha256_file(root / LINKS),
        "config_sha256": sha256_file(root / CONFIG),
        "preregistration_sha256": sha256_file(root / PREREGISTRATION),
        "experiment_registry_head": validation["last_event_hash"],
        "experiment_registry_role9_policy": "UNCHANGED_BECAUSE_ROLE3_ROLE4_HASH_LOCK_WHOLE_FILE; ROLE9_USES_DEDICATED_APPEND_ONLY_MACRO_BACKTEST_RUN_REGISTRY",
    }


def load_inputs(root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    lineage = validate_inputs(root)
    trades = pq.read_table(root / TRADE_REGISTRY).to_pylist()
    links = pq.read_table(root / LINKS).to_pylist()
    if len(trades) != 1362 or len(links) != 1362:
        raise BacktestError("TECHNICAL_BASELINE_RECONCILIATION_FAILED:ROW_CENSUS")
    medium = [row for row in trades if row["scenario_id"] == "NORMALIZED_MEDIUM_COST"]
    if len(medium) != 454 or len({row["setup_id"] for row in medium}) != 454:
        raise BacktestError("TECHNICAL_BASELINE_RECONCILIATION_FAILED:SETUP_CENSUS")
    if Counter(row["fill_status"] for row in medium) != Counter({"FILLED": 306, "NO_FILL": 148}):
        raise BacktestError("TECHNICAL_BASELINE_RECONCILIATION_FAILED:FILL_CENSUS")
    expected = Counter({"WIN_2R": 52, "LOSS_1R": 246, "TIMEOUT": 2, "AMBIGUOUS_ADVERSE_FIRST": 6, "NO_FILL": 148})
    if Counter(row["outcome"] for row in medium) != expected:
        raise BacktestError("TECHNICAL_BASELINE_RECONCILIATION_FAILED:OUTCOME_CENSUS")
    if Counter(row["join_mode"] for row in links) != Counter({"J0": 454, "J1": 454, "J2": 454}):
        raise BacktestError("BACKTEST_ENGINE_BUILDER_INVARIANT_FAILED:JOIN_CENSUS")
    if any(row["macro_bias"] != "UNKNOWN" or row["filter_decision"] != "FILTERED_UNKNOWN" for row in links):
        raise BacktestError("BACKTEST_ENGINE_BUILDER_INVARIANT_FAILED:UNKNOWN_GATE_CHANGED")
    if any(row["future_state_violation"] != "false" or row["replacement_trade_created"] != "false" for row in links):
        raise BacktestError("BACKTEST_ENGINE_BUILDER_TIMING_INVALID:ROLE8_LINK")
    by_setup_scenario = {(row["setup_id"], row["scenario_id"]): row for row in trades}
    if len(by_setup_scenario) != 1362:
        raise BacktestError("TECHNICAL_BASELINE_RECONCILIATION_FAILED:DUPLICATE_TRADE")
    return trades, links, lineage


def variant_permits(link: dict[str, str], variant: str, config: dict[str, Any]) -> bool:
    if variant == "T0":
        return True
    if link["macro_bias"] == "UNKNOWN" or link["final_score"] == "":
        return False
    spec = config["variants"][variant]
    if int(link["valid_category_count"]) < int(spec["minimum_valid_categories"]):
        return False
    score = int(link["final_score"])
    direction = link["technical_direction"]
    return (direction == "BULLISH" and score >= spec["long_min"]) or (direction == "BEARISH" and score <= spec["short_max"])


def selected_setup_ids(
    medium: Sequence[dict[str, str]], links: Sequence[dict[str, str]], variant: str, join: str, config: dict[str, Any]
) -> set[str]:
    if variant in {"T0", "C4_SIMPLE_D1_TREND"}:
        return {row["setup_id"] for row in medium}
    if variant == "C1_LONG_ONLY":
        return {row["setup_id"] for row in medium if row["direction"] == "BULLISH"}
    if variant == "C2_SHORT_ONLY":
        return {row["setup_id"] for row in medium if row["direction"] == "BEARISH"}
    selected: set[str] = set()
    for link in links:
        if link["join_mode"] != join:
            continue
        if variant == "C3_OPPOSITE_MACRO":
            if link["macro_bias"] == "UNKNOWN" or link["final_score"] == "":
                continue
            score = int(link["final_score"])
            direction = link["technical_direction"]
            if (direction == "BEARISH" and score >= 2) or (direction == "BULLISH" and score <= -2):
                selected.add(link["technical_setup_id"])
        elif variant_permits(link, variant, config):
            selected.add(link["technical_setup_id"])
    return selected


def _max_drawdown(values: Sequence[float]) -> tuple[float, float | None]:
    if not values:
        return 0.0, None
    equity = 0.0
    peak = 0.0
    maximum = 0.0
    peak_index = 0
    duration = 0
    for index, value in enumerate(values):
        equity += value
        if equity >= peak:
            peak = equity
            peak_index = index
        drawdown = peak - equity
        if drawdown > maximum:
            maximum = drawdown
            duration = index - peak_index
    return maximum, float(duration)


def _losing_streak(values: Sequence[float]) -> int:
    best = current = 0
    for value in values:
        current = current + 1 if value < 0 else 0
        best = max(best, current)
    return best


def calculate_metrics(
    universe: Sequence[dict[str, str]], selected: Sequence[dict[str, str]], study_span_hours: float
) -> dict[str, Any]:
    ordered = sorted(selected, key=lambda row: (row["exit_time"] or row["decision_time"], row["setup_id"]))
    filled = [row for row in ordered if row["fill_status"] == "FILLED"]
    values = [float(row["net_r"]) for row in filled]
    gross = [float(row["gross_r"]) for row in filled]
    holding = [float(row["holding_hours"]) for row in filled]
    wins = sum(row["outcome"] == "WIN_2R" for row in filled)
    losses = sum(row["outcome"] == "LOSS_1R" for row in filled)
    timeouts = sum(row["outcome"] == "TIMEOUT" for row in filled)
    ambiguities = sum(row["outcome"] == "AMBIGUOUS_ADVERSE_FIRST" for row in filled)
    resolved = wins + losses + ambiguities
    positive = sum(value for value in values if value > 0)
    negative = abs(sum(value for value in values if value < 0))
    drawdown, drawdown_duration_trades = _max_drawdown(values)
    years = sorted({parse_time(row["decision_time"]).year for row in filled})
    yearly = {year: sum(float(row["net_r"]) for row in filled if parse_time(row["decision_time"]).year == year) for year in years}
    entry_times = sorted(parse_time(row["entry_bar_start"]) for row in filled)
    max_inactivity = max(((b - a).total_seconds() / 3600 for a, b in zip(entry_times, entry_times[1:])), default=None)
    return {
        "detected_technical_setups": len(universe),
        "filled_technical_trades": sum(row["fill_status"] == "FILLED" for row in universe),
        "permitted_setups": len(selected),
        "permitted_trades": len(filled),
        "filtered_setups": len(universe) - len(selected),
        "retention_percentage": (100.0 * len(filled) / sum(row["fill_status"] == "FILLED" for row in universe)) if any(row["fill_status"] == "FILLED" for row in universe) else None,
        "no_fills": sum(row["fill_status"] == "NO_FILL" for row in selected),
        "wins": wins, "losses": losses, "timeouts": timeouts, "ambiguities": ambiguities,
        "resolved_win_rate": wins / resolved if resolved else None,
        "two_r_before_stop_rate": wins / len(filled) if filled else None,
        "average_gross_r": statistics.fmean(gross) if gross else None,
        "median_gross_r": statistics.median(gross) if gross else None,
        "average_net_r": statistics.fmean(values) if values else None,
        "median_net_r": statistics.median(values) if values else None,
        "total_net_r": sum(values),
        "expectancy_r": statistics.fmean(values) if values else None,
        "profit_factor": positive / negative if negative else (math.inf if positive else None),
        "maximum_drawdown_r": drawdown,
        "maximum_drawdown_duration_trades": drawdown_duration_trades,
        "longest_losing_streak": _losing_streak(values),
        "average_holding_hours": statistics.fmean(holding) if holding else None,
        "median_holding_hours": statistics.median(holding) if holding else None,
        "profitable_years": sum(value > 0 for value in yearly.values()),
        "losing_years": sum(value < 0 for value in yearly.values()),
        "percentage_profitable_years": sum(value > 0 for value in yearly.values()) / len(yearly) if yearly else None,
        "worst_year": min(yearly, key=yearly.get) if yearly else None,
        "worst_year_net_r": min(yearly.values()) if yearly else None,
        "best_year": max(yearly, key=yearly.get) if yearly else None,
        "best_year_net_r": max(yearly.values()) if yearly else None,
        "maximum_inactivity_hours": max_inactivity,
        "study_span_hours": study_span_hours,
        "metric_status": "PASS" if filled else "ZERO_TRADES",
    }


def metric_rows(trades: list[dict[str, str]], links: list[dict[str, str]], config: dict[str, Any]) -> list[dict[str, Any]]:
    medium = [row for row in trades if row["scenario_id"] == "NORMALIZED_MEDIUM_COST"]
    lookup = {(row["setup_id"], row["scenario_id"]): row for row in trades}
    start = min(parse_time(row["decision_time"]) for row in medium)
    end = max(parse_time(row["expiry_time"]) for row in medium)
    span = (end - start).total_seconds() / 3600
    global_years = sorted({parse_time(row["decision_time"]).year for row in medium})
    runs: list[tuple[str, str]] = []
    for join in JOIN_MODES:
        runs.extend((variant, join) for variant in ("T0", *MACRO_VARIANTS, "C3_OPPOSITE_MACRO"))
    runs.extend((variant, "NOT_APPLICABLE") for variant in ("C1_LONG_ONLY", "C2_SHORT_ONLY", "C4_SIMPLE_D1_TREND"))
    rows: list[dict[str, Any]] = []
    for variant, join in runs:
        selection_join = "J0" if join == "NOT_APPLICABLE" else join
        ids = selected_setup_ids(medium, links, variant, selection_join, config)
        for strategy in STRATEGIES:
            base_medium = [row for row in medium if row["strategy_id"] == strategy]
            for direction in ("ALL", "BULLISH", "BEARISH"):
                directional = base_medium if direction == "ALL" else [row for row in base_medium if row["direction"] == direction]
                years = ["ALL", *global_years]
                for year in years:
                    scoped = directional if year == "ALL" else [row for row in directional if parse_time(row["decision_time"]).year == year]
                    for scenario in SCENARIOS:
                        universe = [lookup[(row["setup_id"], scenario)] for row in scoped]
                        chosen = [row for row in universe if row["setup_id"] in ids]
                        metrics = calculate_metrics(universe, chosen, span)
                        rows.append({
                            "program_id": PROGRAM_ID, "experiment_id": EXPERIMENT_ID,
                            "variant": variant, "join_mode": join, "strategy_id": strategy,
                            "timeframe": base_medium[0]["timeframe"] if base_medium else strategy,
                            "confluence_family": base_medium[0]["family"] if base_medium else "",
                            "direction": direction, "year": year, "cost_scenario": scenario, **metrics,
                        })
    return rows


def comparison_rows(metrics: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    key_fields = ("join_mode", "strategy_id", "direction", "year", "cost_scenario")
    t0 = {}
    for row in metrics:
        if row["variant"] == "T0":
            t0[tuple(row[field] for field in key_fields)] = row
    output = []
    for row in metrics:
        if row["variant"] == "T0":
            continue
        join = "J0" if row["join_mode"] == "NOT_APPLICABLE" else row["join_mode"]
        baseline = t0.get((join, row["strategy_id"], row["direction"], row["year"], row["cost_scenario"]))
        if baseline is None:
            continue
        def delta(field: str) -> float | None:
            left, right = row[field], baseline[field]
            return None if left is None or right is None else float(left) - float(right)
        output.append({
            "variant": row["variant"], "join_mode": row["join_mode"], "strategy_id": row["strategy_id"],
            "direction": row["direction"], "year": row["year"], "cost_scenario": row["cost_scenario"],
            "delta_permitted_trades": delta("permitted_trades"), "delta_total_net_r": delta("total_net_r"),
            "delta_average_net_r": delta("average_net_r"), "delta_resolved_win_rate": delta("resolved_win_rate"),
            "delta_maximum_drawdown_r": delta("maximum_drawdown_r"),
            "delta_retention_percentage": delta("retention_percentage"),
        })
    return output


def random_control_rows(trades: list[dict[str, str]], links: list[dict[str, str]], config: dict[str, Any]) -> list[dict[str, Any]]:
    medium = [row for row in trades if row["scenario_id"] == "NORMALIZED_MEDIUM_COST" and row["fill_status"] == "FILLED"]
    rows = []
    for join in JOIN_MODES:
        for variant in MACRO_VARIANTS:
            selected = selected_setup_ids([row for row in trades if row["scenario_id"] == "NORMALIZED_MEDIUM_COST"], links, variant, join, config)
            target = [row for row in medium if row["setup_id"] in selected]
            direction_counts = Counter(row["direction"] for row in target)
            seed = int(config["random_control"]["base_seed"]) + JOIN_MODES.index(join) * 100 + MACRO_VARIANTS.index(variant)
            if not target:
                rows.append({
                    "join_mode": join, "macro_variant": variant, "seed": seed, "requested_draws": config["random_control"]["draws"],
                    "executed_draws": 0, "target_retained_fills": 0, "target_bullish_fills": 0, "target_bearish_fills": 0,
                    "macro_expectancy_r": None, "random_expectancy_mean_r": None, "random_expectancy_median_r": None,
                    "random_expectancy_p05_r": None, "random_expectancy_p95_r": None,
                    "status": "NOT_APPLICABLE_ZERO_RETENTION",
                    "reason": "A retention-matched distribution is undefined when the frozen macro filter retains zero filled trades; zero is not converted to a random sample.",
                })
                continue
            rng = random.Random(seed)
            values = []
            by_direction = {d: [row for row in medium if row["direction"] == d] for d in ("BULLISH", "BEARISH")}
            for _ in range(int(config["random_control"]["draws"])):
                sample = []
                for direction, count in direction_counts.items():
                    sample.extend(rng.sample(by_direction[direction], count))
                values.append(statistics.fmean(float(row["net_r"]) for row in sample))
            ordered = sorted(values)
            rows.append({
                "join_mode": join, "macro_variant": variant, "seed": seed, "requested_draws": config["random_control"]["draws"],
                "executed_draws": len(values), "target_retained_fills": len(target),
                "target_bullish_fills": direction_counts["BULLISH"], "target_bearish_fills": direction_counts["BEARISH"],
                "macro_expectancy_r": statistics.fmean(float(row["net_r"]) for row in target),
                "random_expectancy_mean_r": statistics.fmean(values), "random_expectancy_median_r": statistics.median(values),
                "random_expectancy_p05_r": ordered[int(0.05 * (len(ordered) - 1))],
                "random_expectancy_p95_r": ordered[int(0.95 * (len(ordered) - 1))],
                "status": "PASS", "reason": "Deterministic direction-preserving retention-matched draws.",
            })
    return rows


def walk_forward_rows(trades: list[dict[str, str]], links: list[dict[str, str]], config: dict[str, Any]) -> list[dict[str, Any]]:
    medium = [row for row in trades if row["scenario_id"] == "NORMALIZED_MEDIUM_COST"]
    rows = []
    variants = ("T0", *MACRO_VARIANTS, "C3_OPPOSITE_MACRO", "C1_LONG_ONLY", "C2_SHORT_ONLY", "C4_SIMPLE_D1_TREND")
    for fold_index, test_years in enumerate(config["walk_forward"]["test_year_blocks"], start=1):
        test_start = datetime(min(test_years), 1, 1)
        test_end = datetime(max(test_years) + 1, 1, 1)
        train = [row for row in medium if parse_time(row["decision_time"]) < test_start]
        purge = [row for row in train if parse_time(row["expiry_time"]) >= test_start]
        train_ids = {row["setup_id"] for row in train} - {row["setup_id"] for row in purge}
        test = [row for row in medium if test_start <= parse_time(row["decision_time"]) < test_end]
        for variant in variants:
            for join in (("J0", "J1", "J2") if variant in {*MACRO_VARIANTS, "C3_OPPOSITE_MACRO"} else ("NOT_APPLICABLE",)):
                selection = selected_setup_ids(medium, links, variant, "J0" if join == "NOT_APPLICABLE" else join, config)
                selected = [row for row in test if row["setup_id"] in selection]
                metric = calculate_metrics(test, selected, (test_end - test_start).total_seconds() / 3600)
                rows.append({
                    "fold": fold_index, "train_start_year": min((parse_time(row["decision_time"]).year for row in train), default=None),
                    "train_end_year": max((parse_time(row["decision_time"]).year for row in train), default=None),
                    "test_years": "|".join(str(year) for year in test_years), "variant": variant, "join_mode": join,
                    "train_setups_before_purge": len(train), "purged_overlapping_setups": len(purge),
                    "train_setups_after_purge": len(train_ids), "embargo_source_trading_days": config["walk_forward"]["embargo_source_trading_days"],
                    "test_setups": len(test), "test_filled_trades": metric["filled_technical_trades"],
                    "retained_filled_trades": metric["permitted_trades"], "total_net_r": metric["total_net_r"],
                    "average_net_r": metric["average_net_r"], "maximum_drawdown_r": metric["maximum_drawdown_r"],
                    "status": metric["metric_status"], "outer_reoptimization": "false",
                })
    return rows


def category_rows(trades: list[dict[str, str]], links: list[dict[str, str]]) -> list[dict[str, Any]]:
    medium = {row["setup_id"]: row for row in trades if row["scenario_id"] == "NORMALIZED_MEDIUM_COST"}
    rows = []
    for join in JOIN_MODES:
        linked = [row for row in links if row["join_mode"] == join]
        for category, field in (("INFLATION", "inflation_score"), ("LABOUR", "labour_score"), ("GROWTH", "growth_score"), ("MONETARY_POLICY", "monetary_policy_score"), ("LIQUIDITY", "liquidity_score")):
            grouped: dict[str, list[dict[str, str]]] = {}
            for link in linked:
                grouped.setdefault(link[field] or "UNKNOWN", []).append(medium[link["technical_setup_id"]])
            for score, group in sorted(grouped.items()):
                metric = calculate_metrics(group, group, 0.0)
                rows.append({"join_mode": join, "category": category, "category_score": score,
                             "setups": len(group), "filled_trades": metric["permitted_trades"],
                             "medium_total_net_r": metric["total_net_r"], "medium_average_net_r": metric["average_net_r"],
                             "status": "DESCRIPTIVE_NOT_CAUSAL"})
    return rows


def _headline(metrics: Sequence[dict[str, Any]], variant: str, strategy: str | None = None, join: str = "J0") -> dict[str, Any]:
    chosen = [row for row in metrics if row["variant"] == variant and row["join_mode"] == join and row["direction"] == "ALL" and row["year"] == "ALL" and row["cost_scenario"] == "NORMALIZED_MEDIUM_COST"]
    if strategy:
        chosen = [row for row in chosen if row["strategy_id"] == strategy]
    if not strategy:
        return {"permitted_trades": sum(row["permitted_trades"] for row in chosen), "total_net_r": sum(row["total_net_r"] for row in chosen)}
    return chosen[0]


def report_text(title: str, strategy_ids: Sequence[str], metrics: Sequence[dict[str, Any]]) -> str:
    lines = [f"# {title}", "", "Decision evidence: `FACT` for frozen counts and `CALCULATION` for metrics. All monetary costs are hypothetical normalized scenarios, not broker facts.", "",
             "| Strategy | T0 fills | T0 medium net R | M2 J0 fills | M2 J0 medium net R | Decision |", "| --- | ---: | ---: | ---: | ---: | --- |"]
    for strategy in strategy_ids:
        t0 = _headline(metrics, "T0", strategy)
        m2 = _headline(metrics, "M2_PRIMARY", strategy)
        lines.append(f"| {strategy} | {t0['permitted_trades']} | {t0['total_net_r']:.6f} | {m2['permitted_trades']} | {m2['total_net_r']:.6f} | INSUFFICIENT_ALIGNED_TRADES |")
    lines += ["", "Every M1/M2/M3/M4 macro row is an explicit zero-trade result under J0/J1/J2 because every frozen link is UNKNOWN. Coverage was not relaxed and no replacement trade was created.", ""]
    return "\n".join(lines)


def generate(root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    out = output_dir or (root / ROLE9)
    out.mkdir(parents=True, exist_ok=True)
    trades, links, lineage = load_inputs(root)
    config = read_json(root / CONFIG)
    metrics = metric_rows(trades, links, config)
    comparisons = comparison_rows(metrics)
    random_rows = random_control_rows(trades, links, config)
    walk = walk_forward_rows(trades, links, config)
    categories = category_rows(trades, links)
    metric_fields = tuple(metrics[0])
    write_csv(out / "MACRO_BACKTEST_METRICS.csv", metrics, metric_fields)
    write_parquet(out / "MACRO_BACKTEST_METRICS.parquet", metrics, metric_fields)
    write_csv(out / "MACRO_VARIANT_DELTAS.csv", comparisons)
    write_csv(out / "MACRO_RANDOM_CONTROL_RESULTS.csv", random_rows)
    write_csv(out / "MACRO_WALK_FORWARD_RESULTS.csv", walk)
    write_csv(out / "MACRO_CATEGORY_CONTRIBUTION.csv", categories)

    medium = [row for row in trades if row["scenario_id"] == "NORMALIZED_MEDIUM_COST"]
    trade_lookup = {(row["setup_id"], row["scenario_id"]): row for row in trades}
    run_rows = []
    selection_rows = []
    curve_rows = []
    for join in JOIN_MODES:
        for variant in ("T0", *MACRO_VARIANTS, "C3_OPPOSITE_MACRO"):
            ids = selected_setup_ids(medium, links, variant, join, config)
            for setup in medium:
                permitted = setup["setup_id"] in ids
                selection_rows.append({"variant": variant, "join_mode": join, "setup_id": setup["setup_id"],
                                       "strategy_id": setup["strategy_id"], "direction": setup["direction"],
                                       "fill_status": setup["fill_status"], "permitted": str(permitted).lower(),
                                       "decision_reason": "TECHNICAL_ONLY" if variant == "T0" else ("PERMITTED" if permitted else "FILTERED_UNKNOWN")})
                for scenario in SCENARIOS:
                    trade = trade_lookup[(setup["setup_id"], scenario)]
                    if trade["fill_status"] == "FILLED" and permitted:
                        curve_rows.append({"variant": variant, "join_mode": join, "strategy_id": trade["strategy_id"],
                                           "timeframe": trade["timeframe"], "confluence_family": trade["family"],
                                           "setup_id": trade["setup_id"], "direction": trade["direction"],
                                           "cost_scenario": scenario, "decision_time": trade["decision_time"],
                                           "exit_time": trade["exit_time"], "net_r": trade["net_r"], "gross_r": trade["gross_r"]})
            run_rows.append({
                "run_id": f"R9-{join}-{variant}", "program_id": PROGRAM_ID, "experiment_id": EXPERIMENT_ID,
                "variant": variant, "join_mode": join, "technical_baseline_sha256": lineage["technical_registry_sha256"],
                "macro_links_sha256": lineage["macro_links_sha256"], "config_sha256": lineage["config_sha256"],
                "retained_setups": len(ids), "retained_filled_medium": sum(row["fill_status"] == "FILLED" and row["setup_id"] in ids for row in medium),
                "status": "PASS_ZERO_TRADES" if variant != "T0" and not ids else "PASS",
            })
    for variant in ("C1_LONG_ONLY", "C2_SHORT_ONLY", "C4_SIMPLE_D1_TREND"):
        ids = selected_setup_ids(medium, links, variant, "J0", config)
        for setup in medium:
            permitted = setup["setup_id"] in ids
            selection_rows.append({"variant": variant, "join_mode": "NOT_APPLICABLE", "setup_id": setup["setup_id"],
                                   "strategy_id": setup["strategy_id"], "direction": setup["direction"],
                                   "fill_status": setup["fill_status"], "permitted": str(permitted).lower(),
                                   "decision_reason": variant})
            for scenario in SCENARIOS:
                trade = trade_lookup[(setup["setup_id"], scenario)]
                if trade["fill_status"] == "FILLED" and permitted:
                    curve_rows.append({"variant": variant, "join_mode": "NOT_APPLICABLE", "strategy_id": trade["strategy_id"],
                                       "timeframe": trade["timeframe"], "confluence_family": trade["family"],
                                       "setup_id": trade["setup_id"], "direction": trade["direction"],
                                       "cost_scenario": scenario, "decision_time": trade["decision_time"],
                                       "exit_time": trade["exit_time"], "net_r": trade["net_r"], "gross_r": trade["gross_r"]})
        run_rows.append({"run_id": f"R9-NA-{variant}", "program_id": PROGRAM_ID, "experiment_id": EXPERIMENT_ID,
                         "variant": variant, "join_mode": "NOT_APPLICABLE", "technical_baseline_sha256": lineage["technical_registry_sha256"],
                         "macro_links_sha256": lineage["macro_links_sha256"], "config_sha256": lineage["config_sha256"],
                         "retained_setups": len(ids), "retained_filled_medium": sum(row["fill_status"] == "FILLED" and row["setup_id"] in ids for row in medium), "status": "PASS"})
    write_parquet(out / "MACRO_BACKTEST_RUN_REGISTRY.parquet", run_rows, tuple(run_rows[0]))
    (out / "MACRO_BACKTEST_RUN_REGISTRY.jsonl").write_text("".join(canonical_json(row) + "\n" for row in run_rows), encoding="ascii")
    write_parquet(out / "MACRO_BACKTEST_SELECTIONS.parquet", selection_rows, tuple(selection_rows[0]))
    write_parquet(out / "MACRO_EQUITY_DRAWDOWN_CURVE_INPUTS.parquet", curve_rows, tuple(curve_rows[0]))

    (out / "MACRO_M15_RESULT_REPORT.md").write_text(report_text("Macro M15 Result Report", STRATEGIES[:2], metrics), encoding="ascii")
    (out / "MACRO_M5_RESULT_REPORT.md").write_text(report_text("Macro M5 Result Report", STRATEGIES[2:4], metrics), encoding="ascii")
    (out / "MACRO_M1_RESULT_REPORT.md").write_text(report_text("Macro M1 Result Report", STRATEGIES[4:6], metrics), encoding="ascii")
    (out / "MACRO_HIERARCHICAL_RESULT_REPORT.md").write_text(report_text("Macro Hierarchical Result Report", STRATEGIES[6:], metrics), encoding="ascii")

    t0 = _headline(metrics, "T0")
    primary = _headline(metrics, "M2_PRIMARY")
    control_summary = {v: _headline(metrics, v, join="J0" if v == "C3_OPPOSITE_MACRO" else "NOT_APPLICABLE") for v in ("C1_LONG_ONLY", "C2_SHORT_ONLY", "C3_OPPOSITE_MACRO", "C4_SIMPLE_D1_TREND")}
    comparison_md = f"""# Macro Timeframe Comparison

T0 reconciles **{t0['permitted_trades']}** medium-cost fills and **{t0['total_net_r']:.6f}R**. M2 Primary J0 retains **{primary['permitted_trades']}** fills and 0R; this is not an improvement claim because it is an inactive zero-trade filter.

The seven frozen strategy IDs remain separate in `MACRO_BACKTEST_METRICS.csv`; standalone M1 is never pooled with hierarchical M1. Low, medium, and high cost rows are explicit.
"""
    (out / "MACRO_TIMEFRAME_COMPARISON.md").write_text(comparison_md, encoding="ascii")
    (out / "MACRO_RANDOM_CONTROL_REPORT.md").write_text("# Macro Random Control Report\n\nAll 12 macro-variant/join targets retain zero fills. Retention-matched random sampling is `NOT_APPLICABLE_ZERO_RETENTION`; zero is not treated as a random distribution. Frozen seeds and requested 1,000 draws remain recorded in the CSV.\n", encoding="ascii")
    (out / "MACRO_WALK_FORWARD_REPORT.md").write_text("# Macro Walk-Forward Report\n\nSix expanding chronological outer folds are reported. Rules are fixed; no model is trained and no outer-fold optimization occurs. Setup intervals overlapping each test boundary are purged and the frozen one-source-day embargo is recorded. Every macro fold has zero retained fills, so fold expectancy and median candidate evidence are unavailable, not favorable zeroes.\n", encoding="ascii")
    (out / "MACRO_ANNUAL_PERFORMANCE_REPORT.md").write_text("# Macro Annual Performance Report\n\nAnnual, direction, strategy, join, and cost partitions are in `MACRO_BACKTEST_METRICS.csv`. Their sums reconcile to corresponding overall rows. Only 2021 is positive for pooled T0 medium cost; no macro variant has an active year because coverage leaves every link UNKNOWN.\n", encoding="ascii")
    (out / "MACRO_CATEGORY_CONTRIBUTION_REPORT.md").write_text("# Macro Category Contribution Report\n\nThis is descriptive, not causal. Category-score partitions are frozen from J0/J1/J2 links. Inflation, labour, and growth are UNKNOWN; monetary-policy/liquidity values may exist, but no row reaches the three-valid-category regime gate. Category contribution therefore cannot support a macro candidate.\n", encoding="ascii")
    (out / "MACRO_EQUITY_DRAWDOWN_INPUTS.md").write_text("# Macro Equity And Drawdown Inputs\n\nRole 10 must chart the complete chronological trade-level curves from the immutable Role 8 registry and the exact Role 9 selections. Role 9 metrics include full maximum-drawdown calculations for every strategy, variant, join, direction, year, and cost; negative T0 curves must remain visible.\n", encoding="ascii")

    decision = {
        "status": "INCONCLUSIVE", "decision": "INSUFFICIENT_ALIGNED_TRADES", "candidate": "NONE",
        "primary_join": "J0", "primary_variant": "M2_PRIMARY", "retained_filled_trades": primary["permitted_trades"],
        "minimum_required": config["candidate_gates"]["minimum_retained_filled_trades"],
        "gate_results": {
            "exact_t0_reconciliation": "PASS", "vintage_safe_daily_evidence": "PASS_WITH_CATEGORY_COVERAGE_LIMIT",
            "minimum_retained_fills": "FAIL_0_LT_30", "positive_medium_average_net_r": "NOT_APPLICABLE_ZERO_TRADES",
            "positive_medium_total_net_r": "FAIL_ZERO_NOT_POSITIVE", "positive_outer_fold_median": "NOT_APPLICABLE_ZERO_TRADES",
            "high_cost_improvement": "NOT_APPLICABLE_ZERO_TRADES", "j0_improvement": "FAIL_NO_ACTIVE_FILTER",
            "year_direction_concentration": "NOT_APPLICABLE_ZERO_TRADES", "beats_long_only": "FAIL_ZERO_TRADES",
            "beats_retention_random": "NOT_APPLICABLE_ZERO_RETENTION", "beats_opposite_macro": "NOT_DEMONSTRATED_BOTH_ZERO",
        },
        "t0_medium": t0, "controls_medium": control_summary,
        "failure_codes": ["BACKTEST_ENGINE_BUILDER_EVIDENCE_INSUFFICIENT", "INSUFFICIENT_CATEGORY_COVERAGE", "INSUFFICIENT_ALIGNED_TRADES"],
        "warnings": ["TECHNICAL_SOURCE_TIMEZONE_UNRESOLVED", "NAS100_SOURCE_LABEL_NOT_BROKER_CONFIRMED", "NORMALIZED_COSTS_NOT_BROKER_FACT", "REGISTRY_CHRONOLOGY_CAVEAT_FINAL_CHAMPION_VETO"],
        "protected_data_accesses": 0, "final_holdout_accesses": 0,
        "exact_next_permitted_action": "Role 10 Reporting and Visualization Engineer only; report and chart the frozen negative/zero evidence without changing inputs or starting audit/deployment.",
    }
    write_json(out / "MACRO_REGIME_CANDIDATE_DECISION.json", decision)
    (out / "MACRO_REGIME_CANDIDATE_DECISION.md").write_text(f"""# Macro Regime Candidate Decision

Decision: **INSUFFICIENT_ALIGNED_TRADES**. Candidate: **NONE**.

M2 Primary under headline J0 retains 0 filled trades, below the frozen minimum of 30. M1 Loose, M3 Strong Only, M4 High Coverage, and opposite-macro also retain zero under J0/J1/J2 because every Role 8 macro link is UNKNOWN. Coverage, thresholds, delays, weights, and technical outcomes were not changed.

T0 remains {t0['permitted_trades']} medium-cost fills and {t0['total_net_r']:.6f}R. A zero-trade result is inactivity, not profitability and not evidence that macro rescued the technical strategy. Random retention is not applicable at zero retention.

No final holdout, broker, deployment, paper, or live action was accessed. The chronology caveat remains a final-champion veto.
""", encoding="ascii")

    self_describing = {"ROLE9_BACKTEST_MANIFEST.json", "ROLE9_OUTPUT_HASHES.json", "ROLE9_TEST_RESULTS.json"}
    named_outputs = sorted(path for path in out.iterdir() if path.is_file() and path.name not in self_describing)
    output_hashes = {str(path.relative_to(root)): sha256_file(path) for path in named_outputs}
    write_json(out / "ROLE9_OUTPUT_HASHES.json", output_hashes)
    manifest = {
        "schema_version": "1.0.0", "artifact_id": "MACRO-REGIME-ROLE9-BACKTEST-MANIFEST-001",
        "request_id": "SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001-ROLE9",
        "program_id": PROGRAM_ID, "experiment_id": EXPERIMENT_ID, "created_at_utc": CREATED_AT_UTC,
        "created_by": "M15/M5/M1 Economic Backtest Researcher", "status": "INCONCLUSIVE",
        "git_commit": "WORKING_TREE_FROM_7ecf69f0849aa17d825f68a482431e2d08a45672",
        "code_version": sha256_file(root / CODE_PATH), "test_version": sha256_file(root / TEST_PATH),
        "config_checksum": lineage["config_sha256"], "random_seed": config["random_control"]["base_seed"],
        "decision": "INSUFFICIENT_ALIGNED_TRADES", "starting_commit": "7ecf69f0849aa17d825f68a482431e2d08a45672",
        "inputs": lineage, "config": config, "counts": {
            "technical_setups": 454, "technical_trade_rows": 1362, "medium_fills": 306, "medium_no_fills": 148,
            "metric_rows": len(metrics), "comparison_rows": len(comparisons), "walk_forward_rows": len(walk),
            "random_control_rows": len(random_rows), "category_contribution_rows": len(categories), "backtest_run_rows": len(run_rows),
            "selection_rows": len(selection_rows), "curve_input_rows": len(curve_rows),
            "macro_retained_fills_all_variants_all_joins": 0,
        },
        "primary_result": decision, "outputs": output_hashes,
        "assumptions": ["FROZEN_TECHNICAL_OUTCOMES_UNCHANGED", "FROZEN_D1_EMA20_EMA50_CONTROL_ALREADY_EMBEDDED_IN_T0", "NO_MODEL_TRAINING"],
        "limitations": decision["warnings"], "protected_data_accesses": 0, "final_holdout_accesses": 0,
        "registry_update": "Dedicated append-only MACRO_BACKTEST_RUN_REGISTRY JSONL/Parquet created; global experiment registry remains frozen to preserve Role 3/4 whole-file input hashes.",
        "deployment": "NOT_RUN_PROHIBITED", "rollback": "Delete only Role 9 outputs/code/test/config/preregistration and append a cancellation/reconciliation event; never rewrite registry history.",
        "exact_next_permitted_action": decision["exact_next_permitted_action"],
    }
    write_json(out / "ROLE9_BACKTEST_MANIFEST.json", manifest)
    return manifest


def validate(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = read_json(root / ROLE9 / "ROLE9_BACKTEST_MANIFEST.json")
    hashes = read_json(root / ROLE9 / "ROLE9_OUTPUT_HASHES.json")
    for relative, expected in hashes.items():
        if sha256_file(root / relative) != expected:
            raise BacktestError(f"BACKTEST_ENGINE_BUILDER_INVARIANT_FAILED:ROLE9_OUTPUT_HASH:{relative}")
    metrics = pq.read_table(root / ROLE9 / "MACRO_BACKTEST_METRICS.parquet").to_pylist()
    macro = [row for row in metrics if row["variant"] in MACRO_VARIANTS]
    if not macro or any(int(row["permitted_trades"]) != 0 for row in macro):
        raise BacktestError("BACKTEST_ENGINE_BUILDER_INVARIANT_FAILED:MACRO_ZERO_RETENTION")
    return {"status": "PASS", "decision": manifest["decision"], "metric_rows": len(metrics), "output_hashes": len(hashes)}


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = validate(args.root) if args.validate_only else generate(args.root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

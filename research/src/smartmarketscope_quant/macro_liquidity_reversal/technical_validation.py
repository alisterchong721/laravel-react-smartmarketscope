from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

from smartmarketscope_quant.validation import SampleInterval, build_cpcv, build_walk_forward

from .technical_economic import (
    EXPOSURE_LABEL,
    MODE,
    PRIMARY_SCENARIO,
    PROGRAM_ID,
    _sha256,
    validate_hash_registry,
)


FILLED_OUTCOMES = {"WIN_2R", "LOSS_1R", "TIMEOUT", "AMBIGUOUS_ADVERSE_FIRST"}
MINIMUM_EFFECTIVE = 30
CPCV_GROUPS = 6
CPCV_TEST_GROUPS = 2
OUTER_TEST_SIZE = 10


class TechnicalValidationError(ValueError):
    pass


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _serializable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(item) for item in value]
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="ascii", newline="") as handle:
        return list(csv.DictReader(handle))


def _quantile(values: Sequence[Decimal], probability: Decimal) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = probability * Decimal(len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def validate_primary_lock(repo_root: Path) -> dict[str, str]:
    artifact_root = repo_root / "research/artifacts/macro_liquidity_reversal"
    registry = validate_hash_registry(artifact_root / "MLR_TECHNICAL_ECONOMIC_EXPERIMENT_REGISTRY.jsonl")
    completed = next(
        (
            row["payload"]
            for row in reversed(registry)
            if row["payload"].get("status") == "PRIMARY_PASS_COMPLETED_HASH_LOCKED"
        ),
        None,
    )
    if completed is None:
        raise TechnicalValidationError("MLR_PRIMARY_PASS_NOT_HASH_LOCKED")
    for relative, expected in completed["artifact_sha256"].items():
        if _sha256(repo_root / relative) != expected:
            raise TechnicalValidationError(f"MLR_PRIMARY_ARTIFACT_CHANGED:{relative}")
    return completed["artifact_sha256"]


def load_effective_rows(repo_root: Path) -> dict[str, list[dict[str, str]]]:
    artifact_root = repo_root / "research/artifacts/macro_liquidity_reversal"
    rows = [
        row
        for row in _read_csv(artifact_root / "MLR_TECHNICAL_PRIMARY_TRADES.csv")
        if row["scenario_id"] == PRIMARY_SCENARIO and row["outcome"] in FILLED_OUTCOMES
    ]
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["strategy_id"]].append(row)
    effective: dict[str, list[dict[str, str]]] = {}
    for strategy, strategy_rows in grouped.items():
        ordered = sorted(
            strategy_rows,
            key=lambda row: (row["entry_path_available_at"], row["exit_time"], row["setup_id"]),
        )
        selected: list[dict[str, str]] = []
        prior_exit: datetime | None = None
        for row in ordered:
            entry = datetime.fromisoformat(row["entry_path_available_at"])
            exit_time = datetime.fromisoformat(row["exit_time"])
            if prior_exit is None or entry > prior_exit:
                selected.append(row)
                prior_exit = exit_time
        effective[strategy] = selected
    return effective


def build_samples(
    rows: Sequence[dict[str, str]],
    event_information_start: dict[str, datetime],
) -> tuple[list[SampleInterval], dict[str, dict[str, str]]]:
    samples: list[SampleInterval] = []
    by_id: dict[str, dict[str, str]] = {}
    for row in rows:
        sample_id = row["setup_id"]
        decision = datetime.fromisoformat(row["decision_time"])
        label_start = datetime.fromisoformat(row["entry_path_available_at"])
        label_end = datetime.fromisoformat(row["exit_time"])
        sample = SampleInterval(
            sample_id=sample_id,
            information_start=event_information_start[row["event_id"]],
            information_end=decision,
            decision_timestamp=decision,
            label_start=label_start,
            label_end=label_end,
        )
        samples.append(sample)
        by_id[sample_id] = row
    samples.sort(key=lambda item: item.decision_timestamp)
    return samples, by_id


def _partition_metrics(ids: Sequence[str], by_id: dict[str, dict[str, str]]) -> dict[str, Any]:
    values = [_decimal(by_id[sample_id]["net_r"]) for sample_id in ids]
    return {
        "trades": len(values),
        "total_net_r": sum(values, Decimal("0")),
        "average_net_r": sum(values, Decimal("0")) / len(values) if values else None,
        "positive": sum(values, Decimal("0")) > 0,
    }


def evaluate_cpcv(
    samples: list[SampleInterval],
    by_id: dict[str, dict[str, str]],
) -> dict[str, Any]:
    result = build_cpcv(
        samples,
        n_groups=CPCV_GROUPS,
        k_test_groups=CPCV_TEST_GROUPS,
        embargo_mode="BARS",
        embargo_value=1,
    )
    splits = []
    for split in result.splits:
        metrics = _partition_metrics(split.test_ids, by_id)
        splits.append(
            {
                "split_id": split.split_id,
                "train_count": len(split.train_ids),
                "test_count": len(split.test_ids),
                "purged_count": len(split.purged_ids),
                "embargoed_count": len(split.embargoed_ids),
                **metrics,
            }
        )
    averages = [_decimal(item["average_net_r"]) for item in splits]
    return {
        "status": "DESCRIPTIVE_FIXED_RULE_NO_SELECTION",
        "split_count": result.split_count,
        "path_count": result.path_count,
        "positive_split_fraction": Decimal(sum(item["positive"] for item in splits)) / len(splits),
        "median_test_net_r_per_trade": _decimal(statistics.median(averages)),
        "lower_quartile_test_net_r_per_trade": _quantile(averages, Decimal("0.25")),
        "worst_split_net_r_per_trade": min(averages),
        "splits": splits,
    }


def evaluate_walk_forward(
    samples: list[SampleInterval],
    by_id: dict[str, dict[str, str]],
) -> dict[str, Any]:
    splits = build_walk_forward(
        samples,
        minimum_train_samples=MINIMUM_EFFECTIVE,
        test_samples=OUTER_TEST_SIZE,
        retraining_delay=timedelta(0),
    )
    folds = []
    for split in splits:
        metrics = _partition_metrics(split.test_ids, by_id)
        folds.append(
            {
                "fold_id": split.split_id,
                "train_count": len(split.train_ids),
                "test_count": len(split.test_ids),
                "purged_count": len(split.purged_ids),
                **metrics,
            }
        )
    averages = [_decimal(item["average_net_r"]) for item in folds]
    return {
        "status": "DESCRIPTIVE_FIXED_RULE_NO_RETRAINING",
        "fold_count": len(folds),
        "positive_fold_fraction": Decimal(sum(item["positive"] for item in folds)) / len(folds),
        "median_fold_net_r_per_trade": _decimal(statistics.median(averages)),
        "lower_quartile_fold_net_r_per_trade": _quantile(averages, Decimal("0.25")),
        "worst_fold_net_r_per_trade": min(averages),
        "folds": folds,
    }


def evaluate(repo_root: Path) -> dict[str, Any]:
    input_hashes = validate_primary_lock(repo_root)
    artifact_root = repo_root / "research/artifacts/macro_liquidity_reversal"
    event_rows = _read_csv(artifact_root / "MLR_EVENT_REGISTRY.csv")
    event_starts = {
        row["event_id"]: datetime.fromisoformat(row["d1_candle1_start"])
        for row in event_rows
    }
    effective = load_effective_rows(repo_root)
    strategy_results: dict[str, Any] = {}
    for strategy, rows in sorted(effective.items()):
        samples, by_id = build_samples(rows, event_starts)
        if len(samples) < MINIMUM_EFFECTIVE:
            strategy_results[strategy] = {
                "effective_filled_trades": len(samples),
                "status": "INSUFFICIENT_FOR_RELIABLE_MODEL_SELECTION",
                "cpcv": None,
                "outer_walk_forward": None,
            }
            continue
        strategy_results[strategy] = {
            "effective_filled_trades": len(samples),
            "status": "RULE_BASED_VALIDATION_PERMITTED",
            "cpcv": evaluate_cpcv(samples, by_id),
            "outer_walk_forward": evaluate_walk_forward(samples, by_id),
        }
    summary = {
        "schema_version": "1.0.0",
        "program_id": PROGRAM_ID,
        "experiment_id": "MLR-TECH-VAL-001",
        "mode": MODE,
        "historical_exposure": EXPOSURE_LABEL,
        "full_macro_strategy_status": "BLOCKED_BY_UNCERTIFIED_MACRO_BIAS",
        "input_artifact_sha256": input_hashes,
        "machine_learning_permission": "PROHIBITED_MAXIMUM_EFFECTIVE_SAMPLE_BELOW_100",
        "strategy_results": strategy_results,
        "prohibitions": {
            "post_2026_06_28_access": False,
            "final_holdout_access": False,
            "automatic_promotion": False,
        },
    }
    serializable = _serializable(summary)
    (artifact_root / "MLR_TECHNICAL_VALIDATION_SUMMARY.json").write_text(
        json.dumps(serializable, indent=2, ensure_ascii=True) + "\n",
        encoding="ascii",
    )
    _write_reports(artifact_root, serializable)
    return serializable


def _number(value: Any) -> str:
    return "N/A" if value is None else f"{float(value):.3f}"


def _percent(value: Any) -> str:
    return "N/A" if value is None else f"{float(value) * 100:.1f}%"


def _write_reports(artifact_root: Path, summary: dict[str, Any]) -> None:
    cpcv_lines = [
        "# MLR Technical CPCV Report",
        "",
        "Status: `TECHNICAL_ONLY_ABLATION` on `PREVIOUSLY_EXPOSED_WINDOW`.",
        "",
        "CPCV is descriptive for a fixed rule; it performs no candidate selection and is not independent proof of robustness.",
        "",
        "| Strategy | Effective fills | Status | Splits | Positive splits | Median test R/trade | Lower quartile | Worst |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    walk_lines = [
        "# MLR Technical Walk-Forward Report",
        "",
        "Status: `TECHNICAL_ONLY_ABLATION` on `PREVIOUSLY_EXPOSED_WINDOW`.",
        "",
        "The rule is frozen and not retrained. Full setup-to-exit intervals are purged from prior training context before each expanding chronological test fold.",
        "",
        "| Strategy | Effective fills | Status | Folds | Positive folds | Median fold R/trade | Lower quartile | Worst |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for strategy, result in summary["strategy_results"].items():
        cpcv = result["cpcv"] or {}
        walk = result["outer_walk_forward"] or {}
        cpcv_lines.append(
            f"| {strategy} | {result['effective_filled_trades']} | {result['status']} | "
            f"{cpcv.get('split_count', 0)} | {_percent(cpcv.get('positive_split_fraction'))} | "
            f"{_number(cpcv.get('median_test_net_r_per_trade'))} | "
            f"{_number(cpcv.get('lower_quartile_test_net_r_per_trade'))} | "
            f"{_number(cpcv.get('worst_split_net_r_per_trade'))} |"
        )
        walk_lines.append(
            f"| {strategy} | {result['effective_filled_trades']} | {result['status']} | "
            f"{walk.get('fold_count', 0)} | {_percent(walk.get('positive_fold_fraction'))} | "
            f"{_number(walk.get('median_fold_net_r_per_trade'))} | "
            f"{_number(walk.get('lower_quartile_fold_net_r_per_trade'))} | "
            f"{_number(walk.get('worst_fold_net_r_per_trade'))} |"
        )
    cpcv_lines.extend(["", "ML is prohibited: the maximum effective filled-trade sample is below 100."])
    walk_lines.extend(["", "No outer fold is a pristine holdout; the historical pool was already exposed."])
    (artifact_root / "MLR_TECHNICAL_CPCV_REPORT.md").write_text("\n".join(cpcv_lines) + "\n", encoding="ascii")
    (artifact_root / "MLR_TECHNICAL_WALK_FORWARD_REPORT.md").write_text(
        "\n".join(walk_lines) + "\n", encoding="ascii"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the frozen MLR technical economic pass")
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.repo_root.resolve())
    print(json.dumps({key: value["effective_filled_trades"] for key, value in result["strategy_results"].items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

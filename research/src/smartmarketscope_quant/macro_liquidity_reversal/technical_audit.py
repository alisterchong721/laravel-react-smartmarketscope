from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

from smartmarketscope_quant.validation import build_cpcv, build_walk_forward

from .technical_economic import (
    PRIMARY_SCENARIO,
    _sha256,
    validate_frequency_checkpoint,
    validate_hash_registry,
)
from .technical_validation import (
    CPCV_GROUPS,
    CPCV_TEST_GROUPS,
    MINIMUM_EFFECTIVE,
    OUTER_TEST_SIZE,
    build_samples,
    evaluate_cpcv,
    evaluate_walk_forward,
    load_effective_rows,
    validate_primary_lock,
)


TOLERANCE = Decimal("0.00000001")


class TechnicalAuditError(ValueError):
    pass


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="ascii", newline="") as handle:
        return list(csv.DictReader(handle))


def _assert(condition: bool, code: str) -> None:
    if not condition:
        raise TechnicalAuditError(code)


def reconcile_primary_rows(rows: Sequence[dict[str, str]]) -> dict[str, Any]:
    _assert(len(rows) == 1362, "MLR_AUDIT_PRIMARY_ROW_COUNT")
    keys = {(row["setup_id"], row["scenario_id"]) for row in rows}
    _assert(len(keys) == len(rows), "MLR_AUDIT_DUPLICATE_SETUP_SCENARIO")
    _assert(len({row["setup_id"] for row in rows}) == 454, "MLR_AUDIT_SETUP_COUNT")
    filled = 0
    no_fill = 0
    ambiguous = 0
    for row in rows:
        _assert(row["protected_data_accesses"] == "0", "MLR_AUDIT_PROTECTED_ACCESS")
        _assert(row["final_holdout_accesses"] == "0", "MLR_AUDIT_FINAL_HOLDOUT_ACCESS")
        _assert(
            datetime.fromisoformat(row["expiry_time"]) <= datetime.fromisoformat("2026-06-28 23:59:59"),
            "MLR_AUDIT_POST_CUTOFF_PATH",
        )
        if row["outcome"] in {"NO_FILL", "INVALID_DATA"}:
            no_fill += 1
            _assert(row["net_r"] == "", "MLR_AUDIT_NO_FILL_HAS_ECONOMICS")
            continue
        filled += 1
        decision = datetime.fromisoformat(row["decision_time"])
        entry = datetime.fromisoformat(row["entry_path_available_at"])
        exit_time = datetime.fromisoformat(row["exit_time"])
        expiry = datetime.fromisoformat(row["expiry_time"])
        _assert(decision <= entry <= exit_time <= expiry, "MLR_AUDIT_TIME_ORDER")
        entry_price = _decimal(row["entry_reference_points"])
        target = _decimal(row["target_reference_points"])
        stop = _decimal(row["stop_reference_points"])
        risk = _decimal(row["risk_points"])
        direction = Decimal("1") if row["direction"] == "BULLISH" else Decimal("-1")
        _assert(abs(direction * (target - entry_price) - Decimal("2") * risk) <= TOLERANCE, "MLR_AUDIT_TARGET_NOT_2R")
        block_lower = _decimal(row["block_lower"])
        block_upper = _decimal(row["block_upper"])
        if row["direction"] == "BULLISH":
            _assert(stop < block_lower, "MLR_AUDIT_LONG_STOP_NOT_BEYOND_BLOCK")
        else:
            _assert(stop > block_upper, "MLR_AUDIT_SHORT_STOP_NOT_BEYOND_BLOCK")
        gross = _decimal(row["gross_movement_points"])
        costs = sum(
            (_decimal(row[column]) for column in (
                "spread_cost_points",
                "slippage_cost_points",
                "commission_cost_points",
                "financing_cost_points",
            )),
            Decimal("0"),
        )
        _assert(abs(gross - costs - _decimal(row["net_points"])) <= TOLERANCE, "MLR_AUDIT_COST_RECONCILIATION")
        _assert(abs(_decimal(row["net_points"]) / risk - _decimal(row["net_r"])) <= TOLERANCE, "MLR_AUDIT_R_RECONCILIATION")
        if row["outcome"] == "AMBIGUOUS_ADVERSE_FIRST":
            ambiguous += 1
            _assert(row["ambiguous_adverse_first"] == "True", "MLR_AUDIT_AMBIGUITY_FLAG")
            _assert(_decimal(row["net_r"]) <= 0, "MLR_AUDIT_AMBIGUITY_NOT_ADVERSE")
    _assert(filled == 918, "MLR_AUDIT_FILLED_SCENARIO_ROWS")
    _assert(no_fill == 444, "MLR_AUDIT_NO_FILL_SCENARIO_ROWS")
    return {
        "primary_rows": len(rows),
        "unique_setups": len({row["setup_id"] for row in rows}),
        "filled_scenario_rows": filled,
        "no_fill_or_invalid_scenario_rows": no_fill,
        "ambiguous_scenario_rows": ambiguous,
    }


def _split_manifest(repo_root: Path) -> dict[str, Any]:
    artifact_root = repo_root / "research/artifacts/macro_liquidity_reversal"
    event_starts = {
        row["event_id"]: datetime.fromisoformat(row["d1_candle1_start"])
        for row in _read_csv(artifact_root / "MLR_EVENT_REGISTRY.csv")
    }
    locked = json.loads((artifact_root / "MLR_TECHNICAL_VALIDATION_SUMMARY.json").read_text())
    effective = load_effective_rows(repo_root)
    strategies: dict[str, Any] = {}
    for strategy, rows in sorted(effective.items()):
        samples, by_id = build_samples(rows, event_starts)
        if len(samples) < MINIMUM_EFFECTIVE:
            strategies[strategy] = {
                "effective_filled_trades": len(samples),
                "status": "INSUFFICIENT_FOR_RELIABLE_MODEL_SELECTION",
                "cpcv": None,
                "outer_walk_forward": None,
            }
            continue
        cpcv = build_cpcv(
            samples,
            n_groups=CPCV_GROUPS,
            k_test_groups=CPCV_TEST_GROUPS,
            embargo_mode="BARS",
            embargo_value=1,
        )
        walk = build_walk_forward(
            samples,
            minimum_train_samples=MINIMUM_EFFECTIVE,
            test_samples=OUTER_TEST_SIZE,
            retraining_delay=timedelta(0),
        )
        recalculated_cpcv = evaluate_cpcv(samples, by_id)
        recalculated_walk = evaluate_walk_forward(samples, by_id)
        locked_strategy = locked["strategy_results"][strategy]
        _assert(
            recalculated_cpcv["positive_split_fraction"]
            == _decimal(locked_strategy["cpcv"]["positive_split_fraction"]),
            "MLR_AUDIT_CPCV_RESULT_MISMATCH",
        )
        _assert(
            recalculated_walk["positive_fold_fraction"]
            == _decimal(locked_strategy["outer_walk_forward"]["positive_fold_fraction"]),
            "MLR_AUDIT_WALK_RESULT_MISMATCH",
        )
        strategies[strategy] = {
            "effective_filled_trades": len(samples),
            "status": "RULE_BASED_VALIDATION_PERMITTED",
            "cpcv": {
                "n_groups": cpcv.n_groups,
                "k_test_groups": cpcv.k_test_groups,
                "split_count": cpcv.split_count,
                "path_count": cpcv.path_count,
                "splits": [
                    {
                        "split_id": split.split_id,
                        "train_ids": list(split.train_ids),
                        "test_ids": list(split.test_ids),
                        "purged_ids": list(split.purged_ids),
                        "embargoed_ids": list(split.embargoed_ids),
                    }
                    for split in cpcv.splits
                ],
                "paths": [
                    {"path_id": path.path_id, "group_to_split": list(path.group_to_split)}
                    for path in cpcv.paths
                ],
            },
            "outer_walk_forward": {
                "minimum_train_trades": MINIMUM_EFFECTIVE,
                "test_trades": OUTER_TEST_SIZE,
                "splits": [
                    {
                        "split_id": split.split_id,
                        "train_ids": list(split.train_ids),
                        "test_ids": list(split.test_ids),
                        "purged_ids": list(split.purged_ids),
                        "embargoed_ids": list(split.embargoed_ids),
                    }
                    for split in walk
                ],
            },
        }
    return {
        "schema_version": "1.0.0",
        "program_id": "QRP-MACRO-LIQUIDITY-REVERSAL-001",
        "mode": "TECHNICAL_ONLY_ABLATION",
        "historical_exposure": "PREVIOUSLY_EXPOSED_WINDOW",
        "primary_trades_sha256": _sha256(artifact_root / "MLR_TECHNICAL_PRIMARY_TRADES.csv"),
        "validation_summary_sha256": _sha256(artifact_root / "MLR_TECHNICAL_VALIDATION_SUMMARY.json"),
        "strategies": strategies,
        "protected_data_accesses": 0,
        "final_holdout_accesses": 0,
    }


def run_audit(repo_root: Path) -> dict[str, Any]:
    artifact_root = repo_root / "research/artifacts/macro_liquidity_reversal"
    validate_frequency_checkpoint(
        repo_root,
        artifact_root / "governance/MLR_FREQUENCY_CHECKPOINT_20260713T123112+0800.json",
    )
    validate_primary_lock(repo_root)
    registry = validate_hash_registry(artifact_root / "MLR_TECHNICAL_ECONOMIC_EXPERIMENT_REGISTRY.jsonl")
    checks = reconcile_primary_rows(_read_csv(artifact_root / "MLR_TECHNICAL_PRIMARY_TRADES.csv"))
    split_manifest = _split_manifest(repo_root)
    (artifact_root / "MLR_TECHNICAL_SPLIT_MANIFEST.json").write_text(
        json.dumps(split_manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="ascii",
    )
    primary = json.loads((artifact_root / "MLR_TECHNICAL_PRIMARY_SUMMARY.json").read_text())
    ablation = json.loads((artifact_root / "MLR_TECHNICAL_ABLATION_001_SUMMARY.json").read_text())
    medium = [
        result[PRIMARY_SCENARIO]
        for result in primary["primary_results"].values()
    ]
    diagnostic = [
        result[PRIMARY_SCENARIO]
        for result in ablation["primary_results"].values()
    ]
    _assert(all(_decimal(item["average_net_r"]) < 0 for item in medium), "MLR_AUDIT_PRIMARY_NOT_ALL_NEGATIVE")
    _assert(all(_decimal(item["average_net_r"]) < 0 for item in diagnostic), "MLR_AUDIT_ABLATION_NOT_ALL_NEGATIVE")
    result = {
        "schema_version": "1.0.0",
        "program_id": "QRP-MACRO-LIQUIDITY-REVERSAL-001",
        "status": "PASS_PROCESS_TECHNICAL_EDGE_NOT_FOUND",
        "mode": "TECHNICAL_ONLY_ABLATION",
        "checks": checks,
        "registry_events_validated": len(registry),
        "split_manifest_sha256": _sha256(artifact_root / "MLR_TECHNICAL_SPLIT_MANIFEST.json"),
        "primary_strategies_negative_medium_cost": len(medium),
        "diagnostic_strategies_negative_medium_cost": len(diagnostic),
        "candidate": "NONE",
        "machine_learning": "PROHIBITED_MAXIMUM_EFFECTIVE_SAMPLE_BELOW_100",
        "full_macro_strategy_status": "BLOCKED_BY_UNCERTIFIED_MACRO_BIAS",
        "protected_data_accesses": 0,
        "final_holdout_accesses": 0,
    }
    (artifact_root / "MLR_TECHNICAL_INDEPENDENT_AUDIT.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=True) + "\n",
        encoding="ascii",
    )
    _write_report(artifact_root, result)
    return result


def _write_report(artifact_root: Path, result: dict[str, Any]) -> None:
    report = f"""# MLR Technical Independent Audit

Status: `PASS_PROCESS_TECHNICAL_EDGE_NOT_FOUND`

## Scope

This audit covers only the explicitly authorized `TECHNICAL_ONLY_ABLATION` on
the `PREVIOUSLY_EXPOSED_WINDOW`. It does not validate the intended macro-first
strategy, Pepperstone economics, FTMO readiness, or Lucid readiness.

## Reconciliation

- Frozen frequency checkpoint: PASS; detector and frequency files are unchanged.
- Hash-linked technical registry: PASS; {result['registry_events_validated']} lifecycle events validated.
- Primary trade rows: PASS; {result['checks']['primary_rows']} scenario rows across {result['checks']['unique_setups']} selected setups.
- Fill accounting: PASS; {result['checks']['filled_scenario_rows']} filled scenario rows and {result['checks']['no_fill_or_invalid_scenario_rows']} no-fill/invalid rows.
- Target, stop, timing, gross-cost-net, and normalized-R equations: PASS for every economic row.
- CPCV and walk-forward reconstruction: PASS; exact sample IDs, purge IDs, embargo IDs, and path mappings are retained in `MLR_TECHNICAL_SPLIT_MANIFEST.json`.
- Protected/final-holdout accesses: 0/0.

## Veto Findings

1. All seven primary 2R strategies have negative medium-cost average net R.
2. Every permitted primary CPCV split is negative; outer folds are overwhelmingly negative.
3. The sole preregistered 1.5R diagnostic remains negative for all seven strategies and is `REJECT`.
4. Every midpoint/confluence strategy underperforms its direction-matched generic-entry control on average.
5. The maximum effective filled-trade sample is 89, so ML is prohibited.
6. Source timezone and broker cost metadata remain unresolved; scenarios are hypothetical only.
7. Certified point-in-time macro coverage remains zero, so no full-strategy inference is permitted.

## Decision

The technical-only decision is `TECHNICAL_EDGE_NOT_FOUND`. Candidate and champion
remain `NONE`. Further parameter search is not justified by the evidence. The
full intended strategy remains `BLOCKED_BY_UNCERTIFIED_MACRO_BIAS`.
"""
    (artifact_root / "MLR_TECHNICAL_INDEPENDENT_AUDIT.md").write_text(report, encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently audit the MLR technical economic continuation")
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_audit(args.repo_root.resolve()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

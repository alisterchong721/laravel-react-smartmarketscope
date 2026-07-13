from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import numpy as np

from smartmarketscope_quant.data_audit.io import sha256_file, sha256_paths
from smartmarketscope_quant.governance.preregistration import validate_preregistration
from smartmarketscope_quant.governance.registry import read_registry, validate_registry
from smartmarketscope_quant.nested_research.candidates import expand_candidates
from smartmarketscope_quant.nested_research.data import (
    load_barrier_event_samples,
    load_daily_event_samples,
)
from smartmarketscope_quant.validation.cpcv import build_cpcv


class PhaseJValidationError(ValueError):
    pass


PREDICTION_FIELDS = [
    "experiment_id",
    "outer_fold_id",
    "scope",
    "candidate_id",
    "split_id",
    "group_id",
    "sample_id",
    "decision_timestamp_source",
    "accepted",
    "probability",
    "target",
    "direction_success",
    "low_cost_net_pnl_usd",
    "medium_cost_net_pnl_usd",
    "high_cost_net_pnl_usd",
]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PhaseJValidationError(message)


def _canonical_hash(value: object) -> str:
    content = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(content.encode("ascii")).hexdigest()


def _load_samples(repo_root: Path, config: dict, experiment: dict):
    family = experiment["family"]
    if family == "H1_VOLATILITY_COMPRESSION_BREAKOUT":
        return load_barrier_event_samples(repo_root, config)[0]
    include_h1 = family in {
        "EFFICIENCY_GATED_DAILY_MOMENTUM",
        "MOMENTUM_TRADE_ACCEPTANCE_LOGISTIC",
    }
    if "candidates" in experiment:
        lookback = max(int(item["lookback_daily_bars"]) for item in experiment["candidates"])
        hold = max(int(item["holding_daily_bars"]) for item in experiment["candidates"])
    else:
        lookback = int(experiment.get("lookback_daily_bars", 20))
        hold = int(experiment.get("holding_daily_bars", 5))
    return load_daily_event_samples(
        repo_root,
        config,
        maximum_lookback=lookback,
        maximum_hold=hold,
        include_h1_features=include_h1,
    )


def _fold_samples(samples, fold: dict, role: str):
    if role == "train":
        start = datetime.fromisoformat(fold["train_start"])
        end = datetime.fromisoformat(fold["train_end_exclusive"])
        return [
            sample
            for sample in samples
            if sample.interval.decision_timestamp >= start and sample.interval.label_end < end
        ]
    start = datetime.fromisoformat(fold["test_start"])
    end = datetime.fromisoformat(fold["test_end_exclusive"])
    return [
        sample
        for sample in samples
        if sample.interval.decision_timestamp >= start
        and sample.interval.decision_timestamp < end
        and sample.interval.label_end < end
    ]


def _read_csv_gzip(path: Path) -> tuple[list[str], list[dict]]:
    with gzip.open(path, "rt", encoding="ascii", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def _assert_close(actual: float, expected: float, message: str, tolerance: float = 1e-6) -> None:
    if abs(actual - expected) > tolerance:
        raise PhaseJValidationError(f"{message}: {actual} != {expected}")


def _expected_reasons(experiment: dict, result: dict, config: dict) -> set[str]:
    gates = config["outer_survival_gates"]
    folds = result["outer_folds"]
    aggregate = result["outer_aggregate"]
    reasons = set()
    if sum(fold["selected_candidate_id"] is not None for fold in folds) < int(gates["minimum_outer_folds"]):
        reasons.add("OUTER_FOLD_WITHOUT_ELIGIBLE_INNER_CANDIDATE")
    fold_nets = [
        fold["metrics"]["net_by_scenario"]["NORMALIZED_MEDIUM_COST"] if fold["metrics"] else 0.0
        for fold in folds
    ]
    if aggregate["net_by_scenario"]["NORMALIZED_MEDIUM_COST"] <= 0:
        reasons.add("AGGREGATE_MEDIUM_COST_NET_NONPOSITIVE")
    if float(np.quantile(fold_nets, 0.25)) <= 0:
        reasons.add("LOWER_QUARTILE_OUTER_FOLD_NET_NONPOSITIVE")
    if sum(value > 0 for value in fold_nets) / len(fold_nets) < float(gates["minimum_profitable_fold_fraction"]):
        reasons.add("PROFITABLE_OUTER_FOLD_FRACTION_LOW")
    if aggregate["net_by_scenario"]["NORMALIZED_HIGH_COST"] <= 0:
        reasons.add("AGGREGATE_HIGH_COST_NET_NONPOSITIVE")
    minimum_trades = int(experiment.get("additional_gates", {}).get("minimum_aggregate_trades", gates["minimum_aggregate_trades"]))
    if aggregate["trade_count"] < minimum_trades:
        reasons.add("OUTER_TRADE_COUNT_LOW")
    decay = result["maximum_absolute_train_to_test_decay"]
    if decay is None or decay > float(gates["maximum_absolute_train_to_test_decay"]):
        reasons.add("TRAIN_TO_TEST_DECAY_EXCESSIVE_OR_UNAVAILABLE")
    if experiment["family"] == "MOMENTUM_TRADE_ACCEPTANCE_LOGISTIC":
        probability = result["outer_probability_metrics"]
        if probability is None:
            reasons.add("OUTER_PROBABILITY_METRICS_UNAVAILABLE")
        else:
            if probability["brier_score"] >= probability["reference_brier_score"]:
                reasons.add("OUTER_BRIER_NO_SKILL")
            if probability["log_loss"] >= probability["reference_log_loss"]:
                reasons.add("OUTER_LOG_LOSS_NO_SKILL")
        candidate_q = float(np.quantile(fold_nets, 0.25))
        control_ids = sorted({key for fold in folds for key in fold.get("controls", {})})
        for control_id in control_ids:
            control_nets = [
                fold.get("controls", {}).get(control_id, {"metrics": {"net_by_scenario": {"NORMALIZED_MEDIUM_COST": 0}}})["metrics"]["net_by_scenario"]["NORMALIZED_MEDIUM_COST"]
                for fold in folds
            ]
            if candidate_q <= float(np.quantile(control_nets, 0.25)):
                reasons.add(f"NON_ML_CONTROL_LOWER_QUARTILE_NOT_BEATEN:{control_id}")
    if experiment["family"] == "H1_VOLATILITY_COMPRESSION_BREAKOUT":
        selected_success = aggregate.get("direction_success_rate")
        controls = [
            (control["metrics"].get("direction_success_rate"), control["metrics"].get("trade_count", 0))
            for fold in folds
            for control in fold.get("controls", {}).values()
            if control["metrics"].get("direction_success_rate") is not None
        ]
        weight = sum(count for _, count in controls)
        control_success = sum(rate * count for rate, count in controls) / weight if weight else None
        if selected_success is None or control_success is None or selected_success <= control_success:
            reasons.add("DIRECTIONAL_SUCCESS_DID_NOT_BEAT_CONTROL")
    return reasons


def _validate_registry_lifecycle(
    states: list[str] | None,
    terminal_payload: dict | None,
    experiment: dict,
    result: dict,
    summary: dict,
) -> None:
    running = ["PREREGISTERED", "STARTED"]
    completed = [*running, "COMPLETED"]
    _require(states in {tuple(running), tuple(completed)} if isinstance(states, tuple) else states in [running, completed], "Unexpected Phase J registry lifecycle")
    if states == running:
        return

    _require(terminal_payload is not None, "Completed Phase J lifecycle has no terminal payload")
    _require(terminal_payload.get("event_type") == "COMPLETED", "Phase J terminal event type mismatch")
    _require(terminal_payload.get("status") == "COMPLETED", "Phase J terminal status mismatch")
    _require(terminal_payload.get("decision") == result["decision"], "Phase J terminal decision mismatch")
    _require(
        int(terminal_payload.get("number_of_trials", -1)) == int(experiment["trial_budget"]),
        "Phase J terminal trial count mismatch",
    )
    _require(terminal_payload.get("config_checksum") == summary["config_sha256"], "Phase J terminal config hash mismatch")
    _require(terminal_payload.get("code_version") == summary["code_sha256"], "Phase J terminal code hash mismatch")
    _require(
        set(terminal_payload.get("rejection_reason", [])) == set(result["rejection_reasons"]),
        "Phase J terminal rejection reasons mismatch",
    )
    metrics = terminal_payload.get("validation_metrics", {})
    _require(metrics.get("outer_trade_log_sha256") == result["outer_trade_log_sha256"], "Phase J terminal trade-log hash mismatch")
    _require(metrics.get("outer_prediction_log_sha256") == result["outer_prediction_log_sha256"], "Phase J terminal prediction-log hash mismatch")
    _require(
        terminal_payload.get("robustness_metrics") == "NOT_APPLICABLE_NO_PHASE_J_SURVIVOR",
        "Phase J terminal robustness handoff mismatch",
    )
    _require(
        terminal_payload.get("prop_metrics") == "NOT_APPLICABLE_NO_PHASE_J_SURVIVOR",
        "Phase J terminal prop handoff mismatch",
    )


def validate_phase_j(repo_root: Path, config_path: Path) -> dict:
    repo_root = repo_root.resolve()
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="ascii"))
    summary_path = repo_root / "research/artifacts/nested/phase_j/summary.json"
    summary = json.loads(summary_path.read_text(encoding="ascii"))
    _require(summary["status"] == "COMPLETED_NO_AUTOMATIC_PROMOTION", "Phase J status mismatch")
    _require(summary["config_sha256"] == sha256_file(config_path), "Phase J config hash mismatch")
    code_paths = sorted((repo_root / "research/src/smartmarketscope_quant/nested_research").glob("*.py"))
    code_hash = sha256_paths(code_paths, path_root=repo_root)
    _require(summary["code_sha256"] == code_hash, "Phase J execution code hash mismatch")
    _require(summary["experiment_count"] == 7 and summary["candidate_trial_count"] == 28, "Phase J budget mismatch")
    _require(summary["final_holdout_access_count"] == 0, "Phase J accessed final holdout")
    _require(summary["automatic_champion_replacement"] is False, "Phase J enabled automatic promotion")
    _require(summary["paper_trading_started"] is False, "Phase J started paper trading")

    registry = validate_registry(repo_root / "EXPERIMENT_REGISTRY.jsonl")
    registry_events = read_registry(repo_root / "EXPERIMENT_REGISTRY.jsonl")
    latest_payload = {
        event["payload"]["experiment_id"]: event["payload"] for event in registry_events
    }
    input_rows = 0
    inner_prediction_rows = 0
    outer_prediction_rows = 0
    validated_trade_rows = 0
    selection_lock_count = 0
    decisions = {}
    experiment_by_id = {item["experiment_id"]: item for item in config["experiments"]}

    for experiment_id, result in summary["experiments"].items():
        experiment = experiment_by_id[experiment_id]
        _validate_registry_lifecycle(
            registry["states"].get(experiment_id),
            latest_payload.get(experiment_id),
            experiment,
            result,
            summary,
        )
        preregistration = validate_preregistration(
            repo_root / "research/preregistrations" / f"{experiment_id}.json"
        )
        _require(result["candidate_trial_count"] == len(expand_candidates(experiment)), f"Trial count mismatch for {experiment_id}")
        samples = _load_samples(repo_root, config, experiment)
        input_rows += len(samples)
        sample_by_id = {sample.interval.sample_id: sample for sample in samples}
        expected_outer_ids = set()
        accepted_outer_keys = set()

        for fold_config, fold in zip(config["outer_walk_forward"]["folds"], result["outer_folds"]):
            _require(fold_config["fold_id"] == fold["fold_id"], "Outer fold order mismatch")
            train = _fold_samples(samples, fold_config, "train")
            test = _fold_samples(samples, fold_config, "test")
            _require((len(train), len(test)) == (fold["train_rows"], fold["test_rows"]), "Outer fold row count mismatch")
            lock = fold["selection_lock"]
            _require(_canonical_hash(lock) == fold["selection_lock_sha256"], "Selection lock hash mismatch")
            _require(lock["code_sha256"] == code_hash and lock["config_sha256"] == summary["config_sha256"], "Selection lineage mismatch")
            _require(lock["preregistration_hash"] == preregistration["preregistration_hash"], "Selection preregistration mismatch")
            _require(lock["train_sample_ids_sha256"] == _canonical_hash([sample.interval.sample_id for sample in train]), "Selection train IDs changed")
            _require(lock["test_sample_ids_sha256"] == _canonical_hash([sample.interval.sample_id for sample in test]), "Selection test IDs changed")
            _require(lock["inner_result_sha256"] == _canonical_hash(fold["inner"]), "Inner result changed after selection")
            _require(lock["selected_candidate_id"] == fold["inner"]["selected_candidate_id"] == fold["selected_candidate_id"], "Selected candidate mismatch")
            _require(not ({"metrics", "probability_metrics", "controls"} & set(lock)), "Outer result leaked into selection lock")
            selection_lock_count += 1

            embargo = int(
                config["inner_cpcv"]["h1_embargo_observations"]
                if experiment["family"] == "H1_VOLATILITY_COMPRESSION_BREAKOUT"
                else config["inner_cpcv"]["daily_embargo_observations"]
            )
            expected_cpcv = build_cpcv(
                [sample.interval for sample in train],
                int(config["inner_cpcv"]["n_chronological_groups"]),
                int(config["inner_cpcv"]["k_test_groups"]),
                "BARS",
                embargo,
            )
            manifest_path = repo_root / "research/artifacts/nested/phase_j/split_manifests" / experiment_id / f"{fold['fold_id']}.json.gz"
            _require(sha256_file(manifest_path) == lock["split_manifest_sha256"], "Split manifest hash mismatch")
            with gzip.open(manifest_path, "rt", encoding="ascii") as handle:
                manifest = json.load(handle)
            _require((manifest["split_count"], manifest["path_count"]) == (15, 5), "CPCV manifest count mismatch")
            for actual, expected in zip(manifest["splits"], expected_cpcv.splits):
                _require(actual["train_ids"] == list(expected.train_ids), "CPCV train manifest mismatch")
                _require(actual["test_ids"] == list(expected.test_ids), "CPCV test manifest mismatch")
                _require(actual["purged_ids"] == list(expected.purged_ids), "CPCV purge manifest mismatch")
                _require(actual["embargoed_ids"] == list(expected.embargoed_ids), "CPCV embargo manifest mismatch")

            inner_path = repo_root / fold["inner_oos_predictions"]
            _require(sha256_file(inner_path) == fold["inner_oos_predictions_sha256"] == lock["selected_inner_oos_predictions_sha256"], "Inner OOS prediction hash mismatch")
            fields, rows = _read_csv_gzip(inner_path)
            _require(fields == PREDICTION_FIELDS, "Inner OOS prediction schema mismatch")
            expected_inner_count = len(train) * 5 if fold["selected_candidate_id"] else 0
            _require(len(rows) == expected_inner_count, "Inner OOS prediction coverage mismatch")
            _require(len({(row["split_id"], row["group_id"], row["sample_id"]) for row in rows}) == len(rows), "Inner OOS prediction key duplicated")
            for row in rows:
                _require(row["candidate_id"] == fold["selected_candidate_id"], "Inner prediction candidate mismatch")
                _require(row["sample_id"] in sample_by_id, "Unknown inner prediction sample")
                _require(datetime.fromisoformat(row["decision_timestamp_source"]) <= datetime(2026, 6, 28), "Inner prediction crossed holdout")
                accepted = row["accepted"] == "true"
                _require(accepted == (row["medium_cost_net_pnl_usd"] != ""), "Inner accepted/net mismatch")
                if row["probability"]:
                    _require(0 <= float(row["probability"]) <= 1, "Inner probability outside [0,1]")
            inner_prediction_rows += len(rows)
            if fold["selected_candidate_id"]:
                expected_outer_ids.update((fold["fold_id"], sample.interval.sample_id) for sample in test)

        outer_prediction_path = repo_root / result["outer_prediction_log"]
        _require(sha256_file(outer_prediction_path) == result["outer_prediction_log_sha256"], "Outer prediction hash mismatch")
        fields, outer_rows = _read_csv_gzip(outer_prediction_path)
        _require(fields == PREDICTION_FIELDS, "Outer prediction schema mismatch")
        _require(len({(row["outer_fold_id"], row["sample_id"]) for row in outer_rows}) == len(outer_rows), "Outer prediction key duplicated")
        _require({(row["outer_fold_id"], row["sample_id"]) for row in outer_rows} == expected_outer_ids, "Outer prediction coverage mismatch")
        probability_values = []
        probability_targets = []
        direction_by_key = {}
        for row in outer_rows:
            _require(datetime.fromisoformat(row["decision_timestamp_source"]) <= datetime(2026, 6, 28), "Outer prediction crossed holdout")
            accepted = row["accepted"] == "true"
            _require(accepted == (row["medium_cost_net_pnl_usd"] != ""), "Outer accepted/net mismatch")
            key = (row["outer_fold_id"], row["sample_id"])
            if accepted:
                accepted_outer_keys.add(key)
                direction_by_key[key] = int(row["direction_success"]) if row["direction_success"] else None
            if row["probability"]:
                probability_values.append(float(row["probability"]))
                probability_targets.append(int(row["target"]))
        outer_prediction_rows += len(outer_rows)
        if experiment["family"] == "MOMENTUM_TRADE_ACCEPTANCE_LOGISTIC":
            _require(len(probability_values) == len(outer_rows), "Trade-filter outer probabilities are incomplete")
            actual = np.asarray(probability_targets, dtype=float)
            predicted = np.asarray(probability_values, dtype=float)
            _assert_close(float(np.mean((predicted - actual) ** 2)), result["outer_probability_metrics"]["brier_score"], "Outer Brier mismatch")
            clipped = np.clip(predicted, 1e-12, 1 - 1e-12)
            log_loss = float(-np.mean(actual * np.log(clipped) + (1 - actual) * np.log(1 - clipped)))
            _assert_close(log_loss, result["outer_probability_metrics"]["log_loss"], "Outer log-loss mismatch")

        trade_path = repo_root / result["outer_trade_log"]
        _require(sha256_file(trade_path) == result["outer_trade_log_sha256"], "Outer trade-log hash mismatch")
        _, trades = _read_csv_gzip(trade_path)
        _require(len({(row["outer_fold_id"], row["sample_id"]) for row in trades}) == len(trades), "Outer trade duplicated")
        previous_exit = None
        balance = Decimal("50000")
        peak = balance
        drawdown = Decimal("0")
        sums = {
            "gross": Decimal("0"),
            "spread": Decimal("0"),
            "slippage": Decimal("0"),
            "commission": Decimal("0"),
            "financing": Decimal("0"),
            "low": Decimal("0"),
            "medium": Decimal("0"),
            "high": Decimal("0"),
        }
        successes = []
        for row in sorted(trades, key=lambda item: (item["decision_timestamp_source"], item["sample_id"])):
            entry = datetime.fromisoformat(row["entry_timestamp_source"])
            exit_time = datetime.fromisoformat(row["exit_timestamp_source"])
            _require(previous_exit is None or entry > previous_exit, "Outer trades overlap")
            previous_exit = exit_time
            key = (row["outer_fold_id"], row["sample_id"])
            _require(key in accepted_outer_keys, "Trade has no accepted outer prediction")
            gross = Decimal(row["gross_pnl_usd"])
            spread = Decimal(row["spread_cost_usd"])
            slippage = Decimal(row["slippage_cost_usd"])
            commission = Decimal(row["commission_usd"])
            financing = Decimal(row["financing_cost_usd"])
            medium = Decimal(row["medium_cost_net_pnl_usd"])
            _require(gross - spread - slippage - commission - financing == medium, "Outer gross/cost/net identity failed")
            for key_name, value in (
                ("gross", gross), ("spread", spread), ("slippage", slippage),
                ("commission", commission), ("financing", financing),
                ("low", Decimal(row["low_cost_net_pnl_usd"])),
                ("medium", medium), ("high", Decimal(row["high_cost_net_pnl_usd"])),
            ):
                sums[key_name] += value
            balance += medium
            peak = max(peak, balance)
            drawdown = max(drawdown, peak - balance)
            if direction_by_key.get(key) is not None:
                successes.append(direction_by_key[key])
        aggregate = result["outer_aggregate"]
        _require(len(trades) == aggregate["trade_count"], "Outer aggregate trade count mismatch")
        _assert_close(float(sums["gross"]), aggregate["gross_pnl_usd"], "Outer aggregate gross mismatch")
        _assert_close(float(sums["medium"]), aggregate["net_by_scenario"]["NORMALIZED_MEDIUM_COST"], "Outer medium net mismatch")
        _assert_close(float(sums["low"]), aggregate["net_by_scenario"]["NORMALIZED_LOW_COST"], "Outer low net mismatch")
        _assert_close(float(sums["high"]), aggregate["net_by_scenario"]["NORMALIZED_HIGH_COST"], "Outer high net mismatch")
        _assert_close(float(drawdown), aggregate["maximum_closed_equity_drawdown_usd"], "Outer drawdown mismatch")
        if successes:
            _assert_close(float(np.mean(successes)), aggregate["direction_success_rate"], "Outer direction-success mismatch")
        validated_trade_rows += len(trades)

        expected_reasons = _expected_reasons(experiment, result, config)
        _require(set(result["rejection_reasons"]) == expected_reasons, f"Frozen rejection decision mismatch for {experiment_id}")
        expected_decision = "SURVIVES_PHASE_J_NOT_CHAMPION" if not expected_reasons else "REJECTED_PHASE_J"
        _require(result["decision"] == expected_decision, f"Decision mismatch for {experiment_id}")
        _require(result["final_holdout_access_count"] == 0, f"Holdout access recorded for {experiment_id}")
        decisions[experiment_id] = result["decision"]

    core = {
        experiment_id: {
            "decision": result["decision"],
            "rejection_reasons": result["rejection_reasons"],
            "outer_aggregate": result["outer_aggregate"],
            "outer_probability_metrics": result["outer_probability_metrics"],
            "selected_candidates": [fold["selected_candidate_id"] for fold in result["outer_folds"]],
            "selection_hashes": [fold["selection_lock_sha256"] for fold in result["outer_folds"]],
        }
        for experiment_id, result in summary["experiments"].items()
    }
    _require(_canonical_hash(core) == summary["core_results_sha256"], "Phase J core result hash mismatch")
    _require((repo_root / "PHASE_J_GOVERNANCE_DEVIATION.md").is_file(), "Phase J deviation disclosure missing")
    result = {
        "schema_version": "1.0.0",
        "artifact_id": "PHASE-J-INDEPENDENT-VALIDATION-QRP-20260712",
        "status": "PASS_WITH_GOVERNANCE_CAVEAT",
        "config_sha256": summary["config_sha256"],
        "execution_code_sha256": code_hash,
        "core_results_sha256": summary["core_results_sha256"],
        "experiment_count": len(summary["experiments"]),
        "candidate_trial_count": summary["candidate_trial_count"],
        "input_rows_across_experiment_views": input_rows,
        "selection_lock_count": selection_lock_count,
        "inner_oos_prediction_rows": inner_prediction_rows,
        "outer_oos_prediction_rows": outer_prediction_rows,
        "validated_outer_trade_rows": validated_trade_rows,
        "decisions": decisions,
        "rejected_experiment_count": sum(value == "REJECTED_PHASE_J" for value in decisions.values()),
        "surviving_experiment_count": sum(value == "SURVIVES_PHASE_J_NOT_CHAMPION" for value in decisions.values()),
        "governance_caveat": "PHASE_J_GOVERNANCE_DEVIATION.md",
        "final_holdout_access_count": 0,
        "paper_trading_started": False,
        "live_execution_started": False,
    }
    output = repo_root / "research/artifacts/nested/phase_j/validation.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="ascii")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Independently validate Phase J nested artifacts")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--config", type=Path, default=Path("research/config/phase_j_cycle1.json")
    )
    args = parser.parse_args()
    root = args.repo_root.resolve()
    config = args.config if args.config.is_absolute() else root / args.config
    print(json.dumps(validate_phase_j(root, config), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

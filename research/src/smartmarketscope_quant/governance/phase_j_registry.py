from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from smartmarketscope_quant.data_audit.io import sha256_file, sha256_paths

from .preregistration import validate_preregistration
from .registry import append_event, validate_registry


def _hash(value: object) -> str:
    content = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(content.encode("ascii")).hexdigest()


def append_phase_j_preregistered(repo_root: Path, config_path: Path) -> dict:
    repo_root = repo_root.resolve()
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="ascii"))
    manifest = json.loads((repo_root / "EXPERIMENT_PREREGISTRATION.yaml").read_text(encoding="ascii"))
    if manifest["phase_j_config_sha256"] != sha256_file(config_path):
        raise ValueError("Combined preregistration does not match Phase J config")
    registry_path = repo_root / "EXPERIMENT_REGISTRY.jsonl"
    projection_path = repo_root / "EXPERIMENT_REGISTRY.csv"
    states = validate_registry(registry_path)["states"]
    manifest_by_id = {item["experiment_id"]: item for item in manifest["experiments"]}
    appended = []
    for experiment in config["experiments"]:
        experiment_id = experiment["experiment_id"]
        if experiment_id in states:
            if states[experiment_id] != ["PREREGISTERED"]:
                raise ValueError(f"Unexpected existing lifecycle for {experiment_id}: {states[experiment_id]}")
            continue
        locked = validate_preregistration(repo_root / manifest_by_id[experiment_id]["relative_path"])
        family = experiment["family"]
        if family == "MOMENTUM_TRADE_ACCEPTANCE_LOGISTIC":
            feature_version = "TECHNICAL_H1_COMPLETED_V1_ASOF_DAILY"
            model_version = "LOGISTIC_TRADE_ACCEPTANCE_PHASE_J_V1"
        elif family == "H1_VOLATILITY_COMPRESSION_BREAKOUT":
            feature_version = "TECHNICAL_H1_COMPLETED_V1"
            model_version = "INTERPRETABLE_THRESHOLD_RULE_PHASE_J_V1"
        elif family == "EFFICIENCY_GATED_DAILY_MOMENTUM":
            feature_version = "COMPLETED_DAILY_PLUS_H1_EFFICIENCY_ASOF_V1"
            model_version = "NOT_APPLICABLE_RULE"
        else:
            feature_version = "COMPLETED_DAILY_OHLC_V1"
            model_version = "NOT_APPLICABLE_RULE"
        event_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload = {
            "schema_version": "1.0.0",
            "event_id": f"{experiment_id}-PREREGISTERED",
            "event_type": "PREREGISTERED",
            "event_time_utc": event_time,
            "experiment_id": experiment_id,
            "parent_experiment": "QRP-C1-BL002" if experiment["proposal_id"] != "H009" else "",
            "git_commit": config["software_lineage"]["git_commit"],
            "dataset_checksum": _hash(config["data"]),
            "code_version": "NOT_IMPLEMENTED_AT_PREREGISTRATION",
            "feature_version": feature_version,
            "model_version": model_version,
            "parameters_hash": _hash(experiment),
            "number_of_trials": 0,
            "training_metrics": "NOT_RUN_PRE_OUTCOME",
            "validation_metrics": "NOT_RUN_PRE_OUTCOME",
            "robustness_metrics": "NOT_RUN_PHASE_J",
            "prop_metrics": "NOT_RUN_PHASE_J",
            "decision": "PREREGISTERED",
            "rejection_reason": "",
            "auditor_comments": "Locked before implementation outcomes; outer reselection, holdout access, automatic promotion, and live deployment are prohibited.",
            "status": "PREREGISTERED",
            "preregistration_hash": locked["preregistration_hash"],
            "config_checksum": sha256_file(config_path),
        }
        event = append_event(registry_path, projection_path, payload)
        event_path = repo_root / "research/artifacts/governance/registry_events" / f"{payload['event_id']}.json"
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_path.write_text(json.dumps(event, indent=2, ensure_ascii=True) + "\n", encoding="ascii")
        appended.append(experiment_id)
        states = validate_registry(registry_path)["states"]
    final = validate_registry(registry_path)
    expected_ids = {item["experiment_id"] for item in config["experiments"]}
    if any(final["states"].get(item) != ["PREREGISTERED"] for item in expected_ids):
        raise ValueError("Phase J preregistration lifecycle validation failed")
    return {
        "status": "PASS",
        "appended": appended,
        "phase_j_experiments": len(expected_ids),
        "registry_event_count": final["event_count"],
        "registry_experiment_count": final["experiment_count"],
        "phase_j_state": "PREREGISTERED",
    }


def append_phase_j_started(repo_root: Path, config_path: Path) -> dict:
    repo_root = repo_root.resolve()
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="ascii"))
    registry_path = repo_root / "EXPERIMENT_REGISTRY.jsonl"
    projection_path = repo_root / "EXPERIMENT_REGISTRY.csv"
    validation = validate_registry(registry_path)
    code_paths = sorted(
        (repo_root / "research/src/smartmarketscope_quant/nested_research").glob("*.py")
    )
    if not code_paths:
        raise ValueError("Phase J nested implementation is missing")
    code_hash = sha256_paths(code_paths, path_root=repo_root)
    existing_events = json.loads("[" + ",".join(registry_path.read_text(encoding="ascii").splitlines()) + "]")
    latest_payload = {}
    for event in existing_events:
        experiment_id = event["payload"].get("experiment_id")
        if experiment_id:
            latest_payload[experiment_id] = event["payload"]
    appended = []
    for experiment in config["experiments"]:
        experiment_id = experiment["experiment_id"]
        state = validation["states"].get(experiment_id)
        if state == ["PREREGISTERED", "STARTED"]:
            continue
        if state != ["PREREGISTERED"]:
            raise ValueError(f"Unexpected pre-start lifecycle for {experiment_id}: {state}")
        previous = latest_payload[experiment_id]
        caveat = (
            " Pre-start inner implementation probe disclosed in PHASE_J_GOVERNANCE_DEVIATION.md; no rule, outer outcome, or holdout was changed or accessed."
            if experiment_id in {"QRP-C1-J001", "QRP-C1-J007"}
            else ""
        )
        payload = {
            **{
                key: previous.get(key, "")
                for key in (
                    "schema_version",
                    "experiment_id",
                    "parent_experiment",
                    "git_commit",
                    "dataset_checksum",
                    "feature_version",
                    "model_version",
                    "parameters_hash",
                    "preregistration_hash",
                    "config_checksum",
                )
            },
            "event_id": f"{experiment_id}-STARTED",
            "event_type": "STARTED",
            "event_time_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "code_version": code_hash,
            "number_of_trials": 0,
            "training_metrics": "RUNNING_INNER_CPCV",
            "validation_metrics": "OUTER_NOT_YET_ACCESSED",
            "robustness_metrics": "NOT_RUN_PHASE_J",
            "prop_metrics": "NOT_RUN_PHASE_J",
            "decision": "STARTED",
            "rejection_reason": "",
            "auditor_comments": "Implementation and synthetic tests passed before empirical runner start; selection is inner-only and outer reselection is prohibited." + caveat,
            "status": "RUNNING",
        }
        event = append_event(registry_path, projection_path, payload)
        event_path = repo_root / "research/artifacts/governance/registry_events" / f"{payload['event_id']}.json"
        event_path.write_text(json.dumps(event, indent=2, ensure_ascii=True) + "\n", encoding="ascii")
        appended.append(experiment_id)
        validation = validate_registry(registry_path)
    expected = {item["experiment_id"] for item in config["experiments"]}
    if any(validation["states"].get(item) != ["PREREGISTERED", "STARTED"] for item in expected):
        raise ValueError("Phase J STARTED lifecycle validation failed")
    return {
        "status": "PASS",
        "appended": appended,
        "phase_j_experiments": len(expected),
        "registry_event_count": validation["event_count"],
        "registry_experiment_count": validation["experiment_count"],
        "phase_j_state": "STARTED",
        "code_sha256": code_hash,
    }


def append_phase_j_completed(repo_root: Path, config_path: Path) -> dict:
    repo_root = repo_root.resolve()
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="ascii"))
    summary = json.loads(
        (repo_root / "research/artifacts/nested/phase_j/summary.json").read_text(encoding="ascii")
    )
    independent = json.loads(
        (repo_root / "research/artifacts/nested/phase_j/validation.json").read_text(encoding="ascii")
    )
    if independent.get("status") != "PASS_WITH_GOVERNANCE_CAVEAT":
        raise ValueError("Phase J independent validation has not passed")
    if summary["config_sha256"] != sha256_file(config_path):
        raise ValueError("Phase J terminal config hash mismatch")
    registry_path = repo_root / "EXPERIMENT_REGISTRY.jsonl"
    projection_path = repo_root / "EXPERIMENT_REGISTRY.csv"
    validation = validate_registry(registry_path)
    existing_events = json.loads("[" + ",".join(registry_path.read_text(encoding="ascii").splitlines()) + "]")
    latest_payload = {}
    for event in existing_events:
        experiment_id = event["payload"].get("experiment_id")
        if experiment_id:
            latest_payload[experiment_id] = event["payload"]
    appended = []
    for experiment in config["experiments"]:
        experiment_id = experiment["experiment_id"]
        state = validation["states"].get(experiment_id)
        if state == ["PREREGISTERED", "STARTED", "COMPLETED"]:
            continue
        if state != ["PREREGISTERED", "STARTED"]:
            raise ValueError(f"Unexpected preterminal lifecycle for {experiment_id}: {state}")
        result = summary["experiments"][experiment_id]
        previous = latest_payload[experiment_id]
        payload = {
            **{
                key: previous.get(key, "")
                for key in (
                    "schema_version",
                    "experiment_id",
                    "parent_experiment",
                    "git_commit",
                    "dataset_checksum",
                    "feature_version",
                    "model_version",
                    "parameters_hash",
                    "preregistration_hash",
                    "config_checksum",
                )
            },
            "event_id": f"{experiment_id}-COMPLETED",
            "event_type": "COMPLETED",
            "event_time_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "code_version": summary["code_sha256"],
            "number_of_trials": int(experiment["trial_budget"]),
            "training_metrics": {
                "inner_cpcv_combinations_per_outer_fold": 15,
                "inner_complete_paths_per_outer_fold": 5,
                "selected_candidates": [
                    fold["selected_candidate_id"] for fold in result["outer_folds"]
                ],
                "parameter_rank_stability": [
                    fold["inner"]["parameter_rank_stability"] for fold in result["outer_folds"]
                ],
            },
            "validation_metrics": {
                "outer_aggregate": result["outer_aggregate"],
                "outer_probability_metrics": result["outer_probability_metrics"],
                "train_to_test_decay": result["train_to_test_decay_distribution"],
                "maximum_absolute_train_to_test_decay": result[
                    "maximum_absolute_train_to_test_decay"
                ],
                "outer_trade_log_sha256": result["outer_trade_log_sha256"],
                "outer_prediction_log_sha256": result["outer_prediction_log_sha256"],
            },
            "robustness_metrics": "NOT_APPLICABLE_NO_PHASE_J_SURVIVOR",
            "prop_metrics": "NOT_APPLICABLE_NO_PHASE_J_SURVIVOR",
            "decision": result["decision"],
            "rejection_reason": result["rejection_reasons"],
            "auditor_comments": "Independent Phase J validation passed with the permanent caveat in PHASE_J_GOVERNANCE_DEVIATION.md. No automatic promotion, Phase K handoff, paper trading, or live execution is authorized.",
            "status": "COMPLETED",
        }
        event = append_event(registry_path, projection_path, payload)
        event_path = repo_root / "research/artifacts/governance/registry_events" / f"{payload['event_id']}.json"
        event_path.write_text(json.dumps(event, indent=2, ensure_ascii=True) + "\n", encoding="ascii")
        appended.append(experiment_id)
        validation = validate_registry(registry_path)
    expected = {item["experiment_id"] for item in config["experiments"]}
    terminal = ["PREREGISTERED", "STARTED", "COMPLETED"]
    if any(validation["states"].get(item) != terminal for item in expected):
        raise ValueError("Phase J terminal lifecycle validation failed")
    return {
        "status": "PASS",
        "appended": appended,
        "phase_j_experiments": len(expected),
        "registry_event_count": validation["event_count"],
        "registry_experiment_count": validation["experiment_count"],
        "phase_j_state": "COMPLETED",
        "rejected_experiments": sum(
            summary["experiments"][item]["decision"] == "REJECTED_PHASE_J"
            for item in expected
        ),
        "final_holdout_access_count": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Append Phase J preregistration registry events")
    parser.add_argument(
        "--action", choices=["preregister", "start", "complete"], default="preregister"
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("research/config/phase_j_cycle1.json"),
    )
    args = parser.parse_args()
    root = args.repo_root.resolve()
    config = args.config if args.config.is_absolute() else root / args.config
    operation = (
        append_phase_j_completed
        if args.action == "complete"
        else append_phase_j_started
        if args.action == "start"
        else append_phase_j_preregistered
    )
    print(json.dumps(operation(root, config), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

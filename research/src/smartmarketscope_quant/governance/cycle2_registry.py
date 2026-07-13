from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from smartmarketscope_quant.data_audit.io import sha256_file, sha256_paths

from .cycle2_creativity import validate_cycle2_creativity
from .preregistration import validate_preregistration
from .registry import append_event, validate_registry


PARENTS = {
    "H011": "QRP-C1-J004",
    "H012": "QRP-C1-J002",
    "H013": "QRP-C1-J005",
    "H014": "QRP-C1-J005",
    "H015": "QRP-C1-J006",
    "H016": "QRP-C1-J007",
}


def _hash(value: object) -> str:
    content = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(content.encode("ascii")).hexdigest()


def _versions(experiment: dict) -> tuple[str, str]:
    family = experiment["family"]
    if family in {"VOL_STATE_DAILY_MOMENTUM", "MULTI_HORIZON_CONSENSUS_MOMENTUM"}:
        return "COMPLETED_DAILY_OHLC_V1", "NOT_APPLICABLE_RULE"
    if family in {"H1_ALIGNED_DAILY_MOMENTUM", "RANGE_EDGE_DAILY_MOMENTUM"}:
        return "COMPLETED_DAILY_PLUS_H1_ASOF_V1", "NOT_APPLICABLE_RULE"
    if family == "MOMENTUM_ADVERSE_RISK_VETO_LOGISTIC":
        return "DAILY_PATH_PLUS_TECHNICAL_H1_ASOF_V1", "LOGISTIC_ADVERSE_RISK_VETO_CYCLE2_V1"
    if family == "H1_BARRIER_ASYMMETRY_TREE":
        return "TECHNICAL_H1_COMPLETED_PLUS_BARRIER_V1", "SHALLOW_TREE_THREE_WAY_BARRIER_CYCLE2_V1"
    raise ValueError(f"Unsupported cycle-two family: {family}")


def append_cycle2_preregistered(repo_root: Path, config_path: Path) -> dict:
    repo_root = repo_root.resolve()
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="ascii"))
    creativity = validate_cycle2_creativity(repo_root, config_path)
    if creativity["status"] != "PASS":
        raise ValueError("Cycle-two creativity gate has not passed")
    manifest = json.loads((repo_root / "EXPERIMENT_PREREGISTRATION.yaml").read_text(encoding="ascii"))
    if manifest["phase_j_config_sha256"] != sha256_file(config_path):
        raise ValueError("Cycle-two combined preregistration does not match config")
    manifest_by_id = {item["experiment_id"]: item for item in manifest["experiments"]}
    registry_path = repo_root / "EXPERIMENT_REGISTRY.jsonl"
    projection_path = repo_root / "EXPERIMENT_REGISTRY.csv"
    validation = validate_registry(registry_path)
    prior_ids = {
        experiment_id
        for experiment_id, states in validation["states"].items()
        if states == ["PREREGISTERED", "STARTED", "COMPLETED"]
    }
    if len(prior_ids) != 13:
        raise ValueError("Cycle two requires exactly 13 terminal predecessor experiments")

    appended = []
    for experiment in config["experiments"]:
        experiment_id = experiment["experiment_id"]
        state = validation["states"].get(experiment_id)
        if state == ["PREREGISTERED"]:
            continue
        if state is not None:
            raise ValueError(f"Unexpected existing lifecycle for {experiment_id}: {state}")
        locked = validate_preregistration(repo_root / manifest_by_id[experiment_id]["relative_path"])
        feature_version, model_version = _versions(experiment)
        payload = {
            "schema_version": "1.0.0",
            "event_id": f"{experiment_id}-PREREGISTERED",
            "event_type": "PREREGISTERED",
            "event_time_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "experiment_id": experiment_id,
            "parent_experiment": PARENTS[experiment["proposal_id"]],
            "git_commit": config["software_lineage"]["git_commit"],
            "dataset_checksum": _hash(config["data"]),
            "code_version": "NOT_IMPLEMENTED_AT_PREREGISTRATION",
            "feature_version": feature_version,
            "model_version": model_version,
            "parameters_hash": _hash(experiment),
            "number_of_trials": 0,
            "training_metrics": "NOT_RUN_PRE_OUTCOME",
            "validation_metrics": "NOT_RUN_PRE_OUTCOME",
            "robustness_metrics": "NOT_RUN_PRE_OUTCOME",
            "prop_metrics": "NOT_RUN_PRE_OUTCOME",
            "decision": "PREREGISTERED",
            "rejection_reason": "",
            "auditor_comments": "Cycle-two protocol locked after comparison with 13 terminal experiments and before implementation outcomes. Historical outer periods are exposed; holdout access, outer reselection, automatic promotion, paper trading, and live execution are prohibited.",
            "status": "PREREGISTERED",
            "preregistration_hash": locked["preregistration_hash"],
            "config_checksum": sha256_file(config_path),
        }
        event = append_event(registry_path, projection_path, payload)
        event_path = (
            repo_root
            / "research/artifacts/governance/registry_events"
            / f"{payload['event_id']}.json"
        )
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_path.write_text(json.dumps(event, indent=2, ensure_ascii=True) + "\n", encoding="ascii")
        appended.append(experiment_id)
        validation = validate_registry(registry_path)

    expected = {item["experiment_id"] for item in config["experiments"]}
    if any(validation["states"].get(item) != ["PREREGISTERED"] for item in expected):
        raise ValueError("Cycle-two preregistration lifecycle validation failed")
    return {
        "status": "PASS",
        "appended": appended,
        "cycle2_experiments": len(expected),
        "candidate_trial_budget": sum(item["trial_budget"] for item in config["experiments"]),
        "registry_event_count": validation["event_count"],
        "registry_experiment_count": validation["experiment_count"],
        "cycle2_state": "PREREGISTERED",
        "final_holdout_access_count": 0,
    }


def append_cycle2_started(repo_root: Path, config_path: Path) -> dict:
    repo_root = repo_root.resolve()
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="ascii"))
    output_summary = repo_root / "research/artifacts/nested/phase_j_cycle2/summary.json"
    if output_summary.exists():
        raise ValueError("Cycle-two outcome artifact exists before STARTED lifecycle closure")
    registry_path = repo_root / "EXPERIMENT_REGISTRY.jsonl"
    projection_path = repo_root / "EXPERIMENT_REGISTRY.csv"
    validation = validate_registry(registry_path)
    code_paths = sorted(
        (
            repo_root
            / "research/src/smartmarketscope_quant/nested_research/cycle2"
        ).glob("*.py")
    )
    if not code_paths:
        raise ValueError("Cycle-two implementation is missing")
    code_hash = sha256_paths(code_paths, path_root=repo_root)
    latest_payload = {}
    for event in json.loads(
        "[" + ",".join(registry_path.read_text(encoding="ascii").splitlines()) + "]"
    ):
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
            raise ValueError(f"Unexpected cycle-two pre-start lifecycle for {experiment_id}: {state}")
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
            "event_id": f"{experiment_id}-STARTED",
            "event_type": "STARTED",
            "event_time_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "code_version": code_hash,
            "number_of_trials": 0,
            "training_metrics": "RUNNING_INNER_CPCV_NO_OUTCOME_ACCESSED_AT_START",
            "validation_metrics": "OUTER_NOT_YET_ACCESSED",
            "robustness_metrics": "NOT_RUN_PHASE_J",
            "prop_metrics": "NOT_RUN_PHASE_J",
            "decision": "STARTED",
            "rejection_reason": "",
            "auditor_comments": "Cycle-two synthetic tests and prior-cycle regression gates passed before empirical start. Selection is inner-only; historical outer periods are exposed and outer reselection is prohibited.",
            "status": "RUNNING",
        }
        event = append_event(registry_path, projection_path, payload)
        event_path = (
            repo_root
            / "research/artifacts/governance/registry_events"
            / f"{payload['event_id']}.json"
        )
        event_path.write_text(
            json.dumps(event, indent=2, ensure_ascii=True) + "\n", encoding="ascii"
        )
        appended.append(experiment_id)
        validation = validate_registry(registry_path)

    expected = {item["experiment_id"] for item in config["experiments"]}
    terminal = ["PREREGISTERED", "STARTED"]
    if any(validation["states"].get(item) != terminal for item in expected):
        raise ValueError("Cycle-two STARTED lifecycle validation failed")
    return {
        "status": "PASS",
        "appended": appended,
        "cycle2_experiments": len(expected),
        "registry_event_count": validation["event_count"],
        "registry_experiment_count": validation["experiment_count"],
        "cycle2_state": "STARTED",
        "code_sha256": code_hash,
        "final_holdout_access_count": 0,
    }


def append_cycle2_completed(repo_root: Path, config_path: Path) -> dict:
    repo_root = repo_root.resolve()
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="ascii"))
    summary = json.loads(
        (
            repo_root / "research/artifacts/nested/phase_j_cycle2/summary.json"
        ).read_text(encoding="ascii")
    )
    independent = json.loads(
        (
            repo_root / "research/artifacts/nested/phase_j_cycle2/validation.json"
        ).read_text(encoding="ascii")
    )
    if independent.get("status") != "PASS_WITH_GOVERNANCE_CAVEAT":
        raise ValueError("Cycle-two independent validation has not passed")
    if summary["config_sha256"] != sha256_file(config_path):
        raise ValueError("Cycle-two terminal config hash mismatch")
    registry_path = repo_root / "EXPERIMENT_REGISTRY.jsonl"
    projection_path = repo_root / "EXPERIMENT_REGISTRY.csv"
    validation = validate_registry(registry_path)
    latest_payload = {}
    for event in json.loads(
        "[" + ",".join(registry_path.read_text(encoding="ascii").splitlines()) + "]"
    ):
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
            raise ValueError(
                f"Unexpected cycle-two preterminal lifecycle for {experiment_id}: {state}"
            )
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
                    fold["inner"]["parameter_rank_stability"]
                    for fold in result["outer_folds"]
                ],
            },
            "validation_metrics": {
                "outer_aggregate": result["outer_aggregate"],
                "outer_probability_metrics": result["outer_probability_metrics"],
                "train_to_test_decay": result[
                    "train_to_test_decay_distribution"
                ],
                "maximum_absolute_train_to_test_decay": result[
                    "maximum_absolute_train_to_test_decay"
                ],
                "outer_trade_log_sha256": result["outer_trade_log_sha256"],
                "outer_prediction_log_sha256": result[
                    "outer_prediction_log_sha256"
                ],
            },
            "robustness_metrics": "NOT_APPLICABLE_NO_PHASE_J_CYCLE2_SURVIVOR",
            "prop_metrics": "NOT_APPLICABLE_NO_PHASE_J_CYCLE2_SURVIVOR",
            "decision": result["decision"],
            "rejection_reason": result["rejection_reasons"],
            "auditor_comments": "Independent cycle-two validation passed with the permanent orchestration caveat in CYCLE_2_GOVERNANCE_DEVIATION.md. No Phase K handoff, LucidFlex run, automatic promotion, paper trading, or live execution is authorized.",
            "status": "COMPLETED",
        }
        event = append_event(registry_path, projection_path, payload)
        event_path = (
            repo_root
            / "research/artifacts/governance/registry_events"
            / f"{payload['event_id']}.json"
        )
        event_path.write_text(
            json.dumps(event, indent=2, ensure_ascii=True) + "\n", encoding="ascii"
        )
        appended.append(experiment_id)
        validation = validate_registry(registry_path)

    expected = {item["experiment_id"] for item in config["experiments"]}
    terminal = ["PREREGISTERED", "STARTED", "COMPLETED"]
    if any(validation["states"].get(item) != terminal for item in expected):
        raise ValueError("Cycle-two terminal lifecycle validation failed")
    return {
        "status": "PASS",
        "appended": appended,
        "cycle2_experiments": len(expected),
        "registry_event_count": validation["event_count"],
        "registry_experiment_count": validation["experiment_count"],
        "cycle2_state": "COMPLETED",
        "rejected_experiments": sum(
            summary["experiments"][item]["decision"] == "REJECTED_PHASE_J"
            for item in expected
        ),
        "final_holdout_access_count": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Append cycle-two experiment lifecycle events")
    parser.add_argument(
        "--action",
        choices=["preregister", "start", "complete"],
        default="preregister",
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=Path("research/config/phase_j_cycle2.json"))
    args = parser.parse_args()
    root = args.repo_root.resolve()
    config = args.config if args.config.is_absolute() else root / args.config
    operation = (
        append_cycle2_completed
        if args.action == "complete"
        else append_cycle2_started
        if args.action == "start"
        else append_cycle2_preregistered
    )
    print(json.dumps(operation(root, config), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

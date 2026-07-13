from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from datetime import datetime
from pathlib import Path

import joblib

from smartmarketscope_quant.data_audit.io import sha256_file, sha256_paths
from smartmarketscope_quant.governance.preregistration import validate_preregistration
from smartmarketscope_quant.governance.registry import read_registry, validate_registry
from smartmarketscope_quant.ml_baseline.runner import PREDICTION_FIELDS, _decision
from smartmarketscope_quant.ml_baseline.trading import threshold_signal


class PhaseIValidationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PhaseIValidationError(message)


def _validate_registry_lifecycle(
    states: list[str] | None,
    terminal_payload: dict | None,
    terminal_artifact: dict,
    model_result: dict,
    summary: dict,
) -> None:
    running = ["PREREGISTERED", "STARTED"]
    completed = [*running, "COMPLETED"]
    _require(states in (running, completed), "Unexpected Phase I registry lifecycle")
    if states == running:
        return

    _require(terminal_payload is not None, "Completed Phase I lifecycle has no terminal payload")
    _require(terminal_payload == terminal_artifact, "Phase I registry payload differs from terminal artifact")
    _require(terminal_payload.get("event_type") == "COMPLETED", "Phase I terminal event type mismatch")
    _require(terminal_payload.get("status") == "COMPLETED", "Phase I terminal status mismatch")
    _require(terminal_payload.get("decision") == model_result["decision"], "Phase I terminal decision mismatch")
    _require(
        terminal_payload.get("rejection_reason") == model_result["rejection_reason"],
        "Phase I terminal rejection reason mismatch",
    )
    _require(terminal_payload.get("number_of_trials") == 1, "Phase I terminal trial count mismatch")
    _require(terminal_payload.get("config_checksum") == summary["config_sha256"], "Phase I terminal config hash mismatch")
    _require(terminal_payload.get("code_version") == summary["code_sha256"], "Phase I terminal code hash mismatch")
    _require(
        terminal_payload.get("preregistration_hash") == model_result["preregistration_hash"],
        "Phase I terminal preregistration hash mismatch",
    )
    validation = terminal_payload.get("validation_metrics", {})
    _require(
        validation.get("probability") == model_result["evaluation_probability_metrics"],
        "Phase I terminal probability metrics mismatch",
    )
    _require(
        terminal_payload.get("robustness_metrics", {}).get("threshold_scenarios")
        == model_result["threshold_scenarios"],
        "Phase I terminal threshold scenarios mismatch",
    )
    _require(terminal_payload.get("prop_metrics") == "NOT_RUN_PHASE_I", "Phase I terminal prop handoff mismatch")


def validate_phase_i(repo_root: Path, config_path: Path) -> dict:
    repo_root = repo_root.resolve()
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="ascii"))
    summary_path = repo_root / config["outputs"]["summary"]
    summary = json.loads(summary_path.read_text(encoding="ascii"))
    _require(summary["status"] == "COMPLETED_NO_AUTOMATIC_PROMOTION", "Phase I status mismatch")
    _require(summary["trial_count"] == 3, "Phase I trial budget mismatch")
    _require(summary["final_holdout_access_count"] == 0, "Phase I accessed a final holdout")
    _require(summary["config_sha256"] == sha256_file(config_path), "Phase I config hash mismatch")
    module_paths = sorted((repo_root / "research/src/smartmarketscope_quant/ml_baseline").glob("*.py"))
    _require(summary["code_sha256"] == sha256_paths(module_paths, path_root=repo_root), "Phase I code hash mismatch")

    core = {
        "lineage": summary["lineage"],
        "partition_counts": summary["partition_counts"],
        "models": {
            experiment_id: {
                key: value for key, value in model.items() if key not in {"model_artifact_sha256"}
            }
            for experiment_id, model in summary["models"].items()
        },
    }
    core_hash = hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    ).hexdigest()
    _require(core_hash == summary["core_results_sha256"], "Phase I core result hash mismatch")
    registry_path = repo_root / config["registry"]
    registry = validate_registry(registry_path)
    registry_events = read_registry(registry_path)
    latest_payload = {
        event["payload"]["experiment_id"]: event["payload"] for event in registry_events
    }

    validated_predictions = 0
    decision_counts = {}
    for definition in config["models"]:
        experiment_id = definition["experiment_id"]
        model_result = summary["models"][experiment_id]
        preregistration = validate_preregistration(repo_root / definition["preregistration_path"])
        _require(
            preregistration["preregistration_hash"] == model_result["preregistration_hash"],
            f"{experiment_id} preregistration hash mismatch",
        )
        _require(len(model_result["selected_features"]) == config["feature_selection"]["k"], "Selected feature count changed")
        expected_decision = _decision(
            model_result["evaluation_probability_metrics"],
            model_result["threshold_scenarios"],
            config["decision_rules"],
            config["thresholds"]["primary"],
        )
        _require(expected_decision == (model_result["decision"], model_result["rejection_reason"]), "Decision rule mismatch")
        decision_counts[model_result["decision"]] = decision_counts.get(model_result["decision"], 0) + 1

        model_path = repo_root / model_result["model_artifact"]
        prediction_path = repo_root / model_result["prediction_log"]
        manifest_path = repo_root / "TRAINING_MANIFESTS" / f"{experiment_id}.json"
        card_path = repo_root / "MODEL_CARDS" / f"{experiment_id}.md"
        _require(manifest_path.is_file() and card_path.is_file(), "Model manifest or card is missing")
        manifest = json.loads(manifest_path.read_text(encoding="ascii"))
        _require(
            sha256_file(model_path) == manifest["model"]["model_artifact_sha256"],
            "Model artifact hash mismatch",
        )
        _require(sha256_file(prediction_path) == model_result["prediction_log_sha256"], "Prediction log hash mismatch")
        artifact = joblib.load(model_path)
        _require(artifact["selected_features"] == model_result["selected_features"], "Serialized feature selection mismatch")
        _require(artifact["random_seed"] == config["random_seed"], "Serialized seed mismatch")
        _require(manifest["trial_count"] == 1 and manifest["final_holdout_access_count"] == 0, "Training manifest budget mismatch")
        _require(manifest["partition_counts"] == summary["partition_counts"], "Training partition manifest mismatch")

        selected_trade_end = None
        prediction_count = 0
        partition_counts = {"calibration": 0, "evaluation": 0}
        with gzip.open(prediction_path, "rt", encoding="ascii", newline="") as handle:
            reader = csv.DictReader(handle)
            _require(reader.fieldnames == PREDICTION_FIELDS, "Prediction schema mismatch")
            for row in reader:
                _require(row["partition"] in partition_counts, "In-sample or unknown prediction partition logged")
                partition_counts[row["partition"]] += 1
                probability = float(row["calibrated_probability"])
                _require(0.0 <= probability <= 1.0, "Prediction probability outside [0,1]")
                _require(
                    int(row["primary_signal"])
                    == threshold_signal(probability, float(config["thresholds"]["primary"])),
                    "Prediction signal contradicts frozen threshold",
                )
                if row["selected_nonoverlapping_primary_trade"] == "true":
                    _require(row["partition"] == "evaluation", "Calibration prediction marked as an economic trade")
                    decision = datetime.fromisoformat(row["decision_timestamp_source"])
                    label_end = datetime.fromisoformat(row["label_end_source"])
                    _require(selected_trade_end is None or decision >= selected_trade_end, "Selected prediction trades overlap")
                    _require(row["primary_medium_net_pnl_usd"] != "", "Selected trade has no net result")
                    selected_trade_end = label_end
                else:
                    _require(row["primary_medium_net_pnl_usd"] == "", "Unselected row contains economic PnL")
                prediction_count += 1
        _require(partition_counts == {
            "calibration": summary["partition_counts"]["calibration"],
            "evaluation": summary["partition_counts"]["evaluation"],
        }, "Prediction partition counts mismatch")
        validated_predictions += prediction_count

        event_path = repo_root / config["outputs"]["registry_event_directory"] / f"{experiment_id}.json"
        event = json.loads(event_path.read_text(encoding="ascii"))
        _validate_registry_lifecycle(
            registry["states"].get(experiment_id),
            latest_payload.get(experiment_id),
            event,
            model_result,
            summary,
        )
        _require(event["decision"] == model_result["decision"], "Terminal event decision mismatch")
        _require(event["number_of_trials"] == 1 and event["status"] == "COMPLETED", "Terminal event budget/status mismatch")

    _require((repo_root / "MODEL_BASELINE_RESULTS.md").is_file(), "Model baseline report missing")
    _require((repo_root / "CALIBRATION_REPORT.md").is_file(), "Calibration report missing")
    result = {
        "schema_version": "1.0.0",
        "artifact_id": "PHASE-I-VALIDATION-QRP-20260712",
        "status": "PASS",
        "core_results_sha256": core_hash,
        "model_count": len(summary["models"]),
        "trial_count": summary["trial_count"],
        "validated_prediction_rows": validated_predictions,
        "partition_counts": summary["partition_counts"],
        "decision_counts": decision_counts,
        "registry_lifecycle_state": "PASS",
        "prediction_timing_and_nonoverlap": "PASS",
        "artifact_hashes": "PASS",
        "final_holdout_access_count": 0,
    }
    output = repo_root / "research/artifacts/models/phase_i/validation.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="ascii")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Independently validate Phase I model baseline artifacts")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    print(json.dumps(validate_phase_i(root, config_path), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

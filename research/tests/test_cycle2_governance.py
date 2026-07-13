from __future__ import annotations

import csv
import hashlib
import json
import unittest
from pathlib import Path

from smartmarketscope_quant.governance.cycle2_creativity import (
    validate_cycle2_creativity,
)
from smartmarketscope_quant.governance.preregistration import validate_preregistration
from smartmarketscope_quant.governance.registry import validate_registry


ROOT = Path(__file__).parents[2]
CONFIG = ROOT / "research/config/phase_j_cycle2.json"


class Cycle2GovernanceTest(unittest.TestCase):
    def test_frozen_cycle_two_portfolio_passes_prospective_gate(self) -> None:
        result = validate_cycle2_creativity(ROOT, CONFIG)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual((result["prior_terminal_experiment_count"], result["proposal_count"]), (13, 9))
        self.assertEqual((result["selected_count"], result["candidate_trial_count"]), (6, 22))
        self.assertEqual((result["exploitation_count"], result["exploration_count"]), (4, 2))
        self.assertEqual((result["cpcv_combinations"], result["cpcv_complete_paths"]), (15, 5))
        self.assertEqual(result["final_holdout_access_count"], 0)

    def test_selected_cycle_two_rows_match_config_and_are_unique(self) -> None:
        config = json.loads(CONFIG.read_text(encoding="ascii"))
        coverage = ROOT / next(
            path
            for path in config["creativity_artifacts"]
            if Path(path).name == "RESEARCH_COVERAGE_MATRIX.csv"
        )
        with coverage.open(encoding="ascii", newline="") as handle:
            rows = list(csv.DictReader(handle))
        selected = {
            row["record_id"]
            for row in rows
            if row["cycle"] == "2" and row["record_type"] == "PROPOSAL" and row["selected"] == "true"
        }
        self.assertEqual(selected, {item["proposal_id"] for item in config["experiments"]})
        self.assertEqual(len({row["record_id"] for row in rows}), len(rows))

    def test_barrier_asymmetry_retains_timeout_without_future_filtering(self) -> None:
        config = json.loads(CONFIG.read_text(encoding="ascii"))
        barrier = next(item for item in config["experiments"] if item["proposal_id"] == "H016")
        self.assertIn("TIMEOUT", barrier["label"])
        self.assertEqual(barrier["timeout_action"], "ABSTAIN")
        self.assertEqual(barrier["ambiguous_same_m5_policy"], "EXCLUDE_AND_REPORT")

    def test_all_cycle_two_preregistrations_are_locked_and_linked(self) -> None:
        manifest = json.loads((ROOT / "EXPERIMENT_PREREGISTRATION.yaml").read_text(encoding="ascii"))
        self.assertEqual(manifest["artifact_id"], "EXPERIMENT-PREREGISTRATION-CYCLE-2-PHASE-J")
        self.assertEqual((manifest["experiment_count"], manifest["candidate_trial_count"]), (6, 22))
        self.assertEqual(manifest["final_holdout_access"], "PROHIBITED")
        for item in manifest["experiments"]:
            document = validate_preregistration(ROOT / item["relative_path"])
            self.assertEqual(document["cycle_id"], "CYCLE-02-PHASE-J")
            self.assertEqual(document["preregistration_hash"], item["preregistration_hash"])
            self.assertEqual(document["holdout_policy"]["final_holdout_access"], "PROHIBITED")
            self.assertEqual(
                document["dataset"]["historical_outer_reuse"],
                "EXPOSED_RESEARCH_COMPARISON_NOT_PRISTINE",
            )

    def test_cycle_one_combined_manifest_is_preserved_byte_for_byte(self) -> None:
        path = ROOT / "research/preregistrations/manifests/cycle1_phase_j.json"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(
            digest,
            "4b7deff757c86f8372518987689810833709cdc4eaad1984ea095bff970ae972",
        )

    def test_cycle_two_registry_is_terminal_after_independent_validation(self) -> None:
        config = json.loads(CONFIG.read_text(encoding="ascii"))
        registry_path = ROOT / "EXPERIMENT_REGISTRY.jsonl"
        all_events = [
            json.loads(line)
            for line in registry_path.read_text(encoding="ascii").splitlines()
            if line.strip()
        ]
        frozen_prefix = all_events[:57]
        self.assertEqual(len(frozen_prefix), 57)

        expected_previous_hash = None
        prefix_states: dict[str, list[str]] = {}
        for event in frozen_prefix:
            payload = event["payload"]
            self.assertEqual(event["previous_event_hash"], expected_previous_hash)
            expected_event_hash = hashlib.sha256(
                json.dumps(
                    {
                        "previous_event_hash": expected_previous_hash,
                        "payload": payload,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                ).encode("ascii")
            ).hexdigest()
            self.assertEqual(event["event_hash"], expected_event_hash)
            expected_previous_hash = expected_event_hash
            prefix_states.setdefault(payload["experiment_id"], []).append(payload["event_type"])

        self.assertEqual(len(prefix_states), 19)
        self.assertEqual(
            expected_previous_hash,
            "c1d19f46dffbbcf62fb1197f3b42aa646f260171660f490ae680cb02d7365c4f",
        )

        registry = validate_registry(registry_path)
        for experiment in config["experiments"]:
            self.assertEqual(
                prefix_states[experiment["experiment_id"]],
                ["PREREGISTERED", "STARTED", "COMPLETED"],
            )
            self.assertEqual(
                registry["states"][experiment["experiment_id"]],
                ["PREREGISTERED", "STARTED", "COMPLETED"],
            )


if __name__ == "__main__":
    unittest.main()

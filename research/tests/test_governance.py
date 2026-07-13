from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from smartmarketscope_quant.governance.preregistration import (
    PreregistrationError,
    lock_preregistration,
    validate_preregistration,
)
from smartmarketscope_quant.governance.registry import (
    CHRONOLOGY_FAILURE_CODES,
    RegistryError,
    _event_hash,
    append_event,
    read_registry,
    validate_registry,
    write_projection,
)


class GovernanceTest(unittest.TestCase):
    def registry_payload(self, event_id: str, event_type: str, event_time_utc: str) -> dict:
        return {
            "schema_version": "1.0.0",
            "event_id": event_id,
            "event_type": event_type,
            "event_time_utc": event_time_utc,
            "experiment_id": "TEST-001",
            "git_commit": "abc",
            "status": event_type,
        }

    def append_raw_event(self, registry: Path, payload: dict) -> dict:
        existing = read_registry(registry)
        previous = existing[-1]["event_hash"] if existing else None
        event = {
            "previous_event_hash": previous,
            "payload": payload,
            "event_hash": _event_hash(previous, payload),
        }
        with registry.open("a", encoding="ascii", newline="") as handle:
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        return event

    def invalid_chronology_registry(self, root: Path) -> tuple[Path, Path]:
        registry = root / "registry.jsonl"
        projection = root / "registry.csv"
        append_event(
            registry,
            projection,
            self.registry_payload("E1", "PREREGISTERED", "2026-01-01T01:00:00Z"),
        )
        append_event(
            registry,
            projection,
            self.registry_payload("E2", "STARTED", "2026-01-01T02:00:00Z"),
        )
        self.append_raw_event(
            registry,
            self.registry_payload("E3", "COMPLETED", "2026-01-01T00:30:00Z"),
        )
        write_projection(registry, projection)
        return registry, projection

    def reconciliation_payload(self, registry: Path, *, event_id: str = "R1") -> dict:
        validation = validate_registry(registry)
        raw = registry.read_bytes()
        affected = []
        for issue in validation["chronology_issues"]:
            affected.append(
                {
                    **issue,
                    "chronology_resolution": "UNRESOLVED_EXACT_COMPLETION_TIME",
                    "corrected_completion_time_utc": None,
                    "likely_metadata_cause": {
                        "status": "EVIDENCE_SUPPORTED_LIKELY_CAUSE",
                        "description": "A static artifact timestamp was reused as lifecycle metadata.",
                        "evidence_sources": ["fixture:config", "fixture:runner"],
                    },
                    "result_content_effect": {
                        "affected": False,
                        "evidence": ["fixture:metrics-match"],
                    },
                    "corrected_interpreted_chronology": {
                        "status": "PARTIAL_ORDER_DEFENSIBLE_EXACT_TIME_UNRESOLVED",
                        "sequence": "PREREGISTERED <= STARTED < RESULT_ARTIFACT_PERSISTED",
                        "evidence_sources": ["fixture:file-metadata"],
                    },
                }
            )
        return {
            "schema_version": "1.0.0",
            "event_id": event_id,
            "event_type": "CHRONOLOGY_RECONCILIATION",
            "event_time_utc": "2026-01-01T04:00:00Z" if event_id == "R1" else "2026-01-01T05:00:00Z",
            "status": "UNRESOLVED",
            "decision": "REGISTRY_CHRONOLOGY_UNRESOLVED",
            "failure_codes": CHRONOLOGY_FAILURE_CODES,
            "source_registry_prefix": {
                "event_count": validation["event_count"],
                "byte_length": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "last_event_hash": validation["last_event_hash"],
            },
            "affected_experiments": affected,
        }

    def preregistration(self) -> dict:
        return {
            "schema_version": "1.0.0",
            "experiment_id": "TEST-001",
            "cycle_id": "C1",
            "status": "DRAFT",
            "hypothesis": "fixture",
            "disconfirming_evidence": ["net <= 0"],
            "dataset": {"checksum": "abc"},
            "feature_rules": [],
            "strategy_rules": {},
            "execution_scenarios": ["TEST"],
            "sizing": {},
            "chronological_evaluation": {},
            "metrics": ["net"],
            "rejection_criteria": ["net <= 0"],
            "trial_budget": 1,
            "holdout_policy": {"final_holdout_access": "PROHIBITED"},
        }

    def test_preregistration_locks_and_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "prereg.json"
            path.write_text(json.dumps(self.preregistration()), encoding="ascii")
            locked = lock_preregistration(path)
            self.assertEqual(validate_preregistration(path)["preregistration_hash"], locked["preregistration_hash"])
            document = json.loads(path.read_text(encoding="ascii"))
            document["hypothesis"] = "tampered"
            path.write_text(json.dumps(document), encoding="ascii")
            with self.assertRaises(PreregistrationError):
                validate_preregistration(path)

    def test_preregistration_allows_bounded_search_but_rejects_budget_overrun(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "prereg.json"
            bounded = self.preregistration()
            bounded["trial_budget"] = 28
            path.write_text(json.dumps(bounded), encoding="ascii")
            self.assertEqual(lock_preregistration(path)["trial_budget"], 28)

            excessive = self.preregistration()
            excessive["trial_budget"] = 201
            path.write_text(json.dumps(excessive), encoding="ascii")
            with self.assertRaises(PreregistrationError):
                lock_preregistration(path)

    def test_registry_hash_chain_lifecycle_and_tamper_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = root / "registry.jsonl"
            projection = root / "registry.csv"
            append_event(
                registry,
                projection,
                self.registry_payload("E1", "PREREGISTERED", "2026-01-01T01:00:00Z"),
            )
            append_event(
                registry,
                projection,
                self.registry_payload("E2", "STARTED", "2026-01-01T02:00:00Z"),
            )
            append_event(
                registry,
                projection,
                self.registry_payload("E3", "FAILED", "2026-01-01T03:00:00Z"),
            )
            result = validate_registry(registry)
            self.assertEqual(result["event_count"], 3)
            self.assertEqual((result["status"], result["chronology_status"]), ("PASS", "PASS"))
            self.assertIn("TEST-001", projection.read_text(encoding="ascii"))
            lines = registry.read_text(encoding="ascii").splitlines()
            record = json.loads(lines[1])
            record["payload"]["status"] = "TAMPERED"
            lines[1] = json.dumps(record)
            registry.write_text("\n".join(lines) + "\n", encoding="ascii")
            with self.assertRaises(RegistryError):
                validate_registry(registry)

    def test_registry_valid_chronology_passes_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = root / "registry.jsonl"
            projection = root / "registry.csv"
            for event_id, event_type, event_time in (
                ("E1", "PREREGISTERED", "2026-01-01T01:00:00Z"),
                ("E2", "STARTED", "2026-01-01T02:00:00Z"),
                ("E3", "COMPLETED", "2026-01-01T03:00:00Z"),
            ):
                append_event(registry, projection, self.registry_payload(event_id, event_type, event_time))
            result = validate_registry(registry)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["chronology_issues"], [])
            self.assertEqual(result["failure_codes"], [])

    def test_registry_invalid_chronological_order_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry, _ = self.invalid_chronology_registry(Path(temporary))
            result = validate_registry(registry)
            self.assertEqual((result["status"], result["decision"]), ("FAIL", "EVENT_ORDER_INVALID"))
            self.assertEqual(result["unreconciled_experiments"], ["TEST-001"])
            self.assertEqual(len(result["chronology_issues"][0]["violations"]), 2)

    def test_registry_reconciliation_is_append_only_and_disclosed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry, projection = self.invalid_chronology_registry(Path(temporary))
            event = append_event(registry, projection, self.reconciliation_payload(registry))
            result = validate_registry(registry)
            self.assertEqual(event["payload"]["event_type"], "CHRONOLOGY_RECONCILIATION")
            self.assertEqual((result["status"], result["decision"]), ("INCONCLUSIVE", "REGISTRY_CHRONOLOGY_UNRESOLVED"))
            self.assertEqual(result["states"]["TEST-001"], ["PREREGISTERED", "STARTED", "COMPLETED"])
            self.assertEqual((result["event_count"], result["lifecycle_event_count"]), (4, 3))
            self.assertEqual(result["reconciled_experiments"], ["TEST-001"])
            self.assertEqual(len(read_registry(registry)), 3)
            self.assertEqual(len(read_registry(registry, include_supplemental=True)), 4)

    def test_registry_original_hash_chain_is_preserved_by_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry, projection = self.invalid_chronology_registry(Path(temporary))
            original_events = read_registry(registry)
            original_hashes = [event["event_hash"] for event in original_events]
            original_head = original_hashes[-1]
            appended = append_event(registry, projection, self.reconciliation_payload(registry))
            final_events = read_registry(registry)
            self.assertEqual([event["event_hash"] for event in final_events[:3]], original_hashes)
            self.assertEqual(appended["previous_event_hash"], original_head)
            self.assertEqual(validate_registry(registry)["hash_chain_status"], "PASS")

    def test_registry_reconciliation_does_not_rewrite_historical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry, projection = self.invalid_chronology_registry(Path(temporary))
            original = registry.read_bytes()
            original_sha = hashlib.sha256(original).hexdigest()
            payload = self.reconciliation_payload(registry)
            self.assertEqual(payload["source_registry_prefix"]["sha256"], original_sha)
            append_event(registry, projection, payload)
            final = registry.read_bytes()
            self.assertTrue(final.startswith(original))
            self.assertEqual(hashlib.sha256(final[: len(original)]).hexdigest(), original_sha)

    def test_registry_reconciliation_preserves_projection_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry, projection = self.invalid_chronology_registry(root)
            original_projection = projection.read_bytes()
            append_event(registry, projection, self.reconciliation_payload(registry))
            self.assertEqual(projection.read_bytes(), original_projection)
            regenerated = root / "regenerated.csv"
            write_projection(registry, regenerated)
            self.assertEqual(regenerated.read_bytes(), original_projection)

    def test_registry_malformed_reconciliation_is_rejected_without_append(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry, projection = self.invalid_chronology_registry(Path(temporary))
            original = registry.read_bytes()
            payload = self.reconciliation_payload(registry)
            payload["affected_experiments"] = []
            with self.assertRaises(RegistryError):
                append_event(registry, projection, payload)
            self.assertEqual(registry.read_bytes(), original)

    def test_registry_duplicate_reconciliation_is_rejected_without_append(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry, projection = self.invalid_chronology_registry(Path(temporary))
            first_payload = self.reconciliation_payload(registry)
            append_event(registry, projection, first_payload)
            original = registry.read_bytes()
            duplicate = copy.deepcopy(first_payload)
            duplicate["event_id"] = "R2"
            duplicate["event_time_utc"] = "2026-01-01T05:00:00Z"
            validation = validate_registry(registry)
            duplicate["source_registry_prefix"] = {
                "event_count": validation["event_count"],
                "byte_length": len(original),
                "sha256": hashlib.sha256(original).hexdigest(),
                "last_event_hash": validation["last_event_hash"],
            }
            with self.assertRaises(RegistryError):
                append_event(registry, projection, duplicate)
            self.assertEqual(registry.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from smartmarketscope_quant.macro_regime.database_architecture import (
    APPEND_ONLY_TABLES,
    CATEGORIES,
    CONFIG_RELATIVE_PATH,
    DatabaseArchitectureError,
    TABLES,
    _load_config,
    _open_schema,
    _schema_inventory,
    _validate_config_contract,
    _validate_declared_file_hashes,
    validate_architecture,
)


ROOT = Path(__file__).resolve().parents[2]


class MacroRegimeDatabaseArchitectureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = validate_architecture(ROOT)
        cls.config = _load_config(ROOT)

    def test_decision_and_zero_work_scope(self) -> None:
        self.assertEqual(self.result["status"], "PASS")
        self.assertEqual(
            self.result["decision"],
            "BUILD_SEPARATE_VERSIONED_MACRO_SCHEMA_REUSE_LINEAGE_PATTERNS",
        )
        self.assertEqual(self.result["experiment_trials_created"], 0)
        self.assertEqual(self.result["final_holdout_access_count"], 0)
        self.assertEqual(self.result["protected_forward_access_count"], 0)
        self.assertEqual(self.result["network_requests"], 0)
        self.assertEqual(
            self.result["validated_input_hashes"],
            {"repository_files": 11, "laravel_files": 7},
        )

    def test_exact_role2_contract_loads_without_mutating_source(self) -> None:
        self.assertEqual(self.result["role2"]["observation_version_count"], 1730)
        self.assertEqual(
            self.result["role2"]["revision_counts"],
            {"FIRST_PRINT": 456, "REVISION": 1274},
        )
        self.assertEqual(
            self.result["role2"]["category_counts"],
            {
                "INFLATION": 489,
                "LABOUR": 921,
                "GROWTH": 214,
                "MONETARY_POLICY": 106,
                "LIQUIDITY": 0,
            },
        )
        self.assertEqual(
            self.result["role2_disposable_schema_load"],
            {"source_runs": 25, "raw_artifacts": 25, "observations": 1730},
        )
        self.assertEqual(
            self.result["role2_provider_bundle"],
            {
                "source_runs": 25,
                "raw_artifact_paths": 25,
                "distinct_raw_payload_sha256": 23,
                "observations": 1730,
                "eligible_observation_source_runs": 5,
            },
        )

    def test_exact_role3_route_census_and_collection_boundary(self) -> None:
        self.assertEqual(
            self.result["role3_decision_counts"],
            {
                "APPROVED_EXISTING_EVIDENCE_ONLY": 5,
                "APPROVED_FOR_BOUNDED_COLLECTION": 19,
                "AVAILABILITY_OR_VERSION_UNRESOLVED": 2,
                "CURRENT_REVISED_HISTORY_ONLY": 1,
                "REJECTED": 3,
                "REQUIRES_KEY_OR_LICENSE_REVIEW": 4,
            },
        )
        self.assertEqual(
            self.config["frozen_contracts"]["role_3"]["collection_allowlist_decision"],
            "APPROVED_FOR_BOUNDED_COLLECTION",
        )
        self.assertIn(
            "CURRENT_REVISED_HISTORY_ONLY",
            self.config["frozen_contracts"]["role_3"]["reconciliation_only_decisions"],
        )

    def test_schema_has_exact_tables_and_append_only_triggers(self) -> None:
        connection = _open_schema(ROOT)
        tables, triggers = _schema_inventory(connection)
        connection.close()
        self.assertEqual(set(tables), set(TABLES))
        for table in APPEND_ONLY_TABLES:
            self.assertIn(f"{table}_no_update", triggers)
            self.assertIn(f"{table}_no_delete", triggers)
        self.assertIn("macro_observations_validate_supersession", triggers)
        self.assertIn("macro_observations_validate_source_lineage", triggers)
        self.assertIn("macro_regime_snapshots_validate_category_lineage", triggers)
        self.assertIn("macro_event_update_validate_lineage", triggers)
        self.assertIn("macro_technical_links_validate_snapshot_time", triggers)

    def test_negative_boundary_and_rollback_proof(self) -> None:
        proof = self.result["schema_proof"]
        self.assertEqual(proof["table_count"], 11)
        self.assertEqual(proof["append_only_table_count"], 11)
        self.assertEqual(proof["trigger_count"], 28)
        self.assertEqual(proof["negative_test_count"], 16)
        self.assertEqual(proof["empty_schema_rollback"], "PASS")
        labels = {entry.split(":", 2)[1] for entry in proof["negative_tests"]}
        self.assertEqual(
            labels,
            {
                "duplicate_idempotency",
                "invalid_category",
                "broken_foreign_key",
                "broken_supersession",
                "supersession_route_mismatch",
                "supersession_category_mismatch",
                "supersession_bundle_mismatch",
                "snapshot_cross_wired_category",
                "snapshot_score_mismatch",
                "event_mismatched_state_lineage",
                "technical_snapshot_score_bias_mismatch",
                "invalid_source_run_timing",
                "invalid_hash",
                "effective_before_availability",
                "append_only_update",
                "append_only_delete",
            },
        )

    def test_five_categories_are_closed_not_extensible_by_accident(self) -> None:
        self.assertEqual(
            CATEGORIES,
            ("INFLATION", "LABOUR", "GROWTH", "MONETARY_POLICY", "LIQUIDITY"),
        )
        connection = _open_schema(ROOT)
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO macro_category_states (
                    category_state_id, category, active_release_bundle_state_ids_json,
                    bundle_lineage_sha256, continuous_category_score, discrete_category_score,
                    category_status, stress_flags_json, stress_flags_sha256, effective_at_utc,
                    scoring_version, scoring_config_sha256, code_sha256, registry_sha256, created_at_utc
                ) VALUES (
                    'bad-category', 'CREDIT', '[]', ?, 0, 0, 'VALID', '[]', ?,
                    '2020-01-01T00:00:00Z', 'v1', ?, ?, ?, '2020-01-01T00:00:00Z'
                )
                """,
                ("a" * 64, "a" * 64, "a" * 64, "a" * 64, "a" * 64),
            )
        connection.close()

    def test_config_contract_fails_closed_on_scope_or_category_change(self) -> None:
        bad_category = copy.deepcopy(self.config)
        bad_category["frozen_contracts"]["categories"] = [*CATEGORIES, "CREDIT"]
        with self.assertRaisesRegex(DatabaseArchitectureError, "Five-category contract changed"):
            _validate_config_contract(bad_category)

        bad_scope = copy.deepcopy(self.config)
        bad_scope["scope"]["experiment_trials_created"] = 1
        with self.assertRaisesRegex(DatabaseArchitectureError, "zero-work invariant"):
            _validate_config_contract(bad_scope)

    def test_declared_sibling_hash_fails_closed_on_isolated_tamper(self) -> None:
        with tempfile.TemporaryDirectory(prefix="role4-laravel-hash-") as directory:
            root = Path(directory)
            fixture = root / "safe-source.php"
            original = b"<?php return 'reviewed';\n"
            fixture.write_bytes(original)
            declarations = {
                "safe_source": {
                    "path": "safe-source.php",
                    "sha256": hashlib.sha256(original).hexdigest(),
                }
            }
            expected_paths = {"safe_source": "safe-source.php"}
            self.assertEqual(
                _validate_declared_file_hashes(
                    root,
                    declarations,
                    label="Isolated Laravel inventory",
                    exact_relative_paths=expected_paths,
                ),
                1,
            )
            fixture.write_bytes(b"<?php return 'tampered';\n")
            with self.assertRaisesRegex(DatabaseArchitectureError, "hash mismatch"):
                _validate_declared_file_hashes(
                    root,
                    declarations,
                    label="Isolated Laravel inventory",
                    exact_relative_paths=expected_paths,
                )

    def test_validation_is_deterministic_and_config_is_ascii_json(self) -> None:
        repeated = validate_architecture(ROOT)
        self.assertEqual(self.result, repeated)
        raw = (ROOT / CONFIG_RELATIVE_PATH).read_bytes()
        raw.decode("ascii")
        self.assertEqual(json.loads(raw), self.config)


if __name__ == "__main__":
    unittest.main()

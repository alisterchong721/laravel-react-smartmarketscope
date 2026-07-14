from __future__ import annotations

import csv
import io
import json
import unittest
from pathlib import Path

from smartmarketscope_quant.macro_regime.h6_full_finalize import (
    ELIGIBLE_CLASSIFICATION,
    ELIGIBLE_PROTOCOL_STATUS,
    NORMALIZATION_CONFIG_PATH,
    build,
    build_chains,
)
from smartmarketscope_quant.macro_regime.historical_collector import (
    CollectionValidationError,
    ParsedValue,
)


ROOT = Path(__file__).resolve().parents[2]


def release(identity: str, canonical_date: str, values: list[tuple[str, str]]) -> dict[str, object]:
    return {
        "source_index_identity": identity,
        "canonical_release_date": canonical_date,
        "source_identity_classification": "DIRECT_OFFICIAL_DATED_RELEASE_IDENTITY",
        "acquisition_classification": "TEST_FIXTURE",
        "source_run_id": f"fixture-{identity}",
        "raw_artifact_id": f"fixture-{identity}-body",
        "raw_artifact_sha256": "a" * 64,
        "relative_private_path": f"fixture/{identity}.html",
        "parser_format": "LEGACY_PRE",
        "values": [ParsedValue(reference, value, reference) for reference, value in values],
    }


class MacroRegimeH6FullFinalizeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs = build(ROOT)
        cls.manifest = json.loads(cls.outputs["ROLE5_H6_FULL_NORMALIZED_MANIFEST.json"])
        cls.config = json.loads((ROOT / NORMALIZATION_CONFIG_PATH).read_text(encoding="ascii"))
        cls.observations = list(csv.DictReader(io.StringIO(cls.outputs["ROLE5_H6_OBSERVATION_VERSIONS.csv"].decode("utf-8"))))
        cls.snapshots = list(csv.DictReader(io.StringIO(cls.outputs["ROLE5_H6_RELEASE_SNAPSHOTS.csv"].decode("utf-8"))))

    def test_complete_release_and_request_accounting(self) -> None:
        self.assertEqual(self.manifest["status"], "PASS")
        self.assertEqual(self.manifest["accepted_release_identity_count"], 1167)
        self.assertEqual(self.manifest["new_network_attempt_count"], 1168)
        self.assertEqual(self.manifest["total_role5_network_request_count_including_pilot"], 1178)
        self.assertEqual(self.manifest["remaining_request_headroom"], 22)
        self.assertEqual(self.manifest["retry_count"], 0)
        self.assertEqual(self.manifest["failed_attempt_count_preserved_and_reconciled"], 10)
        self.assertEqual(self.manifest["http_status_counts"], {"200": 1165, "404": 3})

    def test_frozen_chain_gates_and_exact_counts(self) -> None:
        self.assertEqual(self.manifest["first_appearance_gate"], "PASS")
        self.assertEqual(self.manifest["contiguous_month_gate"], "PASS")
        self.assertEqual(self.manifest["canonical_chronology_gate"], "PASS")
        self.assertEqual(self.manifest["first_reference_date"], "2000-01-01")
        self.assertEqual(self.manifest["last_reference_date"], "2026-05-01")
        self.assertEqual(self.manifest["unique_reference_month_count"], 317)
        self.assertEqual(self.manifest["first_appearance_gate_pass_count"], 317)
        self.assertEqual(self.manifest["contiguous_month_transition_pass_count"], 316)
        self.assertEqual(self.manifest["release_snapshot_count"], 26078)
        self.assertEqual(self.manifest["observation_version_count"], 4859)
        self.assertEqual(self.manifest["first_print_count"], 317)
        self.assertEqual(self.manifest["revision_count"], 4542)
        self.assertEqual(self.manifest["unchanged_snapshot_count"], 21219)
        self.assertEqual(len(self.observations), 4859)
        self.assertEqual(len(self.snapshots), 26078)

    def test_point_in_time_lineage_and_exception_classifications(self) -> None:
        self.assertTrue(all(row["point_in_time_classification"] == ELIGIBLE_CLASSIFICATION for row in self.observations))
        self.assertTrue(all(row["protocol_eligibility"] == ELIGIBLE_PROTOCOL_STATUS for row in self.observations))
        self.assertEqual(
            self.manifest["source_identity_classification_counts"],
            {
                "DIRECT_OFFICIAL_DATED_RELEASE_IDENTITY": 1163,
                "OFFICIAL_ARCHIVE_ALIAS_RECONCILED": 1,
                "OFFICIAL_ARCHIVE_DIRECTORY_DATE_BODY_DATE_DIVERGENCE": 1,
                "OFFICIAL_FEDERAL_HOLIDAY_RELEASE_SHIFT_DIRECTORY_DATE_DIVERGENCE": 1,
                "OFFICIAL_RELEASEDATES_JSON_IDENTITY_CORRECTED_BY_OFFICIAL_YEAR_INDEX": 1,
            },
        )
        canonical = {
            row["source_index_identity"]: row["canonical_release_date"]
            for row in self.snapshots
            if row["source_index_identity"] in {"20050305", "20130405", "20161118", "20171123"}
        }
        self.assertEqual(
            canonical,
            {
                "20050305": "2005-03-03",
                "20130405": "2013-04-04",
                "20161118": "2016-11-17",
                "20171123": "2017-11-24",
            },
        )

    def test_supersedes_and_unchanged_snapshot_invariants(self) -> None:
        observations = {row["observation_id"]: row for row in self.observations}
        revisions = [row for row in self.observations if row["measurement_version_kind"] == "REVISION"]
        unchanged = [row for row in self.snapshots if row["snapshot_action"] == "UNCHANGED_SNAPSHOT_NO_NEW_VERSION"]
        self.assertEqual(len(revisions), 4542)
        self.assertEqual(len(unchanged), 21219)
        self.assertTrue(all(row["supersedes_observation_id"] in observations for row in revisions))
        self.assertTrue(all(row["created_observation_version"] == "false" for row in unchanged))
        self.assertTrue(all(row["active_observation_id"] in observations for row in unchanged))

    def test_official_publication_cadence_transition_is_recorded(self) -> None:
        methods = json.loads(self.outputs["ROLE5_H6_METHOD_LINEAGE.json"])
        self.assertEqual(
            methods["publication_cadence_segments"],
            [
                {
                    "publication_cadence": "WEEKLY_RELEASE",
                    "first_canonical_release_date": "2000-01-06",
                    "last_canonical_release_date": "2021-02-11",
                    "release_count": 1102,
                    "classification": "SOURCE_PUBLICATION_CADENCE_NOT_MEASUREMENT_FREQUENCY",
                },
                {
                    "publication_cadence": "MONTHLY_RELEASE",
                    "first_canonical_release_date": "2021-02-23",
                    "last_canonical_release_date": "2026-06-23",
                    "release_count": 65,
                    "classification": "SOURCE_PUBLICATION_CADENCE_NOT_MEASUREMENT_FREQUENCY",
                },
            ],
        )
        self.assertEqual(
            methods["m2_definition_transition_assessment"]["classification"],
            "M1_PRESENTATION_AND_DEFINITION_CHANGE_M2_STATED_UNCHANGED",
        )

    def test_contract_rejects_first_appearance_not_newest(self) -> None:
        releases = [release("20000301", "2000-03-01", [("2000-01-01", "100"), ("2000-02-01", "101")])]
        with self.assertRaisesRegex(CollectionValidationError, "first-appearance gate failed"):
            build_chains(releases, self.config)

    def test_contract_rejects_non_contiguous_reference_months(self) -> None:
        releases = [
            release("20000201", "2000-02-01", [("2000-01-01", "100")]),
            release("20000401", "2000-04-01", [("2000-01-01", "100"), ("2000-03-01", "103")]),
        ]
        with self.assertRaisesRegex(CollectionValidationError, "contiguous-month gate failed"):
            build_chains(releases, self.config)

    def test_unchanged_snapshot_does_not_create_fake_revision(self) -> None:
        releases = [
            release("20000201", "2000-02-01", [("2000-01-01", "100")]),
            release("20000301", "2000-03-01", [("2000-01-01", "100.0"), ("2000-02-01", "101")]),
        ]
        observations, snapshots, stats = build_chains(releases, self.config)
        self.assertEqual(len(observations), 2)
        self.assertEqual(stats["revision_count"], 0)
        self.assertEqual(stats["unchanged_snapshot_count"], 1)
        self.assertEqual(snapshots[1]["snapshot_action"], "UNCHANGED_SNAPSHOT_NO_NEW_VERSION")

    def test_generation_is_byte_deterministic_and_saved_outputs_match(self) -> None:
        repeated = build(ROOT)
        self.assertEqual(self.outputs, repeated)
        output_dir = ROOT / "research/artifacts/macro_regime/role5"
        for name, payload in self.outputs.items():
            if name == "MACRO_REGIME_ROLE5_COLLECTION_REPORT.md":
                continue  # Aggregate Role 5 report is superseded after H.4.1 completes.
            self.assertEqual((output_dir / name).read_bytes(), payload, name)


if __name__ == "__main__":
    unittest.main()

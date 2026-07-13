from __future__ import annotations

import csv
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from smartmarketscope_quant.macro_regime.source_audit import (
    CATEGORIES,
    CONFIG_RELATIVE_PATH,
    OUTPUT_FILES,
    SourceAuditError,
    build_audit,
    validate_outputs,
)


ROOT = Path(__file__).resolve().parents[2]


class MacroRegimeSourceAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = build_audit(ROOT)
        cls.series = list(csv.DictReader(io.StringIO(cls.result.series_csv.decode("ascii"))))
        cls.years = list(csv.DictReader(io.StringIO(cls.result.year_csv.decode("ascii"))))
        cls.categories = list(csv.DictReader(io.StringIO(cls.result.category_csv.decode("ascii"))))

    def test_frozen_source_decisions_and_counts(self) -> None:
        self.assertEqual(self.result.summary["status"], "PASS")
        self.assertEqual(self.result.summary["decision"], "PASS_BOUNDED_OFFICIAL_SOURCE_SET_FROZEN")
        self.assertEqual(self.result.summary["candidate_route_count"], 34)
        self.assertEqual(self.result.summary["series_output_count"], 34)
        self.assertEqual(self.result.summary["year_output_count"], 135)
        self.assertEqual(self.result.summary["category_output_count"], 5)
        self.assertEqual(self.result.summary["verified_existing_observation_count"], 1730)
        self.assertEqual(self.result.summary["verified_existing_route_count"], 5)
        self.assertEqual(self.result.summary["approved_bounded_route_count"], 19)
        self.assertEqual(
            self.result.summary["decision_counts"],
            {
                "APPROVED_EXISTING_EVIDENCE_ONLY": 5,
                "APPROVED_FOR_BOUNDED_COLLECTION": 19,
                "AVAILABILITY_OR_VERSION_UNRESOLVED": 2,
                "REQUIRES_KEY_OR_LICENSE_REVIEW": 4,
                "REJECTED": 3,
                "CURRENT_REVISED_HISTORY_ONLY": 1,
            },
        )

    def test_existing_counts_reconcile_and_liquidity_is_not_fabricated(self) -> None:
        self.assertEqual(
            self.result.summary["category_verified_counts"],
            {
                "INFLATION": 489,
                "LABOUR": 921,
                "GROWTH": 214,
                "MONETARY_POLICY": 106,
                "LIQUIDITY": 0,
            },
        )
        existing = [row for row in self.series if row["source_decision"] == "APPROVED_EXISTING_EVIDENCE_ONLY"]
        prospective = [row for row in self.series if row["evidence_status"] == "PROSPECTIVE_METADATA_ONLY"]
        self.assertEqual(sum(int(row["existing_observation_count"]) for row in existing), 1730)
        self.assertTrue(all(int(row["existing_observation_count"]) == 0 for row in prospective))
        liquidity = next(row for row in self.categories if row["category"] == "LIQUIDITY")
        self.assertEqual(liquidity["verified_existing_observation_version_count"], "0")
        self.assertEqual(liquidity["coverage_evidence_class"], "PROSPECTIVE_METADATA_ONLY_NO_VERIFIED_OBSERVATIONS")
        self.assertGreaterEqual(int(liquidity["approved_bounded_collection_release_bundle_count"]), 1)

    def test_year_matrix_is_exhaustive_and_distinguishes_evidence(self) -> None:
        self.assertEqual(len(self.years), 27 * 5)
        self.assertEqual({int(row["year"]) for row in self.years}, set(range(2000, 2027)))
        for year in range(2000, 2027):
            rows = [row for row in self.years if int(row["year"]) == year]
            self.assertEqual([row["category"] for row in rows], list(CATEGORIES))
        year_2000 = [row for row in self.years if row["year"] == "2000"]
        self.assertTrue(all(row["coverage_evidence_class"] == "PROSPECTIVE_METADATA_ONLY" for row in year_2000))
        self.assertTrue(all(row["prospective_metadata_expected_coverage"] == "YES" for row in year_2000))
        year_2018_inflation = next(row for row in self.years if row["year"] == "2018" and row["category"] == "INFLATION")
        self.assertEqual(year_2018_inflation["coverage_evidence_class"], "VERIFIED_EXISTING_PLUS_PROSPECTIVE_METADATA_ONLY")
        self.assertEqual(year_2018_inflation["verified_existing_observation_version_count_by_reference_year"], "72")
        year_2026_liquidity = next(row for row in self.years if row["year"] == "2026" and row["category"] == "LIQUIDITY")
        self.assertEqual(year_2026_liquidity["verified_existing_observation_version_count_by_reference_year"], "0")
        self.assertEqual(year_2026_liquidity["prospective_metadata_expected_coverage"], "YES")

    def test_current_revised_and_private_candidates_are_not_approved(self) -> None:
        current_revised = [row for row in self.series if row["source_decision"] == "CURRENT_REVISED_HISTORY_ONLY"]
        rejected = [row for row in self.series if row["source_decision"] == "REJECTED"]
        self.assertEqual([row["route_id"] for row in current_revised], ["NYFED_CURRENT_RRP_HISTORY"])
        self.assertEqual(
            {row["route_id"] for row in rejected},
            {"PRIVATE_ISM_MANUFACTURING", "PRIVATE_SERVICES_PMI", "OFFICIAL_NATIONAL_SERVICES_DIFFUSION_GAP"},
        )
        self.assertTrue(all(row["collection_scope"].startswith("DO_NOT") for row in current_revised + rejected))

    def test_bundle_counts_do_not_equal_route_or_series_weights(self) -> None:
        inflation = next(row for row in self.categories if row["category"] == "INFLATION")
        labour = next(row for row in self.categories if row["category"] == "LABOUR")
        self.assertEqual(inflation["approved_bounded_collection_route_count"], "5")
        self.assertEqual(inflation["approved_bounded_collection_release_bundle_count"], "3")
        self.assertEqual(labour["approved_bounded_collection_route_count"], "5")
        self.assertEqual(labour["approved_bounded_collection_release_bundle_count"], "3")
        cpi_rows = [row for row in self.series if row["release_bundle"] == "CPI_BUNDLE"]
        self.assertGreaterEqual(len(cpi_rows), 3)
        self.assertEqual({row["category"] for row in cpi_rows}, {"INFLATION"})

    def test_documentation_interaction_cap_and_no_collection(self) -> None:
        self.assertEqual(self.result.summary["documentation_interactions"], 41)
        report = self.result.report.decode("ascii")
        self.assertIn("Observation API requests, bulk requests, and raw macro downloads: `0 / 0 / 0`", report)
        self.assertIn("Total documentation interactions: `41`; cap: `60`", report)
        self.assertIn("PROSPECTIVE_COVERAGE_NOT_OBSERVATION_EVIDENCE", report)

    def test_generation_is_byte_deterministic_and_outputs_validate(self) -> None:
        repeated = build_audit(ROOT)
        self.assertEqual(self.result.outputs(), repeated.outputs())
        self.assertEqual(set(self.result.outputs()), set(OUTPUT_FILES))
        for content in self.result.outputs().values():
            content.decode("ascii")
        if all((ROOT / path).exists() for path in OUTPUT_FILES):
            validate_outputs(ROOT, self.result)

    def test_hash_tamper_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = json.loads((ROOT / CONFIG_RELATIVE_PATH).read_text(encoding="ascii"))
            for item in config["repository_inputs"].values():
                source = Path(item["path"])
                if not source.is_absolute():
                    source = ROOT / source
                target = Path(item["path"])
                if target.is_absolute():
                    continue
                destination = root / target
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            for relative in ("ALFRED_REGIME_ELIGIBLE_OBSERVATIONS.csv", "ALFRED_SERIES_RECLASSIFICATION.csv"):
                destination = root / relative
                if not destination.exists():
                    shutil.copy2(ROOT / relative, destination)
            config_path = root / CONFIG_RELATIVE_PATH
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(json.dumps(config, sort_keys=True, separators=(",", ":")) + "\n", encoding="ascii")
            tampered = root / "ALFRED_REGIME_ELIGIBLE_OBSERVATIONS.csv"
            tampered.write_bytes(tampered.read_bytes() + b" ")
            with self.assertRaisesRegex(SourceAuditError, "Repository input hash mismatch"):
                build_audit(root)


if __name__ == "__main__":
    unittest.main()

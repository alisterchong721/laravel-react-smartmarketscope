import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from smartmarketscope_quant.macro_regime import reporting


REPO = Path(__file__).resolve().parents[2]


class MacroRegimeReportingTests(unittest.TestCase):
    def test_upstream_hashes_and_role10_outputs_validate(self):
        result = reporting.validate(REPO)
        self.assertEqual("PASS", result["status"])
        self.assertEqual("INSUFFICIENT_ALIGNED_TRADES", result["decision"])
        self.assertGreaterEqual(result["upstream_hashes_verified"], 60)
        self.assertEqual(11, result["charts"])

    def test_offline_package_is_self_contained_and_fail_closed(self):
        report = REPO / "research/artifacts/macro_regime/report"
        for name in ("index.html", "interactive.html"):
            text = (report / name).read_text(encoding="utf-8").lower()
            for prohibited in ("http://", "https://", "fetch(", "axios", "place order", "broker integration"):
                self.assertNotIn(prohibited, text)
        self.assertIn("not_applicable_zero_retention", (report / "tables/MACRO_RANDOM_CONTROL_RESULTS.csv").read_text(encoding="utf-8").lower())

    def test_in_app_route_is_fail_closed_and_component_has_no_write_surface(self):
        app = (REPO / "src/App.js").read_text(encoding="utf-8")
        component = (REPO / "src/components/research/macro-regime-research.js").read_text(encoding="utf-8").lower()
        self.assertNotIn('path="/research/macro-regime"', app)
        self.assertIn("integration is fail-closed", component)
        for prohibited in ("axios", "fetch(", "post(", "put(", "delete(", "localstorage", "process.env", "dangerouslysetinnerhtml"):
            self.assertNotIn(prohibited, component)

    def test_missing_source_and_hash_tamper_fail_closed(self):
        with mock.patch.object(reporting, "sha256", return_value="0" * 64):
            with self.assertRaisesRegex(ValueError, "UPSTREAM_HASH_MISMATCH"):
                reporting.verify_upstream(REPO)

    def test_zero_and_not_applicable_are_distinct(self):
        with (REPO / "research/artifacts/macro_regime/report/tables/MACRO_RANDOM_CONTROL_RESULTS.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(__import__("csv").DictReader(handle))
        self.assertEqual(12, len(rows))
        self.assertTrue(all(row["target_retained_fills"] == "0" for row in rows))
        self.assertTrue(all(row["status"] == "NOT_APPLICABLE_ZERO_RETENTION" for row in rows))
        self.assertTrue(all(row["random_expectancy_mean_r"] == "" for row in rows))

    def test_manifest_declares_no_live_or_holdout_action(self):
        manifest = json.loads((REPO / "research/artifacts/macro_regime/report/manifests/ROLE10_REPORT_MANIFEST.json").read_text())
        self.assertEqual(0, manifest["external_fetches"])
        self.assertEqual(0, manifest["mutation_endpoints"])
        self.assertEqual(0, manifest["broker_or_order_controls"])
        self.assertEqual(0, manifest["final_holdout_accesses"])


if __name__ == "__main__":
    unittest.main()

import json
import hashlib
import subprocess
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

    def test_in_app_route_is_exact_server_verified_and_has_no_write_surface(self):
        app = (REPO / "src/App.js").read_text(encoding="utf-8")
        component = (REPO / "src/components/research/macro-regime-research.js").read_text(encoding="utf-8").lower()
        route = (REPO / "src/components/research/macro-regime-research-route.js").read_text(encoding="utf-8").lower()
        policy = (REPO / "src/components/research/macro-regime-access-policy.js").read_text(encoding="utf-8")
        self.assertEqual(1, app.count('path="/research/macro-regime"'))
        self.assertNotIn('path="/research/macro-regime/', app)
        self.assertIn("axios.get(apipath('/me')", route)
        self.assertIn("authorization: `bearer ${token}`", route)
        self.assertIn("verified_registered_user_read_only", policy.lower())
        self.assertIn("location.search", policy)
        self.assertIn("location.hash", policy)
        for prohibited in ("axios", "fetch(", "post(", "put(", "patch(", "delete(", "localstorage", "process.env", "dangerouslysetinnerhtml"):
            self.assertNotIn(prohibited, component)
        for prohibited in ("axios.post", "axios.put", "axios.patch", "axios.delete", "fetch(", "dangerouslysetinnerhtml"):
            self.assertNotIn(prohibited, route)

    def test_in_app_chart_copies_reconcile_byte_for_byte(self):
        source = REPO / "research/artifacts/macro_regime/report/charts"
        target = REPO / "src/components/research/charts"
        source_files = sorted(source.glob("*.png"))
        target_files = sorted(target.glob("*.png"))
        self.assertEqual(11, len(source_files))
        self.assertEqual([path.name for path in source_files], [path.name for path in target_files])
        for source_path, target_path in zip(source_files, target_files):
            self.assertEqual(hashlib.sha256(source_path.read_bytes()).hexdigest(), hashlib.sha256(target_path.read_bytes()).hexdigest())

    def test_app_rollback_patch_restores_authorized_baseline(self):
        remediation = REPO / "research/artifacts/macro_regime/role10/remediation"
        ownership = json.loads((remediation / "APP_ROUTE_OWNERSHIP_BOUNDARY.json").read_text())
        app = REPO / "src/App.js"
        self.assertEqual(ownership["post_hunk_sha256"], hashlib.sha256(app.read_bytes()).hexdigest())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src/App.js").write_bytes(app.read_bytes())
            result = subprocess.run(
                ["patch", "-p1", "-d", str(root), "-i", str(remediation / "APP_ROUTE_ROLLBACK.patch")],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            restored = hashlib.sha256((root / "src/App.js").read_bytes()).hexdigest()
            self.assertEqual(ownership["baseline_sha256"], restored)

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

    def test_remediation_manifest_preserves_terminal_research_decision(self):
        manifest = json.loads((REPO / "research/artifacts/macro_regime/role10/remediation/ROLE10_REMEDIATION_MANIFEST.json").read_text())
        self.assertEqual("IN_APP_ROUTE_ACTIVE_PENDING_ROLE11_SECURITY_REAUDIT", manifest["status"])
        self.assertEqual("NO_ACCEPTABLE_STRATEGY_FOUND", manifest["quantitative_decision"])
        self.assertEqual("NONE", manifest["candidate"])
        self.assertEqual([], manifest["mutation_methods"])
        self.assertFalse(manifest["final_holdout_accessed"])


if __name__ == "__main__":
    unittest.main()

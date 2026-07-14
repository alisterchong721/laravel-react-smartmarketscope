import unittest
import json
import hashlib
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

from smartmarketscope_quant.macro_regime import independent_audit


REPO = Path(__file__).resolve().parents[2]


class MacroRegimeIndependentAuditTests(unittest.TestCase):
    def test_terminal_negative_result_reproduces(self):
        evidence = independent_audit.audit(REPO)
        self.assertEqual("NO_ACCEPTABLE_STRATEGY_FOUND", evidence["decision"])
        self.assertEqual("NONE", evidence["candidate"])
        self.assertEqual(10273, evidence["counts"]["observations"])
        self.assertEqual(9676, evidence["counts"]["unknown_daily_rows"])
        self.assertEqual(0, evidence["macro_retained_fills"])

    def test_zero_retention_is_not_a_performance_success(self):
        evidence = independent_audit.audit(REPO)
        self.assertEqual("NOT_APPLICABLE_ZERO_RETENTION", evidence["random_control_status"])
        self.assertEqual("PROGRAM_COMPLETE_NO_ACCEPTABLE_STRATEGY_FOUND", evidence["full_program_status"])

    def test_hash_tamper_fails_closed(self):
        real = independent_audit.sha256

        def tamper(path):
            if path.name == "MACRO_DAILY_ASOF_REGIME.parquet":
                return "0" * 64
            return real(path)

        with mock.patch.object(independent_audit, "sha256", side_effect=tamper):
            with self.assertRaisesRegex(ValueError, "HASH_MISMATCH"):
                independent_audit.audit(REPO)

    def test_active_route_ownership_and_temporary_rollback(self):
        evidence = independent_audit.audit(REPO)["route_remediation"]
        self.assertEqual("PASS_TEMPORARY_COPY_ACTIVE_APP_UNCHANGED", evidence["rollback"])
        self.assertEqual(independent_audit.APP_ACTIVE_SHA256, independent_audit.sha256(REPO / "src/App.js"))

        ownership = json.loads((REPO / "research/artifacts/macro_regime/role10/remediation/APP_ROUTE_OWNERSHIP_BOUNDARY.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            (temporary_root / "src").mkdir()
            temporary_app = temporary_root / "src/App.js"
            temporary_app.write_bytes((REPO / "src/App.js").read_bytes())
            result = subprocess.run(
                ["git", "apply", "--unidiff-zero", str(REPO / ownership["rollback_patch"])],
                cwd=temporary_root,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(ownership["baseline_sha256"], hashlib.sha256(temporary_app.read_bytes()).hexdigest())
        self.assertEqual(ownership["post_hunk_sha256"], independent_audit.sha256(REPO / "src/App.js"))

    def test_active_route_auth_policy_idor_and_read_only_controls(self):
        route = independent_audit.audit(REPO)["route_remediation"]
        self.assertEqual("PASS_SERVER_VERIFIED_GET_ME_FAIL_CLOSED", route["authentication"])
        self.assertEqual("PASS_VERIFIED_REGISTERED_USER_READ_ONLY", route["authorization"])
        self.assertEqual("PASS_QUERY_FRAGMENT_EXTRA_PATH_DENIED", route["negative_idor"])
        self.assertEqual(["GET"], route["network_methods"])
        self.assertEqual([], route["mutation_methods"])

    def test_chart_hashes_page_content_and_accessibility(self):
        route = independent_audit.audit(REPO)["route_remediation"]
        self.assertEqual(11, route["chart_hashes_verified"])
        self.assertTrue(route["page_content"].startswith("PASS_"))
        self.assertTrue(route["accessibility"].startswith("PASS_"))

    def test_route_tamper_fails_closed(self):
        real = independent_audit.sha256

        def tamper(path):
            if path.name == "App.js":
                return "0" * 64
            return real(path)

        with mock.patch.object(independent_audit, "sha256", side_effect=tamper):
            with self.assertRaisesRegex(ValueError, "AUDIT_APP_ACTIVE_HASH"):
                independent_audit.audit(REPO)

    def test_role11_declared_outputs_rehash(self):
        manifest = json.loads((REPO / "research/artifacts/macro_regime/role11/ROLE11_OUTPUT_HASHES.json").read_text())
        for relative, expected in manifest.items():
            self.assertEqual(expected, independent_audit.sha256(REPO / relative))


if __name__ == "__main__":
    unittest.main()

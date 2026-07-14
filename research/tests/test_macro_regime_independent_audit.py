import unittest
import json
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
        self.assertEqual("BLOCKED_IN_APP_ROUTE_INTEGRATION", evidence["full_program_status"])

    def test_hash_tamper_fails_closed(self):
        real = independent_audit.sha256

        def tamper(path):
            if path.name == "MACRO_DAILY_ASOF_REGIME.parquet":
                return "0" * 64
            return real(path)

        with mock.patch.object(independent_audit, "sha256", side_effect=tamper):
            with self.assertRaisesRegex(ValueError, "HASH_MISMATCH"):
                independent_audit.audit(REPO)

    def test_route_must_remain_inactive_in_audit_role(self):
        app = (REPO / "src/App.js").read_text(encoding="utf-8")
        self.assertNotIn('path="/research/macro-regime"', app)

    def test_role11_declared_outputs_rehash(self):
        manifest = json.loads((REPO / "research/artifacts/macro_regime/role11/ROLE11_OUTPUT_HASHES.json").read_text())
        for relative, expected in manifest.items():
            self.assertEqual(expected, independent_audit.sha256(REPO / relative))


if __name__ == "__main__":
    unittest.main()

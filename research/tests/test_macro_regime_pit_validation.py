from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from smartmarketscope_quant.macro_regime import pit_validation as pit


ROOT = Path(__file__).resolve().parents[2]


class MacroRegimePointInTimeValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.role6_manifest, cls.audit, cls.detail = pit.audit_role6(ROOT)

    def test_full_population_independent_audit_passes(self) -> None:
        self.assertEqual([], self.audit.failures)
        self.assertEqual(10_273, self.detail["counts"]["events"])
        self.assertEqual(10_273, self.detail["counts"]["csv_rows"])
        self.assertEqual(10_273, self.detail["counts"]["jsonl_rows"])
        self.assertEqual(10_273, self.detail["counts"]["parquet_rows"])

    def test_daily_asof_and_coverage_decision_are_exact(self) -> None:
        self.assertEqual(9_676, self.detail["counts"]["daily_rows"])
        self.assertEqual(51_361, self.detail["counts"]["active_input_rows"])
        self.assertEqual(9_676, self.detail["counts"]["unknown_bias_rows"])
        self.assertEqual(2, self.detail["maximum_valid_categories"])

    def test_j0_is_dst_aware(self) -> None:
        self.assertEqual("2026-01-16T17:00:00Z", pit.iso_z(pit.j0_effective("2026-01-15")))
        self.assertEqual("2026-07-16T16:00:00Z", pit.iso_z(pit.j0_effective("2026-07-15")))

    def test_j1_j2_use_ordinal_frozen_source_dates(self) -> None:
        calendar = [date(2026, 3, 6), date(2026, 3, 9), date(2026, 3, 10)]
        self.assertEqual(datetime(2026, 3, 9, 4, tzinfo=timezone.utc), pit.trading_day_effective("2026-03-06", calendar, 1))
        self.assertEqual(datetime(2026, 3, 10, 4, tzinfo=timezone.utc), pit.trading_day_effective("2026-03-06", calendar, 2))

    def test_j1_j2_missing_calendar_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "insufficient future dates"):
            pit.trading_day_effective("2026-03-10", [date(2026, 3, 10)], 1)

    def test_prior_only_zero_mad_fallback_and_zero_scale(self) -> None:
        z, method, _, scale = pit.robust_z([0.0] * 11 + [2.0], 1.0)
        self.assertEqual("STD_FALLBACK", method)
        self.assertIsNotNone(z)
        self.assertGreater(scale or 0.0, 0.0)
        self.assertEqual((None, "ZERO_MAD_AND_STD", 1.0, 0.0), pit.robust_z([1.0] * 12, 1.0))

    def test_score_boundaries_are_inclusive_as_frozen(self) -> None:
        self.assertEqual([-2, -1, 0, 1, 2], [pit.z_bucket(value) for value in [-1.0, -0.25, 0.0, 0.25, 1.0]])
        self.assertEqual([-2, -1, 0, 1, 2], [pit.aggregate_bucket(value) for value in [-1.25, -0.25, 0.0, 0.25, 1.25]])

    def test_future_revision_chain_fails_closed(self) -> None:
        base = {
            "indicator_id": "US_CPI_ALL_ITEMS_SA", "reference_date": "2020-01-01", "family": "ALFRED",
            "supersedes_observation_id": "", "revision_number": 0, "observation_id": "O1",
            "effective_at_utc": "2020-02-15T17:00:00Z",
        }
        revision = {**base, "observation_id": "O2", "revision_number": 1, "supersedes_observation_id": "O1", "effective_at_utc": "2020-02-14T17:00:00Z"}
        audit = pit.Audit()
        pit.verify_revision_chains([base, revision], audit)
        self.assertTrue(audit.failures)

    def test_future_effective_time_fails_closed(self) -> None:
        event = {
            "observation_id": "FUTURE", "availability_date": "2020-01-01", "effective_at_utc": "2020-01-03T17:00:00Z",
            "effective_at_kl": "2020-01-04T01:00:00+08:00", "family": "ALFRED",
        }
        audit = pit.Audit()
        pit.verify_availability([event], audit)
        self.assertTrue(audit.failures)
        self.assertIn("POINT_IN_TIME_FEATURE_STORE_TIMING_INVALID", {code for check in audit.failures for code in check.failure_codes})

    def test_output_hash_tamper_fails_before_acceptance(self) -> None:
        real_sha = pit.sha256_file

        def tampered(path: Path) -> str:
            if path.name == "MACRO_DAILY_ASOF_REGIME.parquet":
                return "0" * 64
            return real_sha(path)

        with patch.object(pit, "sha256_file", side_effect=tampered):
            with self.assertRaisesRegex(ValueError, "R7-HASH-ROLE6-OUTPUT"):
                pit.validate_artifacts(ROOT)

    def test_materialized_role7_artifacts_validate(self) -> None:
        manifest = pit.validate_artifacts(ROOT)
        self.assertEqual("PASS", manifest["status"])
        self.assertEqual(0, manifest["counts"]["validation_errors"])

    def test_no_pnl_or_technical_inputs(self) -> None:
        manifest = pit.validate_artifacts(ROOT)
        self.assertEqual(0, manifest["technical_inputs"])
        self.assertEqual(0, manifest["pnl_inputs"])
        self.assertEqual(0, manifest["final_holdout_accesses"])


if __name__ == "__main__":
    unittest.main()

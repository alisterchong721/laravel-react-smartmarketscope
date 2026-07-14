from __future__ import annotations

import csv
import io
import json
import unittest
from pathlib import Path

from smartmarketscope_quant.macro_regime.h41_full_finalize import ELIGIBILITY, PIT, build


ROOT = Path(__file__).resolve().parents[2]


class MacroRegimeH41FullFinalizeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs = build(ROOT)
        cls.manifest = json.loads(cls.outputs["ROLE5_H41_FULL_NORMALIZED_MANIFEST.json"])
        cls.rows = list(csv.DictReader(io.StringIO(cls.outputs["ROLE5_H41_OBSERVATIONS.csv"].decode("utf-8"))))

    def test_full_accounting_and_request_ceiling(self) -> None:
        self.assertEqual(self.manifest["status"], "PASS")
        self.assertEqual(self.manifest["accepted_release_identity_count"], 1228)
        self.assertEqual(self.manifest["normalized_observation_count"], 3684)
        self.assertEqual(self.manifest["new_network_attempt_count"], 1224)
        self.assertEqual(self.manifest["total_h41_network_request_count_including_pilot"], 1232)
        self.assertEqual(self.manifest["remaining_request_headroom"], 28)
        self.assertEqual(self.manifest["retry_count"], 0)
        self.assertEqual(self.manifest["failed_attempt_count_preserved_and_reconciled"], 6)

    def test_series_point_in_time_and_boundaries(self) -> None:
        self.assertEqual(len(self.rows), 3684)
        self.assertEqual({row["internal_indicator_id"] for row in self.rows}, {
            "US_FED_TOTAL_ASSETS", "US_FED_RESERVE_BALANCES", "US_TREASURY_GENERAL_ACCOUNT",
        })
        self.assertTrue(all(row["point_in_time_classification"] == PIT for row in self.rows))
        self.assertTrue(all(row["protocol_eligibility"] == ELIGIBILITY for row in self.rows))
        self.assertEqual(self.manifest["first_reference_date"], "2002-12-18")
        self.assertEqual(self.manifest["last_reference_date"], "2026-06-24")

    def test_exact_signed_and_date_exceptions(self) -> None:
        by_key = {(row["source_index_identity"], row["internal_indicator_id"]): row for row in self.rows}
        signed = by_key[("20080703", "US_FED_RESERVE_BALANCES")]
        self.assertEqual(signed["normalized_numeric_value"], "-6962")
        expected_dates = {
            "20050305": "2005-03-03", "20161118": "2016-11-17",
            "20191128": "2019-11-29", "20200514": "2020-05-15",
        }
        for identity, expected in expected_dates.items():
            self.assertEqual(by_key[(identity, "US_FED_TOTAL_ASSETS")]["canonical_release_date"], expected)

    def test_generation_is_byte_deterministic_and_saved(self) -> None:
        repeated = build(ROOT)
        self.assertEqual(self.outputs, repeated)
        for name, payload in self.outputs.items():
            self.assertEqual((ROOT / "research/artifacts/macro_regime/role5" / name).read_bytes(), payload)


if __name__ == "__main__":
    unittest.main()

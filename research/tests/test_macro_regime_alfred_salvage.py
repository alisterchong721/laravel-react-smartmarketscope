from __future__ import annotations

import csv
import io
import shutil
import tempfile
import unittest
from pathlib import Path

from smartmarketscope_quant.macro_regime.alfred_salvage import (
    AVAILABILITY_DATE_UNRESOLVED,
    BATCH_RELATIVE_PATH,
    CURRENT_REVISED_HISTORY_ONLY,
    ELIGIBLE_CLASSIFICATIONS,
    OBSERVATION_FIELDS,
    OUTPUT_FILES,
    SOURCE_VERSION_UNRESOLVED,
    SalvageAuditError,
    UNUSABLE,
    VINTAGE_SAFE_FOR_DAILY_REGIME,
    VINTAGE_SAFE_WITH_DELAY,
    build_audit,
    classify_protocol_row,
    conservative_effective_times,
)


ROOT = Path(__file__).resolve().parents[2]
CREATED_AT = "2026-07-13T08:00:00Z"


class AlfredMacroRegimeSalvageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = build_audit(ROOT, created_at_utc=CREATED_AT)

    def test_real_batch_is_exhaustive_and_all_rows_require_delay(self) -> None:
        summary = self.result.summary
        self.assertEqual(summary["status"], "PASS_SALVAGED_WITH_CONSERVATIVE_DELAY")
        self.assertEqual(summary["source_run_count"], 25)
        self.assertEqual(summary["raw_artifact_count"], 25)
        self.assertEqual(summary["series_count"], 5)
        self.assertEqual(summary["observation_count"], 1730)
        self.assertEqual(summary["eligible_count"], 1730)
        self.assertEqual(summary["ineligible_count"], 0)
        self.assertEqual(summary["first_print_count"], 456)
        self.assertEqual(summary["revision_count"], 1274)
        self.assertEqual(summary["classifications"], {VINTAGE_SAFE_WITH_DELAY: 1730})
        eligible = list(csv.DictReader(io.StringIO(self.result.eligible_csv.decode("ascii"))))
        ineligible = list(csv.DictReader(io.StringIO(self.result.ineligible_csv.decode("ascii"))))
        self.assertEqual(len(eligible), 1730)
        self.assertEqual(ineligible, [])
        self.assertEqual(tuple(csv.DictReader(io.StringIO(self.result.ineligible_csv.decode("ascii"))).fieldnames), OBSERVATION_FIELDS)
        self.assertEqual(len({row["observation_id"] for row in eligible}), 1730)
        self.assertTrue(all(row["protocol_classification"] == VINTAGE_SAFE_WITH_DELAY for row in eligible))
        self.assertTrue(all(row["protocol_classification"] in ELIGIBLE_CLASSIFICATIONS for row in eligible))
        self.assertTrue(all(row["old_pit_status"] == "NOT_PIT_SAFE" for row in eligible))
        self.assertTrue(all(row["old_availability_at_utc"] == "" for row in eligible))

    def test_category_and_series_counts_reconcile(self) -> None:
        self.assertEqual(
            self.result.summary["category_counts"],
            {
                "INFLATION": 489,
                "LABOUR": 921,
                "GROWTH": 214,
                "MONETARY_POLICY": 106,
                "LIQUIDITY": 0,
            },
        )
        rows = list(csv.DictReader(io.StringIO(self.result.series_csv.decode("ascii"))))
        self.assertEqual([row["source_series_id"] for row in rows], ["CPIAUCSL", "PAYEMS", "UNRATE", "GDPC1", "FEDFUNDS"])
        self.assertEqual(sum(int(row["observation_count"]) for row in rows), 1730)
        self.assertEqual(sum(int(row["eligible_observation_count"]) for row in rows), 1730)
        self.assertEqual(sum(int(row["ineligible_observation_count"]) for row in rows), 0)

    def test_generation_is_byte_deterministic(self) -> None:
        repeated = build_audit(ROOT, created_at_utc=CREATED_AT)
        self.assertEqual(self.result.outputs(), repeated.outputs())
        self.assertEqual(set(self.result.outputs()), set(OUTPUT_FILES))

    def test_date_only_availability_applies_dst_aware_j0(self) -> None:
        winter_utc, winter_my = conservative_effective_times("2026-01-15")
        summer_utc, summer_my = conservative_effective_times("2026-06-15")
        self.assertEqual(winter_utc, "2026-01-16T17:00:00Z")
        self.assertEqual(summer_utc, "2026-06-16T16:00:00Z")
        self.assertEqual(winter_my, "2026-01-17T01:00:00+08:00")
        self.assertEqual(summer_my, "2026-06-17T00:00:00+08:00")

    def test_classifier_uses_only_the_six_frozen_fail_closed_states(self) -> None:
        common = {
            "vintage_mode": "POINT_IN_TIME_VINTAGE",
            "vintage_source": "ALFRED_OUTPUT_TYPE_3_NEW_AND_REVISED",
            "vintage_date": "2026-06-10",
            "historical_vintage_linked": True,
            "raw_hash_retained": True,
            "source_version_resolved": True,
            "immutable_revision_preserved": True,
            "exact_source_day_alignment": False,
        }
        self.assertEqual(classify_protocol_row(**common), VINTAGE_SAFE_WITH_DELAY)
        self.assertEqual(classify_protocol_row(**{**common, "exact_source_day_alignment": True}), VINTAGE_SAFE_FOR_DAILY_REGIME)
        self.assertEqual(classify_protocol_row(**{**common, "vintage_date": None}), AVAILABILITY_DATE_UNRESOLVED)
        self.assertEqual(classify_protocol_row(**{**common, "source_version_resolved": False}), SOURCE_VERSION_UNRESOLVED)
        self.assertEqual(classify_protocol_row(**{**common, "historical_vintage_linked": False}), UNUSABLE)
        self.assertEqual(
            classify_protocol_row(**{**common, "vintage_mode": "CURRENT_VINTAGE", "vintage_source": "STANDARD_FRED_CURRENT"}),
            CURRENT_REVISED_HISTORY_ONLY,
        )

    def test_raw_payload_tamper_fails_closed_without_touching_repository_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch_target = root / BATCH_RELATIVE_PATH
            batch_target.parent.mkdir(parents=True)
            shutil.copytree(ROOT / BATCH_RELATIVE_PATH, batch_target)
            for relative in (
                "research/config/program2_alfred_macro.json",
                "research/src/smartmarketscope_quant/fundamental_pit/alfred.py",
                "POINT_IN_TIME_FUNDAMENTAL_MANIFEST.yaml",
            ):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)
            raw_path = batch_target / "raw/cpiaucsl_new_and_revised_observations.json"
            raw_path.write_bytes(raw_path.read_bytes() + b" ")
            with self.assertRaisesRegex(SalvageAuditError, "Raw byte length mismatch"):
                build_audit(root, created_at_utc=CREATED_AT)

    def test_invalid_created_at_is_rejected(self) -> None:
        with self.assertRaises(SalvageAuditError):
            build_audit(ROOT, created_at_utc="2026-07-13")


if __name__ == "__main__":
    unittest.main()

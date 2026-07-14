from __future__ import annotations

import csv
import hashlib
import unittest
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

from smartmarketscope_quant.macro_regime import technical_alignment as alignment


ROOT = Path(__file__).resolve().parents[2]


class TechnicalAlignmentUnitTests(unittest.TestCase):
    def test_filter_mapping_is_exact(self) -> None:
        self.assertEqual(("NOT_APPLICABLE_UNKNOWN", "FILTERED_UNKNOWN"), alignment.relation_and_filter("UNKNOWN", "BULLISH"))
        self.assertEqual(("NOT_APPLICABLE_NEUTRAL", "FILTERED_NEUTRAL"), alignment.relation_and_filter("NEUTRAL", "BEARISH"))
        self.assertEqual(("DIRECTION_MATCH", "PERMITTED_DIRECTION_MATCH"), alignment.relation_and_filter("STRONG_BULLISH", "BULLISH"))
        self.assertEqual(("OPPOSITE_DIRECTION", "FILTERED_OPPOSITE_DIRECTION"), alignment.relation_and_filter("BEARISH", "BULLISH"))

    def test_source_calendar_ordinals_do_not_infer_dates(self) -> None:
        calendar = [date(2026, 3, 6), date(2026, 3, 9), date(2026, 3, 11)]
        self.assertEqual("2026-03-09", alignment.mode_effective(date(2026, 3, 6), "J1", calendar).date().isoformat())
        self.assertEqual("2026-03-11", alignment.mode_effective(date(2026, 3, 6), "J2", calendar).date().isoformat())
        self.assertIsNone(alignment.mode_effective(date(2026, 3, 10), "J2", calendar))

    def test_exact_effective_equality_is_eligible(self) -> None:
        utc = timezone.utc
        prior = (datetime(2026, 1, 1), datetime(2026, 1, 1, tzinfo=utc), "A", {"macro_snapshot_id": "A"}, "2025-12-31")
        equal = (datetime(2026, 1, 2), datetime(2026, 1, 2, tzinfo=utc), "B", {"macro_snapshot_id": "B"}, "2026-01-01")
        selected = alignment.select_latest_timeline([prior, equal], datetime(2026, 1, 2))
        self.assertIsNotNone(selected)
        self.assertEqual("B", selected[2])

    def test_future_snapshot_is_excluded(self) -> None:
        utc = timezone.utc
        prior = (datetime(2026, 1, 1), datetime(2026, 1, 1, tzinfo=utc), "A", {}, "2025-12-31")
        future = (datetime(2026, 1, 3), datetime(2026, 1, 3, tzinfo=utc), "B", {}, "2026-01-02")
        self.assertEqual("A", alignment.select_latest_timeline([prior, future], datetime(2026, 1, 2))[2])


class TechnicalAlignmentArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.role8 = ROOT / alignment.ROLE8
        cls.trade = pq.read_table(cls.role8 / "MACRO_REGIME_TECHNICAL_TRADE_REGISTRY.parquet").to_pylist()
        cls.links = pq.read_table(cls.role8 / "MACRO_TECHNICAL_LINKS.parquet").to_pylist()

    def test_frozen_baseline_census(self) -> None:
        medium = [row for row in self.trade if row["scenario_id"] == "NORMALIZED_MEDIUM_COST"]
        self.assertEqual(454, len(medium))
        self.assertEqual(Counter({"FILLED": 306, "NO_FILL": 148}), Counter(row["fill_status"] for row in medium))
        self.assertEqual(Counter({"LOSS_1R": 246, "NO_FILL": 148, "WIN_2R": 52, "AMBIGUOUS_ADVERSE_FIRST": 6, "TIMEOUT": 2}), Counter(row["outcome"] for row in medium))

    def test_original_technical_fields_are_byte_strings(self) -> None:
        with (ROOT / alignment.PRIMARY_TRADES).open(newline="", encoding="utf-8") as handle:
            source = list(csv.DictReader(handle))
        self.assertEqual(len(source), len(self.trade))
        for index, source_row in enumerate(source):
            self.assertTrue(all(self.trade[index][field] == source_row[field] for field in alignment.ORIGINAL_TRADE_FIELDS))

    def test_exact_source_calendar(self) -> None:
        with (self.role8 / "NAS100_SOURCE_TRADING_DATE_CALENDAR.csv").open(newline="", encoding="ascii") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(2309, len(rows))
        self.assertEqual("2017-07-17", rows[0]["source_trading_date"])
        self.assertEqual("2026-06-25", rows[-1]["source_trading_date"])
        self.assertEqual(2309, len({row["source_trading_date"] for row in rows}))
        self.assertEqual({"UNRESOLVED"}, {row["source_timezone"] for row in rows})
        self.assertEqual({"-1 day, 19:00:00", "-1 day, 20:00:00"}, {row["america_new_york_utc_offset"] for row in rows})

    def test_all_join_modes_cover_every_setup_once(self) -> None:
        self.assertEqual(1362, len(self.links))
        self.assertEqual(Counter({"J0": 454, "J1": 454, "J2": 454}), Counter(row["join_mode"] for row in self.links))
        self.assertEqual(1362, len({(row["technical_setup_id"], row["join_mode"]) for row in self.links}))

    def test_unknown_is_not_relaxed_and_no_replacements_exist(self) -> None:
        self.assertTrue(all(row["macro_bias"] == "UNKNOWN" for row in self.links))
        self.assertTrue(all(row["filter_decision"] == "FILTERED_UNKNOWN" for row in self.links))
        self.assertTrue(all(row["replacement_trade_created"] == "false" for row in self.links))

    def test_no_future_snapshot_enters_any_link(self) -> None:
        for row in self.links:
            decision = datetime.fromisoformat(row["technical_actionable_source_timestamp"])
            effective = datetime.fromisoformat(row["macro_effective_at_america_new_york"]).replace(tzinfo=None)
            self.assertLessEqual(effective, decision)
            self.assertEqual("false", row["future_state_violation"])

    def test_manifest_hashes_and_validator(self) -> None:
        result = alignment.validate(ROOT)
        self.assertEqual("PASS", result["status"])
        hashes = alignment.json.loads((self.role8 / "ROLE8_OUTPUT_HASHES.json").read_text(encoding="ascii"))
        for relative, expected in hashes.items():
            self.assertEqual(expected, hashlib.sha256((ROOT / relative).read_bytes()).hexdigest())

    def test_row_hashes_bind_every_trade_and_link_field(self) -> None:
        for row in self.trade:
            payload = dict(row)
            expected = payload.pop("technical_registry_row_sha256")
            self.assertEqual(expected, alignment.canonical_hash(payload))
        for row in self.links:
            payload = dict(row)
            expected = payload.pop("link_row_sha256")
            self.assertEqual(expected, alignment.canonical_hash(payload))


if __name__ == "__main__":
    unittest.main()

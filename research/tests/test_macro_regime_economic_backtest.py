from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import pyarrow.parquet as pq

from smartmarketscope_quant.macro_regime import economic_backtest as backtest


ROOT = Path(__file__).resolve().parents[2]


class EconomicBacktestUnitTests(unittest.TestCase):
    def test_unknown_fails_closed_for_every_macro_variant(self) -> None:
        config = backtest.read_json(ROOT / backtest.CONFIG)
        link = {"macro_bias": "UNKNOWN", "final_score": "", "valid_category_count": "2", "technical_direction": "BULLISH"}
        for variant in backtest.MACRO_VARIANTS:
            self.assertFalse(backtest.variant_permits(link, variant, config))

    def test_zero_trade_metrics_distinguish_null_from_zero(self) -> None:
        metric = backtest.calculate_metrics([], [], 100.0)
        self.assertEqual(0, metric["permitted_trades"])
        self.assertEqual(0, metric["total_net_r"])
        self.assertIsNone(metric["average_net_r"])
        self.assertIsNone(metric["profit_factor"])
        self.assertEqual("ZERO_TRADES", metric["metric_status"])

    def test_same_bar_adverse_outcome_is_not_relabelled(self) -> None:
        trades = pq.read_table(ROOT / backtest.TRADE_REGISTRY).to_pylist()
        adverse = [row for row in trades if row["scenario_id"] == "NORMALIZED_MEDIUM_COST" and row["outcome"] == "AMBIGUOUS_ADVERSE_FIRST"]
        self.assertEqual(6, len(adverse))
        self.assertTrue(all(float(row["net_r"]) < 0 for row in adverse))

    def test_hash_tamper_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "fake"
            target.write_text("tampered", encoding="ascii")
            self.assertNotEqual(hashlib.sha256(target.read_bytes()).hexdigest(), backtest.sha256_file(ROOT / backtest.TRADE_REGISTRY))


class EconomicBacktestArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.role9 = ROOT / backtest.ROLE9
        cls.metrics = pq.read_table(cls.role9 / "MACRO_BACKTEST_METRICS.parquet").to_pylist()

    def test_exact_t0_reconciliation(self) -> None:
        rows = [row for row in self.metrics if row["variant"] == "T0" and row["join_mode"] == "J0" and row["direction"] == "ALL" and row["year"] == "ALL" and row["cost_scenario"] == "NORMALIZED_MEDIUM_COST"]
        self.assertEqual(7, len(rows))
        self.assertEqual(306, sum(int(row["permitted_trades"]) for row in rows))
        self.assertAlmostEqual(-173.4578703725847, sum(float(row["total_net_r"]) for row in rows), places=12)

    def test_macro_variants_are_explicit_zero_trade_rows(self) -> None:
        rows = [row for row in self.metrics if row["variant"] in backtest.MACRO_VARIANTS]
        self.assertTrue(rows)
        self.assertTrue(all(int(row["permitted_trades"]) == 0 for row in rows))
        self.assertTrue(all(row["metric_status"] == "ZERO_TRADES" for row in rows))

    def test_every_global_year_is_explicit_for_every_strategy(self) -> None:
        years = {str(year) for year in range(2017, 2027)}
        for strategy in backtest.STRATEGIES:
            found = {row["year"] for row in self.metrics if row["variant"] == "M2_PRIMARY" and row["join_mode"] == "J0" and row["strategy_id"] == strategy and row["direction"] == "ALL"}
            self.assertEqual({"ALL", *years}, found)

    def test_year_rows_reconcile_to_overall(self) -> None:
        rows = [row for row in self.metrics if row["variant"] == "T0" and row["join_mode"] == "J0" and row["direction"] == "ALL" and row["cost_scenario"] == "NORMALIZED_MEDIUM_COST"]
        for strategy in backtest.STRATEGIES:
            selected = [row for row in rows if row["strategy_id"] == strategy]
            overall = next(row for row in selected if row["year"] == "ALL")
            annual = [row for row in selected if row["year"] != "ALL"]
            self.assertAlmostEqual(float(overall["total_net_r"]), sum(float(row["total_net_r"]) for row in annual), places=12)

    def test_join_sensitivities_remain_separate(self) -> None:
        for variant in backtest.MACRO_VARIANTS:
            self.assertEqual(set(backtest.JOIN_MODES), {row["join_mode"] for row in self.metrics if row["variant"] == variant})

    def test_standalone_and_hierarchical_strategies_remain_separate(self) -> None:
        self.assertEqual(set(backtest.STRATEGIES), {row["strategy_id"] for row in self.metrics})

    def test_random_control_is_not_applicable_at_zero_retention(self) -> None:
        import csv
        with (self.role9 / "MACRO_RANDOM_CONTROL_RESULTS.csv").open(newline="", encoding="ascii") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(12, len(rows))
        self.assertTrue(all(row["status"] == "NOT_APPLICABLE_ZERO_RETENTION" for row in rows))
        self.assertTrue(all(row["executed_draws"] == "0" for row in rows))

    def test_walk_forward_has_frozen_six_folds_without_reoptimization(self) -> None:
        import csv
        with (self.role9 / "MACRO_WALK_FORWARD_RESULTS.csv").open(newline="", encoding="ascii") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(set("123456"), {row["fold"] for row in rows})
        self.assertTrue(all(row["outer_reoptimization"] == "false" for row in rows))

    def test_manifest_hashes_and_validator(self) -> None:
        result = backtest.validate(ROOT)
        self.assertEqual("PASS", result["status"])
        self.assertEqual("INSUFFICIENT_ALIGNED_TRADES", result["decision"])


if __name__ == "__main__":
    unittest.main()

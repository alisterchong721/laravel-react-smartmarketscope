from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from smartmarketscope_quant.macro_regime import scoring


ROOT = Path(__file__).resolve().parents[2]


class MacroRegimeScoringUnitTest(unittest.TestCase):
    def test_prior_only_robust_z_and_zero_mad_fallback(self) -> None:
        prior = [float(i) for i in range(12)]
        z, method, center, scale = scoring.robust_z(prior, 12.0)
        self.assertEqual(method, "MAD")
        self.assertAlmostEqual(center, 5.5)
        self.assertGreater(z, 0)
        self.assertGreater(scale, 0)
        z2, method2, _, scale2 = scoring.robust_z([1.0] * 11 + [2.0], 3.0)
        self.assertEqual(method2, "STD_FALLBACK")
        self.assertIsNotNone(z2)
        self.assertGreater(scale2, 0)
        z3, status3, _, scale3 = scoring.robust_z([1.0] * 12, 2.0)
        self.assertIsNone(z3)
        self.assertEqual(status3, "ZERO_MAD_AND_STD")
        self.assertEqual(scale3, 0)
        self.assertEqual(scoring.robust_z(prior[:11], 12.0)[1], "INSUFFICIENT_HISTORY")

    def test_exact_z_and_aggregation_boundaries(self) -> None:
        self.assertEqual(scoring.z_bucket(1.0), 2)
        self.assertEqual(scoring.z_bucket(0.25), 1)
        self.assertEqual(scoring.z_bucket(-0.249999), 0)
        self.assertEqual(scoring.z_bucket(-0.25), -1)
        self.assertEqual(scoring.z_bucket(-1.0), -2)
        self.assertEqual(scoring.aggregate_bucket(1.25), 2)
        self.assertEqual(scoring.aggregate_bucket(0.25), 1)
        self.assertEqual(scoring.aggregate_bucket(-0.249999), 0)
        self.assertEqual(scoring.aggregate_bucket(-0.25), -1)
        self.assertEqual(scoring.aggregate_bucket(-1.25), -2)

    def test_inflation_and_liquidity_direction(self) -> None:
        score, _, _, _ = scoring._indicator_score("US_CPI_ALL_ITEMS_SA", 100, 1, 1, 1.0, 1)
        self.assertEqual(score, -2)
        score, _, _, _ = scoring._indicator_score("US_CPI_ALL_ITEMS_SA", 100, -1, -1, -1.0, -1)
        self.assertEqual(score, 2)
        score, _, _, _ = scoring._indicator_score("US_FED_TOTAL_ASSETS", 100, 1, 1, 1.0, 1)
        self.assertEqual(score, 2)
        score, _, _, _ = scoring._indicator_score("US_TREASURY_GENERAL_ACCOUNT", 100, 1, 1, 1.0, 1)
        self.assertEqual(score, -2)

    def test_labour_growth_policy_boundaries_and_stress(self) -> None:
        payroll = scoring._indicator_score("US_TOTAL_NONFARM_PAYROLLS", 100, -1, -1, 0.0, -1)
        self.assertEqual(payroll[0], -2)
        self.assertIn("PAYROLL_DETERIORATION", payroll[3])
        unemployment = scoring._indicator_score("US_UNEMPLOYMENT_RATE", 5.1, 0.2, 1.0, 0.0, 5.1)
        self.assertEqual(unemployment[0], -2)
        self.assertIn("LABOUR_STRESS", unemployment[3])
        self.assertEqual(scoring._indicator_score("US_UNEMPLOYMENT_RATE", 4.0, 0.0, 0.249999, 0.0, 4.0)[0], 1)
        self.assertEqual(scoring._indicator_score("US_REAL_GDP", 100, 0, 0, 0, -2.0001)[0], -2)
        self.assertEqual(scoring._indicator_score("US_REAL_GDP", 100, 0, 0, 0, 2.0)[0], 1)
        self.assertEqual(scoring._indicator_score("US_REAL_GDP", 100, 0, 0, 0, 3.0001)[0], 2)
        self.assertEqual(scoring._indicator_score("US_EFFECTIVE_FEDERAL_FUNDS_RATE", 5, 0.5, 0.5, None, None)[0], -2)
        self.assertEqual(scoring._indicator_score("US_EFFECTIVE_FEDERAL_FUNDS_RATE", 4, -0.5, -0.5, None, None)[0], 2)

    def test_interactions_caps_clamp_and_unknown(self) -> None:
        gold, adj = scoring.interaction_result({"INFLATION": 1, "LABOUR": 1, "GROWTH": 0, "MONETARY_POLICY": 0, "LIQUIDITY": 0}, set())
        self.assertEqual((gold, adj), (["GOLDILOCKS"], 1))
        hot, adj = scoring.interaction_result({"INFLATION": -1, "LABOUR": 0, "GROWTH": 1, "MONETARY_POLICY": 0, "LIQUIDITY": 0}, set())
        self.assertEqual((hot, adj), (["OVERHEATING"], -1))
        rec, adj = scoring.interaction_result({"INFLATION": 1, "LABOUR": -2, "GROWTH": -1, "MONETARY_POLICY": 2, "LIQUIDITY": 2}, {"LABOUR_STRESS", "UNEMPLOYMENT_STRESS"})
        self.assertEqual(rec, ["RECESSION_RISK", "EMERGENCY_EASING"])
        self.assertEqual(adj, -2)
        self.assertEqual(scoring.classify_bias(10, 2), "UNKNOWN")
        self.assertEqual(scoring.classify_bias(10, 5), "STRONG_BULLISH")
        self.assertEqual(scoring.classify_bias(-10, 5), "STRONG_BEARISH")
        self.assertEqual(scoring.clamp_final_score(10, 2), 10)
        self.assertEqual(scoring.clamp_final_score(-10, -3), -10)

    def test_category_sufficiency_does_not_renormalize(self) -> None:
        bundle = {"bundle_state_id": "b", "category": "INFLATION", "release_bundle": "CPI_BUNDLE", "discrete_bundle_score": 2}
        state = scoring.calculate_category_state("INFLATION", {"b": bundle}, 2, {}, "2020-01-01T00:00:00Z", "c", "d")
        self.assertEqual(state["category_status"], "PARTIAL")
        self.assertIsNone(state["discrete_category_score"])


class MacroRegimeScoringMaterializationTest(unittest.TestCase):
    def _copy_inputs(self, target: Path) -> None:
        paths = [
            "ALFRED_REGIME_ELIGIBLE_OBSERVATIONS.csv",
            "research/artifacts/macro_regime/role5/ROLE5_H6_OBSERVATION_VERSIONS.csv",
            "research/artifacts/macro_regime/role5/ROLE5_H41_OBSERVATIONS.csv",
            "research/config/MACRO_REGIME_INDICATOR_REGISTRY.yaml",
            "research/config/MACRO_REGIME_ALIAS_MAP.yaml",
            "research/config/MACRO_REGIME_RELEASE_BUNDLES.yaml",
            "research/config/MACRO_REGIME_SCORING_CONFIG.yaml",
        ]
        for relative in paths:
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)

    def test_real_inputs_materialize_validate_and_repeat_byte_identically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._copy_inputs(target)
            first = scoring.materialize(target)
            scoring.validate(target)
            output = target / scoring.OUTPUT_REL
            first_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
            second = scoring.materialize(target)
            scoring.validate(target)
            second_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
            self.assertEqual(first_hashes, second_hashes)
            self.assertEqual(first["counts"], second["counts"])
            self.assertEqual(first["counts"]["event_ledger_rows"], 10273)
            self.assertEqual(first["counts"]["final_bias_counts"], {"UNKNOWN": first["counts"]["daily_asof_rows"]})
            import pyarrow.parquet as pq
            active = pq.read_table(output / "MACRO_ACTIVE_INPUTS_BY_DAY.parquet").to_pylist()
            m2 = [r for r in active if r["indicator_id"] == "US_M2_MONEY_STOCK_SA"]
            same_state_run = next((i for i in range(len(m2) - 1) if m2[i]["indicator_state_id"] == m2[i + 1]["indicator_state_id"]), None)
            self.assertIsNotNone(same_state_run, "no-decay state must persist on a day without an update")
            indicator_states = pq.read_table(output / "MACRO_INDICATOR_STATE_HISTORY.parquet").to_pylist()
            m2_states = [r for r in indicator_states if r["indicator_id"] == "US_M2_MONEY_STOCK_SA"]
            self.assertIsNone(m2_states[0]["discrete_score"])
            self.assertEqual(m2_states[0]["coverage_state"], "INSUFFICIENT_HISTORY")
            self.assertTrue(any(r["coverage_state"] == "VALID" for r in m2_states))

    def test_input_hash_tamper_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._copy_inputs(target)
            path = target / "ALFRED_REGIME_ELIGIBLE_OBSERVATIONS.csv"
            path.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "input hash mismatch"):
                scoring.materialize(target)

    def test_registry_hash_tamper_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._copy_inputs(target)
            path = target / "research/config/MACRO_REGIME_ALIAS_MAP.yaml"
            value = json.loads(path.read_text())
            value["aliases"]["BAD"] = "US_REAL_GDP"
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "registry hash mismatch"):
                scoring.materialize(target)


if __name__ == "__main__":
    unittest.main()

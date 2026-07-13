from __future__ import annotations

import csv
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from smartmarketscope_quant.backtest.types import InstrumentScenario
from smartmarketscope_quant.macro_liquidity_reversal.models import Bar, Direction, Zone
from smartmarketscope_quant.macro_liquidity_reversal.technical_economic import (
    BarIndex,
    FillProof,
    FrozenEvent,
    TechnicalSetup,
    prove_limit_fill,
    prove_next_open_fill,
    simulate_path,
    simulate_setup,
    validate_frequency_checkpoint,
    validate_hash_registry,
)
from smartmarketscope_quant.macro_liquidity_reversal.technical_validation import (
    evaluate_cpcv,
    evaluate_walk_forward,
    validate_primary_lock,
)
from smartmarketscope_quant.macro_liquidity_reversal.technical_ablation import (
    TARGET_MULTIPLE,
    WIN_OUTCOME,
    simulate_path_at_target,
)
from smartmarketscope_quant.macro_liquidity_reversal.technical_audit import (
    reconcile_primary_rows,
)
from smartmarketscope_quant.validation import SampleInterval


BASE = datetime(2025, 1, 2, 12, 0)
REPO_ROOT = Path(__file__).resolve().parents[2]


def minute_bar(
    offset: int,
    open_: float,
    high: float,
    low: float,
    close: float,
) -> Bar:
    start = BASE + timedelta(minutes=offset)
    return Bar(start, start + timedelta(minutes=1), open_, high, low, close)


def setup(
    *,
    family: str = "C2_FVG_BREAKER",
    direction: Direction = Direction.BULLISH,
    expiry_minutes: int = 10,
) -> TechnicalSetup:
    return TechnicalSetup(
        setup_id="SETUP-1",
        strategy_id="M1_C2_FVG_BREAKER" if family == "C2_FVG_BREAKER" else "M1_C1_OB_FVG",
        event_id="EVENT-1",
        timeframe="M1",
        family=family,
        direction=direction,
        available_at=BASE,
        expiry_time=BASE + timedelta(minutes=expiry_minutes),
        confluence_zone=Zone(102, 104),
        block_zone=Zone(100, 104) if direction is Direction.BULLISH else Zone(102, 106),
        block_kind="BREAKER" if family == "C2_FVG_BREAKER" else "OB",
        component_ids=("FVG-1", "BLOCK-1"),
    )


def event(direction: Direction = Direction.BULLISH) -> FrozenEvent:
    return FrozenEvent(
        event_id="EVENT-1",
        direction=direction,
        d1_candle1_start=BASE - timedelta(days=1),
        d1_candle2_start=BASE,
        d1_confirmation_time=BASE,
        actionable_time=BASE,
        expiry_time=BASE + timedelta(minutes=10),
        h4_confirmation_time=BASE,
    )


def scenario() -> InstrumentScenario:
    return InstrumentScenario(
        scenario_id="NORMALIZED_TEST_COST",
        evidence_class="HYPOTHETICAL_SCENARIO_NOT_BROKER_FACT",
        currency="USD",
        point_value_usd_per_unit=Decimal("1"),
        contract_size_per_unit=Decimal("1"),
        min_quantity=Decimal("1"),
        quantity_step=Decimal("1"),
        max_quantity=Decimal("1"),
        leverage=Decimal("1"),
        spread_points=Decimal("0.4"),
        slippage_points_per_side=Decimal("0.1"),
        commission_usd_per_unit_per_side=Decimal("0.05"),
        financing_usd_per_unit_per_bar=Decimal("0"),
    )


class FrozenEvidenceTests(unittest.TestCase):
    def test_frequency_checkpoint_and_registry_chain_are_intact(self) -> None:
        checkpoint = REPO_ROOT / (
            "research/artifacts/macro_liquidity_reversal/governance/"
            "MLR_FREQUENCY_CHECKPOINT_20260713T123112+0800.json"
        )
        registry = REPO_ROOT / (
            "research/artifacts/macro_liquidity_reversal/"
            "MLR_TECHNICAL_ECONOMIC_EXPERIMENT_REGISTRY.jsonl"
        )
        validated = validate_frequency_checkpoint(REPO_ROOT, checkpoint)
        self.assertEqual(validated["verified_counts"]["d1_h4_confirmations"], 89)
        registry_rows = validate_hash_registry(registry)
        self.assertGreaterEqual(len(registry_rows), 1)
        self.assertEqual(registry_rows[0]["payload"]["status"], "PREREGISTERED")

    def test_primary_economic_artifacts_match_completed_lock(self) -> None:
        hashes = validate_primary_lock(REPO_ROOT)
        self.assertIn(
            "research/artifacts/macro_liquidity_reversal/MLR_TECHNICAL_PRIMARY_TRADES.csv",
            hashes,
        )

    def test_primary_trade_rows_reconcile_independently(self) -> None:
        trade_path = REPO_ROOT / (
            "research/artifacts/macro_liquidity_reversal/MLR_TECHNICAL_PRIMARY_TRADES.csv"
        )
        with trade_path.open(encoding="ascii", newline="") as handle:
            rows = list(csv.DictReader(handle))
        checks = reconcile_primary_rows(rows)
        self.assertEqual(checks["unique_setups"], 454)
        self.assertEqual(checks["filled_scenario_rows"], 918)


class FillAndPathTests(unittest.TestCase):
    def test_limit_requires_strict_penetration(self) -> None:
        candidate = setup()
        equality = BarIndex([minute_bar(0, 104, 105, 103, 104)])
        penetrated = BarIndex([minute_bar(0, 104, 105, 102.9, 104)])
        self.assertEqual(prove_limit_fill(candidate, equality).status, "NO_FILL")
        self.assertEqual(prove_limit_fill(candidate, penetrated).status, "FILLED")

    def test_c1_block_touch_before_midpoint_is_no_fill(self) -> None:
        candidate = setup(family="C1_OB_FVG")
        path = BarIndex([minute_bar(0, 104.5, 105, 103, 104.5)])
        proof = prove_limit_fill(candidate, path)
        self.assertEqual(proof.status, "NO_FILL")
        self.assertEqual(proof.reason, "OB_MITIGATED_BEFORE_MIDPOINT")

    def test_dual_barrier_is_adverse_first_and_retains_flag(self) -> None:
        candidate = setup()
        path = BarIndex(
            [
                minute_bar(0, 104, 105, 102.9, 104),
                minute_bar(1, 104, 112, 99, 105),
            ]
        )
        proof = prove_limit_fill(candidate, path)
        simulated, barriers = simulate_path(candidate, proof, scenario(), path)
        self.assertEqual(simulated.outcome, "AMBIGUOUS_ADVERSE_FIRST")
        self.assertTrue(simulated.ambiguous)
        self.assertEqual(barriers["stop"], Decimal("99.6"))
        self.assertEqual(barriers["risk_points"], Decimal("4.1"))
        self.assertEqual(barriers["target"], Decimal("111.2"))

    def test_entry_bar_target_is_ignored(self) -> None:
        candidate = setup(expiry_minutes=3)
        path = BarIndex(
            [
                minute_bar(0, 104, 112, 102.9, 110),
                minute_bar(1, 110, 111, 109, 110),
                minute_bar(2, 110, 111, 109, 110),
            ]
        )
        proof = prove_limit_fill(candidate, path)
        simulated, _ = simulate_path(candidate, proof, scenario(), path)
        self.assertEqual(simulated.outcome, "TIMEOUT")

    def test_control_entry_beyond_stop_is_skipped(self) -> None:
        candidate = setup()
        candidate = TechnicalSetup(
            setup_id=candidate.setup_id,
            strategy_id="CONTROL_D1_ONLY_GENERIC",
            event_id=candidate.event_id,
            timeframe=candidate.timeframe,
            family="GENERIC_DIRECTIONAL_ENTRY",
            direction=candidate.direction,
            available_at=candidate.available_at,
            expiry_time=candidate.expiry_time,
            confluence_zone=Zone(100, 100),
            block_zone=Zone(100, 100),
            block_kind="D1_CANDLE2_EXTREME",
            component_ids=(),
            entry_mode="MARKET_NEXT_M1_OPEN",
        )
        path = BarIndex([minute_bar(0, 98, 99, 97, 98)])
        proof = prove_next_open_fill(candidate, path)
        simulated, barriers = simulate_path(candidate, proof, scenario(), path)
        self.assertEqual(simulated.outcome, "NO_FILL")
        self.assertEqual(simulated.exit_reason, "PROTECTIVE_STOP_BREACHED_BEFORE_CONTROL_ENTRY")
        self.assertEqual(barriers, {})

    def test_costs_reconcile_and_simulated_fill_is_limit(self) -> None:
        candidate = setup()
        path = BarIndex(
            [
                minute_bar(0, 104, 105, 102.9, 104),
                minute_bar(1, 104, 112, 103.5, 111.5),
            ]
        )
        row = simulate_setup(candidate, path, [scenario()], event())[0]
        self.assertEqual(row["outcome"], "WIN_2R")
        self.assertEqual(row["actual_entry_fill_points"], Decimal("103.0"))
        self.assertEqual(row["actual_exit_fill_points"], Decimal("111.2"))
        self.assertEqual(row["gross_movement_points"], Decimal("8.2"))
        self.assertEqual(row["net_points"], Decimal("7.5"))
        self.assertEqual(
            row["gross_movement_points"]
            - row["spread_cost_points"]
            - row["slippage_cost_points"]
            - row["commission_cost_points"]
            - row["financing_cost_points"],
            row["net_points"],
        )


class ValidationTests(unittest.TestCase):
    def test_fixed_rule_cpcv_and_walk_forward_use_purged_intervals(self) -> None:
        samples = []
        by_id = {}
        for index in range(42):
            start = BASE + timedelta(days=index * 3)
            sample_id = f"S-{index:03d}"
            samples.append(
                SampleInterval(
                    sample_id=sample_id,
                    information_start=start,
                    information_end=start + timedelta(hours=1),
                    decision_timestamp=start + timedelta(hours=1),
                    label_start=start + timedelta(hours=2),
                    label_end=start + timedelta(days=1),
                )
            )
            by_id[sample_id] = {"net_r": "1" if index % 3 == 0 else "-0.5"}
        cpcv = evaluate_cpcv(samples, by_id)
        walk = evaluate_walk_forward(samples, by_id)
        self.assertEqual(cpcv["split_count"], 15)
        self.assertEqual(cpcv["path_count"], 5)
        self.assertEqual(walk["fold_count"], 2)
        self.assertTrue(all(fold["train_count"] >= 30 for fold in walk["folds"]))

    def test_authorized_target_ablation_changes_only_target_distance(self) -> None:
        candidate = setup()
        path = BarIndex(
            [
                minute_bar(0, 104, 105, 102.9, 104),
                minute_bar(1, 104, 109.2, 103.5, 109.1),
            ]
        )
        proof = prove_limit_fill(candidate, path)
        simulated, barriers = simulate_path_at_target(candidate, proof, scenario(), path)
        self.assertEqual(TARGET_MULTIPLE, Decimal("1.5"))
        self.assertEqual(barriers["risk_points"], Decimal("4.1"))
        self.assertEqual(barriers["target"], Decimal("109.15"))
        self.assertEqual(simulated.outcome, WIN_OUTCOME)


if __name__ == "__main__":
    unittest.main()

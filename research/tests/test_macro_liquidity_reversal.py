from __future__ import annotations

import csv
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from smartmarketscope_quant.data_audit.io import sha256_file, sha256_paths
from smartmarketscope_quant.macro_liquidity_reversal import (
    Bar,
    Confluence,
    Direction,
    FairValueGap,
    MacroBiasRecord,
    MacroState,
    OrderBlock,
    Zone,
    actionable_time,
    barrier_outcome,
    confluence,
    component_confluence,
    detect_fvgs,
    detect_breakers,
    detect_order_blocks,
    detect_sweep,
    exact_target,
    ema_from_completed_bars,
    find_h4_confirmation,
    frequency_permission,
    hierarchical_confluence,
    is_expired,
    macro_gate,
    midpoint_entry,
    protective_stop,
    trend_context,
)
from smartmarketscope_quant.macro_liquidity_reversal.detectors import is_unmitigated_before


BASE = datetime(2026, 1, 1)


def bar(index: int, open_: float, high: float, low: float, close: float, complete: bool = True) -> Bar:
    start = BASE + timedelta(days=index)
    return Bar(start, start + timedelta(days=1), open_, high, low, close, complete)


class SweepTests(unittest.TestCase):
    def test_valid_bullish_and_bearish_symmetry(self) -> None:
        bull = detect_sweep(bar(0, 110, 111, 99, 100), bar(1, 101, 104, 98, 102), Direction.BULLISH)
        bear = detect_sweep(bar(0, 100, 111, 99, 110), bar(1, 109, 112, 106, 108), Direction.BEARISH)
        self.assertIsNotNone(bull)
        self.assertIsNotNone(bear)

    def test_ratio_equality_passes_and_too_large_fails(self) -> None:
        first = bar(0, 110, 111, 99, 100)
        self.assertIsNotNone(detect_sweep(first, bar(1, 99.5, 105, 98, 104.5), Direction.BULLISH))
        self.assertIsNone(detect_sweep(first, bar(1, 99.5, 106, 98, 104.6), Direction.BULLISH))

    def test_touch_and_equal_close_fail_cross_and_close_back_pass(self) -> None:
        first = bar(0, 110, 111, 99, 100)
        self.assertIsNone(detect_sweep(first, bar(1, 101, 103, 99, 102), Direction.BULLISH))
        self.assertIsNone(detect_sweep(first, bar(1, 100, 103, 98, 99), Direction.BULLISH))
        self.assertIsNotNone(detect_sweep(first, bar(1, 100, 103, 98, 101), Direction.BULLISH))

    def test_candle2_may_be_bullish_or_bearish(self) -> None:
        first = bar(0, 110, 111, 99, 100)
        self.assertIsNotNone(detect_sweep(first, bar(1, 100, 103, 98, 101), Direction.BULLISH))
        self.assertIsNotNone(detect_sweep(first, bar(1, 102, 103, 98, 101), Direction.BULLISH))

    def test_stricter_full_body_is_only_ablation(self) -> None:
        first = bar(0, 110, 111, 99, 100)
        second = bar(1, 98.5, 103, 98, 100)
        self.assertIsNotNone(detect_sweep(first, second, Direction.BULLISH))
        self.assertIsNone(detect_sweep(first, second, Direction.BULLISH, full_body_above_below=True))

    def test_incomplete_bar_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "MLR_INCOMPLETE_BAR"):
            detect_sweep(bar(0, 110, 111, 99, 100), bar(1, 100, 103, 98, 101, False), Direction.BULLISH)

    def test_trend_context(self) -> None:
        self.assertTrue(trend_context(90, 95, 100, Direction.BULLISH))
        self.assertTrue(trend_context(110, 105, 100, Direction.BEARISH))
        self.assertFalse(trend_context(95, 95, 100, Direction.BULLISH))
        self.assertFalse(trend_context(90, 100, 100, Direction.BULLISH))

    def test_ema_warmup_and_incomplete_bar_fail_closed(self) -> None:
        bars = [bar(i, 100, 101, 99, 100) for i in range(49)]
        self.assertTrue(all(value is None for value in ema_from_completed_bars(bars, 50)))
        incomplete = [*bars, bar(49, 100, 101, 99, 100, False)]
        with self.assertRaisesRegex(ValueError, "MLR_INCOMPLETE_BAR"):
            ema_from_completed_bars(incomplete, 50)

    def test_wrong_candle1_direction_rejected(self) -> None:
        self.assertIsNone(detect_sweep(bar(0, 100, 111, 99, 110), bar(1, 101, 104, 98, 102), Direction.BULLISH))
        self.assertIsNone(detect_sweep(bar(0, 110, 111, 99, 100), bar(1, 109, 112, 106, 108), Direction.BEARISH))


class TimingZoneAndRiskTests(unittest.TestCase):
    def test_actionable_time_uses_later_confirmation(self) -> None:
        d1 = BASE + timedelta(days=2)
        h4 = BASE + timedelta(days=2, hours=4)
        self.assertEqual(actionable_time(d1, h4), h4)
        self.assertEqual(actionable_time(h4, d1), h4)

    def test_fvg_is_strict_and_available_after_third_close(self) -> None:
        bars = [bar(0, 100, 101, 99, 100), bar(1, 101, 102, 100, 101), bar(2, 104, 105, 103, 104)]
        found = detect_fvgs(bars, Direction.BULLISH)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].zone, Zone(101, 103))
        touching = [bar(0, 100, 101, 99, 100), bars[1], bar(2, 102, 103, 101, 102)]
        self.assertEqual(detect_fvgs(touching, Direction.BULLISH), [])

    def test_bearish_fvg_and_incomplete_component(self) -> None:
        bars = [bar(0, 104, 105, 103, 104), bar(1, 103, 104, 102, 103), bar(2, 100, 101, 99, 100)]
        found = detect_fvgs(bars, Direction.BEARISH)
        self.assertEqual(found[0].zone, Zone(101, 103))
        self.assertEqual(found[0].available_at, bars[2].available_at)
        with self.assertRaisesRegex(ValueError, "MLR_INCOMPLETE_BAR"):
            detect_fvgs([bars[0], bar(1, 103, 104, 102, 103, False), bars[2]], Direction.BEARISH)

    def test_positive_overlap_only(self) -> None:
        available = BASE + timedelta(days=1)
        self.assertEqual(confluence(Direction.BULLISH, "C1", Zone(10, 12), Zone(11, 13), available, available).zone, Zone(11, 12))
        self.assertIsNone(confluence(Direction.BULLISH, "C1", Zone(10, 11), Zone(11, 12), available, available))

    def test_component_confluence_rejects_opposite_direction(self) -> None:
        available = BASE + timedelta(days=1)
        fvg = FairValueGap(Direction.BULLISH, 0, 2, Zone(100, 104), available)
        opposite = OrderBlock(Direction.BEARISH, 0, 1, Zone(102, 106), available)
        same = OrderBlock(Direction.BULLISH, 0, 1, Zone(102, 106), available)
        self.assertIsNone(component_confluence("C1_OB_FVG", fvg, opposite))
        self.assertEqual(component_confluence("C1_OB_FVG", fvg, same).zone, Zone(102, 104))

    def test_stop_and_exact_two_r(self) -> None:
        stop = protective_stop(Direction.BULLISH, Zone(98, 101), point=0.1, pit_spread=0.5)
        self.assertEqual(stop, 97.5)
        self.assertEqual(exact_target(Direction.BULLISH, fill=100, stop=97.5), 105)
        self.assertEqual(exact_target(Direction.BEARISH, fill=100, stop=102.5), 95)
        with self.assertRaisesRegex(ValueError, "MLR_COST_UNRESOLVED"):
            protective_stop(Direction.BULLISH, Zone(98, 101), 0.1, 0.5, units_documented=False)

    def test_cost_inclusive_two_r_and_no_double_count_contract(self) -> None:
        self.assertEqual(exact_target(Direction.BULLISH, fill=103, stop=99.6, total_cost_per_unit=0.6), 111)
        self.assertEqual(exact_target(Direction.BULLISH, fill=103, stop=99.6, total_cost_per_unit=0.0), 109.8)

    def test_same_bar_is_adverse_first_without_valid_path(self) -> None:
        dual = bar(0, 100, 106, 94, 101)
        self.assertEqual(barrier_outcome(Direction.BULLISH, dual, 95, 105), "STOP")
        self.assertEqual(barrier_outcome(Direction.BULLISH, dual, 95, 105, "TARGET_FIRST"), "TARGET")

    def test_future_mutation_does_not_change_past_sweep(self) -> None:
        first = bar(0, 110, 111, 99, 100)
        second = bar(1, 100, 103, 98, 101)
        before = detect_sweep(first, second, Direction.BULLISH)
        future = bar(2, 1, 1000, 0.1, 999)
        after = detect_sweep(first, second, Direction.BULLISH)
        self.assertEqual(before, after)
        self.assertTrue(future.complete)

    def test_midpoint_entry_timing_fill_expiry_and_one_trade(self) -> None:
        candidate = Confluence(Direction.BULLISH, "C1_OB_FVG", Zone(102, 104), BASE + timedelta(hours=1))
        expiry = BASE + timedelta(hours=4)
        self.assertEqual(midpoint_entry("S1", candidate, BASE + timedelta(hours=2), 103, expiry, set(), False).reason, "MLR_FILL_UNPROVEN")
        self.assertTrue(midpoint_entry("S1", candidate, BASE + timedelta(hours=2), 103, expiry, set(), True).eligible)
        self.assertEqual(midpoint_entry("S1", candidate, candidate.available_at, 103, expiry, set(), True).reason, "COMPONENT_NOT_AVAILABLE")
        self.assertEqual(midpoint_entry("S1", candidate, expiry, 103, expiry, set(), True).reason, "SETUP_EXPIRED")
        self.assertEqual(midpoint_entry("S1", candidate, BASE + timedelta(hours=2), 103, expiry, {"S1"}, True).reason, "ONE_TRADE_PER_D1_SETUP")
        self.assertTrue(is_expired(expiry, expiry))

    def test_hierarchy_requires_order_overlap_and_same_family(self) -> None:
        expiry = BASE + timedelta(hours=8)
        m15 = [Confluence(Direction.BULLISH, "C1", Zone(100, 110), BASE + timedelta(hours=1))]
        m5 = [Confluence(Direction.BULLISH, "C1", Zone(102, 108), BASE + timedelta(hours=2))]
        m1 = [Confluence(Direction.BULLISH, "C1", Zone(103, 107), BASE + timedelta(hours=3))]
        self.assertEqual(hierarchical_confluence(m15, m5, m1, Direction.BULLISH, expiry).zone, Zone(103, 107))
        mixed = [Confluence(Direction.BULLISH, "C2", Zone(103, 107), BASE + timedelta(hours=3))]
        self.assertIsNone(hierarchical_confluence(m15, m5, mixed, Direction.BULLISH, expiry))
        nonoverlap = [Confluence(Direction.BULLISH, "C1", Zone(111, 112), BASE + timedelta(hours=2))]
        self.assertIsNone(hierarchical_confluence(m15, nonoverlap, m1, Direction.BULLISH, expiry))
        self.assertIsNone(hierarchical_confluence(m15, [], m1, Direction.BULLISH, expiry))

    def test_frequency_permissions(self) -> None:
        self.assertEqual(frequency_permission(29), "INSUFFICIENT_COMPLETE_SETUP_FREQUENCY")
        self.assertEqual(frequency_permission(30), "RULE_BASED_ONLY_ML_PROHIBITED")
        self.assertEqual(frequency_permission(99), "RULE_BASED_ONLY_ML_PROHIBITED")
        self.assertEqual(frequency_permission(100), "LOGISTIC_AND_SHALLOW_TREE_PERMITTED")
        self.assertEqual(frequency_permission(250), "XGBOOST_MAY_BE_CONSIDERED_UNDER_FROZEN_BUDGET")

    def test_completed_bar_safety_is_identical_for_all_ltf_names(self) -> None:
        for timeframe in ("M15", "M5", "M1"):
            with self.subTest(timeframe=timeframe), self.assertRaisesRegex(ValueError, "MLR_INCOMPLETE_BAR"):
                detect_fvgs([bar(0, 100, 101, 99, 100), bar(1, 101, 102, 100, 101), bar(2, 104, 105, 103, 104, False)], Direction.BULLISH)


class BlockTests(unittest.TestCase):
    def _bullish_structure(self, displacement_close: float = 120.0) -> list[Bar]:
        bars = [bar(i, 100 + i * 0.1, 102 + i * 0.1, 98 + i * 0.1, 100.5 + i * 0.1) for i in range(13)]
        bars.append(bar(13, 103, 104, 97, 99))
        bars.append(bar(14, 100, 121, 99, displacement_close))
        return bars

    def test_ob_requires_structure_and_displacement(self) -> None:
        valid = detect_order_blocks(self._bullish_structure(), Direction.BULLISH)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0].candle_index, 13)
        weak = detect_order_blocks(self._bullish_structure(105), Direction.BULLISH)
        self.assertEqual(weak, [])

    def test_ob_strict_break_equality_and_bearish_symmetry(self) -> None:
        equal = self._bullish_structure(103.2)
        prior_high = max(x.high for x in equal[4:14])
        equal[14] = bar(14, 100, prior_high + 1, 99, prior_high)
        self.assertEqual(detect_order_blocks(equal, Direction.BULLISH, displacement_atr=0), [])
        bullish = self._bullish_structure()
        mirrored = [Bar(x.start, x.available_at, -x.open, -x.low, -x.high, -x.close) for x in bullish]
        bearish = detect_order_blocks(mirrored, Direction.BEARISH)
        self.assertEqual(len(bearish), 1)
        self.assertEqual(bearish[0].candle_index, 13)

    def test_latest_candidate_wins_and_candidate_is_not_duplicated(self) -> None:
        bars = self._bullish_structure()
        bars[12] = bar(12, 105, 106, 98, 99)
        bars[13] = bar(13, 104, 105, 97, 98)
        bars.append(bar(15, 120, 125, 119, 124))
        found = detect_order_blocks(bars, Direction.BULLISH, displacement_atr=0)
        self.assertEqual(found[0].candle_index, 13)
        self.assertEqual(sum(block.candle_index == 13 for block in found), 1)

    def test_candidate_older_than_k_fails_and_threshold_is_not_silently_lowered(self) -> None:
        bars = [bar(i, 100, 102, 98, 101) for i in range(15)]
        bars[10] = bar(10, 104, 105, 99, 100)
        bars[14] = bar(14, 101, 112, 100, 111)
        self.assertEqual(detect_order_blocks(bars, Direction.BULLISH, displacement_atr=0), [])
        threshold_fixture = self._bullish_structure(108)
        self.assertEqual(detect_order_blocks(threshold_fixture, Direction.BULLISH, displacement_atr=1.0), [])
        self.assertEqual(len(detect_order_blocks(threshold_fixture, Direction.BULLISH, displacement_atr=0.5)), 1)

    def test_prior_mitigation_invalidates_unmitigated_state(self) -> None:
        bars = self._bullish_structure()
        block = detect_order_blocks(bars, Direction.BULLISH)[0]
        later = bars + [bar(15, 110, 112, 105, 111), bar(16, 105, 106, 100, 103)]
        self.assertTrue(is_unmitigated_before(block, later, 16))
        self.assertFalse(is_unmitigated_before(block, later, 17))

    def test_breaker_requires_correct_approach_and_first_retest(self) -> None:
        source = OrderBlock(Direction.BEARISH, 0, 1, Zone(100, 105), bar(1, 103, 104, 95, 96).available_at)
        valid = [
            bar(0, 104, 105, 100, 103),
            bar(1, 103, 104, 95, 96),
            bar(2, 96, 108, 95, 106),
            bar(3, 106, 107, 104, 104),
        ]
        self.assertEqual(len(detect_breakers(valid, [source])), 1)
        wrong_side_then_later_valid = [
            *valid[:3],
            bar(3, 98, 99, 97, 98),
            bar(4, 99, 104, 98, 103),
            bar(5, 106, 107, 104, 104),
        ]
        self.assertEqual(detect_breakers(wrong_side_then_later_valid, [source]), [])

    def test_failed_first_retest_cannot_be_reused(self) -> None:
        source = OrderBlock(Direction.BEARISH, 0, 1, Zone(100, 105), bar(1, 103, 104, 95, 96).available_at)
        bars = [
            bar(0, 104, 105, 100, 103),
            bar(1, 103, 104, 95, 96),
            bar(2, 96, 108, 95, 106),
            bar(3, 106, 107, 100, 101),
            bar(4, 106, 107, 104, 104),
        ]
        self.assertEqual(detect_breakers(bars, [source]), [])

    def test_break_and_midpoint_equality_fail_and_bearish_mirror(self) -> None:
        source = OrderBlock(Direction.BEARISH, 0, 1, Zone(100, 104), bar(1, 103, 104, 95, 96).available_at)
        equality_break = [bar(0, 104, 105, 100, 103), bar(1, 103, 104, 95, 96), bar(2, 96, 105, 95, 104)]
        self.assertEqual(detect_breakers(equality_break, [source]), [])
        midpoint_equal = [*equality_break[:2], bar(2, 96, 106, 95, 105), bar(3, 106, 107, 100, 102)]
        self.assertEqual(detect_breakers(midpoint_equal, [source]), [])
        valid_bullish = [*equality_break[:2], bar(2, 96, 106, 95, 105), bar(3, 106, 107, 103, 103)]
        mirrored = [Bar(x.start, x.available_at, -x.open, -x.low, -x.high, -x.close) for x in valid_bullish]
        mirrored_source = OrderBlock(Direction.BULLISH, 0, 1, Zone(-104, -100), source.available_at)
        bearish = detect_breakers(mirrored, [mirrored_source])
        self.assertEqual(len(bearish), 1)
        self.assertEqual(bearish[0].direction, Direction.BEARISH)


class MacroGateTests(unittest.TestCase):
    MACRO_BASE = BASE.replace(tzinfo=timezone.utc)

    def record(self, state: MacroState = MacroState.BULLISH, **changes) -> MacroBiasRecord:
        values = {
            "bias_id": "B1",
            "state": state,
            "effective_at": self.MACRO_BASE,
            "expires_at": self.MACRO_BASE + timedelta(days=1),
            "source_observation_ids": ("O1",),
            "source_run_ids": ("R1",),
            "first_received_at": (self.MACRO_BASE,),
            "revision_status": "ORIGINAL",
            "model_or_rule_version": "v1",
            "model_or_rule_sha256": "a" * 64,
            "validator_artifact_id": "V1",
            "validator_sha256": "b" * 64,
            "certification_status": "CERTIFIED_POINT_IN_TIME",
        }
        values.update(changes)
        return MacroBiasRecord(**values)

    def test_certified_directional_states_gate_direction(self) -> None:
        self.assertEqual(macro_gate(self.record(), self.MACRO_BASE + timedelta(hours=1)).direction, Direction.BULLISH)
        self.assertEqual(macro_gate(self.record(MacroState.BEARISH), self.MACRO_BASE + timedelta(hours=1)).direction, Direction.BEARISH)

    def test_non_directional_states_are_no_trade(self) -> None:
        for state in (MacroState.NEUTRAL, MacroState.UNKNOWN, MacroState.STALE, MacroState.CONFLICTING):
            with self.subTest(state=state):
                self.assertFalse(macro_gate(self.record(state), self.MACRO_BASE + timedelta(hours=1)).allowed)

    def test_missing_uncertified_future_and_expired_lineage_fail_closed(self) -> None:
        self.assertEqual(macro_gate(None, self.MACRO_BASE).reason, "BLOCKED_BY_UNCERTIFIED_MACRO_BIAS")
        self.assertFalse(macro_gate(self.record(certification_status="NOT_CERTIFIED"), self.MACRO_BASE + timedelta(hours=1)).allowed)
        self.assertEqual(macro_gate(self.record(first_received_at=(self.MACRO_BASE + timedelta(hours=2),)), self.MACRO_BASE + timedelta(hours=1)).reason, "MLR_TIMING_LEAKAGE")
        self.assertEqual(macro_gate(self.record(), self.MACRO_BASE + timedelta(days=1)).reason, "MACRO_NOT_EFFECTIVE_OR_EXPIRED")
        self.assertFalse(macro_gate(self.record(source_run_ids=()), self.MACRO_BASE + timedelta(hours=1)).allowed)

    def test_timezone_naive_macro_is_rejected(self) -> None:
        naive = self.record(effective_at=BASE, expires_at=BASE + timedelta(days=1), first_received_at=(BASE,))
        self.assertEqual(macro_gate(naive, BASE + timedelta(hours=1)).reason, "MLR_INPUT_INVALID_TIMEZONE_NAIVE_MACRO")


class H4WindowTests(unittest.TestCase):
    def test_h4_uses_own_level_and_actionable_max(self) -> None:
        d1_c2 = Bar(BASE, BASE + timedelta(days=1), 100, 110, 90, 95)
        d1_c3 = Bar(BASE + timedelta(days=1), BASE + timedelta(days=2), 95, 105, 92, 100)
        h4 = [
            Bar(BASE, BASE + timedelta(hours=4), 110, 112, 100, 102),
            Bar(BASE + timedelta(hours=4), BASE + timedelta(hours=8), 101, 106, 99, 104),
        ]
        found = find_h4_confirmation(d1_c2, d1_c3, h4, Direction.BULLISH, contained_only=True)
        self.assertEqual(found.reference_level, 100)
        self.assertEqual(actionable_time(d1_c2.available_at, found.confirmation_time), d1_c2.available_at)

    def test_h4_after_d1_outside_window_and_incomplete(self) -> None:
        d1_c2 = Bar(BASE, BASE + timedelta(days=1), 100, 110, 90, 95)
        d1_c3 = Bar(BASE + timedelta(days=1), BASE + timedelta(days=2), 95, 105, 92, 100)
        h4 = [
            Bar(BASE + timedelta(days=1), BASE + timedelta(days=1, hours=4), 110, 112, 100, 102),
            Bar(BASE + timedelta(days=1, hours=4), BASE + timedelta(days=1, hours=8), 101, 106, 99, 104),
            Bar(BASE + timedelta(days=1, hours=8), BASE + timedelta(days=1, hours=12), 104, 105, 103, 104),
        ]
        found = find_h4_confirmation(d1_c2, d1_c3, h4, Direction.BULLISH, extension_bars=2)
        self.assertEqual(found.confirmation_time, h4[1].available_at)
        self.assertEqual(actionable_time(d1_c2.available_at, found.confirmation_time), found.confirmation_time)
        self.assertIsNone(find_h4_confirmation(d1_c2, d1_c3, h4[2:], Direction.BULLISH, extension_bars=2))
        with self.assertRaisesRegex(ValueError, "MLR_INCOMPLETE_BAR"):
            find_h4_confirmation(d1_c2, d1_c3, [Bar(x.start, x.available_at, x.open, x.high, x.low, x.close, False) for x in h4], Direction.BULLISH)

    def test_later_h4_mutation_cannot_change_prior_confirmation(self) -> None:
        d1_c2 = Bar(BASE, BASE + timedelta(days=1), 100, 110, 90, 95)
        d1_c3 = Bar(BASE + timedelta(days=1), BASE + timedelta(days=2), 95, 105, 92, 100)
        h4 = [
            Bar(BASE, BASE + timedelta(hours=4), 110, 112, 100, 102),
            Bar(BASE + timedelta(hours=4), BASE + timedelta(hours=8), 101, 106, 99, 104),
            Bar(BASE + timedelta(hours=8), BASE + timedelta(hours=12), 104, 105, 103, 104),
        ]
        before = find_h4_confirmation(d1_c2, d1_c3, h4, Direction.BULLISH, contained_only=True)
        mutated = [*h4[:2], Bar(h4[2].start, h4[2].available_at, 1, 1000, 0, 999)]
        after = find_h4_confirmation(d1_c2, d1_c3, mutated, Direction.BULLISH, contained_only=True)
        self.assertEqual(before, after)


class FrequencyArtifactTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[2]
    ARTIFACTS = ROOT / "research/artifacts/macro_liquidity_reversal"

    def rows(self, name: str):
        with (self.ARTIFACTS / name).open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_required_machine_readable_registries_exist(self) -> None:
        required = {
            "MLR_MACRO_BIAS_REGISTRY.csv",
            "MLR_EVENT_REGISTRY.csv",
            "MLR_SETUP_REGISTRY.csv",
            "MLR_FVG_REGISTRY.csv",
            "MLR_OB_REGISTRY.csv",
            "MLR_BREAKER_REGISTRY.csv",
            "MLR_CONFLUENCE_REGISTRY.csv",
            "MLR_TECHNICAL_LAYER_REGISTRY.csv",
            "program_registry.json",
            "MLR_SPLIT_MANIFEST.json",
            "MLR_PREDICTIONS.csv",
            "MLR_TRADE_LOG.csv",
            "artifact_manifest.json",
        }
        self.assertTrue(required.issubset({path.name for path in self.ARTIFACTS.iterdir()}))

    def test_frequency_summary_reconciles_required_counts_and_gates(self) -> None:
        summary = json.loads((self.ARTIFACTS / "frequency_summary.json").read_text())
        self.assertEqual(summary["certified_macro_bias_days"], 0)
        self.assertEqual(sum(summary["d1_trend_sweep_counts"].values()), 183)
        self.assertEqual(sum(summary["d1_h4_confirmation_counts"].values()), 89)
        self.assertEqual(summary["setups_blocked_by_missing_macro_bias"], 89)
        self.assertEqual(summary["setups_blocked_by_incomplete_higher_timeframe_data"], 0)
        self.assertEqual(summary["per_timeframe"]["M15"]["technical_complete_setups"], 54)
        self.assertEqual(summary["per_timeframe"]["M5"]["technical_complete_setups"], 85)
        self.assertEqual(summary["per_timeframe"]["M1"]["technical_complete_setups"], 89)
        self.assertEqual(summary["per_timeframe"]["HIERARCHICAL_M15_M5_M1"]["technical_complete_setups"], 12)
        self.assertEqual(summary["per_timeframe"]["M1"]["frequency_permission"], "RULE_BASED_ONLY_ML_PROHIBITED")
        self.assertEqual(summary["full_strategy_complete_setups"], 0)

    def test_manifest_hashes_reconcile(self) -> None:
        manifest = json.loads((self.ARTIFACTS / "artifact_manifest.json").read_text())
        implementation = [self.ROOT / relative for relative in manifest["implementation_files"]]
        self.assertEqual(
            sha256_paths(implementation, path_root=self.ROOT),
            manifest["implementation_sha256"],
        )
        artifact_files = {
            "macro_bias_registry": "MLR_MACRO_BIAS_REGISTRY.csv",
            "event_registry": "MLR_EVENT_REGISTRY.csv",
            "setup_registry": "MLR_SETUP_REGISTRY.csv",
            "zone_registry": "MLR_ZONE_REGISTRY.csv",
            "fvg_registry": "MLR_FVG_REGISTRY.csv",
            "ob_registry": "MLR_OB_REGISTRY.csv",
            "breaker_registry": "MLR_BREAKER_REGISTRY.csv",
            "confluence_registry": "MLR_CONFLUENCE_REGISTRY.csv",
            "technical_layer_registry": "MLR_TECHNICAL_LAYER_REGISTRY.csv",
            "split_manifest": "MLR_SPLIT_MANIFEST.json",
            "predictions": "MLR_PREDICTIONS.csv",
            "trade_log": "MLR_TRADE_LOG.csv",
            "frequency_summary": "frequency_summary.json",
            "technical_ablations": "technical_ablation_results.json",
            "program_registry": "program_registry.json",
        }
        for key, filename in artifact_files.items():
            self.assertEqual(sha256_file(self.ARTIFACTS / filename), manifest["artifact_sha256"][key])
        self.assertEqual(manifest["counts"]["technical_experiments"], 6)
        self.assertEqual(manifest["counts"]["technical_variant_exposures"], 17)

    def test_setup_and_layer_registries_contain_no_economic_claim(self) -> None:
        setups = self.rows("MLR_SETUP_REGISTRY.csv")
        self.assertEqual(len(setups), 356)
        forbidden = {"pnl", "return", "fill_price", "target_outcome"}
        self.assertTrue(forbidden.isdisjoint(setups[0]))
        layers = self.rows("MLR_TECHNICAL_LAYER_REGISTRY.csv")
        for row in layers:
            for field in ("trade_count", "gross_result", "spread", "slippage", "commission", "net_result", "drawdown", "lower_tail_fold_result"):
                self.assertEqual(row[field], "NOT_RUN")

    def test_blocked_downstream_outputs_and_exposure_counts(self) -> None:
        macro = self.rows("MLR_MACRO_BIAS_REGISTRY.csv")
        self.assertEqual(macro[0]["eligible_bias_days"], "0")
        self.assertEqual(macro[0]["failure_code"], "BLOCKED_BY_UNCERTIFIED_MACRO_BIAS")
        split = json.loads((self.ARTIFACTS / "MLR_SPLIT_MANIFEST.json").read_text())
        self.assertEqual(split["splits"], [])
        self.assertTrue(split["status"].startswith("NOT_RUN"))
        self.assertTrue(self.rows("MLR_PREDICTIONS.csv")[0]["status"].startswith("NOT_RUN"))
        self.assertTrue(self.rows("MLR_TRADE_LOG.csv")[0]["status"].startswith("NOT_RUN"))
        registry = json.loads((self.ARTIFACTS / "program_registry.json").read_text())
        self.assertEqual(len(registry["experiments"]), 6)
        self.assertEqual(len(registry["trials"]), 17)
        self.assertEqual(registry["full_strategy_runs"], 0)
        ablations = json.loads((self.ARTIFACTS / "technical_ablation_results.json").read_text())
        self.assertEqual(len(ablations["results"]), 17)

    def test_no_event_crosses_protected_tuning_boundary(self) -> None:
        events = self.rows("MLR_EVENT_REGISTRY.csv")
        cutoff = datetime(2026, 6, 28, 23, 59, 59)
        self.assertTrue(all(datetime.fromisoformat(row["d1_candle2_start"]) <= cutoff for row in events))


if __name__ == "__main__":
    unittest.main()

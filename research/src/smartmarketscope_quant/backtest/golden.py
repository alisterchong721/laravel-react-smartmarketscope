from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from smartmarketscope_quant.data_audit.io import sha256_file, sha256_paths
from smartmarketscope_quant.validation.cpcv import build_cpcv
from smartmarketscope_quant.validation.splits import build_purged_kfold, build_walk_forward
from smartmarketscope_quant.validation.types import SampleInterval

from .config import load_execution_scenarios, load_prop_rule_scenarios
from .engine import BacktestEngine
from .prop import PropOutcome, evaluate_prop_path
from .sizing import size_for_risk
from .types import AccountPoint, MarketBar, OrderType, Side, TradeIntent


D = Decimal


def _bar(minute: int, open_value: str, high: str, low: str, close: str) -> MarketBar:
    timestamp = datetime(2026, 1, 2, 10, minute)
    return MarketBar(
        timestamp,
        timestamp + timedelta(minutes=15),
        D(open_value),
        D(high),
        D(low),
        D(close),
    )


def _intent(intent_id: str, side: Side = Side.LONG) -> TradeIntent:
    return TradeIntent(
        intent_id=intent_id,
        decision_timestamp=datetime(2026, 1, 2, 9, 59),
        activation_timestamp=datetime(2026, 1, 2, 10, 0),
        side=side,
        quantity=D("1"),
        entry_order_type=OrderType.MARKET,
        entry_order_price=None,
        stop_price=D("95") if side is Side.LONG else D("105"),
        target_price=D("110") if side is Side.LONG else D("90"),
        max_holding_bars=10,
    )


def _samples(count: int = 18) -> list[SampleInterval]:
    origin = datetime(2020, 1, 1)
    return [
        SampleInterval(
            sample_id=f"G{index:03d}",
            information_start=origin + timedelta(days=index, hours=-1),
            information_end=origin + timedelta(days=index),
            decision_timestamp=origin + timedelta(days=index),
            label_start=origin + timedelta(days=index),
            label_end=origin + timedelta(days=index, hours=6),
        )
        for index in range(count)
    ]


def _trade_summary(trade) -> dict:
    return {
        "exit_reason": trade.exit.reason,
        "exit_reference_price": str(trade.exit.reference_price),
        "gross_pnl_usd": str(trade.gross_pnl_usd),
        "spread_cost_usd": str(trade.spread_cost_usd),
        "slippage_cost_usd": str(trade.slippage_cost_usd),
        "commission_usd": str(trade.commission_usd),
        "financing_cost_usd": str(trade.financing_cost_usd),
        "net_pnl_usd": str(trade.net_pnl_usd),
        "ambiguity": trade.ambiguity,
        "evidence_class": trade.exit.evidence_class,
    }


def run_golden_harness(repo_root: Path) -> dict:
    execution_config = repo_root / "research/config/execution_scenarios.json"
    prop_config = repo_root / "research/config/prop_scenarios.json"
    scenarios = load_execution_scenarios(execution_config)
    scenario = next(item for item in scenarios if item.scenario_id == "NORMALIZED_MEDIUM_COST")
    prop_rules = load_prop_rule_scenarios(prop_config)
    static_rules = next(item for item in prop_rules if item.scenario_id == "GENERIC_STATIC_EQUITY_DD")
    trailing_rules = next(item for item in prop_rules if item.scenario_id == "GENERIC_TRAILING_EQUITY_DD")
    engine = BacktestEngine(scenario, D("50000"), 900)

    winning = engine.run(
        [_bar(0, "100", "104", "99", "103"), _bar(15, "103", "111", "102", "110")],
        [_intent("WIN")],
    ).trades[0]
    losing = engine.run([_bar(0, "100", "111", "94", "105")], [_intent("AMBIGUOUS")]).trades[0]
    gap = engine.run(
        [_bar(0, "100", "104", "99", "103"), _bar(15, "90", "92", "88", "89")],
        [_intent("GAP")],
    ).trades[0]
    short = engine.run(
        [_bar(0, "100", "102", "99", "100"), _bar(15, "99", "100", "89", "90")],
        [_intent("SHORT", Side.SHORT)],
    ).trades[0]
    sized = size_for_risk(scenario, D("100"), D("5"), D("103"), D("1000"))

    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    prop_target = evaluate_prop_path(
        [
            AccountPoint(start, D("50000"), D("50000"), "START"),
            AccountPoint(start + timedelta(days=10), D("53000"), D("53000"), "TARGET"),
        ],
        static_rules,
    )
    prop_drawdown = evaluate_prop_path(
        [
            AccountPoint(start, D("50000"), D("50000"), "START"),
            AccountPoint(start + timedelta(days=2), D("49000"), D("48000"), "BREACH"),
        ],
        static_rules,
    )
    prop_trailing = evaluate_prop_path(
        [
            AccountPoint(start, D("50000"), D("50000"), "START"),
            AccountPoint(start + timedelta(days=1), D("52000"), D("52000"), "PEAK"),
            AccountPoint(start + timedelta(days=2), D("51000"), D("50000"), "BREACH"),
        ],
        trailing_rules,
    )
    prop_timeout = evaluate_prop_path(
        [
            AccountPoint(start, D("50000"), D("50000"), "START"),
            AccountPoint(datetime(2026, 2, 1, tzinfo=timezone.utc), D("50500"), D("50500"), "END"),
        ],
        static_rules,
    )

    samples = _samples()
    walk = build_walk_forward(samples, 6, 3, timedelta(hours=1))
    purged = build_purged_kfold(samples, 3, "BARS", 1)
    cpcv = build_cpcv(samples, 6, 2, "BARS", 1)

    core_results = {
        "execution_scenario": scenario.scenario_id,
        "trades": {
            "winning_long": _trade_summary(winning),
            "adverse_first_same_bar": _trade_summary(losing),
            "gap_through_stop": _trade_summary(gap),
            "winning_short": _trade_summary(short),
        },
        "position_sizing": {
            "quantity": str(sized.quantity),
            "risk_per_unit_usd": str(sized.risk_per_unit_usd),
            "total_risk_usd": str(sized.total_risk_usd),
            "required_margin_usd": str(sized.required_margin_usd),
            "limiting_constraint": sized.limiting_constraint,
        },
        "prop_paths": {
            "target_before_drawdown": prop_target.outcome.value,
            "drawdown_before_target": prop_drawdown.outcome.value,
            "trailing_boundary": prop_trailing.outcome.value,
            "one_month_no_boundary": prop_timeout.outcome.value,
        },
        "validation_interfaces": {
            "walk_forward_splits": len(walk),
            "purged_kfold_splits": len(purged),
            "cpcv_splits": cpcv.split_count,
            "cpcv_paths": cpcv.path_count,
            "cpcv_identity_left": cpcv.identity_left,
            "cpcv_identity_right": cpcv.identity_right,
        },
    }
    if core_results["trades"]["adverse_first_same_bar"]["exit_reason"] != "STOP":
        raise RuntimeError("Golden same-bar outcome is not adverse-first")
    if core_results["trades"]["gap_through_stop"]["exit_reference_price"] != "90":
        raise RuntimeError("Golden gap stop did not use the gap open")
    if prop_target.outcome is not PropOutcome.TARGET_REACHED or prop_drawdown.outcome is not PropOutcome.DRAWDOWN_BREACH:
        raise RuntimeError("Golden prop path ordering failed")
    if cpcv.identity_left != cpcv.identity_right:
        raise RuntimeError("Golden CPCV identity failed")

    canonical = json.dumps(core_results, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    code_paths = sorted(
        list((repo_root / "research/src/smartmarketscope_quant/backtest").glob("*.py"))
        + list((repo_root / "research/src/smartmarketscope_quant/validation").glob("*.py"))
    )
    return {
        "schema_version": "1.0.0",
        "artifact_id": "VALIDATION-HARNESS-GOLDEN-QRP-20260712",
        "request_id": "QRP-20260711-141225Z",
        "status": "PASS",
        "random_seed": 0,
        "code_checksum": sha256_paths(code_paths),
        "execution_config_checksum": sha256_file(execution_config),
        "prop_config_checksum": sha256_file(prop_config),
        "core_results_checksum": hashlib.sha256(canonical.encode("ascii")).hexdigest(),
        "core_results": core_results,
        "limitations": [
            "All execution and prop rules are hypothetical scenarios, not broker or firm facts.",
            "Session embargo is unavailable until source timezone and calendar are verified.",
            "No strategy or historical performance was evaluated.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic Phase F golden fixtures")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research/artifacts/validation_harness/golden_results.json"),
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    output = args.output if args.output.is_absolute() else repo_root / args.output
    result = run_golden_harness(repo_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(result, indent=2, ensure_ascii=True) + "\n"
    output.write_text(content, encoding="ascii")
    print(content, end="")


if __name__ == "__main__":
    main()

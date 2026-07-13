from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .prop import DrawdownMode, PropRuleSpec, ValueBasis
from .types import InstrumentScenario


class HarnessConfigurationError(ValueError):
    pass


def _decimal(value, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise HarnessConfigurationError(f"Invalid decimal for {field}: {value!r}") from error


def _read(path: Path) -> dict:
    with path.open("r", encoding="ascii") as handle:
        return json.load(handle)


def load_execution_scenarios(path: Path) -> list[InstrumentScenario]:
    document = _read(path)
    if document.get("status") != "HYPOTHETICAL_SCENARIOS_NOT_BROKER_FACTS":
        raise HarnessConfigurationError("Execution scenarios must not masquerade as broker facts")
    scenarios = []
    for row in document.get("scenarios", []):
        scenarios.append(
            InstrumentScenario(
                scenario_id=row["scenario_id"],
                evidence_class=row["evidence_class"],
                currency=row["currency"],
                point_value_usd_per_unit=_decimal(row["point_value_usd_per_unit"], "point_value"),
                contract_size_per_unit=_decimal(row["contract_size_per_unit"], "contract_size"),
                min_quantity=_decimal(row["min_quantity"], "min_quantity"),
                quantity_step=_decimal(row["quantity_step"], "quantity_step"),
                max_quantity=_decimal(row["max_quantity"], "max_quantity"),
                leverage=_decimal(row["leverage"], "leverage"),
                spread_points=_decimal(row["spread_points"], "spread_points"),
                slippage_points_per_side=_decimal(
                    row["slippage_points_per_side"], "slippage_points_per_side"
                ),
                commission_usd_per_unit_per_side=_decimal(
                    row["commission_usd_per_unit_per_side"], "commission"
                ),
                financing_usd_per_unit_per_bar=_decimal(
                    row["financing_usd_per_unit_per_bar"], "financing"
                ),
            )
        )
    if not scenarios or len({item.scenario_id for item in scenarios}) != len(scenarios):
        raise HarnessConfigurationError("Execution scenario IDs must be nonempty and unique")
    return scenarios


def load_prop_rule_scenarios(path: Path) -> list[PropRuleSpec]:
    document = _read(path)
    if document.get("status") != "HYPOTHETICAL_SCENARIOS_NOT_PROP_FIRM_RULES":
        raise HarnessConfigurationError("Prop scenarios must not masquerade as firm rules")
    scenarios = []
    for row in document.get("scenarios", []):
        daily = row.get("daily_drawdown_usd")
        scenarios.append(
            PropRuleSpec(
                scenario_id=row["scenario_id"],
                rule_source=row["rule_source"],
                starting_equity_usd=_decimal(row["starting_equity_usd"], "starting_equity"),
                profit_target_usd=_decimal(row["profit_target_usd"], "profit_target"),
                maximum_drawdown_usd=_decimal(row["maximum_drawdown_usd"], "maximum_drawdown"),
                drawdown_mode=DrawdownMode(row["drawdown_mode"]),
                drawdown_basis=ValueBasis(row["drawdown_basis"]),
                target_basis=ValueBasis(row["target_basis"]),
                daily_drawdown_usd=_decimal(daily, "daily_drawdown") if daily is not None else None,
                daily_reset_timezone=row.get("daily_reset_timezone"),
            )
        )
    if not scenarios or len({item.scenario_id for item in scenarios}) != len(scenarios):
        raise HarnessConfigurationError("Prop scenario IDs must be nonempty and unique")
    return scenarios

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from .execution import make_fill, mark_to_market_exit_cost, resolve_entry, resolve_exit
from .types import (
    AccountPoint,
    BacktestResult,
    InstrumentScenario,
    MarketBar,
    Position,
    Side,
    TradeIntent,
    TradeResult,
    ZERO,
    money,
)


class BacktestError(ValueError):
    pass


class BacktestEngine:
    def __init__(
        self,
        scenario: InstrumentScenario,
        starting_balance_usd: Decimal,
        expected_bar_seconds: int,
    ) -> None:
        if starting_balance_usd <= ZERO or expected_bar_seconds <= 0:
            raise BacktestError("Starting balance and expected bar duration must be positive")
        self.scenario = scenario
        self.starting_balance_usd = money(starting_balance_usd)
        self.expected_bar_seconds = expected_bar_seconds

    def _validate_bars(self, bars: list[MarketBar]) -> None:
        if not bars:
            raise BacktestError("At least one market bar is required")
        for previous, current in zip(bars, bars[1:]):
            if current.timestamp <= previous.timestamp:
                raise BacktestError("Bars must be strictly chronological with no duplicates")

    @staticmethod
    def _barrier_order_valid(intent: TradeIntent, entry_reference: Decimal) -> bool:
        if intent.side is Side.LONG:
            return intent.stop_price < entry_reference < intent.target_price
        return intent.target_price < entry_reference < intent.stop_price

    def _quantity_valid(self, quantity: Decimal) -> bool:
        scenario = self.scenario
        if not (scenario.min_quantity <= quantity <= scenario.max_quantity):
            return False
        steps = quantity / scenario.quantity_step
        return steps == steps.to_integral_value()

    def _required_margin(self, quantity: Decimal, entry_reference: Decimal) -> Decimal:
        return money(
            entry_reference
            * self.scenario.contract_size_per_unit
            * quantity
            / self.scenario.leverage
        )

    def _close_trade(self, position: Position, exit_fill) -> TradeResult:
        intent = position.intent
        quantity = intent.quantity
        gross = money(
            intent.side.direction
            * (exit_fill.reference_price - position.entry_fill.reference_price)
            * quantity
            * self.scenario.point_value_usd_per_unit
        )
        spread = money(position.entry_fill.spread_cost_usd + exit_fill.spread_cost_usd)
        slippage = money(position.entry_fill.slippage_cost_usd + exit_fill.slippage_cost_usd)
        commission = money(position.entry_fill.commission_usd + exit_fill.commission_usd)
        net = money(gross - spread - slippage - commission - position.financing_cost_usd)
        fill_based = money(
            intent.side.direction
            * (exit_fill.fill_price - position.entry_fill.fill_price)
            * quantity
            * self.scenario.point_value_usd_per_unit
            - commission
            - position.financing_cost_usd
        )
        if fill_based != net:
            raise BacktestError("Gross/cost/net reconciliation failed")
        return TradeResult(
            intent_id=intent.intent_id,
            side=intent.side,
            quantity=quantity,
            entry=position.entry_fill,
            exit=exit_fill,
            gross_pnl_usd=gross,
            spread_cost_usd=spread,
            slippage_cost_usd=slippage,
            commission_usd=commission,
            financing_cost_usd=position.financing_cost_usd,
            net_pnl_usd=net,
            ambiguity=position.entry_fill.ambiguity or exit_fill.ambiguity,
            bars_held=position.bars_held,
        )

    def run(
        self,
        bars: list[MarketBar],
        intents: list[TradeIntent],
        lower_timeframe_evidence: dict[datetime, list[MarketBar]] | None = None,
    ) -> BacktestResult:
        self._validate_bars(bars)
        pending = sorted(intents, key=lambda item: (item.activation_timestamp, item.intent_id))
        if len({item.intent_id for item in pending}) != len(pending):
            raise BacktestError("Intent IDs must be unique")
        result = BacktestResult(
            starting_balance_usd=self.starting_balance_usd,
            ending_balance_usd=self.starting_balance_usd,
        )
        balance = self.starting_balance_usd
        position: Position | None = None
        previous_bar: MarketBar | None = None

        for bar_index, bar in enumerate(bars):
            had_position_at_bar_start = position is not None
            if previous_bar is not None:
                delta = int((bar.timestamp - previous_bar.timestamp).total_seconds())
                if delta != self.expected_bar_seconds or bar.missing_before:
                    result.event_log.append(
                        {
                            "timestamp": bar.timestamp.isoformat(),
                            "event": "MISSING_OR_IRREGULAR_BAR_GAP",
                            "delta_seconds": delta,
                            "contains_weekend": previous_bar.timestamp.weekday() >= 5
                            or bar.timestamp.weekday() >= 5
                            or delta >= 2 * 86400,
                        }
                    )

            if position is not None:
                position.bars_held += 1
                position.financing_cost_usd = money(
                    position.financing_cost_usd
                    + position.intent.quantity * self.scenario.financing_usd_per_unit_per_bar
                )
                lower = (lower_timeframe_evidence or {}).get(bar.timestamp)
                exit_fill = resolve_exit(position, bar, self.scenario, lower)
                if exit_fill is None and position.bars_held >= position.intent.max_holding_bars:
                    transaction = "SELL" if position.intent.side is Side.LONG else "BUY"
                    exit_fill = make_fill(
                        bar.timestamp,
                        "MAX_HOLD_EXIT",
                        transaction,
                        bar.close,
                        position.intent.quantity,
                        self.scenario,
                        "BAR_CLOSE_SCENARIO",
                    )
                if exit_fill is not None:
                    trade = self._close_trade(position, exit_fill)
                    balance = money(balance + trade.net_pnl_usd)
                    result.trades.append(trade)
                    result.event_log.append(
                        {
                            "timestamp": bar.timestamp.isoformat(),
                            "event": "POSITION_CLOSED",
                            "intent_id": trade.intent_id,
                            "reason": trade.exit.reason,
                            "net_pnl_usd": str(trade.net_pnl_usd),
                        }
                    )
                    position = None

            if position is None and not had_position_at_bar_start:
                for intent in list(pending):
                    if intent.activation_timestamp > bar.timestamp:
                        break
                    pending.remove(intent)
                    if intent.decision_timestamp > bar.timestamp:
                        result.event_log.append(
                            {
                                "timestamp": bar.timestamp.isoformat(),
                                "event": "ORDER_REJECTED_FUTURE_DECISION",
                                "intent_id": intent.intent_id,
                            }
                        )
                        continue
                    entry_fill = resolve_entry(intent, bar, self.scenario)
                    if entry_fill is None:
                        pending.append(intent)
                        pending.sort(key=lambda item: (item.activation_timestamp, item.intent_id))
                        continue
                    if not self._barrier_order_valid(intent, entry_fill.reference_price):
                        result.event_log.append(
                            {
                                "timestamp": bar.timestamp.isoformat(),
                                "event": "ORDER_REJECTED_INVALID_BARRIERS",
                                "intent_id": intent.intent_id,
                            }
                        )
                        continue
                    if not self._quantity_valid(intent.quantity):
                        result.event_log.append(
                            {
                                "timestamp": bar.timestamp.isoformat(),
                                "event": "ORDER_REJECTED_QUANTITY_RULE",
                                "intent_id": intent.intent_id,
                            }
                        )
                        continue
                    required_margin = self._required_margin(intent.quantity, entry_fill.reference_price)
                    if required_margin > balance:
                        result.event_log.append(
                            {
                                "timestamp": bar.timestamp.isoformat(),
                                "event": "ORDER_REJECTED_MARGIN",
                                "intent_id": intent.intent_id,
                                "required_margin_usd": str(required_margin),
                            }
                        )
                        continue
                    position = Position(
                        intent=intent,
                        entry_fill=entry_fill,
                        margin_used_usd=required_margin,
                    )
                    result.event_log.append(
                        {
                            "timestamp": bar.timestamp.isoformat(),
                            "event": "POSITION_OPENED",
                            "intent_id": intent.intent_id,
                            "fill_price": str(entry_fill.fill_price),
                        }
                    )
                    lower = (lower_timeframe_evidence or {}).get(bar.timestamp)
                    same_bar_exit = resolve_exit(position, bar, self.scenario, lower)
                    if (
                        same_bar_exit is not None
                        and same_bar_exit.reason == "TARGET"
                        and intent.entry_order_type.value != "MARKET"
                    ):
                        result.event_log.append(
                            {
                                "timestamp": bar.timestamp.isoformat(),
                                "event": "SAME_BAR_TARGET_IGNORED_ENTRY_ORDERING_UNRESOLVED",
                                "intent_id": intent.intent_id,
                            }
                        )
                        same_bar_exit = None
                    if same_bar_exit is not None:
                        trade = self._close_trade(position, same_bar_exit)
                        balance = money(balance + trade.net_pnl_usd)
                        result.trades.append(trade)
                        result.event_log.append(
                            {
                                "timestamp": bar.timestamp.isoformat(),
                                "event": "POSITION_CLOSED_SAME_BAR",
                                "intent_id": trade.intent_id,
                                "reason": trade.exit.reason,
                                "net_pnl_usd": str(trade.net_pnl_usd),
                            }
                        )
                        position = None
                    break

            if position is None:
                equity = balance
                margin_used = ZERO
            else:
                unrealized_gross = money(
                    position.intent.side.direction
                    * (bar.close - position.entry_fill.reference_price)
                    * position.intent.quantity
                    * self.scenario.point_value_usd_per_unit
                )
                incurred_entry_cost = position.entry_fill.total_cost_usd
                estimated_exit_cost = mark_to_market_exit_cost(position, self.scenario)
                equity = money(
                    balance
                    + unrealized_gross
                    - incurred_entry_cost
                    - estimated_exit_cost
                    - position.financing_cost_usd
                )
                margin_used = position.margin_used_usd
            result.account_path.append(
                AccountPoint(
                    timestamp=bar.available_at,
                    balance_usd=balance,
                    equity_usd=equity,
                    event="BAR_MARK",
                    margin_used_usd=margin_used,
                    free_margin_usd=money(equity - margin_used),
                )
            )
            previous_bar = bar

        if position is not None:
            last = bars[-1]
            transaction = "SELL" if position.intent.side is Side.LONG else "BUY"
            exit_fill = make_fill(
                last.available_at,
                "END_OF_DATA_EXIT",
                transaction,
                last.close,
                position.intent.quantity,
                self.scenario,
                "FINAL_AVAILABLE_CLOSE_SCENARIO",
            )
            trade = self._close_trade(position, exit_fill)
            balance = money(balance + trade.net_pnl_usd)
            result.trades.append(trade)
            final_point = AccountPoint(last.available_at, balance, balance, "END_OF_DATA_EXIT", ZERO, balance)
            if result.account_path and result.account_path[-1].timestamp == last.available_at:
                result.account_path[-1] = final_point
            else:
                result.account_path.append(final_point)

        for intent in pending:
            result.event_log.append(
                {
                    "timestamp": bars[-1].available_at.isoformat(),
                    "event": "ORDER_EXPIRED_END_OF_DATA",
                    "intent_id": intent.intent_id,
                }
            )
        result.ending_balance_usd = balance
        return result

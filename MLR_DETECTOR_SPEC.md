# MLR Detector Specification

Implementation:
`research/src/smartmarketscope_quant/macro_liquidity_reversal/`

The package provides immutable bar/zone/event models and symmetric direction-
parameterized implementations for trend context, D1/H4 sweep, actionable time,
FVG, OB, breaker, confluence, block stop, exact 2R, and adverse-first barrier
resolution. It rejects incomplete bars and equality where the skill requires a
strict cross or positive-width overlap.

Frequency code treats midpoint contact only as
`MIDPOINT_REACHED_NOT_FILL_PROOF`. It does not call the conservative execution
engine or create a trade.


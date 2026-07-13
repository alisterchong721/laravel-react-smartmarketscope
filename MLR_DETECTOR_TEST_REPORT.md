# MLR Detector Test Report

Status: `PASS_DETERMINISTIC_DETECTOR_SCOPE`

Command:

```text
PYTHONPATH=research/src python3 -m unittest research.tests.test_macro_liquidity_reversal -v
```

Result: 43 tests passed. Covered boundaries include bullish/bearish symmetry,
ratio equality, oversized body, wick touch versus cross, close equality, candle-2
polarity, close-only versus full-body rule, incomplete-bar rejection, EMA warmup
and completed-bar safety, actionable-time ordering, H4 search windows, strict FVG,
positive overlap, OB structure/displacement/lookback, prior mitigation,
first-retest breaker invalidation and approach handling, hierarchical confluence,
entry timing/expiry/one-trade rules, block stop, exact cost-inclusive 2R,
adverse-first same-bar resolution, and future-mutation invariance.

The suite also verifies that the macro gate fails closed for missing,
uncertified, stale, future-received, non-directional, lineage-deficient, and
timezone-naive observations. Machine-readable frequency artifacts reconcile to
the reports, contain no economic claims, stop at the protected-data cutoff, and
leave split, prediction, and trade outputs explicitly blocked. The manifest's
implementation-set and artifact hashes are recomputed by the suite.

Limitation: these are deterministic unit fixtures. They prove implementation
behavior, not market validity, fill quality, costs, or strategy edge.

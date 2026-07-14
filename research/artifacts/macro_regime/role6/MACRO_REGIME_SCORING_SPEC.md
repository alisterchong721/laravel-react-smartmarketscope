# Macro Regime Scoring Specification

Status: `PROSPECTIVELY_FROZEN_BEFORE_MATERIALIZATION`
Config version: `MACRO_REGIME_SCORING_V1`
Config SHA-256: `dbbe0d01ac22bbc05aef8b7d3c44867ecf265fddf9e427a94bb4488d9e643f2d`

## Point-in-time state construction

Only the 10,273 frozen eligible Role 2/5 observation versions may enter. Exact
effective timestamps are processed in atomic batches. For each reference period,
the latest version available at that timestamp replaces the earlier version;
future vintages are absent. Transformations use only the active reference series
known then. Robust center and scale exclude the current reference change and use
strictly earlier reference changes. At least 12 earlier valid changes are
required, except the numerical policy direction needs three observations. MAD is
multiplied by `1.4826`; zero MAD falls back to the prior-only population standard
deviation; if both are zero the update is `INSUFFICIENT_HISTORY`.

The state has no decay. A valid state remains active until that indicator's next
availability batch. An unscorable update explicitly replaces it with `UNKNOWN`.
Daily read-only as-of rows use `23:59:59Z` on every calendar date from
`2000-01-01` through `2026-06-28`; Role 7 owns later J0/J1/J2 and source-trading-
day validation before any technical join.

## Aggregation and interactions

Release bundles mean valid component discrete scores with equal weights.
Categories mean active valid bundle discrete scores with equal weights. Both use
the exact thresholds in the frozen config. All five valid categories would be
summed equally, but fewer than three valid categories returns `UNKNOWN` without
imputation or renormalization.

Only four interactions are permitted: `GOLDILOCKS +1`, `OVERHEATING -1`,
`RECESSION_RISK -2`, and conditional `EMERGENCY_EASING -1`. Their combined
adjustment is clamped to `[-2,+2]`; the final score is clamped to `[-10,+10]`.
Liquidity receives no additional interaction vote. Exact predicates are in the
frozen config.

Final bias is `STRONG_BULLISH` for `+5..+10`, `BULLISH` for `+2..+4`, `NEUTRAL`
for `-1..+1`, `BEARISH` for `-4..-2`, `STRONG_BEARISH` for `-10..-5`, and
`UNKNOWN` whenever category sufficiency fails.

## Exclusions and rejection criteria

No ML, LLM, news/sentiment, score decay, PnL-derived weight, technical join,
outcome inspection, experiment trial, or holdout access is allowed. A hash
mismatch, future-effective source, alias/category/bundle mismatch, nonfinite
value, invalid revision chain, boundary-test failure, or byte-nondeterministic
output fails materialization closed.

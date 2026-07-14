# Macro Regime Direction Mapping

Status: `PROSPECTIVELY_FROZEN`
Config SHA-256: `dbbe0d01ac22bbc05aef8b7d3c44867ecf265fddf9e427a94bb4488d9e643f2d`

The score means expected impact on NAS100, not generic US economic health.
Indicator scores are integers from `-2` (strong bearish) to `+2` (strong
bullish). Prior-only robust z boundaries are exactly `-1.00`, `-0.25`, `+0.25`,
and `+1.00`. Inflation and TGA invert the direct z mapping; M2, Fed assets, and
reserve balances use it directly.

- CPI uses the one-release change in year-over-year inflation. Acceleration is
  bearish; cooling is bullish.
- Payrolls reward positive, non-overheating growth, mark contraction bearish,
  and activate payroll stress when the three-release sum is negative.
- Unemployment is supportive when low/stable or mildly cooling. A three-release
  rise of at least `0.25` percentage point is bearish, at least `0.5` activates
  stress, and at least `1.0` is strongly bearish.
- Real GDP uses quarter-on-quarter annualized growth: below `-2%` is `-2`, below
  zero is `-1`, zero through `3%` is `+1`, and above `3%` is `+2` with an
  overheating flag available to the frozen interaction.
- Effective fed funds changes are inverted: strong tightening is `-2`, mild
  tightening is `-1`, stability is `0`, mild easing is `+1`, and strong easing
  is `+2`. Easing is not automatically bullish because the recession and
  emergency-easing interactions remain applicable.
- Liquidity uses prior-only normalized changes. TGA increases are drains and
  therefore invert direction. The one valid signed legacy reserve level uses
  absolute changes, not percentages.

Bundle and category scores are equal-weight means discretized at `-1.25`,
`-0.25`, `+0.25`, and `+1.25`. The exact formulas, equality boundaries,
stress rules, interactions, caps, and missingness behavior are authoritative in
the hash-locked config.

# MLR Frequency Report

Status: `TECHNICAL_ONLY_ABLATION`; full strategy status:
`BLOCKED_BY_UNCERTIFIED_MACRO_BIAS`.

## Higher Timeframes

| Measure | Bullish | Bearish | Total |
| --- | ---: | ---: | ---: |
| EMA trend-context days | 370 | 1,333 | 1,703 |
| D1 sweeps before trend filter | 144 | 203 | 347 |
| D1 sweeps matching trend | 38 | 145 | 183 |
| D1 + H4 confirmations | 18 | 71 | 89 |

Average actionable delay from D1 confirmation was 5.08 source-clock hours;
maximum was 60 hours, including native weekend/gap spacing. Ninety-four
trend-matched D1 sweeps lacked H4 confirmation in the primary window.

## Lower Timeframes

| Architecture | FVG | OB | Breaker | C1 reaches | C2 reaches | Any technical setup | Effective non-overlap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| M15 | 741 | 129 | 80 | 32 | 43 | 54 | 54 |
| M5 | 2,231 | 445 | 239 | 70 | 78 | 85 | 85 |
| M1 | 12,596 | 2,352 | 1,465 | 89 | 89 | 89 | 89 |
| Hierarchical M15→M5→M1 | N/A | N/A | N/A | 0 | 12 | 12 | 12 |

| Architecture | Average gap hours | Maximum gap hours | Overlap clusters | Frequency permission |
| --- | ---: | ---: | ---: | --- |
| M15 | 1,415.68 | 5,454.50 | 0 | Rule-based only; ML prohibited |
| M5 | 900.11 | 3,750.75 | 0 | Rule-based only; ML prohibited |
| M1 | 860.14 | 3,734.17 | 0 | Rule-based only; ML prohibited |
| Hierarchical M15→M5→M1 | 5,495.88 | 10,578.45 | 0 | Insufficient frequency |

M1 loaded 111,326 rows inside setup windows. The 89 M1 complete technical
setups consist of 18 bullish and 71 bearish windows. The hierarchical 12 consist
of 2 bullish and 10 bearish windows. This direction imbalance is material.

Full-strategy complete setups: zero, because certified macro-bias days are zero.
All 89 D1+H4 windows are blocked by missing certified macro bias; zero are
classified stale and zero are blocked by incomplete higher-timeframe data. All
C1/C2 values are first midpoint-reach diagnostics, not proved fills.

Machine-readable evidence under `research/artifacts/macro_liquidity_reversal/`
includes dedicated macro-bias, event, setup, FVG, OB, breaker, confluence, zone,
and technical-layer registries. Split, prediction, and trade files are present
only as explicit `NOT_RUN_BLOCKED_BY_UNCERTIFIED_MACRO_BIAS` records.

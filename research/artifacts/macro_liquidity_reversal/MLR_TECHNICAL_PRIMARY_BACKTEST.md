# MLR Technical Primary Backtest

Status: `TECHNICAL_ONLY_ABLATION`

This is the frozen first economic pass of the mechanical technical structure. It is not the intended macro-first strategy, not broker-calibrated, and not evidence of FTMO or Lucid readiness. Every historical row is `PREVIOUSLY_EXPOSED_WINDOW`.

## Preservation Check

The frozen detector/frequency checkpoint passed: 183 D1 sweeps, 89 D1+H4 confirmations, and midpoint-reach diagnostics 54/85/89/12 for M15/M5/M1/hierarchical.

Economic eligible setup counts may differ because this pass prospectively selects the first confirmed confluence before knowing whether its midpoint fills; the earlier diagnostics searched for a later midpoint reach. No frozen file was regenerated.

## Medium-Cost Primary Results

| Strategy | Eligible | Filled | No fill | Wins | Losses | Timeout | Ambiguous | Win rate | Avg net R | Total net R | Max DD R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| M15_C1_OB_FVG | 49 | 13 | 36 | 3 | 10 | 0 | 0 | 23.08% | -0.380 | -4.945 | 6.712 |
| M5_C1_OB_FVG | 83 | 24 | 59 | 5 | 18 | 0 | 1 | 20.83% | -0.473 | -11.350 | 11.721 |
| M1_C1_OB_FVG | 89 | 49 | 40 | 7 | 42 | 0 | 0 | 14.29% | -0.656 | -32.158 | 32.533 |
| M15_C2_FVG_BREAKER | 48 | 42 | 6 | 6 | 35 | 1 | 0 | 14.63% | -0.604 | -25.366 | 25.366 |
| M5_C2_FVG_BREAKER | 81 | 76 | 5 | 14 | 59 | 1 | 2 | 18.67% | -0.510 | -38.791 | 38.791 |
| M1_C2_FVG_BREAKER | 89 | 89 | 0 | 15 | 72 | 0 | 2 | 16.85% | -0.592 | -52.724 | 52.724 |
| HIERARCHICAL_M15_M5_M1 | 15 | 13 | 2 | 2 | 10 | 0 | 1 | 15.38% | -0.625 | -8.123 | 8.123 |

## Cost Sensitivity

| Strategy | Scenario | Filled | Wins | Losses | Timeout | Ambiguous | Avg gross R | Avg net R | Median net R | Profit factor | Total net R | Max DD R | Break-even win rate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| M15_C1_OB_FVG | NORMALIZED_LOW_COST | 13 | 3 | 10 | 0 | 0 | -0.141 | -0.355 | -1.000 | 0.539 | -4.613 | 6.474 | 35.77% |
| M15_C1_OB_FVG | NORMALIZED_MEDIUM_COST | 13 | 3 | 10 | 0 | 0 | -0.066 | -0.380 | -1.000 | 0.506 | -4.945 | 6.712 | 37.24% |
| M15_C1_OB_FVG | NORMALIZED_HIGH_COST | 13 | 1 | 12 | 0 | 0 | -0.361 | -0.808 | -1.000 | 0.125 | -10.502 | 10.502 | 40.03% |
| M5_C1_OB_FVG | NORMALIZED_LOW_COST | 24 | 5 | 18 | 0 | 1 | -0.066 | -0.447 | -1.000 | 0.436 | -10.719 | 11.157 | 37.65% |
| M5_C1_OB_FVG | NORMALIZED_MEDIUM_COST | 24 | 5 | 18 | 0 | 1 | 0.010 | -0.473 | -1.000 | 0.403 | -11.350 | 11.721 | 39.53% |
| M5_C1_OB_FVG | NORMALIZED_HIGH_COST | 24 | 3 | 20 | 1 | 0 | -0.108 | -0.682 | -1.000 | 0.212 | -16.358 | 16.358 | 40.29% |
| M1_C1_OB_FVG | NORMALIZED_LOW_COST | 49 | 8 | 41 | 0 | 0 | -0.072 | -0.600 | -1.000 | 0.286 | -29.389 | 29.389 | 40.53% |
| M1_C1_OB_FVG | NORMALIZED_MEDIUM_COST | 49 | 7 | 42 | 0 | 0 | -0.056 | -0.656 | -1.000 | 0.234 | -32.158 | 32.533 | 41.56% |
| M1_C1_OB_FVG | NORMALIZED_HIGH_COST | 49 | 3 | 46 | 0 | 0 | -0.218 | -0.855 | -1.000 | 0.090 | -41.877 | 42.227 | 42.12% |
| M15_C2_FVG_BREAKER | NORMALIZED_LOW_COST | 42 | 7 | 32 | 1 | 2 | -0.203 | -0.537 | -1.000 | 0.348 | -22.534 | 22.534 | 36.48% |
| M15_C2_FVG_BREAKER | NORMALIZED_MEDIUM_COST | 42 | 6 | 35 | 1 | 0 | -0.184 | -0.604 | -1.000 | 0.285 | -25.366 | 25.366 | 36.92% |
| M15_C2_FVG_BREAKER | NORMALIZED_HIGH_COST | 42 | 8 | 32 | 2 | 0 | 0.021 | -0.493 | -1.000 | 0.370 | -20.690 | 20.690 | 38.86% |
| M5_C2_FVG_BREAKER | NORMALIZED_LOW_COST | 76 | 12 | 58 | 1 | 5 | -0.141 | -0.558 | -1.000 | 0.327 | -42.422 | 42.422 | 38.72% |
| M5_C2_FVG_BREAKER | NORMALIZED_MEDIUM_COST | 76 | 14 | 59 | 1 | 2 | -0.001 | -0.510 | -1.000 | 0.364 | -38.791 | 38.791 | 40.31% |
| M5_C2_FVG_BREAKER | NORMALIZED_HIGH_COST | 76 | 10 | 63 | 3 | 0 | -0.075 | -0.660 | -1.000 | 0.222 | -50.167 | 50.167 | 43.26% |
| M1_C2_FVG_BREAKER | NORMALIZED_LOW_COST | 89 | 17 | 69 | 0 | 3 | 0.004 | -0.523 | -1.000 | 0.354 | -46.543 | 46.543 | 40.04% |
| M1_C2_FVG_BREAKER | NORMALIZED_MEDIUM_COST | 89 | 15 | 72 | 0 | 2 | 0.002 | -0.592 | -1.000 | 0.288 | -52.724 | 52.724 | 41.28% |
| M1_C2_FVG_BREAKER | NORMALIZED_HIGH_COST | 89 | 14 | 75 | 0 | 0 | 0.006 | -0.625 | -1.000 | 0.259 | -55.608 | 55.608 | 41.87% |
| HIERARCHICAL_M15_M5_M1 | NORMALIZED_LOW_COST | 13 | 2 | 9 | 0 | 2 | -0.137 | -0.612 | -1.000 | 0.277 | -7.957 | 7.957 | 39.66% |
| HIERARCHICAL_M15_M5_M1 | NORMALIZED_MEDIUM_COST | 13 | 2 | 10 | 0 | 1 | -0.073 | -0.625 | -1.000 | 0.262 | -8.123 | 8.123 | 41.01% |
| HIERARCHICAL_M15_M5_M1 | NORMALIZED_HIGH_COST | 13 | 2 | 10 | 0 | 1 | -0.026 | -0.632 | -1.000 | 0.253 | -8.222 | 8.222 | 41.86% |

## Medium-Cost Stability Detail

| Strategy | Avg hold hours | Profitable years | Active years | Years without trades | Bull fills / net R | Bear fills / net R |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| M15_C1_OB_FVG | 0.569 | 2 | 7 | 2017, 2018, 2026 | 1 / -1.000 | 12 / -3.945 |
| M5_C1_OB_FVG | 0.877 | 2 | 9 | 2026 | 2 / 0.593 | 22 / -11.944 |
| M1_C1_OB_FVG | 0.378 | 2 | 10 | None | 9 / -4.124 | 40 / -28.034 |
| M15_C2_FVG_BREAKER | 0.569 | 2 | 10 | None | 7 / -4.690 | 35 / -20.677 |
| M5_C2_FVG_BREAKER | 0.331 | 1 | 10 | None | 14 / -1.403 | 62 / -37.389 |
| M1_C2_FVG_BREAKER | 0.527 | 0 | 10 | None | 18 / -5.960 | 71 / -46.765 |
| HIERARCHICAL_M15_M5_M1 | 0.068 | 2 | 8 | 2017, 2018 | 2 / 0.539 | 11 / -8.662 |

## Accounting

Stops use `max(0.1 source-file quantum, scenario spread)` beyond the selected OB/breaker. Targets use the frozen exact-2R function with known round-trip spread, slippage, and commission points. Path-dependent hypothetical financing is charged to realized net R per full 24 source-clock hours and does not move the ex-ante barrier.

M1 strict penetration proves a conservative limit reach with no favorable price improvement. Equality alone is no fill. Entry-bar favorable targets are ignored; unresolved M1 dual barriers are adverse-first and separately flagged.

The low/medium/high costs are sensitivity scenarios, not Pepperstone facts. Dollar PnL is not claimed.

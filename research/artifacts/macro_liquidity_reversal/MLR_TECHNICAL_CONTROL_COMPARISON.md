# MLR Technical Control Comparison

Status: `TECHNICAL_ONLY_ABLATION`

All comparisons use normalized medium-cost R on previously exposed history.

| Strategy | Avg net R | Matched generic avg net R | Increment | D1+H4 generic avg net R |
| --- | ---: | ---: | ---: | ---: |
| M15_C1_OB_FVG | -0.380 | -0.110 | -0.270 | -0.143 |
| M5_C1_OB_FVG | -0.473 | -0.331 | -0.142 | -0.143 |
| M1_C1_OB_FVG | -0.656 | -0.518 | -0.139 | -0.143 |
| M15_C2_FVG_BREAKER | -0.604 | -0.530 | -0.074 | -0.143 |
| M5_C2_FVG_BREAKER | -0.510 | -0.393 | -0.118 | -0.143 |
| M1_C2_FVG_BREAKER | -0.592 | -0.430 | -0.162 | -0.143 |
| HIERARCHICAL_M15_M5_M1 | -0.625 | 0.064 | -0.688 | -0.143 |

No-trade control: 0 trades, 0 R. D1-only generic: 179 fills, -0.060 average net R. D1+H4 generic: 86 fills, -0.143 average net R.

The matched generic control preserves each setup's direction, activation, block, stop, target, expiry, and costs but enters at the next M1 open. It tests the midpoint-mitigation entry increment. D1-only and D1+H4 controls use the D1 candle-2 reversal extreme as the protective block and therefore are broader directional controls, not identical-trade counterfactuals.

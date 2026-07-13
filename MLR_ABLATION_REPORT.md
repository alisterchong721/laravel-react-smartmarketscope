# MLR Ablation Report

Status: `COMPLETED_TECHNICAL_ONLY_NO_SELECTION`

Six preregistered experiments exposed 17 frequency variants:

| Dimension | Variant | D1 sweeps | D1+H4 |
| --- | --- | ---: | ---: |
| Body ratio | 0.25 | 130 | 39 |
| Body ratio | 0.50 primary | 183 | 89 |
| Body ratio | 0.75 | 222 | 130 |
| Sweep rule | Close-only primary | 183 | 89 |
| Sweep rule | Full body across level | 174 | 83 |
| Trend | EMA20/EMA50 primary | 183 | 89 |
| Trend | No trend filter | 357 | 157 |
| H4 window | Contained in D1 candle 2 | 183 | 61 |
| H4 window | Two post-close H4 | 183 | 75 |
| H4 window | Three post-close H4 primary | 183 | 89 |
| H4 window | Through D1 candle 3 | 183 | 111 |

The two lower-timeframe OB experiments report detector frequency only:

| Dimension | Variant | M15 OB / windows | M5 OB / windows | M1 OB / windows |
| --- | --- | ---: | ---: | ---: |
| Structure lookback | 5 | 167 / 73 | 576 / 88 | 3,150 / 89 |
| Structure lookback | 10 primary | 129 / 65 | 445 / 88 | 2,352 / 89 |
| Structure lookback | 20 | 98 / 57 | 322 / 85 | 1,691 / 89 |
| Displacement | None | 277 / 83 | 856 / 89 | 4,372 / 89 |
| Displacement | 0.5 ATR | 206 / 80 | 682 / 89 | 3,541 / 89 |
| Displacement | 1.0 ATR primary | 129 / 65 | 445 / 88 | 2,352 / 89 |

These are mechanical frequency effects, not economic comparisons. No variant was
selected, promoted, or used to change the frozen primary. The OB window figures
are counts of the 89 D1+H4 windows containing at least one qualifying OB, not
trades. Results are retained in `technical_ablation_results.json`, the program
registry, and the cumulative exposure matrix.

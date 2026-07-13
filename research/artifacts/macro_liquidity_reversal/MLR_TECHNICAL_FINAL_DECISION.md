# MLR Technical Final Decision

Mode: `TECHNICAL_ONLY_ABLATION`  
History: `PREVIOUSLY_EXPOSED_WINDOW`  
Decision: `TECHNICAL_EDGE_NOT_FOUND`  
Full strategy: `BLOCKED_BY_UNCERTIFIED_MACRO_BIAS`

1. Total detected setups: 454 strategy-specific first-confirmed setups across 89 D1+H4 events. Frozen midpoint-reach diagnostics remain unchanged at M15 54, M5 85, M1 89, and hierarchy 12.
2. Filled trades: 306 under the medium-cost scenario.
3. No fills: 148; invalid-data rows: 0. Neither class is counted as a loss.
4. Wins: 52.
5. Losses: 246 ordinary stop-first outcomes.
6. Timeouts: 2.
7. Overall target-before-stop rate: 17.11% among 304 resolved filled trades; six adverse-first ambiguities are retained in the denominator.
8. OB+FVG target-before-stop rate: M15 23.08%, M5 20.83%, M1 14.29%.
9. FVG+breaker target-before-stop rate: M15 14.63%, M5 18.67%, M1 16.85%. Hierarchical: 15.38% on 13 fills.
10. Pooled strategy-observation average/total medium-cost net R: -0.567 / -173.458. This pool compares configurations and is not a simultaneous portfolio.
11. Worst strategy closed-equity drawdown: 52.724R for M1 FVG+breaker.
12. Bullish: 53 fills, -16.043R total, -0.303R average. Bearish: 253 fills, -157.415R total, -0.622R average.
13. Pooled year-attributed net R is negative in 2017-2020 and 2022-2026. Only 2021 is positive at +1.694R; this is not sufficient stability.
14. Low/medium/high pooled average net R: -0.537 / -0.567 / -0.665. Total net R: -164.179 / -173.458 / -203.425.
15. Medium cost has six ambiguous adverse-first rows totaling -6R. Even the invalid optimistic target-first upper bound improves results by only 14.902R, leaving pooled net R negative at -158.556R.
16. Every confluence strategy has lower average net R than its direction-matched next-open control. D1-only generic averages -0.060R; D1+H4 generic averages -0.143R.
17. CPCV applies to four strategies with 42, 49, 76, and 89 effective fills. All 15 CPCV test combinations are negative for each strategy.
18. Outer walk-forward positive folds: M15 breaker 0/2, M1 OB 0/2, M1 breaker 0/6, and M5 breaker 1/5. No primary rule survives the frozen outer gate.
19. ML is prohibited because the maximum effective filled-trade count is 89, below the 100-trade gate. No ML trial ran.
20. Candidate decision: `TECHNICAL_EDGE_NOT_FOUND`; candidate and champion are `NONE`. The authorized 1.5R diagnostic is also negative for all seven strategies and is `REJECT`.
21. Macro certification remains required because this technical ablation does not test the intended macro direction gate. Certified point-in-time eligible macro coverage remains zero.
22. Exact next permitted action: stop parameter search and obtain independently certified point-in-time macro release/receipt lineage plus Pepperstone NAS100 timezone, point, spread, contract, and feed metadata. No FTMO, Lucid, paper, broker, or live preparation is justified.

The independent audit status is `PASS_PROCESS_TECHNICAL_EDGE_NOT_FOUND`.

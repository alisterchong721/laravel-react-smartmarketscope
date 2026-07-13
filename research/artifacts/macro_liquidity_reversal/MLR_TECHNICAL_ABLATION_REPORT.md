# MLR Technical Ablation Report

Experiment: `MLR-TECH-ABL-001`

Status: `TECHNICAL_ONLY_ABLATION` on `PREVIOUSLY_EXPOSED_WINDOW`.

The only change is a diagnostic 1.5R target. The intended strategy target remains 2R and this result cannot be promoted automatically.

| Strategy | Filled | Wins | Avg net R | Total net R | CPCV positive splits | Outer positive folds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| M15_C1_OB_FVG | 13 | 4 | -0.347 | -4.516 | N/A | N/A |
| M5_C1_OB_FVG | 24 | 7 | -0.414 | -9.943 | N/A | N/A |
| M1_C1_OB_FVG | 49 | 7 | -0.728 | -35.658 | 0.000 | 0.000 |
| M15_C2_FVG_BREAKER | 42 | 9 | -0.517 | -21.697 | 0.000 | 0.000 |
| M5_C2_FVG_BREAKER | 76 | 17 | -0.523 | -39.772 | 0.000 | 0.200 |
| M1_C2_FVG_BREAKER | 89 | 21 | -0.547 | -48.654 | 0.000 | 0.000 |
| HIERARCHICAL_M15_M5_M1 | 13 | 3 | -0.539 | -7.012 | N/A | N/A |

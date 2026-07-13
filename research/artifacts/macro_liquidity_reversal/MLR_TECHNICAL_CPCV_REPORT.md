# MLR Technical CPCV Report

Status: `TECHNICAL_ONLY_ABLATION` on `PREVIOUSLY_EXPOSED_WINDOW`.

CPCV is descriptive for a fixed rule; it performs no candidate selection and is not independent proof of robustness.

| Strategy | Effective fills | Status | Splits | Positive splits | Median test R/trade | Lower quartile | Worst |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| HIERARCHICAL_M15_M5_M1 | 13 | INSUFFICIENT_FOR_RELIABLE_MODEL_SELECTION | 0 | N/A | N/A | N/A | N/A |
| M15_C1_OB_FVG | 13 | INSUFFICIENT_FOR_RELIABLE_MODEL_SELECTION | 0 | N/A | N/A | N/A | N/A |
| M15_C2_FVG_BREAKER | 42 | RULE_BASED_VALIDATION_PERMITTED | 15 | 0.0% | -0.592 | -0.712 | -0.835 |
| M1_C1_OB_FVG | 49 | RULE_BASED_VALIDATION_PERMITTED | 15 | 0.0% | -0.695 | -0.722 | -0.865 |
| M1_C2_FVG_BREAKER | 89 | RULE_BASED_VALIDATION_PERMITTED | 15 | 0.0% | -0.602 | -0.677 | -0.838 |
| M5_C1_OB_FVG | 24 | INSUFFICIENT_FOR_RELIABLE_MODEL_SELECTION | 0 | N/A | N/A | N/A | N/A |
| M5_C2_FVG_BREAKER | 76 | RULE_BASED_VALIDATION_PERMITTED | 15 | 0.0% | -0.507 | -0.580 | -0.617 |

ML is prohibited: the maximum effective filled-trade sample is below 100.

# MLR Technical Walk-Forward Report

Status: `TECHNICAL_ONLY_ABLATION` on `PREVIOUSLY_EXPOSED_WINDOW`.

The rule is frozen and not retrained. Full setup-to-exit intervals are purged from prior training context before each expanding chronological test fold.

| Strategy | Effective fills | Status | Folds | Positive folds | Median fold R/trade | Lower quartile | Worst |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| HIERARCHICAL_M15_M5_M1 | 13 | INSUFFICIENT_FOR_RELIABLE_MODEL_SELECTION | 0 | N/A | N/A | N/A | N/A |
| M15_C1_OB_FVG | 13 | INSUFFICIENT_FOR_RELIABLE_MODEL_SELECTION | 0 | N/A | N/A | N/A | N/A |
| M15_C2_FVG_BREAKER | 42 | RULE_BASED_VALIDATION_PERMITTED | 2 | 0.0% | -0.595 | -0.798 | -1.000 |
| M1_C1_OB_FVG | 49 | RULE_BASED_VALIDATION_PERMITTED | 2 | 0.0% | -0.732 | -0.866 | -1.000 |
| M1_C2_FVG_BREAKER | 89 | RULE_BASED_VALIDATION_PERMITTED | 6 | 0.0% | -0.499 | -0.527 | -1.000 |
| M5_C1_OB_FVG | 24 | INSUFFICIENT_FOR_RELIABLE_MODEL_SELECTION | 0 | N/A | N/A | N/A | N/A |
| M5_C2_FVG_BREAKER | 76 | RULE_BASED_VALIDATION_PERMITTED | 5 | 20.0% | -0.476 | -1.000 | -1.000 |

No outer fold is a pristine holdout; the historical pool was already exposed.

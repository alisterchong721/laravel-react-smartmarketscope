# Macro Data Coverage Report

Status: `PASS_INPUT_COVERAGE_RECONCILED_SCORING_COVERAGE_INSUFFICIENT`
Decision: `INSUFFICIENT_CATEGORY_COVERAGE`

The complete frozen input set contains 10,273 immutable eligible observation versions from `2000-02-11T17:00:00Z` through `2026-06-26T16:00:00Z`. The requested read-only daily history contains 9,676 calendar days from `2000-01-01` through `2026-06-28`. No unavailable observation or year was fabricated.

| Indicator | Observation versions | Valid calculated states | Insufficient-history states |
| --- | ---: | ---: | ---: |
| `US_CPI_ALL_ITEMS_SA` | 489 | 85 | 26 |
| `US_TOTAL_NONFARM_PAYROLLS` | 744 | 93 | 13 |
| `US_UNEMPLOYMENT_RATE` | 177 | 93 | 13 |
| `US_REAL_GDP` | 214 | 59 | 41 |
| `US_EFFECTIVE_FEDERAL_FUNDS_RATE` | 106 | 103 | 3 |
| `US_M2_MONEY_STOCK_SA` | 4,859 | 954 | 49 |
| `US_FED_TOTAL_ASSETS` | 1,228 | 1,215 | 13 |
| `US_RESERVE_BALANCES` | 1,228 | 1,215 | 13 |
| `US_TREASURY_GENERAL_ACCOUNT` | 1,228 | 1,215 | 13 |

| Category | Observation versions |
| --- | ---: |
| INFLATION | 489 |
| LABOUR | 921 |
| GROWTH | 214 |
| MONETARY_POLICY | 106 |
| LIQUIDITY | 8,543 |

Coverage capacity is one bundle for inflation, one for labour, one for growth, one for monetary policy, and four for liquidity. Frozen minima are respectively `2, 2, 2, 1, 1`. Inflation, labour, and growth therefore remain `PARTIAL` after warm-up; only policy and liquidity can be valid. Maximum valid-category count is two, below the overall minimum of three. All 9,676 daily final biases are consequently `UNKNOWN`; this is a sufficiency result, not a scoring error.

Missing candidate families include core/PCE/PPI inflation, claims/JOLTS/wages, consumption/industrial/manufacturing/services growth, policy target bounds/real-rate proxy, and RRP. Role 6 did not substitute current-revised or unofficial histories for them.

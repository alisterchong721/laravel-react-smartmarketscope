# Macro Regime Category Taxonomy

Status: `PROSPECTIVELY_FROZEN`
Version: `MACRO_REGIME_SCORING_V1`
Program: `SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001`

Exactly five categories have equal overall voting power: `INFLATION`, `LABOUR`,
`GROWTH`, `MONETARY_POLICY`, and `LIQUIDITY`. More source rows or indicators do
not increase a category's overall weight. Closely related indicators first form
one release-bundle vote; active valid bundles then receive equal weight inside
their category. No score decays.

| Category | Eligible bundles in V1 | Minimum valid bundles | Economic role |
| --- | --- | ---: | --- |
| INFLATION | `CPI_BUNDLE` | 2 | Valuation and Federal Reserve reaction pressure |
| LABOUR | `EMPLOYMENT_REPORT_BUNDLE` | 2 | Goldilocks cooling versus labour/recession stress |
| GROWTH | `GDP_BUNDLE` | 2 | Earnings support versus contraction risk |
| MONETARY_POLICY | `POLICY_RATE_BUNDLE` | 1 | Numerical tightening/easing conditions |
| LIQUIDITY | `MONEY_SUPPLY_BUNDLE`, `FED_BALANCE_SHEET_BUNDLE`, `BANK_RESERVES_BUNDLE`, `LIQUIDITY_DRAINS_BUNDLE` | 1 | System liquidity support or restriction |

The frozen evidence therefore cannot make inflation, labour, or growth `VALID`:
each has one eligible bundle and requires two. This expected coverage result is
not repaired with imputation, renormalization, reduced minima, or copied votes.
Policy and liquidity may become valid after their indicators become scorable,
but two valid categories are below the overall minimum of three, so the final
bias remains `UNKNOWN` under V1.

Category statuses are `VALID`, `PARTIAL`, `UNKNOWN`, `INSUFFICIENT_HISTORY`,
`DATA_GAP`, `CONFLICTING`, and `STRESS`. A category with some valid bundles but
fewer than its minimum is `PARTIAL`; zero valid bundles is `UNKNOWN` or
`INSUFFICIENT_HISTORY` when observations exist but no score is yet possible.
Stress and conflict flags are retained even when coverage is insufficient.

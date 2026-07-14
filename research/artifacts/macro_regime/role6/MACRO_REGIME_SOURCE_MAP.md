# Macro Regime Source Map

Status: `PROSPECTIVELY_FROZEN`

| Provider/source | Series | Internal indicator | Category | Bundle | Eligible versions |
| --- | --- | --- | --- | --- | ---: |
| ALFRED | `CPIAUCSL` | `US_CPI_ALL_ITEMS_SA` | INFLATION | CPI_BUNDLE | 489 |
| ALFRED | `PAYEMS` | `US_TOTAL_NONFARM_PAYROLLS` | LABOUR | EMPLOYMENT_REPORT_BUNDLE | 744 |
| ALFRED | `UNRATE` | `US_UNEMPLOYMENT_RATE` | LABOUR | EMPLOYMENT_REPORT_BUNDLE | 177 |
| ALFRED | `GDPC1` | `US_REAL_GDP` | GROWTH | GDP_BUNDLE | 214 |
| ALFRED | `FEDFUNDS` | `US_EFFECTIVE_FEDERAL_FUNDS_RATE` | MONETARY_POLICY | POLICY_RATE_BUNDLE | 106 |
| Federal Reserve H.6 | `H6/M2SL` | `US_M2_MONEY_STOCK_SA` | LIQUIDITY | MONEY_SUPPLY_BUNDLE | 4,859 |
| Federal Reserve H.4.1 | `H41/TOTAL_ASSETS` | `US_FED_TOTAL_ASSETS` | LIQUIDITY | FED_BALANCE_SHEET_BUNDLE | 1,228 |
| Federal Reserve H.4.1 | `H41/RESERVE_BALANCES` | `US_RESERVE_BALANCES` | LIQUIDITY | BANK_RESERVES_BUNDLE | 1,228 |
| Federal Reserve H.4.1 | `H41/TGA` | `US_TREASURY_GENERAL_ACCOUNT` | LIQUIDITY | LIQUIDITY_DRAINS_BUNDLE | 1,228 |

The three frozen input hashes are recorded in
`research/config/MACRO_REGIME_SCORING_CONFIG.yaml`. Every state retains trigger
and active observation identities, source run, raw artifact hash, effective
timestamp, registry hash, scoring-config hash, and code hash. No technical,
trade, PnL, news, sentiment, current-revised-only, protected, or final-holdout
source is in this map.

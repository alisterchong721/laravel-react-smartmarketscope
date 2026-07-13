# Macro Regime Official Source and Coverage Audit

## Output envelope

- `schema_version`: `1.0.0`
- `artifact_id`: `MACRO-REGIME-OFFICIAL-SOURCE-AUDIT-001`
- `program_id`: `SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001`
- `protocol_id`: `MACRO_REGIME_DAILY_H4_V1`
- `created_at_utc`: `2026-07-13T07:25:48Z`
- `created_by`: `Official Macro Source and Coverage Auditor`
- `status`: `PASS`
- `decision`: `PASS_BOUNDED_OFFICIAL_SOURCE_SET_FROZEN`
- `final_holdout_access_count`: `0`
- `protected_forward_access_count`: `0`
- `post_2026-06-28_market_outcome_access_count`: `0`
- `macro_observation_api_requests`: `0`
- `raw_macro_observations_downloaded`: `0`
- `experiment_trials_created`: `0`

## Decision

`[INTERPRETATION]` The official source plan is fit to proceed to bounded, immutable collection. Nineteen keyless official archive routes are approved across exactly five categories. The approved archive metadata indicates prospective coverage from 2000 for every category, including M2 for LIQUIDITY. This is a source-plan pass, not a data-coverage pass.

`[FACT]` Only the retained Role 2 ALFRED batch is verified observation evidence: 1,730 immutable versions, five series, 25 source runs/raw artifacts, four categories, reference coverage from 2017-08-01, and zero LIQUIDITY rows. Every archive row in the coverage outputs is labeled `PROSPECTIVE_METADATA_ONLY` and contributes no observation count.

`[LIMITATION]` Official archives have format, methodology, unit, benchmark, and correction changes. `APPROVED_FOR_BOUNDED_COLLECTION` authorizes a bounded collector with fail-closed parser validation; it does not certify any row before raw bytes, dates, versions, and hashes are captured and independently validated.

## Verified existing evidence

| Category | Series | Observation versions | Reference periods | Reference coverage | Decision |
| --- | --- | ---: | ---: | --- | --- |
| INFLATION | CPIAUCSL | 489 | 105 | 2017-08-01 to 2026-05-01 | APPROVED_EXISTING_EVIDENCE_ONLY |
| LABOUR | PAYEMS | 744 | 106 | 2017-08-01 to 2026-05-01 | APPROVED_EXISTING_EVIDENCE_ONLY |
| LABOUR | UNRATE | 177 | 105 | 2017-08-01 to 2026-05-01 | APPROVED_EXISTING_EVIDENCE_ONLY |
| GROWTH | GDPC1 | 214 | 34 | 2017-10-01 to 2026-01-01 | APPROVED_EXISTING_EVIDENCE_ONLY |
| MONETARY_POLICY | FEDFUNDS | 106 | 106 | 2017-08-01 to 2026-05-01 | APPROVED_EXISTING_EVIDENCE_ONLY |

Existing ALFRED values remain `VINTAGE_SAFE_WITH_DELAY`. Their date-level vintage availability is activated only by `J0_CONSERVATIVE_36H_FROM_AVAILABILITY_DATE_START_AMERICA_NEW_YORK`; it is not an exact historical release minute or first-receipt claim.

## Exact approved bounded collection set

| Category | Route | Series identity | Bundle | Expected reference coverage | Source |
| --- | --- | --- | --- | --- | --- |
| INFLATION | BLS_ARCHIVE_CPI_HEADLINE | CUSR0000SA0 / CPIAUCSL | CPI_BUNDLE | 2000-01-01 to 2026-05-01 | https://www.bls.gov/bls/news-release/cpi.htm |
| INFLATION | BLS_ARCHIVE_CPI_CORE | CUSR0000SA0L1E / CPILFESL | CPI_BUNDLE | 2000-01-01 to 2026-05-01 | https://www.bls.gov/bls/news-release/cpi.htm |
| INFLATION | BLS_ARCHIVE_PPI | WPU00000000 / PPIACO | PPI_BUNDLE | 2000-01-01 to 2026-05-01 | https://www.bls.gov/bls/news-release/ppi.htm |
| INFLATION | BEA_ARCHIVE_PCE_HEADLINE | DPCERG / PCEPI | PCE_BUNDLE | 2000-01-01 to 2026-05-01 | https://www.bea.gov/news/archive |
| INFLATION | BEA_ARCHIVE_PCE_CORE | DPCCRG / PCEPILFE | PCE_BUNDLE | 2000-01-01 to 2026-05-01 | https://www.bea.gov/news/archive |
| LABOUR | BLS_ARCHIVE_PAYEMS | CES0000000001 / PAYEMS | EMPLOYMENT_REPORT_BUNDLE | 2000-01-01 to 2026-05-01 | https://www.bls.gov/bls/news-release/empsit.htm |
| LABOUR | BLS_ARCHIVE_UNRATE | LNS14000000 / UNRATE | EMPLOYMENT_REPORT_BUNDLE | 2000-01-01 to 2026-05-01 | https://www.bls.gov/bls/news-release/empsit.htm |
| LABOUR | BLS_ARCHIVE_AHE | CES0500000008 | WAGE_PRESSURE_BUNDLE | 2000-01-01 to 2026-05-01 | https://www.bls.gov/bls/news-release/empsit.htm |
| LABOUR | BLS_ARCHIVE_CIVPART | LNS11300000 / CIVPART | EMPLOYMENT_REPORT_BUNDLE | 2000-01-01 to 2026-05-01 | https://www.bls.gov/bls/news-release/empsit.htm |
| LABOUR | BLS_ARCHIVE_JOLTS | JTS000000000000000JOL / JTSJOL | JOLTS_BUNDLE | 2000-12-01 to 2026-04-01 | https://www.bls.gov/bls/news-release/jolts.htm |
| GROWTH | BEA_ARCHIVE_GDPC1 | A191RX / GDPC1 | GDP_BUNDLE | 2000-01-01 to 2026-01-01 | https://www.bea.gov/news/archive |
| GROWTH | CENSUS_ARCHIVE_RSAFS | RSAFS | CONSUMPTION_BUNDLE | 2000-01-01 to 2026-05-01 | https://www.census.gov/retail/marts/historic_releases.html |
| GROWTH | FED_G17_REALTIME_INDPRO | INDPRO | INDUSTRIAL_BUNDLE | 2000-01-01 to 2026-05-01 | https://www.federalreserve.gov/releases/g17/download.htm |
| GROWTH | CENSUS_ARCHIVE_DGORDER | DGORDER | MANUFACTURING_BUNDLE | 2000-01-01 to 2026-05-01 | https://www.census.gov/manufacturing/m3/data/index.html |
| MONETARY_POLICY | FED_H15_ARCHIVE_EFFR | H15/RIFSPFF_N.D / FEDFUNDS | POLICY_RATE_BUNDLE | 2000-01-01 to 2026-06-26 | https://www.federalreserve.gov/releases/h15/20000228/h15.htm |
| LIQUIDITY | FED_H6_ARCHIVE_M2 | H6/M2SL / M2SL | MONEY_SUPPLY_BUNDLE | 2000-01-01 to 2026-05-01 | https://www.federalreserve.gov/releases/h6/default.htm |
| LIQUIDITY | FED_H41_ARCHIVE_TOTAL_ASSETS | H41/H41/RESPPA_N.WW / WALCL | FED_BALANCE_SHEET_BUNDLE | 2002-12-18 to 2026-06-24 | https://www.federalreserve.gov/releases/h41/default.htm |
| LIQUIDITY | FED_H41_ARCHIVE_RESERVE_BALANCES | WRESBAL / H41_TABLE_1_RESERVE_BALANCES | BANK_RESERVES_BUNDLE | 2002-12-18 to 2026-06-24 | https://www.federalreserve.gov/releases/h41/default.htm |
| LIQUIDITY | FED_H41_ARCHIVE_TGA | WTREGEN / H41_TREASURY_GENERAL_ACCOUNT_ROW | LIQUIDITY_DRAINS_BUNDLE | 2002-12-18 to 2026-06-24 | https://www.federalreserve.gov/releases/h41/default.htm |

Collection priority is deterministic: (1) H.6 M2 to establish LIQUIDITY from 2000; (2) H.4.1 total assets, reserve balances, and TGA from the 2002 format boundary; (3) pre-2017 gaps for the five existing ALFRED concepts; (4) missing core CPI/PCE/PPI, wages, participation, JOLTS, retail sales, industrial production, and durable goods. Overlapping official archive and retained ALFRED routes reconcile versions but never cast independent category votes.

## Source-decision census

| Frozen source decision | Route count |
| --- | ---: |
| APPROVED_EXISTING_EVIDENCE_ONLY | 5 |
| APPROVED_FOR_BOUNDED_COLLECTION | 19 |
| AVAILABILITY_OR_VERSION_UNRESOLVED | 2 |
| CURRENT_REVISED_HISTORY_ONLY | 1 |
| REJECTED | 3 |
| REQUIRES_KEY_OR_LICENSE_REVIEW | 4 |

## Category coverage

| Category | Verified versions | Approved routes | Approved bundles | Prospective start | Coverage class | Unresolved gap |
| --- | ---: | ---: | ---: | --- | --- | --- |
| INFLATION | 489 | 5 | 3 | 2000-01-01 | VERIFIED_EXISTING_PLUS_PROSPECTIVE_METADATA_ONLY | NONE_AFTER_BOUNDED_ARCHIVE_COLLECTION; VERIFIED_ROWS_STILL_ONLY_HEADLINE_CPI_2017_PLUS |
| LABOUR | 921 | 5 | 3 | 2000-01-01 | VERIFIED_EXISTING_PLUS_PROSPECTIVE_METADATA_ONLY | CLAIMS_BUNDLE_UNRESOLVED_PENDING_DOL_ARCHIVE_OR_FREE_ALFRED_KEY_REVIEW |
| GROWTH | 214 | 4 | 4 | 2000-01-01 | VERIFIED_EXISTING_PLUS_PROSPECTIVE_METADATA_ONLY | SERVICES_BUNDLE_UNPOPULATED; PRIVATE_ISM_AND_PMI_NOT_APPROVED |
| MONETARY_POLICY | 106 | 1 | 1 | 2000-01-01 | VERIFIED_EXISTING_PLUS_PROSPECTIVE_METADATA_ONLY | TARGET_RANGE_OPTIONAL_AND_KEY_GATED; H15_EFFR_IS_APPROVED_MINIMUM_PATH |
| LIQUIDITY | 0 | 4 | 4 | 2000-01-01 | PROSPECTIVE_METADATA_ONLY_NO_VERIFIED_OBSERVATIONS | ZERO_VERIFIED_ROWS; RRP_VINTAGES_NOT_APPROVED; H6_AND_H41_ARCHIVES_ARE_PROSPECTIVE_ONLY |

`MACRO_REGIME_COVERAGE_BY_YEAR.csv` contains exactly 135 data rows: every year 2000-2026 crossed with exactly five categories. It carries Role 2 counts by both reference year and availability year. Prospective archive coverage is expressed only as route/indicator/bundle presence; no prospective row count is guessed.

## Vintage, availability, and revision decisions

- Dated BLS, BEA, Census, H.15, H.6, H.4.1, and G.17 release files are eligible collection inputs because the raw release copy is tied to a publication date and later releases can remain separate versions.
- Current BLS/BEA/Census/Fed time-series downloads remain useful for reconciliation only; they must not replace archived values or be called point-in-time history.
- FRED/ALFRED `series/vintagedates` and `series/observations` are suitable vintage mechanisms, but new calls require a free registered API key and source-specific terms review. The key must never enter configuration, logs, artifacts, or source control.
- The public NY Fed reverse-repo historical search was not shown to preserve immutable prior correction versions. It is `CURRENT_REVISED_HISTORY_ONLY`. The ALFRED RRP alternative remains key-gated.
- DOL current claims releases show advance and revised values, but an exhaustive stable dated archive traversal for 2000-2026 was not verified. ICSA/CCSA remain unresolved rather than assumed safe.
- ISM and private PMI families are not official government sources and were not accessed. They are rejected under this official-only program. No qualifying national official services diffusion series was identified.

## Duplicate-vote controls

- Headline and core CPI share `CPI_BUNDLE`; headline and core PCE share `PCE_BUNDLE`.
- PAYEMS, UNRATE, and participation are components of `EMPLOYMENT_REPORT_BUNDLE`; wages enter `WAGE_PRESSURE_BUNDLE`; ICSA/CCSA would share `CLAIMS_BUNDLE` if later approved.
- GDP, retail sales, industrial production, and durable goods map to distinct frozen growth bundles. Advance versus revised releases are versions, not separate votes.
- Effective rate and target bounds share `POLICY_RATE_BUNDLE`.
- H.4.1 total assets, reserve balances, and TGA map to their named liquidity bundles; multiple revisions or current-download aliases do not create extra votes.
- Category aggregation later remains equal-bundle and equal-category. Observation counts and number of source routes never become weights.

## Access and usage constraints

- Official archive downloads are keyless, but collectors must respect agency terms, request pacing, robots directives, and source citation. This audit does not grant redistribution rights.
- BEA labels its archive research-only and warns that data may be superseded. That property is useful for vintages but requires the exact archived table, not the current API table.
- FRED/ALFRED and BEA APIs require registered keys. No key was requested, read, written, or inferred in this role.
- Preserve raw response bodies/files, HTTP metadata, source URLs, retrieval times, release dates, units, seasonal-adjustment state, parser/config/code hashes, and every later correction as an immutable version.
- Current/revised download endpoints may be used only as comparison evidence. A mismatch creates a new version or an error; it never overwrites an archive row.

## Documentation interaction ledger

- Evidence access completed: `2026-07-13T07:25:48Z`.
- Official-domain search queries: `29`.
- Official page-open attempts: `12` (`11` successful, `1` safe failure).
- Total documentation interactions: `41`; cap: `60`.
- Observation API requests, bulk requests, and raw macro downloads: `0 / 0 / 0`.
- The single safe failure was an in-tool NY Fed terms URL rejection; no bypass or retry occurred. The official data-hub notice that terms apply is retained as the constraint.

Post-cutoff official documentation metadata was used only to verify current source access and archive contracts. No post-2026-06-28 NAS100 price, technical outcome, macro value, PnL, protected path, or final holdout was accessed or used.

## Official evidence URLs

| Evidence ID | Official URL | Audited fact |
| --- | --- | --- |
| FRED_VINTAGE_DATES_DOC | https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html | The endpoint reports dates when values were revised or newly released and requires an API key. |
| FRED_OBSERVATIONS_DOC | https://fred.stlouisfed.org/docs/api/fred/series_observations.html | The endpoint supports real-time periods and explicit vintage dates; the API key is required. |
| BLS_API_DOC | https://www.bls.gov/developers/ | BLS API v1 is keyless and limited; v2 registration increases limits, but API history is not a revision-vintage ledger. |
| BLS_EMPLOYMENT_ARCHIVE | https://www.bls.gov/bls/news-release/empsit.htm | Dated archived Employment Situation releases are listed back through the requested 2000 start and retain superseded values. |
| BLS_CPI_ARCHIVE | https://www.bls.gov/bls/news-release/cpi.htm | Dated archived CPI releases are listed back through the requested 2000 start and warn that later releases may revise data. |
| BLS_PPI_ARCHIVE | https://www.bls.gov/bls/news-release/ppi.htm | Dated archived PPI releases are listed back through the requested 2000 start. |
| BLS_JOLTS_ARCHIVE | https://www.bls.gov/bls/news-release/jolts.htm | Dated archived JOLTS releases are available; the series begins near the end of 2000. |
| BEA_NEWS_ARCHIVE | https://www.bea.gov/news/archive | BEA provides a research archive of dated GDP and Personal Income and Outlays releases; data may be superseded. |
| BEA_API_GUIDE | https://apps.bea.gov/api/_pdf/bea_web_service_api_user_guide.pdf | The BEA API requires a registered UserID and exposes current published datasets, not a historical revision ledger. |
| CENSUS_RETAIL_ARCHIVE | https://www.census.gov/retail/marts/historic_releases.html | The archive explicitly retains old releases that do not contain the most current data and covers the requested period. |
| CENSUS_DURABLE_ARCHIVE | https://www.census.gov/manufacturing/m3/data/index.html | Census lists historical advance durable-goods and full M3 releases plus revision information. |
| FED_G17_DOWNLOAD | https://www.federalreserve.gov/releases/g17/download.htm | The Board publishes original and subsequent normal-window revisions for industrial production plus dated release archives. |
| FED_G17_ARCHIVE | https://www.federalreserve.gov/releases/g17/default.htm | Monthly HTML, PDF, and ASCII G.17 releases cover the requested 2000 start. |
| FED_H15_ARCHIVE | https://www.federalreserve.gov/releases/h15/20000228/h15.htm | A dated 2000 H.15 release preserves daily effective federal funds observations as published. |
| FED_H41_ARCHIVE | https://www.federalreserve.gov/releases/h41/default.htm | Dated H.4.1 balance-sheet release pages and files are available, including the 2002 format transition. |
| FED_H41_TOTAL_ASSETS_ID | https://www.federalreserve.gov/datadownload/Preview.aspx?pi=400&preview=H41%2FH41%2FRESPPA_N.WW&rel=H41 | RESPPA_N.WW is the stable DDP identity for H.4.1 total assets, in millions of dollars, weekly Wednesday level. |
| FED_H6_ARCHIVE | https://www.federalreserve.gov/releases/h6/default.htm | The H.6 release-date index exposes dated releases back through 2000; archived release copies preserve as-published M2 tables. |
| NY_FED_DATA_HUB | https://www.newyorkfed.org/markets/data-hub | The public data hub exposes current and historical-search reference-rate and repo-operation data but does not document immutable prior API versions. |
| DOL_CURRENT_CLAIMS_RELEASE | https://www.dol.gov/ui/data.pdf | The current weekly release preserves advance and revised prior-week values, but this audit did not verify an exhaustive stable 2000-2026 archive index. |

## Reproducibility and hashes

- Audit config SHA-256: `be02e79bca74014a2686bbe10ea4468f650d3b3d6809651717f4d98066e943cb`
- Generator code SHA-256: `93bc4147105fcbb19f560652fff95047664d87b75fce66593447c1c06d535ddc`
- Role 2 eligible observations SHA-256: `9240a65211b8efc2954adace8ef8a17150bc370ad8677b7db4295d2f5aa38f31`
- Coverage-by-series SHA-256: `f3953b70536b0ba9a2bb56fcb30ba9441389ae0122744baab695f7133faff730`
- Coverage-by-year SHA-256: `8fa0a5d9985a64e780eb0e8a9f28d15ac07d56692ae7aed719a12facf3a58464`
- Coverage-by-category SHA-256: `4b0b3721a57ee7b867189d4c369a6547ac06fff38e47102335f53b7664260228`

| Repository input | Path | SHA-256 |
| --- | --- | --- |
| directive | /Users/alisterchong/.codex/attachments/7df06f50-f36c-4f67-ba5c-f70071c426f6/pasted-text-1.txt | 13abac33865b02502cdea7dc4ef4bde27d15127cda764d4965df79db11611601 |
| salvage_report | ALFRED_MACRO_REGIME_SALVAGE_AUDIT.md | ed2c9765498d4b28e4683a5202010ac794d15eb1442f7dacc17fa646d4f66bc7 |
| series_reclassification | ALFRED_SERIES_RECLASSIFICATION.csv | 84aa0bbcb8d85b6eb72ce052c74ae9777518c5764547f58fabeb0f00a2809307 |
| eligible_observations | ALFRED_REGIME_ELIGIBLE_OBSERVATIONS.csv | 9240a65211b8efc2954adace8ef8a17150bc370ad8677b7db4295d2f5aa38f31 |
| ineligible_observations | ALFRED_REGIME_INELIGIBLE_OBSERVATIONS.csv | 328c71c629454a532244f4599b6ec8feaa78c67d75a946c0efc81fe0d60dd477 |
| registry_validation | REGISTRY_CHRONOLOGY_VALIDATION.json | 8cf9c92d5ac74a07e040de59eb7ce347ffcd593f4a835265fc7c9ff584e1b390 |
| experiment_registry_jsonl | EXPERIMENT_REGISTRY.jsonl | b7cb999912aed3108d12fcdb62c079d3c51610214a419a3b5fc72ac19c65d044 |
| experiment_registry_csv | EXPERIMENT_REGISTRY.csv | eaa310a101f02fbd0682a1864a77665f1ef15338c809baedfffff198a383d57a |
| governance | config/governance.default.yaml | aa8e1f35491550d66e1e210189cc9f4e383a83d088513fb5bb3176cab5a9bb9f |

Reproduction command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m smartmarketscope_quant.macro_regime.source_audit --repo-root .
```

The validator rehashes every declared repository input, re-reads all 1,730 Role 2 rows, proves five exact categories, enforces the six allowed decisions, rejects post-cutoff dates/non-official evidence URLs/fabricated prospective counts, and regenerates all four outputs byte-identically.

## Failure codes and limitations

Non-terminal audit warnings carried forward:

- `PROSPECTIVE_COVERAGE_NOT_OBSERVATION_EVIDENCE`
- `LIQUIDITY_VERIFIED_OBSERVATION_COUNT_ZERO`
- `CLAIMS_ARCHIVE_AVAILABILITY_OR_VERSION_UNRESOLVED`
- `ALFRED_FREE_API_KEY_REVIEW_REQUIRED_FOR_OPTIONAL_FALLBACKS`
- `CURRENT_REVISED_HISTORY_NOT_VINTAGE_SAFE`
- `OFFICIAL_SERVICES_DIFFUSION_SOURCE_NOT_IDENTIFIED`
- `REGISTRY_CHRONOLOGY_UNRESOLVED_FINAL_CHAMPION_VETO`

The audit does not claim that the requested 2000-2026 dataset exists yet. Actual coverage, row counts, missing releases, hashes, and parser fitness must be measured during bounded collection. Archive formats and methodology breaks may reduce the prospective plan.

## Next permitted action

Proceed sequentially to Role 4, Smart MarketScope Macro Database Architect. Bind the 1,730 verified rows and this frozen 34-route source decision into an immutable, append-only schema and migration plan. Role 4 must not collect observations, score regimes, join technical setups, inspect PnL, or start later roles. Role 5 may later collect only the 19 approved bounded routes, beginning with H.6 M2 and H.4.1 liquidity evidence, under request pacing, checkpoints, raw-body hashes, and fail-closed version semantics.

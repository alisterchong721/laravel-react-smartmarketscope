# ALFRED Macro-Regime Salvage Audit

## Output envelope

- `schema_version`: `1.0.0`
- `artifact_id`: `ALFRED-MACRO-REGIME-SALVAGE-AUDIT-001`
- `program_id`: `SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001`
- `protocol_id`: `MACRO_REGIME_DAILY_H4_V1`
- `batch_id`: `QRP2-ALFRED-20260713T070000Z`
- `created_at_utc`: `2026-07-13T07:16:38Z`
- `created_by`: `Existing Macro Evidence and ALFRED Salvage Auditor`
- `status`: `PASS_SALVAGED_WITH_CONSERVATIVE_DELAY`
- `decision`: `PASS_1730_VINTAGE_SAFE_WITH_DELAY`
- `final_holdout_access_count`: `0`
- `protected_forward_access_count`: `0`
- `network_requests_created_by_role_2`: `0`
- `experiment_trials_created_by_role_2`: `0`

## Decision

`[INTERPRETATION]` All 1,730 immutable observation versions in the retained
ALFRED batch are eligible for the new daily/H4 macro-regime protocol only
under `VINTAGE_SAFE_WITH_DELAY`. Zero rows are ineligible under this protocol.
This reverses none of the old Program 2 facts: every original row remains
`NOT_PIT_SAFE` with null old availability for the superseded intraday
release-surprise contract. No old row, source run, raw payload, validator,
configuration, or classification was modified.

`[FACT]` Each normalized row links to an ALFRED `output_type=3` historical
vintage, its date-level vintage appears in the retained series release-date
payload, all later versions remain distinct in a contiguous supersedes chain,
and the source-run raw hash, collector hash, configuration hash, normalized
payload hash, and batch hash are retained. These facts satisfy the new
protocol's date-level vintage and immutable-lineage requirements.

`[LIMITATION]` The date is not an authoritative release minute or proof of
historical first receipt. Therefore no row is classified as
`VINTAGE_SAFE_FOR_DAILY_REGIME` without delay. Consensus, surprise,
forecast-as-published, previous-as-published, and exact same-minute reaction
remain unavailable and were neither required nor reconstructed.

## Availability and J0 semantics

- `availability_date` is the ALFRED vintage date carried in the retained
  `output_type=3` column and cross-checked against the retained provider
  release-date response for the same series.
- Its calendar timezone is retained as `America/New_York`. It is a date,
  not an invented wall-clock timestamp.
- For deterministic arithmetic only, J0 starts at `00:00:00` on that source
  calendar date, applies exactly 36 hours, and then records date-aware UTC and
  `Asia/Kuala_Lumpur` timestamps.
- Rule identifier: `J0_CONSERVATIVE_36H_FROM_AVAILABILITY_DATE_START_AMERICA_NEW_YORK`.
- J1 and J2 require a later source-calendar/technical-join role and were not
  materialized or compared here.

## Requested versus actual coverage

| Measure | Requested | Actual retained evidence |
| --- | --- | --- |
| Reference/history range | `2000-01-01` through `2026-06-28` | `2017-08-01` through `2026-05-01` |
| Vintage/availability range | Discover | `2017-09-01` through `2026-06-25` |
| Series | Candidate registry to be audited | `5` frozen series |
| Source runs / raw artifacts | Reuse safe evidence | `25` / `25` |
| Observation versions | Reuse safe evidence | `1730` |
| Eligible / ineligible | Determine exactly | `1730` / `0` |

No observation before the actual retained range was fabricated. The batch
contains no LIQUIDITY series, so it cannot by itself meet the five-category
program coverage requirement. It also does not supply the requested pre-2017
warm-up history.

## Series reclassification

| Series | Category | Reference periods | First prints | Revisions | Rows | Classification |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `CPIAUCSL` | `INFLATION` | 105 | 105 | 384 | 489 | `VINTAGE_SAFE_WITH_DELAY` |
| `PAYEMS` | `LABOUR` | 106 | 106 | 638 | 744 | `VINTAGE_SAFE_WITH_DELAY` |
| `UNRATE` | `LABOUR` | 105 | 105 | 72 | 177 | `VINTAGE_SAFE_WITH_DELAY` |
| `GDPC1` | `GROWTH` | 34 | 34 | 180 | 214 | `VINTAGE_SAFE_WITH_DELAY` |
| `FEDFUNDS` | `MONETARY_POLICY` | 106 | 106 | 0 | 106 | `VINTAGE_SAFE_WITH_DELAY` |

Category observation-version counts:

- `INFLATION`: 489
- `LABOUR`: 921
- `GROWTH`: 214
- `MONETARY_POLICY`: 106
- `LIQUIDITY`: 0

Source-run counts are five per series and five per source type:

- `INITIAL_RELEASE_OBSERVATIONS`: 5
- `NEW_AND_REVISED_OBSERVATIONS`: 5
- `RELEASE_DATES`: 5
- `SERIES_METADATA`: 5
- `SERIES_RELEASE`: 5

## Integrity and reproducibility

| Evidence | SHA-256 |
| --- | --- |
| Frozen ALFRED config | `667e69c1f229ac0b202284537b34e25e656b5c292d1556018173482b8d161799` |
| Original collector code | `6c58a0a96993196cf6606fc7132a5caac498047595f473a0735c88de1ac45f5d` |
| Original PIT manifest | `115fc7b12bc01a54a8645183b6da77aaaa8180069e1799c41aab04c535bd6833` |
| Original ALFRED bundle | `6a33f296268652d6402cc09d300278545b47d309d78e27f7d4564e71ca366d57` |
| Original provenance manifest | `2b8c414748bf3ddb5134cf75ef3a50aca61a1bff88d3b29a2b5976513ed677cf` |
| Original validation result | `45b112ee0450880baecd96f42a449748011ba4e31b88ace0257d5f812a5c56fa` |
| Original validation recheck | `45b112ee0450880baecd96f42a449748011ba4e31b88ace0257d5f812a5c56fa` |
| Role 2 salvage code | `b52078e9d8a36da7e7fe75153d857d98bd501ec4fdc731bf5aaa581864abf5c0` |
| Series reclassification CSV | `84aa0bbcb8d85b6eb72ce052c74ae9777518c5764547f58fabeb0f00a2809307` |
| Eligible observations CSV | `9240a65211b8efc2954adace8ef8a17150bc370ad8677b7db4295d2f5aa38f31` |
| Ineligible observations CSV | `328c71c629454a532244f4599b6ec8feaa78c67d75a946c0efc81fe0d60dd477` |

The provenance manifest carries the individual identity, byte length,
source-run ID, and SHA-256 for all 25 raw payloads. The audit independently
rehashed every payload, matched it to its source run, reconstructed every
normalized provider payload hash, cross-checked all initial values, and
proved mutually exclusive/exhaustive output partitioning.

Reproduction command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m smartmarketscope_quant.macro_regime.alfred_salvage --repo-root . --created-at-utc 2026-07-13T07:16:38Z
```

Verification commands executed for this role:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m unittest research.tests.test_macro_regime_alfred_salvage -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m smartmarketscope_quant.macro_regime.alfred_salvage --repo-root . --created-at-utc 2026-07-13T07:16:38Z --validate-only
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m unittest discover -s research/tests -v
```

All three commands exit `0`; the integrated suite passes 190 tests. Focused tests include positive, deterministic
repeat, raw-tamper, missing-availability, current-vintage, unresolved-source,
revision-chain, DST, and exhaustive-partition assertions.

## Limitations and exclusions

- The source covers four of five required categories; LIQUIDITY is absent.
- Actual vintage-safe coverage begins in 2017, not the requested 2000.
- Headline CPI alone is not the complete frozen INFLATION coverage target.
- PAYEMS and UNRATE share one release family and must later be bundled before
  category voting; row counts are not category weights.
- FEDFUNDS is a monthly effective-rate series, not a complete target-range or
  meeting-event policy ledger.
- No indicator transformations, release bundles, category scores, regime
  score, technical join, PnL, graph, source collection, or database write
  occurred in this role.
- Third-party series rights remain local-research-only under the preserved
  provenance warning; this audit does not approve redistribution.
- Registry chronology remains `REGISTRY_CHRONOLOGY_UNRESOLVED`; this does not
  block read-only data construction but remains a final-champion veto.

Failure codes: none for the retained Role 2 partition. Missing requested
coverage is carried forward as `INSUFFICIENT_CATEGORY_COVERAGE_NOT_YET_TESTED`,
not converted into an observation-level failure.

## Next permitted action

Run Role 3, Official Macro Source and Coverage Auditor, sequentially. It may
audit official keyless/vintage-safe coverage needed to extend history and
supply missing categories, especially LIQUIDITY. It must reuse these 1,730
rows, must not recollect them merely because the old surprise protocol
rejected them, and must not begin database writes, scoring, technical joins,
economic backtests, or champion claims.

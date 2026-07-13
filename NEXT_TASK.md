# Next Task

## Macro Regime Program — Role 3 Official Source and Coverage Audit

Program: `SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001`

Current status: `REGISTRY_CHRONOLOGY_UNRESOLVED` with append-only disclosure.
This caveat permits read-only macro dataset construction but prohibits any final
champion claim.

Role 2 is complete with `PASS_1730_VINTAGE_SAFE_WITH_DELAY`: all 1,730 retained
ALFRED observation versions are eligible under J0 delayed daily-regime semantics,
with zero ineligible rows. Existing coverage spans four categories and lacks
LIQUIDITY and pre-2017 warm-up history.

Run exactly one next sequential role: Official Macro Source and Coverage Auditor.
Audit responsible official/public vintage-safe sources for the requested
`2000-01-01` through `2026-06-28` period, using the frozen source hierarchy and
candidate families in the active program directive. Reuse the existing 1,730
ALFRED rows and do not recollect them merely because the superseded surprise
protocol rejected them.

Required Role 3 outputs:

- `MACRO_REGIME_SOURCE_AUDIT.md`
- `MACRO_REGIME_COVERAGE_BY_YEAR.csv`
- `MACRO_REGIME_COVERAGE_BY_SERIES.csv`
- `MACRO_REGIME_COVERAGE_BY_CATEGORY.csv`

For every candidate source/series, record official ownership, endpoint or file
family, authentication requirement, access/usage constraints, vintage/version
semantics, availability-date evidence, units/frequency, expected range, missing
periods, revision behavior, raw-snapshot feasibility, category/release-bundle
mapping, and one of:

- `APPROVED_FOR_BOUNDED_COLLECTION`
- `APPROVED_EXISTING_EVIDENCE_ONLY`
- `REQUIRES_KEY_OR_LICENSE_REVIEW`
- `CURRENT_REVISED_HISTORY_ONLY`
- `AVAILABILITY_OR_VERSION_UNRESOLVED`
- `REJECTED`

Prioritize the missing LIQUIDITY category and the pre-2017 warm-up gap, then
audit broader inflation, labour, growth, and monetary-policy candidates without
allowing duplicate releases to gain extra category voting power. Prefer official
downloadable files or documented keyless/public endpoints. A free formal API may
be used when appropriate; a paid provider is not required.

Do not restart public Trading Economics scraping, bypass access controls, perform
bulk collection, design or migrate the database, score macro states, align
technical setups, inspect PnL, or start Roles 4–11 during this role. Small
read-only metadata/coverage probes are permitted when necessary and must be
counted and preserved as audit evidence. End with an explicit approved source
set, uncovered gaps, collection constraints, and the exact next permitted action.

## Macro Liquidity Reversal Gate

The authorized technical economic continuation is terminal with
`TECHNICAL_EDGE_NOT_FOUND`. Do not run further parameter search or ML. The next
permitted MLR action is external evidence onboarding and independent
certification only: exact point-in-time macro release/receipt lineage and
Pepperstone NAS100 instrument/feed metadata.

Do not continue the full MLR strategy. First certify immutable macro source-run
and observation records with exact historical release/receipt and as-published
values, then obtain Pepperstone NAS100 source-timezone and symbol/spread metadata.
The exact requirements are in `MLR_NEXT_TASK.md`. Do not reconstruct unavailable
timestamps or access post-2026-06-28 data for tuning.

Status: `BLOCKED_EXTERNAL_POINT_IN_TIME_EVIDENCE`

## Task ID

`PROGRAM2-PIT-RELEASE-LINEAGE-003`

## Current Block

The point-in-time contract and a real bounded ALFRED bundle pass validation. The
bundle has 25 source runs and 1,730 initial/revision rows, but eligible count is
zero. ALFRED supplies date-level vintage lineage, not authoritative exact source
wall-clock, historical first-receipt, consensus forecast, or
previous-as-published lineage. Historical signed sentiment still lacks
contemporaneous receipt and model/prompt/schema hashes. Cycle 3 cannot be
preregistered from excluded rows or retrospectively rescored articles.

## Next Permitted Work

1. Join the frozen ALFRED series/reference periods to authoritative exact source
   release clocks. Preserve source timezone, DST-aware UTC/Malaysia conversion,
   schedule revisions, source URLs, and payload/code/config hashes.
2. Onboard a licensed point-in-time forecast source for surprise features,
   retaining forecast and previous exactly as published. If unavailable, keep
   the surprise family blocked rather than substituting later values.
3. Start or verify passive protected news collection that freezes `published_at`,
   first receipt, revisions/retractions, content hash, and exact as-received
   sentiment model/prompt/schema hashes. Do not inspect it for outcomes.
4. Pass a bundle with nonzero eligible rows through the existing independent
   validator and demonstrate coverage sufficient for both required families.
5. After enough evidence exists, prospectively generate at least five candidate
   proposals, freeze approximately 70/30 exploit/explore allocation, and create
   Cycle 3 preregistrations before empirical code or outcome access.

## Invariants

- Do not fabricate historical first-received or exact release times.
- Do not use current-vintage revisable macro data as historical first prints.
- Do not rescore historical news and call it as-received.
- Do not open protected-forward data for feature design or tuning.
- Do not append an experiment registry event until a complete preregistration is
  hash-locked.
- Do not build/deploy paper infrastructure or connect a broker without a frozen
  provisional champion and separate authorization.

## Unblock Evidence

- Real provider bundle validator status `PASS` with nonzero eligible rows.
- Eligible row counts and coverage sufficient for both required families.
- Frozen source/feature manifests and leakage audit with no critical veto.
- A mature protected forward evaluation window reserved for one frozen promotion
  decision.

Until those facts exist, `BLOCKED_BEFORE_CYCLE_3_PREREGISTRATION` is the only
defensible state.

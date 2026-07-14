# Next Task

## Macro Regime Program — Role 7 Point-in-Time and Availability Validation

Program: `SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001`

Role 6 is complete. The hash-locked deterministic scoring engine reconciles all
10,273 eligible observations and materializes 5,216 indicator states, 5,111
bundle states, 1,840 category states, 1,718 event-time snapshots, 9,676 daily
as-of rows, 51,361 active-input rows, and 10,273 event-ledger rows. Focused tests
pass 9/9 and the full research suite passes 232/232.

The frozen evidence supports at most two valid categories: policy and liquidity.
Inflation, labour, and growth each have one eligible bundle against a minimum of
two. The engine therefore returns `UNKNOWN` on all daily rows rather than
imputing, renormalizing, relaxing coverage, or carrying an invalid vote.

Run exactly one next sequential role: Point-in-Time and Availability Validation
Engineer.

1. Independently rehash the three frozen inputs, all Role 6 registries/config,
   scoring code, manifest, and every named output.
2. Prove that every observation version is excluded before its effective time,
   later revisions replace only their own reference version, and no current-
   revised or future vintage enters an earlier indicator state.
3. Independently recompute one-release, three-release, six-release, year-over-
   year, prior-only median/MAD, zero-MAD fallback, percentile, score-boundary,
   no-decay, and unscorable-replacement examples across all source families.
4. Verify exact atomic same-effective-time batching, observation-to-indicator-to-
   bundle-to-category-to-snapshot lineage, 10,273 ledger-row parity across CSV,
   JSONL and Parquet, and daily as-of nonanticipation.
5. Verify date-aware `America/New_York`, UTC, and `Asia/Kuala_Lumpur` availability
   semantics and assess J0 readiness. J1/J2 source-trading-day rules may be
   specified for later sensitivity but must not be selected from PnL.
6. Confirm independently that the frozen minimum-bundle and minimum-category
   rules imply `INSUFFICIENT_CATEGORY_COVERAGE`, all 9,676 daily biases are
   `UNKNOWN`, and no technical alignment is permitted under that state.
7. Produce a point-in-time audit, availability audit, lineage/error census,
   deterministic validation artifact, exact test evidence, limitations, and the
   next permitted action. Preserve failures rather than repairing Role 6 in place.

Do not join technical setups, inspect trade outcomes or PnL, run an economic
backtest, tune transformations/thresholds/weights, access protected/final-
holdout paths, add public write routes, deploy, connect a broker, or start Roles
8–11. A material Role 6 defect must fail closed and return to a prospective
scoring amendment; it must not be silently corrected during independent
validation.

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

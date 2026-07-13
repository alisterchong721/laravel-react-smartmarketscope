# Next Task

## Macro Regime Program — Role 4 Smart MarketScope Macro Database Architecture

Program: `SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001`

Current status: `REGISTRY_CHRONOLOGY_UNRESOLVED` with append-only disclosure.
This caveat permits read-only macro dataset construction but prohibits any final
champion claim.

Roles 2 and 3 are complete. The only verified macro evidence is the retained
1,730-version ALFRED batch under conservative J0 delay semantics. Role 3 froze
34 source decisions, including 19 keyless official routes approved only for
future bounded collection. LIQUIDITY still has zero verified observations and
all pre-2017 coverage remains prospective.

Run exactly one next sequential role: Smart MarketScope Macro Database Architect.
Inspect the sibling Laravel backend, its framework/dependencies, migrations,
models, existing macro/calendar tables, tests, configuration, conventions,
security boundaries, dirty state, and rollback path before proposing or making
schema changes. Reuse existing structures where their contracts are sufficient;
document every reuse, extension, adaptation, or new-table decision.

The architecture must support the program directive's immutable concepts:

- `macro_source_providers`
- append-only `macro_source_runs`
- immutable `macro_raw_artifacts`
- versioned, never-overwritten `macro_observations`
- `macro_indicator_states`
- `macro_release_bundle_states`
- `macro_category_states`
- `macro_regime_snapshots`
- append-only `macro_event_update_ledger`
- `macro_technical_links`
- `macro_backtest_runs`

Bind the schema to the exact Role 2 and Role 3 contracts, including source and
raw-body hashes, source-run lineage, observation supersession, reference/vintage/
availability/conservative-effective timestamps, point-in-time classification,
release bundles, five exact categories, scoring/config/code/registry hashes, and
idempotent uniqueness rules. Preserve raw bodies rather than only DOM hashes.
Define foreign keys, indexes, checks, append-only enforcement, transaction and
retry semantics, resumable collection boundaries, access control, retention,
rollback, and deterministic export/validation contracts.

Required Role 4 evidence includes a database inventory and reuse decision, the
target schema/data-flow/contract specification, migration and rollback design,
risk-appropriate schema tests or migration proof, exact commands and exit
results, and the exact next permitted Role 5 collection action. Any executable
migration/model work must be bounded to this architecture and remain compatible
with the existing Laravel application.

Do not collect or download macro observations, populate production tables,
modify raw `dataset/` files, calculate indicator/bundle/category/regime scores,
join technical setups, inspect strategy PnL, run an economic backtest, connect a
broker, deploy, or start Roles 5–11. Role 4 is architecture and schema only.

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

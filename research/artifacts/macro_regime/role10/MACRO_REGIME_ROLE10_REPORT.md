# Role 10 Reporting and Visualization Report

Status: `PASS_OFFLINE_REPORTING_IN_APP_ROUTE_BLOCKED`
Decision: `INSUFFICIENT_ALIGNED_TRADES`
Candidate: `NONE`

## FACT

- 71 immutable upstream source/output hashes reconcile.
- T0 remains 306 medium-cost fills and -173.4578703725847R.
- Every M1/M2/M3/M4 and opposite-macro variant retains zero fills under J0/J1/J2 because all macro biases are UNKNOWN.
- 11 static charts A-K, one self-contained interactive explorer, and exact local tables were produced. A read-only React component is isolated and tested but is not routed.

## CALCULATION

Presentation-only groupings and cumulative curves are derived from frozen Role 6-9 rows. No score, filter, trade, cost, fold, or candidate result is recalculated.

## ASSUMPTION

No new research assumption is introduced. The page inherits the disclosed source-label, timezone, and hypothetical-cost limitations.

## INTERPRETATION

The macro filter is inactive. Zero retained trades and zero net R are not evidence of improvement, profitability, or strategy rescue. Random retention is NOT_APPLICABLE at zero retention.

## Security and operation

The isolated component has no resource identifier, network request, mutation endpoint, unrestricted source URL, secret, collector, order, paper, broker, or live control. Authenticated route integration is `BLOCKED/FAIL_CLOSED_DIRTY_FILE_OWNERSHIP`: the only router file is a large pre-existing uncommitted user rewrite, and capturing it would violate repository ownership controls. Role 10 removed its two provisional App.js additions and left that user file unchanged. No route is active and no deployment occurred.

## Verification

Focused Python reporting/security tests: 6/6. Frontend: 7/7. Full research regression: 275/275. Production build: exit 0 with pre-existing dependency/source-map/lint warnings. Two complete report generations produced byte-identical 53-file output hash inventories.

Next permitted action: Role 11 Independent Quantitative Auditor only.

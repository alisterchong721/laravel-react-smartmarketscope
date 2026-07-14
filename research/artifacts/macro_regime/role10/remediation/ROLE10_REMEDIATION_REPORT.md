# Role 10 Bounded In-App Reporting Remediation

Program: `SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001`

Status: `IN_APP_ROUTE_ACTIVE_PENDING_ROLE11_SECURITY_REAUDIT`

Quantitative decision: `NO_ACCEPTABLE_STRATEGY_FOUND`
Candidate: `NONE`

## Decision

The previously blocked in-app presentation surface is implemented at the exact
working-tree path `/research/macro-regime`. This does not change the failed
research result: insufficient category coverage produced UNKNOWN bias, zero
aligned trades, and no acceptable strategy.

The route is not protected by token presence alone. It performs a read-only
request through the existing Smart MarketScope API boundary to protected
`GET /me`, validates a positive user identifier and syntactically valid email,
then applies `VERIFIED_REGISTERED_USER_READ_ONLY`. Missing, rejected, malformed,
or unverifiable identities receive no research page. Query strings, fragments,
and extra path segments are denied as unsupported resource selectors.

## Presentation Reconciliation

The in-app page presents frozen evidence only: as-of/source health, category
capacity, current stress/interaction/base/final/permission/bias, technical-only
and macro-filter results, distinct strategy timeframes/families, latest active
indicator ledger drill-downs, and historical category, regime, event, equity,
drawdown, annual, timeframe, regime-performance, category-contribution,
retention, and random-control charts A-K.

All 11 PNGs are byte-identical to
`research/artifacts/macro_regime/report/charts/`. UNKNOWN, numeric zero, and
NOT_APPLICABLE remain distinct. T0 remains 306 medium fills and
-173.4578703725847R; every macro variant retains zero fills, and inactivity is
not presented as improvement.

## Security and Ownership Boundary

The implementation has no POST, PUT, PATCH, or DELETE method; user-selectable
resource identifier; unrestricted research-source URL; raw source URL; secret;
order; broker; paper; deployment; or live control. The sole network action is
identity verification through the existing protected API boundary.

`src/App.js` is a pre-existing user-owned rewrite. Its authorized pre-hunk hash
was `d702d1ddeed2458842c2f420bb258913a1f1b93241bb8347099f63d0ab07f542`.
Only one import and one exact route were added, producing
`233fd2401ffbe316aa6f14386ffe85f26a01ec5a430894b55789e2758579184f`.
Those hunks remain intentionally unstaged and uncommitted. The inverse patch in
this directory applies cleanly and restores the exact pre-hunk hash.

## Verification Outcome

- Focused React authentication/authorization/presentation: 13/13 pass.
- Full frontend: 19/19 pass.
- Focused Python reporting/security/hash/rollback: 9/9 pass.
- Production build: exit 0 with previously disclosed dependency source-map,
  stale browser metadata, unrelated lint, and bundle-size warnings.
- Role 10 validation-only, twice: 71 upstream hashes, 53 output hashes, 11
  charts, PASS; inventory hash unchanged.
- Full research suite: 278 tests pass; three existing Role 11 assertions fail
  because they intentionally require the route to remain absent. Role 10 does
  not rewrite independent-audit evidence. Updating and rerunning those
  assertions is the exact next Role 11 reporting/security re-audit.

No final holdout or post-cutoff outcome was accessed. No frozen quantitative
artifact or registry state was changed.

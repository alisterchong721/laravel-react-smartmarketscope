# MLR Independent Audit

Status: `PASS_PROCESS_VETO_FULL_STRATEGY`

## Findings

### Critical

1. Macro coverage is uncertified: all 1,730 observations are excluded. The
   requested strategy cannot be evaluated and must remain
   `BLOCKED_BY_UNCERTIFIED_MACRO_BIAS`.

### High

2. The supplied eligible phase is probable NAS100 CFD, not Pepperstone-confirmed.
3. Source timezone and MT5 spread units are unresolved; session and cost claims
   would be unsupported.
4. Midpoint bar contact is not an executable fill. No economic result may be
   derived from the frequency registry.

### Medium

5. M1 reaches C1 and C2 in every D1+H4 window. The count reproduces, but its
   saturation and 18/71 direction split require out-of-sample scrutiny after the
   dependency gates pass.
6. The master preregistration timestamp was reconciled from filesystem evidence
   after the first descriptive run. No rule, variant, budget, or result changed;
   the metadata repair is permanently disclosed.

## Reproduction

- Focused detector and artifact suite: PASS, 43 tests.
- Full research suite: PASS, 159 tests.
- Point-in-time macro contract/ALFRED suite: PASS, 20 tests; eligible macro
  observations remain zero.
- Laravel security regression suite: PASS, 65 tests and 257 assertions,
  including IDOR ownership and SSRF route-absence fixtures.
- Primary frequency run: PASS and reproduced.
- Technical ablation run: PASS, 6 experiments and 17 variants reproduced after
  native H4 adjacency and completed-bar checks.
- Dedicated macro, event, setup, zone, component, confluence, and technical-layer
  registries: PASS; downstream split/prediction/trade artifacts are blocked
  placeholders and contain no economic result.
- Full strategy runs: 0.
- Economic backtests: 0.
- Model trials: 0.
- Protected/final-holdout accesses: 0/0.

The auditor accepts the fail-closed process and vetoes candidate promotion,
economic interpretation, LucidFlex analysis, and FTMO preparation.

## Technical Economic Continuation Addendum - 2026-07-13

Status: `PASS_PROCESS_TECHNICAL_EDGE_NOT_FOUND`.

The continuation independently reconciled 1,362 primary scenario rows across
454 selected setups, including exact target/stop equations, timing, path flags,
gross-cost-net accounting, normalized R, summary counts, CPCV, walk-forward,
and the append-only registry. Protected/final-holdout access is 0/0.

All seven primary strategies and all seven 1.5R diagnostics are negative at
medium cost. Every permitted CPCV split is negative, and every confluence entry
underperforms its matched generic-entry control on average. The auditor therefore
vetoes further search and promotion. Detailed evidence is in
`research/artifacts/macro_liquidity_reversal/MLR_TECHNICAL_INDEPENDENT_AUDIT.md`.

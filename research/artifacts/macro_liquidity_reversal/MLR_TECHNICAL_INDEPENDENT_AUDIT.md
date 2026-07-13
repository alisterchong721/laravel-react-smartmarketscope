# MLR Technical Independent Audit

Status: `PASS_PROCESS_TECHNICAL_EDGE_NOT_FOUND`

## Scope

This audit covers only the explicitly authorized `TECHNICAL_ONLY_ABLATION` on
the `PREVIOUSLY_EXPOSED_WINDOW`. It does not validate the intended macro-first
strategy, Pepperstone economics, FTMO readiness, or Lucid readiness.

## Reconciliation

- Frozen frequency checkpoint: PASS; detector and frequency files are unchanged.
- Hash-linked technical registry: PASS; 14 lifecycle events validated.
- Primary trade rows: PASS; 1362 scenario rows across 454 selected setups.
- Fill accounting: PASS; 918 filled scenario rows and 444 no-fill/invalid rows.
- Target, stop, timing, gross-cost-net, and normalized-R equations: PASS for every economic row.
- CPCV and walk-forward reconstruction: PASS; exact sample IDs, purge IDs, embargo IDs, and path mappings are retained in `MLR_TECHNICAL_SPLIT_MANIFEST.json`.
- Protected/final-holdout accesses: 0/0.

## Veto Findings

1. All seven primary 2R strategies have negative medium-cost average net R.
2. Every permitted primary CPCV split is negative; outer folds are overwhelmingly negative.
3. The sole preregistered 1.5R diagnostic remains negative for all seven strategies and is `REJECT`.
4. Every midpoint/confluence strategy underperforms its direction-matched generic-entry control on average.
5. The maximum effective filled-trade sample is 89, so ML is prohibited.
6. Source timezone and broker cost metadata remain unresolved; scenarios are hypothetical only.
7. Certified point-in-time macro coverage remains zero, so no full-strategy inference is permitted.

## Decision

The technical-only decision is `TECHNICAL_EDGE_NOT_FOUND`. Candidate and champion
remain `NONE`. Further parameter search is not justified by the evidence. The
full intended strategy remains `BLOCKED_BY_UNCERTIFIED_MACRO_BIAS`.

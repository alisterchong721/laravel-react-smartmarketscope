# Macro Filter Decision

Program: `SMART-MARKETSCOPE-PUBLIC-MACRO-BIAS-001`

Status: `FAIL`

Decision: `PUBLIC_HISTORY_NOT_POINT_IN_TIME_SAFE`

Candidate: `NONE`. Champion: `NONE`.

## Veto

The public historical source gate failed before collection and scoring. The
sampled Trading Economics surface did not demonstrate historical as-published
Actual, Consensus, Previous, exact release time, or immutable revision lineage.
Using current chart history or current `Previous` values as if they were known
at original release time would violate the point-in-time contract.

## Frozen Comparison Status

| Variant | Status | Reason |
|---|---|---|
| T0 technical only | `FROZEN_REFERENCE_ONLY` | Existing result: 306 medium-cost fills, 52 wins, 246 losses, 2 timeouts, -173.458R. |
| M1 loose macro direction | `NOT_RUN_GATE_FAILED` | No certified macro score history. |
| M2 primary strict direction | `NOT_RUN_GATE_FAILED` | No certified macro score history. |
| M3 strong macro only | `NOT_RUN_GATE_FAILED` | No certified macro score history. |
| M4 strict coverage | `NOT_RUN_GATE_FAILED` | No certified macro score history. |
| M5 opposite-direction control | `NOT_RUN_GATE_FAILED` | No certified macro score history. |

J0, J1, J2, category leave-one-out diagnostics, expanding outer comparison,
cost sensitivity, retention analysis, and PnL deltas are all
`NOT_APPLICABLE_GATE_FAILED`. No zero-valued metrics were substituted.

## Candidate Requirements

No candidate requirement was evaluated because there were zero normalized
macro observations, zero score snapshots, and zero trade-to-bias links. The
program cannot claim `MACRO_FILTER_ADDED_NO_VALUE`, because the macro filter was
never safely constructed or tested. The defensible conclusion is the earlier
source-lineage failure.

## Deployment Decision

- Historical macro-filter candidate: `NONE`.
- FTMO preparation: not justified.
- Lucid preparation: not justified.
- Paper trading: prohibited.
- Broker connection: prohibited.
- Live deployment/order actions: prohibited.

## Exact Next Action

Obtain a licensed point-in-time provider with historical Actual, Consensus,
Previous-as-published, exact source release clocks, immutable revisions, and
clear collection rights. A new child program or prospective amendment must
freeze the provider and lineage contract before collection or economic outcome
access.

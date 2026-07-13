# MLR Program State

Program ID: `QRP-MACRO-LIQUIDITY-REVERSAL-001`  
Registry namespace: `macro_liquidity_reversal`  
Status: `BLOCKED_BY_UNCERTIFIED_MACRO_BIAS`

The repository skill `multi-timeframe-macro-liquidity-reversal` is the sole
mechanical source of truth. The skill installation and critical IDOR/SSRF gates
pass. The macro gate fails because no eligible observation proves an immutable
historical first-received timestamp, exact source release time, forecast as
published, and previous value as published.

Permitted work is limited to deterministic detector correctness, technical
frequency measurement, and explicitly labelled `TECHNICAL_ONLY_ABLATION` work.
No full strategy, economic backtest, model, CPCV selection, walk-forward,
robustness promotion, LucidFlex analysis, paper trading, broker connection, or
deployment is authorized.

The prior program remains untouched. Its cumulative registry snapshot is 57
events, 19 terminal experiments, and last event hash
`c1d19f46dffbbcf62fb1197f3b42aa646f260171660f490ae680cb02d7365c4f`.

## Completed Permitted Work

- Deterministic detector and artifact suite: 43 tests passed.
- Primary technical frequency: 183 D1 trend sweeps, 89 D1+H4 confirmations.
- Standalone technical setups: M15 54, M5 85, M1 89.
- Hierarchical M15→M5→M1 technical setups: 12.
- Technical-only experiments/variant exposures: 6/17.
- Full strategy/economic backtest/model trials: 0/0/0.
- Candidate/champion: `NONE`/`NONE`.

Exact next action is recorded in `MLR_NEXT_TASK.md`.

## Technical Economic Continuation Addendum - 2026-07-13

The user prospectively authorized correction of the incomplete technical-only
scope. The frozen detector/frequency evidence was hash-locked and preserved;
the continuation then completed conservative economic simulation, controls,
CPCV, expanding walk-forward, one preregistered 1.5R diagnostic, and independent
audit.

Technical-only status is `TECHNICAL_EDGE_NOT_FOUND`. Across 454 strategy-specific
eligible setups, the medium-cost pass produced 306 fills, 148 no-fills, 52 wins,
246 losses, 2 timeouts, and 6 adverse-first ambiguities. Pooled configuration
observations average -0.567R and total -173.458R. All seven primary strategies
are negative; every permitted CPCV split is negative; ML is prohibited because
the maximum effective sample is 89. The 1.5R diagnostic is `REJECT`.

The technical registry contains 15 valid hash-linked lifecycle events. The
latest independent audit passes process reconciliation and vetoes promotion.
Candidate/champion remain `NONE`/`NONE`; protected/final-holdout access remains
0/0. The full intended strategy remains `BLOCKED_BY_UNCERTIFIED_MACRO_BIAS`.

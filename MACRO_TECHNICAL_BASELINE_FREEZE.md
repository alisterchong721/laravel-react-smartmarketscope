# Macro Technical Baseline Freeze

Status: `PASS_TECHNICAL_BASELINE_FROZEN`

Program: `SMART-MARKETSCOPE-PUBLIC-MACRO-BIAS-001`

The completed technical-only MLR result is frozen as an immutable control. This artifact does not alter detector, setup, entry, stop, 2R target, expiry, fill, or outcome logic.

## Reconciliation

- Clean byte-identical regeneration: `PASS_BYTE_IDENTICAL_REPRODUCTION` across 6 primary artifacts.
- Frozen technical setups: 454.
- Frozen setup/scenario trade rows: 1362.
- Medium-cost fills/no-fills: 306/148.
- Medium-cost wins/losses/timeouts: 52/246/2.
- Medium-cost average/total net R: -0.5668557855313225551546933291 / -173.4578703725847018773361587.
- Worst strategy drawdown: 52.72435033062773699774507294R.
- Code commit: `231e27c55017e67e02872115cce4f1ab1e4e42da`.
- Strategy configuration SHA-256: `800b6fe27da064ad952d87b8fee4e7bad96a28dba67176e7597e852540808124`.
- Detector SHA-256: `0e5af7d33c09f76e72802fd17cb9421bce03cb3d9aaea16b6dcc917ce523d297`.
- Baseline registry SHA-256: `b5784ce9ab7311063b21eb33bdaf9c4218a5ade730624c00a3ddb50e468b7db7`.
- Protected/final-holdout accesses: 0/0.

## Use Rule

Every macro comparison must filter this exact candidate set. No retained trade may change the source setup, entry, stop, 2R target, expiry, fill status, outcome, gross R, or net R.

The technical decision remains `TECHNICAL_EDGE_NOT_FOUND`; this freeze is a comparator, not a candidate or trading authorization.

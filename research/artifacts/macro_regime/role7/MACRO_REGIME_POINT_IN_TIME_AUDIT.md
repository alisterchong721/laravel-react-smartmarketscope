# Macro Regime Point-in-Time Audit

Status: `PASS`
Decision: `ROLE7_POINT_IN_TIME_VALIDATED_ROLE8_ALIGNMENT_PERMITTED`

Independent Role 7 reconstruction rehashed all three frozen inputs, four Role 6 registry/config files, the scoring code, the Role 6 manifest, and every named output. It reconstructed all `5,216` indicator states from only observation versions effective at each state time, then validated observation → indicator → bundle → category → snapshot lineage.

- Eligible versions / ledger rows: `10,273` / `10,273`.
- Unique raw artifacts independently rehashed: `2,236` (`334,666,627` bytes).
- Indicator / bundle / category / snapshot states: `5,216` / `5,111` / `1,840` / `1,718`.
- Daily as-of / active-input rows: `9,676` / `51,361`.
- Future-vintage, pre-effective, cross-reference replacement, within-batch public-state, and carried-score violations: `0`.
- All `9,676` daily biases are `UNKNOWN`; every technical permission is `NO_TRADE`.
- Frozen bundle capacity is `{"GROWTH":1,"INFLATION":1,"LABOUR":1,"LIQUIDITY":4,"MONETARY_POLICY":1}`. At most `2` categories can be valid against the minimum of three.

The H.4.1 Role 5 export carries one release-level bundle label for all three observations in each weekly release. That upstream field conflicts with the Role 6 registry for reserves and TGA on `2,456` rows. Role 6 explicitly treats the frozen indicator registry as the scoring taxonomy and its outputs consistently use `BANK_RESERVES_BUNDLE` and `LIQUIDITY_DRAINS_BUNDLE`; no output inherited the conflicting label. This is retained as a disclosed lineage warning, not silently rewritten.

No technical setup, trade outcome, PnL, protected/final-holdout path, experiment, broker, or deployment input was accessed.

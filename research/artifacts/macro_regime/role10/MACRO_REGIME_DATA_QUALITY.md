<!-- Exact Role 10 reporting copy. Source: research/artifacts/macro_regime/role6/MACRO_DATA_QUALITY_REPORT.md; SHA-256: ce88f3f91cacef356545154c0d10001d5e6b8921e9f364c6c0aa4454a5374c83. -->
# Macro Data Quality Report

Status: `PASS_ROLE6_DETERMINISTIC_MATERIALIZATION_WITH_COVERAGE_VETO`

- Frozen input hashes matched: `3/3`.
- Eligible inputs / ledger rows: `10,273 / 10,273`.
- Revisions retained: `5,816`.
- Unique indicator states: `5,216`; statuses `{"INSUFFICIENT_HISTORY":184,"VALID":5032}`.
- Release-bundle states: `5,111`; statuses `{"INSUFFICIENT_HISTORY":171,"VALID":4940}`.
- Category states: `1,840`; statuses `{"CONFLICTING":766,"INSUFFICIENT_HISTORY":132,"PARTIAL":238,"VALID":704}`.
- Regime snapshots / daily rows: `1,718 / 9,676`.
- Duplicate observation IDs, nonfinite values, alias mismatches, category mismatches, future-effective rows, config/registry hash mismatches: `0 accepted`.
- Current-revised-only inputs, technical inputs, PnL inputs, news/LLM inputs, experiment trials, protected/final-holdout accesses: `0`.

The H.4.1 signed reserve observation is retained and transformed with absolute changes. H.6 release revisions are atomic at exact effective timestamps. ALFRED revisions remain immutable and only replace the same reference period after their conservative J0 timestamp. Same-time rows are applied as one availability batch, preventing artificial within-release ordering from changing the public state.

Limitations: Role 6 is a deterministic construction role, not the independent point-in-time audit. Role 7 must independently verify source/effective chronology, future-vintage exclusion, atomic replacement, daily as-of semantics, and J0 readiness before any technical join. Registry chronology remains a final-champion veto.

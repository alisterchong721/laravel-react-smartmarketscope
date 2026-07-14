# Macro Regime Availability Audit

Status: `PASS`
Headline join readiness: `J0_READY_FOR_ROLE8_ASOF_JOIN`

All `10,273` observation versions exactly equal local midnight on their recorded `America/New_York` availability date plus 36 elapsed hours. UTC and `Asia/Kuala_Lumpur` conversions reconcile exactly. The population exercises both New York offsets: `{"-1 day, 19:00:00":4209,"-1 day, 20:00:00":6064}`.

## Frozen timing semantics

- `J0`: availability-date start in `America/New_York` plus 36 hours. Eligibility is inclusive at the exact effective timestamp.
- `J1`: start of the first frozen source trading date strictly after the availability date.
- `J2`: start of the second frozen source trading date strictly after the availability date.
- J1/J2 require a hash-locked NAS100 source trading-date calendar from Role 8. Missing dates fail closed; weekdays or holidays must not be inferred. Their semantics are frozen for sensitivity only and may not be selected from PnL.
- Same-effective-time observations activate atomically. No within-batch state is public.

The DST boundary fixture maps J1/J2 to `2026-03-09T04:00:00Z` and `2026-03-10T04:00:00Z`. J0 is ready; J1/J2 materialization remains deliberately pending the Role 8 source-calendar hash and does not block the headline J0 join.

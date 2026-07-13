# MLR Point-In-Time Audit

Status: `FAIL_FULL_STRATEGY_PASS_TECHNICAL_DETECTORS`

- Completed canonical D1/H4/M15/M5 bars expose distinct start and availability
  timestamps; detector searches filter on availability.
- M1 is auxiliary native data and is conservatively made available one native
  minute after its source label for technical frequency only.
- LTF searches begin no earlier than
  `max(d1_confirmation_time, h4_confirmation_time)`.
- No post-2026-06-28 observation or final holdout was accessed.
- Future-mutation invariance passes in deterministic fixtures.
- Macro PIT certification fails: 25 source runs, 1,730 observations, zero
  eligible observations, and no exact historical first-received timestamp.

The full strategy is therefore `BLOCKED_BY_UNCERTIFIED_MACRO_BIAS`. Source
timezone is also unresolved, so named session conversion is not attempted.


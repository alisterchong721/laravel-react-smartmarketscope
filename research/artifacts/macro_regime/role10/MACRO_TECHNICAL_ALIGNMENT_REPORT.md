<!-- Exact Role 10 reporting copy. Source: research/artifacts/macro_regime/role8/MACRO_TECHNICAL_ALIGNMENT_REPORT.md; SHA-256: f370cc98bc12098d2bc5516bd432f0af55950f378c212d30ceaa4c1928343c09. -->
# Macro Technical Alignment Report

Status: `PASS_ROLE8_ALIGNMENT_COMPLETE_ROLE9_PERMITTED`

All `454` frozen technical setups are linked once under each of `J0`, `J1`, and `J2` for `1362` immutable links. Every linked macro state is `UNKNOWN`, so all links remain `FILTERED_UNKNOWN`; coverage was not relaxed and no replacement trade was created.

## Source calendar and timing

The exact source calendar contains `2309` NAS100-labelled eligible D1 bar-start dates from `2017-07-17` through `2026-06-25`. No weekday or holiday was inserted. Source timezone remains unresolved. `America/New_York`, UTC, and `Asia/Kuala_Lumpur` columns are date-aware conversions of the frozen Role 7 activation rule, not claims about the source feed timezone.

Technical actionable timestamps remain byte-identical source wall-clock labels. Because their timezone is unresolved, the as-of comparison uses the Role 7 activation wall-clock coordinate and is explicitly labelled `NOT_UTC_EQUIVALENCE`. Every selected snapshot is effective at or before that coordinate; exact equality is eligible.

`J1` selects the first frozen source trading date strictly after availability and `J2` the second. Events before the calendar begins collapse prospectively onto its first available dates rather than inventing earlier dates. Tail snapshots without enough later frozen dates remain unmapped ({'J1': 1, 'J2': 1}) and cannot enter a link.

## Census

| Join | Links | Filtered unknown | Future states | Replacement trades |
|---|---:|---:|---:|---:|
| J0 | 454 | 454 | 0 | 0 |
| J1 | 454 | 454 | 0 | 0 |
| J2 | 454 | 454 | 0 | 0 |


No macro-filter PnL, return, expectancy, selection, tuning, protected/final-holdout access, broker action, or deployment occurred. Role 9 may consume these frozen links for the preregistered economic comparison only.

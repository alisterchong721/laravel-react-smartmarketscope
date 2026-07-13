# Trading Economics Public Access Limitations

Status: `PUBLIC_HISTORY_NOT_POINT_IN_TIME_SAFE`

Access outcome: `PUBLIC_ACCESS_PARTIAL`

## Blocking Limitations

1. Public indicator pages expose only a small recent release table. Their
   long-run history is a current chart/statistics series, not an immutable
   as-published release ledger.
2. Historical Forecast/Consensus was not reached for 2005, 2010, 2015, 2020, or
   2024. It was visible only for selected recent rows.
3. Historical Previous-as-published was not reached. The current Previous field
   can incorporate later revisions.
4. A separate Actual release timestamp was not available. Recent pages label a
   GMT calendar time, but do not distinguish scheduled time, first publication,
   delayed publication, or modern page-update time.
5. Stable indicator URLs and names exist, but immutable source event IDs and
   release-instance version IDs were not exposed.
6. Revision events are described narratively and sometimes appear as successive
   releases, but supersession links and exact as-published snapshots are absent.
7. Importance was not present in the sampled indicator-page release rows.
8. The balance-sheet sample had no public Consensus values in its recent rows.
9. The public calendar accepted custom 2005 values in the visible form controls,
   but submission did not replace the July 2026 table with 2005 release rows.
10. CSV/API export displayed a subscription notice and login link. No restricted
    export was attempted.

## Historical Year Interpretation

The sampled chart ranges encompass 2005, 2010, 2015, 2020, 2024, and 2026.
Those years are reachable only as current historical-series coverage in this
audit. They are classified `CURRENT_REVISED_VALUE_ONLY` unless a separate
release ledger proves otherwise.

The earliest sampled chart year is 1914 for CPI. The latest exact-time release
row inside the target cutoff was GDP on 2026-06-25. The liquidity page's visible
release rows began after the 2026-06-28 cutoff, so no cutoff-eligible liquidity
release row was accepted.

## Timestamp Limitations

- The recent indicator tables label their time column `GMT`.
- This is usable evidence for the displayed recent rows only.
- It does not prove historical time-zone semantics or DST handling for the
  requested years.
- No historical first-received timestamp exists because this is a modern public
  reconstruction.
- `first_received_at` would have to remain null.
- Any stored recent row would require
  `historical_reconstruction_type=TRADING_ECONOMICS_PUBLIC_RECONSTRUCTION`.

## Access-Rules Evidence

The public `robots.txt` request returned HTTP 200 with `Content-Length: 49` and
the body `Sitemap: https://tradingeconomics.com/sitemap.xml`. It did not contain
user-agent directives. This is not a license grant and does not override the
site's subscription controls. The audit did not access paid export/API routes,
log in, or bypass controls.

## No-Go Conclusions

- Do not label public chart values `PIT_CERTIFIED`.
- Do not use recent current-page Consensus as historical consensus coverage.
- Do not substitute Previous for missing Forecast.
- Do not infer historical release timestamps from a modern schedule.
- Do not silently treat current revised values as first prints.
- Do not begin the historical collector or macro-versus-technical comparison.

Secondary terminal limitation: `PUBLIC_CONSENSUS_HISTORY_UNAVAILABLE`.


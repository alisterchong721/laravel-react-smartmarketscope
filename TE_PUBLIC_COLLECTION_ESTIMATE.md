# Trading Economics Public Collection Estimate

Decision: `PUBLIC_COLLECTION_NOT_PRACTICAL` under the sampled public surface,
with the primary governance stop `PUBLIC_HISTORY_NOT_POINT_IN_TIME_SAFE`.

## Pilot Accounting

- Pilot ceiling: 120 pages.
- Unique successful HTML URLs: 6.
- Ineffective custom historical-date interaction: 1.
- Public `robots.txt` GET: 1.
- Conservative total page/request interactions: 8.
- Raw historical pages collected: 0.
- Normalized macro observations: 0.
- 403/CAPTCHA/429 outcomes: 0/0/0.

## Requested Scope Estimate

The supplied Phase P1 list contains approximately 29 named indicator/release
families: 8 inflation, 8 growth, 6 labour, 3 monetary-policy descriptions, and
4 liquidity descriptions. The requested 2000-2026 interval contains 27 calendar
years.

If every indicator page supplied all required release rows in one response, the
theoretical lower bound would be about 29 indicator pages. The sampled pages do
not do that: they provide long-run current chart data and only a few recent
release rows.

A separate annual release-ledger traversal would require at least 29 x 27 = 783
indicator-year page units before retries, changed-page versions, or validation.
A less granular calendar-first traversal would still require at least 27 annual
calendar ranges plus 29 indicator pages (56 navigations) and deterministic
indicator filtering. The public custom-date test did not demonstrate that those
annual release rows are retrievable.

These counts are estimates, not an authorization or target.

## Field Coverage Estimate

| Field family | Observed public coverage | Full-history estimate |
|---|---|---|
| Actual | Recent rows plus current revised chart series | Historical first prints not demonstrated |
| Forecast/Consensus | Selected recent rows only | Historical coverage unavailable |
| Previous | Selected recent rows only | Previous-as-published unavailable |
| Exact time | Recent GMT rows only | Historical exact-time coverage unavailable |
| Revisions | Narrative/successive recent estimates | Immutable revision lineage unavailable |
| Stable identity | Stable indicator URL/name | Release-instance identity unavailable |
| Importance | Not exposed in sampled indicator rows | Unknown |

## Practicality Decision

The dominant problem is not request volume. It is source semantics. Even a
successful 783-page traversal of current chart history would not reconstruct
historical Forecast, Previous-as-published, exact release clocks, or immutable
revision lineage. Full collection therefore cannot pass the point-in-time gate.

Bulk CSV/API export also displayed a subscription/login notice. The audit did
not attempt that path. A licensed point-in-time source is the defensible next
source option.


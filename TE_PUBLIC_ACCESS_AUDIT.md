# Trading Economics Public Access Audit

Program: `SMART-MARKETSCOPE-PUBLIC-MACRO-BIAS-001`

Role: Public Macro Access and Provenance Auditor (Phase P1)

Audit generated: `2026-07-13T05:49:42Z`

Technical baseline gate: `PASS_TECHNICAL_BASELINE_FROZEN` at commit
`48ca2bdb1c44ad05f5207a3d33144a839185bfed`.

Access outcome: `PUBLIC_ACCESS_PARTIAL`

Primary terminal outcome: `PUBLIC_HISTORY_NOT_POINT_IN_TIME_SAFE`

Secondary limitation: `PUBLIC_CONSENSUS_HISTORY_UNAVAILABLE`

Full collection gate: `FAIL` (1 of 10 gates passes). Do not begin full
historical collection or an economic comparison from this public evidence.

## Decision

Trading Economics public indicator pages loaded without login, CAPTCHA, 403, or
429. They expose current/recent release tables with a GMT date/time, reference
period, Actual, Previous, Consensus, and TEForecast where the field exists. They
also expose long-run indicator ranges and chart controls.

That public surface is not a historical as-published release ledger. The
long-run series is presented as current historical data, while the visible
release table is limited to a few recent rows. The public calendar custom-date
interaction accepted a 2005 date range in its controls but did not transition
the rendered table away from July 2026. CSV/API export opened a notice stating
that subscription users can export data and use the API. No login or paid path
was attempted.

The visible revision evidence is also incompatible with assuming historical
point-in-time safety. The GDP page shows successive Q1 2026 estimates of 1.6%
and 2.1%. The payroll page describes May payrolls as downwardly revised to 129K
after a recent release row displayed 172K. The pages do not provide immutable
release-instance IDs, page versions, historical first-receipt timestamps, or an
explicit previous-as-published lineage. Therefore recent values may be useful as
modern public reconstruction evidence, but they cannot certify historical
surprise inputs.

## Controls And Request Accounting

- One browser worker was used sequentially.
- Six unique HTML page URLs rendered successfully.
- One public custom-date interaction was attempted and did not expose the 2005
  release ledger.
- One non-retried `robots.txt` GET returned HTTP 200.
- Conservative pilot accounting is 8 page/request interactions, below the
  ceiling of 120.
- Concurrent requests: 1.
- 403 retries: 0. CAPTCHA retries: 0. 429 retries: 0.
- No login, subscription, API key, proxy, identity rotation, or access-control
  bypass was used.
- No full collection, normalized observation creation, scoring, or technical
  comparison began.
- Browser DOM snapshots were hashed in memory. Raw HTML response bodies were
  not available through the approved browser surface and were not represented
  as cached raw pages.

## Public Evidence Sample

| Category | Page | Public long-run range | Recent pre-cutoff release evidence | Source shown |
|---|---|---:|---|---|
| INFLATION | US Inflation Rate | 1914-2026 | 2026-06-10, May reference, Actual/Previous/Consensus/TEForecast, GMT | U.S. Bureau of Labor Statistics |
| GROWTH | US GDP Growth Rate | 1947-2026 | 2026-05-28 and 2026-06-25, Q1 estimates, Actual/Previous/Consensus/TEForecast, GMT | U.S. Bureau of Economic Analysis |
| LABOUR | US Non Farm Payrolls | 1939-2026 | 2026-06-05, May reference, Actual/Previous/Consensus/TEForecast, GMT | U.S. Bureau of Labor Statistics |
| MONETARY_POLICY | US Fed Funds Interest Rate | 1971-2026 | 2026-06-17, Fed decision, Actual/Previous/Consensus/TEForecast, GMT | Federal Reserve |
| LIQUIDITY | US Central Bank Balance Sheet | 2002-2026 | No pre-2026-06-28 release row visible; recent July rows omit Consensus | Federal Reserve |

The long-run ranges include 2005, 2010, 2015, 2020, 2024, and 2026 for all five
sampled categories. This proves only that a current revised chart series spans
those years. It does not prove that historical Actual, Forecast, Previous, or
release-time records for those years are publicly reachable or as published.

Earliest reachable current-series year in the sample is 1914 (CPI). Earliest
common current-series year across all five categories is 2002 because the
balance-sheet page begins in 2002. The latest target-eligible exact-time release
row observed was 2026-06-25 (GDP). Pages also displayed post-2026-06-28 content;
that content is outside the requested historical cutoff and was not treated as
eligible evidence.

## Source Facts Versus Audit Inference

Source facts:

- Public pages rendered without authentication.
- Recent release tables use the columns Calendar, GMT, Reference, Actual,
  Previous, Consensus, and TEForecast.
- The five pages show the long-run ranges listed above.
- GDP exposes multiple estimates for the same Q1 reference period.
- Payroll text explicitly identifies a later revision to May payrolls.
- The balance-sheet recent rows have blank Consensus cells.
- Download Data opened a notice that export/API access is for subscription
  users and included a Member Login link.
- `robots.txt` returned HTTP 200 and contained only a sitemap declaration; no
  user-agent rules were present in the retrieved 49-byte body.

Audit inferences:

- A long-run chart is current revised history unless a versioned, as-published
  lineage is separately demonstrated.
- A recent Calendar row is deterministic to parse, but its current rendering is
  not proof of the values visible at the historical release time.
- The absence of an immutable release-instance ID and revision lineage prevents
  point-in-time certification.
- The public surface cannot support the frozen surprise scorer for at least
  three categories over the requested history.

## Ten Full-Collection Gates

| # | Gate | Result | Evidence |
|---:|---|---|---|
| 1 | Historical pages are publicly accessible | FAIL | Current long-run charts are public, but as-published historical release pages were not reached. |
| 2 | Access requires no bypass | PASS | All successful pages were public; no restricted path was bypassed. |
| 3 | Navigation reaches a useful number of years | FAIL | Chart ranges span years, but the 2005 calendar attempt did not expose historical release rows. |
| 4 | Historical Actual is available | FAIL | Recent Actual is visible; older public history is current/revised chart data without release versions. |
| 5 | Historical Forecast/Consensus is available | FAIL | Consensus was observed only in recent rows and was absent for liquidity rows. |
| 6 | Release timestamps are available or defensibly bounded | FAIL | Recent rows show GMT; representative historical release timestamps were not reached. |
| 7 | Revision semantics are understandable | FAIL | Revisions are visible, but immutable supersession and previous-as-published semantics are absent. |
| 8 | A deterministic parser can be built | FAIL | A recent-row parser is feasible; a deterministic full-history release parser has no reachable source ledger. |
| 9 | At least three categories have usable coverage | FAIL | No category has demonstrated historical Actual+Consensus+time+revision lineage. |
| 10 | Independent provenance review approves collection | FAIL | This provenance review rejects full collection from the sampled public surface. |

## Permitted Next Action

Do not proceed to Roles 3-8 as an empirical public-history program. Preserve
this failure and either:

1. obtain a licensed, point-in-time provider that supplies historical
   Actual/Consensus/Previous-as-published, exact release clocks, and revision
   lineage; or
2. implement later infrastructure only against explicit synthetic fixtures,
   without running the macro-versus-technical economic comparison.


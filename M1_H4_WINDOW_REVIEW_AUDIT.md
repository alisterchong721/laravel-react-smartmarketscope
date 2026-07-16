# M1 H4 Window Review, Hierarchy Context, and Setup Filter Audit

Date: 2026-07-16
Outcome: `COMPLETE_AS_DISPLAY_ONLY_EVIDENCE`
Parent decision preserved: `TECHNICAL_EDGE_NOT_FOUND`

## Delivered

`Backtesting → NAS100 Candle` now has an M1 setup-state filter with five views:

- all setup states;
- filled;
- formed, including filled and unfilled;
- formed but not filled;
- not formed (`0 filled / 0 formed`).

Selecting a zero-filled row now shows the complete raw M1 candlestick shape for
that row's owning four-hour H4 interval. The H4 intrabar activation is marked
using the M1 bar's `availableAt` time so the still-forming minute cannot appear
completed at activation. A not-formed chart has no breaker/FVG zone, entry,
stop, target, fill, outcome, or execution overlay.

Filled and formed setup charts now use the same complete owning-H4 projection.
The full four-hour area is labeled `Owning H4 window`, while the frozen breaker
and displacement-FVG roles, zones, entry, stop, and selected 2R/2.5R target are
unchanged. The H4 evidence chart labels its active D1 window. Every D1 chart
contains exactly five candles: three earlier native Daily context candles plus
the exact frozen C1/C2 swing pair. No later D1 candle is appended.

## Evidence boundary

This change did not rerun or alter the frozen detector. It created a separate
chart-only projection from the locked corrected result index and the locked M1
source. Each detail is bounded by `h4WindowOpen <= M1 bar start <
h4WindowExpiry`. It does not infer a setup from visual appearance and adds zero
strategy trials.

| Reconciliation | Count |
| --- | ---: |
| Nested D1/H4 events | 658 |
| Filled events | 31 |
| Formed events, including filled | 32 |
| Formed but not filled | 1 |
| Not formed | 626 |
| M1 candles projected | 140,356 |
| Empty H4 chart windows | 0 |
| Events with fewer than five D1 context candles | 0 |
| New strategy trials | 0 |

## Integrity

- Corrected parent index SHA-256:
  `3654b47e1a9b715952747abaf2eb0e6df8fadb9e1f6262a8275168d5006c9b9e`.
- Source M1 SHA-256:
  `9ca414716a7c30b20006052af651d1f06f77ce23f62e7072feebd79896567f65`.
- Native Daily context SHA-256:
  `2de323fa640b3afef2f32c4aad69309e6583848ab938e3920619bd1242510a75`.
- Frozen parent manifest SHA-256:
  `6241d1752c61b43a5b94904efc01da397b7d7d1183a28601e98ff29222c93558`.
- Review index SHA-256:
  `14f2f4062d36735d72425ae0374d703d67564bcd931390df838b69c800db71c3`.
- Review manifest SHA-256:
  `505265126cd8804c49b9211361409f00f0ccfd541e218f2defeffec5cbfbf340`.
- All 658 detail files are listed with hashes in the manifest.
- The protected detail API explicitly returns `chartOnly: true` and
  `executionAuthorized: false`.

## Verification

- Focused projection Python: 3 tests passed.
- Focused React: 2 suites, 15 tests passed.
- Focused Laravel: 4 tests passed, 50 assertions.
- Full React: 17 suites, 80 tests passed.
- Full Laravel: 106 tests passed, 571 assertions, with 3 existing
  target-driver skips.
- Production React build: succeeded with pre-existing dependency source-map,
  stale browser-data, bundle-size, and unrelated lint warnings.
- A clean second projection run reproduced the index and manifest byte for
  byte.

## Remaining limits

The source history was previously exposed and is not a pristine holdout. The
source clock, broker identity, price side, spread units, and contract terms
remain unresolved. These charts are for inspection only and do not authorize
paper, broker, or live execution.

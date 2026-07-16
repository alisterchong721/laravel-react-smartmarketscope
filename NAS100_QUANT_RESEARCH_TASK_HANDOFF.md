# NAS100 Quant Research Task — Current State and Handoff

Document version: `1.1.0`
Prepared: `2026-07-16` (`Asia/Kuala_Lumpur`)
Repository: `react-smart_marketscope/react-smartmarketscope`
Repository base commit at stage start: `d6c9f12726e068a5d66d9f4142d93751a84822f2`
Current branch: `codex/public-macro-bias-001`
Primary instrument: supplied NAS100 CFD source files; not NDX, NQ, MNQ, or a
universal NAS100 contract
Research cutoff: no NAS100 observation after `2026-06-28` may be used for
historical tuning or model selection
Overall status: `RESEARCH_CONTINUES_WITH_NO_VALIDATED_CANDIDATE`

### Latest presentation stage — hierarchy context complete

The current `NAS100 Candle` modal now makes timeframe ownership explicit:

- every filled/formed M1 chart spans and labels the complete owning H4 interval;
- its frozen breaker/FVG annotations and 2R/2.5R result are unchanged;
- the H4 chart labels the active parent D1 window;
- every D1 chart shows three earlier context bars plus the exact frozen C1/C2
  swing pair, for five D1 candles total and no later daily bar.

The projection reconciles 658/658 events, 140,356 M1 candles, zero empty H4
windows, zero D1 charts below five candles, and zero new trials. This is a
display-only refinement and leaves `TECHNICAL_EDGE_NOT_FOUND`, candidate
`NONE`, and champion `NONE` unchanged. See `M1_H4_WINDOW_REVIEW_AUDIT.md`.

## 1. Purpose of this document

This is the durable handoff for the current NAS100 quant work. It records:

- what the research is trying to build;
- the exact technical and macro logic already frozen;
- what has been implemented in Smart MarketScope;
- what empirical work has already completed;
- what failed and why;
- which data can and cannot support a historical claim;
- the immediate `NAS100 Candle` product task;
- the gates that must pass before a true macro-plus-technical backtest can run;
- the exact next actions and acceptance checklist.

This document does not create a new experiment, change a detector, reopen a
rejected strategy, or authorize paper/live trading.

## 2. Decision summary

| Workstream | Current state | Decision |
| --- | --- | --- |
| Frozen multi-timeframe technical detector | Complete | Detector and artifacts are preserved. |
| Technical-only economic backtest | Complete | `TECHNICAL_EDGE_NOT_FOUND`; candidate `NONE`. |
| Public point-in-time macro acquisition | Stopped at source gate | `PUBLIC_HISTORY_NOT_POINT_IN_TIME_SAFE`; candidate `NONE`. |
| Historical macro-filter comparison | Not validly runnable | No certified macro history; M1–M4 were not run in the compliant public-macro program. |
| Current-vintage weekly macro page | Implemented | Display-only reconstruction at `/backtesting/nas100`; not a backtest. |
| Historical alignment evidence viewer | Implemented but hidden from primary navigation | Read-only 454-setup projection with D1/H4/M15/M5/M1 candles. |
| `NAS100 Candle` page | Complete and browser-verified | Preserve as a read-only technical evidence explorer using frozen artifacts. |
| Validated strategy/champion | None | No paper, broker, FTMO, Lucid, or live use is authorized. |

The current research conclusion is deliberately unfavorable: the frozen
technical strategy did not demonstrate an edge, and public macro history could
not satisfy the historical point-in-time contract. The correct next product
work is evidence inspection, not additional parameter searching.

## 3. Program structure

The work consists of three distinct layers. They must not be conflated.

### 3.1 Technical detector and technical-only evidence

Program: `QRP-MACRO-LIQUIDITY-REVERSAL-001`
Technical experiment: `MLR-TECH-ECO-001`

This layer detects daily and H4 liquidity-reversal context, then searches M15,
M5, and M1 for mechanically defined confluence. It has already been frozen,
simulated, validated, and independently audited.

### 3.2 Macro acquisition and bias scoring

Program: `SMART-MARKETSCOPE-PUBLIC-MACRO-BIAS-001`

This layer was intended to acquire United States releases through compliant
public access, construct immutable point-in-time category scores, and filter
the exact frozen technical candidate set. Public pages were reachable, but the
historical as-published fields required for a valid backtest were not proven.
The program correctly stopped before collection/scoring/PnL comparison.

Separately, the application contains a current-vintage U.S. macro history for
display. That product history must not be described as the successful outcome
of the point-in-time macro research program.

### 3.3 Smart MarketScope research UI

This layer exposes already frozen evidence for inspection. It may organize and
visualize existing observations and candles, but it may not silently recompute
setups, tune thresholds, replace UNKNOWN macro states, or create trading
actions.

## 4. Exact technical logic already frozen

The source of truth is `MLR_MECHANICAL_SPEC.md` and the immutable
multi-timeframe skill specification. No generalized or discretionary ICT/SMC
interpretation is permitted.

### 4.1 Bar and timing rules

- Use completed bars only.
- Preserve source wall-clock labels because the source timezone remains
  unresolved.
- Do not describe source timestamps as UTC, New York, or Malaysia time.
- Use SMA-seeded EMA20 and EMA50 for D1 trend context.
- Use SMA-seeded Wilder ATR14 where ATR is required.
- Entry components become eligible only after every required component is
  available.
- One filled trade maximum is allowed per D1 event, family, and architecture.

### 4.2 D1 trend and sweep context

The D1 stage uses the completed D1 EMA20/EMA50 relationship and a strict
two-candle close-only sweep/reversal pattern.

For a bullish sweep:

- candle 1 is bearish;
- candle 2 trades below candle 1's low;
- candle 2 closes back above candle 1's low;
- candle 2's body is no more than 50% of candle 1's body;
- the direction must agree with the frozen D1 trend context.

The bearish rule is the exact mirror. Equality does not satisfy a strict cross.

### 4.3 H4 confirmation

- Inspect the three native H4 bars after the completed D1 confirmation.
- Apply the same strict sweep/reversal definition in the required direction.
- The technical actionable time is the later of D1 confirmation and H4
  confirmation.
- Only the 89 frozen D1+H4 events are eligible for the economic continuation.

### 4.4 Lower-timeframe components

#### Fair Value Gap (FVG)

- Strict three-bar gap.
- The gap must have positive width; touching/equality is not a valid gap.
- Availability begins only after the third bar completes.

#### Order Block (OB)

- Structure lookback: `N = 10`.
- Candidate window: latest opposite candle within `K = 3`.
- Required displacement: at least `1.0 × ATR14`.
- The block must remain unmitigated under the frozen rule.

#### Breaker

- Begin from a failed OB.
- Require a strict break.
- Use the first qualifying retest from the correct side.
- Require the frozen midpoint/close behavior; no discretionary breaker drawing.

### 4.5 Confluence families

Only two families exist:

- `C1_OB_FVG`: strict positive overlap between the selected OB and FVG.
- `C2_FVG_BREAKER`: strict positive overlap between the selected FVG and
  breaker.

C1 and C2 are not mixed inside one hierarchical setup.

### 4.6 Architectures

- Standalone M15.
- Standalone M5.
- Standalone M1.
- Hierarchical M15 → later overlapping same-family M5 → later overlapping
  same-family M1.

For each event/family/architecture, only the first confirmed confluence is used.

### 4.7 Frozen trade mechanics

- Entry: midpoint of the strict positive overlap.
- Entry must occur strictly after all components become available.
- Equality-only contact is `NO_FILL`; strict child-bar penetration is required.
- C1 stop: beyond the selected OB.
- C2 stop: beyond the selected breaker.
- Hierarchical stop: beyond the final M1-stage block.
- Stop buffer: maximum of the `0.1` source quantum and scenario spread points.
- Target: exact cost-aware 2R under the frozen formula.
- Expiry: native D1 candle-3 close.
- Gap-through stop: adverse gap open.
- Stop and target in the same unresolved M1 bar: adverse-first ambiguity.
- `NO_FILL` and `INVALID_DATA` are not losses.

The cost cases are normalized scenarios, not broker facts. Dollar PnL is not a
permitted claim.

## 5. Technical data and coverage

### 5.1 Supplied raw candle files

| Timeframe | Start | End | Approximate rows |
| --- | --- | --- | ---: |
| D1 | 2008-08-06 | 2026-06-26 | 4,780 |
| H4 | 2008-08-06 00:00 | 2026-06-26 20:00 | 18,096 |
| M15 | 2008-08-06 00:00 | 2026-06-26 23:45 | 222,177 |
| M5 | 2008-08-06 00:00 | 2026-06-26 23:50 | 645,849 |
| M1 | 2008-08-06 00:00 | 2026-06-26 23:54 | 3,180,929 |

The supplied candle data does **not** begin in 2000. A UI must not imply that
technical candles exist from 2000. Frozen strategy-specific setups are
concentrated in 2017–2026 after data/warmup and rule eligibility. The macro
display may begin in 2000, but that does not extend technical candle coverage.

### 5.2 Frozen detector counts

| Stage | Frozen count |
| --- | ---: |
| D1 trend-matched sweeps | 183 |
| D1 + H4 confirmations | 89 |
| Standalone midpoint-reach diagnostic: M15 | 54 |
| Standalone midpoint-reach diagnostic: M5 | 85 |
| Standalone midpoint-reach diagnostic: M1 | 89 |
| Hierarchical midpoint-reach diagnostic | 12 |
| Strategy-specific first-confirmed setups in economic continuation | 454 |
| Scenario rows across low/medium/high cost | 1,362 |

The 54/85/89/12 counts are earlier midpoint-reach frequency diagnostics. They
are not fill proofs and must not be substituted for the later 454 first-
confirmed setup registry.

## 6. Frozen technical-only result

Final decision: `TECHNICAL_EDGE_NOT_FOUND`
Full intended macro-first strategy: `BLOCKED_BY_UNCERTIFIED_MACRO_BIAS`
Candidate: `NONE`
Champion: `NONE`
Independent audit: `PASS_PROCESS_TECHNICAL_EDGE_NOT_FOUND`

Medium-cost result across the seven frozen architectures:

| Measure | Result |
| --- | ---: |
| Eligible strategy-specific setups | 454 |
| Filled | 306 |
| No fill | 148 |
| Wins | 52 |
| Ordinary losses | 246 |
| Timeouts | 2 |
| Adverse-first ambiguities | 6 |
| Target-before-stop rate | 17.11% of 304 resolved filled trades |
| Average net R | -0.567R |
| Total net R | -173.458R |
| Worst strategy drawdown | 52.724R |

Additional findings:

- Bullish: 53 fills, -16.043R total, -0.303R average.
- Bearish: 253 fills, -157.415R total, -0.622R average.
- The pooled result was negative in 2017–2020 and 2022–2026; only 2021 was
  positive at +1.694R.
- Low/medium/high cost totals were -164.179R, -173.458R, and -203.425R.
- Every confluence strategy underperformed its direction-matched generic
  next-open control on average net R.
- All 15 CPCV test combinations were negative for every strategy that met the
  CPCV sample gate.
- The maximum effective filled-trade sample was 89, below the 100-trade ML
  gate. No ML trial ran.
- The authorized 1.5R diagnostic was also negative and was rejected.

This result is not a reason to keep changing the detector until it wins. The
frozen conclusion must remain visible in any future UI and handoff.

## 7. Macro research state

### 7.1 Intended macro contract

The original governed program requires a deterministic, category-based,
versioned, immutable, no-decay macro engine using exactly five categories:

1. `INFLATION`
2. `GROWTH`
3. `LABOUR`
4. `MONETARY_POLICY`
5. `LIQUIDITY`

It requires historical Actual, Forecast/Consensus, Previous-as-published,
release time, revisions, source lineage, and point-in-time availability. Related
events must be grouped into release bundles so a category with more indicators
does not receive more votes.

### 7.2 Public-access program outcome

Terminal outcome: `PUBLIC_HISTORY_NOT_POINT_IN_TIME_SAFE`
Secondary failure: `PUBLIC_CONSENSUS_HISTORY_UNAVAILABLE`
Access outcome: `PUBLIC_ACCESS_PARTIAL`
Candidate/champion: `NONE` / `NONE`

The pilot used 8 of a maximum 120 interactions. Six pages were reachable
without CAPTCHA, 403, 429, login bypass, subscription bypass, or proxy
rotation. However, the sample did not establish:

- historical as-published Actual vintages;
- historical Forecast/Consensus;
- Previous-as-published;
- authoritative historical release clocks;
- immutable revision lineage.

Only 1 of 10 full-collection gates passed. Therefore the compliant program did
not run bulk collection, scoring, macro-to-technical joins, or a macro-filter
PnL comparison. It normalized zero research observations and created zero
certified score snapshots.

### 7.3 Current application macro history

The application separately stores current-vintage Trading Economics Public
Chart Actual history for 21 approved U.S. event definitions. A full refresh
found 8,295 eligible observations for 2000–2026. These rows are suitable for
display and current-vintage diagnostics, not historical surprise claims.

The existing `/backtesting/nas100` page uses 8,276 rows through `2026-05-31`,
excludes June 2026, and materializes 1,379 weekly periods. Historical Forecast
is unavailable, so the page compares Actual to the prior current-vintage
observation. It visibly declares:

`CURRENT_VINTAGE_NOT_POINT_IN_TIME_SAFE`

This page must not be used as a substitute for the missing point-in-time macro
engine.

### 7.4 Historical macro-filter comparison

The frozen technical reference T0 remains:

- 306 medium-cost fills;
- 52 wins;
- 246 losses;
- 2 timeouts;
- -173.458R total net.

The compliant public-macro variants M1–M4 were not run because no certified
macro score history exists. A separate archived macro-regime projection linked
every setup to `UNKNOWN`, retained zero trades, and concluded
`INSUFFICIENT_ALIGNED_TRADES`. Zero retained trades mean inactivity, not a
profitable or rescued strategy.

## 8. What is already built in Smart MarketScope

### 8.1 Backtesting → NAS100 macro page

Route: `/backtesting/nas100`

Implemented:

- authenticated React route;
- authenticated Laravel weekly-summary and detail endpoints;
- weekly periods from 2000-01-01 through 2026-05-31;
- June 2026 exclusion;
- Bullish/Bearish/Neutral current-vintage macro classification;
- year filter, pagination, refresh, and responsive layout;
- 21-event drill-down modal;
- `—` for unavailable values;
- no visible Source column;
- explicit point-in-time warning.

Verification recorded at implementation:

- Laravel: 95 passed, 3 target-driver skips, 479 assertions.
- React: 14 suites, 63 tests passed.
- Production build: exit 0 with pre-existing warnings.

### 8.2 Existing hidden historical alignment viewer

Route: `/research/alignment-review`

The navigation link was removed at the user's request, but the read-only route,
APIs, artifacts, and tests remain preserved. It already provides most of the
infrastructure reused by the completed `NAS100 Candle` page:

- 454 frozen medium-cost setups;
- setup filters for year, timeframe, family, and outcome;
- setup selector and detector checklist;
- entry, stop, 2R target, exit, and net-R evidence;
- D1, H4, M15, M5, and M1 candle windows;
- entry/stop/target lines and confluence zone overlay;
- authenticated read-only APIs;
- allowlisted 24-character setup identifiers;
- no write/order/broker action.

The existing renderer is a local responsive SVG candlestick component. The
project does not currently depend on TradingView Lightweight Charts. Reusing
the verified SVG path is the lowest-risk first implementation; adding a new
chart dependency should occur only if the required pan/zoom interaction cannot
be met by the existing component.

## 9. Completed product task — `NAS100 Candle`

### 9.1 User-facing objective

Create a second sibling under `Backtesting` that lists the frozen
technical periods satisfying the D1 + H4 + lower-timeframe rules. Selecting a
row must open the corresponding candles so the user can inspect whether the
mechanical technical-bias logic is correctly represented.

Recommended navigation:

```text
Backtesting
├── NAS100          -> /backtesting/nas100
└── NAS100 Candle   -> /backtesting/nas100-candle
```

Both entries are leaf siblings. `NAS100 Candle` must not be nested beneath the
existing `NAS100` macro page.

### 9.2 Scope of the table

The table should consume the frozen 454 strategy-specific first-confirmed
setups. It must not rerun the detector in the browser or invent additional
periods.

Recommended visible columns:

| Column | Meaning |
| --- | --- |
| Actionable time | Frozen source wall-clock time after D1 and H4 confirmation. |
| Direction | `BULLISH` or `BEARISH`. |
| D1 sweep | Frozen daily event identity/confirmation. |
| H4 confirmation | Frozen confirming H4 bar/time. |
| Entry timeframe | M15, M5, M1, or hierarchical. |
| Confluence | `C1_OB_FVG` or `C2_FVG_BREAKER`. |
| Entry status | Filled, no fill, timeout/outcome evidence when shown. |
| View candles | Opens the evidence modal/drawer. |

Outcome filtering should remain an inspection feature, not a strategy
selection tool. The default ordering should be chronological or reverse
chronological, never best-PnL first.

### 9.3 Candle detail view

Clicking a setup should show:

- D1 candle window with EMA/trend and sweep evidence;
- H4 confirmation window;
- M15, M5, and M1 windows;
- confluence zone;
- selected OB or breaker bounds;
- FVG bounds;
- entry, stop, and target lines where frozen trade evidence exists;
- source wall-clock warning;
- detector checklist explaining why each rule passed;
- lineage identifiers and immutable artifact hashes in a detail/advanced area.

The first release should be read-only. It must contain no trade button, broker
connection, paper-order action, or editable detector threshold.

### 9.4 Required detector checklist in the UI

For each setup, show the frozen status of:

1. Completed D1 bars.
2. D1 EMA20/EMA50 direction.
3. D1 strict two-candle sweep.
4. H4 sweep within the three-bar window.
5. Actionable time.
6. FVG present and available.
7. OB or breaker present and available.
8. Strict positive overlap.
9. Correct confluence family.
10. Correct first-confirmed architecture.
11. Frozen entry/stop/target/expiry evidence when applicable.

### 9.5 What this page is not

The page is not:

- a new backtest;
- a new strategy candidate;
- a parameter optimizer;
- proof of technical edge;
- a point-in-time macro alignment result;
- a signal or probability;
- a live or paper trading surface.

It is a visual correctness and audit surface for already frozen evidence.

## 10. Current progress on `NAS100 Candle`

### Completed discovery/design and implementation

- [x] Located the frozen D1/H4/FVG/OB/breaker specifications.
- [x] Confirmed the terminal technical result and setup counts.
- [x] Confirmed actual candle coverage starts in 2008, not 2000.
- [x] Located the 454 prepared setup-detail artifacts.
- [x] Located the authenticated index/detail APIs.
- [x] Located the existing five-timeframe SVG candlestick renderer.
- [x] Confirmed the existing route is read-only and allowlist-validates setup IDs.
- [x] Identified the safe navigation structure and backward-compatible macro URL.
- [x] Determined that no new detector run or data mutation is needed.
- [x] Added sibling navigation and protected `/backtesting/nas100-candle` route.
- [x] Built the 454-row setup table with search and five bounded filters.
- [x] Reused the immutable index/detail APIs without detector recomputation.
- [x] Refactored the existing SVG renderer into a shared chart component.
- [x] Added D1/H4/M15/M5/M1 modal charts, overlays, and checklist language.
- [x] Added source-timezone, data-coverage, and rejected-strategy warnings.
- [x] Added focused filtering, renderer, route, and navigation tests.
- [x] Verified 454 index rows, 454 details, and five candle keys per detail.
- [x] Ran the full React suite, protected Laravel API tests, and production build.
- [x] Performed authenticated browser QA for filters, reset, modal, and charts.
- [x] Updated project state, next action, and implementation audit.

## 11. Proposed implementation sequence

### Phase A — Freeze display contract

1. Define the exact setup-table schema.
2. Confirm that every displayed field is already present in the frozen index or
   setup detail.
3. Freeze default ordering and filters.
4. Freeze the warning and no-trading copy.
5. Record that the page is an evidence projection, not a new experiment.

### Phase B — Reuse backend projection

1. Reuse the existing immutable alignment-review artifacts.
2. Prefer a new authenticated read-only route namespace only if necessary for
   product semantics; do not duplicate or recompute the 454 setup files.
3. Preserve allowlisted setup identifiers and 422/404 behavior.
4. Keep POST/PUT/PATCH/DELETE unavailable.

### Phase C — Build React table and candle modal

1. Add NAS100 Candle as a sibling leaf under Backtesting.
2. Preserve `/backtesting/nas100` for Macro Bias.
3. Add `/backtesting/nas100-candle`.
4. Build a chronological setup table.
5. Reuse the existing candle renderer and overlays.
6. Add the mechanical checklist and advanced lineage view.
7. Preserve persistent sidebar and native new-tab semantics.

### Phase D — Verification

1. Focused setup filtering and status tests.
2. React route/auth/navigation tests.
3. Laravel auth, invalid-ID, unknown-ID, and method-rejection tests.
4. Projection integrity: 454 index entries and 454 detail files.
5. Verify all five timeframes exist for every detail file or explicitly display
   a missing-window state.
6. Full React tests.
7. Full Laravel tests.
8. Production build.
9. Authenticated browser QA: table, filters, row click, modal, all five charts,
   keyboard access, responsive layout, and no live-trading control.

## 12. Later macro-plus-technical work

A genuine macro-filter backtest is a separate future research cycle. Before it
can begin, all of the following are required:

- licensed or independently defensible historical Actual as initially
  published;
- historical Forecast/Consensus;
- Previous-as-published and revision lineage;
- exact release/receipt timestamp with source timezone;
- nonzero usable point-in-time coverage in at least three categories;
- independently validated collection rights and provenance;
- confirmed Pepperstone NAS100 source timezone;
- confirmed point, spread, contract, and feed metadata;
- a new prospective preregistration;
- the unchanged frozen 454-setup / 1,362-scenario T0 baseline;
- no access to a protected final-holdout path during development.

If those gates pass, the macro layer may filter the frozen technical trades. It
must not alter entry, stop, target, expiry, costs, fill, or outcome. The primary
conservative join remains J0: macro evidence must be available at least 36
hours before the technical actionable source timestamp until the source
timezone is confirmed.

## 13. Known limitations and risks

| Risk | Effect | Required handling |
| --- | --- | --- |
| NAS100 source timezone unresolved | Session and release-time joins are uncertain. | Keep source wall-clock labels; no same-day macro claim. |
| Candle history begins in 2008 | Technical coverage cannot start in 2000. | Show actual coverage; never fabricate candles. |
| Historical pool is exposure-unknown | It is not a pristine final holdout. | No tuning or final-validation claim. |
| Current-vintage macro revisions | Later knowledge may contaminate historical interpretation. | Display-only label; exclude from PIT alignment. |
| Historical Forecast absent | Surprise scoring cannot be reconstructed safely. | Keep true macro backtest blocked. |
| Normalized costs are not broker facts | Economic result is not broker-specific PnL. | Report points/R only with evidence class. |
| Existing technical result is negative | UI could invite cherry-picking. | Chronological default, frozen rules, prominent final decision. |
| Outcome filters expose known results | User may select favorable examples. | Treat as audit filters; do not use for strategy selection. |
| Chart dependency temptation | New library adds bundle and maintenance risk. | Reuse the verified SVG first; add dependency only with a demonstrated need. |

## 14. Non-negotiable governance

- Do not modify raw files under `dataset/`.
- Do not access or disclose a protected final-holdout path.
- Do not use post-2026-06-28 NAS100 data for tuning or model selection.
- Do not treat NAS100 CFD, NDX, NQ, or MNQ as interchangeable.
- Do not change frozen setup inclusion, detector thresholds, or trade outcomes
  through UI work.
- Do not call current-vintage macro history point-in-time safe.
- Do not convert missing macro values into fabricated releases.
- Do not suppress the negative technical result.
- Do not claim a candidate, champion, FTMO readiness, Lucid readiness, paper
  readiness, or live readiness.
- Do not add broker connectivity or order controls.
- Preserve the dirty worktree and unrelated user changes.

## 15. Key source artifacts

### Technical specification and state

- `MLR_MECHANICAL_SPEC.md`
- `MLR_DETECTOR_SPEC.md`
- `MLR_PROGRAM_STATE.md`
- `MLR_NEXT_TASK.md`
- `research/preregistrations/macro_liquidity_reversal/MLR_PREREGISTRATION_MASTER.yaml`
- `research/preregistrations/macro_liquidity_reversal/MLR_TECHNICAL_ECONOMIC_PRIMARY.yaml`

### Frozen technical results

- `research/artifacts/macro_liquidity_reversal/MLR_TECHNICAL_PRIMARY_BACKTEST.md`
- `research/artifacts/macro_liquidity_reversal/MLR_TECHNICAL_PRIMARY_TRADES.csv`
- `research/artifacts/macro_liquidity_reversal/MLR_TECHNICAL_PRIMARY_SUMMARY.json`
- `research/artifacts/macro_liquidity_reversal/MLR_TECHNICAL_CONTROL_COMPARISON.md`
- `research/artifacts/macro_liquidity_reversal/MLR_TECHNICAL_PATH_AMBIGUITIES.csv`
- `research/artifacts/macro_liquidity_reversal/MLR_TECHNICAL_FINAL_DECISION.md`
- `research/artifacts/macro_liquidity_reversal/MLR_TECHNICAL_INDEPENDENT_AUDIT.md`

### Macro state

- `PUBLIC_MACRO_PROGRAM_STATE.md`
- `MACRO_FILTER_DECISION.md`
- `MACRO_INDEPENDENT_AUDIT.md`
- `MACRO_NEXT_TASK.md`
- `research/preregistrations/public_macro_bias/SMART_MARKETSCOPE_PUBLIC_MACRO_BIAS_001.yaml`
- `US_MACRO_2000_2026_COVERAGE_AUDIT.md`

### Existing UI evidence and implementation

- `NAS100_WEEKLY_MACRO_BIAS_BACKTESTING_TASK.md`
- `HISTORICAL_ALIGNMENT_REVIEW_UI_PREREGISTRATION.yaml`
- `HISTORICAL_ALIGNMENT_REVIEW_AUDIT.md`
- `src/components/backtesting/nas100-macro-bias.js`
- `src/components/research/alignment-review.js`
- Laravel `AlignmentReviewController`, `AlignmentReviewService`, and protected
  API routes in the sibling Laravel application.

## 16. Completion checklist for the current product task

The `NAS100 Candle` task is complete only when:

- [x] Backtesting navigation exposes NAS100 and NAS100 Candle as siblings.
- [x] Existing Macro Bias URL and behavior remain intact.
- [x] NAS100 Candle lists the frozen setup census without recomputation.
- [x] Table rows show direction, D1/H4 context, timeframe, and confluence.
- [x] Clicking a row opens D1, H4, M15, M5, and M1 candles.
- [x] The detector checklist explains the frozen rule passes.
- [x] Entry/stop/target/zone overlays reconcile to the frozen detail artifact.
- [x] Source-timezone and historical-exposure limitations are visible.
- [x] The negative technical decision is not hidden.
- [x] No current-vintage macro row is used as historical alignment input.
- [x] No live/paper/broker action exists.
- [x] Authentication and invalid setup identifiers are tested.
- [x] Focused and full test/build commands are recorded with exact outcomes.
- [x] Browser QA verifies the actual rendered interaction.
- [x] Project state and next-task documents are updated from verified evidence.

## 17. Exact next permitted action

Stop for user visual review of the completed read-only `Backtesting → NAS100
Candle` sibling. A new
empirical strategy cycle may begin only after the point-in-time macro and
instrument-metadata gates are independently satisfied and prospectively
preregistered.

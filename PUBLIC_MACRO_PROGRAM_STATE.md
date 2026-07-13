# Public Macro Program State

Schema version: `1.0.0`

Artifact ID: `PUBLIC-MACRO-PROGRAM-STATE-001`

Program: `SMART-MARKETSCOPE-PUBLIC-MACRO-BIAS-001`

Created at UTC: `2026-07-13T06:05:22Z`

Created by: `quant-research-orchestrator` and `research-cycle-reporter`

Status: `FAIL`

Terminal outcome: `PUBLIC_HISTORY_NOT_POINT_IN_TIME_SAFE`

Secondary terminal limitation: `PUBLIC_CONSENSUS_HISTORY_UNAVAILABLE`

Access outcome: `PUBLIC_ACCESS_PARTIAL`

Candidate: `NONE`. Champion: `NONE`.

## Decision

The program stopped at the mandatory public-history collection gate. Public
Trading Economics indicator pages were reachable without login or access-control
circumvention, but the sampled surface did not expose a historical as-published
release ledger with Actual, Consensus, Previous-as-published, exact release
clocks, immutable release versions, and revision lineage. Only 1 of the 10
required collection gates passed.

Full collection, normalized observation creation, the deterministic scoring
engine, point-in-time macro histories, technical joins, and macro-versus-
technical economic comparisons were not run. Their metrics are
`NOT_APPLICABLE_GATE_FAILED`, not zero.

## Evidence Envelope

- Directive SHA-256:
  `de39cb4e8cd2bd34966c18d602e48c37e979043ea9c97ab94f73982bad206de5`.
- Directive first present at: `2026-07-13T05:11:25Z`, derived from the local
  attachment filesystem birth time and used only as registry timing evidence.
- Instrument: Pepperstone MetaTrader 5 NAS100 CFD source label; broker/feed
  identity and source timezone remain unconfirmed.
- Historical exposure: `PREVIOUSLY_EXPOSED_WINDOW` through 2026-06-28.
- Protected/final-holdout accesses: `0/0`.
- Technical source-provenance commit:
  `231e27c55017e67e02872115cce4f1ab1e4e42da`.
- Durable Phase P0 freeze commit:
  `48ca2bdb1c44ad05f5207a3d33144a839185bfed`.
- Public-access evidence commit:
  `46b993c7b11b99f5f216b790c446bea42d541694`.
- Registry: 60 hash-linked events, 20 experiments, terminal event hash
  `4078a29b2e15bc782b553436054e7448a65884d18b588df61669eeb651f33f68`.
- Registry JSONL SHA-256:
  `55ef403baeab74c033015ee4bea3659a1639b56b58618ecff96cc4c956c1947b`.
- Registry CSV projection SHA-256:
  `eaa310a101f02fbd0682a1864a77665f1ef15338c809baedfffff198a383d57a`.

## Sequential Role Ledger

| Role | Outcome | Scope |
|---|---|---|
| 1. Technical Baseline Freeze Auditor | `PASS_TECHNICAL_BASELINE_FROZEN` | Independent hash, row, and byte-identical reproduction audit passed. |
| 2. Public Macro Access and Provenance Auditor | `PUBLIC_HISTORY_NOT_POINT_IN_TIME_SAFE` | Eight-interaction public pilot; full-collection gate failed. |
| 3. Database and Security Architect | `NOT_RUN_GATE_FAILED` | No schema or route changes. |
| 4. Historical Macro Collector | `NOT_RUN_GATE_FAILED` | No raw historical pages and no observations. |
| 5. Taxonomy and Scoring Engineer | `NOT_RUN_GATE_FAILED` | No scoring version or score rows. |
| 6. Point-in-Time Alignment Engineer | `NOT_RUN_GATE_FAILED` | No J0/J1/J2 joins. |
| 7. Macro-versus-Technical Researcher | `NOT_RUN_GATE_FAILED` | No M1-M5 economic comparison. |
| 8. Independent Quantitative Auditor | `PENDING_TERMINAL_AUDIT` | Must audit the stop decision, not rescue the program. |

## Technical-Only Control

- Frozen unique setup IDs: 454.
- Frozen setup/scenario rows: 1,362.
- Medium-cost fills/no-fills: 306/148.
- Medium-cost wins/losses/timeouts: 52/246/2.
- Medium-cost win rate: 17.11%.
- Medium-cost average net R: `-0.5668557855313225551546933291`.
- Medium-cost total net R: `-173.4578703725847018773361587`.
- Worst strategy drawdown: `52.72435033062773699774507294R`.
- Technical decision: `TECHNICAL_EDGE_NOT_FOUND`.
- Phase P0 validator: 1,362 rows, 454 setup IDs, 1,362 unique setup
  hashes, and 1,362 unique trade hashes.
- Isolated regeneration: six technical economic artifacts matched byte for
  byte.

## Public Access Findings

- Pilot usage: 8 of 120 maximum page/request interactions.
- Successful public HTML URLs: 6.
- Ineffective custom historical-date submission: 1.
- `robots.txt` GET: 1.
- HTTP 403/CAPTCHA/HTTP 429: 0/0/0.
- Raw pages persisted: 0 because the approved browser surface supplied DOM
  snapshots rather than raw response bodies.
- Normalized macro observations: 0.
- Earliest sampled current-series year: 1914 (CPI).
- Earliest year common across the five sampled categories: 2002.
- Latest cutoff-eligible exact-time row observed: 2026-06-25 (GDP).
- Public modern pages showed recent Actual/Previous/Consensus fields for
  selected releases, but did not demonstrate historical as-published coverage.
- Historical Forecast/Consensus coverage: unavailable in the sampled 2005,
  2010, 2015, 2020, and 2024 years.
- Historical Previous-as-published coverage: unavailable.
- Historical exact-time coverage: unavailable; recent rows only showed GMT.
- Revision semantics: unresolved because immutable version/supersession
  lineage was absent.
- Point-in-time classification: recent rows may only be
  `PUBLIC_HISTORICAL_RECONSTRUCTION`; older chart values are
  `CURRENT_REVISED_VALUE_ONLY` or `UNUSABLE`.

## Collection Gate

Only the no-bypass gate passed. The other nine gates failed: reachable
as-published historical pages, useful historical release navigation,
historical Actual first prints, historical Consensus, historical timestamps,
understandable revision semantics, a full-history parser source, three usable
categories, and provenance approval.

## Required Final-Response Matrix

| # | Required item | Result |
|---:|---|---|
| 1 | Technical-only baseline | `TECHNICAL_EDGE_NOT_FOUND`; 306 fills, -173.458R medium cost. |
| 2 | Baseline exact reproduction | Yes; Phase P0 pass and six byte-identical artifacts. |
| 3 | Public TE access | Partial; current/recent public pages loaded. |
| 4 | Public collection permitted | Page viewing was compliant; full historical collection was not approved. |
| 5 | Earliest reachable year | 1914 current CPI series; 2002 common across five categories. |
| 6 | Latest reachable date | 2026-06-25 accepted exact-time row inside the cutoff. |
| 7 | Pages sampled | 8 interactions, 6 unique successful HTML URLs. |
| 8 | Pages collected | 0 raw pages. |
| 9 | Normalized observations | 0. |
| 10-13 | Actual/Forecast/Previous/exact-time coverage | Historical as-published coverage not demonstrated; all downstream rates `NOT_APPLICABLE`. |
| 14 | Revision semantics | `SEMANTICS_UNRESOLVED`. |
| 15 | PIT classification | `PUBLIC_HISTORICAL_RECONSTRUCTION`, `CURRENT_REVISED_VALUE_ONLY`, or `UNUSABLE`; never `PIT_CERTIFIED`. |
| 16 | Category coverage | Five categories sampled; zero usable historical categories. |
| 17 | Insufficient years | 2005, 2010, 2015, 2020, and 2024 for all five sampled categories; 2026 incomplete. |
| 18-21 | Indicator/bundle/category/overall scoring | `NOT_RUN_GATE_FAILED`. |
| 22 | T0 | Frozen technical result only; no new run. |
| 23-26 | M1-M4 | `NOT_RUN_GATE_FAILED`. |
| 27-38 | Retention, performance, category, join, and outer comparisons | `NOT_RUN_GATE_FAILED`. |
| 39 | Independent audit | Pending terminal audit at this draft. |
| 40 | Candidate decision | `NONE`; no macro-filter candidate. |
| 41 | FTMO preparation | Not justified. |
| 42 | Next action | Licensed point-in-time macro source onboarding or synthetic-fixture infrastructure only. |

## Warnings And Limitations

- The chart ranges are modern revised histories, not proof of first prints.
- `first_received_at` would be null for any modern public reconstruction.
- No source assertion establishes that the current `Previous` field was the
  value known at the historical release time.
- The source timezone of the technical bars remains unresolved.
- No broker, paper, FTMO, Lucid, or live action is authorized.

## Failure Codes

- `PUBLIC_HISTORY_NOT_POINT_IN_TIME_SAFE`
- `PUBLIC_CONSENSUS_HISTORY_UNAVAILABLE`
- `RESEARCH_CYCLE_REPORTER_EVIDENCE_INSUFFICIENT`
- `EXPERIMENT_REGISTRY_EVIDENCE_INSUFFICIENT`

## Next Permitted Action

Follow `MACRO_NEXT_TASK.md`. Do not resume this failed public-history run or
construct economic results from the sampled pages.

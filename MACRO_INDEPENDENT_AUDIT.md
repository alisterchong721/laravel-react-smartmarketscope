# Macro Independent Audit

## Output envelope

- `schema_version`: `1.0.0`
- `artifact_id`: `MACRO-INDEPENDENT-AUDIT-001`
- `request_id`: `SMART-MARKETSCOPE-PUBLIC-MACRO-BIAS-001-ROLE-8-AUDIT`
- `experiment_id`: `SMART-MARKETSCOPE-PUBLIC-MACRO-BIAS-001`
- `created_at_utc`: `2026-07-13T06:16:32Z`
- `created_at_local`: `2026-07-13T14:16:32+08:00`
- `created_by`: `independent-quant-auditor`
- `git_commit`: `58cc80a68c13a8dc61c34a1d8506f1d374605836`
- `code_version`: `58cc80a68c13a8dc61c34a1d8506f1d374605836`
- `config_checksum`: `aa8e1f35491550d66e1e210189cc9f4e383a83d088513fb5bb3176cab5a9bb9f`
- `random_seed`: `NOT_APPLICABLE_DETERMINISTIC_AUDIT`
- `dataset_id`: `MACRO_TECHNICAL_BASELINE_REGISTRY_V1`
- `dataset_checksum`: `b5784ce9ab7311063b21eb33bdaf9c4218a5ade730624c00a3ddb50e468b7db7`
- `instrument`: `PEPPERSTONE_MT5_NAS100_CFD_SOURCE_LABEL_NOT_BROKER_CONFIRMED`
- `decision_timezone`: `Asia/Kuala_Lumpur`
- `source_timezone`: `UNRESOLVED`
- `historical_exposure`: `PREVIOUSLY_EXPOSED_WINDOW_THROUGH_2026-06-28`
- `status`: `FAIL`
- `decision`: `FAIL_PACKAGE_REGISTRY_INVARIANT`
- `terminal_program_outcome_review`: `ACCEPT_PUBLIC_HISTORY_NOT_POINT_IN_TIME_SAFE`
- `candidate`: `NONE`
- `champion`: `NONE`

## Decision

`[INTERPRETATION]` The terminal source decision is supported: the sampled public
Trading Economics surface did not demonstrate the historical, as-published,
versioned release evidence required by the frozen point-in-time contract. The
correct fail-closed program outcome remains
`PUBLIC_HISTORY_NOT_POINT_IN_TIME_SAFE`.

`[FACT]` `PUBLIC_CONSENSUS_HISTORY_UNAVAILABLE` is properly secondary. Public
page viewing succeeded and is recorded as `PUBLIC_ACCESS_PARTIAL`; no 403,
CAPTCHA, or 429 occurred. The secondary outcome concerns unavailable historical
Consensus coverage, not prohibited access.

`[INTERPRETATION]` The audited package nevertheless fails independent audit
because the complete 60-event registry violates the mandatory per-experiment
timestamp-order invariant for three earlier experiments. This does not reverse
the macro source veto or authorize Roles 3-7. It prevents a clean package-level
`PASS` until governance reconciles the registry without silently rewriting its
history.

## Severity-ranked findings

### P1 high - Registry event timestamps are nonmonotonic

`[FACT]` The cryptographic chain, event IDs, lifecycle order, and CSV projection
validate, but these three histories have `COMPLETED` timestamps earlier than
their own `PREREGISTERED` and `STARTED` timestamps:

| Experiment | Preregistered UTC | Started UTC | Completed UTC |
|---|---|---|---|
| `QRP-C1-ML001` | `2026-07-12T01:48:32Z` | `2026-07-12T01:48:35Z` | `2026-07-12T01:25:43Z` |
| `QRP-C1-ML002` | `2026-07-12T01:48:33Z` | `2026-07-12T01:48:36Z` | `2026-07-12T01:25:43Z` |
| `QRP-C1-ML003` | `2026-07-12T01:48:34Z` | `2026-07-12T01:48:37Z` | `2026-07-12T01:25:43Z` |

`[FACT]` The production registry validator returns `PASS` because it checks hash
and lifecycle order but does not check `event_time_utc` ordering. The bundled
Quantitative Validation Contract requires timestamps to be nondecreasing per
experiment.

`[INTERPRETATION]` Scope: this invalidates the claim that the entire registry
satisfies the required registry contract. The three-event public-macro suffix is
itself ordered (`05:11:25Z`, `05:28:29Z`, `05:49:42Z`) and its source decision
does not depend on those earlier ML outcomes, so the defect does not invalidate
the conservative macro stop.

Required response: preserve the original 60-event log and define a prospective,
versioned governance correction or migration that explicitly reconciles the
three timestamps. Do not edit or delete historical events silently. Add a
nondecreasing per-experiment timestamp assertion to the validator.

Failure codes: `EVENT_ORDER_INVALID`,
`INDEPENDENT_QUANT_AUDITOR_INVARIANT_FAILED`.

### P2 medium - Public page observations are not byte-replayable

`[FACT]` `TE_PUBLIC_PAGE_INVENTORY.json` records hashes of browser DOM snapshot
strings, but the DOM strings were not retained. Raw response bodies were also
not available or persisted. The 49-byte `robots.txt` response has a body hash,
but its body is not stored as a committed source artifact.

`[INTERPRETATION]` The access auditor's exact page observations and recorded DOM
hashes cannot be independently recomputed from this commit. This is a source
preservation limitation, not evidence that the stop was too strict: absent
replayable as-published history, the required point-in-time gate still cannot
pass. No additional page retrieval was authorized or performed by Role 8.

Required response: any future source audit should preserve permitted immutable
snapshots or explicitly downgrade fact-level reproducibility when the approved
browser surface cannot provide them.

Warning: `P1_SOURCE_SNAPSHOT_NOT_PERSISTED`.

## Artifact identity and hashes

`[FACT]` The supplied 1,434-line directive hashes to
`de39cb4e8cd2bd34966c18d602e48c37e979043ea9c97ab94f73982bad206de5`.
Both referenced attachment copies produce the same hash. The target commit
resolves to `58cc80a68c13a8dc61c34a1d8506f1d374605836`.

`[FACT]` The six Phase P1 artifacts are present at the target commit and hash as
follows:

| Artifact | SHA-256 |
|---|---|
| `TE_PUBLIC_ACCESS_AUDIT.md` | `edd2a3c406d17fe46712f22795879afdddea1ec328e6eefb91b4df9912b2905b` |
| `TE_PUBLIC_PAGE_INVENTORY.json` | `bd469fb5791ff8b7ad4e979d207cda213a82ad0d12050ea3e4e4bdca46e704c8` |
| `TE_PUBLIC_COVERAGE_SAMPLE.csv` | `8dc9fe3a37cc194bc2cecc6259c51e9fb0ded7060ab68c42d8d0cecf4ac03b30` |
| `TE_PUBLIC_FIELD_AVAILABILITY.csv` | `19f58660c00d86c4af63d2d10e64341169173be228013a7a71f4c121675a1094` |
| `TE_PUBLIC_ACCESS_LIMITATIONS.md` | `9d2b4b031f03c7049e1c105e91db53cedd0aa61ebf85bb9a15f8c119d217f3ba` |
| `TE_PUBLIC_COLLECTION_ESTIMATE.md` | `63365ec457f691c74deb72dba31a40ac2bc7b2f49fa6cf4b9adf8e0addda7c66` |

Source timestamps: the P1 inventory and access audit record
`2026-07-13T05:49:42Z`; `PUBLIC_MACRO_PROGRAM_STATE.md` records
`2026-07-13T06:05:22Z`. The exact directive hash, target commit, governance
checksum, P0 baseline checksum, and registry head bind the audit inputs.

## Phase P0 independent reproduction

`[CALCULATION]` The baseline validator recomputed 1,362 setup/scenario rows, 454
unique setup IDs, 1,362 unique setup hashes, and 1,362 unique trade hashes. The
ordered hash ledger matches all 1,362 registry rows. Its 13 artifact hashes and
code commit binding also match current bytes.

`[CALCULATION]` Isolated regeneration in the implementation's temporary
directory reproduced all six technical artifacts byte for byte:

| Artifact | Reproduced SHA-256 |
|---|---|
| `MLR_TECHNICAL_PRIMARY_TRADES.csv` | `a9cf589273faed4bd965a1a84162c1c33288265b8634b7f8f5984b50cb66d8dd` |
| `MLR_TECHNICAL_PRIMARY_SUMMARY.json` | `272009ab3f41b25cfe00c68e0f3e3f64f2ae412429227614dbd07fe5146cbc71` |
| `MLR_TECHNICAL_PRIMARY_BACKTEST.md` | `4fd066f3826d3c4088d4566060ac4b7862de3cc43070f8c483f82f5bffb07b72` |
| `MLR_TECHNICAL_CONTROL_COMPARISON.md` | `bde6544e44ca5b4c2061a3f4d5f5e5c4019d00d6c50e0ae78bb05a210611c86f` |
| `MLR_TECHNICAL_PATH_AMBIGUITIES.csv` | `75b4e5eefa470f8305f1e214ef6decbdddf32166f2c595daec2c0f8c629ba5cb` |
| `MLR_TECHNICAL_CONTROL_TRADES.csv` | `faa90c9f71dd46de6bac5cae8626541d220e8db4efbc4fef50092940263e2375` |

The source pre-completion technical registry head was
`9dc280dfbb8d2aa2e070062284ca02ccd495442aac7f585617978de340b552d8`.
The frozen medium-cost control remains 306 fills, 148 no-fills, 52 wins, 246
losses, 2 timeouts, 17.11% win rate, and approximately `-173.458R`. This is a
frozen comparator, not a candidate.

## Phase P1 schema, coverage, and gate audit

`[CALCULATION]` JSON and CSV checks reproduced:

- 8 inventory records/interactions, 6 unique successful HTML URLs, maximum
  concurrency 1, pilot ceiling 120, 0 raw pages, 0 normalized observations,
  and 0/0/0 HTTP 403/CAPTCHA/HTTP 429 outcomes;
- 30 unique coverage rows: exactly 5 categories by 6 representative years;
- point-in-time classifications: 25 `CURRENT_REVISED_VALUE_ONLY`, 4
  `PUBLIC_HISTORICAL_RECONSTRUCTION`, and 1 `UNUSABLE`;
- 75 unique field rows: exactly 15 fields for each of 5 categories; and
- 10 collection gates: exactly 1 `PASS` and 9 `FAIL`.

`[FACT]` The audit report explicitly separates `Source facts` from `Audit
inferences`. Its source facts state that current/recent public pages rendered,
recent rows exposed selected fields, the custom 2005 calendar interaction did
not yield a 2005 release ledger, and the export interaction displayed a
subscription/login notice. Its inference section does not label modern chart
history as historically point-in-time safe.

`[INTERPRETATION]` The primary outcome is the broader source-lineage failure:
historical as-published Actual, exact release clocks, Previous-as-published,
immutable versions, and revision lineage were not demonstrated. Historical
Consensus unavailability is one necessary-field failure within that broader
veto and is therefore correctly secondary. The package does not claim that
public page access itself was prohibited.

## Registry audit

`[CALCULATION]` The production validator and an independent hash calculation
agree on 60 chained events, 20 experiments, and terminal hash
`4078a29b2e15bc782b553436054e7448a65884d18b588df61669eeb651f33f68`.
The CSV projection regenerates byte-identically from JSONL. The prior 57-event,
19-experiment prefix independently validates to
`c1d19f46dffbbcf62fb1197f3b42aa646f260171660f490ae680cb02d7365c4f`.

`[FACT]` The public-macro experiment has exactly three events:
`PREREGISTERED -> STARTED -> FAILED`. They bind the exact directive hash, record
zero trials, and end in `PUBLIC_HISTORY_NOT_POINT_IN_TIME_SAFE`. That suffix is
chronological and has no event after terminal state.

`[INTERPRETATION]` Cryptographic append-only integrity passes. Full contract
integrity fails only as described in P1 because the production validator omits
the mandatory timestamp-order assertion.

## Zero-work and prohibited-action confirmation

`[FACT]` The target commit contains no `MACRO_RAW_MANIFEST.yaml`, normalized
manifest, score histories, bias histories, join report, macro-versus-technical
comparison, category-contribution report, or walk-forward report. The public
macro artifact directory contains only the frozen baseline registry and three
registry-event payloads.

`[FACT]` The diff from the Phase P0 freeze commit through the target contains
only the six P1 evidence artifacts, the registry/state/decision/next-task files,
and the three event payloads. It contains no dataset, technical outcome,
collector, database, scoring, alignment, comparison, paper, broker, or live
implementation change.

`[INTERPRETATION]` Within the committed evidence and executed audit commands,
protected/final-holdout access is 0/0, post-2026-06-28 market outcomes were not
used, and no broker, FTMO, Lucid, paper, or live action occurred. This is a
repository-evidence confirmation, not an operating-system forensic audit.

## Deterministic tests and exact results

Commands were run from the repository root with no write to audited artifacts.
Mutation tests used `tempfile.TemporaryDirectory` only.

1. `git rev-parse 58cc80a`
   - Exit `0`; result
     `58cc80a68c13a8dc61c34a1d8506f1d374605836`.
2. `shasum -a 256 <directive-attachment>`
   - Exit `0`; both attachment copies returned
     `de39cb4e8cd2bd34966c18d602e48c37e979043ea9c97ab94f73982bad206de5`.
3. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m smartmarketscope_quant.public_macro_bias.baseline_freeze --repo-root . --validate-only`
   - Exit `0`; `PASS_TECHNICAL_BASELINE_FROZEN`, 1,362 rows, 454 setup IDs,
     1,362 unique setup hashes, and 1,362 unique trade hashes.
4. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m smartmarketscope_quant.public_macro_bias.baseline_freeze --repo-root . --verify-reproduction-only`
   - Exit `0`; `PASS_BYTE_IDENTICAL_REPRODUCTION`, 6 artifacts, hashes listed
     above.
5. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m unittest research.tests.test_public_macro_bias_baseline_freeze -v`
   - Exit `0`; 5 tests passed.
6. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -c 'from pathlib import Path; from smartmarketscope_quant.governance.registry import validate_registry; import json; print(json.dumps(validate_registry(Path("EXPERIMENT_REGISTRY.jsonl")), sort_keys=True))'`
   - Exit `0`; production validator reported `PASS`, 60 events, 20
     experiments, and the expected terminal hash.
7. `git show 58cc80a:EXPERIMENT_REGISTRY.jsonl | jq -s 'group_by(.payload.experiment_id) | map(select(([.[].payload.event_time_utc] | . != sort))) | map({experiment_id: .[0].payload.experiment_id, times: [.[].payload.event_time_utc]})'`
   - Exit `0`; returned the three nonmonotonic experiment histories in P1.
8. The first inline independent audit harness exited `1` at its prospective
   assertion that every experiment timestamp sequence was nondecreasing. This
   failed-first result is retained; it exposed P1 and changed no file.
9. The corrected diagnostic harness exited `0` while retaining
   `registry_timestamp_invariant=FAIL:3_experiments_nonmonotonic`. Positive
   checks passed for the chain, byte-identical projection, 57-event backward
   prefix, P0 hash ledger, six P1 hashes, schemas, counts, and 1/10 gate.
10. Temporary-copy negative checks failed closed for interrupted JSON, payload
    tampering, duplicate registry event ID, an event after terminal state,
    duplicate P1 page ID, malformed inventory JSON, duplicate coverage ID,
    and a missing field-availability row.
11. The request-budget boundary accepted exactly 120 interactions and rejected
    121. An empty registry is accepted only as a structurally empty initial log;
    the objective-specific audit separately requires and verified 60 events.
12. Concurrent-write testing is `NOT_APPLICABLE`: Role 8 performed no append,
    update, collector, or multi-writer operation.

## Domain-method applicability

`NOT_APPLICABLE_GATE_FAILED` applies to macro costs, fills, rolls, drawdown,
overlaps, trial selection, parameter stability, concentration, regimes,
purging, embargo, CPCV, walk-forward, scoring, joins, and overrides. Roles 3-7
did not run, there are zero macro observations and zero trade-to-bias links, and
no macro market outcome exists to audit. Returning a numeric zero or economic
performance conclusion for these methods would be misleading.

The frozen technical comparator keeps gross, cost, and net results distinct,
but Role 8 did not recalculate or optimize technical strategy logic. No
statistical method, candidate promotion, or deployment readiness claim is made.

## Warnings, assumptions, limitations, and unresolved questions

Warnings:

- `P1_SOURCE_SNAPSHOT_NOT_PERSISTED`.
- `CURRENT_STATE.md` and root `NEXT_TASK.md` predate the terminal public-macro
  state; program-specific state and next action are in
  `PUBLIC_MACRO_PROGRAM_STATE.md` and `MACRO_NEXT_TASK.md`.

Assumptions:

- Relevant tracked files in the working tree matched target commit
  `58cc80a68c13a8dc61c34a1d8506f1d374605836` when commands were run.
- The attachment filesystem birth time is accepted only as the registry's
  disclosed prospective timing evidence; its exact content hash is independently
  reproduced.
- Repository evidence is the authorized audit boundary; no external system or
  browser was revisited.

Limitations:

- DOM and raw response bodies are absent, so P1 page facts cannot be byte-replayed.
- The technical source timezone and broker/feed identity remain unresolved.
- The historical NAS100 pool is exposed and is not a pristine final holdout.
- No OS-level network, browser-history, broker, or credential forensic audit was
  authorized.

Unresolved questions:

- Which immutable governance mechanism will reconcile the three historical
  registry timestamps while preserving the original log bytes?
- Can a licensed provider supply exact as-published Actual, Consensus,
  Previous, release clocks, revisions, and permitted immutable snapshots for at
  least three frozen categories?

## Failure codes and acceptance veto

Failure codes:

- `EVENT_ORDER_INVALID`
- `INDEPENDENT_QUANT_AUDITOR_INVARIANT_FAILED`

Acceptance/veto:

- Terminal source veto: `ACCEPT_PUBLIC_HISTORY_NOT_POINT_IN_TIME_SAFE`.
- Independent package audit: `FAIL`.
- Historical macro-filter candidate: `NONE`.
- Automatic promotion, FTMO preparation, Lucid preparation, paper trading,
  broker connection, and live action: `VETOED`.

## Next permitted action

First reconcile the registry timestamp invariant prospectively without
overwriting or deleting the original chain, add the missing validator assertion,
and rerun independent package validation. Preserve the terminal public-source
failure. Do not run Roles 3-7 from the sampled public pages.

After governance reconciliation, follow `MACRO_NEXT_TASK.md`: onboard and
independently certify a licensed point-in-time provider under a new prospective
child protocol, or build explicitly labeled synthetic-fixture infrastructure
without economic comparison.

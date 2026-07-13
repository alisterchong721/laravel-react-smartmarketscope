# Registry Chronology Reconciliation

## Output envelope

- Schema version: `1.0.0`
- Artifact ID: `REGISTRY-CHRONOLOGY-RECONCILIATION-R0-001`
- Request ID: `SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001-R0`
- Phase: `R0_RESEARCH_REGISTRY_CHRONOLOGY_REPAIR`
- Created at UTC: `2026-07-13T06:51:33Z`
- Created by: `registry-chronology-reconciliation-auditor`
- Base Git commit: `e23578de32a38881a23695fe225d9c63541628f8`
- Governance config SHA-256: `aa8e1f35491550d66e1e210189cc9f4e383a83d088513fb5bb3176cab5a9bb9f`
- Status: `INCONCLUSIVE`
- Decision: `REGISTRY_CHRONOLOGY_UNRESOLVED`
- Failure codes: `EVENT_ORDER_INVALID`, `EXPERIMENT_REGISTRY_TIMING_INVALID`

## Decision

The registry's cryptographic append-only integrity passes, but its historical
lifecycle chronology cannot receive a clean `PASS`. Three Phase I experiments
record `COMPLETED` metadata earlier than their own `PREREGISTERED` and `STARTED`
metadata. The exact corrected completion instants cannot be proven from
immutable contemporaneous evidence, so no replacement timestamp was created.

One supplemental `CHRONOLOGY_RECONCILIATION` event was appended. It discloses
the defect and binds every affected original event by ID, original timestamp,
event hash, prior-event hash, and canonical payload hash. It does not become an
experiment lifecycle row and does not replace any affected terminal payload or
metric.

This outcome does not block subsequent read-only macro dataset construction. It
does block a clean registry claim and any final champion claim until a stronger
governance resolution is independently accepted.

## Affected original events

| Experiment | Event type | Original event ID | Original UTC | Original event hash |
| --- | --- | --- | --- | --- |
| `QRP-C1-ML001` | `PREREGISTERED` | `QRP-C1-ML001-PREREGISTERED` | `2026-07-12T01:48:32Z` | `283927432cc51b4b0914e23e28744884bff23952033ad554909796b3146c3606` |
| `QRP-C1-ML001` | `STARTED` | `QRP-C1-ML001-STARTED` | `2026-07-12T01:48:35Z` | `f71577bd7d0b52230ab15995a261ee8a13a25263bc613b8b63500b7ddbdb9a38` |
| `QRP-C1-ML001` | `COMPLETED` | `QRP-C1-ML001-COMPLETED` | `2026-07-12T01:25:43Z` | `fd7ec61f5b7f531b456fdebe5adf58e97eb0e54432cb3214e7351468bc0cf629` |
| `QRP-C1-ML002` | `PREREGISTERED` | `QRP-C1-ML002-PREREGISTERED` | `2026-07-12T01:48:33Z` | `07866d4d5db452017970c2236fc5f40147df9d229bebaf29ff58a7f23290b788` |
| `QRP-C1-ML002` | `STARTED` | `QRP-C1-ML002-STARTED` | `2026-07-12T01:48:36Z` | `f37270604c6e05a5263d1da3fe1a1520a103ff095327351447d36c3ca3412eb8` |
| `QRP-C1-ML002` | `COMPLETED` | `QRP-C1-ML002-COMPLETED` | `2026-07-12T01:25:43Z` | `5b5258538fb2f9c9d0a622637d4ca171137ce4407364d43e1eab9f1d0e6e4428` |
| `QRP-C1-ML003` | `PREREGISTERED` | `QRP-C1-ML003-PREREGISTERED` | `2026-07-12T01:48:34Z` | `12610fd51bf09a1793704fff8691c112da0c52b3ab3bbc75261a521941334c39` |
| `QRP-C1-ML003` | `STARTED` | `QRP-C1-ML003-STARTED` | `2026-07-12T01:48:37Z` | `a4b67c450c5e06fdcaabf4ff76df18db0013dd677302edaa772f25b9176a2965` |
| `QRP-C1-ML003` | `COMPLETED` | `QRP-C1-ML003-COMPLETED` | `2026-07-12T01:25:43Z` | `abeb54c886a6e55663aec2fe099c3e3429ceb184a565ed1e71fe3a0570d8d5b9` |

Each experiment has two violated comparisons: preregistration is later than the
recorded completion metadata, and start is later than the recorded completion
metadata. `REGISTRY_CHRONOLOGY_ISSUES.csv` retains the prior-event and payload
hashes in addition to the event hashes shown here.

## Evidence-supported likely cause

`[FACT]` `research/config/ml_baselines_phase_i.json:5` freezes
`artifact_created_at_utc` as `2026-07-12T01:25:43Z`.

`[FACT]` `research/src/smartmarketscope_quant/ml_baseline/runner.py:457`
assigns that static artifact timestamp directly to each generated completion
payload's `event_time_utc`. The source file SHA-256 is
`3caf012fcb827abec03ace67985d33af240a76d09722b17737e1c738e01d5b9f`.

`[FACT]` Each generated Phase I completion payload exactly equals its terminal
registry payload. The frozen payload hashes are:

- `QRP-C1-ML001`: `868730efeae67759cec7b359c09152e5e327c224a1c61fb721dad096a8bd97bb`
- `QRP-C1-ML002`: `26fd9948ec49e6081c6a59ebe306c213ea8bad0af28cb0e99544b805eddac88b`
- `QRP-C1-ML003`: `c7eb4bfab2d17b22f42dabe9e76577d9ffc0aeaaeed42f32c084c8c7660091ff`

`[INTERPRETATION]` The likely cause is static artifact-time reuse as lifecycle
metadata, not a change to model output or metrics. This is evidence-supported as
a likely metadata cause; it is not promoted into an exact replacement time.

## Defensible partial ordering and unresolved exact time

Current filesystem metadata places the locked preregistration files around
`2026-07-12T01:47:53Z` to `01:48:24Z` and the generated Phase I result,
training-manifest, and completion-payload files around `01:51:24Z` to
`01:51:53Z`. That supports the interpreted partial order:

`PREREGISTERED <= STARTED < RESULT_AND_EVENT_ARTIFACT_PERSISTENCE`

Filesystem birth and modification times are mutable. They cannot establish the
exact instant at which calculation completed. Accordingly:

- corrected completion time: `NULL` for all three experiments;
- chronology resolution: `UNRESOLVED_EXACT_COMPLETION_TIME`;
- no historical timestamp was edited;
- no corrected timestamp was inserted into the affected experiment histories.

## Result-content impact

No result-content change was detected. For every affected experiment:

- the generated completion payload exactly matches the registry payload;
- the decision matches `research/artifacts/models/phase_i/summary.json`;
- probability metrics match the Phase I summary;
- all threshold-scenario metrics match the Phase I summary; and
- training-manifest hashes remain frozen.

The Phase I summary SHA-256 is
`f57e4613865e82dae21bc6213cc5f3602f2c899280f40216c8edb962e8c7dfb7`.
This finding is limited to content consistency; it does not cure the lifecycle
metadata defect.

## Append-only proof

Before reconciliation:

- event count: `60`;
- byte length: `123799`;
- registry SHA-256:
  `55ef403baeab74c033015ee4bea3659a1639b56b58618ecff96cc4c956c1947b`;
- last event hash:
  `4078a29b2e15bc782b553436054e7448a65884d18b588df61669eeb651f33f68`.

After reconciliation:

- total event count: `61`;
- lifecycle event count: `60`;
- reconciliation event count: `1`;
- experiment count: `20`;
- registry SHA-256:
  `b7cb999912aed3108d12fcdb62c079d3c51610214a419a3b5fc72ac19c65d044`;
- last/reconciliation event hash:
  `29e88a1577792dd450732bf53b5fcf35a5fc319a2bed978b97282569e6680e69`.

The first `123799` bytes of the current registry reproduce the original SHA-256
exactly. Original update count is `0`; original delete count is `0`; appended
event count is `1`.

The event payload is
`research/artifacts/governance/registry_events/REGISTRY-CHRONOLOGY-RECONCILIATION-R0-001.json`
with SHA-256
`25b19752e69f18769d7c3c68417d4f6ac4adf73211cf09eb15128f2140e33083`.

## CSV projection proof

The CSV remains a 20-row experiment projection. Supplemental reconciliation
events are deliberately excluded. Its SHA-256 before and after reconciliation
is unchanged:

`eaa310a101f02fbd0682a1864a77665f1ef15338c809baedfffff198a383d57a`

Regenerating the projection from the 61-event JSONL produces the same bytes.
No affected experiment row, terminal decision, metrics field, or last lifecycle
event hash was overwritten.

## Validator behavior and compatibility

`research/src/smartmarketscope_quant/governance/registry.py` now:

1. validates canonical UTC lifecycle timestamps;
2. enforces nondecreasing per-experiment lifecycle order;
3. returns `FAIL / EVENT_ORDER_INVALID` for an undisclosed defect;
4. validates an exact hash-linked reconciliation against the original byte
   prefix and every affected event reference;
5. returns `INCONCLUSIVE / REGISTRY_CHRONOLOGY_UNRESOLVED` after a valid
   unresolved disclosure, never a clean `PASS`;
6. transactionally rejects malformed or duplicate reconciliation events before
   writing;
7. excludes supplemental events from the experiment CSV; and
8. preserves legacy `read_registry()` behavior for lifecycle consumers while
   exposing supplemental events through `include_supplemental=True`.

Direct raw-event consumers in the Phase J and Cycle 2 registry utilities now
ignore non-experiment governance events when building experiment maps.

## Verification commands and exact results

1. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m unittest research.tests.test_cycle2_governance.Cycle2GovernanceTest.test_cycle_two_registry_is_terminal_after_independent_validation -v`
   - Exit `0`; `1` focused Cycle 2 registry-checkpoint test passed.
   - Recomputes the complete hash chain of the frozen `57`-lifecycle-event,
     `19`-experiment prefix and verifies its terminal hash is
     `c1d19f46dffbbcf62fb1197f3b42aa646f260171660f490ae680cb02d7365c4f`.
   - Later append-only experiment lifecycle and supplemental governance events
     are permitted and are not misrepresented as part of the Cycle 2 prefix.
2. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m unittest research.tests.test_governance -v`
   - Exit `0`; `11` tests passed.
   - Covers valid chronology, invalid order, original chain preservation,
     append-only reconciliation, duplicate and malformed reconciliation,
     projection consistency, and no historical rewrite.
3. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m unittest discover -s research/tests`
   - Exit `0`; all `183` tests passed with zero failures and zero errors.
4. `git diff --check`
   - Exit `0`.

An earlier full-suite failed-first run also exposed that supplemental events
could reach a legacy Phase I payload map without an `experiment_id`. The
registry API compatibility boundary was corrected, focused Phase I/Phase J
tests then passed, and the final full suite contains no such error. A subsequent
failed-first full-suite run exposed the stale Cycle 2 global-count assertion;
the test now validates the immutable Cycle 2 prefix rather than treating it as
the current global registry. Both failed-first results are retained in
`REGISTRY_CHRONOLOGY_VALIDATION.json` context.

## Scope and prohibitions

No macro data, technical setup/trade, strategy rule, React/Laravel file,
dataset/raw file, broker connection, paper action, protected/final holdout, or
live path was touched. No experiment metrics or decisions were changed. No
champion or deployment claim is authorized.

## Next permitted action

Proceed sequentially to the Existing Macro Evidence and ALFRED Salvage Auditor.
Retain `REGISTRY_CHRONOLOGY_UNRESOLVED` as a disclosed governance caveat and
final-champion veto.

# Macro Regime Database Architecture

## Output envelope

- `schema_version`: `1.0.0`
- `artifact_id`: `MACRO-REGIME-DATABASE-ARCHITECTURE-001`
- `request_id`: `SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001-ROLE-4`
- `program_id`: `SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001`
- `protocol_id`: `MACRO_REGIME_DAILY_H4_V1`
- `created_at_utc`: `2026-07-13T07:44:33Z`
- `decision_timestamp`: `2026-07-13T15:44:33+08:00`
- `created_by`: `Smart MarketScope Macro Database Architect`
- `git_commit_before_role`: `db0670af9d1227346b94018b78211906ac6815ae`
- `status`: `PASS`
- `decision`: `BUILD_SEPARATE_VERSIONED_MACRO_SCHEMA_REUSE_LINEAGE_PATTERNS`
- `experiment_id`: `NOT_APPLICABLE_NON_EMPIRICAL_ARCHITECTURE`
- `random_seed`: `NOT_APPLICABLE_DETERMINISTIC_SCHEMA_VALIDATION`
- `instrument`: `NAS100_CFD_SOURCE_LABEL_NOT_BROKER_CONFIRMED`
- `instrument_use_in_role`: `NOT_APPLICABLE_ARCHITECTURE_ONLY`
- `final_holdout_access_count`: `0`
- `protected_forward_access_count`: `0`
- `post_2026_06_28_market_outcome_access_count`: `0`
- `network_requests`: `0`
- `macro_observations_collected`: `0`
- `database_rows_written_outside_disposable_validation`: `0`
- `experiment_trials_created`: `0`
- `paper_or_live_actions`: `0`

## Decision

`[INTERPRETATION]` Build a separate, versioned 11-table macro evidence schema. Reuse Laravel's runtime, transactions, migrations, locks, Sanctum/policy pattern, and the useful lineage/redaction patterns in `research_news_*`. Do not reuse the `fundamental_data` table, its mutable model, its public sync/store surface, or the news tables themselves.

`[FACT]` `fundamental_data` is an economic-calendar presentation contract. It stores mutable Actual/Forecast/Previous/impact fields and the collector updates existing rows in place. It has no vintage identity, raw-body artifact, supersession chain, conservative effective timestamp, scoring/config/code/registry hashes, or database append-only enforcement.

`[FACT]` The news-lineage implementation provides UUIDs, hashes, redaction checks, a transaction, `lockForUpdate`, and revision chains. It remains news-specific, stores JSON bodies in database rows, and has no database trigger preventing UPDATE or DELETE. It is a pattern source, not a macro table to extend.

`[FACT]` The sibling Laravel backend is Laravel `12.39.0` on PHP `8.2.4`, but it has no Git repository. The actual target engine/version is also unresolved. Role 4 therefore did not place unreviewed executable migration/model/service files in that directory and did not inspect or modify a user/production database.

`[INTERPRETATION]` The selected change is the smallest one that satisfies the immutable research contract without weakening existing application behavior: freeze a target schema, prove its invariants in disposable SQLite, and require a separately reviewed Laravel/target-driver translation before Role 5 collection. This `PASS` approves the architecture artifact only. It is not a production, deployment, data-coverage, scoring, or strategy pass.

The full component inventory and decision evidence are in `MACRO_REGIME_DATABASE_INVENTORY.csv`.

## Build-versus-reuse comparison

| Option | Decision | Maintenance/security/data-quality assessment |
| --- | --- | --- |
| Reuse `fundamental_data` | Reject | Lowest initial code cost, but it would silently inherit mutable surprise/calendar semantics and cannot represent the frozen point-in-time contract. |
| Extend `fundamental_data` | Reject | Adding dozens of nullable lineage columns would preserve in-place updates and mix presentation data with immutable evidence. Rollback and access control would remain ambiguous. |
| Reuse `research_news_*` tables | Reject | Source-run/revision ideas are useful, but story identity, publication timing, sentiment hashes, and protected-forward roles are the wrong domain. |
| Create a generic cross-domain evidence super-table | Reject | It broadens the task, increases nullable fields, and creates shared migration/security risk without evidence of another consumer. |
| External database/service | Defer | Could isolate writes, but no operational need, service owner, deployment boundary, or target infrastructure is approved. |
| Separate macro tables inside Laravel | Select | Explicit keys, constraints, roles, retention, and rollback are testable; the tables bind the Role 2/3 contracts without changing application calendar behavior. |

`[INTERPRETATION]` The main cost is 11 new tables plus driver-specific triggers and service tests. That cost is justified because an immutable source run, raw body, observation version, derived state, event ledger, technical link, and backtest run have different identities and retention rules. Collapsing them would remove audit boundaries rather than simplify them.

## Frozen upstream contract

### Role 2 retained evidence

`[FACT]` The retained ALFRED bundle contains 25 unique source-run IDs and 25 unique raw paths. There are 23 distinct payload hashes because two pairs of source responses are byte-identical; identical bytes do not collapse separate source-run/raw-artifact identities.

`[FACT]` The 1,730 eligible observation versions reference the five `NEW_AND_REVISED_OBSERVATIONS` runs among those 25. The schema proof imports all 25 runs, all 25 raw-artifact identities, and all 1,730 observation versions. It preserves 456 first prints and 1,274 revisions. This distinction is deliberate:

| Contract count | Value |
| --- | ---: |
| Source-run identities in retained bundle | 25 |
| Raw-artifact path identities in retained bundle | 25 |
| Distinct raw payload SHA-256 values | 23 |
| Observation-bearing source runs referenced by eligible CSV | 5 |
| Immutable observation versions | 1,730 |

Category counts remain INFLATION `489`, LABOUR `921`, GROWTH `214`, MONETARY_POLICY `106`, and LIQUIDITY `0`. All 1,730 rows remain `VINTAGE_SAFE_WITH_DELAY` under `J0_CONSERVATIVE_36H`; no exact historical release-minute or first-receipt claim is added.

### Role 3 frozen source plan

`[FACT]` The schema validator binds the exact 34-route source census: 5 existing-evidence, 19 bounded-collection, 2 unresolved, 1 current-revised-only, 4 key/license-review, and 3 rejected routes.

`[INTERPRETATION]` Only `APPROVED_FOR_BOUNDED_COLLECTION` is a Role 5 collection allowlist decision. `CURRENT_REVISED_HISTORY_ONLY` remains reconciliation-only. Rejected or unresolved routes cannot become collectible because a URL responds or a current download exists.

## Target entities and ownership

| Table | Immutable identity and purpose | Principal constraints/indexes |
| --- | --- | --- |
| `macro_source_providers` | Versioned provider/source-family row | Unique provider code/version; official/public status; no update/delete. |
| `macro_source_runs` | One terminal source attempt, including failures/partials | Provider FK; route/series; request/vintage ranges; start/end; status; row count; collector/parser/config/raw hashes; parent resume; redacted error; idempotency key. |
| `macro_raw_artifacts` | One retained raw-body identity | Run FK; private immutable path; media/compression/bytes/SHA-256; source reference; same-route supersession; no global hash uniqueness. |
| `macro_observations` | One never-overwritten source version | Provider/run/raw FKs; route/series/indicator/category/bundle; reference/vintage/availability/effective times; raw and numeric values; revision chain; PIT class; payload/code/config/registry hashes. |
| `macro_indicator_states` | One calculation-version state for an observation | Observation FK; prior-only transformations; coverage/stress; continuous/discrete score; scoring/code/registry hashes. |
| `macro_release_bundle_states` | One effective bundle version | Canonical component-state JSON/hash; coverage; score; effective time and scoring lineage. |
| `macro_category_states` | One of exactly five effective category versions | Exact category CHECK; active bundle JSON/hash; stress JSON/hash; score/status and scoring lineage. |
| `macro_regime_snapshots` | One overall point-in-time regime version | Five nullable category-state FKs; category/base/interaction/final bounds; valid-category count; bias; source lineage/hash. |
| `macro_event_update_ledger` | One readable macro update transition | Observation/run/state/snapshot FKs; before/after indicator, bundle, category, interaction, final score, bias, reason, and lineage hashes. |
| `macro_technical_links` | One frozen technical setup/trade to as-of snapshot link | Snapshot FK; actionable and macro effective times; category/final scores; direction/filter/J0-J2 rule; baseline/manifest/config/code/registry hashes. |
| `macro_backtest_runs` | One terminal hash-bound comparison attempt | Baseline/macro/scoring/join/result hashes; variant/period/artifact manifest; terminal status and chronology. |

### Key semantics

`[FACT]` All 11 tables are append-only in the proof schema. Every table has both a no-UPDATE and no-DELETE trigger. Provider changes append a new `provider_version`; a source retry/resume appends a new source-run row; a revised observation appends `revision_number + 1`; derived recalculation appends a new calculation/scoring version.

`[FACT]` Six lineage triggers now reject cross-identity observation supersession; source-run/raw-artifact mismatches; invalid raw-artifact supersession; cross-wired, future, missing, or score-inconsistent named category states in a snapshot; wrong event observation/state/snapshot lineage; and technical copies that differ from their linked snapshot. Together with the 22 append-only triggers, the disposable schema contains 28 triggers.

`[FACT]` A revision preserves provider, route, source series, internal indicator, category, release bundle, and reference date. A snapshot requires each named state ID and score to be jointly null or jointly non-null, to name the correct category, to carry the same discrete score, and to be effective no later than the snapshot; `valid_category_count` equals the number of non-null named scores.

`[FACT]` An event now binds its indicator state to the source observation/indicator, its bundle and category states to the named bundle/category, all state calculation/effective times to no later than the event, all scoring/code/registry hashes to the event lineage, and the after snapshot to the event effective time, updated category-state identity, copied after scores, interaction flags, and bias. A technical link copies the five category scores, final score, bias, effective time, and scoring version exactly from its snapshot.

`[FACT]` Foreign keys use restrictive behavior. No evidence relationship cascades on delete. Runtime roles do not receive UPDATE, DELETE, ALTER, or DROP permissions.

`[ASSUMPTION]` SQLite text timestamps are a deterministic architecture proof. The Laravel translation must use canonical UTC `DATETIME(6)` (or the target engine's equivalent), retain the original source timestamp/timezone separately, and convert `America/New_York` to `Asia/Kuala_Lumpur` with date-aware timezone rules.

`[LIMITATION]` Bundle/category lineage arrays are canonical JSON plus SHA-256 because an array cannot have ordinary element-level foreign keys. The Role 6 scoring transaction and export validator must prove every component ID exists, is of the correct type, and is effective no later than the derived row. This open control is recorded as `DBR-011`.

## Data flow and transaction boundaries

```text
frozen route allowlist
  -> paced official request/file read
  -> private temporary raw bytes + streaming SHA-256
  -> fsync + atomic rename
  -> one DB transaction:
       terminal source run
       + raw artifact metadata
       + immutable observation versions
  -> independent raw/hash/row/coverage export validation
  -> later scoring transaction:
       indicator -> bundle -> category -> snapshot -> event ledger
  -> later as-of join:
       snapshot -> technical link
  -> later terminal comparison record:
       backtest run
```

`[INTERPRETATION]` `macro_source_runs` is append-only, so a collector does not insert `STARTED` and later update it. It records timing in memory and appends one terminal `COMPLETED`, `FAILED`, or `PARTIAL` attempt. A resume is a new row linked through `parent_resume_run_id`.

The write protocol is:

1. Acquire a per-route mutex. Reject any route not frozen as `APPROVED_FOR_BOUNDED_COLLECTION`.
2. Stream bytes to a private same-filesystem temporary file while hashing. Do not write beneath `public/`.
3. Validate response type, parser semantics, units, requested period, source identity, and raw SHA-256; then fsync and atomically rename.
4. In one database transaction, append the terminal source-run row, raw-artifact metadata, and observation versions. Lock the latest same-identity observation before assigning a revision number.
5. An identical idempotency key plus identical hashes is a no-op. An identity collision with different bytes becomes a new run/artifact version or fails closed; it never overwrites.
6. Retry only transient database/deadlock failures with bounded exponential backoff and jitter. Parser, semantic, hash, source-identity, licensing, and time-order errors are terminal for that attempt.
7. If the database transaction fails after raw rename, quarantine the unattached artifact. Attach it on a later run only after full byte/hash revalidation.
8. A crash or incomplete traversal appends a `PARTIAL` attempt; the next attempt links its parent and resumes from the last independently verified checkpoint.

## Access control and security

`[FACT]` No Role 4 API, command, collector, scheduler, model, or page was added. The existing fundamental prefix includes public write/sync endpoints, so it is explicitly not a macro research write surface.

Future runtime roles are separated:

- `macro_collector`: insert run/raw/observation rows only;
- `macro_scorer`: select source evidence and insert indicator/bundle/category/snapshot/event rows only;
- `macro_aligner`: select snapshots and insert technical links only;
- `macro_backtester`: select links and insert terminal backtest-run rows only;
- read API: authenticated, policy-authorized, read-only, with negative IDOR tests and no raw filesystem path disclosure.

Request parameters and error text must be redacted before insertion. Secret-bearing keys, credential values, arbitrary URLs, and raw authentication headers are prohibited in tables, logs, artifacts, fixtures, and exports.

## Retention, export, and validation

`[FACT]` Raw response bytes are authoritative evidence. A DOM or content hash without retained permitted bytes is insufficient. The database stores the private path, content type, compression, byte length, retrieval time, source reference, and verified SHA-256.

`[INTERPRETATION]` Evidence retention is indefinite until a prospective governance policy authorizes archive movement. A move is copy -> hash verify -> append relocation manifest -> reader switch -> independent verification. It must not silently mutate an existing raw-artifact path.

Deterministic exports use the sort keys frozen in `research/config/macro_regime_database_architecture.json`. Every export manifest includes table row counts, schema/config/code/registry hashes, ordered output hashes, and a full raw-file existence/size/hash reconciliation. Null/UNKNOWN is preserved; it is never serialized as numeric zero.

## Migration and rollback design

### Prospective Laravel migration

1. Put the sibling Laravel backend under version control or establish an equivalent immutable patch/rollback baseline.
2. Confirm the exact MySQL/MariaDB engine and version. Verify CHECK, JSON, fractional UTC datetime, FK, and trigger behavior for that engine.
3. Translate the frozen table order into one reviewed Laravel migration. Use explicit names for indexes, unique keys, FKs, and driver-specific triggers.
4. Translate append-only triggers using the target engine's fail-closed mechanism (for example, MySQL/MariaDB `SIGNAL SQLSTATE '45000'`). Eloquent guards may provide clearer errors but are not the security boundary.
5. Run `migrate:fresh` and all negative tests on a clean disposable target-driver database. Repeat the migration to prove idempotent deployment behavior and inspect the generated schema.
6. Verify the empty-schema down path in exact reverse FK order. Do not run it after evidence exists.
7. Add runtime database roles/grants, private raw storage, collector/scorer services, commands, and integration tests only in their owning later roles.

### Rollback

`[FACT]` Role 4 rollback is deletion of only these new version-controlled architecture artifacts; the Laravel sibling and user databases are unchanged.

`[INTERPRETATION]` A future destructive down migration is permitted only when every macro table is empty. After any evidence exists, rollback means quiesce writers, export and independently verify all tables and raw bytes, create a new schema version, copy/append records, switch readers, and retain the old schema read-only. Dropping populated evidence tables is prohibited.

The disposable proof dropped all 11 empty tables in reverse order successfully.

## Risk register

`MACRO_REGIME_DATABASE_RISK_REGISTER.csv` records 17 risks, their evidence, controls, owners, and next actions. The principal unresolved or review-significant items are:

- `DBR-001`: Laravel sibling has no Git rollback;
- `DBR-002`: target MySQL/MariaDB engine/version unresolved;
- `DBR-004`: existing public fundamental write/sync surface is not reusable;
- `DBR-010`: private raw-storage backend/retention authority not approved;
- `DBR-011`: derived JSON component arrays need transactional/export FK validation;
- `DBR-012`: registry chronology caveat remains a final-champion veto;
- `DBR-013`: LIQUIDITY verified coverage remains zero;
- `DBR-014`: destructive rollback after evidence is prohibited.
- `DBR-016`: independent review found and caused correction of cross-wirable lineage;
- `DBR-017`: declared Laravel source hashes were originally report-only and are now revalidated.

These do not invalidate a schema-design `PASS`; they must be closed or enforced before their respective integration, collection, scoring, or promotion gates.

## Verification evidence

### Hashes

| Artifact/input | SHA-256 |
| --- | --- |
| Architecture config | `1c0c575fdd674d473ee6a676219b6afb01965ba3c27289300b0bf2a3644a9b13` |
| SQLite proof schema | `d76d9eccb141bf90c6c02d11a401661be5e51150598718c9399a871ba0513e02` |
| Architecture validator | `130dcc691b1571ed9fd765567b07181d2f0b417f7643a2d71f242e3728295720` |
| Focused tests | `6e9f8af6c1a814059cedf89bc90eaa2f3a27a5e4cc3201b8c182b56979d25105` |
| Inventory/reuse matrix | `9c986e088daec0e61c93af550840b610981e14733d966875de9d24b82d3d39b2` |
| Risk register | `912bf4eca66f474dced2b29adf47bef965bbac6a45a3de245d130caad3285d92` |
| Role 2 provider bundle | `6a33f296268652d6402cc09d300278545b47d309d78e27f7d4564e71ca366d57` |
| Role 2 eligible observations | `9240a65211b8efc2954adace8ef8a17150bc370ad8677b7db4295d2f5aa38f31` |
| Role 3 coverage by series | `f3953b70536b0ba9a2bb56fcb30ba9441389ae0122744baab695f7133faff730` |
| Experiment registry | `b7cb999912aed3108d12fcdb62c079d3c51610214a419a3b5fc72ac19c65d044` |
| Governance config | `aa8e1f35491550d66e1e210189cc9f4e383a83d088513fb5bb3176cab5a9bb9f` |

### Positive, boundary, and negative checks

`[FACT]` The validator built 11 tables and 28 triggers in a fresh in-memory database; loaded 25 retained source runs, 25 raw-artifact identities, and all 1,730 observations; inserted one valid synthetic indicator-to-bundle-to-category-to-snapshot-to-event-to-technical lineage chain; reproduced the category/revision counts; rehashed 11 declared repository inputs and all seven allowlisted non-secret Laravel source files; and dropped the empty schema in reverse order.

Sixteen schema negative/boundary checks failed closed:

1. duplicate idempotency key;
2. invalid sixth category;
3. missing/mismatched source-run/raw-artifact FK lineage;
4. broken revision-gap supersession;
5. revision route mismatch;
6. revision category mismatch;
7. revision release-bundle mismatch;
8. snapshot cross-wired to the wrong named category;
9. snapshot score differing from the named category state;
10. event indicator state belonging to a different observation;
11. technical score and bias differing from the linked snapshot;
12. retrieval completion before start;
13. invalid SHA-256;
14. effective time before exact availability time;
15. UPDATE of immutable evidence;
16. DELETE of immutable evidence.

`[FACT]` A separate isolated temporary-file unit test first validates a declared safe source hash and then tampers with the fixture; the same read-only verifier fails closed on the mismatch. The real Laravel sibling is never modified by this test.

`[FACT]` J0 validation recomputed date-aware `America/New_York` +36-hour timestamps and their `Asia/Kuala_Lumpur` equivalents for all 1,730 retained rows, including DST changes.

### Commands and exact results

1. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m smartmarketscope_quant.macro_regime.database_architecture --repo-root . --validate-only`
   - Exit `0`; `PASS`; 11 tables, 28 triggers, 16 schema negative checks, one valid synthetic derived-lineage chain, empty rollback `PASS`, 25 source runs, 25 raw artifacts, 1,730 observations, 11 repository hashes, seven Laravel source hashes, exact 34-route census, 0 trials/holdout/network.
2. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m unittest research.tests.test_macro_regime_database_architecture -v`
   - Exit `0`; 9/9 tests passed in `0.290s`, including isolated Laravel-source tamper detection.
3. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m unittest discover -s research/tests -v`
   - Exit `0`; 207/207 tests passed in `1.997s`.
4. `DB_CONNECTION=sqlite DB_DATABASE=/tmp/smartmarketscope-role4-XXXXXX.sqlite CACHE_STORE=array SESSION_DRIVER=array QUEUE_CONNECTION=sync php artisan migrate:fresh --force`
   - Earlier Role 4 baseline exited `0`; all 20 existing Laravel migrations passed against a clean disposable SQLite file and the file was removed. It was not rerun after the independent-review correction because no backend or migration file changed. This remains a baseline, not a migration of the new schema.
5. `php artisan test`
   - Exit `0`; 65/65 Laravel tests and 257 assertions passed in `1.64s` after the review correction; no Laravel file changed.
6. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m py_compile research/src/smartmarketscope_quant/macro_regime/database_architecture.py`
   - Exit `0`.

### Failed-first evidence

`[FACT]` The first validator run exited `1` because the duplicate-idempotency negative fixture accidentally assigned the attempted duplicate value to `source_run_id` rather than `idempotency_key`. The schema did not fail; the test helper did not create the intended collision. The helper was corrected, the duplicate now fails the unique key, and the full proof passes. No source evidence, schema threshold, or favorable outcome was changed.

`[FACT]` The initial disposable-load summary represented only the five observation-bearing source runs visible in `ALFRED_REGIME_ELIGIBLE_OBSERVATIONS.csv`. Review against `bundle.json` showed that the complete retained evidence contract is 25 source runs/raw artifacts. The validator and regression tests were expanded prospectively to load all 25 identities and report 23 distinct byte hashes without collapsing the 25 artifacts. This correction changed no retained evidence.

`[FACT]` Independent review then found that the original 27-trigger contract could accept a revision with a changed route/category/bundle, cross-wire a named snapshot category, accept event FKs whose referenced states did not belong to the event identities, copy altered scores/bias into a technical link, and report Laravel source hashes without revalidating them. Before implementation, the focused expectations were raised and the suite exited `1` with two failures: the snapshot-lineage trigger was absent and the proof returned 27 rather than 28 triggers. The strengthened contract now passes 28 triggers and 16 schema negatives. This review-found failure remains recorded as `DBR-016` and `DBR-017`; it created no empirical trial and changed no source evidence.

## Warnings, assumptions, and limitations

Warnings:

- `REGISTRY_CHRONOLOGY_UNRESOLVED_FINAL_CHAMPION_VETO`
- `LIQUIDITY_VERIFIED_OBSERVATION_COUNT_ZERO`
- `PRE_2017_COVERAGE_PROSPECTIVE_ONLY`
- `LARAVEL_SIBLING_HAS_NO_GIT_ROLLBACK`
- `MYSQL_OR_MARIADB_TRANSLATION_NOT_YET_EXECUTED`
- `EXISTING_PUBLIC_FUNDAMENTAL_ROUTES_NOT_AUTHORIZED_FOR_MACRO_RESEARCH_WRITES`

Assumptions:

- `[ASSUMPTION]` Laravel source/migrations are the authorized inventory boundary; no production database contents were inspected.
- `[ASSUMPTION]` Role 5 will collect only frozen approved routes and will use current/revised endpoints only for reconciliation.
- `[ASSUMPTION]` A private raw-storage backend will be approved before collection.

Limitations:

- SQLite proves the declared relational behavior, not MySQL/MariaDB production compatibility.
- No executable Laravel macro migration, command, model, service, route, or scheduler exists yet.
- No new macro data, scoring, snapshot, event ledger, technical link, PnL, backtest, graph, page, broker, paper, or live action was created.
- The schema does not cure missing LIQUIDITY data, prospective-only coverage, source methodology changes, or the registry chronology caveat.

Failure codes: none for the declared architecture objective.

## Exact next permitted action

Proceed sequentially to Role 5, Historical Macro Data Collector.

Role 5 must first translate this exact frozen schema into a reviewed Laravel migration with all 22 append-only and six strengthened lineage triggers in a version-controlled/rollback-capable backend, then pass clean disposable target-driver migration, empty rollback, access-control, idempotency, full supersession identity, snapshot category/score/count, event state/snapshot lineage, technical copied-value, timing, hash, and append-only tests. It may import the already retained Role 2 evidence only as 25 source runs, 25 raw artifacts, and 1,730 immutable observations with exact hashes.

New collection must then begin with one bounded H.6 M2 archive traversal to address LIQUIDITY from 2000, followed by H.4.1 total assets, reserve balances, and TGA only after the M2 parser/raw/version/checkpoint gate passes. It may use only the 19 `APPROVED_FOR_BOUNDED_COLLECTION` routes, preserve every permitted raw body, respect pacing/terms, append failures and partial attempts, and stop on unresolved format/unit/version semantics.

Role 5 must not score indicators or regimes, link technical setups, inspect PnL, backtest, deploy, expose a write API, connect a broker, touch a protected/final-holdout path, or start Roles 6-11.

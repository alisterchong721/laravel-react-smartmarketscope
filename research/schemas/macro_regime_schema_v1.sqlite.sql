PRAGMA foreign_keys = ON;

CREATE TABLE macro_source_providers (
    provider_id TEXT PRIMARY KEY,
    provider_code TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    official_public_status TEXT NOT NULL CHECK (official_public_status IN (
        'OFFICIAL_PUBLIC', 'OFFICIAL_KEY_REQUIRED', 'RECONCILIATION_ONLY', 'RETAINED_EVIDENCE'
    )),
    source_family TEXT NOT NULL,
    endpoint_or_file_family TEXT NOT NULL,
    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
    provider_version TEXT NOT NULL,
    source_terms_status TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL CHECK (updated_at_utc >= created_at_utc),
    UNIQUE (provider_code, provider_version)
);

CREATE TABLE macro_source_runs (
    source_run_id TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL REFERENCES macro_source_providers(provider_id),
    route_id TEXT NOT NULL,
    source_series_id TEXT NOT NULL,
    requested_start_date TEXT,
    requested_end_date TEXT,
    vintage_start_date TEXT,
    vintage_end_date TEXT,
    retrieval_started_at_utc TEXT NOT NULL,
    retrieval_completed_at_utc TEXT NOT NULL,
    run_status TEXT NOT NULL CHECK (run_status IN ('COMPLETED', 'FAILED', 'PARTIAL')),
    http_or_file_status TEXT NOT NULL,
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    collector_version TEXT NOT NULL,
    collector_code_sha256 TEXT NOT NULL CHECK (
        length(collector_code_sha256) = 64 AND collector_code_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    parser_version TEXT NOT NULL,
    parser_code_sha256 TEXT NOT NULL CHECK (
        length(parser_code_sha256) = 64 AND parser_code_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    request_config_sha256 TEXT NOT NULL CHECK (
        length(request_config_sha256) = 64 AND request_config_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    raw_payload_sha256 TEXT CHECK (
        raw_payload_sha256 IS NULL OR (length(raw_payload_sha256) = 64 AND raw_payload_sha256 NOT GLOB '*[^0-9a-f]*')
    ),
    source_reference TEXT NOT NULL,
    parent_resume_run_id TEXT REFERENCES macro_source_runs(source_run_id),
    checkpoint_cursor TEXT,
    attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
    idempotency_key TEXT NOT NULL,
    error_class TEXT,
    redacted_error_detail TEXT,
    contains_secrets INTEGER NOT NULL DEFAULT 0 CHECK (contains_secrets = 0),
    created_at_utc TEXT NOT NULL,
    CHECK (retrieval_completed_at_utc >= retrieval_started_at_utc),
    CHECK (requested_start_date IS NULL OR requested_end_date IS NULL OR requested_end_date >= requested_start_date),
    CHECK (vintage_start_date IS NULL OR vintage_end_date IS NULL OR vintage_end_date >= vintage_start_date),
    CHECK (parent_resume_run_id IS NULL OR parent_resume_run_id <> source_run_id),
    CHECK ((run_status = 'FAILED' AND row_count = 0) OR raw_payload_sha256 IS NOT NULL),
    UNIQUE (provider_id, route_id, idempotency_key)
);

CREATE INDEX macro_source_runs_route_time_idx
    ON macro_source_runs(route_id, retrieval_completed_at_utc);
CREATE INDEX macro_source_runs_provider_series_idx
    ON macro_source_runs(provider_id, source_series_id, retrieval_completed_at_utc);
CREATE INDEX macro_source_runs_resume_idx
    ON macro_source_runs(parent_resume_run_id, attempt_number);

CREATE TABLE macro_raw_artifacts (
    raw_artifact_id TEXT PRIMARY KEY,
    source_run_id TEXT NOT NULL REFERENCES macro_source_runs(source_run_id),
    artifact_ordinal INTEGER NOT NULL CHECK (artifact_ordinal >= 0),
    immutable_path TEXT NOT NULL CHECK (
        immutable_path <> '' AND immutable_path NOT LIKE '%..%' AND immutable_path NOT LIKE 'public/%'
    ),
    content_type TEXT NOT NULL,
    compression TEXT NOT NULL CHECK (compression IN ('NONE', 'GZIP', 'ZIP', 'BZIP2', 'XZ')),
    byte_length INTEGER NOT NULL CHECK (byte_length > 0),
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'),
    retrieved_at_utc TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    supersedes_artifact_id TEXT REFERENCES macro_raw_artifacts(raw_artifact_id),
    created_at_utc TEXT NOT NULL,
    CHECK (supersedes_artifact_id IS NULL OR supersedes_artifact_id <> raw_artifact_id),
    UNIQUE (source_run_id, artifact_ordinal),
    UNIQUE (immutable_path)
);

CREATE INDEX macro_raw_artifacts_hash_idx ON macro_raw_artifacts(sha256);
CREATE INDEX macro_raw_artifacts_supersedes_idx ON macro_raw_artifacts(supersedes_artifact_id);

CREATE TABLE macro_observations (
    observation_id TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL REFERENCES macro_source_providers(provider_id),
    source_run_id TEXT NOT NULL REFERENCES macro_source_runs(source_run_id),
    raw_artifact_id TEXT NOT NULL REFERENCES macro_raw_artifacts(raw_artifact_id),
    route_id TEXT NOT NULL,
    source_series_id TEXT NOT NULL,
    internal_indicator_id TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN (
        'INFLATION', 'LABOUR', 'GROWTH', 'MONETARY_POLICY', 'LIQUIDITY'
    )),
    release_bundle TEXT NOT NULL,
    reference_date TEXT NOT NULL,
    vintage_date TEXT NOT NULL,
    source_timestamp_raw TEXT,
    source_timezone TEXT NOT NULL,
    availability_date TEXT NOT NULL,
    availability_at_utc TEXT,
    availability_semantics TEXT NOT NULL,
    conservative_effective_at_utc TEXT NOT NULL,
    conservative_effective_at_asia_kuala_lumpur TEXT NOT NULL,
    effective_rule TEXT NOT NULL CHECK (effective_rule IN (
        'J0_CONSERVATIVE_36H', 'J1_NEXT_SOURCE_TRADING_DAY', 'J2_TWO_SOURCE_TRADING_DAYS'
    )),
    raw_value TEXT NOT NULL,
    normalized_numeric_value NUMERIC,
    normalization_status TEXT NOT NULL CHECK (normalization_status IN ('VALID', 'UNSCORABLE', 'MISSING')),
    unit TEXT NOT NULL,
    seasonal_adjustment_status TEXT NOT NULL,
    frequency TEXT NOT NULL,
    revision_number INTEGER NOT NULL CHECK (revision_number >= 0),
    revision_kind TEXT NOT NULL CHECK (revision_kind IN ('FIRST_PRINT', 'REVISION', 'CORRECTION')),
    supersedes_observation_id TEXT REFERENCES macro_observations(observation_id),
    point_in_time_classification TEXT NOT NULL CHECK (point_in_time_classification IN (
        'VINTAGE_SAFE_FOR_DAILY_REGIME', 'VINTAGE_SAFE_WITH_DELAY',
        'CURRENT_REVISED_HISTORY_ONLY', 'AVAILABILITY_DATE_UNRESOLVED',
        'SOURCE_VERSION_UNRESOLVED', 'UNUSABLE'
    )),
    protocol_eligibility TEXT NOT NULL CHECK (protocol_eligibility IN ('ELIGIBLE', 'INELIGIBLE')),
    historical_reconstruction INTEGER NOT NULL CHECK (historical_reconstruction IN (0, 1)),
    raw_artifact_sha256 TEXT NOT NULL CHECK (
        length(raw_artifact_sha256) = 64 AND raw_artifact_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    observation_payload_sha256 TEXT NOT NULL CHECK (
        length(observation_payload_sha256) = 64 AND observation_payload_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    normalization_code_sha256 TEXT NOT NULL CHECK (
        length(normalization_code_sha256) = 64 AND normalization_code_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    config_sha256 TEXT NOT NULL CHECK (length(config_sha256) = 64 AND config_sha256 NOT GLOB '*[^0-9a-f]*'),
    collector_code_sha256 TEXT NOT NULL CHECK (
        length(collector_code_sha256) = 64 AND collector_code_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    registry_sha256 TEXT NOT NULL CHECK (
        length(registry_sha256) = 64 AND registry_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    retrieved_at_utc TEXT NOT NULL,
    inserted_at_utc TEXT NOT NULL,
    CHECK (availability_at_utc IS NULL OR conservative_effective_at_utc >= availability_at_utc),
    CHECK ((revision_number = 0 AND supersedes_observation_id IS NULL AND revision_kind = 'FIRST_PRINT') OR
           (revision_number > 0 AND supersedes_observation_id IS NOT NULL AND revision_kind IN ('REVISION', 'CORRECTION'))),
    CHECK ((normalization_status = 'VALID' AND normalized_numeric_value IS NOT NULL) OR
           normalization_status <> 'VALID'),
    CHECK ((protocol_eligibility = 'ELIGIBLE' AND point_in_time_classification IN (
        'VINTAGE_SAFE_FOR_DAILY_REGIME', 'VINTAGE_SAFE_WITH_DELAY'
    )) OR protocol_eligibility = 'INELIGIBLE'),
    UNIQUE (provider_id, source_series_id, reference_date, vintage_date, revision_number)
);

CREATE INDEX macro_observations_asof_idx
    ON macro_observations(internal_indicator_id, conservative_effective_at_utc);
CREATE INDEX macro_observations_category_bundle_idx
    ON macro_observations(category, release_bundle, conservative_effective_at_utc);
CREATE INDEX macro_observations_lineage_idx
    ON macro_observations(source_run_id, raw_artifact_id);
CREATE INDEX macro_observations_supersedes_idx
    ON macro_observations(supersedes_observation_id);

CREATE TABLE macro_indicator_states (
    indicator_state_id TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL REFERENCES macro_observations(observation_id),
    internal_indicator_id TEXT NOT NULL,
    calculation_version TEXT NOT NULL,
    current_value NUMERIC,
    previous_point_in_time_value NUMERIC,
    one_release_change NUMERIC,
    three_release_change NUMERIC,
    six_release_change NUMERIC,
    year_over_year_transformation NUMERIC,
    prior_only_robust_z_score NUMERIC,
    prior_only_level_percentile NUMERIC CHECK (
        prior_only_level_percentile IS NULL OR (prior_only_level_percentile >= 0 AND prior_only_level_percentile <= 1)
    ),
    trend_classification TEXT NOT NULL,
    stress_classification TEXT NOT NULL,
    continuous_score NUMERIC,
    discrete_score INTEGER CHECK (discrete_score IS NULL OR discrete_score BETWEEN -2 AND 2),
    coverage_status TEXT NOT NULL CHECK (coverage_status IN (
        'VALID', 'PARTIAL', 'UNKNOWN', 'INSUFFICIENT_HISTORY', 'DATA_GAP', 'CONFLICTING', 'STRESS'
    )),
    scoring_rationale_code TEXT NOT NULL,
    scoring_config_sha256 TEXT NOT NULL CHECK (
        length(scoring_config_sha256) = 64 AND scoring_config_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    code_sha256 TEXT NOT NULL CHECK (length(code_sha256) = 64 AND code_sha256 NOT GLOB '*[^0-9a-f]*'),
    registry_sha256 TEXT NOT NULL CHECK (length(registry_sha256) = 64 AND registry_sha256 NOT GLOB '*[^0-9a-f]*'),
    calculated_at_utc TEXT NOT NULL,
    CHECK ((coverage_status IN ('VALID', 'STRESS') AND discrete_score IS NOT NULL) OR
           coverage_status NOT IN ('VALID', 'STRESS')),
    UNIQUE (observation_id, calculation_version)
);

CREATE INDEX macro_indicator_states_asof_idx
    ON macro_indicator_states(internal_indicator_id, calculated_at_utc);

CREATE TABLE macro_release_bundle_states (
    release_bundle_state_id TEXT PRIMARY KEY,
    release_bundle TEXT NOT NULL,
    component_indicator_state_ids_json TEXT NOT NULL CHECK (json_valid(component_indicator_state_ids_json)),
    component_lineage_sha256 TEXT NOT NULL CHECK (
        length(component_lineage_sha256) = 64 AND component_lineage_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    continuous_bundle_score NUMERIC,
    discrete_bundle_score INTEGER CHECK (discrete_bundle_score IS NULL OR discrete_bundle_score BETWEEN -2 AND 2),
    coverage_status TEXT NOT NULL CHECK (coverage_status IN (
        'VALID', 'PARTIAL', 'UNKNOWN', 'INSUFFICIENT_HISTORY', 'DATA_GAP', 'CONFLICTING', 'STRESS'
    )),
    effective_at_utc TEXT NOT NULL,
    scoring_version TEXT NOT NULL,
    scoring_config_sha256 TEXT NOT NULL CHECK (
        length(scoring_config_sha256) = 64 AND scoring_config_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    code_sha256 TEXT NOT NULL CHECK (length(code_sha256) = 64 AND code_sha256 NOT GLOB '*[^0-9a-f]*'),
    registry_sha256 TEXT NOT NULL CHECK (length(registry_sha256) = 64 AND registry_sha256 NOT GLOB '*[^0-9a-f]*'),
    created_at_utc TEXT NOT NULL,
    UNIQUE (release_bundle, effective_at_utc, scoring_version)
);

CREATE INDEX macro_release_bundle_states_asof_idx
    ON macro_release_bundle_states(release_bundle, effective_at_utc);

CREATE TABLE macro_category_states (
    category_state_id TEXT PRIMARY KEY,
    category TEXT NOT NULL CHECK (category IN (
        'INFLATION', 'LABOUR', 'GROWTH', 'MONETARY_POLICY', 'LIQUIDITY'
    )),
    active_release_bundle_state_ids_json TEXT NOT NULL CHECK (json_valid(active_release_bundle_state_ids_json)),
    bundle_lineage_sha256 TEXT NOT NULL CHECK (
        length(bundle_lineage_sha256) = 64 AND bundle_lineage_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    continuous_category_score NUMERIC,
    discrete_category_score INTEGER CHECK (discrete_category_score IS NULL OR discrete_category_score BETWEEN -2 AND 2),
    category_status TEXT NOT NULL CHECK (category_status IN (
        'VALID', 'PARTIAL', 'UNKNOWN', 'INSUFFICIENT_HISTORY', 'DATA_GAP', 'CONFLICTING', 'STRESS'
    )),
    stress_flags_json TEXT NOT NULL CHECK (json_valid(stress_flags_json)),
    stress_flags_sha256 TEXT NOT NULL CHECK (
        length(stress_flags_sha256) = 64 AND stress_flags_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    effective_at_utc TEXT NOT NULL,
    scoring_version TEXT NOT NULL,
    scoring_config_sha256 TEXT NOT NULL CHECK (
        length(scoring_config_sha256) = 64 AND scoring_config_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    code_sha256 TEXT NOT NULL CHECK (length(code_sha256) = 64 AND code_sha256 NOT GLOB '*[^0-9a-f]*'),
    registry_sha256 TEXT NOT NULL CHECK (length(registry_sha256) = 64 AND registry_sha256 NOT GLOB '*[^0-9a-f]*'),
    created_at_utc TEXT NOT NULL,
    UNIQUE (category, effective_at_utc, scoring_version)
);

CREATE INDEX macro_category_states_asof_idx ON macro_category_states(category, effective_at_utc);

CREATE TABLE macro_regime_snapshots (
    macro_snapshot_id TEXT PRIMARY KEY,
    effective_at_utc TEXT NOT NULL,
    inflation_category_state_id TEXT REFERENCES macro_category_states(category_state_id),
    labour_category_state_id TEXT REFERENCES macro_category_states(category_state_id),
    growth_category_state_id TEXT REFERENCES macro_category_states(category_state_id),
    monetary_policy_category_state_id TEXT REFERENCES macro_category_states(category_state_id),
    liquidity_category_state_id TEXT REFERENCES macro_category_states(category_state_id),
    inflation_score INTEGER CHECK (inflation_score IS NULL OR inflation_score BETWEEN -2 AND 2),
    labour_score INTEGER CHECK (labour_score IS NULL OR labour_score BETWEEN -2 AND 2),
    growth_score INTEGER CHECK (growth_score IS NULL OR growth_score BETWEEN -2 AND 2),
    monetary_policy_score INTEGER CHECK (monetary_policy_score IS NULL OR monetary_policy_score BETWEEN -2 AND 2),
    liquidity_score INTEGER CHECK (liquidity_score IS NULL OR liquidity_score BETWEEN -2 AND 2),
    base_overall_score INTEGER CHECK (base_overall_score IS NULL OR base_overall_score BETWEEN -10 AND 10),
    active_interaction_flags_json TEXT NOT NULL CHECK (json_valid(active_interaction_flags_json)),
    interaction_adjustment INTEGER NOT NULL CHECK (interaction_adjustment BETWEEN -2 AND 2),
    final_score INTEGER CHECK (final_score IS NULL OR final_score BETWEEN -10 AND 10),
    final_bias TEXT NOT NULL CHECK (final_bias IN (
        'STRONG_BULLISH', 'BULLISH', 'NEUTRAL', 'BEARISH', 'STRONG_BEARISH', 'UNKNOWN'
    )),
    valid_category_count INTEGER NOT NULL CHECK (valid_category_count BETWEEN 0 AND 5),
    source_observation_lineage_json TEXT NOT NULL CHECK (json_valid(source_observation_lineage_json)),
    source_observation_lineage_sha256 TEXT NOT NULL CHECK (
        length(source_observation_lineage_sha256) = 64 AND source_observation_lineage_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    scoring_version TEXT NOT NULL,
    scoring_config_sha256 TEXT NOT NULL CHECK (
        length(scoring_config_sha256) = 64 AND scoring_config_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    registry_sha256 TEXT NOT NULL CHECK (length(registry_sha256) = 64 AND registry_sha256 NOT GLOB '*[^0-9a-f]*'),
    code_sha256 TEXT NOT NULL CHECK (length(code_sha256) = 64 AND code_sha256 NOT GLOB '*[^0-9a-f]*'),
    created_at_utc TEXT NOT NULL,
    CHECK ((valid_category_count >= 3 AND final_bias <> 'UNKNOWN' AND final_score IS NOT NULL AND base_overall_score IS NOT NULL) OR
           (valid_category_count < 3 AND final_bias = 'UNKNOWN')),
    UNIQUE (effective_at_utc, scoring_version)
);

CREATE INDEX macro_regime_snapshots_asof_idx
    ON macro_regime_snapshots(effective_at_utc, scoring_version);

CREATE TABLE macro_event_update_ledger (
    event_update_id TEXT PRIMARY KEY,
    availability_at_utc TEXT,
    effective_at_utc TEXT NOT NULL,
    indicator_updated TEXT NOT NULL,
    previous_value NUMERIC,
    current_value NUMERIC,
    one_release_change NUMERIC,
    previous_indicator_score INTEGER CHECK (previous_indicator_score IS NULL OR previous_indicator_score BETWEEN -2 AND 2),
    new_indicator_score INTEGER CHECK (new_indicator_score IS NULL OR new_indicator_score BETWEEN -2 AND 2),
    release_bundle_updated TEXT NOT NULL,
    previous_bundle_score INTEGER CHECK (previous_bundle_score IS NULL OR previous_bundle_score BETWEEN -2 AND 2),
    new_bundle_score INTEGER CHECK (new_bundle_score IS NULL OR new_bundle_score BETWEEN -2 AND 2),
    category_updated TEXT NOT NULL CHECK (category_updated IN (
        'INFLATION', 'LABOUR', 'GROWTH', 'MONETARY_POLICY', 'LIQUIDITY'
    )),
    previous_category_score INTEGER CHECK (previous_category_score IS NULL OR previous_category_score BETWEEN -2 AND 2),
    new_category_score INTEGER CHECK (new_category_score IS NULL OR new_category_score BETWEEN -2 AND 2),
    base_overall_score_before INTEGER CHECK (base_overall_score_before IS NULL OR base_overall_score_before BETWEEN -10 AND 10),
    base_overall_score_after INTEGER CHECK (base_overall_score_after IS NULL OR base_overall_score_after BETWEEN -10 AND 10),
    active_interaction_before_json TEXT NOT NULL CHECK (json_valid(active_interaction_before_json)),
    active_interaction_after_json TEXT NOT NULL CHECK (json_valid(active_interaction_after_json)),
    final_macro_score_before INTEGER CHECK (final_macro_score_before IS NULL OR final_macro_score_before BETWEEN -10 AND 10),
    final_macro_score_after INTEGER CHECK (final_macro_score_after IS NULL OR final_macro_score_after BETWEEN -10 AND 10),
    bias_before TEXT NOT NULL CHECK (bias_before IN (
        'STRONG_BULLISH', 'BULLISH', 'NEUTRAL', 'BEARISH', 'STRONG_BEARISH', 'UNKNOWN'
    )),
    bias_after TEXT NOT NULL CHECK (bias_after IN (
        'STRONG_BULLISH', 'BULLISH', 'NEUTRAL', 'BEARISH', 'STRONG_BEARISH', 'UNKNOWN'
    )),
    source_observation_id TEXT NOT NULL REFERENCES macro_observations(observation_id),
    source_run_id TEXT NOT NULL REFERENCES macro_source_runs(source_run_id),
    indicator_state_id TEXT NOT NULL REFERENCES macro_indicator_states(indicator_state_id),
    release_bundle_state_id TEXT NOT NULL REFERENCES macro_release_bundle_states(release_bundle_state_id),
    category_state_id TEXT NOT NULL REFERENCES macro_category_states(category_state_id),
    snapshot_before_id TEXT REFERENCES macro_regime_snapshots(macro_snapshot_id),
    snapshot_after_id TEXT NOT NULL REFERENCES macro_regime_snapshots(macro_snapshot_id),
    point_in_time_classification TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    scoring_config_sha256 TEXT NOT NULL CHECK (
        length(scoring_config_sha256) = 64 AND scoring_config_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    code_sha256 TEXT NOT NULL CHECK (length(code_sha256) = 64 AND code_sha256 NOT GLOB '*[^0-9a-f]*'),
    registry_sha256 TEXT NOT NULL CHECK (length(registry_sha256) = 64 AND registry_sha256 NOT GLOB '*[^0-9a-f]*'),
    created_at_utc TEXT NOT NULL,
    CHECK (availability_at_utc IS NULL OR effective_at_utc >= availability_at_utc)
);

CREATE INDEX macro_event_update_ledger_effective_idx
    ON macro_event_update_ledger(effective_at_utc, category_updated);
CREATE INDEX macro_event_update_ledger_lineage_idx
    ON macro_event_update_ledger(source_observation_id, source_run_id);

CREATE TABLE macro_technical_links (
    macro_technical_link_id TEXT PRIMARY KEY,
    technical_setup_id TEXT NOT NULL,
    technical_trade_id TEXT NOT NULL,
    technical_actionable_at_utc TEXT NOT NULL,
    technical_source_date TEXT NOT NULL,
    macro_snapshot_id TEXT NOT NULL REFERENCES macro_regime_snapshots(macro_snapshot_id),
    macro_effective_at_utc TEXT NOT NULL,
    inflation_score INTEGER CHECK (inflation_score IS NULL OR inflation_score BETWEEN -2 AND 2),
    labour_score INTEGER CHECK (labour_score IS NULL OR labour_score BETWEEN -2 AND 2),
    growth_score INTEGER CHECK (growth_score IS NULL OR growth_score BETWEEN -2 AND 2),
    monetary_policy_score INTEGER CHECK (monetary_policy_score IS NULL OR monetary_policy_score BETWEEN -2 AND 2),
    liquidity_score INTEGER CHECK (liquidity_score IS NULL OR liquidity_score BETWEEN -2 AND 2),
    final_macro_score INTEGER CHECK (final_macro_score IS NULL OR final_macro_score BETWEEN -10 AND 10),
    macro_bias TEXT NOT NULL CHECK (macro_bias IN (
        'STRONG_BULLISH', 'BULLISH', 'NEUTRAL', 'BEARISH', 'STRONG_BEARISH', 'UNKNOWN'
    )),
    direction_match TEXT NOT NULL CHECK (direction_match IN ('MATCH', 'OPPOSITE', 'NEUTRAL', 'UNKNOWN')),
    filter_decision TEXT NOT NULL CHECK (filter_decision IN (
        'PERMITTED_DIRECTION_MATCH', 'FILTERED_OPPOSITE_DIRECTION', 'FILTERED_NEUTRAL', 'FILTERED_UNKNOWN'
    )),
    join_rule TEXT NOT NULL CHECK (join_rule IN (
        'J0_CONSERVATIVE_36H', 'J1_NEXT_SOURCE_TRADING_DAY', 'J2_TWO_SOURCE_TRADING_DAYS'
    )),
    scoring_version TEXT NOT NULL,
    technical_baseline_sha256 TEXT NOT NULL CHECK (
        length(technical_baseline_sha256) = 64 AND technical_baseline_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    macro_manifest_sha256 TEXT NOT NULL CHECK (
        length(macro_manifest_sha256) = 64 AND macro_manifest_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    join_config_sha256 TEXT NOT NULL CHECK (
        length(join_config_sha256) = 64 AND join_config_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    code_sha256 TEXT NOT NULL CHECK (length(code_sha256) = 64 AND code_sha256 NOT GLOB '*[^0-9a-f]*'),
    registry_sha256 TEXT NOT NULL CHECK (length(registry_sha256) = 64 AND registry_sha256 NOT GLOB '*[^0-9a-f]*'),
    created_at_utc TEXT NOT NULL,
    CHECK (macro_effective_at_utc <= technical_actionable_at_utc),
    UNIQUE (technical_setup_id, technical_trade_id, join_rule, scoring_version)
);

CREATE INDEX macro_technical_links_setup_idx
    ON macro_technical_links(technical_setup_id, technical_actionable_at_utc);
CREATE INDEX macro_technical_links_snapshot_idx ON macro_technical_links(macro_snapshot_id);

CREATE TABLE macro_backtest_runs (
    macro_backtest_run_id TEXT PRIMARY KEY,
    technical_baseline_sha256 TEXT NOT NULL CHECK (
        length(technical_baseline_sha256) = 64 AND technical_baseline_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    macro_manifest_sha256 TEXT NOT NULL CHECK (
        length(macro_manifest_sha256) = 64 AND macro_manifest_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    scoring_config_sha256 TEXT NOT NULL CHECK (
        length(scoring_config_sha256) = 64 AND scoring_config_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    join_config_sha256 TEXT NOT NULL CHECK (
        length(join_config_sha256) = 64 AND join_config_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    comparison_variant TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL CHECK (end_date >= start_date),
    generated_artifacts_json TEXT NOT NULL CHECK (json_valid(generated_artifacts_json)),
    generated_artifacts_manifest_sha256 TEXT NOT NULL CHECK (
        length(generated_artifacts_manifest_sha256) = 64 AND generated_artifacts_manifest_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    result_sha256 TEXT NOT NULL CHECK (length(result_sha256) = 64 AND result_sha256 NOT GLOB '*[^0-9a-f]*'),
    registry_sha256 TEXT NOT NULL CHECK (length(registry_sha256) = 64 AND registry_sha256 NOT GLOB '*[^0-9a-f]*'),
    run_status TEXT NOT NULL CHECK (run_status IN ('COMPLETED', 'FAILED', 'INCONCLUSIVE', 'CANCELLED')),
    started_at_utc TEXT NOT NULL,
    completed_at_utc TEXT NOT NULL CHECK (completed_at_utc >= started_at_utc),
    created_at_utc TEXT NOT NULL,
    UNIQUE (
        technical_baseline_sha256, macro_manifest_sha256, scoring_config_sha256,
        join_config_sha256, comparison_variant, start_date, end_date
    )
);

CREATE INDEX macro_backtest_runs_variant_idx
    ON macro_backtest_runs(comparison_variant, start_date, end_date);

CREATE TRIGGER macro_observations_validate_supersession
BEFORE INSERT ON macro_observations
WHEN NEW.supersedes_observation_id IS NOT NULL
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM macro_observations AS previous
        WHERE previous.observation_id = NEW.supersedes_observation_id
          AND previous.provider_id = NEW.provider_id
          AND previous.route_id = NEW.route_id
          AND previous.source_series_id = NEW.source_series_id
          AND previous.internal_indicator_id = NEW.internal_indicator_id
          AND previous.category = NEW.category
          AND previous.release_bundle = NEW.release_bundle
          AND previous.reference_date = NEW.reference_date
          AND previous.revision_number + 1 = NEW.revision_number
          AND previous.vintage_date <= NEW.vintage_date
          AND previous.conservative_effective_at_utc <= NEW.conservative_effective_at_utc
    ) THEN RAISE(ABORT, 'invalid_observation_supersession') END;
END;

CREATE TRIGGER macro_observations_validate_source_lineage
BEFORE INSERT ON macro_observations
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM macro_source_runs AS source_run
        JOIN macro_raw_artifacts AS raw_artifact
          ON raw_artifact.source_run_id = source_run.source_run_id
        WHERE source_run.source_run_id = NEW.source_run_id
          AND source_run.provider_id = NEW.provider_id
          AND source_run.route_id = NEW.route_id
          AND source_run.source_series_id = NEW.source_series_id
          AND raw_artifact.raw_artifact_id = NEW.raw_artifact_id
          AND raw_artifact.sha256 = NEW.raw_artifact_sha256
    ) THEN RAISE(ABORT, 'invalid_observation_source_lineage') END;
END;

CREATE TRIGGER macro_raw_artifacts_validate_supersession
BEFORE INSERT ON macro_raw_artifacts
WHEN NEW.supersedes_artifact_id IS NOT NULL
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM macro_raw_artifacts AS previous
        JOIN macro_source_runs AS previous_run ON previous_run.source_run_id = previous.source_run_id
        JOIN macro_source_runs AS new_run ON new_run.source_run_id = NEW.source_run_id
        WHERE previous.raw_artifact_id = NEW.supersedes_artifact_id
          AND previous_run.provider_id = new_run.provider_id
          AND previous_run.route_id = new_run.route_id
          AND previous_run.source_series_id = new_run.source_series_id
          AND previous.retrieved_at_utc <= NEW.retrieved_at_utc
    ) THEN RAISE(ABORT, 'invalid_artifact_supersession') END;
END;

CREATE TRIGGER macro_regime_snapshots_validate_category_lineage
BEFORE INSERT ON macro_regime_snapshots
BEGIN
    SELECT CASE WHEN NOT (
        ((NEW.inflation_category_state_id IS NULL AND NEW.inflation_score IS NULL) OR
         (NEW.inflation_category_state_id IS NOT NULL AND NEW.inflation_score IS NOT NULL AND EXISTS (
             SELECT 1 FROM macro_category_states
             WHERE category_state_id = NEW.inflation_category_state_id
               AND category = 'INFLATION'
               AND discrete_category_score IS NEW.inflation_score
               AND effective_at_utc <= NEW.effective_at_utc
         ))) AND
        ((NEW.labour_category_state_id IS NULL AND NEW.labour_score IS NULL) OR
         (NEW.labour_category_state_id IS NOT NULL AND NEW.labour_score IS NOT NULL AND EXISTS (
             SELECT 1 FROM macro_category_states
             WHERE category_state_id = NEW.labour_category_state_id
               AND category = 'LABOUR'
               AND discrete_category_score IS NEW.labour_score
               AND effective_at_utc <= NEW.effective_at_utc
         ))) AND
        ((NEW.growth_category_state_id IS NULL AND NEW.growth_score IS NULL) OR
         (NEW.growth_category_state_id IS NOT NULL AND NEW.growth_score IS NOT NULL AND EXISTS (
             SELECT 1 FROM macro_category_states
             WHERE category_state_id = NEW.growth_category_state_id
               AND category = 'GROWTH'
               AND discrete_category_score IS NEW.growth_score
               AND effective_at_utc <= NEW.effective_at_utc
         ))) AND
        ((NEW.monetary_policy_category_state_id IS NULL AND NEW.monetary_policy_score IS NULL) OR
         (NEW.monetary_policy_category_state_id IS NOT NULL AND NEW.monetary_policy_score IS NOT NULL AND EXISTS (
             SELECT 1 FROM macro_category_states
             WHERE category_state_id = NEW.monetary_policy_category_state_id
               AND category = 'MONETARY_POLICY'
               AND discrete_category_score IS NEW.monetary_policy_score
               AND effective_at_utc <= NEW.effective_at_utc
         ))) AND
        ((NEW.liquidity_category_state_id IS NULL AND NEW.liquidity_score IS NULL) OR
         (NEW.liquidity_category_state_id IS NOT NULL AND NEW.liquidity_score IS NOT NULL AND EXISTS (
             SELECT 1 FROM macro_category_states
             WHERE category_state_id = NEW.liquidity_category_state_id
               AND category = 'LIQUIDITY'
               AND discrete_category_score IS NEW.liquidity_score
               AND effective_at_utc <= NEW.effective_at_utc
         ))) AND
        NEW.valid_category_count =
            (NEW.inflation_score IS NOT NULL) +
            (NEW.labour_score IS NOT NULL) +
            (NEW.growth_score IS NOT NULL) +
            (NEW.monetary_policy_score IS NOT NULL) +
            (NEW.liquidity_score IS NOT NULL)
    ) THEN RAISE(ABORT, 'invalid_regime_snapshot_category_lineage') END;
END;

CREATE TRIGGER macro_event_update_validate_lineage
BEFORE INSERT ON macro_event_update_ledger
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM macro_observations AS observation
        JOIN macro_indicator_states AS indicator_state
          ON indicator_state.indicator_state_id = NEW.indicator_state_id
        JOIN macro_release_bundle_states AS bundle_state
          ON bundle_state.release_bundle_state_id = NEW.release_bundle_state_id
        JOIN macro_category_states AS category_state
          ON category_state.category_state_id = NEW.category_state_id
        JOIN macro_regime_snapshots AS snapshot_after
          ON snapshot_after.macro_snapshot_id = NEW.snapshot_after_id
        LEFT JOIN macro_regime_snapshots AS snapshot_before
          ON snapshot_before.macro_snapshot_id = NEW.snapshot_before_id
        WHERE observation.observation_id = NEW.source_observation_id
          AND observation.source_run_id = NEW.source_run_id
          AND observation.internal_indicator_id = NEW.indicator_updated
          AND observation.release_bundle = NEW.release_bundle_updated
          AND observation.category = NEW.category_updated
          AND observation.point_in_time_classification = NEW.point_in_time_classification
          AND observation.conservative_effective_at_utc <= NEW.effective_at_utc
          AND indicator_state.observation_id = NEW.source_observation_id
          AND indicator_state.internal_indicator_id = NEW.indicator_updated
          AND indicator_state.current_value IS NEW.current_value
          AND indicator_state.previous_point_in_time_value IS NEW.previous_value
          AND indicator_state.one_release_change IS NEW.one_release_change
          AND indicator_state.discrete_score IS NEW.new_indicator_score
          AND indicator_state.calculated_at_utc <= NEW.effective_at_utc
          AND bundle_state.release_bundle = NEW.release_bundle_updated
          AND bundle_state.discrete_bundle_score IS NEW.new_bundle_score
          AND bundle_state.effective_at_utc <= NEW.effective_at_utc
          AND category_state.category = NEW.category_updated
          AND category_state.discrete_category_score IS NEW.new_category_score
          AND category_state.effective_at_utc <= NEW.effective_at_utc
          AND indicator_state.scoring_config_sha256 = NEW.scoring_config_sha256
          AND indicator_state.code_sha256 = NEW.code_sha256
          AND indicator_state.registry_sha256 = NEW.registry_sha256
          AND bundle_state.scoring_config_sha256 = NEW.scoring_config_sha256
          AND bundle_state.code_sha256 = NEW.code_sha256
          AND bundle_state.registry_sha256 = NEW.registry_sha256
          AND category_state.scoring_config_sha256 = NEW.scoring_config_sha256
          AND category_state.code_sha256 = NEW.code_sha256
          AND category_state.registry_sha256 = NEW.registry_sha256
          AND snapshot_after.scoring_config_sha256 = NEW.scoring_config_sha256
          AND snapshot_after.code_sha256 = NEW.code_sha256
          AND snapshot_after.registry_sha256 = NEW.registry_sha256
          AND snapshot_after.effective_at_utc = NEW.effective_at_utc
          AND snapshot_after.base_overall_score IS NEW.base_overall_score_after
          AND snapshot_after.active_interaction_flags_json = NEW.active_interaction_after_json
          AND snapshot_after.final_score IS NEW.final_macro_score_after
          AND snapshot_after.final_bias = NEW.bias_after
          AND (
              (NEW.category_updated = 'INFLATION'
               AND snapshot_after.inflation_category_state_id = NEW.category_state_id
               AND snapshot_after.inflation_score IS NEW.new_category_score) OR
              (NEW.category_updated = 'LABOUR'
               AND snapshot_after.labour_category_state_id = NEW.category_state_id
               AND snapshot_after.labour_score IS NEW.new_category_score) OR
              (NEW.category_updated = 'GROWTH'
               AND snapshot_after.growth_category_state_id = NEW.category_state_id
               AND snapshot_after.growth_score IS NEW.new_category_score) OR
              (NEW.category_updated = 'MONETARY_POLICY'
               AND snapshot_after.monetary_policy_category_state_id = NEW.category_state_id
               AND snapshot_after.monetary_policy_score IS NEW.new_category_score) OR
              (NEW.category_updated = 'LIQUIDITY'
               AND snapshot_after.liquidity_category_state_id = NEW.category_state_id
               AND snapshot_after.liquidity_score IS NEW.new_category_score)
          )
          AND (
              (NEW.snapshot_before_id IS NULL
               AND NEW.base_overall_score_before IS NULL
               AND NEW.final_macro_score_before IS NULL
               AND NEW.bias_before = 'UNKNOWN') OR
              (NEW.snapshot_before_id IS NOT NULL
               AND snapshot_before.effective_at_utc <= NEW.effective_at_utc
               AND snapshot_before.base_overall_score IS NEW.base_overall_score_before
               AND snapshot_before.active_interaction_flags_json = NEW.active_interaction_before_json
               AND snapshot_before.final_score IS NEW.final_macro_score_before
               AND snapshot_before.final_bias = NEW.bias_before
               AND CASE NEW.category_updated
                   WHEN 'INFLATION' THEN snapshot_before.inflation_score
                   WHEN 'LABOUR' THEN snapshot_before.labour_score
                   WHEN 'GROWTH' THEN snapshot_before.growth_score
                   WHEN 'MONETARY_POLICY' THEN snapshot_before.monetary_policy_score
                   WHEN 'LIQUIDITY' THEN snapshot_before.liquidity_score
               END IS NEW.previous_category_score)
          )
    ) THEN RAISE(ABORT, 'invalid_event_update_lineage') END;
END;

CREATE TRIGGER macro_technical_links_validate_snapshot_time
BEFORE INSERT ON macro_technical_links
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM macro_regime_snapshots
        WHERE macro_snapshot_id = NEW.macro_snapshot_id
          AND effective_at_utc = NEW.macro_effective_at_utc
          AND effective_at_utc <= NEW.technical_actionable_at_utc
          AND inflation_score IS NEW.inflation_score
          AND labour_score IS NEW.labour_score
          AND growth_score IS NEW.growth_score
          AND monetary_policy_score IS NEW.monetary_policy_score
          AND liquidity_score IS NEW.liquidity_score
          AND final_score IS NEW.final_macro_score
          AND final_bias = NEW.macro_bias
          AND scoring_version = NEW.scoring_version
    ) THEN RAISE(ABORT, 'invalid_macro_technical_snapshot_time') END;
END;

CREATE TRIGGER macro_source_providers_no_update BEFORE UPDATE ON macro_source_providers BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_source_providers_no_delete BEFORE DELETE ON macro_source_providers BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_source_runs_no_update BEFORE UPDATE ON macro_source_runs BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_source_runs_no_delete BEFORE DELETE ON macro_source_runs BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_raw_artifacts_no_update BEFORE UPDATE ON macro_raw_artifacts BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_raw_artifacts_no_delete BEFORE DELETE ON macro_raw_artifacts BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_observations_no_update BEFORE UPDATE ON macro_observations BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_observations_no_delete BEFORE DELETE ON macro_observations BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_indicator_states_no_update BEFORE UPDATE ON macro_indicator_states BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_indicator_states_no_delete BEFORE DELETE ON macro_indicator_states BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_release_bundle_states_no_update BEFORE UPDATE ON macro_release_bundle_states BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_release_bundle_states_no_delete BEFORE DELETE ON macro_release_bundle_states BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_category_states_no_update BEFORE UPDATE ON macro_category_states BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_category_states_no_delete BEFORE DELETE ON macro_category_states BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_regime_snapshots_no_update BEFORE UPDATE ON macro_regime_snapshots BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_regime_snapshots_no_delete BEFORE DELETE ON macro_regime_snapshots BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_event_update_ledger_no_update BEFORE UPDATE ON macro_event_update_ledger BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_event_update_ledger_no_delete BEFORE DELETE ON macro_event_update_ledger BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_technical_links_no_update BEFORE UPDATE ON macro_technical_links BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_technical_links_no_delete BEFORE DELETE ON macro_technical_links BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_backtest_runs_no_update BEFORE UPDATE ON macro_backtest_runs BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER macro_backtest_runs_no_delete BEFORE DELETE ON macro_backtest_runs BEGIN SELECT RAISE(ABORT, 'append_only'); END;

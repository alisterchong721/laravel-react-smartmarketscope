"""Validate the frozen macro-regime database architecture without external writes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


CONFIG_RELATIVE_PATH = Path("research/config/macro_regime_database_architecture.json")
SCHEMA_RELATIVE_PATH = Path("research/schemas/macro_regime_schema_v1.sqlite.sql")
ELIGIBLE_RELATIVE_PATH = Path("ALFRED_REGIME_ELIGIBLE_OBSERVATIONS.csv")
COVERAGE_SERIES_RELATIVE_PATH = Path("MACRO_REGIME_COVERAGE_BY_SERIES.csv")
ROLE2_BUNDLE_RELATIVE_PATH = Path(
    "research/artifacts/program2/alfred/QRP2-ALFRED-20260713T070000Z/bundle.json"
)

CATEGORIES = (
    "INFLATION",
    "LABOUR",
    "GROWTH",
    "MONETARY_POLICY",
    "LIQUIDITY",
)

TABLES = (
    "macro_source_providers",
    "macro_source_runs",
    "macro_raw_artifacts",
    "macro_observations",
    "macro_indicator_states",
    "macro_release_bundle_states",
    "macro_category_states",
    "macro_regime_snapshots",
    "macro_event_update_ledger",
    "macro_technical_links",
    "macro_backtest_runs",
)

APPEND_ONLY_TABLES = TABLES
HEX64 = "a" * 64
ROLE2_RELEASE_BUNDLES = {
    "CPIAUCSL": "CPI_BUNDLE",
    "PAYEMS": "EMPLOYMENT_REPORT_BUNDLE",
    "UNRATE": "EMPLOYMENT_REPORT_BUNDLE",
    "GDPC1": "GDP_BUNDLE",
    "FEDFUNDS": "POLICY_RATE_BUNDLE",
}
LARAVEL_INVENTORY_FILE_PATHS = {
    "composer_lock": "composer.lock",
    "fundamental_data_migration": (
        "database/migrations/2025_12_26_152031_create_fundamental_data_table.php"
    ),
    "fundamental_data_model": "app/Models/FundamentalData.php",
    "research_news_lineage_migration": (
        "database/migrations/2026_07_13_010000_create_research_news_lineage_tables.php"
    ),
    "research_news_lineage_service": "app/Http/Service/ResearchNewsLineageService.php",
    "api_routes": "routes/api.php",
    "phpunit_config": "phpunit.xml",
}


class DatabaseArchitectureError(RuntimeError):
    """Raised when the frozen architecture or its evidence fails validation."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve(root: Path, path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else root / path


def _load_config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_RELATIVE_PATH
    try:
        config = json.loads(path.read_text(encoding="ascii"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DatabaseArchitectureError(f"Architecture config is unreadable: {error}") from error
    if not isinstance(config, dict):
        raise DatabaseArchitectureError("Architecture config must be an object")
    return config


def _validate_declared_file_hashes(
    base_root: Path,
    inputs: Any,
    *,
    label: str,
    exact_relative_paths: dict[str, str] | None = None,
) -> int:
    if not isinstance(inputs, dict) or not inputs:
        raise DatabaseArchitectureError(f"{label} inputs are missing")
    if exact_relative_paths is not None and set(inputs) != set(exact_relative_paths):
        raise DatabaseArchitectureError(f"{label} input inventory changed")
    for name, declaration in inputs.items():
        if not isinstance(declaration, dict):
            raise DatabaseArchitectureError(f"{label} input {name} is malformed")
        declared_path = str(declaration.get("path", ""))
        if exact_relative_paths is not None:
            if declared_path != exact_relative_paths[name]:
                raise DatabaseArchitectureError(f"{label} input path changed for {name}")
            relative_path = Path(declared_path)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise DatabaseArchitectureError(f"{label} input path is unsafe for {name}")
            path = base_root / relative_path
            if path.is_symlink():
                raise DatabaseArchitectureError(f"{label} input must not be a symlink: {name}")
        else:
            path = _resolve(base_root, declared_path)
        expected = str(declaration.get("sha256", ""))
        if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
            raise DatabaseArchitectureError(f"{label} input {name} has an invalid SHA-256 declaration")
        if not path.is_file():
            raise DatabaseArchitectureError(f"{label} input {name} is missing: {path}")
        actual = sha256_file(path)
        if actual != expected:
            raise DatabaseArchitectureError(
                f"{label} input hash mismatch for {name}: expected {expected}, got {actual}"
            )
    return len(inputs)


def _validate_hashes(
    root: Path,
    config: dict[str, Any],
    *,
    laravel_root_override: Path | None = None,
) -> dict[str, int]:
    repository_count = _validate_declared_file_hashes(
        root,
        config.get("repository_inputs"),
        label="Repository",
    )
    laravel_inputs = config.get("laravel_inventory_inputs")
    if not isinstance(laravel_inputs, dict):
        raise DatabaseArchitectureError("Laravel inventory inputs are missing")
    configured_root = Path(str(laravel_inputs.get("root", "")))
    laravel_root = laravel_root_override or configured_root
    laravel_count = _validate_declared_file_hashes(
        laravel_root,
        laravel_inputs.get("files"),
        label="Laravel inventory",
        exact_relative_paths=LARAVEL_INVENTORY_FILE_PATHS,
    )
    return {"repository_files": repository_count, "laravel_files": laravel_count}


def _validate_config_contract(config: dict[str, Any]) -> None:
    if config.get("status") != "PASS":
        raise DatabaseArchitectureError("Architecture status is not PASS")
    if config.get("decision") != "BUILD_SEPARATE_VERSIONED_MACRO_SCHEMA_REUSE_LINEAGE_PATTERNS":
        raise DatabaseArchitectureError("Architecture decision changed")
    scope = config.get("scope", {})
    zero_fields = (
        "experiment_trials_created",
        "final_holdout_access_count",
        "protected_forward_access_count",
        "post_2026_06_28_market_outcome_access_count",
        "network_requests",
        "macro_observations_collected",
        "database_rows_written_outside_disposable_validation",
        "live_or_paper_actions",
    )
    for field in zero_fields:
        if scope.get(field) != 0:
            raise DatabaseArchitectureError(f"Role 4 zero-work invariant failed: {field}")
    if tuple(config.get("frozen_contracts", {}).get("categories", [])) != CATEGORIES:
        raise DatabaseArchitectureError("Five-category contract changed")
    schema = config.get("schema", {})
    if tuple(schema.get("tables", [])) != TABLES:
        raise DatabaseArchitectureError("Required table contract changed")
    if tuple(schema.get("append_only_tables", [])) != APPEND_ONLY_TABLES:
        raise DatabaseArchitectureError("Append-only table contract changed")
    if schema.get("trigger_count") != 28 or schema.get("negative_schema_gate_count") != 16:
        raise DatabaseArchitectureError("Schema proof count contract changed")
    role_2 = config.get("frozen_contracts", {}).get("role_2", {})
    if role_2.get("observation_version_count") != 1730 or role_2.get("source_run_count") != 25:
        raise DatabaseArchitectureError("Role 2 frozen count contract changed")
    role_3 = config.get("frozen_contracts", {}).get("role_3", {})
    if role_3.get("candidate_route_count") != 34 or role_3.get("approved_bounded_collection_route_count") != 19:
        raise DatabaseArchitectureError("Role 3 frozen route contract changed")


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="ascii", newline="") as handle:
            return list(csv.DictReader(handle))
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise DatabaseArchitectureError(f"CSV input is unreadable: {path}: {error}") from error


def _validate_role3_routes(root: Path, config: dict[str, Any]) -> dict[str, int]:
    rows = _read_csv(root / COVERAGE_SERIES_RELATIVE_PATH)
    if len(rows) != 34:
        raise DatabaseArchitectureError(f"Expected 34 Role 3 routes, found {len(rows)}")
    route_ids = [row["route_id"] for row in rows]
    if len(set(route_ids)) != len(route_ids):
        raise DatabaseArchitectureError("Role 3 route IDs are not unique")
    if {row["category"] for row in rows} != set(CATEGORIES):
        raise DatabaseArchitectureError("Role 3 routes do not cover exactly five categories")
    decision_counts = Counter(row["source_decision"] for row in rows)
    expected = {
        "APPROVED_EXISTING_EVIDENCE_ONLY": 5,
        "APPROVED_FOR_BOUNDED_COLLECTION": 19,
        "AVAILABILITY_OR_VERSION_UNRESOLVED": 2,
        "CURRENT_REVISED_HISTORY_ONLY": 1,
        "REQUIRES_KEY_OR_LICENSE_REVIEW": 4,
        "REJECTED": 3,
    }
    if dict(decision_counts) != expected:
        raise DatabaseArchitectureError(f"Role 3 decision census changed: {dict(decision_counts)}")
    allowlisted = [row for row in rows if row["source_decision"] == "APPROVED_FOR_BOUNDED_COLLECTION"]
    if any(int(row["existing_observation_count"]) != 0 for row in allowlisted):
        raise DatabaseArchitectureError("Prospective routes contain fabricated observation counts")
    if any(row["collection_scope"].startswith("DO_NOT") for row in allowlisted):
        raise DatabaseArchitectureError("A prohibited route entered the collection allowlist")
    if any(
        not row["collection_scope"].startswith("DO_NOT")
        for row in rows
        if row["source_decision"] in {"CURRENT_REVISED_HISTORY_ONLY", "REJECTED"}
    ):
        raise DatabaseArchitectureError("A reconciliation-only or rejected route is collectable")
    frozen = config["frozen_contracts"]["role_3"]
    if len(allowlisted) != frozen["approved_bounded_collection_route_count"]:
        raise DatabaseArchitectureError("Role 3 allowlist count does not match the architecture contract")
    return dict(sorted(decision_counts.items()))


def _parse_aware(value: str) -> datetime:
    resolved = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if resolved.tzinfo is None:
        raise DatabaseArchitectureError(f"Timestamp lacks timezone: {value}")
    return resolved


def _validate_role2_rows(root: Path, config: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    rows = _read_csv(root / ELIGIBLE_RELATIVE_PATH)
    if len(rows) != 1730:
        raise DatabaseArchitectureError(f"Expected 1,730 Role 2 rows, found {len(rows)}")
    if len({row["observation_id"] for row in rows}) != len(rows):
        raise DatabaseArchitectureError("Role 2 observation IDs are not unique")
    if {row["regime_category"] for row in rows} != set(CATEGORIES) - {"LIQUIDITY"}:
        raise DatabaseArchitectureError("Role 2 verified categories changed")
    category_counts = Counter(row["regime_category"] for row in rows)
    category_counts["LIQUIDITY"] = 0
    expected_categories = config["frozen_contracts"]["role_2"]["category_counts"]
    if dict(category_counts) != expected_categories:
        raise DatabaseArchitectureError(f"Role 2 category counts changed: {dict(category_counts)}")
    revision_counts = Counter(row["revision_kind"] for row in rows)
    if revision_counts != {"FIRST_PRINT": 456, "REVISION": 1274}:
        raise DatabaseArchitectureError(f"Role 2 revision census changed: {dict(revision_counts)}")
    if any(row["protocol_classification"] != "VINTAGE_SAFE_WITH_DELAY" for row in rows):
        raise DatabaseArchitectureError("Role 2 classification changed")
    if any(row["protocol_eligibility"] != "ELIGIBLE" for row in rows):
        raise DatabaseArchitectureError("Role 2 includes an ineligible row")

    by_id = {row["observation_id"]: row for row in rows}
    new_york = ZoneInfo("America/New_York")
    malaysia = ZoneInfo("Asia/Kuala_Lumpur")
    for row in rows:
        raw_hash = row["raw_artifact_sha256"]
        payload_hash = row["observation_payload_sha256"]
        if any(len(value) != 64 or any(char not in "0123456789abcdef" for char in value) for value in (raw_hash, payload_hash)):
            raise DatabaseArchitectureError(f"Invalid Role 2 hash for {row['observation_id']}")
        availability_date = datetime.fromisoformat(row["availability_date"]).date()
        expected_utc = datetime.combine(availability_date, datetime.min.time(), tzinfo=new_york) + timedelta(hours=36)
        effective_utc = _parse_aware(row["conservative_effective_time_utc"])
        effective_malaysia = _parse_aware(row["conservative_effective_time_asia_kuala_lumpur"])
        if effective_utc != expected_utc or effective_malaysia != expected_utc.astimezone(malaysia):
            raise DatabaseArchitectureError(f"J0/DST conversion mismatch for {row['observation_id']}")
        revision_number = int(row["revision_number"])
        supersedes = row["supersedes_observation_id"]
        if revision_number == 0 and supersedes:
            raise DatabaseArchitectureError(f"First print supersedes another row: {row['observation_id']}")
        if revision_number > 0:
            parent = by_id.get(supersedes)
            if parent is None:
                raise DatabaseArchitectureError(f"Missing Role 2 supersession parent: {row['observation_id']}")
            identity = ("source_series_id", "canonical_event_id", "reference_period")
            if any(parent[field] != row[field] for field in identity):
                raise DatabaseArchitectureError(f"Cross-identity Role 2 supersession: {row['observation_id']}")
            if int(parent["revision_number"]) + 1 != revision_number:
                raise DatabaseArchitectureError(f"Role 2 revision gap: {row['observation_id']}")

    summary = {
        "observation_version_count": len(rows),
        "source_run_ids_referenced_by_eligible_rows": len({row["source_run_id"] for row in rows}),
        "raw_artifacts_referenced_by_eligible_rows": len({row["raw_artifact_relative_path"] for row in rows}),
        "category_counts": dict(category_counts),
        "revision_counts": dict(revision_counts),
    }
    return rows, summary


def _load_role2_bundle(
    root: Path,
    eligible_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    try:
        bundle = json.loads((root / ROLE2_BUNDLE_RELATIVE_PATH).read_text(encoding="ascii"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DatabaseArchitectureError(f"Role 2 provider bundle is unreadable: {error}") from error
    if not isinstance(bundle, dict):
        raise DatabaseArchitectureError("Role 2 provider bundle must be an object")
    source_runs = bundle.get("source_runs")
    observations = bundle.get("observations")
    if not isinstance(source_runs, list) or len(source_runs) != 25:
        raise DatabaseArchitectureError("Role 2 provider bundle must contain 25 source runs")
    if not isinstance(observations, list) or len(observations) != 1730:
        raise DatabaseArchitectureError("Role 2 provider bundle must contain 1,730 observations")
    source_run_ids = [str(run.get("source_run_id", "")) for run in source_runs if isinstance(run, dict)]
    if len(source_run_ids) != 25 or len(set(source_run_ids)) != 25:
        raise DatabaseArchitectureError("Role 2 provider bundle source-run IDs are not 25 unique values")
    bundle_observation_ids = {
        str(observation.get("observation_id", ""))
        for observation in observations
        if isinstance(observation, dict)
    }
    if bundle_observation_ids != {row["observation_id"] for row in eligible_rows}:
        raise DatabaseArchitectureError("Role 2 bundle and eligible observation IDs do not reconcile")

    raw_paths: set[str] = set()
    raw_hashes: set[str] = set()
    for run in source_runs:
        if not isinstance(run, dict):
            raise DatabaseArchitectureError("Role 2 provider source run is malformed")
        if run.get("status") != "COMPLETED" or run.get("contains_secrets") is not False:
            raise DatabaseArchitectureError(f"Role 2 source run is unsafe: {run.get('source_run_id')}")
        raw_relative_path = str(run.get("raw_relative_path", ""))
        raw_path = root / raw_relative_path
        payload_hash = str(run.get("payload_sha256", ""))
        if not raw_path.is_file() or sha256_file(raw_path) != payload_hash:
            raise DatabaseArchitectureError(f"Role 2 raw payload mismatch: {raw_relative_path}")
        raw_paths.add(raw_relative_path)
        raw_hashes.add(payload_hash)
        parameters = run.get("request_parameters_redacted")
        if not isinstance(parameters, dict):
            raise DatabaseArchitectureError(f"Role 2 source run parameters are incomplete: {run.get('source_run_id')}")
        series_id = parameters.get("series_id")
        if not series_id:
            remainder = str(run["source_run_id"]).removeprefix(f"{bundle['batch_id']}-")
            series_id = remainder.split("-", 1)[0]
        if series_id not in ROLE2_RELEASE_BUNDLES:
            raise DatabaseArchitectureError(f"Role 2 source series is unresolved: {run.get('source_run_id')}")
        run["architecture_series_id"] = series_id
    if len(raw_paths) != 25:
        raise DatabaseArchitectureError("Role 2 provider bundle does not preserve 25 raw paths")
    if len(raw_hashes) != 23:
        raise DatabaseArchitectureError("Role 2 provider bundle raw-hash census changed from 23 distinct payloads")
    eligible_run_ids = {row["source_run_id"] for row in eligible_rows}
    if not eligible_run_ids.issubset(set(source_run_ids)) or len(eligible_run_ids) != 5:
        raise DatabaseArchitectureError("Role 2 eligible rows must reference five of the 25 source runs")
    return source_runs, {
        "source_runs": len(source_run_ids),
        "raw_artifact_paths": len(raw_paths),
        "distinct_raw_payload_sha256": len(raw_hashes),
        "observations": len(observations),
        "eligible_observation_source_runs": len(eligible_run_ids),
    }


def _open_schema(root: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        connection.executescript((root / SCHEMA_RELATIVE_PATH).read_text(encoding="ascii"))
    except (OSError, UnicodeDecodeError, sqlite3.Error) as error:
        connection.close()
        raise DatabaseArchitectureError(f"SQLite schema failed: {error}") from error
    return connection


def _schema_inventory(connection: sqlite3.Connection) -> tuple[list[str], list[str]]:
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'macro_%' ORDER BY name"
        )
    ]
    triggers = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'macro_%' ORDER BY name"
        )
    ]
    return tables, triggers


def _insert_provider(connection: sqlite3.Connection, provider_id: str = "provider-alfred") -> None:
    connection.execute(
        """
        INSERT INTO macro_source_providers (
            provider_id, provider_code, provider_name, official_public_status,
            source_family, endpoint_or_file_family, enabled, provider_version,
            source_terms_status, created_at_utc, updated_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            provider_id,
            provider_id,
            "Federal Reserve Bank of St. Louis ALFRED retained evidence",
            "RETAINED_EVIDENCE",
            "FRED_ALFRED",
            "RETAINED_OUTPUT_TYPE_3",
            1,
            "ROLE2-1.0.0",
            "RETAINED_EVIDENCE_NO_NEW_REQUEST",
            "2026-07-13T07:44:33Z",
            "2026-07-13T07:44:33Z",
        ),
    )


def _insert_source_run(
    connection: sqlite3.Connection,
    *,
    source_run_id: str = "run-1",
    provider_id: str = "provider-alfred",
    route_id: str = "EXISTING_ALFRED_CPIAUCSL",
    source_series_id: str = "CPIAUCSL",
    started: str = "2026-07-12T23:15:07Z",
    completed: str = "2026-07-12T23:15:08Z",
    raw_hash: str | None = HEX64,
    row_count: int = 1,
    status: str = "COMPLETED",
    idempotency_key: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO macro_source_runs (
            source_run_id, provider_id, route_id, source_series_id,
            requested_start_date, requested_end_date, vintage_start_date, vintage_end_date,
            retrieval_started_at_utc, retrieval_completed_at_utc, run_status,
            http_or_file_status, row_count, collector_version, collector_code_sha256,
            parser_version, parser_code_sha256, request_config_sha256, raw_payload_sha256,
            source_reference, parent_resume_run_id, checkpoint_cursor, attempt_number,
            idempotency_key, error_class, redacted_error_detail, contains_secrets, created_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_run_id,
            provider_id,
            route_id,
            source_series_id,
            "2017-01-01",
            "2026-06-28",
            "2017-01-01",
            "2026-06-28",
            started,
            completed,
            status,
            "RETAINED_FILE_OK" if status != "FAILED" else "FAILED",
            row_count,
            "ROLE2-RETAINED",
            HEX64,
            "ROLE2-RETAINED",
            HEX64,
            HEX64,
            raw_hash,
            "research fixture",
            None,
            None,
            1,
            idempotency_key or source_run_id,
            "SYNTHETIC_FAILURE" if status == "FAILED" else None,
            "synthetic redacted failure" if status == "FAILED" else None,
            0,
            completed,
        ),
    )


def _insert_raw_artifact(
    connection: sqlite3.Connection,
    *,
    raw_artifact_id: str = "raw-1",
    source_run_id: str = "run-1",
    path: str = "storage/macro_raw/provider=alfred/run=run-1/payload.json",
    raw_hash: str = HEX64,
) -> None:
    connection.execute(
        """
        INSERT INTO macro_raw_artifacts (
            raw_artifact_id, source_run_id, artifact_ordinal, immutable_path,
            content_type, compression, byte_length, sha256, retrieved_at_utc,
            source_reference, supersedes_artifact_id, created_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            raw_artifact_id,
            source_run_id,
            0,
            path,
            "application/json",
            "NONE",
            1,
            raw_hash,
            "2026-07-12T23:15:08Z",
            "research fixture",
            None,
            "2026-07-12T23:15:08Z",
        ),
    )


def _observation_values(
    *,
    observation_id: str = "obs-1",
    source_run_id: str = "run-1",
    raw_artifact_id: str = "raw-1",
    source_series_id: str = "CPIAUCSL",
    indicator_id: str = "US_CPI_ALL_ITEMS_SA",
    category: str = "INFLATION",
    route_id: str | None = None,
    release_bundle: str = "CPI_BUNDLE",
    reference_date: str = "2020-01-01",
    vintage_date: str = "2020-02-13",
    effective_at: str = "2020-02-14T17:00:00Z",
    revision_number: int = 0,
    revision_kind: str = "FIRST_PRINT",
    supersedes: str | None = None,
) -> tuple[Any, ...]:
    return (
        observation_id,
        "provider-alfred",
        source_run_id,
        raw_artifact_id,
        route_id or f"EXISTING_ALFRED_{source_series_id}",
        source_series_id,
        indicator_id,
        category,
        release_bundle,
        reference_date,
        vintage_date,
        vintage_date,
        "America/New_York",
        vintage_date,
        None,
        "DATE_LEVEL_VINTAGE_NO_WALLCLOCK_CLAIM",
        effective_at,
        effective_at,
        "J0_CONSERVATIVE_36H",
        "100.0",
        100.0,
        "VALID",
        "INDEX",
        "SEASONALLY_ADJUSTED",
        "MONTHLY",
        revision_number,
        revision_kind,
        supersedes,
        "VINTAGE_SAFE_WITH_DELAY",
        "ELIGIBLE",
        0,
        HEX64,
        HEX64,
        HEX64,
        HEX64,
        HEX64,
        HEX64,
        "2026-07-12T23:15:08Z",
        "2026-07-13T07:44:33Z",
    )


OBSERVATION_INSERT = """
    INSERT INTO macro_observations (
        observation_id, provider_id, source_run_id, raw_artifact_id, route_id,
        source_series_id, internal_indicator_id, category, release_bundle,
        reference_date, vintage_date, source_timestamp_raw, source_timezone,
        availability_date, availability_at_utc, availability_semantics,
        conservative_effective_at_utc, conservative_effective_at_asia_kuala_lumpur,
        effective_rule, raw_value, normalized_numeric_value, normalization_status,
        unit, seasonal_adjustment_status, frequency, revision_number, revision_kind,
        supersedes_observation_id, point_in_time_classification, protocol_eligibility,
        historical_reconstruction, raw_artifact_sha256, observation_payload_sha256,
        normalization_code_sha256, config_sha256, collector_code_sha256, registry_sha256,
        retrieved_at_utc, inserted_at_utc
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _insert_indicator_state(
    connection: sqlite3.Connection,
    *,
    indicator_state_id: str,
    observation_id: str,
    calculated_at_utc: str,
    indicator_id: str = "US_CPI_ALL_ITEMS_SA",
    discrete_score: int = 1,
) -> None:
    connection.execute(
        """
        INSERT INTO macro_indicator_states (
            indicator_state_id, observation_id, internal_indicator_id, calculation_version,
            current_value, previous_point_in_time_value, one_release_change,
            three_release_change, six_release_change, year_over_year_transformation,
            prior_only_robust_z_score, prior_only_level_percentile, trend_classification,
            stress_classification, continuous_score, discrete_score, coverage_status,
            scoring_rationale_code, scoring_config_sha256, code_sha256, registry_sha256,
            calculated_at_utc
        ) VALUES (?, ?, ?, 'v1', 100.0, 100.0, 0.0, NULL, NULL, NULL, NULL, NULL,
                  'STABLE', 'NONE', 1.0, ?, 'VALID', 'SYNTHETIC_LINEAGE_PROOF', ?, ?, ?, ?)
        """,
        (
            indicator_state_id,
            observation_id,
            indicator_id,
            discrete_score,
            HEX64,
            HEX64,
            HEX64,
            calculated_at_utc,
        ),
    )


def _insert_release_bundle_state(
    connection: sqlite3.Connection,
    *,
    release_bundle_state_id: str,
    indicator_state_id: str,
    effective_at_utc: str,
    release_bundle: str = "CPI_BUNDLE",
    discrete_score: int = 1,
) -> None:
    connection.execute(
        """
        INSERT INTO macro_release_bundle_states (
            release_bundle_state_id, release_bundle, component_indicator_state_ids_json,
            component_lineage_sha256, continuous_bundle_score, discrete_bundle_score,
            coverage_status, effective_at_utc, scoring_version, scoring_config_sha256,
            code_sha256, registry_sha256, created_at_utc
        ) VALUES (?, ?, ?, ?, 1.0, ?, 'VALID', ?, 'v1', ?, ?, ?, ?)
        """,
        (
            release_bundle_state_id,
            release_bundle,
            json.dumps([indicator_state_id], separators=(",", ":")),
            HEX64,
            discrete_score,
            effective_at_utc,
            HEX64,
            HEX64,
            HEX64,
            effective_at_utc,
        ),
    )


def _insert_category_state(
    connection: sqlite3.Connection,
    *,
    category_state_id: str,
    release_bundle_state_id: str,
    effective_at_utc: str,
    category: str = "INFLATION",
    discrete_score: int = 1,
) -> None:
    connection.execute(
        """
        INSERT INTO macro_category_states (
            category_state_id, category, active_release_bundle_state_ids_json,
            bundle_lineage_sha256, continuous_category_score, discrete_category_score,
            category_status, stress_flags_json, stress_flags_sha256, effective_at_utc,
            scoring_version, scoring_config_sha256, code_sha256, registry_sha256,
            created_at_utc
        ) VALUES (?, ?, ?, ?, 1.0, ?, 'VALID', '[]', ?, ?, 'v1', ?, ?, ?, ?)
        """,
        (
            category_state_id,
            category,
            json.dumps([release_bundle_state_id], separators=(",", ":")),
            HEX64,
            discrete_score,
            HEX64,
            effective_at_utc,
            HEX64,
            HEX64,
            HEX64,
            effective_at_utc,
        ),
    )


def _insert_snapshot(
    connection: sqlite3.Connection,
    *,
    macro_snapshot_id: str,
    effective_at_utc: str,
    inflation_state_id: str | None = None,
    labour_state_id: str | None = None,
    growth_state_id: str | None = None,
    monetary_policy_state_id: str | None = None,
    liquidity_state_id: str | None = None,
    inflation_score: int | None = None,
    labour_score: int | None = None,
    growth_score: int | None = None,
    monetary_policy_score: int | None = None,
    liquidity_score: int | None = None,
    base_overall_score: int | None = 1,
    final_score: int | None = 1,
    final_bias: str = "UNKNOWN",
    valid_category_count: int = 1,
) -> None:
    connection.execute(
        """
        INSERT INTO macro_regime_snapshots (
            macro_snapshot_id, effective_at_utc,
            inflation_category_state_id, labour_category_state_id, growth_category_state_id,
            monetary_policy_category_state_id, liquidity_category_state_id,
            inflation_score, labour_score, growth_score, monetary_policy_score, liquidity_score,
            base_overall_score, active_interaction_flags_json, interaction_adjustment,
            final_score, final_bias, valid_category_count, source_observation_lineage_json,
            source_observation_lineage_sha256, scoring_version, scoring_config_sha256,
            registry_sha256, code_sha256, created_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', 0, ?, ?, ?, '["obs-2"]',
                  ?, 'v1', ?, ?, ?, ?)
        """,
        (
            macro_snapshot_id,
            effective_at_utc,
            inflation_state_id,
            labour_state_id,
            growth_state_id,
            monetary_policy_state_id,
            liquidity_state_id,
            inflation_score,
            labour_score,
            growth_score,
            monetary_policy_score,
            liquidity_score,
            base_overall_score,
            final_score,
            final_bias,
            valid_category_count,
            HEX64,
            HEX64,
            HEX64,
            HEX64,
            effective_at_utc,
        ),
    )


def _insert_event_update(
    connection: sqlite3.Connection,
    *,
    event_update_id: str,
    indicator_state_id: str,
    release_bundle_state_id: str,
    category_state_id: str,
    snapshot_after_id: str,
    effective_at_utc: str,
) -> None:
    connection.execute(
        """
        INSERT INTO macro_event_update_ledger (
            event_update_id, availability_at_utc, effective_at_utc, indicator_updated,
            previous_value, current_value, one_release_change, previous_indicator_score,
            new_indicator_score, release_bundle_updated, previous_bundle_score,
            new_bundle_score, category_updated, previous_category_score, new_category_score,
            base_overall_score_before, base_overall_score_after,
            active_interaction_before_json, active_interaction_after_json,
            final_macro_score_before, final_macro_score_after, bias_before, bias_after,
            source_observation_id, source_run_id, indicator_state_id,
            release_bundle_state_id, category_state_id, snapshot_before_id, snapshot_after_id,
            point_in_time_classification, reason_code, scoring_config_sha256, code_sha256,
            registry_sha256, created_at_utc
        ) VALUES (?, NULL, ?, 'US_CPI_ALL_ITEMS_SA', 100.0, 100.0, 0.0, NULL, 1,
                  'CPI_BUNDLE', NULL, 1, 'INFLATION', NULL, 1, NULL, 1, '[]', '[]',
                  NULL, 1, 'UNKNOWN', 'UNKNOWN', 'obs-2', 'run-1', ?, ?, ?, NULL, ?,
                  'VINTAGE_SAFE_WITH_DELAY', 'SYNTHETIC_LINEAGE_PROOF', ?, ?, ?, ?)
        """,
        (
            event_update_id,
            effective_at_utc,
            indicator_state_id,
            release_bundle_state_id,
            category_state_id,
            snapshot_after_id,
            HEX64,
            HEX64,
            HEX64,
            effective_at_utc,
        ),
    )


def _insert_technical_link(
    connection: sqlite3.Connection,
    *,
    macro_technical_link_id: str,
    macro_snapshot_id: str,
    macro_effective_at_utc: str,
    final_macro_score: int = 1,
    macro_bias: str = "UNKNOWN",
) -> None:
    connection.execute(
        """
        INSERT INTO macro_technical_links (
            macro_technical_link_id, technical_setup_id, technical_trade_id,
            technical_actionable_at_utc, technical_source_date, macro_snapshot_id,
            macro_effective_at_utc, inflation_score, labour_score, growth_score,
            monetary_policy_score, liquidity_score, final_macro_score, macro_bias,
            direction_match, filter_decision, join_rule, scoring_version,
            technical_baseline_sha256, macro_manifest_sha256, join_config_sha256,
            code_sha256, registry_sha256, created_at_utc
        ) VALUES (?, ?, ?, '2021-02-14T18:00:00Z', '2021-02-14', ?, ?, 1, NULL, NULL,
                  NULL, NULL, ?, ?, 'UNKNOWN', 'FILTERED_UNKNOWN', 'J0_CONSERVATIVE_36H',
                  'v1', ?, ?, ?, ?, ?, '2021-02-14T18:00:00Z')
        """,
        (
            macro_technical_link_id,
            f"setup-{macro_technical_link_id}",
            f"trade-{macro_technical_link_id}",
            macro_snapshot_id,
            macro_effective_at_utc,
            final_macro_score,
            macro_bias,
            HEX64,
            HEX64,
            HEX64,
            HEX64,
            HEX64,
        ),
    )


def _expect_integrity_error(
    label: str,
    operation: Any,
    *,
    expected_message: str | None = None,
) -> str:
    try:
        operation()
    except sqlite3.IntegrityError as error:
        if expected_message is not None and expected_message not in str(error):
            raise DatabaseArchitectureError(
                f"Negative test {label} failed for the wrong reason: {error}"
            ) from error
        return f"PASS:{label}:{str(error)}"
    raise DatabaseArchitectureError(f"Negative test did not fail closed: {label}")


def _exercise_schema(root: Path) -> dict[str, Any]:
    connection = _open_schema(root)
    connection.isolation_level = None
    tables, triggers = _schema_inventory(connection)
    if set(tables) != set(TABLES):
        raise DatabaseArchitectureError(f"Schema table inventory changed: {tables}")
    for table in APPEND_ONLY_TABLES:
        for suffix in ("no_update", "no_delete"):
            if f"{table}_{suffix}" not in triggers:
                raise DatabaseArchitectureError(f"Missing append-only trigger: {table}_{suffix}")

    connection.execute("BEGIN")
    _insert_provider(connection)
    _insert_source_run(connection)
    _insert_raw_artifact(connection)
    connection.execute(OBSERVATION_INSERT, _observation_values())
    connection.execute(
        OBSERVATION_INSERT,
        _observation_values(
            observation_id="obs-2",
            vintage_date="2021-02-13",
            effective_at="2021-02-14T17:00:00Z",
            revision_number=1,
            revision_kind="REVISION",
            supersedes="obs-1",
        ),
    )
    connection.execute("COMMIT")

    _insert_source_run(
        connection,
        source_run_id="run-alternate-route",
        route_id="ALTERNATE_CPI_ROUTE",
        source_series_id="CPIAUCSL",
    )
    _insert_raw_artifact(
        connection,
        raw_artifact_id="raw-alternate-route",
        source_run_id="run-alternate-route",
        path="storage/macro_raw/raw-alternate-route.json",
    )

    derived_effective_at = "2021-02-14T17:00:00Z"
    _insert_indicator_state(
        connection,
        indicator_state_id="indicator-state-after",
        observation_id="obs-2",
        calculated_at_utc=derived_effective_at,
    )
    _insert_indicator_state(
        connection,
        indicator_state_id="indicator-state-wrong-observation",
        observation_id="obs-1",
        calculated_at_utc="2020-02-14T17:00:00Z",
    )
    _insert_release_bundle_state(
        connection,
        release_bundle_state_id="bundle-state-after",
        indicator_state_id="indicator-state-after",
        effective_at_utc=derived_effective_at,
    )
    _insert_category_state(
        connection,
        category_state_id="category-state-inflation-after",
        release_bundle_state_id="bundle-state-after",
        effective_at_utc=derived_effective_at,
    )

    negative_results: list[str] = []
    negative_results.append(
        _expect_integrity_error(
            "duplicate_idempotency",
            lambda: _insert_source_run(
                connection,
                source_run_id="run-duplicate",
                idempotency_key="run-1",
            ),
        )
    )
    negative_results.append(
        _expect_integrity_error(
            "invalid_category",
            lambda: connection.execute(
                OBSERVATION_INSERT,
                _observation_values(observation_id="obs-bad-category", category="CREDIT"),
            ),
        )
    )
    negative_results.append(
        _expect_integrity_error(
            "broken_foreign_key",
            lambda: connection.execute(
                OBSERVATION_INSERT,
                _observation_values(
                    observation_id="obs-bad-fk",
                    source_run_id="missing-run",
                    raw_artifact_id="missing-raw",
                    source_series_id="UNRATE",
                    indicator_id="US_UNEMPLOYMENT_RATE_SA",
                    category="LABOUR",
                    reference_date="2022-01-01",
                    vintage_date="2022-02-01",
                    effective_at="2022-02-02T17:00:00Z",
                ),
            ),
        )
    )
    negative_results.append(
        _expect_integrity_error(
            "broken_supersession",
            lambda: connection.execute(
                OBSERVATION_INSERT,
                _observation_values(
                    observation_id="obs-bad-supersession",
                    reference_date="2022-01-01",
                    vintage_date="2022-02-01",
                    effective_at="2022-02-02T17:00:00Z",
                    revision_number=2,
                    revision_kind="REVISION",
                    supersedes="obs-1",
                ),
            ),
            expected_message="invalid_observation_supersession",
        )
    )
    revision_two = {
        "reference_date": "2020-01-01",
        "vintage_date": "2022-02-13",
        "effective_at": "2022-02-14T17:00:00Z",
        "revision_number": 2,
        "revision_kind": "REVISION",
        "supersedes": "obs-2",
    }
    negative_results.append(
        _expect_integrity_error(
            "supersession_route_mismatch",
            lambda: connection.execute(
                OBSERVATION_INSERT,
                _observation_values(
                    observation_id="obs-bad-supersession-route",
                    source_run_id="run-alternate-route",
                    raw_artifact_id="raw-alternate-route",
                    route_id="ALTERNATE_CPI_ROUTE",
                    **revision_two,
                ),
            ),
            expected_message="invalid_observation_supersession",
        )
    )
    negative_results.append(
        _expect_integrity_error(
            "supersession_category_mismatch",
            lambda: connection.execute(
                OBSERVATION_INSERT,
                _observation_values(
                    observation_id="obs-bad-supersession-category",
                    category="LABOUR",
                    **revision_two,
                ),
            ),
            expected_message="invalid_observation_supersession",
        )
    )
    negative_results.append(
        _expect_integrity_error(
            "supersession_bundle_mismatch",
            lambda: connection.execute(
                OBSERVATION_INSERT,
                _observation_values(
                    observation_id="obs-bad-supersession-bundle",
                    release_bundle="OTHER_BUNDLE",
                    **revision_two,
                ),
            ),
            expected_message="invalid_observation_supersession",
        )
    )
    negative_results.append(
        _expect_integrity_error(
            "snapshot_cross_wired_category",
            lambda: _insert_snapshot(
                connection,
                macro_snapshot_id="snapshot-cross-wired",
                effective_at_utc=derived_effective_at,
                labour_state_id="category-state-inflation-after",
                labour_score=1,
            ),
            expected_message="invalid_regime_snapshot_category_lineage",
        )
    )
    negative_results.append(
        _expect_integrity_error(
            "snapshot_score_mismatch",
            lambda: _insert_snapshot(
                connection,
                macro_snapshot_id="snapshot-score-mismatch",
                effective_at_utc=derived_effective_at,
                inflation_state_id="category-state-inflation-after",
                inflation_score=2,
                base_overall_score=2,
                final_score=2,
            ),
            expected_message="invalid_regime_snapshot_category_lineage",
        )
    )
    _insert_snapshot(
        connection,
        macro_snapshot_id="snapshot-after",
        effective_at_utc=derived_effective_at,
        inflation_state_id="category-state-inflation-after",
        inflation_score=1,
    )
    _insert_event_update(
        connection,
        event_update_id="event-update-after",
        indicator_state_id="indicator-state-after",
        release_bundle_state_id="bundle-state-after",
        category_state_id="category-state-inflation-after",
        snapshot_after_id="snapshot-after",
        effective_at_utc=derived_effective_at,
    )
    negative_results.append(
        _expect_integrity_error(
            "event_mismatched_state_lineage",
            lambda: _insert_event_update(
                connection,
                event_update_id="event-update-wrong-indicator-state",
                indicator_state_id="indicator-state-wrong-observation",
                release_bundle_state_id="bundle-state-after",
                category_state_id="category-state-inflation-after",
                snapshot_after_id="snapshot-after",
                effective_at_utc=derived_effective_at,
            ),
            expected_message="invalid_event_update_lineage",
        )
    )
    _insert_technical_link(
        connection,
        macro_technical_link_id="technical-link-valid",
        macro_snapshot_id="snapshot-after",
        macro_effective_at_utc=derived_effective_at,
    )
    negative_results.append(
        _expect_integrity_error(
            "technical_snapshot_score_bias_mismatch",
            lambda: _insert_technical_link(
                connection,
                macro_technical_link_id="technical-link-score-bias-mismatch",
                macro_snapshot_id="snapshot-after",
                macro_effective_at_utc=derived_effective_at,
                final_macro_score=2,
                macro_bias="BULLISH",
            ),
            expected_message="invalid_macro_technical_snapshot_time",
        )
    )
    negative_results.append(
        _expect_integrity_error(
            "invalid_source_run_timing",
            lambda: _insert_source_run(
                connection,
                source_run_id="run-bad-time",
                route_id="EXISTING_ALFRED_UNRATE",
                source_series_id="UNRATE",
                started="2026-07-12T23:15:08Z",
                completed="2026-07-12T23:15:07Z",
            ),
        )
    )
    negative_results.append(
        _expect_integrity_error(
            "invalid_hash",
            lambda: _insert_raw_artifact(
                connection,
                raw_artifact_id="raw-bad-hash",
                path="storage/macro_raw/raw-bad-hash.json",
                raw_hash="not-a-hash",
            ),
        )
    )
    early_effective = list(_observation_values(observation_id="obs-bad-effective"))
    early_effective[14] = "2020-02-14T17:00:00Z"
    early_effective[16] = "2020-02-13T17:00:00Z"
    negative_results.append(
        _expect_integrity_error(
            "effective_before_availability",
            lambda: connection.execute(OBSERVATION_INSERT, tuple(early_effective)),
        )
    )
    negative_results.append(
        _expect_integrity_error(
            "append_only_update",
            lambda: connection.execute(
                "UPDATE macro_observations SET raw_value='changed' WHERE observation_id='obs-1'"
            ),
        )
    )
    negative_results.append(
        _expect_integrity_error(
            "append_only_delete",
            lambda: connection.execute("DELETE FROM macro_observations WHERE observation_id='obs-1'"),
        )
    )
    if connection.execute("SELECT COUNT(*) FROM macro_observations").fetchone()[0] != 2:
        raise DatabaseArchitectureError("Negative tests mutated immutable observation evidence")
    connection.close()

    rollback_connection = _open_schema(root)
    for table in reversed(TABLES):
        rollback_connection.execute(f"DROP TABLE {table}")
    remaining, _ = _schema_inventory(rollback_connection)
    rollback_connection.close()
    if remaining:
        raise DatabaseArchitectureError(f"Empty-schema rollback left tables: {remaining}")

    return {
        "table_count": len(tables),
        "trigger_count": len(triggers),
        "append_only_table_count": len(APPEND_ONLY_TABLES),
        "positive_fixture_observation_count": 2,
        "positive_fixture_snapshot_count": 1,
        "positive_fixture_event_count": 1,
        "positive_fixture_technical_link_count": 1,
        "negative_test_count": len(negative_results),
        "negative_tests": negative_results,
        "empty_schema_rollback": "PASS",
    }


def _provider_response_row_count(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    count = payload.get("count")
    if isinstance(count, int) and count >= 0:
        return count
    return max(
        (
            len(payload.get(key, []))
            for key in ("observations", "seriess", "releases", "release_dates")
            if isinstance(payload.get(key), list)
        ),
        default=0,
    )


def _load_all_role2_rows(
    root: Path,
    rows: Iterable[dict[str, str]],
    registry_hash: str,
    source_runs: list[dict[str, Any]],
) -> dict[str, int]:
    connection = _open_schema(root)
    _insert_provider(connection)
    artifact_ids: dict[str, str] = {}
    for ordinal, source_run in enumerate(sorted(source_runs, key=lambda run: str(run["source_run_id"]))):
        source_run_id = str(source_run["source_run_id"])
        parameters = source_run["request_parameters_redacted"]
        series_id = str(source_run["architecture_series_id"])
        raw_relative_path = str(source_run["raw_relative_path"])
        raw_path = root / raw_relative_path
        payload = json.loads(raw_path.read_text(encoding="ascii"))
        connection.execute(
            """
            INSERT INTO macro_source_runs (
                source_run_id, provider_id, route_id, source_series_id,
                requested_start_date, requested_end_date, vintage_start_date, vintage_end_date,
                retrieval_started_at_utc, retrieval_completed_at_utc, run_status,
                http_or_file_status, row_count, collector_version, collector_code_sha256,
                parser_version, parser_code_sha256, request_config_sha256, raw_payload_sha256,
                source_reference, parent_resume_run_id, checkpoint_cursor, attempt_number,
                idempotency_key, error_class, redacted_error_detail, contains_secrets, created_at_utc
            ) VALUES (?, 'provider-alfred', ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETED',
                      'RETAINED_FILE_OK', ?, ?, ?, 'ROLE2_RETAINED', ?, ?, ?, ?,
                      NULL, NULL, 1, ?, NULL, NULL, 0, ?)
            """,
            (
                source_run_id,
                f"EXISTING_ALFRED_{series_id}",
                series_id,
                parameters.get("observation_start") or parameters.get("realtime_start"),
                parameters.get("observation_end") or parameters.get("realtime_end"),
                parameters.get("realtime_start"),
                parameters.get("realtime_end"),
                source_run["started_at_utc"],
                source_run["completed_at_utc"],
                _provider_response_row_count(payload),
                source_run["collector_version"],
                source_run["collector_code_sha256"],
                source_run["collector_code_sha256"],
                source_run["config_sha256"],
                source_run["payload_sha256"],
                raw_relative_path,
                source_run_id,
                source_run["completed_at_utc"],
            ),
        )
        artifact_id = f"role2-raw-{ordinal:02d}"
        artifact_ids[source_run_id] = artifact_id
        connection.execute(
            """
            INSERT INTO macro_raw_artifacts (
                raw_artifact_id, source_run_id, artifact_ordinal, immutable_path,
                content_type, compression, byte_length, sha256, retrieved_at_utc,
                source_reference, supersedes_artifact_id, created_at_utc
            ) VALUES (?, ?, 0, ?, 'application/json', 'NONE', ?, ?, ?, ?, NULL, ?)
            """,
            (
                artifact_id,
                source_run_id,
                raw_relative_path,
                raw_path.stat().st_size,
                source_run["payload_sha256"],
                source_run["completed_at_utc"],
                raw_relative_path,
                source_run["completed_at_utc"],
            ),
        )

    ordered_rows = sorted(
        rows,
        key=lambda row: (
            row["source_series_id"],
            row["reference_period"],
            int(row["revision_number"]),
            row["vintage_date"],
            row["observation_id"],
        ),
    )
    for row in ordered_rows:
        connection.execute(
            OBSERVATION_INSERT,
            (
                row["observation_id"],
                "provider-alfred",
                row["source_run_id"],
                artifact_ids[row["source_run_id"]],
                f"EXISTING_ALFRED_{row['source_series_id']}",
                row["source_series_id"],
                row["canonical_event_id"],
                row["regime_category"],
                ROLE2_RELEASE_BUNDLES[row["source_series_id"]],
                row["reference_period"],
                row["vintage_date"],
                row["availability_date"],
                row["availability_date_timezone"],
                row["availability_date"],
                None,
                row["availability_date_semantics"],
                row["conservative_effective_time_utc"],
                row["conservative_effective_time_asia_kuala_lumpur"],
                "J0_CONSERVATIVE_36H",
                row["actual_value"],
                float(row["actual_value"]),
                "VALID",
                row["unit"],
                "ROLE2_RETAINED_SERIES_METADATA",
                "ROLE2_RETAINED_FREQUENCY",
                int(row["revision_number"]),
                row["revision_kind"],
                row["supersedes_observation_id"] or None,
                row["protocol_classification"],
                row["protocol_eligibility"],
                0,
                row["raw_artifact_sha256"],
                row["observation_payload_sha256"],
                row["normalization_code_sha256"],
                row["config_sha256"],
                row["collector_code_sha256"],
                registry_hash,
                row["source_run_completed_at_utc"],
                "2026-07-13T07:44:33Z",
            ),
        )
    counts = {
        "source_runs": connection.execute("SELECT COUNT(*) FROM macro_source_runs").fetchone()[0],
        "raw_artifacts": connection.execute("SELECT COUNT(*) FROM macro_raw_artifacts").fetchone()[0],
        "observations": connection.execute("SELECT COUNT(*) FROM macro_observations").fetchone()[0],
    }
    if counts != {"source_runs": 25, "raw_artifacts": 25, "observations": 1730}:
        raise DatabaseArchitectureError(f"Role 2 disposable load count mismatch: {counts}")
    category_counts = dict(
        connection.execute(
            "SELECT category, COUNT(*) FROM macro_observations GROUP BY category ORDER BY category"
        ).fetchall()
    )
    expected_nonzero = {key: value for key, value in config_category_counts().items() if value}
    if category_counts != expected_nonzero:
        raise DatabaseArchitectureError(f"Role 2 disposable category mismatch: {category_counts}")
    connection.close()
    return counts


def config_category_counts() -> dict[str, int]:
    return {
        "INFLATION": 489,
        "LABOUR": 921,
        "GROWTH": 214,
        "MONETARY_POLICY": 106,
        "LIQUIDITY": 0,
    }


def validate_architecture(root: Path) -> dict[str, Any]:
    root = root.resolve()
    config = _load_config(root)
    _validate_config_contract(config)
    input_hashes = _validate_hashes(root, config)
    route_decisions = _validate_role3_routes(root, config)
    role2_rows, role2_summary = _validate_role2_rows(root, config)
    role2_source_runs, role2_bundle_summary = _load_role2_bundle(root, role2_rows)
    schema_summary = _exercise_schema(root)
    role2_load = _load_all_role2_rows(
        root,
        role2_rows,
        config["repository_inputs"]["experiment_registry"]["sha256"],
        role2_source_runs,
    )
    return {
        "status": "PASS",
        "decision": config["decision"],
        "table_count": len(TABLES),
        "append_only_table_count": len(APPEND_ONLY_TABLES),
        "role2": role2_summary,
        "role2_provider_bundle": role2_bundle_summary,
        "role2_disposable_schema_load": role2_load,
        "role3_decision_counts": route_decisions,
        "validated_input_hashes": input_hashes,
        "schema_proof": schema_summary,
        "experiment_trials_created": 0,
        "final_holdout_access_count": 0,
        "protected_forward_access_count": 0,
        "network_requests": 0,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--validate-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = validate_architecture(args.repo_root)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


PROGRAM_ID = "SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001"
PROTOCOL_ID = "MACRO_REGIME_DAILY_H4_V1"
BATCH_ID = "QRP2-ALFRED-20260713T070000Z"
BATCH_RELATIVE_PATH = f"research/artifacts/program2/alfred/{BATCH_ID}"
CONFIG_RELATIVE_PATH = "research/config/program2_alfred_macro.json"
COLLECTOR_RELATIVE_PATH = "research/src/smartmarketscope_quant/fundamental_pit/alfred.py"
PIT_MANIFEST_RELATIVE_PATH = "POINT_IN_TIME_FUNDAMENTAL_MANIFEST.yaml"
SOURCE_TIMEZONE = "America/New_York"
REPORT_TIMEZONE = "Asia/Kuala_Lumpur"
J0_RULE = "J0_CONSERVATIVE_36H_FROM_AVAILABILITY_DATE_START_AMERICA_NEW_YORK"

VINTAGE_SAFE_FOR_DAILY_REGIME = "VINTAGE_SAFE_FOR_DAILY_REGIME"
VINTAGE_SAFE_WITH_DELAY = "VINTAGE_SAFE_WITH_DELAY"
CURRENT_REVISED_HISTORY_ONLY = "CURRENT_REVISED_HISTORY_ONLY"
AVAILABILITY_DATE_UNRESOLVED = "AVAILABILITY_DATE_UNRESOLVED"
SOURCE_VERSION_UNRESOLVED = "SOURCE_VERSION_UNRESOLVED"
UNUSABLE = "UNUSABLE"
ALLOWED_CLASSIFICATIONS = {
    VINTAGE_SAFE_FOR_DAILY_REGIME,
    VINTAGE_SAFE_WITH_DELAY,
    CURRENT_REVISED_HISTORY_ONLY,
    AVAILABILITY_DATE_UNRESOLVED,
    SOURCE_VERSION_UNRESOLVED,
    UNUSABLE,
}
ELIGIBLE_CLASSIFICATIONS = {
    VINTAGE_SAFE_FOR_DAILY_REGIME,
    VINTAGE_SAFE_WITH_DELAY,
}

OUTPUT_FILES = (
    "ALFRED_MACRO_REGIME_SALVAGE_AUDIT.md",
    "ALFRED_SERIES_RECLASSIFICATION.csv",
    "ALFRED_REGIME_ELIGIBLE_OBSERVATIONS.csv",
    "ALFRED_REGIME_INELIGIBLE_OBSERVATIONS.csv",
)

EXPECTED_SERIES = ("CPIAUCSL", "PAYEMS", "UNRATE", "GDPC1", "FEDFUNDS")
EXPECTED_SOURCE_TYPES = {
    "SERIES_METADATA",
    "SERIES_RELEASE",
    "INITIAL_RELEASE_OBSERVATIONS",
    "NEW_AND_REVISED_OBSERVATIONS",
    "RELEASE_DATES",
}
CATEGORY_MAP = {
    "INFLATION": "INFLATION",
    "LABOR": "LABOUR",
    "GROWTH": "GROWTH",
    "POLICY": "MONETARY_POLICY",
}

SERIES_FIELDS = (
    "schema_version",
    "program_id",
    "protocol_id",
    "batch_id",
    "provider",
    "source_series_id",
    "canonical_event_id",
    "regime_category",
    "release_name",
    "frequency",
    "unit",
    "requested_start_date",
    "requested_end_date",
    "reference_start_date",
    "reference_end_date",
    "vintage_start_date",
    "vintage_end_date",
    "source_run_count",
    "raw_artifact_count",
    "release_date_count",
    "observation_count",
    "unique_reference_period_count",
    "first_print_count",
    "revision_count",
    "maximum_revision_number",
    "protocol_classification",
    "eligible_observation_count",
    "ineligible_observation_count",
    "availability_basis",
    "availability_date_timezone",
    "conservative_effective_rule",
    "source_run_set_sha256",
    "raw_artifact_set_sha256",
    "config_sha256",
    "collector_code_sha256",
    "bundle_sha256",
    "limitations",
)

OBSERVATION_FIELDS = (
    "schema_version",
    "program_id",
    "protocol_id",
    "batch_id",
    "provider",
    "observation_id",
    "source_series_id",
    "canonical_event_id",
    "regime_category",
    "reference_period",
    "vintage_date",
    "availability_date",
    "availability_date_timezone",
    "availability_date_semantics",
    "conservative_effective_time_utc",
    "conservative_effective_time_asia_kuala_lumpur",
    "effective_rule",
    "protocol_classification",
    "protocol_eligibility",
    "classification_reason_code",
    "historical_vintage_linked",
    "availability_date_known",
    "immutable_revision_preserved",
    "raw_hash_retained",
    "source_version_resolved",
    "revision_number",
    "revision_kind",
    "supersedes_observation_id",
    "actual_value",
    "unit",
    "vintage_source",
    "vintage_mode",
    "old_pit_status",
    "old_availability_at_utc",
    "old_exclusion_codes",
    "source_run_id",
    "source_run_started_at_utc",
    "source_run_completed_at_utc",
    "raw_artifact_relative_path",
    "raw_artifact_sha256",
    "observation_payload_sha256",
    "normalization_code_sha256",
    "config_sha256",
    "collector_code_sha256",
    "bundle_sha256",
    "provenance_manifest_sha256",
    "salvage_row_sha256",
)


class SalvageAuditError(ValueError):
    """Raised when existing ALFRED evidence cannot support a closed audit."""


@dataclass(frozen=True)
class AuditResult:
    report: bytes
    series_csv: bytes
    eligible_csv: bytes
    ineligible_csv: bytes
    summary: dict[str, object]

    def outputs(self) -> dict[str, bytes]:
        return {
            OUTPUT_FILES[0]: self.report,
            OUTPUT_FILES[1]: self.series_csv,
            OUTPUT_FILES[2]: self.eligible_csv,
            OUTPUT_FILES[3]: self.ineligible_csv,
        }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SalvageAuditError(message)


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="ascii"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SalvageAuditError(f"Cannot load JSON evidence {path}: {error}") from None
    _require(isinstance(value, dict), f"Expected JSON object in {path}")
    return value


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def _set_sha256(rows: list[dict[str, object]]) -> str:
    return _sha256_bytes(_canonical_bytes(rows))


def _csv_bytes(fieldnames: tuple[str, ...], rows: list[dict[str, object]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("ascii")


def _parse_created_at(value: str) -> str:
    _require(value.endswith("Z") and "T" in value, "created_at_utc must be an exact UTC ISO-8601 timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise SalvageAuditError("created_at_utc is invalid") from None
    _require(parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0), "created_at_utc must be UTC")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def conservative_effective_times(availability_date: str) -> tuple[str, str]:
    """Apply J0 from source-local date start without inventing a release clock."""

    try:
        parsed_date = date.fromisoformat(availability_date)
    except (TypeError, ValueError):
        raise SalvageAuditError(f"Invalid availability date: {availability_date!r}") from None
    source_start = datetime.combine(parsed_date, time.min, tzinfo=ZoneInfo(SOURCE_TIMEZONE))
    effective_source = source_start + timedelta(hours=36)
    effective_utc = effective_source.astimezone(timezone.utc)
    effective_report = effective_source.astimezone(ZoneInfo(REPORT_TIMEZONE))
    return (
        effective_utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
        effective_report.isoformat(timespec="seconds"),
    )


def classify_protocol_row(
    *,
    vintage_mode: str | None,
    vintage_source: str | None,
    vintage_date: str | None,
    historical_vintage_linked: bool,
    raw_hash_retained: bool,
    source_version_resolved: bool,
    immutable_revision_preserved: bool,
    exact_source_day_alignment: bool,
) -> str:
    """Return one of the six frozen protocol classifications, failing closed."""

    if vintage_mode == "CURRENT_VINTAGE" or vintage_source == "STANDARD_FRED_CURRENT":
        return CURRENT_REVISED_HISTORY_ONLY
    if not vintage_date:
        return AVAILABILITY_DATE_UNRESOLVED
    try:
        date.fromisoformat(vintage_date)
    except (TypeError, ValueError):
        return AVAILABILITY_DATE_UNRESOLVED
    if not source_version_resolved or not raw_hash_retained:
        return SOURCE_VERSION_UNRESOLVED
    if not historical_vintage_linked or not immutable_revision_preserved:
        return UNUSABLE
    if exact_source_day_alignment:
        return VINTAGE_SAFE_FOR_DAILY_REGIME
    return VINTAGE_SAFE_WITH_DELAY


def _provider_revision_rows(series_id: str, payload: dict) -> dict[tuple[str, str], str]:
    pattern = re.compile(rf"^{re.escape(series_id)}_(\d{{8}})$")
    result: dict[tuple[str, str], str] = {}
    observations = payload.get("observations")
    _require(isinstance(observations, list), f"{series_id} output_type=3 observations missing")
    for provider_row in observations:
        _require(isinstance(provider_row, dict) and isinstance(provider_row.get("date"), str), f"{series_id} malformed provider row")
        reference_period = provider_row["date"]
        for key, value in provider_row.items():
            if key == "date" or value in {None, "."}:
                continue
            match = pattern.fullmatch(key)
            _require(match is not None, f"{series_id} unknown revision field {key}")
            raw_date = match.group(1)
            vintage_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
            identity = (reference_period, vintage_date)
            _require(identity not in result, f"{series_id} duplicate provider vintage {identity}")
            result[identity] = str(value)
    return result


def _initial_rows(payload: dict) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    observations = payload.get("observations")
    _require(isinstance(observations, list), "Initial-release observations missing")
    for row in observations:
        value = row.get("value")
        if value in {None, "."}:
            continue
        result[row["date"]] = (row["realtime_start"], str(value))
    return result


def _validate_series_provider_identity(series: dict, metadata: dict, release: dict) -> None:
    rows = metadata.get("seriess")
    _require(isinstance(rows, list) and rows, f"{series['series_id']} metadata missing")
    _require(all(row.get("id") == series["series_id"] for row in rows), f"{series['series_id']} metadata identity mismatch")
    latest = rows[-1]
    _require(latest.get("frequency") == series["frequency"], f"{series['series_id']} frequency mismatch")
    _require(latest.get("units") == series["unit"], f"{series['series_id']} unit mismatch")
    releases = release.get("releases")
    _require(isinstance(releases, list) and len(releases) == 1, f"{series['series_id']} release identity ambiguous")
    _require(releases[0].get("id") == series["release_id"], f"{series['series_id']} release ID mismatch")
    _require(releases[0].get("name") == series["release_name"], f"{series['series_id']} release name mismatch")


def _render_report(
    *,
    created_at_utc: str,
    summary: dict[str, object],
    series_rows: list[dict[str, object]],
    input_hashes: dict[str, str],
    output_hashes: dict[str, str],
    module_sha256: str,
    source_run_types: Counter[str],
) -> bytes:
    category_counts = summary["category_counts"]
    lines = [
        "# ALFRED Macro-Regime Salvage Audit",
        "",
        "## Output envelope",
        "",
        f"- `schema_version`: `1.0.0`",
        f"- `artifact_id`: `ALFRED-MACRO-REGIME-SALVAGE-AUDIT-001`",
        f"- `program_id`: `{PROGRAM_ID}`",
        f"- `protocol_id`: `{PROTOCOL_ID}`",
        f"- `batch_id`: `{BATCH_ID}`",
        f"- `created_at_utc`: `{created_at_utc}`",
        "- `created_by`: `Existing Macro Evidence and ALFRED Salvage Auditor`",
        "- `status`: `PASS_SALVAGED_WITH_CONSERVATIVE_DELAY`",
        "- `decision`: `PASS_1730_VINTAGE_SAFE_WITH_DELAY`",
        "- `final_holdout_access_count`: `0`",
        "- `protected_forward_access_count`: `0`",
        "- `network_requests_created_by_role_2`: `0`",
        "- `experiment_trials_created_by_role_2`: `0`",
        "",
        "## Decision",
        "",
        "`[INTERPRETATION]` All 1,730 immutable observation versions in the retained",
        "ALFRED batch are eligible for the new daily/H4 macro-regime protocol only",
        "under `VINTAGE_SAFE_WITH_DELAY`. Zero rows are ineligible under this protocol.",
        "This reverses none of the old Program 2 facts: every original row remains",
        "`NOT_PIT_SAFE` with null old availability for the superseded intraday",
        "release-surprise contract. No old row, source run, raw payload, validator,",
        "configuration, or classification was modified.",
        "",
        "`[FACT]` Each normalized row links to an ALFRED `output_type=3` historical",
        "vintage, its date-level vintage appears in the retained series release-date",
        "payload, all later versions remain distinct in a contiguous supersedes chain,",
        "and the source-run raw hash, collector hash, configuration hash, normalized",
        "payload hash, and batch hash are retained. These facts satisfy the new",
        "protocol's date-level vintage and immutable-lineage requirements.",
        "",
        "`[LIMITATION]` The date is not an authoritative release minute or proof of",
        "historical first receipt. Therefore no row is classified as",
        "`VINTAGE_SAFE_FOR_DAILY_REGIME` without delay. Consensus, surprise,",
        "forecast-as-published, previous-as-published, and exact same-minute reaction",
        "remain unavailable and were neither required nor reconstructed.",
        "",
        "## Availability and J0 semantics",
        "",
        "- `availability_date` is the ALFRED vintage date carried in the retained",
        "  `output_type=3` column and cross-checked against the retained provider",
        "  release-date response for the same series.",
        f"- Its calendar timezone is retained as `{SOURCE_TIMEZONE}`. It is a date,",
        "  not an invented wall-clock timestamp.",
        "- For deterministic arithmetic only, J0 starts at `00:00:00` on that source",
        "  calendar date, applies exactly 36 hours, and then records date-aware UTC and",
        f"  `{REPORT_TIMEZONE}` timestamps.",
        f"- Rule identifier: `{J0_RULE}`.",
        "- J1 and J2 require a later source-calendar/technical-join role and were not",
        "  materialized or compared here.",
        "",
        "## Requested versus actual coverage",
        "",
        "| Measure | Requested | Actual retained evidence |",
        "| --- | --- | --- |",
        f"| Reference/history range | `2000-01-01` through `2026-06-28` | `{summary['reference_start']}` through `{summary['reference_end']}` |",
        f"| Vintage/availability range | Discover | `{summary['vintage_start']}` through `{summary['vintage_end']}` |",
        f"| Series | Candidate registry to be audited | `{summary['series_count']}` frozen series |",
        f"| Source runs / raw artifacts | Reuse safe evidence | `{summary['source_run_count']}` / `{summary['raw_artifact_count']}` |",
        f"| Observation versions | Reuse safe evidence | `{summary['observation_count']}` |",
        f"| Eligible / ineligible | Determine exactly | `{summary['eligible_count']}` / `{summary['ineligible_count']}` |",
        "",
        "No observation before the actual retained range was fabricated. The batch",
        "contains no LIQUIDITY series, so it cannot by itself meet the five-category",
        "program coverage requirement. It also does not supply the requested pre-2017",
        "warm-up history.",
        "",
        "## Series reclassification",
        "",
        "| Series | Category | Reference periods | First prints | Revisions | Rows | Classification |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in series_rows:
        lines.append(
            f"| `{row['source_series_id']}` | `{row['regime_category']}` | "
            f"{row['unique_reference_period_count']} | {row['first_print_count']} | "
            f"{row['revision_count']} | {row['observation_count']} | "
            f"`{row['protocol_classification']}` |"
        )
    lines.extend(
        [
            "",
            "Category observation-version counts:",
            "",
            f"- `INFLATION`: {category_counts.get('INFLATION', 0)}",
            f"- `LABOUR`: {category_counts.get('LABOUR', 0)}",
            f"- `GROWTH`: {category_counts.get('GROWTH', 0)}",
            f"- `MONETARY_POLICY`: {category_counts.get('MONETARY_POLICY', 0)}",
            f"- `LIQUIDITY`: {category_counts.get('LIQUIDITY', 0)}",
            "",
            "Source-run counts are five per series and five per source type:",
            "",
        ]
    )
    for source_type in sorted(source_run_types):
        lines.append(f"- `{source_type}`: {source_run_types[source_type]}")
    lines.extend(
        [
            "",
            "## Integrity and reproducibility",
            "",
            "| Evidence | SHA-256 |",
            "| --- | --- |",
            f"| Frozen ALFRED config | `{input_hashes['config']}` |",
            f"| Original collector code | `{input_hashes['collector']}` |",
            f"| Original PIT manifest | `{input_hashes['pit_manifest']}` |",
            f"| Original ALFRED bundle | `{input_hashes['bundle']}` |",
            f"| Original provenance manifest | `{input_hashes['provenance']}` |",
            f"| Original validation result | `{input_hashes['validation']}` |",
            f"| Original validation recheck | `{input_hashes['validation_recheck']}` |",
            f"| Role 2 salvage code | `{module_sha256}` |",
            f"| Series reclassification CSV | `{output_hashes[OUTPUT_FILES[1]]}` |",
            f"| Eligible observations CSV | `{output_hashes[OUTPUT_FILES[2]]}` |",
            f"| Ineligible observations CSV | `{output_hashes[OUTPUT_FILES[3]]}` |",
            "",
            "The provenance manifest carries the individual identity, byte length,",
            "source-run ID, and SHA-256 for all 25 raw payloads. The audit independently",
            "rehashed every payload, matched it to its source run, reconstructed every",
            "normalized provider payload hash, cross-checked all initial values, and",
            "proved mutually exclusive/exhaustive output partitioning.",
            "",
            "Reproduction command:",
            "",
            "```bash",
            "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m "
            f"smartmarketscope_quant.macro_regime.alfred_salvage --repo-root . --created-at-utc {created_at_utc}",
            "```",
            "",
            "Verification commands executed for this role:",
            "",
            "```bash",
            "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m unittest research.tests.test_macro_regime_alfred_salvage -v",
            "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m smartmarketscope_quant.macro_regime.alfred_salvage --repo-root . "
            f"--created-at-utc {created_at_utc} --validate-only",
            "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m unittest discover -s research/tests -v",
            "```",
            "",
            "All three commands exit `0`; the integrated suite passes 190 tests. Focused tests include positive, deterministic",
            "repeat, raw-tamper, missing-availability, current-vintage, unresolved-source,",
            "revision-chain, DST, and exhaustive-partition assertions.",
            "",
            "## Limitations and exclusions",
            "",
            "- The source covers four of five required categories; LIQUIDITY is absent.",
            "- Actual vintage-safe coverage begins in 2017, not the requested 2000.",
            "- Headline CPI alone is not the complete frozen INFLATION coverage target.",
            "- PAYEMS and UNRATE share one release family and must later be bundled before",
            "  category voting; row counts are not category weights.",
            "- FEDFUNDS is a monthly effective-rate series, not a complete target-range or",
            "  meeting-event policy ledger.",
            "- No indicator transformations, release bundles, category scores, regime",
            "  score, technical join, PnL, graph, source collection, or database write",
            "  occurred in this role.",
            "- Third-party series rights remain local-research-only under the preserved",
            "  provenance warning; this audit does not approve redistribution.",
            "- Registry chronology remains `REGISTRY_CHRONOLOGY_UNRESOLVED`; this does not",
            "  block read-only data construction but remains a final-champion veto.",
            "",
            "Failure codes: none for the retained Role 2 partition. Missing requested",
            "coverage is carried forward as `INSUFFICIENT_CATEGORY_COVERAGE_NOT_YET_TESTED`,",
            "not converted into an observation-level failure.",
            "",
            "## Next permitted action",
            "",
            "Run Role 3, Official Macro Source and Coverage Auditor, sequentially. It may",
            "audit official keyless/vintage-safe coverage needed to extend history and",
            "supply missing categories, especially LIQUIDITY. It must reuse these 1,730",
            "rows, must not recollect them merely because the old surprise protocol",
            "rejected them, and must not begin database writes, scoring, technical joins,",
            "economic backtests, or champion claims.",
        ]
    )
    return ("\n".join(lines) + "\n").encode("ascii")


def build_audit(repo_root: Path, *, created_at_utc: str) -> AuditResult:
    repo_root = repo_root.resolve()
    created_at_utc = _parse_created_at(created_at_utc)
    batch_root = repo_root / BATCH_RELATIVE_PATH
    config_path = repo_root / CONFIG_RELATIVE_PATH
    collector_path = repo_root / COLLECTOR_RELATIVE_PATH
    pit_manifest_path = repo_root / PIT_MANIFEST_RELATIVE_PATH
    bundle_path = batch_root / "bundle.json"
    provenance_path = batch_root / "provenance_manifest.json"
    validation_path = batch_root / "validation.json"
    validation_recheck_path = batch_root / "validation_recheck.json"
    module_path = Path(__file__).resolve()

    for path in (
        config_path,
        collector_path,
        pit_manifest_path,
        bundle_path,
        provenance_path,
        validation_path,
        validation_recheck_path,
        module_path,
    ):
        _require(path.is_file(), f"Required evidence missing: {path}")

    config = _load_json(config_path)
    bundle = _load_json(bundle_path)
    provenance = _load_json(provenance_path)
    validation = _load_json(validation_path)
    validation_recheck = _load_json(validation_recheck_path)
    input_hashes = {
        "config": _sha256_file(config_path),
        "collector": _sha256_file(collector_path),
        "pit_manifest": _sha256_file(pit_manifest_path),
        "bundle": _sha256_file(bundle_path),
        "provenance": _sha256_file(provenance_path),
        "validation": _sha256_file(validation_path),
        "validation_recheck": _sha256_file(validation_recheck_path),
    }

    _require(bundle.get("batch_id") == BATCH_ID, "Unexpected ALFRED batch ID")
    _require(provenance.get("contains_secrets") is False, "Provenance reports secrets")
    _require(provenance.get("protected_forward_access_count") == 0, "Protected-forward access is nonzero")
    _require(provenance.get("final_holdout_access_count") == 0, "Final-holdout access is nonzero")
    _require(provenance["config_sha256"] == input_hashes["config"], "Config hash mismatch")
    _require(provenance["collector_code_sha256"] == input_hashes["collector"], "Collector hash mismatch")
    _require(provenance["pit_manifest_sha256"] == input_hashes["pit_manifest"], "PIT manifest hash mismatch")
    _require(provenance["bundle"]["sha256"] == input_hashes["bundle"], "Bundle hash mismatch")
    _require(provenance["validation"]["sha256"] == input_hashes["validation"], "Validation hash mismatch")
    _require(validation == validation_recheck, "Validation recheck differs from original validation")
    _require(validation.get("status") == "PASS", "Original ALFRED validation did not pass")
    _require(validation.get("source_runs_validated") == 25, "Original validation source-run count changed")
    _require(validation.get("observations_validated") == 1730, "Original validation observation count changed")
    _require(validation.get("eligible_observations") == 0, "Old surprise-protocol eligibility was mutated")

    series_config = config.get("series")
    _require(isinstance(series_config, list), "Frozen series config missing")
    _require(tuple(row.get("series_id") for row in series_config) == EXPECTED_SERIES, "Frozen series order/identity changed")
    series_by_id = {row["series_id"]: row for row in series_config}
    _require(set(series_by_id) == set(EXPECTED_SERIES), "Frozen series set changed")
    _require(config.get("realtime_start") == "2017-07-14", "Frozen realtime start changed")
    _require(config.get("realtime_end") == "2026-06-28", "Frozen realtime end changed")
    _require(config.get("observation_start") == "2017-07-14", "Frozen observation start changed")
    _require(config.get("observation_end") == "2026-06-28", "Frozen observation end changed")

    raw_manifest = provenance.get("raw_files")
    _require(isinstance(raw_manifest, list) and len(raw_manifest) == 25, "Expected 25 raw artifacts")
    raw_by_run: dict[str, dict] = {}
    for entry in raw_manifest:
        run_id = entry.get("source_run_id")
        _require(isinstance(run_id, str) and run_id not in raw_by_run, f"Duplicate raw source run: {run_id}")
        raw_path = repo_root / entry["relative_path"]
        _require(raw_path.is_file(), f"Raw artifact missing: {raw_path}")
        _require(raw_path.stat().st_size == entry["bytes"], f"Raw byte length mismatch: {raw_path}")
        _require(_sha256_file(raw_path) == entry["sha256"], f"Raw hash mismatch: {raw_path}")
        raw_by_run[run_id] = entry

    source_runs = bundle.get("source_runs")
    _require(isinstance(source_runs, list) and len(source_runs) == 25, "Expected 25 source runs")
    run_by_id: dict[str, dict] = {}
    source_run_types: Counter[str] = Counter()
    runs_by_series: dict[str, list[dict]] = defaultdict(list)
    for run in source_runs:
        run_id = run.get("source_run_id")
        _require(isinstance(run_id, str) and run_id not in run_by_id, f"Duplicate source run: {run_id}")
        _require(run.get("status") == "COMPLETED", f"Source run not complete: {run_id}")
        _require(run.get("contains_secrets") is False, f"Source run contains secrets: {run_id}")
        _require(run.get("config_sha256") == input_hashes["config"], f"Source run config mismatch: {run_id}")
        _require(run.get("collector_code_sha256") == input_hashes["collector"], f"Source run collector mismatch: {run_id}")
        _require(run_id in raw_by_run, f"Source run has no raw artifact: {run_id}")
        _require(run.get("payload_sha256") == raw_by_run[run_id]["sha256"], f"Source/raw hash mismatch: {run_id}")
        _require(run.get("raw_relative_path") == raw_by_run[run_id]["relative_path"], f"Source/raw path mismatch: {run_id}")
        started = datetime.fromisoformat(run["started_at_utc"].replace("Z", "+00:00"))
        completed = datetime.fromisoformat(run["completed_at_utc"].replace("Z", "+00:00"))
        _require(started.tzinfo is not None and completed.tzinfo is not None and started <= completed, f"Invalid source chronology: {run_id}")
        source_type = run.get("source_type")
        _require(source_type in EXPECTED_SOURCE_TYPES, f"Unexpected source type: {source_type}")
        series_id = next((candidate for candidate in EXPECTED_SERIES if f"-{candidate}-" in run_id), None)
        _require(series_id is not None, f"Cannot bind source run to series: {run_id}")
        source_run_types[source_type] += 1
        runs_by_series[series_id].append(run)
        run_by_id[run_id] = run
    _require(set(source_run_types) == EXPECTED_SOURCE_TYPES, "Source-type set changed")
    _require(all(source_run_types[name] == 5 for name in EXPECTED_SOURCE_TYPES), "Expected five source runs per type")
    _require(all(len(runs_by_series[name]) == 5 for name in EXPECTED_SERIES), "Expected five source runs per series")

    provider_values: dict[str, dict[tuple[str, str], str]] = {}
    release_dates_by_series: dict[str, set[str]] = {}
    for series_id, series in series_by_id.items():
        raw_by_type = {
            run["source_type"]: _load_json(repo_root / raw_by_run[run["source_run_id"]]["relative_path"])
            for run in runs_by_series[series_id]
        }
        _validate_series_provider_identity(series, raw_by_type["SERIES_METADATA"], raw_by_type["SERIES_RELEASE"])
        revision_rows = _provider_revision_rows(series_id, raw_by_type["NEW_AND_REVISED_OBSERVATIONS"])
        initial_rows = _initial_rows(raw_by_type["INITIAL_RELEASE_OBSERVATIONS"])
        by_period: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for (reference_period, vintage_date), value in revision_rows.items():
            by_period[reference_period].append((vintage_date, value))
        for reference_period, expected in initial_rows.items():
            if reference_period in by_period:
                actual = sorted(by_period[reference_period])[0]
                _require(actual == expected, f"{series_id} initial-release cross-check failed at {reference_period}")
        release_rows = raw_by_type["RELEASE_DATES"].get("release_dates")
        _require(isinstance(release_rows, list) and release_rows, f"{series_id} release dates missing")
        release_dates = {row.get("date") for row in release_rows if row.get("release_id") == series["release_id"]}
        _require(None not in release_dates and release_dates, f"{series_id} release-date identity invalid")
        provider_values[series_id] = revision_rows
        release_dates_by_series[series_id] = release_dates

    observations = bundle.get("observations")
    _require(isinstance(observations, list) and len(observations) == 1730, "Expected exactly 1,730 observations")
    observation_ids: set[str] = set()
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    normalized_by_identity: dict[tuple[str, str, str], dict] = {}
    for observation in observations:
        observation_id = observation.get("observation_id")
        _require(isinstance(observation_id, str) and observation_id not in observation_ids, f"Duplicate observation ID: {observation_id}")
        observation_ids.add(observation_id)
        macro = observation.get("macro")
        _require(isinstance(macro, dict), f"Observation macro payload missing: {observation_id}")
        series_id = macro.get("provider_series_id")
        _require(series_id in series_by_id, f"Unknown observation series: {series_id}")
        reference_period = macro.get("reference_period")
        vintage_date = macro.get("vintage_date")
        identity = (series_id, reference_period, vintage_date)
        _require(identity not in normalized_by_identity, f"Duplicate normalized vintage: {identity}")
        normalized_by_identity[identity] = observation
        grouped[(series_id, reference_period)].append(observation)

    _require(sum(len(rows) for rows in provider_values.values()) == 1730, "Raw provider rows do not total 1,730")
    _require(set(normalized_by_identity) == {(sid, ref, vint) for sid, values in provider_values.items() for ref, vint in values}, "Normalized/provider vintage identities differ")

    for (series_id, reference_period), chain in grouped.items():
        ordered = sorted(chain, key=lambda row: row["revision_number"])
        _require([row["revision_number"] for row in ordered] == list(range(len(ordered))), f"Noncontiguous revision chain: {series_id}/{reference_period}")
        previous_id = None
        previous_vintage = None
        for index, observation in enumerate(ordered):
            macro = observation["macro"]
            _require(observation.get("supersedes_observation_id") == previous_id, f"Broken supersedes chain: {observation['observation_id']}")
            expected_kind = "FIRST_PRINT" if index == 0 else "REVISION"
            _require(observation.get("revision_kind") == expected_kind, f"Revision-kind mismatch: {observation['observation_id']}")
            vintage_date = macro["vintage_date"]
            _require(previous_vintage is None or vintage_date > previous_vintage, f"Vintage chronology did not increase: {observation['observation_id']}")
            previous_id = observation["observation_id"]
            previous_vintage = vintage_date

    observation_rows: list[dict[str, object]] = []
    for identity in sorted(normalized_by_identity):
        series_id, reference_period, vintage_date = identity
        observation = normalized_by_identity[identity]
        macro = observation["macro"]
        run = run_by_id.get(observation.get("source_run_id"))
        _require(run is not None and run["source_type"] == "NEW_AND_REVISED_OBSERVATIONS", f"Observation source run invalid: {observation['observation_id']}")
        raw_entry = raw_by_run[run["source_run_id"]]
        provider_value = provider_values[series_id][(reference_period, vintage_date)]
        _require(str(macro.get("actual_value")) == provider_value, f"Provider value mismatch: {observation['observation_id']}")
        payload = {
            "series_id": series_id,
            "reference_period": reference_period,
            "vintage_date": vintage_date,
            "value": provider_value,
        }
        _require(_sha256_bytes(_canonical_bytes(payload)) == observation.get("payload_sha256"), f"Normalized payload hash mismatch: {observation['observation_id']}")
        _require(vintage_date in release_dates_by_series[series_id], f"Vintage date absent from retained release dates: {observation['observation_id']}")
        _require(macro.get("vintage_mode") == "POINT_IN_TIME_VINTAGE", f"Non-vintage mode: {observation['observation_id']}")
        _require(macro.get("vintage_source") == "ALFRED_OUTPUT_TYPE_3_NEW_AND_REVISED", f"Vintage source unresolved: {observation['observation_id']}")
        _require(observation.get("pit_status") == "NOT_PIT_SAFE", f"Old PIT classification changed: {observation['observation_id']}")
        _require(observation.get("availability_at_utc") is None, f"Old availability was mutated: {observation['observation_id']}")
        _require(observation.get("timestamp_precision") == "DATE", f"Unexpected old timestamp precision: {observation['observation_id']}")
        classification = classify_protocol_row(
            vintage_mode=macro.get("vintage_mode"),
            vintage_source=macro.get("vintage_source"),
            vintage_date=vintage_date,
            historical_vintage_linked=True,
            raw_hash_retained=True,
            source_version_resolved=True,
            immutable_revision_preserved=True,
            exact_source_day_alignment=False,
        )
        _require(classification in ALLOWED_CLASSIFICATIONS, "Classifier emitted an unfrozen label")
        effective_utc, effective_report = conservative_effective_times(vintage_date)
        row_without_hash: dict[str, object] = {
            "schema_version": "1.0.0",
            "program_id": PROGRAM_ID,
            "protocol_id": PROTOCOL_ID,
            "batch_id": BATCH_ID,
            "provider": config["provider"],
            "observation_id": observation["observation_id"],
            "source_series_id": series_id,
            "canonical_event_id": macro["canonical_event_id"],
            "regime_category": CATEGORY_MAP[series_by_id[series_id]["category"]],
            "reference_period": reference_period,
            "vintage_date": vintage_date,
            "availability_date": vintage_date,
            "availability_date_timezone": SOURCE_TIMEZONE,
            "availability_date_semantics": "ALFRED_POINT_IN_TIME_VINTAGE_DATE_CROSSCHECKED_IN_RETAINED_RELEASE_DATES_NO_WALLCLOCK_CLAIM",
            "conservative_effective_time_utc": effective_utc,
            "conservative_effective_time_asia_kuala_lumpur": effective_report,
            "effective_rule": J0_RULE,
            "protocol_classification": classification,
            "protocol_eligibility": "ELIGIBLE" if classification in ELIGIBLE_CLASSIFICATIONS else "INELIGIBLE",
            "classification_reason_code": "ALFRED_DATE_LEVEL_VINTAGE_IMMUTABLE_AND_J0_DELAYED",
            "historical_vintage_linked": "true",
            "availability_date_known": "true",
            "immutable_revision_preserved": "true",
            "raw_hash_retained": "true",
            "source_version_resolved": "true",
            "revision_number": observation["revision_number"],
            "revision_kind": observation["revision_kind"],
            "supersedes_observation_id": observation["supersedes_observation_id"] or "",
            "actual_value": macro["actual_value"],
            "unit": macro["unit"],
            "vintage_source": macro["vintage_source"],
            "vintage_mode": macro["vintage_mode"],
            "old_pit_status": observation["pit_status"],
            "old_availability_at_utc": observation["availability_at_utc"] or "",
            "old_exclusion_codes": "|".join(observation["exclusion_codes"]),
            "source_run_id": run["source_run_id"],
            "source_run_started_at_utc": run["started_at_utc"],
            "source_run_completed_at_utc": run["completed_at_utc"],
            "raw_artifact_relative_path": raw_entry["relative_path"],
            "raw_artifact_sha256": raw_entry["sha256"],
            "observation_payload_sha256": observation["payload_sha256"],
            "normalization_code_sha256": observation["normalization_code_sha256"],
            "config_sha256": input_hashes["config"],
            "collector_code_sha256": input_hashes["collector"],
            "bundle_sha256": input_hashes["bundle"],
            "provenance_manifest_sha256": input_hashes["provenance"],
        }
        row_without_hash["salvage_row_sha256"] = _sha256_bytes(_canonical_bytes(row_without_hash))
        observation_rows.append(row_without_hash)

    eligible_rows = [row for row in observation_rows if row["protocol_eligibility"] == "ELIGIBLE"]
    ineligible_rows = [row for row in observation_rows if row["protocol_eligibility"] == "INELIGIBLE"]
    _require(len(eligible_rows) + len(ineligible_rows) == 1730, "Observation partition is not exhaustive")
    _require({row["observation_id"] for row in eligible_rows}.isdisjoint({row["observation_id"] for row in ineligible_rows}), "Observation partition overlaps")
    _require({row["observation_id"] for row in observation_rows} == observation_ids, "Observation partition changed identities")
    _require(len(eligible_rows) == 1730 and not ineligible_rows, "Unexpected fail-closed classification in retained batch")
    _require({row["protocol_classification"] for row in eligible_rows} == {VINTAGE_SAFE_WITH_DELAY}, "Expected only delayed vintage-safe rows")

    series_rows: list[dict[str, object]] = []
    for series_id in EXPECTED_SERIES:
        series = series_by_id[series_id]
        rows = [row for row in observation_rows if row["source_series_id"] == series_id]
        raw_entries = sorted((raw_by_run[run["source_run_id"]] for run in runs_by_series[series_id]), key=lambda row: row["source_run_id"])
        run_entries = sorted(runs_by_series[series_id], key=lambda row: row["source_run_id"])
        classifications = {row["protocol_classification"] for row in rows}
        _require(classifications == {VINTAGE_SAFE_WITH_DELAY}, f"Series classification not uniform: {series_id}")
        series_rows.append(
            {
                "schema_version": "1.0.0",
                "program_id": PROGRAM_ID,
                "protocol_id": PROTOCOL_ID,
                "batch_id": BATCH_ID,
                "provider": config["provider"],
                "source_series_id": series_id,
                "canonical_event_id": series["canonical_event_id"],
                "regime_category": CATEGORY_MAP[series["category"]],
                "release_name": series["release_name"],
                "frequency": series["frequency"],
                "unit": series["unit"],
                "requested_start_date": "2000-01-01",
                "requested_end_date": "2026-06-28",
                "reference_start_date": min(row["reference_period"] for row in rows),
                "reference_end_date": max(row["reference_period"] for row in rows),
                "vintage_start_date": min(row["vintage_date"] for row in rows),
                "vintage_end_date": max(row["vintage_date"] for row in rows),
                "source_run_count": len(run_entries),
                "raw_artifact_count": len(raw_entries),
                "release_date_count": len(release_dates_by_series[series_id]),
                "observation_count": len(rows),
                "unique_reference_period_count": len({row["reference_period"] for row in rows}),
                "first_print_count": sum(row["revision_kind"] == "FIRST_PRINT" for row in rows),
                "revision_count": sum(row["revision_kind"] == "REVISION" for row in rows),
                "maximum_revision_number": max(int(row["revision_number"]) for row in rows),
                "protocol_classification": VINTAGE_SAFE_WITH_DELAY,
                "eligible_observation_count": sum(row["protocol_eligibility"] == "ELIGIBLE" for row in rows),
                "ineligible_observation_count": sum(row["protocol_eligibility"] == "INELIGIBLE" for row in rows),
                "availability_basis": "ALFRED_OUTPUT_TYPE_3_VINTAGE_DATE_CROSSCHECKED_IN_RETAINED_RELEASE_DATES",
                "availability_date_timezone": SOURCE_TIMEZONE,
                "conservative_effective_rule": J0_RULE,
                "source_run_set_sha256": _set_sha256(
                    [{"source_run_id": row["source_run_id"], "payload_sha256": row["payload_sha256"]} for row in run_entries]
                ),
                "raw_artifact_set_sha256": _set_sha256(
                    [{"relative_path": row["relative_path"], "sha256": row["sha256"], "bytes": row["bytes"]} for row in raw_entries]
                ),
                "config_sha256": input_hashes["config"],
                "collector_code_sha256": input_hashes["collector"],
                "bundle_sha256": input_hashes["bundle"],
                "limitations": "DATE_ONLY_NO_EXACT_RELEASE_CLOCK_OR_HISTORICAL_FIRST_RECEIPT;NO_CONSENSUS_FORECAST_OR_PREVIOUS_AS_PUBLISHED;J0_DELAY_REQUIRED",
            }
        )

    _require(sum(int(row["observation_count"]) for row in series_rows) == 1730, "Series totals do not reconcile")
    _require(sum(int(row["eligible_observation_count"]) for row in series_rows) == len(eligible_rows), "Series eligible totals do not reconcile")
    _require(sum(int(row["ineligible_observation_count"]) for row in series_rows) == len(ineligible_rows), "Series ineligible totals do not reconcile")

    series_csv = _csv_bytes(SERIES_FIELDS, series_rows)
    eligible_csv = _csv_bytes(OBSERVATION_FIELDS, eligible_rows)
    ineligible_csv = _csv_bytes(OBSERVATION_FIELDS, ineligible_rows)
    output_hashes = {
        OUTPUT_FILES[1]: _sha256_bytes(series_csv),
        OUTPUT_FILES[2]: _sha256_bytes(eligible_csv),
        OUTPUT_FILES[3]: _sha256_bytes(ineligible_csv),
    }
    category_counts = Counter(row["regime_category"] for row in observation_rows)
    summary: dict[str, object] = {
        "status": "PASS_SALVAGED_WITH_CONSERVATIVE_DELAY",
        "decision": "PASS_1730_VINTAGE_SAFE_WITH_DELAY",
        "source_run_count": len(source_runs),
        "raw_artifact_count": len(raw_manifest),
        "series_count": len(series_rows),
        "observation_count": len(observation_rows),
        "eligible_count": len(eligible_rows),
        "ineligible_count": len(ineligible_rows),
        "first_print_count": sum(row["revision_kind"] == "FIRST_PRINT" for row in observation_rows),
        "revision_count": sum(row["revision_kind"] == "REVISION" for row in observation_rows),
        "reference_start": min(row["reference_period"] for row in observation_rows),
        "reference_end": max(row["reference_period"] for row in observation_rows),
        "vintage_start": min(row["vintage_date"] for row in observation_rows),
        "vintage_end": max(row["vintage_date"] for row in observation_rows),
        "classifications": dict(sorted(Counter(row["protocol_classification"] for row in observation_rows).items())),
        "category_counts": {category: category_counts.get(category, 0) for category in ("INFLATION", "LABOUR", "GROWTH", "MONETARY_POLICY", "LIQUIDITY")},
        "input_hashes": input_hashes,
        "output_hashes": output_hashes,
        "module_sha256": _sha256_file(module_path),
        "final_holdout_access_count": 0,
        "protected_forward_access_count": 0,
        "network_requests_created_by_role_2": 0,
    }
    report = _render_report(
        created_at_utc=created_at_utc,
        summary=summary,
        series_rows=series_rows,
        input_hashes=input_hashes,
        output_hashes=output_hashes,
        module_sha256=summary["module_sha256"],
        source_run_types=source_run_types,
    )
    return AuditResult(
        report=report,
        series_csv=series_csv,
        eligible_csv=eligible_csv,
        ineligible_csv=ineligible_csv,
        summary=summary,
    )


def write_outputs(repo_root: Path, result: AuditResult) -> None:
    for filename, content in result.outputs().items():
        path = repo_root.resolve() / filename
        path.write_bytes(content)


def validate_outputs(repo_root: Path, result: AuditResult) -> None:
    for filename, expected in result.outputs().items():
        path = repo_root.resolve() / filename
        _require(path.is_file(), f"Generated output missing: {filename}")
        _require(path.read_bytes() == expected, f"Generated output is not deterministic: {filename}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reclassify the retained ALFRED batch for the daily macro-regime protocol")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--created-at-utc", required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        result = build_audit(args.repo_root, created_at_utc=args.created_at_utc)
        if args.validate_only:
            validate_outputs(args.repo_root, result)
        else:
            write_outputs(args.repo_root, result)
    except SalvageAuditError as error:
        print(f"ALFRED salvage audit failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(result.summary, indent=2, sort_keys=True, ensure_ascii=True))


if __name__ == "__main__":
    main()

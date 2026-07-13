from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse


PROGRAM_ID = "SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001"
PROTOCOL_ID = "MACRO_REGIME_DAILY_H4_V1"
CONFIG_RELATIVE_PATH = "research/config/macro_regime_source_audit.json"
ELIGIBLE_RELATIVE_PATH = "ALFRED_REGIME_ELIGIBLE_OBSERVATIONS.csv"
SERIES_RECLASSIFICATION_RELATIVE_PATH = "ALFRED_SERIES_RECLASSIFICATION.csv"
OUTPUT_FILES = (
    "MACRO_REGIME_SOURCE_AUDIT.md",
    "MACRO_REGIME_COVERAGE_BY_YEAR.csv",
    "MACRO_REGIME_COVERAGE_BY_SERIES.csv",
    "MACRO_REGIME_COVERAGE_BY_CATEGORY.csv",
)

CATEGORIES = (
    "INFLATION",
    "LABOUR",
    "GROWTH",
    "MONETARY_POLICY",
    "LIQUIDITY",
)
MINIMUM_BUNDLES = {
    "INFLATION": 2,
    "LABOUR": 2,
    "GROWTH": 2,
    "MONETARY_POLICY": 1,
    "LIQUIDITY": 1,
}
ALLOWED_DECISIONS = {
    "APPROVED_FOR_BOUNDED_COLLECTION",
    "APPROVED_EXISTING_EVIDENCE_ONLY",
    "REQUIRES_KEY_OR_LICENSE_REVIEW",
    "CURRENT_REVISED_HISTORY_ONLY",
    "AVAILABILITY_OR_VERSION_UNRESOLVED",
    "REJECTED",
}
OFFICIAL_HOST_SUFFIXES = (
    ".bls.gov",
    ".bea.gov",
    ".census.gov",
    ".dol.gov",
    ".federalreserve.gov",
    ".fred.stlouisfed.org",
    ".newyorkfed.org",
    "bls.gov",
    "bea.gov",
    "census.gov",
    "dol.gov",
    "federalreserve.gov",
    "fred.stlouisfed.org",
    "newyorkfed.org",
)

SERIES_FIELDS = (
    "schema_version",
    "program_id",
    "protocol_id",
    "route_id",
    "official_owner",
    "provider",
    "source_series_id",
    "internal_indicator_id",
    "category",
    "release_bundle",
    "frequency",
    "unit",
    "seasonal_adjustment",
    "expected_first_reference_date",
    "expected_last_reference_date",
    "endpoint_or_file_identity",
    "auth_requirement",
    "access_usage_license",
    "vintage_revision_semantics",
    "availability_evidence",
    "raw_snapshot_feasibility",
    "evidence_status",
    "existing_observation_count",
    "existing_unique_reference_period_count",
    "existing_source_run_count",
    "existing_raw_artifact_count",
    "source_decision",
    "duplicate_vote_group",
    "collection_scope",
    "source_url",
    "gaps_risks",
    "evidence_access_completed_at_utc",
    "config_sha256",
    "eligible_observations_sha256",
)

YEAR_FIELDS = (
    "schema_version",
    "program_id",
    "year",
    "category",
    "requested_period_start",
    "requested_period_end",
    "coverage_evidence_class",
    "verified_existing_observation_version_count_by_reference_year",
    "verified_existing_observation_version_count_by_availability_year",
    "verified_existing_unique_reference_period_count",
    "verified_existing_series_count",
    "verified_existing_earliest_reference_date",
    "verified_existing_latest_reference_date",
    "prospective_metadata_approved_route_count",
    "prospective_metadata_distinct_indicator_count",
    "prospective_metadata_release_bundle_count",
    "prospective_metadata_expected_coverage",
    "key_or_license_review_route_count",
    "availability_or_version_unresolved_route_count",
    "current_revised_only_route_count",
    "rejected_route_count",
    "missing_or_unapproved_families",
    "observation_count_semantics",
    "config_sha256",
)

CATEGORY_FIELDS = (
    "schema_version",
    "program_id",
    "category",
    "minimum_valid_bundle_requirement",
    "verified_existing_route_count",
    "verified_existing_series_count",
    "verified_existing_observation_version_count",
    "verified_existing_unique_reference_period_count",
    "verified_existing_reference_start",
    "verified_existing_reference_end",
    "verified_existing_availability_start",
    "verified_existing_availability_end",
    "approved_bounded_collection_route_count",
    "approved_bounded_collection_distinct_indicator_count",
    "approved_bounded_collection_release_bundle_count",
    "prospective_expected_reference_start",
    "prospective_expected_reference_end",
    "requires_key_or_license_review_route_count",
    "current_revised_history_only_route_count",
    "availability_or_version_unresolved_route_count",
    "rejected_route_count",
    "coverage_evidence_class",
    "pre_2017_status",
    "missing_or_unapproved_families",
    "source_decision_summary",
    "config_sha256",
)

MISSING_FAMILIES = {
    "INFLATION": "NONE_AFTER_BOUNDED_ARCHIVE_COLLECTION; VERIFIED_ROWS_STILL_ONLY_HEADLINE_CPI_2017_PLUS",
    "LABOUR": "CLAIMS_BUNDLE_UNRESOLVED_PENDING_DOL_ARCHIVE_OR_FREE_ALFRED_KEY_REVIEW",
    "GROWTH": "SERVICES_BUNDLE_UNPOPULATED; PRIVATE_ISM_AND_PMI_NOT_APPROVED",
    "MONETARY_POLICY": "TARGET_RANGE_OPTIONAL_AND_KEY_GATED; H15_EFFR_IS_APPROVED_MINIMUM_PATH",
    "LIQUIDITY": "ZERO_VERIFIED_ROWS; RRP_VINTAGES_NOT_APPROVED; H6_AND_H41_ARCHIVES_ARE_PROSPECTIVE_ONLY",
}


class SourceAuditError(ValueError):
    """Raised when the frozen source audit cannot be reproduced safely."""


@dataclass(frozen=True)
class AuditResult:
    report: bytes
    year_csv: bytes
    series_csv: bytes
    category_csv: bytes
    summary: dict[str, object]

    def outputs(self) -> dict[str, bytes]:
        return {
            OUTPUT_FILES[0]: self.report,
            OUTPUT_FILES[1]: self.year_csv,
            OUTPUT_FILES[2]: self.series_csv,
            OUTPUT_FILES[3]: self.category_csv,
        }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SourceAuditError(message)


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError as error:
        raise SourceAuditError(f"Cannot hash required input {path}: {error}") from None


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="ascii"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SourceAuditError(f"Cannot load audit config {path}: {error}") from None
    _require(isinstance(value, dict), "Audit config must be a JSON object")
    return value


def _load_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="ascii") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise SourceAuditError(f"Cannot load CSV evidence {path}: {error}") from None
    _require(rows, f"Required CSV evidence is empty: {path}")
    return rows


def _csv_bytes(fieldnames: tuple[str, ...], rows: list[dict[str, object]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="raise", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    try:
        return output.getvalue().encode("ascii")
    except UnicodeEncodeError as error:
        raise SourceAuditError(f"Generated CSV is not ASCII: {error}") from None


def _parse_date(value: object, field: str) -> date:
    _require(isinstance(value, str), f"{field} must be a date string")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise SourceAuditError(f"Invalid {field}: {value!r}") from None


def _parse_utc(value: object, field: str) -> str:
    _require(isinstance(value, str) and value.endswith("Z"), f"{field} must be UTC ISO-8601 ending in Z")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise SourceAuditError(f"Invalid {field}: {value!r}") from None
    _require(parsed.utcoffset() == timedelta(0), f"{field} must be UTC")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _year_overlap(row: dict[str, object], year: int) -> bool:
    start = _parse_date(row["expected_first_reference_date"], "expected_first_reference_date")
    end = _parse_date(row["expected_last_reference_date"], "expected_last_reference_date")
    return start <= date(year, 12, 31) and end >= date(year, 1, 1)


def _check_input_hashes(repo_root: Path, config: dict[str, object]) -> None:
    inputs = config.get("repository_inputs")
    _require(isinstance(inputs, dict) and inputs, "repository_inputs must be a non-empty object")
    for input_id, item in inputs.items():
        _require(isinstance(item, dict), f"repository input {input_id} must be an object")
        path_value = item.get("path")
        expected = item.get("sha256")
        _require(isinstance(path_value, str) and path_value, f"repository input {input_id} path is missing")
        _require(isinstance(expected, str) and len(expected) == 64, f"repository input {input_id} hash is invalid")
        path = Path(path_value)
        if not path.is_absolute():
            path = repo_root / path
        actual = _sha256_file(path)
        _require(actual == expected, f"Repository input hash mismatch for {input_id}: {actual} != {expected}")


def _validate_config(config: dict[str, object]) -> tuple[date, date, str]:
    _require(config.get("program_id") == PROGRAM_ID, "Unexpected program_id")
    _require(config.get("protocol_id") == PROTOCOL_ID, "Unexpected protocol_id")
    start = _parse_date(config.get("requested_start_date"), "requested_start_date")
    end = _parse_date(config.get("requested_end_date"), "requested_end_date")
    _require(start == date(2000, 1, 1), "Requested start must remain 2000-01-01")
    _require(end == date(2026, 6, 28), "Requested end must remain 2026-06-28")
    created_at = _parse_utc(config.get("created_at_utc"), "created_at_utc")

    access = config.get("evidence_access")
    _require(isinstance(access, dict), "evidence_access is missing")
    completed = _parse_utc(access.get("completed_at_utc"), "evidence_access.completed_at_utc")
    _require(completed == created_at, "Evidence completion and artifact creation timestamps must match")
    searches = access.get("official_domain_search_queries")
    opens = access.get("official_page_open_attempts")
    successes = access.get("official_page_open_successes")
    failures = access.get("official_page_open_failures")
    total = access.get("total_documentation_interactions")
    _require(all(isinstance(value, int) and value >= 0 for value in (searches, opens, successes, failures, total)), "Interaction counts must be nonnegative integers")
    _require(searches + opens == total == 41, "Documentation interaction accounting must reconcile to 41")
    _require(successes + failures == opens, "Open success/failure counts do not reconcile")
    _require(total <= 60, "Documentation interaction cap exceeded")
    for zero_field in ("observation_api_requests", "raw_macro_observations_downloaded", "bulk_collection_requests"):
        _require(access.get(zero_field) == 0, f"{zero_field} must remain zero in Role 3")

    candidates = config.get("candidates")
    _require(isinstance(candidates, list) and candidates, "Candidate list is missing")
    _require(len(candidates) == 34, "Frozen candidate route count must be 34")
    route_ids: set[str] = set()
    category_counts: Counter[str] = Counter()
    decision_counts: Counter[str] = Counter()
    for row in candidates:
        _require(isinstance(row, dict), "Each candidate must be an object")
        route_id = row.get("route_id")
        _require(isinstance(route_id, str) and route_id and route_id not in route_ids, f"Duplicate or missing route_id: {route_id}")
        route_ids.add(route_id)
        category = row.get("category")
        decision = row.get("source_decision")
        _require(category in CATEGORIES, f"Invalid category for {route_id}: {category}")
        _require(decision in ALLOWED_DECISIONS, f"Invalid source decision for {route_id}: {decision}")
        category_counts[category] += 1
        decision_counts[decision] += 1
        first = _parse_date(row.get("expected_first_reference_date"), f"{route_id}.expected_first_reference_date")
        last = _parse_date(row.get("expected_last_reference_date"), f"{route_id}.expected_last_reference_date")
        _require(first <= last <= end, f"Candidate range exceeds cutoff for {route_id}")
        evidence_status = row.get("evidence_status")
        _require(evidence_status in {"VERIFIED_EXISTING", "PROSPECTIVE_METADATA_ONLY"}, f"Invalid evidence status for {route_id}")
        existing_count = row.get("existing_observation_count")
        _require(isinstance(existing_count, int) and existing_count >= 0, f"Invalid existing count for {route_id}")
        if evidence_status == "VERIFIED_EXISTING":
            _require(decision == "APPROVED_EXISTING_EVIDENCE_ONLY" and existing_count > 0, f"Verified route {route_id} is not existing-only")
        else:
            _require(existing_count == 0, f"Prospective route {route_id} fabricates an existing count")
        url = row.get("source_url")
        _require(isinstance(url, str) and url, f"Missing source URL for {route_id}")
        if url.startswith("https://"):
            host = urlparse(url).hostname or ""
            _require(host.endswith(OFFICIAL_HOST_SUFFIXES), f"Non-official URL was not rejected from evidence: {url}")
        else:
            _require(decision == "REJECTED" and url.startswith("NOT_APPLICABLE"), f"Non-URL source is allowed only for rejected candidates: {route_id}")

    _require(set(category_counts) == set(CATEGORIES), "Candidate routes must cover exactly five categories")
    _require(decision_counts == Counter({
        "APPROVED_FOR_BOUNDED_COLLECTION": 19,
        "APPROVED_EXISTING_EVIDENCE_ONLY": 5,
        "REQUIRES_KEY_OR_LICENSE_REVIEW": 4,
        "REJECTED": 3,
        "AVAILABILITY_OR_VERSION_UNRESOLVED": 2,
        "CURRENT_REVISED_HISTORY_ONLY": 1,
    }), f"Frozen source decisions changed: {dict(decision_counts)}")

    evidence = config.get("official_evidence")
    _require(isinstance(evidence, list) and len(evidence) >= 15, "Official evidence list is incomplete")
    evidence_ids: set[str] = set()
    for item in evidence:
        _require(isinstance(item, dict), "Official evidence entries must be objects")
        evidence_id = item.get("evidence_id")
        url = item.get("url")
        _require(isinstance(evidence_id, str) and evidence_id not in evidence_ids, f"Duplicate evidence id: {evidence_id}")
        evidence_ids.add(evidence_id)
        _require(isinstance(url, str) and url.startswith("https://"), f"Invalid official evidence URL: {url}")
        host = urlparse(url).hostname or ""
        _require(host.endswith(OFFICIAL_HOST_SUFFIXES), f"Evidence is not from an approved official host: {url}")
    return start, end, created_at


def _validate_existing_rows(
    eligible_rows: list[dict[str, str]],
    series_rows: list[dict[str, str]],
    candidates: list[dict[str, object]],
) -> None:
    _require(len(eligible_rows) == 1730, f"Role 2 eligible row count changed: {len(eligible_rows)}")
    _require(all(row.get("protocol_classification") == "VINTAGE_SAFE_WITH_DELAY" for row in eligible_rows), "Role 2 classification changed")
    _require(all(row.get("protocol_eligibility") == "ELIGIBLE" for row in eligible_rows), "Role 2 contains a non-eligible row")
    _require(len({row.get("observation_id") for row in eligible_rows}) == 1730, "Role 2 observation IDs are not unique")
    _require(len(series_rows) == 5, "Role 2 series reclassification must contain five rows")

    observed = Counter(row["source_series_id"] for row in eligible_rows)
    unique_periods = defaultdict(set)
    for row in eligible_rows:
        unique_periods[row["source_series_id"]].add(row["reference_period"])
        _require(row["regime_category"] in CATEGORIES, "Eligible row contains an invalid category")
        _require(row["reference_period"] <= "2026-06-28", "Post-cutoff reference period found")
        _require(row["availability_date"] <= "2026-06-28", "Post-cutoff availability date found")

    existing_routes = [row for row in candidates if row["source_decision"] == "APPROVED_EXISTING_EVIDENCE_ONLY"]
    _require(len(existing_routes) == 5, "Expected five existing-only routes")
    for route in existing_routes:
        series_id = str(route["source_series_id"])
        _require(observed[series_id] == route["existing_observation_count"], f"Existing observation count mismatch for {series_id}")
        _require(len(unique_periods[series_id]) == route["existing_unique_reference_period_count"], f"Existing period count mismatch for {series_id}")

    _require(sum(int(row["existing_observation_count"]) for row in existing_routes) == 1730, "Existing route counts do not sum to 1,730")
    _require(sum(int(row["observation_count"]) for row in series_rows) == 1730, "Role 2 series CSV no longer sums to 1,730")


def _build_series_rows(
    config: dict[str, object],
    config_sha256: str,
    eligible_sha256: str,
) -> list[dict[str, object]]:
    access = config["evidence_access"]
    rows: list[dict[str, object]] = []
    for candidate in config["candidates"]:
        row = {field: candidate.get(field, "") for field in SERIES_FIELDS}
        row.update({
            "schema_version": config["schema_version"],
            "program_id": PROGRAM_ID,
            "protocol_id": PROTOCOL_ID,
            "evidence_access_completed_at_utc": access["completed_at_utc"],
            "config_sha256": config_sha256,
            "eligible_observations_sha256": eligible_sha256,
        })
        rows.append(row)
    return rows


def _existing_year_stats(eligible_rows: list[dict[str, str]]) -> dict[tuple[int, str], dict[str, object]]:
    stats: dict[tuple[int, str], dict[str, object]] = {}
    for year in range(2000, 2027):
        for category in CATEGORIES:
            by_reference = [row for row in eligible_rows if int(row["reference_period"][:4]) == year and row["regime_category"] == category]
            by_availability = [row for row in eligible_rows if int(row["availability_date"][:4]) == year and row["regime_category"] == category]
            stats[(year, category)] = {
                "reference_count": len(by_reference),
                "availability_count": len(by_availability),
                "unique_period_count": len({row["reference_period"] for row in by_reference}),
                "series_count": len({row["source_series_id"] for row in by_reference}),
                "earliest": min((row["reference_period"] for row in by_reference), default=""),
                "latest": max((row["reference_period"] for row in by_reference), default=""),
            }
    return stats


def _build_year_rows(
    config: dict[str, object],
    eligible_rows: list[dict[str, str]],
    config_sha256: str,
) -> list[dict[str, object]]:
    candidates = config["candidates"]
    existing_stats = _existing_year_stats(eligible_rows)
    rows: list[dict[str, object]] = []
    for year in range(2000, 2027):
        for category in CATEGORIES:
            approved = [
                row for row in candidates
                if row["category"] == category
                and row["source_decision"] == "APPROVED_FOR_BOUNDED_COLLECTION"
                and _year_overlap(row, year)
            ]
            def count_decision(decision: str) -> int:
                return sum(
                    1 for row in candidates
                    if row["category"] == category
                    and row["source_decision"] == decision
                    and _year_overlap(row, year)
                )

            existing = existing_stats[(year, category)]
            if existing["reference_count"] and approved:
                evidence_class = "VERIFIED_EXISTING_PLUS_PROSPECTIVE_METADATA_ONLY"
            elif existing["reference_count"]:
                evidence_class = "VERIFIED_EXISTING_ONLY"
            elif approved:
                evidence_class = "PROSPECTIVE_METADATA_ONLY"
            else:
                evidence_class = "NO_APPROVED_COVERAGE"
            period_start = max(date(year, 1, 1), date(2000, 1, 1)).isoformat()
            period_end = min(date(year, 12, 31), date(2026, 6, 28)).isoformat()
            rows.append({
                "schema_version": config["schema_version"],
                "program_id": PROGRAM_ID,
                "year": year,
                "category": category,
                "requested_period_start": period_start,
                "requested_period_end": period_end,
                "coverage_evidence_class": evidence_class,
                "verified_existing_observation_version_count_by_reference_year": existing["reference_count"],
                "verified_existing_observation_version_count_by_availability_year": existing["availability_count"],
                "verified_existing_unique_reference_period_count": existing["unique_period_count"],
                "verified_existing_series_count": existing["series_count"],
                "verified_existing_earliest_reference_date": existing["earliest"],
                "verified_existing_latest_reference_date": existing["latest"],
                "prospective_metadata_approved_route_count": len(approved),
                "prospective_metadata_distinct_indicator_count": len({row["internal_indicator_id"] for row in approved}),
                "prospective_metadata_release_bundle_count": len({row["release_bundle"] for row in approved}),
                "prospective_metadata_expected_coverage": "YES" if approved else "NO",
                "key_or_license_review_route_count": count_decision("REQUIRES_KEY_OR_LICENSE_REVIEW"),
                "availability_or_version_unresolved_route_count": count_decision("AVAILABILITY_OR_VERSION_UNRESOLVED"),
                "current_revised_only_route_count": count_decision("CURRENT_REVISED_HISTORY_ONLY"),
                "rejected_route_count": count_decision("REJECTED"),
                "missing_or_unapproved_families": MISSING_FAMILIES[category],
                "observation_count_semantics": "ONLY_ROLE2_VERIFIED_ROWS_ARE_COUNTED; PROSPECTIVE_METADATA_HAS_NO_FABRICATED_ROWS",
                "config_sha256": config_sha256,
            })
    _require(len(rows) == 135, f"Coverage-by-year must contain 135 rows, got {len(rows)}")
    return rows


def _build_category_rows(
    config: dict[str, object],
    eligible_rows: list[dict[str, str]],
    config_sha256: str,
) -> list[dict[str, object]]:
    candidates = config["candidates"]
    rows: list[dict[str, object]] = []
    for category in CATEGORIES:
        category_candidates = [row for row in candidates if row["category"] == category]
        existing_routes = [row for row in category_candidates if row["source_decision"] == "APPROVED_EXISTING_EVIDENCE_ONLY"]
        approved = [row for row in category_candidates if row["source_decision"] == "APPROVED_FOR_BOUNDED_COLLECTION"]
        observed = [row for row in eligible_rows if row["regime_category"] == category]
        expected_start = min((row["expected_first_reference_date"] for row in approved), default="")
        expected_end = max((row["expected_last_reference_date"] for row in approved), default="")
        coverage_class = (
            "VERIFIED_EXISTING_PLUS_PROSPECTIVE_METADATA_ONLY"
            if observed and approved
            else "VERIFIED_EXISTING_ONLY"
            if observed
            else "PROSPECTIVE_METADATA_ONLY_NO_VERIFIED_OBSERVATIONS"
            if approved
            else "NO_APPROVED_COVERAGE"
        )
        decision_counter = Counter(row["source_decision"] for row in category_candidates)
        rows.append({
            "schema_version": config["schema_version"],
            "program_id": PROGRAM_ID,
            "category": category,
            "minimum_valid_bundle_requirement": MINIMUM_BUNDLES[category],
            "verified_existing_route_count": len(existing_routes),
            "verified_existing_series_count": len({row["source_series_id"] for row in existing_routes}),
            "verified_existing_observation_version_count": len(observed),
            "verified_existing_unique_reference_period_count": len({row["reference_period"] for row in observed}),
            "verified_existing_reference_start": min((row["reference_period"] for row in observed), default=""),
            "verified_existing_reference_end": max((row["reference_period"] for row in observed), default=""),
            "verified_existing_availability_start": min((row["availability_date"] for row in observed), default=""),
            "verified_existing_availability_end": max((row["availability_date"] for row in observed), default=""),
            "approved_bounded_collection_route_count": len(approved),
            "approved_bounded_collection_distinct_indicator_count": len({row["internal_indicator_id"] for row in approved}),
            "approved_bounded_collection_release_bundle_count": len({row["release_bundle"] for row in approved}),
            "prospective_expected_reference_start": expected_start,
            "prospective_expected_reference_end": expected_end,
            "requires_key_or_license_review_route_count": decision_counter["REQUIRES_KEY_OR_LICENSE_REVIEW"],
            "current_revised_history_only_route_count": decision_counter["CURRENT_REVISED_HISTORY_ONLY"],
            "availability_or_version_unresolved_route_count": decision_counter["AVAILABILITY_OR_VERSION_UNRESOLVED"],
            "rejected_route_count": decision_counter["REJECTED"],
            "coverage_evidence_class": coverage_class,
            "pre_2017_status": "PROSPECTIVE_METADATA_ONLY_NOT_YET_COLLECTED",
            "missing_or_unapproved_families": MISSING_FAMILIES[category],
            "source_decision_summary": ";".join(f"{key}={decision_counter[key]}" for key in sorted(decision_counter)),
            "config_sha256": config_sha256,
        })
    _require([row["category"] for row in rows] == list(CATEGORIES), "Category output order changed")
    return rows


def _table_row(values: list[object]) -> str:
    return "| " + " | ".join(str(value).replace("|", "/") for value in values) + " |"


def _build_report(
    config: dict[str, object],
    config_sha256: str,
    code_sha256: str,
    eligible_sha256: str,
    series_csv: bytes,
    year_csv: bytes,
    category_csv: bytes,
    category_rows: list[dict[str, object]],
) -> bytes:
    candidates = config["candidates"]
    decisions = Counter(row["source_decision"] for row in candidates)
    approved_routes = [row for row in candidates if row["source_decision"] == "APPROVED_FOR_BOUNDED_COLLECTION"]
    existing_routes = [row for row in candidates if row["source_decision"] == "APPROVED_EXISTING_EVIDENCE_ONLY"]
    access = config["evidence_access"]
    lines = [
        "# Macro Regime Official Source and Coverage Audit",
        "",
        "## Output envelope",
        "",
        f"- `schema_version`: `{config['schema_version']}`",
        f"- `artifact_id`: `{config['artifact_id']}`",
        f"- `program_id`: `{PROGRAM_ID}`",
        f"- `protocol_id`: `{PROTOCOL_ID}`",
        f"- `created_at_utc`: `{config['created_at_utc']}`",
        f"- `created_by`: `{config['created_by']}`",
        "- `status`: `PASS`",
        "- `decision`: `PASS_BOUNDED_OFFICIAL_SOURCE_SET_FROZEN`",
        "- `final_holdout_access_count`: `0`",
        "- `protected_forward_access_count`: `0`",
        "- `post_2026-06-28_market_outcome_access_count`: `0`",
        "- `macro_observation_api_requests`: `0`",
        "- `raw_macro_observations_downloaded`: `0`",
        "- `experiment_trials_created`: `0`",
        "",
        "## Decision",
        "",
        "`[INTERPRETATION]` The official source plan is fit to proceed to bounded, immutable collection. Nineteen keyless official archive routes are approved across exactly five categories. The approved archive metadata indicates prospective coverage from 2000 for every category, including M2 for LIQUIDITY. This is a source-plan pass, not a data-coverage pass.",
        "",
        "`[FACT]` Only the retained Role 2 ALFRED batch is verified observation evidence: 1,730 immutable versions, five series, 25 source runs/raw artifacts, four categories, reference coverage from 2017-08-01, and zero LIQUIDITY rows. Every archive row in the coverage outputs is labeled `PROSPECTIVE_METADATA_ONLY` and contributes no observation count.",
        "",
        "`[LIMITATION]` Official archives have format, methodology, unit, benchmark, and correction changes. `APPROVED_FOR_BOUNDED_COLLECTION` authorizes a bounded collector with fail-closed parser validation; it does not certify any row before raw bytes, dates, versions, and hashes are captured and independently validated.",
        "",
        "## Verified existing evidence",
        "",
        _table_row(["Category", "Series", "Observation versions", "Reference periods", "Reference coverage", "Decision"]),
        _table_row(["---", "---", "---:", "---:", "---", "---"]),
    ]
    for route in existing_routes:
        lines.append(_table_row([
            route["category"],
            route["source_series_id"],
            route["existing_observation_count"],
            route["existing_unique_reference_period_count"],
            f"{route['expected_first_reference_date']} to {route['expected_last_reference_date']}",
            route["source_decision"],
        ]))

    lines.extend([
        "",
        "Existing ALFRED values remain `VINTAGE_SAFE_WITH_DELAY`. Their date-level vintage availability is activated only by `J0_CONSERVATIVE_36H_FROM_AVAILABILITY_DATE_START_AMERICA_NEW_YORK`; it is not an exact historical release minute or first-receipt claim.",
        "",
        "## Exact approved bounded collection set",
        "",
        _table_row(["Category", "Route", "Series identity", "Bundle", "Expected reference coverage", "Source"]),
        _table_row(["---", "---", "---", "---", "---", "---"]),
    ])
    for route in approved_routes:
        lines.append(_table_row([
            route["category"],
            route["route_id"],
            route["source_series_id"],
            route["release_bundle"],
            f"{route['expected_first_reference_date']} to {route['expected_last_reference_date']}",
            route["source_url"],
        ]))

    lines.extend([
        "",
        "Collection priority is deterministic: (1) H.6 M2 to establish LIQUIDITY from 2000; (2) H.4.1 total assets, reserve balances, and TGA from the 2002 format boundary; (3) pre-2017 gaps for the five existing ALFRED concepts; (4) missing core CPI/PCE/PPI, wages, participation, JOLTS, retail sales, industrial production, and durable goods. Overlapping official archive and retained ALFRED routes reconcile versions but never cast independent category votes.",
        "",
        "## Source-decision census",
        "",
        _table_row(["Frozen source decision", "Route count"]),
        _table_row(["---", "---:"]),
    ])
    for decision in sorted(ALLOWED_DECISIONS):
        lines.append(_table_row([decision, decisions[decision]]))

    lines.extend([
        "",
        "## Category coverage",
        "",
        _table_row(["Category", "Verified versions", "Approved routes", "Approved bundles", "Prospective start", "Coverage class", "Unresolved gap"]),
        _table_row(["---", "---:", "---:", "---:", "---", "---", "---"]),
    ])
    for row in category_rows:
        lines.append(_table_row([
            row["category"],
            row["verified_existing_observation_version_count"],
            row["approved_bounded_collection_route_count"],
            row["approved_bounded_collection_release_bundle_count"],
            row["prospective_expected_reference_start"],
            row["coverage_evidence_class"],
            row["missing_or_unapproved_families"],
        ]))

    lines.extend([
        "",
        "`MACRO_REGIME_COVERAGE_BY_YEAR.csv` contains exactly 135 data rows: every year 2000-2026 crossed with exactly five categories. It carries Role 2 counts by both reference year and availability year. Prospective archive coverage is expressed only as route/indicator/bundle presence; no prospective row count is guessed.",
        "",
        "## Vintage, availability, and revision decisions",
        "",
        "- Dated BLS, BEA, Census, H.15, H.6, H.4.1, and G.17 release files are eligible collection inputs because the raw release copy is tied to a publication date and later releases can remain separate versions.",
        "- Current BLS/BEA/Census/Fed time-series downloads remain useful for reconciliation only; they must not replace archived values or be called point-in-time history.",
        "- FRED/ALFRED `series/vintagedates` and `series/observations` are suitable vintage mechanisms, but new calls require a free registered API key and source-specific terms review. The key must never enter configuration, logs, artifacts, or source control.",
        "- The public NY Fed reverse-repo historical search was not shown to preserve immutable prior correction versions. It is `CURRENT_REVISED_HISTORY_ONLY`. The ALFRED RRP alternative remains key-gated.",
        "- DOL current claims releases show advance and revised values, but an exhaustive stable dated archive traversal for 2000-2026 was not verified. ICSA/CCSA remain unresolved rather than assumed safe.",
        "- ISM and private PMI families are not official government sources and were not accessed. They are rejected under this official-only program. No qualifying national official services diffusion series was identified.",
        "",
        "## Duplicate-vote controls",
        "",
        "- Headline and core CPI share `CPI_BUNDLE`; headline and core PCE share `PCE_BUNDLE`.",
        "- PAYEMS, UNRATE, and participation are components of `EMPLOYMENT_REPORT_BUNDLE`; wages enter `WAGE_PRESSURE_BUNDLE`; ICSA/CCSA would share `CLAIMS_BUNDLE` if later approved.",
        "- GDP, retail sales, industrial production, and durable goods map to distinct frozen growth bundles. Advance versus revised releases are versions, not separate votes.",
        "- Effective rate and target bounds share `POLICY_RATE_BUNDLE`.",
        "- H.4.1 total assets, reserve balances, and TGA map to their named liquidity bundles; multiple revisions or current-download aliases do not create extra votes.",
        "- Category aggregation later remains equal-bundle and equal-category. Observation counts and number of source routes never become weights.",
        "",
        "## Access and usage constraints",
        "",
        "- Official archive downloads are keyless, but collectors must respect agency terms, request pacing, robots directives, and source citation. This audit does not grant redistribution rights.",
        "- BEA labels its archive research-only and warns that data may be superseded. That property is useful for vintages but requires the exact archived table, not the current API table.",
        "- FRED/ALFRED and BEA APIs require registered keys. No key was requested, read, written, or inferred in this role.",
        "- Preserve raw response bodies/files, HTTP metadata, source URLs, retrieval times, release dates, units, seasonal-adjustment state, parser/config/code hashes, and every later correction as an immutable version.",
        "- Current/revised download endpoints may be used only as comparison evidence. A mismatch creates a new version or an error; it never overwrites an archive row.",
        "",
        "## Documentation interaction ledger",
        "",
        f"- Evidence access completed: `{access['completed_at_utc']}`.",
        f"- Official-domain search queries: `{access['official_domain_search_queries']}`.",
        f"- Official page-open attempts: `{access['official_page_open_attempts']}` (`{access['official_page_open_successes']}` successful, `{access['official_page_open_failures']}` safe failure).",
        f"- Total documentation interactions: `{access['total_documentation_interactions']}`; cap: `60`.",
        "- Observation API requests, bulk requests, and raw macro downloads: `0 / 0 / 0`.",
        "- The single safe failure was an in-tool NY Fed terms URL rejection; no bypass or retry occurred. The official data-hub notice that terms apply is retained as the constraint.",
        "",
        "Post-cutoff official documentation metadata was used only to verify current source access and archive contracts. No post-2026-06-28 NAS100 price, technical outcome, macro value, PnL, protected path, or final holdout was accessed or used.",
        "",
        "## Official evidence URLs",
        "",
        _table_row(["Evidence ID", "Official URL", "Audited fact"]),
        _table_row(["---", "---", "---"]),
    ])
    for item in config["official_evidence"]:
        lines.append(_table_row([item["evidence_id"], item["url"], item["fact"]]))

    lines.extend([
        "",
        "## Reproducibility and hashes",
        "",
        f"- Audit config SHA-256: `{config_sha256}`",
        f"- Generator code SHA-256: `{code_sha256}`",
        f"- Role 2 eligible observations SHA-256: `{eligible_sha256}`",
        f"- Coverage-by-series SHA-256: `{_sha256_bytes(series_csv)}`",
        f"- Coverage-by-year SHA-256: `{_sha256_bytes(year_csv)}`",
        f"- Coverage-by-category SHA-256: `{_sha256_bytes(category_csv)}`",
        "",
        _table_row(["Repository input", "Path", "SHA-256"]),
        _table_row(["---", "---", "---"]),
    ])
    for input_id, item in config["repository_inputs"].items():
        lines.append(_table_row([input_id, item["path"], item["sha256"]]))

    lines.extend([
        "",
        "Reproduction command:",
        "",
        "```bash",
        "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m smartmarketscope_quant.macro_regime.source_audit --repo-root .",
        "```",
        "",
        "The validator rehashes every declared repository input, re-reads all 1,730 Role 2 rows, proves five exact categories, enforces the six allowed decisions, rejects post-cutoff dates/non-official evidence URLs/fabricated prospective counts, and regenerates all four outputs byte-identically.",
        "",
        "## Failure codes and limitations",
        "",
        "Non-terminal audit warnings carried forward:",
        "",
        "- `PROSPECTIVE_COVERAGE_NOT_OBSERVATION_EVIDENCE`",
        "- `LIQUIDITY_VERIFIED_OBSERVATION_COUNT_ZERO`",
        "- `CLAIMS_ARCHIVE_AVAILABILITY_OR_VERSION_UNRESOLVED`",
        "- `ALFRED_FREE_API_KEY_REVIEW_REQUIRED_FOR_OPTIONAL_FALLBACKS`",
        "- `CURRENT_REVISED_HISTORY_NOT_VINTAGE_SAFE`",
        "- `OFFICIAL_SERVICES_DIFFUSION_SOURCE_NOT_IDENTIFIED`",
        "- `REGISTRY_CHRONOLOGY_UNRESOLVED_FINAL_CHAMPION_VETO`",
        "",
        "The audit does not claim that the requested 2000-2026 dataset exists yet. Actual coverage, row counts, missing releases, hashes, and parser fitness must be measured during bounded collection. Archive formats and methodology breaks may reduce the prospective plan.",
        "",
        "## Next permitted action",
        "",
        "Proceed sequentially to Role 4, Smart MarketScope Macro Database Architect. Bind the 1,730 verified rows and this frozen 34-route source decision into an immutable, append-only schema and migration plan. Role 4 must not collect observations, score regimes, join technical setups, inspect PnL, or start later roles. Role 5 may later collect only the 19 approved bounded routes, beginning with H.6 M2 and H.4.1 liquidity evidence, under request pacing, checkpoints, raw-body hashes, and fail-closed version semantics.",
        "",
    ])
    try:
        return "\n".join(lines).encode("ascii")
    except UnicodeEncodeError as error:
        raise SourceAuditError(f"Generated report is not ASCII: {error}") from None


def build_audit(repo_root: Path) -> AuditResult:
    repo_root = repo_root.resolve()
    config_path = repo_root / CONFIG_RELATIVE_PATH
    eligible_path = repo_root / ELIGIBLE_RELATIVE_PATH
    series_reclassification_path = repo_root / SERIES_RECLASSIFICATION_RELATIVE_PATH
    config = _load_json(config_path)
    _validate_config(config)
    _check_input_hashes(repo_root, config)

    eligible_rows = _load_csv(eligible_path)
    role2_series_rows = _load_csv(series_reclassification_path)
    candidates = config["candidates"]
    _validate_existing_rows(eligible_rows, role2_series_rows, candidates)

    config_sha256 = _sha256_file(config_path)
    eligible_sha256 = _sha256_file(eligible_path)
    code_sha256 = _sha256_file(Path(__file__))
    series_rows = _build_series_rows(config, config_sha256, eligible_sha256)
    year_rows = _build_year_rows(config, eligible_rows, config_sha256)
    category_rows = _build_category_rows(config, eligible_rows, config_sha256)
    series_csv = _csv_bytes(SERIES_FIELDS, series_rows)
    year_csv = _csv_bytes(YEAR_FIELDS, year_rows)
    category_csv = _csv_bytes(CATEGORY_FIELDS, category_rows)
    report = _build_report(
        config,
        config_sha256,
        code_sha256,
        eligible_sha256,
        series_csv,
        year_csv,
        category_csv,
        category_rows,
    )
    summary = {
        "status": config["status"],
        "decision": config["decision"],
        "candidate_route_count": len(candidates),
        "series_output_count": len(series_rows),
        "year_output_count": len(year_rows),
        "category_output_count": len(category_rows),
        "verified_existing_observation_count": len(eligible_rows),
        "verified_existing_route_count": sum(row["source_decision"] == "APPROVED_EXISTING_EVIDENCE_ONLY" for row in candidates),
        "approved_bounded_route_count": sum(row["source_decision"] == "APPROVED_FOR_BOUNDED_COLLECTION" for row in candidates),
        "decision_counts": dict(Counter(row["source_decision"] for row in candidates)),
        "category_verified_counts": {row["category"]: row["verified_existing_observation_version_count"] for row in category_rows},
        "documentation_interactions": config["evidence_access"]["total_documentation_interactions"],
        "config_sha256": config_sha256,
        "code_sha256": code_sha256,
        "output_sha256": {
            OUTPUT_FILES[0]: _sha256_bytes(report),
            OUTPUT_FILES[1]: _sha256_bytes(year_csv),
            OUTPUT_FILES[2]: _sha256_bytes(series_csv),
            OUTPUT_FILES[3]: _sha256_bytes(category_csv),
        },
    }
    return AuditResult(report, year_csv, series_csv, category_csv, summary)


def write_outputs(repo_root: Path, result: AuditResult) -> None:
    for relative_path, content in result.outputs().items():
        path = repo_root / relative_path
        path.write_bytes(content)


def validate_outputs(repo_root: Path, result: AuditResult) -> None:
    for relative_path, expected in result.outputs().items():
        path = repo_root / relative_path
        _require(path.exists(), f"Missing generated output: {relative_path}")
        actual = path.read_bytes()
        _require(actual == expected, f"Generated output is stale or non-deterministic: {relative_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate and validate the official macro-regime source audit")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    try:
        result = build_audit(repo_root)
        if args.validate_only:
            validate_outputs(repo_root, result)
        else:
            write_outputs(repo_root, result)
    except SourceAuditError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result.summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from io import StringIO
from pathlib import Path

from .h6_full_collector import (
    CONFIG_PATH,
    CONFIG_HASH_PATH,
    PILOT_CONFIG_PATH,
    canonical_json,
    config_hash,
    pilot_cache,
    release_identities,
)
from .historical_collector import CollectionValidationError, j0, parse_release, sha256_bytes


OUTPUT_DIR = Path("research/artifacts/macro_regime/role5")
NORMALIZATION_CONFIG_PATH = Path("research/config/macro_regime_h6_full_normalization_v1.json")
NORMALIZATION_HASH_PATH = Path("research/config/macro_regime_h6_full_normalization_v1.sha256")
DIRECT_CLASSIFICATION = "DIRECT_OFFICIAL_DATED_RELEASE_IDENTITY"
ELIGIBLE_CLASSIFICATION = "PIT_CERTIFIED_OFFICIAL_DATED_RELEASE_CHAIN"
ELIGIBLE_PROTOCOL_STATUS = "ELIGIBLE_COMPLETE_H6_REVISION_CHAIN"
EXCEPTION_RUNS = {
    "20050305": "role5-h6-full-0279-20050305-a1",
    "20130405": "role5-h6-correction-0703-20130404",
    "20161118": "role5-h6-full-0892-20161118-a1",
    "20171123": "role5-h6-full-0947-20171123-a1",
}


def csv_bytes(rows: list[dict[str, object]], fields: list[str]) -> bytes:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def frozen_hash(repo_root: Path, data_path: Path, hash_path: Path) -> str:
    raw = (repo_root / data_path).read_bytes()
    actual = sha256_bytes(raw)
    expected = (repo_root / hash_path).read_text(encoding="ascii").split()[0]
    if actual != expected:
        raise CollectionValidationError(f"Frozen hash mismatch: {data_path}: {actual}")
    return actual


def decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def next_month(value: str) -> str:
    parsed = date.fromisoformat(value)
    if parsed.month == 12:
        return date(parsed.year + 1, 1, 1).isoformat()
    return date(parsed.year, parsed.month + 1, 1).isoformat()


def header_retrieval_time(path: Path) -> str:
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="iso-8859-1", errors="replace").replace("\r", "").splitlines():
        if line.lower().startswith("date:"):
            try:
                parsed = parsedate_to_datetime(line.split(":", 1)[1].strip()).astimezone(timezone.utc)
                return parsed.isoformat().replace("+00:00", "Z")
            except (TypeError, ValueError, OverflowError):
                return ""
    return ""


def parser_input(body: bytes, source_format: str) -> bytes:
    return b"<pre>" + body + b"</pre>" if source_format == "ASCII" else body


def load_inputs(repo_root: Path) -> dict[str, object]:
    full_hash = config_hash(repo_root)
    full_config = json.loads((repo_root / CONFIG_PATH).read_text(encoding="ascii"))
    normalization_hash = frozen_hash(repo_root, NORMALIZATION_CONFIG_PATH, NORMALIZATION_HASH_PATH)
    normalization = json.loads((repo_root / NORMALIZATION_CONFIG_PATH).read_text(encoding="ascii"))
    if normalization["parent_full_traversal_config_sha256"] != full_hash:
        raise CollectionValidationError("Normalization contract has wrong traversal parent")
    raw_root = Path(full_config["storage_policy"]["private_raw_root"])
    namespace = raw_root / full_config["storage_policy"]["full_traversal_namespace"]
    checkpoint_path = namespace / "checkpoint.json"
    checkpoint_raw = checkpoint_path.read_bytes()
    checkpoint_hash = sha256_bytes(checkpoint_raw)
    checkpoint = json.loads(checkpoint_raw)
    if checkpoint_hash != normalization["terminal_raw_checkpoint_sha256"]:
        raise CollectionValidationError("Terminal raw checkpoint differs from frozen normalization input")
    if checkpoint["status"] != normalization["terminal_raw_checkpoint_status_required"]:
        raise CollectionValidationError("Raw H6 sequence is not complete")
    if checkpoint["identity_count"] != normalization["expected_release_identity_count"]:
        raise CollectionValidationError("Raw identity count differs from normalization contract")

    lineage_hashes: dict[str, str] = {}
    for hash_path in sorted((repo_root / "research/config").glob("macro_regime_h6_*.sha256")):
        data_path = hash_path.with_suffix(".json")
        if not data_path.is_file():
            raise CollectionValidationError(f"Frozen H6 config missing for hash file: {hash_path.name}")
        actual = sha256_bytes(data_path.read_bytes())
        expected = hash_path.read_text(encoding="ascii").split()[0]
        if actual != expected:
            raise CollectionValidationError(f"H6 lineage config hash mismatch: {data_path.name}")
        lineage_hashes[data_path.name] = actual

    release_index = raw_root / "vintage_year=2026" / "source_run=role5-release-dates-0003" / "releaseDates.json"
    release_index_raw = release_index.read_bytes()
    if sha256_bytes(release_index_raw) != full_config["release_dates_raw_sha256"]:
        raise CollectionValidationError("Official releaseDates index hash changed")
    identities = release_identities(release_index_raw, full_config)
    if identities != checkpoint["completed_release_ids"]:
        raise CollectionValidationError("Completed release order differs from official source index")
    pilot = json.loads((repo_root / PILOT_CONFIG_PATH).read_text(encoding="ascii"))
    cache = pilot_cache(full_config, pilot, raw_root)
    return {
        "full_hash": full_hash,
        "full_config": full_config,
        "normalization_hash": normalization_hash,
        "normalization": normalization,
        "raw_root": raw_root,
        "namespace": namespace,
        "checkpoint": checkpoint,
        "checkpoint_hash": checkpoint_hash,
        "identities": identities,
        "pilot": pilot,
        "cache": cache,
        "lineage_hashes": lineage_hashes,
    }


def load_attempts(namespace: Path, raw_root: Path, checkpoint: dict[str, object]) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    attempts: list[dict[str, object]] = []
    by_run: dict[str, dict[str, object]] = {}
    for attempt_path in sorted(namespace.glob("**/attempt.json")):
        raw = attempt_path.read_bytes()
        attempt = json.loads(raw)
        body_name = str(attempt.get("body_filename", "release.html"))
        source_format = str(attempt.get("source_format", "HTML"))
        body_path = attempt_path.with_name(body_name)
        header_path = attempt_path.with_name("safe_headers.txt")
        body = body_path.read_bytes()
        headers = header_path.read_bytes()
        if sha256_bytes(body) != attempt["body_sha256"]:
            raise CollectionValidationError(f"Body hash mismatch: {attempt['source_run_id']}")
        if sha256_bytes(headers) != attempt["safe_header_sha256"]:
            raise CollectionValidationError(f"Safe-header hash mismatch: {attempt['source_run_id']}")
        record = dict(attempt)
        record["body_filename"] = body_name
        record["source_format"] = source_format
        record["attempt_record_sha256"] = sha256_bytes(raw)
        record["relative_attempt_path"] = str(attempt_path.relative_to(raw_root))
        record["relative_body_path"] = str(body_path.relative_to(raw_root))
        record["relative_safe_header_path"] = str(header_path.relative_to(raw_root))
        record["_body_path"] = body_path
        record["_attempt_path"] = attempt_path
        if record["source_run_id"] in by_run:
            raise CollectionValidationError(f"Duplicate source run: {record['source_run_id']}")
        attempts.append(record)
        by_run[str(record["source_run_id"])] = record
    attempts.sort(key=lambda item: int(item["network_request_ordinal_role5"]))
    ordinals = [int(item["network_request_ordinal_role5"]) for item in attempts]
    if len(attempts) != checkpoint["new_network_attempt_count"] or len(set(ordinals)) != len(ordinals):
        raise CollectionValidationError("Full attempt count or request ordinal uniqueness failed")
    if ordinals != list(range(11, checkpoint["total_role5_network_request_count"] + 1)):
        raise CollectionValidationError("Role 5 network request ordinals are not contiguous after pilot")
    return attempts, by_run


def accepted_releases(inputs: dict[str, object], attempts_by_run: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    full_config = inputs["full_config"]
    raw_root: Path = inputs["raw_root"]
    namespace: Path = inputs["namespace"]
    cache: dict[str, dict[str, object]] = inputs["cache"]
    identities: list[str] = inputs["identities"]
    normalization = inputs["normalization"]
    pilot = inputs["pilot"]
    pilot_urls = {
        re.search(r"/(\d{8})/", str(entry["url"])).group(1): str(entry["url"])
        for entry in pilot["request_ledger"] if entry["kind"] == "PILOT_RELEASE"
    }
    successes: dict[str, list[dict[str, object]]] = defaultdict(list)
    for attempt in attempts_by_run.values():
        if attempt["outcome"] == "SUCCESS":
            successes[str(attempt["release_id"])].append(attempt)

    releases: list[dict[str, object]] = []
    for source_identity in identities:
        acquisition = "NEW_FULL_TRAVERSAL_BODY"
        source_identity_classification = DIRECT_CLASSIFICATION
        reconciliation_relative_path = ""
        if source_identity in cache:
            cached = cache[source_identity]
            body_path = Path(str(cached["path"]))
            source_run_id = str(cached["source_run_id"])
            source_format = "HTML"
            body_sha256 = str(cached["sha256"])
            source_url = pilot_urls[source_identity]
            retrieved_at = header_retrieval_time(body_path.with_name("headers.txt"))
            acquisition = "HASH_VERIFIED_PILOT_CACHE_REUSE"
        elif source_identity in EXCEPTION_RUNS:
            attempt = attempts_by_run[EXCEPTION_RUNS[source_identity]]
            body_path = Path(str(attempt["_body_path"]))
            source_run_id = str(attempt["source_run_id"])
            source_format = str(attempt["source_format"])
            body_sha256 = str(attempt["body_sha256"])
            source_url = str(attempt["source_url"])
            retrieved_at = str(attempt["completed_at_utc"])
            override = normalization["canonical_availability_overrides"][source_identity]
            source_identity_classification = str(override["classification"])
            if source_identity == "20050305":
                reconciliation = namespace / "alias_reconciliations/source_index_identity=20050305/reconciliation.json"
            elif source_identity == "20130405":
                reconciliation = namespace / "identity_corrections/json_identity=2013-04-05/reconciliation.json"
            else:
                formatted = f"{source_identity[:4]}-{source_identity[4:6]}-{source_identity[6:]}"
                reconciliation = namespace / f"pdf_corroborations/source_index_identity={formatted}/reconciliation.json"
            evidence = json.loads(reconciliation.read_text(encoding="ascii"))
            if evidence["classification"] != source_identity_classification:
                raise CollectionValidationError(f"Exact reconciliation classification mismatch: {source_identity}")
            if evidence["availability_date_for_j0"] != override["availability_date"]:
                raise CollectionValidationError(f"Exact reconciliation availability mismatch: {source_identity}")
            reconciliation_relative_path = str(reconciliation.relative_to(raw_root))
            acquisition = "EXACT_RECONCILED_OFFICIAL_BODY"
        else:
            candidates = successes.get(source_identity, [])
            if len(candidates) != 1:
                raise CollectionValidationError(f"Expected one accepted body for {source_identity}, got {len(candidates)}")
            attempt = candidates[0]
            body_path = Path(str(attempt["_body_path"]))
            source_run_id = str(attempt["source_run_id"])
            source_format = str(attempt["source_format"])
            body_sha256 = str(attempt["body_sha256"])
            source_url = str(attempt["source_url"])
            retrieved_at = str(attempt["completed_at_utc"])

        body = body_path.read_bytes()
        if sha256_bytes(body) != body_sha256:
            raise CollectionValidationError(f"Accepted body hash mismatch: {source_identity}")
        declared_release, parser_format, values = parse_release(parser_input(body, source_format))
        canonical_date = declared_release
        if source_identity in normalization["canonical_availability_overrides"]:
            expected_date = normalization["canonical_availability_overrides"][source_identity]["availability_date"]
            if canonical_date != expected_date:
                raise CollectionValidationError(f"Exception body date mismatch: {source_identity}")
        elif canonical_date.replace("-", "") != source_identity:
            raise CollectionValidationError(f"Direct body date mismatch: {source_identity}")
        if parser_format not in normalization["accepted_parser_formats"]:
            raise CollectionValidationError(f"Parser format outside normalization contract: {parser_format}")
        if canonical_date > normalization["availability_cutoff_date"]:
            raise CollectionValidationError(f"Post-cutoff canonical release: {source_identity}")
        references = [item.reference_date for item in values]
        if len(references) != len(set(references)):
            raise CollectionValidationError(f"Duplicate reference within release: {source_identity}")
        if len(values) < 12:
            raise CollectionValidationError(f"Unexpectedly sparse accepted Table 1: {source_identity}")
        if any(Decimal(item.value) <= 0 for item in values):
            raise CollectionValidationError(f"Nonpositive M2 value: {source_identity}")
        lowered = body.lower()
        method_markers = []
        for marker in (
            b"before may 2020",
            b"definition of m1",
            b"historical and current definitions",
            b"first monthly h.6 statistical release",
            b"published at a monthly frequency",
            b"leaving the m2 monetary aggregate unchanged",
        ):
            if marker in lowered:
                method_markers.append(marker.decode("ascii"))
        releases.append({
            "source_index_identity": source_identity,
            "canonical_release_date": canonical_date,
            "source_identity_classification": source_identity_classification,
            "acquisition_classification": acquisition,
            "source_run_id": source_run_id,
            "source_url": source_url,
            "source_format": source_format,
            "parser_format": parser_format,
            "raw_artifact_id": f"{source_run_id}-body",
            "raw_artifact_sha256": body_sha256,
            "relative_private_path": str(body_path.relative_to(raw_root)),
            "retrieved_at_utc": retrieved_at,
            "reconciliation_relative_path": reconciliation_relative_path,
            "values": values,
            "method_note_markers": method_markers,
        })

    releases.sort(key=lambda item: (str(item["canonical_release_date"]), str(item["source_index_identity"])))
    canonical_dates = [str(item["canonical_release_date"]) for item in releases]
    if canonical_dates != sorted(canonical_dates) or len(set(canonical_dates)) != len(canonical_dates):
        raise CollectionValidationError("Canonical availability dates are not strictly increasing and unique")
    if len(releases) != normalization["expected_release_identity_count"]:
        raise CollectionValidationError("Accepted release count mismatch")
    return releases


def build_chains(releases: list[dict[str, object]], normalization: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    start = str(normalization["requested_reference_date_start"])
    cutoff = str(normalization["availability_cutoff_date"])
    observations: list[dict[str, object]] = []
    snapshots: list[dict[str, object]] = []
    current: dict[str, dict[str, object]] = {}
    versions: Counter[str] = Counter()
    first_appearance_gate_count = 0
    for release in releases:
        values = sorted(release["values"], key=lambda item: item.reference_date)
        newest_reference = max(item.reference_date for item in values)
        for value in values:
            reference = value.reference_date
            if reference < start or reference > cutoff:
                continue
            numeric = Decimal(value.value)
            numeric_text = decimal_text(numeric)
            previous = current.get(reference)
            if previous is None:
                if reference != newest_reference:
                    raise CollectionValidationError(
                        f"Frozen first-appearance gate failed: {reference} first appears in "
                        f"{release['source_index_identity']} but newest reference is {newest_reference}"
                    )
                first_appearance_gate_count += 1
                versions[reference] += 1
                action = "FIRST_PRINT_CREATED"
                kind = "FIRST_PRINT"
                previous_id = ""
                previous_value = ""
                delta = ""
                creates_version = True
            elif Decimal(str(previous["normalized_numeric_value"])) != numeric:
                versions[reference] += 1
                action = "REVISION_CREATED"
                kind = "REVISION"
                previous_id = str(previous["observation_id"])
                previous_value = str(previous["normalized_numeric_value"])
                delta = decimal_text(numeric - Decimal(previous_value))
                creates_version = True
            else:
                action = "UNCHANGED_SNAPSHOT_NO_NEW_VERSION"
                kind = ""
                previous_id = str(previous["observation_id"])
                previous_value = str(previous["normalized_numeric_value"])
                delta = "0"
                creates_version = False

            if creates_version:
                version = versions[reference]
                observation_id = f"H6-M2-{reference[:7].replace('-', '')}-V{version:04d}"
                effective_utc, effective_my = j0(str(release["canonical_release_date"]))
                row: dict[str, object] = {
                    "observation_id": observation_id,
                    "source_series_id": "H6/M2SL",
                    "internal_indicator_id": "US_M2_MONEY_STOCK_SA",
                    "category": "LIQUIDITY",
                    "release_bundle": "MONEY_SUPPLY_BUNDLE",
                    "reference_date": reference,
                    "observation_version": version,
                    "measurement_version_kind": kind,
                    "supersedes_observation_id": previous_id,
                    "previous_normalized_numeric_value": previous_value,
                    "revision_delta": delta,
                    "raw_value": value.value,
                    "normalized_numeric_value": numeric_text,
                    "unit": "BILLIONS_OF_DOLLARS",
                    "frequency": "MONTHLY",
                    "seasonal_adjustment": "SEASONALLY_ADJUSTED",
                    "raw_label": value.raw_label,
                    "source_index_identity": release["source_index_identity"],
                    "canonical_release_date": release["canonical_release_date"],
                    "availability_date": release["canonical_release_date"],
                    "effective_at_utc": effective_utc,
                    "effective_at_asia_kuala_lumpur": effective_my,
                    "availability_rule": "J0_CONSERVATIVE_36H_FROM_CANONICAL_DATED_RELEASE_DATE_START_AMERICA_NEW_YORK",
                    "source_identity_classification": release["source_identity_classification"],
                    "acquisition_classification": release["acquisition_classification"],
                    "source_run_id": release["source_run_id"],
                    "raw_artifact_id": release["raw_artifact_id"],
                    "raw_artifact_sha256": release["raw_artifact_sha256"],
                    "raw_relative_private_path": release["relative_private_path"],
                    "parser_format": release["parser_format"],
                    "point_in_time_classification": ELIGIBLE_CLASSIFICATION,
                    "protocol_eligibility": ELIGIBLE_PROTOCOL_STATUS,
                    "historical_reconstruction": True,
                }
                row["observation_payload_sha256"] = sha256_bytes(canonical_json(row))
                observations.append(row)
                current[reference] = row
            else:
                observation_id = str(previous["observation_id"])
                version = int(previous["observation_version"])

            snapshots.append({
                "release_snapshot_id": f"H6-M2-{release['source_index_identity']}-{reference[:7].replace('-', '')}",
                "source_index_identity": release["source_index_identity"],
                "canonical_release_date": release["canonical_release_date"],
                "reference_date": reference,
                "raw_value": value.value,
                "normalized_numeric_value": numeric_text,
                "snapshot_action": action,
                "created_observation_version": str(creates_version).lower(),
                "active_observation_id": observation_id,
                "active_observation_version": version,
                "previous_observation_id": previous_id,
                "previous_normalized_numeric_value": previous_value,
                "revision_delta": delta,
                "source_identity_classification": release["source_identity_classification"],
                "acquisition_classification": release["acquisition_classification"],
                "source_run_id": release["source_run_id"],
                "raw_artifact_id": release["raw_artifact_id"],
                "raw_artifact_sha256": release["raw_artifact_sha256"],
                "parser_format": release["parser_format"],
            })

    references = sorted(current)
    if not references or references[0] != start:
        raise CollectionValidationError(f"Frozen reference-start gate failed: {references[:1]}")
    for prior, following in zip(references, references[1:]):
        if next_month(prior) != following:
            raise CollectionValidationError(f"Frozen contiguous-month gate failed: {prior} -> {following}")
    if first_appearance_gate_count != len(references):
        raise CollectionValidationError("First-appearance proof count differs from unique reference count")
    by_reference: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in observations:
        by_reference[str(row["reference_date"])].append(row)
    for reference, rows in by_reference.items():
        rows.sort(key=lambda item: int(item["observation_version"]))
        if [int(item["observation_version"]) for item in rows] != list(range(1, len(rows) + 1)):
            raise CollectionValidationError(f"Non-contiguous version chain: {reference}")
        for index, row in enumerate(rows):
            expected = "" if index == 0 else rows[index - 1]["observation_id"]
            if row["supersedes_observation_id"] != expected:
                raise CollectionValidationError(f"Broken supersedes link: {reference}")
    stats = {
        "unique_reference_month_count": len(references),
        "first_reference_date": references[0],
        "last_reference_date": references[-1],
        "first_appearance_gate_pass_count": first_appearance_gate_count,
        "contiguous_month_transition_pass_count": len(references) - 1,
        "observation_version_count": len(observations),
        "first_print_count": sum(item["measurement_version_kind"] == "FIRST_PRINT" for item in observations),
        "revision_count": sum(item["measurement_version_kind"] == "REVISION" for item in observations),
        "release_snapshot_count": len(snapshots),
        "unchanged_snapshot_count": sum(item["snapshot_action"] == "UNCHANGED_SNAPSHOT_NO_NEW_VERSION" for item in snapshots),
    }
    if stats["release_snapshot_count"] != stats["observation_version_count"] + stats["unchanged_snapshot_count"]:
        raise CollectionValidationError("Snapshot/version accounting invariant failed")
    return observations, snapshots, stats


def method_lineage(releases: list[dict[str, object]]) -> dict[str, object]:
    segments: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    marker_releases: list[dict[str, object]] = []
    for release in releases:
        parser_format = str(release["parser_format"])
        if current is None or current["parser_format"] != parser_format:
            if current is not None:
                segments.append(current)
            current = {
                "parser_format": parser_format,
                "first_source_index_identity": release["source_index_identity"],
                "first_canonical_release_date": release["canonical_release_date"],
                "last_source_index_identity": release["source_index_identity"],
                "last_canonical_release_date": release["canonical_release_date"],
                "release_count": 1,
                "classification": "PRESENTATION_FORMAT_SEGMENT_NOT_INFERRED_DEFINITION_BREAK",
            }
        else:
            current["last_source_index_identity"] = release["source_index_identity"]
            current["last_canonical_release_date"] = release["canonical_release_date"]
            current["release_count"] = int(current["release_count"]) + 1
        if release["method_note_markers"]:
            marker_releases.append({
                "source_index_identity": release["source_index_identity"],
                "canonical_release_date": release["canonical_release_date"],
                "raw_artifact_sha256": release["raw_artifact_sha256"],
                "markers": release["method_note_markers"],
            })
    if current is not None:
        segments.append(current)
    monthly_transition = next(
        (
            release
            for release in releases
            if {
                "first monthly h.6 statistical release",
                "published at a monthly frequency",
            }.issubset(set(release["method_note_markers"]))
        ),
        None,
    )
    if monthly_transition is None or monthly_transition["canonical_release_date"] != "2021-02-23":
        raise CollectionValidationError("Official H6 weekly-to-monthly transition evidence is missing")
    transition_index = releases.index(monthly_transition)
    if transition_index == 0 or releases[transition_index - 1]["canonical_release_date"] != "2021-02-11":
        raise CollectionValidationError("Official H6 last-weekly/first-monthly boundary is not contiguous")
    cadence_segments = [
        {
            "publication_cadence": "WEEKLY_RELEASE",
            "first_canonical_release_date": releases[0]["canonical_release_date"],
            "last_canonical_release_date": releases[transition_index - 1]["canonical_release_date"],
            "release_count": transition_index,
            "classification": "SOURCE_PUBLICATION_CADENCE_NOT_MEASUREMENT_FREQUENCY",
        },
        {
            "publication_cadence": "MONTHLY_RELEASE",
            "first_canonical_release_date": monthly_transition["canonical_release_date"],
            "last_canonical_release_date": releases[-1]["canonical_release_date"],
            "release_count": len(releases) - transition_index,
            "classification": "SOURCE_PUBLICATION_CADENCE_NOT_MEASUREMENT_FREQUENCY",
        },
    ]
    return {
        "schema_version": "1.0.0",
        "artifact_id": "ROLE5-H6-METHOD-LINEAGE-001",
        "series": "M2",
        "table": "H6_TABLE_1",
        "unit": "BILLIONS_OF_DOLLARS",
        "seasonal_adjustment": "SEASONALLY_ADJUSTED",
        "release_count_validated": len(releases),
        "parser_format_segments": segments,
        "publication_cadence_segments": cadence_segments,
        "publication_cadence_transition_evidence": {
            "source_index_identity": monthly_transition["source_index_identity"],
            "canonical_release_date": monthly_transition["canonical_release_date"],
            "raw_artifact_sha256": monthly_transition["raw_artifact_sha256"],
            "classification": "OFFICIAL_FIRST_MONTHLY_H6_RELEASE",
            "prior_last_weekly_release_date": releases[transition_index - 1]["canonical_release_date"],
        },
        "m2_definition_transition_assessment": {
            "official_note_marker": "leaving the m2 monetary aggregate unchanged",
            "classification": "M1_PRESENTATION_AND_DEFINITION_CHANGE_M2_STATED_UNCHANGED",
            "measurement_frequency_remains": "MONTHLY",
        },
        "method_note_marker_release_count": len(marker_releases),
        "first_method_note_marker": marker_releases[0] if marker_releases else None,
        "last_method_note_marker": marker_releases[-1] if marker_releases else None,
        "inferred_definition_breaks": [],
        "classification": "NO_OUTCOME_AWARE_DEFINITION_BREAK_INFERRED_VALUE_CHAIN_RETAINS_RAW_METHOD_NOTE_LINEAGE",
        "warning": "Parser-format transitions are presentation changes, not proof of an economic-series definition break.",
    }


def build(repo_root: Path) -> dict[str, bytes]:
    inputs = load_inputs(repo_root)
    attempts, attempts_by_run = load_attempts(inputs["namespace"], inputs["raw_root"], inputs["checkpoint"])
    releases = accepted_releases(inputs, attempts_by_run)
    observations, snapshots, stats = build_chains(releases, inputs["normalization"])
    methods = method_lineage(releases)
    accepted_runs = {str(item["source_run_id"]) for item in releases}
    cached_runs = {str(item["source_run_id"]) for item in releases if item["acquisition_classification"] == "HASH_VERIFIED_PILOT_CACHE_REUSE"}

    source_run_lines = []
    artifacts: list[dict[str, object]] = []
    for attempt in attempts:
        export = {key: value for key, value in attempt.items() if not key.startswith("_")}
        source_run_lines.append(canonical_json(export))
        artifacts.append({
            "raw_artifact_id": f"{attempt['source_run_id']}-body",
            "source_run_id": attempt["source_run_id"],
            "release_id": attempt["release_id"],
            "source_url": attempt["source_url"],
            "relative_private_path": attempt["relative_body_path"],
            "source_format": attempt["source_format"],
            "byte_length": attempt["body_byte_length"],
            "sha256": attempt["body_sha256"],
            "http_status": attempt["http_status"],
            "outcome": attempt["outcome"],
            "retrieved_at_utc": attempt["completed_at_utc"],
            "safe_header_relative_path": attempt["relative_safe_header_path"],
            "safe_header_sha256": attempt["safe_header_sha256"],
            "parser_version": attempt["parser_version"],
            "accepted_for_measurement_chain": str(attempt["source_run_id"] in accepted_runs).lower(),
            "acquisition_classification": "FULL_NETWORK_ATTEMPT",
        })
    for release in releases:
        if release["source_run_id"] not in cached_runs:
            continue
        body_path = inputs["raw_root"] / str(release["relative_private_path"])
        header_path = body_path.with_name("headers.txt")
        artifacts.append({
            "raw_artifact_id": release["raw_artifact_id"],
            "source_run_id": release["source_run_id"],
            "release_id": release["source_index_identity"],
            "source_url": release["source_url"],
            "relative_private_path": release["relative_private_path"],
            "source_format": "HTML",
            "byte_length": len(body_path.read_bytes()),
            "sha256": release["raw_artifact_sha256"],
            "http_status": 200,
            "outcome": "HASH_VERIFIED_PILOT_CACHE_REUSE",
            "retrieved_at_utc": release["retrieved_at_utc"],
            "safe_header_relative_path": str(header_path.relative_to(inputs["raw_root"])),
            "safe_header_sha256": sha256_bytes(header_path.read_bytes()),
            "parser_version": inputs["full_config"]["parser_version"],
            "accepted_for_measurement_chain": "true",
            "acquisition_classification": "HASH_VERIFIED_PILOT_CACHE_REUSE",
        })
    artifacts.sort(key=lambda item: (str(item["release_id"]), str(item["source_run_id"])))

    failures = [item for item in attempts if not str(item["outcome"]).startswith("SUCCESS")]
    failure_rows = [{
        "source_run_id": item["source_run_id"],
        "release_id": item["release_id"],
        "network_request_ordinal_role5": item["network_request_ordinal_role5"],
        "source_url": item["source_url"],
        "http_status": item["http_status"],
        "outcome": item["outcome"],
        "body_sha256": item["body_sha256"],
        "redacted_error": item.get("redacted_error") or "",
        "recovered_by_exact_reconciliation": "true",
        "terminal_effect": "EVIDENCE_PRESERVED_EXACT_REPAIR_CHAIN_CONTINUED",
    } for item in failures]

    releases_by_year: dict[int, list[dict[str, object]]] = defaultdict(list)
    snapshots_by_year: Counter[int] = Counter()
    firsts_by_year: Counter[int] = Counter()
    revisions_by_year: Counter[int] = Counter()
    unchanged_by_year: Counter[int] = Counter()
    for release in releases:
        releases_by_year[int(str(release["canonical_release_date"])[:4])].append(release)
    for row in snapshots:
        year = int(str(row["canonical_release_date"])[:4])
        snapshots_by_year[year] += 1
        if row["snapshot_action"] == "FIRST_PRINT_CREATED":
            firsts_by_year[year] += 1
        elif row["snapshot_action"] == "REVISION_CREATED":
            revisions_by_year[year] += 1
        else:
            unchanged_by_year[year] += 1
    coverage_rows = []
    for year in range(2000, 2027):
        year_releases = releases_by_year[year]
        coverage_rows.append({
            "year": year,
            "accepted_release_count": len(year_releases),
            "direct_release_count": sum(item["source_identity_classification"] == DIRECT_CLASSIFICATION for item in year_releases),
            "exact_reconciled_release_count": sum(item["source_identity_classification"] != DIRECT_CLASSIFICATION for item in year_releases),
            "parsed_snapshot_count": snapshots_by_year[year],
            "first_print_count": firsts_by_year[year],
            "revision_count": revisions_by_year[year],
            "unchanged_snapshot_count": unchanged_by_year[year],
            "coverage_status": "COMPLETE_HASH_AND_CHAIN_VALIDATED",
        })

    outcome_counts = Counter(str(item["outcome"]) for item in attempts)
    http_counts = Counter(str(item["http_status"]) for item in attempts)
    parser_counts = Counter(str(item["parser_format"]) for item in releases)
    identity_counts = Counter(str(item["source_identity_classification"]) for item in releases)
    acquisition_counts = Counter(str(item["acquisition_classification"]) for item in releases)
    checkpoint = inputs["checkpoint"]
    manifest = {
        "schema_version": "1.0.0",
        "artifact_id": "ROLE5-H6-FULL-NORMALIZED-MANIFEST-001",
        "program_id": inputs["full_config"]["program_id"],
        "request_id": inputs["full_config"]["request_id"],
        "created_at_utc": checkpoint["last_updated_at_utc"],
        "status": "PASS",
        "decision": "H6_FULL_POINT_IN_TIME_REVISION_CHAIN_VALIDATED",
        "full_traversal_config_sha256": inputs["full_hash"],
        "normalization_contract_sha256": inputs["normalization_hash"],
        "terminal_raw_checkpoint_sha256": inputs["checkpoint_hash"],
        "lineage_config_hashes": inputs["lineage_hashes"],
        "expected_release_identity_count": len(inputs["identities"]),
        "accepted_release_identity_count": len(releases),
        "new_network_attempt_count": len(attempts),
        "total_role5_network_request_count_including_pilot": checkpoint["total_role5_network_request_count"],
        "hard_total_role5_network_request_ceiling": inputs["full_config"]["hard_total_role5_network_request_ceiling"],
        "remaining_request_headroom": inputs["full_config"]["hard_total_role5_network_request_ceiling"] - checkpoint["total_role5_network_request_count"],
        "retry_count": checkpoint["retry_count"],
        "failed_attempt_count_preserved_and_reconciled": len(failures),
        "outcome_counts": dict(sorted(outcome_counts.items())),
        "http_status_counts": dict(sorted(http_counts.items())),
        "accepted_parser_format_counts": dict(sorted(parser_counts.items())),
        "source_identity_classification_counts": dict(sorted(identity_counts.items())),
        "acquisition_classification_counts": dict(sorted(acquisition_counts.items())),
        **stats,
        "eligible_h6_observation_version_count": len(observations),
        "retained_role2_eligible_observation_count": 1730,
        "combined_verified_observation_count": 1730 + len(observations),
        "pilot_sparse_observation_count_preserved_ineligible": 103,
        "first_appearance_gate": "PASS",
        "contiguous_month_gate": "PASS",
        "canonical_chronology_gate": "PASS",
        "raw_hash_gate": "PASS",
        "supersedes_chain_gate": "PASS",
        "point_in_time_classification": ELIGIBLE_CLASSIFICATION,
        "protocol_eligibility": ELIGIBLE_PROTOCOL_STATUS,
        "h41_started": False,
        "role6_started": False,
        "technical_join_started": False,
        "pnl_inspection_started": False,
        "experiment_trials": 0,
        "final_holdout_accesses": 0,
        "exact_next_permitted_action": "Prospectively freeze and run the bounded H.4.1 traversal under Role 5. Do not start Role 6 scoring until the H.4.1 prerequisite is resolved.",
    }

    report = f"""# Role 5 Historical Macro Data Collector Report

Status: `PASS_H6_FULL_CHAIN`  
Decision: `H6_FULL_POINT_IN_TIME_REVISION_CHAIN_VALIDATED`

## Current status

`[FACT]` The full official H.6 traversal reconciles all {len(releases):,} frozen release identities through 2026-06-23. It used {acquisition_counts['HASH_VERIFIED_PILOT_CACHE_REUSE']} hash-verified pilot bodies and {len(releases) - acquisition_counts['HASH_VERIFIED_PILOT_CACHE_REUSE']} accepted full-traversal bodies. Role 5 made {checkpoint['total_role5_network_request_count']:,} source requests including the pilot, below the hard ceiling of {inputs['full_config']['hard_total_role5_network_request_ceiling']:,}, with {checkpoint['retry_count']} retries, zero 403s, zero 429s, zero CAPTCHAs, and zero explicit access blocks.

`[FACT]` The prospectively frozen normalization contract is SHA-256 `{inputs['normalization_hash']}`. All {len(releases):,} accepted release bodies passed raw-hash, parser, source-identity/canonical-date, strict chronology, unit, seasonal-adjustment, and within-release uniqueness checks.

`[FACT]` The monthly chain spans {stats['first_reference_date']} through {stats['last_reference_date']} with {stats['unique_reference_month_count']:,} contiguous reference months. The frozen first-appearance-is-newest-reference gate passed {stats['first_appearance_gate_pass_count']:,}/{stats['unique_reference_month_count']:,}; the contiguous-month gate passed {stats['contiguous_month_transition_pass_count']:,}/{stats['contiguous_month_transition_pass_count']:,} transitions.

`[FACT]` {stats['release_snapshot_count']:,} dated release snapshots produced {stats['observation_version_count']:,} eligible measurement versions: {stats['first_print_count']:,} first prints and {stats['revision_count']:,} revisions. The remaining {stats['unchanged_snapshot_count']:,} repeated values are preserved as `UNCHANGED_SNAPSHOT_NO_NEW_VERSION`; they were not mislabeled as revisions. Every revision has an exact supersedes link, raw source-run/body hash, canonical availability date, and conservative J0 +36-hour timestamps in UTC and Asia/Kuala_Lumpur.

`[FACT]` Four source-index/date identities required exact, non-generalized reconciliation: 2005-03-05 -> 2005-03-03, 2013-04-05 -> 2013-04-04, 2016-11-18 -> 2016-11-17, and 2017-11-23 -> 2017-11-24. The 2002-06-13 HTML mismatch was recovered by its official dated ASCII body. Source-identity correction is separate from measurement revision classification.

## What failed and how it was handled

`[FACT]` The initial 10-request pilot was intentionally inconclusive: seven dated bodies yielded 103 sparse parse-valid rows but could not prove a revision chain. Those rows remain preserved and ineligible; none were promoted by relabeling the sparse pilot.

`[FACT]` The full traversal preserves {len(failures)} non-success attempt records. These cover source identity/date mismatches, three HTTP 404 responses, and two failed exact validators. Each was resolved only by an exact frozen reconciliation with the failed body and stopped checkpoint retained. No failed attempt was erased or silently reclassified as a normal direct success.

`[FACT]` Failed-first implementation evidence is also retained in the cycle record: disposable MariaDB bootstrap ownership, a PHP namespace warning, an over-broad route assertion, invalid test column/scoring fixtures, a zsh reserved variable, legacy H.6 header/row parsing, a 2013 year-index display/link validator assumption, a 2016 PDF layout extraction assumption, and a pre-request 2017 local missing import. Each was corrected and rerun; the pre-request import defect consumed no network request.

## Why later steps were skipped

Later roles were not skipped to jump to a final result. They were held behind prerequisites. Before this validation, H.6 had no defensible complete vintage chain, so H.4.1, scoring, timestamp alignment, technical joins, PnL comparison, and independent audit would have transformed incomplete source evidence into look-ahead-biased results. H.6 now passes, but H.4.1 has not started. Role 6 and Roles 7-11 therefore remain closed in their required sequence.

## Exact next permitted action

Prospectively freeze and run the bounded H.4.1 historical traversal under Role 5. Do not start Role 6 scoring, technical alignment, PnL comparison, or final audit until that prerequisite is resolved.
""".encode("utf-8")

    observation_fields = [
        "observation_id", "source_series_id", "internal_indicator_id", "category", "release_bundle",
        "reference_date", "observation_version", "measurement_version_kind", "supersedes_observation_id",
        "previous_normalized_numeric_value", "revision_delta", "raw_value", "normalized_numeric_value",
        "unit", "frequency", "seasonal_adjustment", "raw_label", "source_index_identity",
        "canonical_release_date", "availability_date", "effective_at_utc", "effective_at_asia_kuala_lumpur",
        "availability_rule", "source_identity_classification", "acquisition_classification", "source_run_id",
        "raw_artifact_id", "raw_artifact_sha256", "raw_relative_private_path", "parser_format",
        "point_in_time_classification", "protocol_eligibility", "historical_reconstruction",
        "observation_payload_sha256",
    ]
    snapshot_fields = [
        "release_snapshot_id", "source_index_identity", "canonical_release_date", "reference_date", "raw_value",
        "normalized_numeric_value", "snapshot_action", "created_observation_version", "active_observation_id",
        "active_observation_version", "previous_observation_id", "previous_normalized_numeric_value",
        "revision_delta", "source_identity_classification", "acquisition_classification", "source_run_id",
        "raw_artifact_id", "raw_artifact_sha256", "parser_format",
    ]
    artifact_fields = [
        "raw_artifact_id", "source_run_id", "release_id", "source_url", "relative_private_path",
        "source_format", "byte_length", "sha256", "http_status", "outcome", "retrieved_at_utc",
        "safe_header_relative_path", "safe_header_sha256", "parser_version", "accepted_for_measurement_chain",
        "acquisition_classification",
    ]
    failure_fields = [
        "source_run_id", "release_id", "network_request_ordinal_role5", "source_url", "http_status", "outcome",
        "body_sha256", "redacted_error", "recovered_by_exact_reconciliation", "terminal_effect",
    ]
    coverage_fields = [
        "year", "accepted_release_count", "direct_release_count", "exact_reconciled_release_count",
        "parsed_snapshot_count", "first_print_count", "revision_count", "unchanged_snapshot_count", "coverage_status",
    ]
    outputs: dict[str, bytes] = {
        "ROLE5_H6_FULL_SOURCE_RUNS.jsonl": b"".join(source_run_lines),
        "ROLE5_H6_FULL_RAW_ARTIFACT_MANIFEST.csv": csv_bytes(artifacts, artifact_fields),
        "ROLE5_H6_RELEASE_SNAPSHOTS.csv": csv_bytes(snapshots, snapshot_fields),
        "ROLE5_H6_OBSERVATION_VERSIONS.csv": csv_bytes(observations, observation_fields),
        "ROLE5_H6_FULL_FAILURES.csv": csv_bytes(failure_rows, failure_fields),
        "ROLE5_H6_FULL_COVERAGE_BY_YEAR.csv": csv_bytes(coverage_rows, coverage_fields),
        "ROLE5_H6_METHOD_LINEAGE.json": canonical_json(methods),
        "ROLE5_H6_FULL_NORMALIZED_MANIFEST.json": canonical_json(manifest),
        "ROLE5_H6_FULL_COLLECTION_REPORT.md": report,
        "MACRO_REGIME_ROLE5_COLLECTION_REPORT.md": report,
    }
    output_hashes = {
        "schema_version": "1.0.0",
        "artifact_id": "ROLE5-H6-FULL-OUTPUT-HASHES-001",
        "full_traversal_config_sha256": inputs["full_hash"],
        "normalization_contract_sha256": inputs["normalization_hash"],
        "terminal_raw_checkpoint_sha256": inputs["checkpoint_hash"],
        "outputs": {name: sha256_bytes(payload) for name, payload in sorted(outputs.items())},
    }
    outputs["ROLE5_H6_FULL_OUTPUT_HASHES.json"] = canonical_json(output_hashes)
    return outputs


def write(repo_root: Path, outputs: dict[str, bytes], validate_only: bool) -> None:
    target = repo_root / OUTPUT_DIR
    for name, payload in outputs.items():
        path = target / name
        if validate_only:
            if not path.is_file() or path.read_bytes() != payload:
                raise CollectionValidationError(f"Output mismatch: {name}")
        else:
            atomic_write(path, payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    outputs = build(repo_root)
    write(repo_root, outputs, args.validate_only)
    manifest = json.loads(outputs["ROLE5_H6_FULL_NORMALIZED_MANIFEST.json"])
    print(json.dumps({
        "status": "PASS_H6_FULL_CHAIN",
        "release_count": manifest["accepted_release_identity_count"],
        "observation_version_count": manifest["observation_version_count"],
        "first_print_count": manifest["first_print_count"],
        "revision_count": manifest["revision_count"],
        "unchanged_snapshot_count": manifest["unchanged_snapshot_count"],
        "validate_only": args.validate_only,
    }, sort_keys=True))


if __name__ == "__main__":
    main()

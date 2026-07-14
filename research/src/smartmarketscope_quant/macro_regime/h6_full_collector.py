from __future__ import annotations

import argparse
import fcntl
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

from .historical_collector import CollectionValidationError, parse_release, sha256_bytes


CONFIG_PATH = Path("research/config/macro_regime_h6_full_traversal.json")
CONFIG_HASH_PATH = Path("research/config/macro_regime_h6_full_traversal.sha256")
FALLBACK_CONFIG_PATH = Path("research/config/macro_regime_h6_source_identity_fallback_v1.json")
FALLBACK_HASH_PATH = Path("research/config/macro_regime_h6_source_identity_fallback_v1.sha256")
ALIAS_CONFIG_PATH = Path("research/config/macro_regime_h6_archive_alias_20050305.json")
ALIAS_HASH_PATH = Path("research/config/macro_regime_h6_archive_alias_20050305.sha256")
CORRECTION_CONFIG_PATH = Path("research/config/macro_regime_h6_json_identity_correction_20130405.json")
CORRECTION_HASH_PATH = Path("research/config/macro_regime_h6_json_identity_correction_20130405.sha256")
YEAR_INDEX_PARSER_CONFIG_PATH = Path("research/config/macro_regime_h6_2013_year_index_parser_reconciliation.json")
YEAR_INDEX_PARSER_HASH_PATH = Path("research/config/macro_regime_h6_2013_year_index_parser_reconciliation.sha256")
YEAR_INDEX_VALIDATOR_V2_PATH = Path("research/config/macro_regime_h6_2013_year_index_validator_amendment_v2.json")
YEAR_INDEX_VALIDATOR_V2_HASH_PATH = Path("research/config/macro_regime_h6_2013_year_index_validator_amendment_v2.sha256")
PDF_CONFIG_PATH = Path("research/config/macro_regime_h6_pdf_corroboration_20161118.json")
PDF_HASH_PATH = Path("research/config/macro_regime_h6_pdf_corroboration_20161118.sha256")
CACHED_PDF_CONFIG_PATH = Path("research/config/macro_regime_h6_cached_pdf_validator_amendment_20161118.json")
CACHED_PDF_HASH_PATH = Path("research/config/macro_regime_h6_cached_pdf_validator_amendment_20161118.sha256")
PDF_2017_CONFIG_PATH = Path("research/config/macro_regime_h6_pdf_corroboration_20171123.json")
PDF_2017_HASH_PATH = Path("research/config/macro_regime_h6_pdf_corroboration_20171123.sha256")
PILOT_CONFIG_PATH = Path("research/config/macro_regime_h6_pilot.json")
CHECKPOINT_NAME = "checkpoint.json"
SAFE_HEADER_NAMES = {
    "accept-ranges", "age", "cache-control", "cf-cache-status", "content-encoding",
    "content-length", "content-type", "date", "etag", "expires", "last-modified",
    "location", "retry-after", "server", "strict-transport-security", "vary",
    "x-content-type-options", "x-frame-options",
}


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


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


def config_hash(repo_root: Path) -> str:
    raw = (repo_root / CONFIG_PATH).read_bytes()
    actual = sha256_bytes(raw)
    expected = (repo_root / CONFIG_HASH_PATH).read_text(encoding="ascii").split()[0]
    if actual != expected:
        raise CollectionValidationError(f"Frozen full traversal config hash mismatch: {actual}")
    return actual


def validate_url(url: str, config: dict[str, object], allow_ascii_fallback: bool = False) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != config["official_scheme"]
        or parsed.hostname != config["official_host"]
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"/releases/h6/\d{8}/(?:h6\.txt)?" if allow_ascii_fallback else r"/releases/h6/\d{8}/", parsed.path)
    ):
        raise CollectionValidationError(f"URL outside frozen H6 route: {url}")


def release_identities(raw: bytes, config: dict[str, object]) -> list[str]:
    payload = json.loads(raw)
    values = {
        value[:8]
        for year in payload
        for month in year["Months"]
        for value in month["Dates"]
        if "20000101" <= value[:8] <= str(config["cutoff_release_date"]).replace("-", "")
    }
    ordered = sorted(values)
    if len(ordered) != config["expected_dated_release_identities"]:
        raise CollectionValidationError(f"Official release identity count changed: {len(ordered)}")
    return ordered


def pilot_cache(config: dict[str, object], pilot: dict[str, object], raw_root: Path) -> dict[str, dict[str, object]]:
    cache: dict[str, dict[str, object]] = {}
    for entry in pilot["request_ledger"]:
        if entry["kind"] != "PILOT_RELEASE":
            continue
        release_id = re.search(r"/(\d{8})/", entry["url"]).group(1)
        path = raw_root / f"vintage_year={release_id[:4]}" / f"source_run={entry['run_id']}" / entry["body_name"]
        raw = path.read_bytes()
        parsed_release, parser_format, _ = parse_release(raw)
        if parsed_release.replace("-", "") != release_id:
            raise CollectionValidationError(f"Pilot cache release mismatch: {release_id}")
        cache[release_id] = {
            "source_run_id": entry["run_id"], "path": str(path), "sha256": sha256_bytes(raw),
            "byte_length": len(raw), "parser_format": parser_format,
        }
    if len(cache) != config["cached_pilot_release_identities"]:
        raise CollectionValidationError("Frozen pilot cache count mismatch")
    return cache


def safe_headers(raw: bytes) -> tuple[bytes, dict[str, str]]:
    text = raw.decode("iso-8859-1", errors="replace")
    lines = text.replace("\r", "").splitlines()
    selected: list[str] = []
    values: dict[str, str] = {}
    if lines and lines[0].startswith("HTTP/"):
        selected.append(lines[0])
    for line in lines[1:]:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        key = name.lower().strip()
        if key in SAFE_HEADER_NAMES:
            clean = re.sub(r"\s+", " ", value).strip()
            selected.append(f"{name.strip()}: {clean}")
            values[key] = clean
    return ("\n".join(selected) + "\n").encode("utf-8"), values


def retry_delay(headers: dict[str, str], config: dict[str, object]) -> int:
    retry_after = headers.get("retry-after")
    if retry_after:
        if retry_after.isdigit():
            return max(0, int(retry_after))
        try:
            target = parsedate_to_datetime(retry_after)
            return max(0, int((target - datetime.now(timezone.utc)).total_seconds()))
        except (TypeError, ValueError, OverflowError):
            pass
    return int(config["retry_policy"]["fallback_backoff_seconds"])


def classify(status: int, body: bytes, attempt: int, config: dict[str, object]) -> str:
    lowered = body[:2_000_000].lower()
    if b"captcha" in lowered or b"cf-chl-captcha" in lowered:
        return "STOP_CAPTCHA"
    if b"automated access" in lowered and (b"blocked" in lowered or b"denied" in lowered):
        return "STOP_EXPLICIT_AUTOMATED_ACCESS_BLOCK"
    if status == 200:
        return "SUCCESS"
    if status == 403:
        return "STOP_HTTP_403"
    if status in config["retry_policy"]["retryable_http_statuses"]:
        return "RETRY" if attempt == 1 else "STOP_RETRY_EXHAUSTED"
    if 300 <= status <= 399:
        return "STOP_REDIRECT"
    return "STOP_HTTP_ERROR"


def quarantine_temporary_orphans(namespace: Path) -> list[str]:
    quarantined: list[str] = []
    quarantine = namespace / "orphan_quarantine"
    for path in sorted(namespace.glob(".*.tmp")) if namespace.exists() else []:
        quarantine.mkdir(parents=True, exist_ok=True)
        target = quarantine / f"{path.name}.{int(time.time())}"
        os.replace(path, target)
        quarantined.append(str(target.relative_to(namespace)))
    return quarantined


@contextmanager
def collection_lock(namespace: Path):
    namespace.mkdir(parents=True, exist_ok=True)
    lock_path = namespace / ".collector.lock"
    with lock_path.open("a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CollectionValidationError("Another full H6 collector owns the lock") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def initial_checkpoint(config: dict[str, object], config_sha256: str, identities: list[str], cache: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "1.0.0", "artifact_id": "ROLE5-H6-FULL-CHECKPOINT-001",
        "request_id": config["request_id"], "program_id": config["program_id"],
        "config_sha256": config_sha256, "status": "IN_PROGRESS",
        "governance_decision": config["governance_decision"],
        "identity_count": len(identities), "pilot_network_request_count": config["pilot_request_count_frozen"],
        "new_network_attempt_count": 0, "total_role5_network_request_count": config["pilot_request_count_frozen"],
        "cache_reuse_count": 0, "successful_new_body_count": 0, "retry_count": 0,
        "completed_release_ids": [], "failed_release_id": None, "failure_code": None,
        "last_completed_release_id": None, "last_updated_at_utc": None,
        "quarantined_orphans": [], "cached_pilot_release_ids": sorted(cache),
    }


def verify_completed(namespace: Path, checkpoint: dict[str, object]) -> None:
    for release_id in checkpoint["completed_release_ids"]:
        if release_id in checkpoint["cached_pilot_release_ids"]:
            continue
        if release_id in checkpoint.get("alias_reconciled_release_ids", []):
            reconciliation = namespace / "alias_reconciliations" / f"source_index_identity={release_id}" / "reconciliation.json"
            evidence = json.loads(reconciliation.read_text(encoding="ascii"))
            if evidence["classification"] != "OFFICIAL_ARCHIVE_ALIAS_RECONCILED":
                raise CollectionValidationError(f"Alias reconciliation invalid: {release_id}")
            continue
        if release_id in checkpoint.get("identity_corrected_release_ids", []):
            reconciliation = namespace / "identity_corrections" / f"json_identity={release_id[:4]}-{release_id[4:6]}-{release_id[6:]}" / "reconciliation.json"
            evidence = json.loads(reconciliation.read_text(encoding="ascii"))
            if evidence["classification"] != "OFFICIAL_RELEASEDATES_JSON_IDENTITY_CORRECTED_BY_OFFICIAL_YEAR_INDEX":
                raise CollectionValidationError(f"Identity correction invalid: {release_id}")
            continue
        if release_id in checkpoint.get("directory_alias_release_ids", []):
            reconciliation = namespace / "pdf_corroborations" / f"source_index_identity={release_id[:4]}-{release_id[4:6]}-{release_id[6:]}" / "reconciliation.json"
            evidence = json.loads(reconciliation.read_text(encoding="ascii"))
            if evidence["classification"] not in {
                "OFFICIAL_ARCHIVE_DIRECTORY_DATE_BODY_DATE_DIVERGENCE",
                "OFFICIAL_FEDERAL_HOLIDAY_RELEASE_SHIFT_DIRECTORY_DATE_DIVERGENCE",
            }:
                raise CollectionValidationError(f"PDF-corroborated directory alias invalid: {release_id}")
            continue
        candidates = sorted((namespace / f"release_date={release_id[:4]}-{release_id[4:6]}-{release_id[6:]}").glob("source_run=*/attempt.json"))
        successes = []
        for candidate in candidates:
            attempt = json.loads(candidate.read_text(encoding="ascii"))
            if attempt["outcome"] == "SUCCESS":
                body = candidate.with_name(attempt.get("body_filename", "release.html"))
                if body.is_file() and sha256_bytes(body.read_bytes()) == attempt["body_sha256"]:
                    successes.append(candidate)
        if len(successes) != 1:
            raise CollectionValidationError(f"Completed release cache invalid: {release_id}")


def curl_request(url: str, header_path: Path, body_path: Path, config: dict[str, object]) -> tuple[int, str, str, int]:
    command = [
        "/usr/bin/curl", "--silent", "--show-error", "--proto", "=https",
        "--connect-timeout", str(config["connect_timeout_seconds"]),
        "--max-time", str(config["request_timeout_seconds"]),
        "--max-redirs", "0", "--user-agent", "SmartMarketScope-Research-H6/1.0",
        "--dump-header", str(header_path), "--output", str(body_path),
        "--write-out", "%{http_code}\n%{url_effective}\n%{content_type}\n", url,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    parts = result.stdout.splitlines()
    status = int(parts[0]) if parts and parts[0].isdigit() else 0
    effective_url = parts[1] if len(parts) > 1 else url
    content_type = parts[2] if len(parts) > 2 else ""
    return status, effective_url, content_type, result.returncode


def correction_request(
    namespace: Path,
    relative_parent: Path,
    run_id: str,
    ordinal: int,
    release_id: str,
    url: str,
    body_name: str,
    source_format: str,
    config: dict[str, object],
    config_sha256: str,
    success_outcome: str,
    validator,
) -> tuple[dict[str, object], bytes]:
    parent = namespace / relative_parent
    final_dir = parent / f"source_run={run_id}"
    temporary_dir = parent / f".{run_id}.tmp"
    if final_dir.exists() or temporary_dir.exists():
        raise CollectionValidationError(f"Immutable correction source-run path collision: {run_id}")
    temporary_dir.mkdir(parents=True)
    raw_headers_path = temporary_dir / ".raw_headers.tmp"
    body_path = temporary_dir / body_name
    started = datetime.now(timezone.utc)
    status, effective_url, content_type, curl_exit = curl_request(url, raw_headers_path, body_path, config)
    body = body_path.read_bytes() if body_path.exists() else b""
    header_raw = raw_headers_path.read_bytes() if raw_headers_path.exists() else b""
    redacted_headers, _ = safe_headers(header_raw)
    raw_headers_path.unlink(missing_ok=True)
    outcome = success_outcome
    redacted_error = None
    validation = {}
    if effective_url != url:
        outcome = "STOP_CORRECTION_REDIRECT"
    elif status != 200:
        outcome = f"STOP_CORRECTION_HTTP_{status}"
    else:
        access_outcome = classify(status, body, 2, config)
        if access_outcome != "SUCCESS":
            outcome = f"STOP_CORRECTION_{access_outcome}"
        else:
            try:
                validation = validator(body)
            except Exception as exc:
                outcome = "STOP_CORRECTION_VALIDATION_FAILED"
                redacted_error = f"{type(exc).__name__}: {exc}"[:500]
    if outcome == success_outcome and source_format == "PDF" and "application/pdf" not in content_type.lower():
        outcome = "STOP_CORRECTION_PDF_CONTENT_TYPE_INVALID"
    completed_at = datetime.now(timezone.utc)
    record = {
        "schema_version": "1.0.0", "source_run_id": run_id, "request_id": config["request_id"],
        "config_sha256": config_sha256, "network_request_ordinal_role5": ordinal,
        "release_id": release_id, "source_url": url, "effective_url": effective_url,
        "attempt_number": 1, "started_at_utc": started.isoformat().replace("+00:00", "Z"),
        "completed_at_utc": completed_at.isoformat().replace("+00:00", "Z"),
        "http_status": status, "curl_exit_code": curl_exit, "content_type": content_type,
        "outcome": outcome, "body_byte_length": len(body), "body_sha256": sha256_bytes(body),
        "body_filename": body_name, "source_format": source_format,
        "safe_header_byte_length": len(redacted_headers), "safe_header_sha256": sha256_bytes(redacted_headers),
        "parser_version": config["parser_version"], "redacted_error": redacted_error,
        "contains_credentials": False, "raw_unredacted_headers_preserved": False,
        "validation": validation,
    }
    atomic_write(temporary_dir / "safe_headers.txt", redacted_headers)
    atomic_write(temporary_dir / "attempt.json", canonical_json(record))
    os.replace(temporary_dir, final_dir)
    return record, body


def collect(repo_root: Path) -> dict[str, object]:
    config_sha256 = config_hash(repo_root)
    config = json.loads((repo_root / CONFIG_PATH).read_text(encoding="ascii"))
    fallback = json.loads((repo_root / FALLBACK_CONFIG_PATH).read_text(encoding="ascii"))
    fallback_sha256 = sha256_bytes((repo_root / FALLBACK_CONFIG_PATH).read_bytes())
    expected_fallback_sha256 = (repo_root / FALLBACK_HASH_PATH).read_text(encoding="ascii").split()[0]
    if fallback_sha256 != expected_fallback_sha256 or fallback["parent_config_sha256"] != config_sha256:
        raise CollectionValidationError("Frozen source-identity fallback hash/lineage mismatch")
    alias = json.loads((repo_root / ALIAS_CONFIG_PATH).read_text(encoding="ascii"))
    alias_sha256 = sha256_bytes((repo_root / ALIAS_CONFIG_PATH).read_bytes())
    expected_alias_sha256 = (repo_root / ALIAS_HASH_PATH).read_text(encoding="ascii").split()[0]
    if alias_sha256 != expected_alias_sha256 or alias["parent_config_sha256"] != config_sha256 or alias["fallback_config_sha256"] != fallback_sha256:
        raise CollectionValidationError("Frozen exact archive alias hash/lineage mismatch")
    correction = json.loads((repo_root / CORRECTION_CONFIG_PATH).read_text(encoding="ascii"))
    correction_sha256 = sha256_bytes((repo_root / CORRECTION_CONFIG_PATH).read_bytes())
    expected_correction_sha256 = (repo_root / CORRECTION_HASH_PATH).read_text(encoding="ascii").split()[0]
    if (
        correction_sha256 != expected_correction_sha256
        or correction["parent_config_sha256"] != config_sha256
        or correction["fallback_config_sha256"] != fallback_sha256
        or correction["archive_alias_config_sha256"] != alias_sha256
    ):
        raise CollectionValidationError("Frozen JSON identity correction hash/lineage mismatch")
    year_parser = json.loads((repo_root / YEAR_INDEX_PARSER_CONFIG_PATH).read_text(encoding="ascii"))
    year_parser_sha256 = sha256_bytes((repo_root / YEAR_INDEX_PARSER_CONFIG_PATH).read_bytes())
    expected_year_parser_sha256 = (repo_root / YEAR_INDEX_PARSER_HASH_PATH).read_text(encoding="ascii").split()[0]
    if year_parser_sha256 != expected_year_parser_sha256 or year_parser["identity_correction_config_sha256"] != correction_sha256:
        raise CollectionValidationError("Frozen year-index parser reconciliation hash/lineage mismatch")
    year_validator_v2 = json.loads((repo_root / YEAR_INDEX_VALIDATOR_V2_PATH).read_text(encoding="ascii"))
    year_validator_v2_sha256 = sha256_bytes((repo_root / YEAR_INDEX_VALIDATOR_V2_PATH).read_bytes())
    expected_year_validator_v2_sha256 = (repo_root / YEAR_INDEX_VALIDATOR_V2_HASH_PATH).read_text(encoding="ascii").split()[0]
    if (
        year_validator_v2_sha256 != expected_year_validator_v2_sha256
        or year_validator_v2["identity_correction_config_sha256"] != correction_sha256
        or year_validator_v2["superseded_incomplete_parser_reconciliation_sha256"] != year_parser_sha256
        or year_validator_v2["prior_validator_stop_checkpoint_sha256"] != year_parser["prior_validator_stop_checkpoint_sha256"]
    ):
        raise CollectionValidationError("Frozen year-index validator V2 hash/lineage mismatch")
    pdf_config = json.loads((repo_root / PDF_CONFIG_PATH).read_text(encoding="ascii"))
    pdf_config_sha256 = sha256_bytes((repo_root / PDF_CONFIG_PATH).read_bytes())
    expected_pdf_config_sha256 = (repo_root / PDF_HASH_PATH).read_text(encoding="ascii").split()[0]
    validator_path = repo_root / "research/src/smartmarketscope_quant/macro_regime/h6_pdf_validator.py"
    if (
        pdf_config_sha256 != expected_pdf_config_sha256
        or pdf_config["parent_full_config_sha256"] != config_sha256
        or pdf_config["parent_fallback_config_sha256"] != fallback_sha256
        or pdf_config["archive_alias_config_sha256"] != alias_sha256
        or pdf_config["identity_correction_config_sha256"] != correction_sha256
        or pdf_config["year_index_validator_v2_sha256"] != year_validator_v2_sha256
        or pdf_config["pdf_validator_sha256"] != sha256_bytes(validator_path.read_bytes())
    ):
        raise CollectionValidationError("Frozen PDF corroboration hash/lineage mismatch")
    cached_pdf = json.loads((repo_root / CACHED_PDF_CONFIG_PATH).read_text(encoding="ascii"))
    cached_pdf_sha256 = sha256_bytes((repo_root / CACHED_PDF_CONFIG_PATH).read_bytes())
    expected_cached_pdf_sha256 = (repo_root / CACHED_PDF_HASH_PATH).read_text(encoding="ascii").split()[0]
    exact_validator_path = repo_root / "research/src/smartmarketscope_quant/macro_regime/h6_pdf_validator_exact_20161118.py"
    if (
        cached_pdf_sha256 != expected_cached_pdf_sha256
        or cached_pdf["pdf_corroboration_config_sha256"] != pdf_config_sha256
        or cached_pdf["failed_layout_validator_sha256"] != pdf_config["pdf_validator_sha256"]
        or cached_pdf["exact_validator_sha256"] != sha256_bytes(exact_validator_path.read_bytes())
    ):
        raise CollectionValidationError("Frozen cached-PDF validator amendment hash/lineage mismatch")
    pdf_2017 = json.loads((repo_root / PDF_2017_CONFIG_PATH).read_text(encoding="ascii"))
    pdf_2017_sha256 = sha256_bytes((repo_root / PDF_2017_CONFIG_PATH).read_bytes())
    expected_pdf_2017_sha256 = (repo_root / PDF_2017_HASH_PATH).read_text(encoding="ascii").split()[0]
    pdf_2017_validator_path = repo_root / "research/src/smartmarketscope_quant/macro_regime/h6_pdf_validator_exact_20171123.py"
    if (
        pdf_2017_sha256 != expected_pdf_2017_sha256
        or pdf_2017["parent_full_config_sha256"] != config_sha256
        or pdf_2017["parent_fallback_config_sha256"] != fallback_sha256
        or pdf_2017["archive_alias_config_sha256"] != alias_sha256
        or pdf_2017["identity_correction_config_sha256"] != correction_sha256
        or pdf_2017["pdf_2016_config_sha256"] != pdf_config_sha256
        or pdf_2017["pdf_2016_cached_validator_amendment_sha256"] != cached_pdf_sha256
        or pdf_2017["pdf_validator_sha256"] != sha256_bytes(pdf_2017_validator_path.read_bytes())
    ):
        raise CollectionValidationError("Frozen 2017 PDF corroboration hash/lineage mismatch")
    pilot = json.loads((repo_root / PILOT_CONFIG_PATH).read_text(encoding="ascii"))
    raw_root = Path(config["storage_policy"]["private_raw_root"])
    namespace = raw_root / config["storage_policy"]["full_traversal_namespace"]
    release_index = raw_root / "vintage_year=2026" / "source_run=role5-release-dates-0003" / "releaseDates.json"
    release_index_raw = release_index.read_bytes()
    if sha256_bytes(release_index_raw) != config["release_dates_raw_sha256"]:
        raise CollectionValidationError("Frozen releaseDates cache hash mismatch")
    identities = release_identities(release_index_raw, config)
    cache = pilot_cache(config, pilot, raw_root)

    with collection_lock(namespace):
        checkpoint_path = namespace / CHECKPOINT_NAME
        if checkpoint_path.exists():
            checkpoint = json.loads(checkpoint_path.read_text(encoding="ascii"))
            if checkpoint["config_sha256"] != config_sha256:
                raise CollectionValidationError("Checkpoint belongs to another config")
        else:
            checkpoint = initial_checkpoint(config, config_sha256, identities, cache)
        if (
            checkpoint["status"] == "STOPPED"
            and checkpoint["failure_code"] == alias["prior_terminal_failure_code"]
            and checkpoint["failed_release_id"] == alias["source_index_identity"]
        ):
            prior_checkpoint_raw = checkpoint_path.read_bytes()
            prior_checkpoint_sha256 = sha256_bytes(prior_checkpoint_raw)
            if prior_checkpoint_sha256 != alias["prior_terminal_checkpoint_sha256"]:
                raise CollectionValidationError("Exact archive alias prior stop checkpoint mismatch")
            source_identity = alias["source_index_identity"]
            if source_identity not in identities or alias["canonical_body_release_date"].replace("-", "") in identities:
                raise CollectionValidationError("Exact archive alias index proof failed")
            position = identities.index(source_identity)
            if identities[position - 1] != alias["preceding_source_index_identity"] or identities[position + 1] != alias["following_source_index_identity"]:
                raise CollectionValidationError("Exact archive alias neighbor proof failed")
            release_dir = namespace / "release_date=2005-03-05"
            source_evidence = []
            for source_run_id, expected_body_sha256, expected_format in (
                (alias["html_source_run_id"], alias["html_body_sha256"], "HTML"),
                (alias["ascii_source_run_id"], alias["ascii_body_sha256"], "ASCII"),
            ):
                attempt_path = release_dir / f"source_run={source_run_id}" / "attempt.json"
                attempt = json.loads(attempt_path.read_text(encoding="ascii"))
                body_path = attempt_path.with_name(attempt["body_filename"])
                body = body_path.read_bytes()
                if sha256_bytes(body) != expected_body_sha256 or attempt["source_format"] != expected_format:
                    raise CollectionValidationError("Exact archive alias body proof failed")
                parser_input = b"<pre>" + body + b"</pre>" if expected_format == "ASCII" else body
                declared_date, parser_format, values = parse_release(parser_input)
                if declared_date != alias["canonical_body_release_date"]:
                    raise CollectionValidationError("Exact archive alias canonical date proof failed")
                source_evidence.append({
                    "source_run_id": source_run_id, "source_format": expected_format,
                    "body_sha256": expected_body_sha256, "declared_release_date": declared_date,
                    "parser_format": parser_format, "parsed_table1_m2_row_count": len(values),
                })
            reconciliation = {
                "schema_version": "1.0.0", "artifact_id": "ROLE5-H6-ALIAS-RECONCILIATION-20050305-001",
                "classification": alias["classification"], "alias_config_sha256": alias_sha256,
                "parent_stopped_checkpoint_sha256": prior_checkpoint_sha256,
                "source_index_identity": source_identity, "canonical_body_release_date": alias["canonical_body_release_date"],
                "availability_date_for_j0": alias["availability_date_for_j0"],
                "source_index_contains_canonical_body_date_identity": False,
                "duplicate_canonical_release_in_index": False, "source_evidence": source_evidence,
            }
            reconciliation_path = namespace / "alias_reconciliations" / f"source_index_identity={source_identity}" / "reconciliation.json"
            atomic_write(reconciliation_path, canonical_json(reconciliation))
            checkpoint["completed_release_ids"].append(source_identity)
            checkpoint["last_completed_release_id"] = source_identity
            checkpoint["alias_reconciled_release_ids"] = [source_identity]
            checkpoint["archive_alias_count"] = 1
            checkpoint["alias_config_sha256"] = alias_sha256
            checkpoint["parent_stopped_checkpoint_sha256"] = prior_checkpoint_sha256
            checkpoint["active_child_run_id"] = alias["resume_child_run_id"]
            checkpoint["status"] = "IN_PROGRESS"
            checkpoint["failed_release_id"] = None
            checkpoint["failure_code"] = None
            checkpoint["fallback_config_sha256"] = fallback_sha256
            checkpoint["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            atomic_write(checkpoint_path, canonical_json(checkpoint))
        elif (
            checkpoint["status"] == "STOPPED"
            and checkpoint["failure_code"] == correction["prior_terminal_failure_code"]
            and checkpoint["failed_release_id"] == correction["release_dates_json_identity"]
        ):
            prior_checkpoint_raw = checkpoint_path.read_bytes()
            prior_checkpoint_sha256 = sha256_bytes(prior_checkpoint_raw)
            if prior_checkpoint_sha256 != correction["prior_terminal_checkpoint_sha256"]:
                raise CollectionValidationError("JSON identity correction prior stop checkpoint mismatch")
            json_identity = correction["release_dates_json_identity"]
            canonical_identity = correction["canonical_official_identity"]
            if json_identity not in identities or canonical_identity in identities:
                raise CollectionValidationError("JSON identity correction cached index proof failed")
            position = identities.index(json_identity)
            if identities[position - 1] != correction["preceding_identity"] or identities[position + 1] != correction["following_identity"]:
                raise CollectionValidationError("JSON identity correction neighbor proof failed")
            failed_attempt_path = namespace / "release_date=2013-04-05" / f"source_run={correction['failed_json_identity_source_run_id']}" / "attempt.json"
            failed_attempt = json.loads(failed_attempt_path.read_text(encoding="ascii"))
            failed_body = failed_attempt_path.with_name(failed_attempt["body_filename"]).read_bytes()
            if failed_attempt["http_status"] != 404 or sha256_bytes(failed_body) != correction["failed_json_identity_body_sha256"]:
                raise CollectionValidationError("JSON identity correction failed-parent proof failed")

            def validate_year_index(body: bytes) -> dict[str, object]:
                text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body.decode("utf-8", errors="replace"))))
                for expected in ("March 28, 2013", "April 11, 2013"):
                    if expected not in text:
                        raise CollectionValidationError(f"Official year index missing {expected}")
                if not re.search(r"April\s+0?4,\s+2013", text) or re.search(r"April\s+0?5,\s+2013", text):
                    raise CollectionValidationError("Official year index April correction proof failed")
                return {"lists_march_28": True, "lists_april_04": True, "lists_april_05": False, "lists_april_11": True}

            def validate_canonical_body(body: bytes) -> dict[str, object]:
                release, parser_format, values = parse_release(body)
                if release.replace("-", "") != canonical_identity or not values:
                    raise CollectionValidationError("Canonical corrected H6 body identity/parser failed")
                return {"declared_release_date": release, "parser_format": parser_format, "parsed_table1_m2_row_count": len(values)}

            correction_records = []
            for ordinal, relative_parent, run_id, release_id, url, body_name, source_format, success_outcome, validator in (
                (
                    correction["next_network_request_ordinal_year_index"], Path("identity_corrections/json_identity=2013-04-05/year_index"),
                    "role5-h6-correction-0702-year-index", "2013_YEAR_INDEX", correction["official_year_index_url"],
                    "year_index.html", "HTML", "SUCCESS_RECONCILIATION_YEAR_INDEX", validate_year_index,
                ),
                (
                    correction["next_network_request_ordinal_canonical_body"], Path("identity_corrections/json_identity=2013-04-05/canonical_release"),
                    "role5-h6-correction-0703-20130404", canonical_identity, correction["canonical_release_url"],
                    "release.html", "HTML", "SUCCESS_IDENTITY_CORRECTION", validate_canonical_body,
                ),
            ):
                if checkpoint["total_role5_network_request_count"] + 1 != ordinal:
                    raise CollectionValidationError("JSON identity correction request ordinal drift")
                if ordinal > config["hard_total_role5_network_request_ceiling"]:
                    raise CollectionValidationError("JSON identity correction exceeds request ceiling")
                record, _ = correction_request(
                    namespace, relative_parent, run_id, ordinal, release_id, url, body_name, source_format,
                    config, config_sha256, success_outcome, validator,
                )
                checkpoint["new_network_attempt_count"] += 1
                checkpoint["total_role5_network_request_count"] += 1
                checkpoint["last_updated_at_utc"] = record["completed_at_utc"]
                correction_records.append(record)
                atomic_write(checkpoint_path, canonical_json(checkpoint))
                if record["outcome"] != success_outcome:
                    checkpoint.update({"status": "STOPPED", "failed_release_id": json_identity, "failure_code": record["outcome"]})
                    atomic_write(checkpoint_path, canonical_json(checkpoint))
                    print(json.dumps({"status": "STOPPED", "release_id": json_identity, "failure_code": record["outcome"]}), flush=True)
                    return checkpoint
                if ordinal == correction["next_network_request_ordinal_year_index"]:
                    elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(record["started_at_utc"].replace("Z", "+00:00"))).total_seconds()
                    if elapsed < float(config["minimum_pacing_seconds"]):
                        time.sleep(float(config["minimum_pacing_seconds"]) - elapsed)

            reconciliation = {
                "schema_version": "1.0.0", "artifact_id": "ROLE5-H6-JSON-IDENTITY-CORRECTION-20130405-001",
                "classification": correction["classification"], "correction_config_sha256": correction_sha256,
                "parent_stopped_checkpoint_sha256": prior_checkpoint_sha256,
                "release_dates_json_identity": json_identity, "canonical_official_identity": canonical_identity,
                "availability_date_for_j0": correction["availability_date_for_j0"],
                "release_dates_json_contains_canonical_identity": False, "duplicate_canonical_release": False,
                "evidence_source_runs": [record["source_run_id"] for record in correction_records],
                "evidence_body_sha256": [record["body_sha256"] for record in correction_records],
            }
            reconciliation_path = namespace / "identity_corrections" / "json_identity=2013-04-05" / "reconciliation.json"
            atomic_write(reconciliation_path, canonical_json(reconciliation))
            checkpoint["completed_release_ids"].append(json_identity)
            checkpoint["last_completed_release_id"] = json_identity
            checkpoint["identity_corrected_release_ids"] = [json_identity]
            checkpoint["identity_correction_count"] = 1
            checkpoint["identity_correction_config_sha256"] = correction_sha256
            checkpoint["identity_correction_parent_stopped_checkpoint_sha256"] = prior_checkpoint_sha256
            checkpoint["active_child_run_id"] = correction["resume_child_run_id"]
            checkpoint["successful_new_body_count"] += 1
            checkpoint["reconciliation_evidence_body_count"] = 1
            checkpoint["status"] = "IN_PROGRESS"
            checkpoint["failed_release_id"] = None
            checkpoint["failure_code"] = None
            checkpoint["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            atomic_write(checkpoint_path, canonical_json(checkpoint))
        elif (
            checkpoint["status"] == "STOPPED"
            and checkpoint["failure_code"] == "STOP_CORRECTION_VALIDATION_FAILED"
            and checkpoint["failed_release_id"] == correction["release_dates_json_identity"]
        ):
            prior_checkpoint_raw = checkpoint_path.read_bytes()
            prior_checkpoint_sha256 = sha256_bytes(prior_checkpoint_raw)
            if prior_checkpoint_sha256 != year_parser["prior_validator_stop_checkpoint_sha256"]:
                raise CollectionValidationError("Year-index parser reconciliation prior checkpoint mismatch")
            year_attempt_path = namespace / "identity_corrections/json_identity=2013-04-05/year_index/source_run=role5-h6-correction-0702-year-index/attempt.json"
            year_attempt = json.loads(year_attempt_path.read_text(encoding="ascii"))
            year_body = year_attempt_path.with_name(year_attempt["body_filename"]).read_bytes()
            if sha256_bytes(year_body) != year_parser["failed_validator_body_sha256"]:
                raise CollectionValidationError("Year-index parser reconciliation body hash mismatch")
            if sha256_bytes(year_body) != year_validator_v2["request_702_body_sha256"]:
                raise CollectionValidationError("Year-index validator V2 body hash mismatch")
            raw_text = year_body.decode("utf-8", errors="replace")

            def month_row(month: str) -> str:
                match = re.search(rf"<tr>\s*<td\s+class=[\"']month[\"']>{month}</td>(.*?)</tr>", raw_text, re.I | re.S)
                if not match:
                    raise CollectionValidationError(f"Official year index {month} row missing")
                return match.group(1)

            march_row = month_row("March")
            april_row = month_row("April")
            if not re.search(r"href=[\"']20130328/?[\"'][^>]*>\s*28\s*</a>", march_row, re.I):
                raise CollectionValidationError("Official year index March 28 structural proof failed")
            if not re.search(r"href=[\"']20130405/?[\"'][^>]*>\s*04\s*</a>", april_row, re.I):
                raise CollectionValidationError("Official year index April 04 structural proof failed")
            if not re.search(r"href=[\"']20130411/?[\"'][^>]*>\s*11\s*</a>", april_row, re.I):
                raise CollectionValidationError("Official year index April 11 structural proof failed")
            if re.search(r">\s*05\s*</a>", april_row, re.I):
                raise CollectionValidationError("Official year index unexpectedly displays April 05")

            def validate_canonical_body_after_cached_year(body: bytes) -> dict[str, object]:
                release, parser_format, values = parse_release(body)
                if release != correction["canonical_body_required_declared_release_date"] or not values:
                    raise CollectionValidationError("Canonical corrected H6 body identity/parser failed")
                return {"declared_release_date": release, "parser_format": parser_format, "parsed_table1_m2_row_count": len(values)}

            ordinal = year_parser["next_network_request_ordinal"]
            if checkpoint["total_role5_network_request_count"] + 1 != ordinal:
                raise CollectionValidationError("Canonical correction request ordinal drift")
            canonical_record, _ = correction_request(
                namespace, Path("identity_corrections/json_identity=2013-04-05/canonical_release"),
                "role5-h6-correction-0703-20130404", ordinal, correction["canonical_official_identity"],
                correction["canonical_release_url"], "release.html", "HTML", config, config_sha256,
                "SUCCESS_IDENTITY_CORRECTION", validate_canonical_body_after_cached_year,
            )
            checkpoint["new_network_attempt_count"] += 1
            checkpoint["total_role5_network_request_count"] += 1
            checkpoint["last_updated_at_utc"] = canonical_record["completed_at_utc"]
            atomic_write(checkpoint_path, canonical_json(checkpoint))
            if canonical_record["outcome"] != "SUCCESS_IDENTITY_CORRECTION":
                checkpoint.update({"status": "STOPPED", "failed_release_id": correction["release_dates_json_identity"], "failure_code": canonical_record["outcome"]})
                atomic_write(checkpoint_path, canonical_json(checkpoint))
                print(json.dumps({"status": "STOPPED", "release_id": correction["release_dates_json_identity"], "failure_code": canonical_record["outcome"]}), flush=True)
                return checkpoint
            reconciliation = {
                "schema_version": "1.0.0", "artifact_id": "ROLE5-H6-JSON-IDENTITY-CORRECTION-20130405-001",
                "classification": correction["classification"], "correction_config_sha256": correction_sha256,
                "year_index_parser_reconciliation_sha256": year_parser_sha256,
                "year_index_validator_v2_sha256": year_validator_v2_sha256,
                "year_index_classification": year_validator_v2["classification"],
                "parent_http_stop_checkpoint_sha256": correction["prior_terminal_checkpoint_sha256"],
                "parent_validator_stop_checkpoint_sha256": prior_checkpoint_sha256,
                "release_dates_json_identity": correction["release_dates_json_identity"],
                "canonical_official_identity": correction["canonical_official_identity"],
                "availability_date_for_j0": correction["availability_date_for_j0"],
                "year_index_structural_proof": year_parser["required_structural_proof"],
                "evidence_source_runs": [year_attempt["source_run_id"], canonical_record["source_run_id"]],
                "evidence_body_sha256": [year_attempt["body_sha256"], canonical_record["body_sha256"]],
            }
            reconciliation_path = namespace / "identity_corrections/json_identity=2013-04-05/reconciliation.json"
            atomic_write(reconciliation_path, canonical_json(reconciliation))
            json_identity = correction["release_dates_json_identity"]
            checkpoint["completed_release_ids"].append(json_identity)
            checkpoint["last_completed_release_id"] = json_identity
            checkpoint["identity_corrected_release_ids"] = [json_identity]
            checkpoint["identity_correction_count"] = 1
            checkpoint["identity_correction_config_sha256"] = correction_sha256
            checkpoint["year_index_parser_reconciliation_sha256"] = year_parser_sha256
            checkpoint["year_index_validator_v2_sha256"] = year_validator_v2_sha256
            checkpoint["identity_correction_parent_stopped_checkpoint_sha256"] = correction["prior_terminal_checkpoint_sha256"]
            checkpoint["identity_correction_validator_stopped_checkpoint_sha256"] = prior_checkpoint_sha256
            checkpoint["active_child_run_id"] = correction["resume_child_run_id"]
            checkpoint["successful_new_body_count"] += 1
            checkpoint["reconciliation_evidence_body_count"] = checkpoint.get("reconciliation_evidence_body_count", 0) + 1
            checkpoint["status"] = "IN_PROGRESS"
            checkpoint["failed_release_id"] = None
            checkpoint["failure_code"] = None
            checkpoint["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            atomic_write(checkpoint_path, canonical_json(checkpoint))
        elif (
            checkpoint["status"] == "STOPPED"
            and checkpoint["failure_code"] == "STOP_HTTP_ERROR"
            and checkpoint["failed_release_id"] == pdf_config["source_index_identity"]
        ):
            prior_checkpoint_raw = checkpoint_path.read_bytes()
            prior_checkpoint_sha256 = sha256_bytes(prior_checkpoint_raw)
            if prior_checkpoint_sha256 != pdf_config["prior_terminal_checkpoint_sha256"]:
                raise CollectionValidationError("PDF corroboration prior stop checkpoint mismatch")
            source_identity = pdf_config["source_index_identity"]
            canonical_identity = pdf_config["canonical_body_release_date"].replace("-", "")
            if source_identity not in identities or canonical_identity in identities:
                raise CollectionValidationError("PDF corroboration cached index proof failed")
            position = identities.index(source_identity)
            if identities[position - 1] != pdf_config["preceding_source_index_identity"] or identities[position + 1] != pdf_config["following_source_index_identity"]:
                raise CollectionValidationError("PDF corroboration neighbor proof failed")
            release_dir = namespace / "release_date=2016-11-18"
            root_attempt_path = release_dir / f"source_run={pdf_config['root_html_source_run_id']}" / "attempt.json"
            ascii_attempt_path = release_dir / f"source_run={pdf_config['failed_ascii_source_run_id']}" / "attempt.json"
            root_attempt = json.loads(root_attempt_path.read_text(encoding="ascii"))
            ascii_attempt = json.loads(ascii_attempt_path.read_text(encoding="ascii"))
            root_body = root_attempt_path.with_name(root_attempt["body_filename"]).read_bytes()
            ascii_body = ascii_attempt_path.with_name(ascii_attempt["body_filename"]).read_bytes()
            if (
                sha256_bytes(root_attempt_path.read_bytes()) != pdf_config["root_html_attempt_sha256"]
                or sha256_bytes(root_body) != pdf_config["root_html_body_sha256"]
                or sha256_bytes(ascii_attempt_path.read_bytes()) != pdf_config["failed_ascii_attempt_sha256"]
                or sha256_bytes(ascii_body) != pdf_config["failed_ascii_body_sha256"]
                or ascii_attempt["http_status"] != pdf_config["failed_ascii_http_status"]
            ):
                raise CollectionValidationError("PDF corroboration root/ASCII evidence hash failed")
            root_release, root_format, root_values = parse_release(root_body)
            root_text = root_body.decode("utf-8", errors="replace")
            if (
                root_release != pdf_config["canonical_body_release_date"]
                or not root_values
                or "Last update:  November 17, 2016" not in root_text
                or 'href="H6.pdf"' not in root_text
            ):
                raise CollectionValidationError("PDF corroboration root HTML semantic proof failed")

            def validate_pdf(body: bytes) -> dict[str, object]:
                import pypdf
                from .h6_pdf_validator import VALIDATOR_VERSION, validate_h6_pdf
                if pypdf.__version__ != pdf_config["pdf_library_version"] or VALIDATOR_VERSION != pdf_config["pdf_validator_version"]:
                    raise CollectionValidationError("Frozen PDF runtime/library version mismatch")
                return validate_h6_pdf(body, "November 17, 2016")

            ordinal = pdf_config["pdf_network_request_ordinal"]
            if checkpoint["total_role5_network_request_count"] + 1 != ordinal:
                raise CollectionValidationError("PDF corroboration request ordinal drift")
            pdf_record, _ = correction_request(
                namespace, Path("pdf_corroborations/source_index_identity=2016-11-18/pdf"),
                "role5-h6-pdf-0894-20161118", ordinal, source_identity, pdf_config["pdf_url"],
                "H6.pdf", "PDF", config, config_sha256, "SUCCESS_PDF_CORROBORATION", validate_pdf,
            )
            checkpoint["new_network_attempt_count"] += 1
            checkpoint["total_role5_network_request_count"] += 1
            checkpoint["last_updated_at_utc"] = pdf_record["completed_at_utc"]
            atomic_write(checkpoint_path, canonical_json(checkpoint))
            if pdf_record["outcome"] != "SUCCESS_PDF_CORROBORATION":
                checkpoint.update({"status": "STOPPED", "failed_release_id": source_identity, "failure_code": pdf_record["outcome"]})
                atomic_write(checkpoint_path, canonical_json(checkpoint))
                print(json.dumps({"status": "STOPPED", "release_id": source_identity, "failure_code": pdf_record["outcome"]}), flush=True)
                return checkpoint
            reconciliation = {
                "schema_version": "1.0.0", "artifact_id": "ROLE5-H6-PDF-CORROBORATION-20161118-001",
                "classification": pdf_config["classification_if_confirmed"], "pdf_config_sha256": pdf_config_sha256,
                "parent_stopped_checkpoint_sha256": prior_checkpoint_sha256,
                "source_index_identity": source_identity, "canonical_body_release_date": pdf_config["canonical_body_release_date"],
                "availability_date_for_j0": pdf_config["availability_date_for_j0"],
                "source_index_contains_canonical_body_date_identity": False,
                "duplicate_canonical_release_in_index": False,
                "root_html_source_run_id": root_attempt["source_run_id"], "root_html_body_sha256": root_attempt["body_sha256"],
                "failed_ascii_source_run_id": ascii_attempt["source_run_id"], "failed_ascii_body_sha256": ascii_attempt["body_sha256"],
                "pdf_source_run_id": pdf_record["source_run_id"], "pdf_body_sha256": pdf_record["body_sha256"],
                "pdf_validation": pdf_record["validation"], "root_parser_format": root_format,
                "root_parsed_table1_m2_row_count": len(root_values),
            }
            reconciliation_path = namespace / "pdf_corroborations/source_index_identity=2016-11-18/reconciliation.json"
            atomic_write(reconciliation_path, canonical_json(reconciliation))
            checkpoint["completed_release_ids"].append(source_identity)
            checkpoint["last_completed_release_id"] = source_identity
            checkpoint["directory_alias_release_ids"] = [source_identity]
            checkpoint["directory_alias_count"] = 1
            checkpoint["pdf_corroboration_config_sha256"] = pdf_config_sha256
            checkpoint["pdf_corroboration_parent_stopped_checkpoint_sha256"] = prior_checkpoint_sha256
            checkpoint["active_child_run_id"] = pdf_config["resume_child_run_id"]
            checkpoint["successful_new_body_count"] += 1
            checkpoint["reconciliation_evidence_body_count"] = checkpoint.get("reconciliation_evidence_body_count", 0) + 1
            checkpoint["status"] = "IN_PROGRESS"
            checkpoint["failed_release_id"] = None
            checkpoint["failure_code"] = None
            checkpoint["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            atomic_write(checkpoint_path, canonical_json(checkpoint))
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(pdf_record["started_at_utc"].replace("Z", "+00:00"))).total_seconds()
            if elapsed < float(config["minimum_pacing_seconds"]):
                time.sleep(float(config["minimum_pacing_seconds"]) - elapsed)
        elif (
            checkpoint["status"] == "STOPPED"
            and checkpoint["failure_code"] == cached_pdf["failed_layout_validator_outcome"]
            and checkpoint["failed_release_id"] == cached_pdf["source_index_identity"]
        ):
            prior_checkpoint_raw = checkpoint_path.read_bytes()
            prior_checkpoint_sha256 = sha256_bytes(prior_checkpoint_raw)
            if prior_checkpoint_sha256 != cached_pdf["prior_pdf_validator_stop_checkpoint_sha256"]:
                raise CollectionValidationError("Cached-PDF amendment prior stop checkpoint mismatch")
            pdf_attempt_path = namespace / "pdf_corroborations/source_index_identity=2016-11-18/pdf/source_run=role5-h6-pdf-0894-20161118/attempt.json"
            pdf_attempt = json.loads(pdf_attempt_path.read_text(encoding="ascii"))
            pdf_body = pdf_attempt_path.with_name(pdf_attempt["body_filename"]).read_bytes()
            if (
                sha256_bytes(pdf_attempt_path.read_bytes()) != cached_pdf["request_894_attempt_sha256"]
                or sha256_bytes(pdf_body) != cached_pdf["request_894_body_sha256"]
                or pdf_attempt["http_status"] != cached_pdf["request_894_http_status"]
                or pdf_attempt["content_type"] != cached_pdf["request_894_content_type"]
            ):
                raise CollectionValidationError("Cached-PDF amendment request894 proof failed")
            import pypdf
            from .h6_pdf_validator_exact_20161118 import VALIDATOR_VERSION, validate_exact_20161118
            if pypdf.__version__ != cached_pdf["library_version"] or VALIDATOR_VERSION != cached_pdf["exact_validator_version"]:
                raise CollectionValidationError("Cached-PDF pinned runtime/library mismatch")
            exact_validation = validate_exact_20161118(
                pdf_body, cached_pdf["request_894_body_sha256"], cached_pdf["extracted_text_sha256"]
            )
            source_identity = cached_pdf["source_index_identity"]
            release_dir = namespace / "release_date=2016-11-18"
            root_attempt_path = release_dir / f"source_run={pdf_config['root_html_source_run_id']}" / "attempt.json"
            ascii_attempt_path = release_dir / f"source_run={pdf_config['failed_ascii_source_run_id']}" / "attempt.json"
            root_attempt = json.loads(root_attempt_path.read_text(encoding="ascii"))
            ascii_attempt = json.loads(ascii_attempt_path.read_text(encoding="ascii"))
            root_body = root_attempt_path.with_name(root_attempt["body_filename"]).read_bytes()
            root_release, root_format, root_values = parse_release(root_body)
            if root_release != cached_pdf["canonical_body_release_date"] or not root_values:
                raise CollectionValidationError("Cached-PDF root canonical body proof failed")
            reconciliation = {
                "schema_version": "1.0.0", "artifact_id": "ROLE5-H6-PDF-CORROBORATION-20161118-001",
                "classification": cached_pdf["classification_if_reextraction_passes"],
                "pdf_config_sha256": pdf_config_sha256, "cached_pdf_amendment_sha256": cached_pdf_sha256,
                "parent_pdf_validator_stopped_checkpoint_sha256": prior_checkpoint_sha256,
                "source_index_identity": source_identity, "canonical_body_release_date": cached_pdf["canonical_body_release_date"],
                "availability_date_for_j0": cached_pdf["availability_date_for_j0"],
                "source_index_contains_canonical_body_date_identity": False, "duplicate_canonical_release_in_index": False,
                "root_html_source_run_id": root_attempt["source_run_id"], "root_html_body_sha256": root_attempt["body_sha256"],
                "failed_ascii_source_run_id": ascii_attempt["source_run_id"], "failed_ascii_body_sha256": ascii_attempt["body_sha256"],
                "pdf_source_run_id": pdf_attempt["source_run_id"], "pdf_body_sha256": pdf_attempt["body_sha256"],
                "failed_layout_validator_outcome": pdf_attempt["outcome"], "exact_cached_pdf_validation": exact_validation,
                "root_parser_format": root_format, "root_parsed_table1_m2_row_count": len(root_values),
            }
            reconciliation_path = namespace / "pdf_corroborations/source_index_identity=2016-11-18/reconciliation.json"
            atomic_write(reconciliation_path, canonical_json(reconciliation))
            checkpoint["completed_release_ids"].append(source_identity)
            checkpoint["last_completed_release_id"] = source_identity
            checkpoint["directory_alias_release_ids"] = [source_identity]
            checkpoint["directory_alias_count"] = 1
            checkpoint["pdf_corroboration_config_sha256"] = pdf_config_sha256
            checkpoint["cached_pdf_validator_amendment_sha256"] = cached_pdf_sha256
            checkpoint["pdf_corroboration_parent_stopped_checkpoint_sha256"] = pdf_config["prior_terminal_checkpoint_sha256"]
            checkpoint["pdf_validator_parent_stopped_checkpoint_sha256"] = prior_checkpoint_sha256
            checkpoint["active_child_run_id"] = cached_pdf["resume_child_run_id"]
            checkpoint["successful_new_body_count"] += 1
            checkpoint["reconciliation_evidence_body_count"] = checkpoint.get("reconciliation_evidence_body_count", 0) + 1
            checkpoint["status"] = "IN_PROGRESS"
            checkpoint["failed_release_id"] = None
            checkpoint["failure_code"] = None
            checkpoint["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            atomic_write(checkpoint_path, canonical_json(checkpoint))
        elif (
            checkpoint["status"] == "STOPPED"
            and checkpoint["failure_code"] == "STOP_HTTP_ERROR"
            and checkpoint["failed_release_id"] == pdf_2017["source_index_identity"]
        ):
            prior_checkpoint_raw = checkpoint_path.read_bytes()
            prior_checkpoint_sha256 = sha256_bytes(prior_checkpoint_raw)
            if prior_checkpoint_sha256 != pdf_2017["prior_terminal_checkpoint_sha256"]:
                raise CollectionValidationError("2017 PDF corroboration prior checkpoint mismatch")
            source_identity = pdf_2017["source_index_identity"]
            canonical_identity = pdf_2017["canonical_body_release_date"].replace("-", "")
            if source_identity not in identities or canonical_identity in identities:
                raise CollectionValidationError("2017 PDF corroboration index identity proof failed")
            position = identities.index(source_identity)
            if identities[position - 1] != pdf_2017["preceding_source_index_identity"] or identities[position + 1] != pdf_2017["following_source_index_identity"]:
                raise CollectionValidationError("2017 PDF corroboration neighbor proof failed")
            index_body = raw_root / "vintage_year=2026/source_run=role5-index-0002/index.html"
            index_raw = index_body.read_bytes()
            if sha256_bytes(index_raw) != pdf_2017["cached_official_index_body_sha256"] or pdf_2017["cached_official_index_policy"].encode("ascii") not in index_raw:
                raise CollectionValidationError("2017 PDF corroboration official policy proof failed")
            nominal = date.fromisoformat("2017-11-23")
            canonical = date.fromisoformat(pdf_2017["canonical_body_release_date"])
            if nominal.strftime("%A") != "Thursday" or (nominal.day - 1) // 7 + 1 != 4 or canonical != nominal + timedelta(days=1) or canonical.strftime("%A") != "Friday":
                raise CollectionValidationError("2017 PDF corroboration calendar proof failed")
            release_dir = namespace / "release_date=2017-11-23"
            root_attempt_path = release_dir / f"source_run={pdf_2017['root_html_source_run_id']}" / "attempt.json"
            ascii_attempt_path = release_dir / f"source_run={pdf_2017['failed_ascii_source_run_id']}" / "attempt.json"
            root_attempt = json.loads(root_attempt_path.read_text(encoding="ascii"))
            ascii_attempt = json.loads(ascii_attempt_path.read_text(encoding="ascii"))
            root_body = root_attempt_path.with_name(root_attempt["body_filename"]).read_bytes()
            ascii_body = ascii_attempt_path.with_name(ascii_attempt["body_filename"]).read_bytes()
            if (
                sha256_bytes(root_attempt_path.read_bytes()) != pdf_2017["root_html_attempt_sha256"]
                or sha256_bytes(root_body) != pdf_2017["root_html_body_sha256"]
                or sha256_bytes(ascii_attempt_path.read_bytes()) != pdf_2017["failed_ascii_attempt_sha256"]
                or sha256_bytes(ascii_body) != pdf_2017["failed_ascii_body_sha256"]
                or ascii_attempt["http_status"] != pdf_2017["failed_ascii_http_status"]
            ):
                raise CollectionValidationError("2017 PDF corroboration root/ASCII hash proof failed")
            root_release, root_format, root_values = parse_release(root_body)
            root_text = root_body.decode("utf-8", errors="replace")
            if (
                root_release != pdf_2017["canonical_body_release_date"]
                or not root_values
                or "The Fed - Money Stock and Debt Measures - H.6 Release -  November 24, 2017" not in root_text
                or "Last Update:  November 24, 2017" not in root_text
                or 'href="h6.pdf"' not in root_text
            ):
                raise CollectionValidationError("2017 PDF corroboration root semantic proof failed")

            def validate_pdf_2017(body: bytes) -> dict[str, object]:
                import pypdf
                from .h6_pdf_validator_exact_20171123 import VALIDATOR_VERSION, validate_exact_20171123
                if pypdf.__version__ != pdf_2017["pdf_library_version"] or VALIDATOR_VERSION != pdf_2017["pdf_validator_version"]:
                    raise CollectionValidationError("2017 PDF pinned runtime/library mismatch")
                return validate_exact_20171123(body)

            ordinal = pdf_2017["pdf_network_request_ordinal"]
            if checkpoint["total_role5_network_request_count"] + 1 != ordinal:
                raise CollectionValidationError("2017 PDF request ordinal drift")
            pdf_record, _ = correction_request(
                namespace, Path("pdf_corroborations/source_index_identity=2017-11-23/pdf"),
                "role5-h6-pdf-0949-20171123", ordinal, source_identity, pdf_2017["pdf_url"],
                "h6.pdf", "PDF", config, config_sha256, "SUCCESS_PDF_CORROBORATION", validate_pdf_2017,
            )
            checkpoint["new_network_attempt_count"] += 1
            checkpoint["total_role5_network_request_count"] += 1
            checkpoint["last_updated_at_utc"] = pdf_record["completed_at_utc"]
            atomic_write(checkpoint_path, canonical_json(checkpoint))
            if pdf_record["outcome"] != "SUCCESS_PDF_CORROBORATION":
                checkpoint.update({"status": "STOPPED", "failed_release_id": source_identity, "failure_code": pdf_record["outcome"]})
                atomic_write(checkpoint_path, canonical_json(checkpoint))
                print(json.dumps({"status": "STOPPED", "release_id": source_identity, "failure_code": pdf_record["outcome"]}), flush=True)
                return checkpoint
            reconciliation = {
                "schema_version": "1.0.0", "artifact_id": "ROLE5-H6-PDF-CORROBORATION-20171123-001",
                "classification": pdf_2017["classification_if_confirmed"], "pdf_config_sha256": pdf_2017_sha256,
                "parent_stopped_checkpoint_sha256": prior_checkpoint_sha256,
                "source_index_identity": source_identity, "canonical_body_release_date": pdf_2017["canonical_body_release_date"],
                "availability_date_for_j0": pdf_2017["availability_date_for_j0"],
                "source_index_contains_canonical_body_date_identity": False,
                "calendar_proof": pdf_2017["calendar_proof"], "official_policy_body_sha256": pdf_2017["cached_official_index_body_sha256"],
                "root_html_source_run_id": root_attempt["source_run_id"], "root_html_body_sha256": root_attempt["body_sha256"],
                "failed_ascii_source_run_id": ascii_attempt["source_run_id"], "failed_ascii_body_sha256": ascii_attempt["body_sha256"],
                "pdf_source_run_id": pdf_record["source_run_id"], "pdf_body_sha256": pdf_record["body_sha256"],
                "pdf_validation": pdf_record["validation"], "root_parser_format": root_format,
                "root_parsed_table1_m2_row_count": len(root_values),
            }
            reconciliation_path = namespace / "pdf_corroborations/source_index_identity=2017-11-23/reconciliation.json"
            atomic_write(reconciliation_path, canonical_json(reconciliation))
            checkpoint["completed_release_ids"].append(source_identity)
            checkpoint["last_completed_release_id"] = source_identity
            checkpoint.setdefault("directory_alias_release_ids", []).append(source_identity)
            checkpoint["directory_alias_count"] = len(checkpoint["directory_alias_release_ids"])
            checkpoint["pdf_2017_corroboration_config_sha256"] = pdf_2017_sha256
            checkpoint["pdf_2017_parent_stopped_checkpoint_sha256"] = prior_checkpoint_sha256
            checkpoint["active_child_run_id"] = pdf_2017["resume_child_run_id"]
            checkpoint["successful_new_body_count"] += 1
            checkpoint["reconciliation_evidence_body_count"] = checkpoint.get("reconciliation_evidence_body_count", 0) + 1
            checkpoint["status"] = "IN_PROGRESS"
            checkpoint["failed_release_id"] = None
            checkpoint["failure_code"] = None
            checkpoint["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            atomic_write(checkpoint_path, canonical_json(checkpoint))
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(pdf_record["started_at_utc"].replace("Z", "+00:00"))).total_seconds()
            if elapsed < float(config["minimum_pacing_seconds"]):
                time.sleep(float(config["minimum_pacing_seconds"]) - elapsed)
        elif checkpoint["status"] == "STOPPED" and checkpoint["failure_code"] == "STOP_PARSER_OR_SOURCE_IDENTITY_UNRESOLVED":
            checkpoint["status"] = "IN_PROGRESS"
            checkpoint["fallback_config_sha256"] = fallback_sha256
        elif checkpoint["status"] == "STOPPED":
            return checkpoint
        checkpoint["quarantined_orphans"].extend(quarantine_temporary_orphans(namespace))
        verify_completed(namespace, checkpoint)
        completed = set(checkpoint["completed_release_ids"])
        last_progress = time.monotonic()

        for release_id in identities:
            if release_id in completed:
                continue
            if release_id in cache:
                item = cache[release_id]
                raw = Path(item["path"]).read_bytes()
                if sha256_bytes(raw) != item["sha256"]:
                    raise CollectionValidationError(f"Pilot cache changed: {release_id}")
                checkpoint["cache_reuse_count"] += 1
                checkpoint["completed_release_ids"].append(release_id)
                checkpoint["last_completed_release_id"] = release_id
                checkpoint["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                atomic_write(checkpoint_path, canonical_json(checkpoint))
                completed.add(release_id)
                continue

            release_dir = namespace / f"release_date={release_id[:4]}-{release_id[4:6]}-{release_id[6:]}"
            prior_attempts = []
            for candidate in sorted(release_dir.glob("source_run=*/attempt.json")):
                prior_attempts.append(json.loads(candidate.read_text(encoding="ascii")))
            fallback_mode = any(item["outcome"] == "STOP_PARSER_OR_SOURCE_IDENTITY_UNRESOLVED" for item in prior_attempts)
            if fallback_mode:
                url = fallback["prospective_fallback_url_template"].format(release_yyyymmdd=release_id)
                attempt_numbers = (2,)
                body_name = "release.txt"
            else:
                url = config["fixed_release_url_template"].format(release_yyyymmdd=release_id)
                attempt_numbers = (1, 2)
                body_name = "release.html"
            validate_url(url, config, allow_ascii_fallback=fallback_mode)
            for attempt_number in attempt_numbers:
                if checkpoint["total_role5_network_request_count"] >= config["hard_total_role5_network_request_ceiling"]:
                    checkpoint.update({"status": "STOPPED", "failed_release_id": release_id, "failure_code": "REQUEST_CEILING_REACHED"})
                    atomic_write(checkpoint_path, canonical_json(checkpoint))
                    return checkpoint

                ordinal = checkpoint["total_role5_network_request_count"] + 1
                run_id = f"role5-h6-full-{ordinal:04d}-{release_id}-a{attempt_number}"
                final_dir = release_dir / f"source_run={run_id}"
                temporary_dir = release_dir / f".{run_id}.tmp"
                if final_dir.exists() or temporary_dir.exists():
                    raise CollectionValidationError(f"Immutable source-run path collision: {run_id}")
                temporary_dir.mkdir(parents=True)
                raw_headers_path = temporary_dir / ".raw_headers.tmp"
                body_path = temporary_dir / body_name
                started = datetime.now(timezone.utc)
                monotonic_started = time.monotonic()
                status, effective_url, content_type, curl_exit = curl_request(url, raw_headers_path, body_path, config)
                body = body_path.read_bytes() if body_path.exists() else b""
                header_raw = raw_headers_path.read_bytes() if raw_headers_path.exists() else b""
                redacted_headers, header_values = safe_headers(header_raw)
                raw_headers_path.unlink(missing_ok=True)
                if effective_url != url:
                    outcome = "STOP_REDIRECT_OUTSIDE_FROZEN_ROUTE"
                else:
                    outcome = classify(status, body, attempt_number, config)
                parser_format = None
                parsed_row_count = None
                parse_error = None
                if outcome == "SUCCESS":
                    try:
                        parser_input = b"<pre>" + body + b"</pre>" if fallback_mode else body
                        parsed_release, parser_format, parsed_values = parse_release(parser_input)
                        if parsed_release.replace("-", "") != release_id:
                            raise CollectionValidationError("Parsed release date mismatches URL")
                        parsed_row_count = len(parsed_values)
                    except Exception as exc:  # fail closed and preserve the raw evidence
                        outcome = "STOP_PARSER_OR_SOURCE_IDENTITY_UNRESOLVED"
                        parse_error = f"{type(exc).__name__}: {exc}"[:500]
                completed_at = datetime.now(timezone.utc)
                attempt_record = {
                    "schema_version": "1.0.0", "source_run_id": run_id, "request_id": config["request_id"],
                    "config_sha256": config_sha256, "network_request_ordinal_role5": ordinal,
                    "release_id": release_id, "source_url": url, "effective_url": effective_url,
                    "attempt_number": attempt_number, "started_at_utc": started.isoformat().replace("+00:00", "Z"),
                    "completed_at_utc": completed_at.isoformat().replace("+00:00", "Z"),
                    "http_status": status, "curl_exit_code": curl_exit, "content_type": content_type,
                    "outcome": outcome, "body_byte_length": len(body), "body_sha256": sha256_bytes(body),
                    "body_filename": body_name, "source_format": "ASCII" if fallback_mode else "HTML",
                    "safe_header_byte_length": len(redacted_headers), "safe_header_sha256": sha256_bytes(redacted_headers),
                    "parser_version": config["parser_version"], "parser_format": parser_format,
                    "parsed_table1_m2_row_count": parsed_row_count, "redacted_error": parse_error,
                    "contains_credentials": False, "raw_unredacted_headers_preserved": False,
                }
                atomic_write(temporary_dir / "safe_headers.txt", redacted_headers)
                atomic_write(temporary_dir / "attempt.json", canonical_json(attempt_record))
                os.replace(temporary_dir, final_dir)
                checkpoint["new_network_attempt_count"] += 1
                checkpoint["total_role5_network_request_count"] += 1
                checkpoint["last_updated_at_utc"] = completed_at.isoformat().replace("+00:00", "Z")
                if outcome == "SUCCESS":
                    checkpoint["successful_new_body_count"] += 1
                    checkpoint["failed_release_id"] = None
                    checkpoint["failure_code"] = None
                    checkpoint["completed_release_ids"].append(release_id)
                    checkpoint["last_completed_release_id"] = release_id
                    completed.add(release_id)
                    atomic_write(checkpoint_path, canonical_json(checkpoint))
                    elapsed = time.monotonic() - monotonic_started
                    if elapsed < float(config["minimum_pacing_seconds"]):
                        time.sleep(float(config["minimum_pacing_seconds"]) - elapsed)
                    break
                if outcome == "RETRY":
                    checkpoint["retry_count"] += 1
                    atomic_write(checkpoint_path, canonical_json(checkpoint))
                    delay = retry_delay(header_values, config)
                    print(json.dumps({"status": "RETRY", "release_id": release_id, "http_status": status, "delay_seconds": delay}), flush=True)
                    time.sleep(delay)
                    continue
                checkpoint.update({"status": "STOPPED", "failed_release_id": release_id, "failure_code": outcome})
                atomic_write(checkpoint_path, canonical_json(checkpoint))
                print(json.dumps({"status": "STOPPED", "release_id": release_id, "failure_code": outcome}), flush=True)
                return checkpoint

            now = time.monotonic()
            if checkpoint["new_network_attempt_count"] % config["checkpoint_policy"]["progress_report_every_network_attempts"] == 0 or now - last_progress >= config["checkpoint_policy"]["maximum_progress_report_interval_seconds"]:
                print(json.dumps({
                    "status": "IN_PROGRESS", "completed_identities": len(completed),
                    "identity_count": len(identities), "new_network_attempts": checkpoint["new_network_attempt_count"],
                    "total_role5_network_requests": checkpoint["total_role5_network_request_count"],
                    "last_release_id": checkpoint["last_completed_release_id"],
                }, sort_keys=True), flush=True)
                last_progress = now

        checkpoint.update({
            "status": "COMPLETE_RAW_SEQUENCE", "failed_release_id": None, "failure_code": None,
            "last_updated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        })
        atomic_write(checkpoint_path, canonical_json(checkpoint))
        print(json.dumps({"status": "COMPLETE_RAW_SEQUENCE", "completed_identities": len(completed), "new_network_attempts": checkpoint["new_network_attempt_count"]}, sort_keys=True), flush=True)
        return checkpoint


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = collect(args.repo_root.resolve())
    if result["status"] != "COMPLETE_RAW_SEQUENCE":
        raise SystemExit(2)


if __name__ == "__main__":
    main()

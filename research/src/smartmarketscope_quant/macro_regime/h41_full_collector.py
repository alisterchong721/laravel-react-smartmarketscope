from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

from .h6_full_collector import atomic_write, canonical_json, classify, retry_delay, safe_headers
from .h41_parser import parse_h41
from .historical_collector import CollectionValidationError, sha256_bytes


CONFIG_PATH = Path("research/config/macro_regime_h41_full_traversal.json")
CONFIG_HASH_PATH = Path("research/config/macro_regime_h41_full_traversal.sha256")
PILOT_CONFIG_PATH = Path("research/config/macro_regime_h41_pilot.json")
PILOT_CONFIG_HASH_PATH = Path("research/config/macro_regime_h41_pilot.sha256")
SCOPE_RECONCILIATION_PATH = Path("research/config/macro_regime_h41_pilot_scope_reconciliation.json")
SCOPE_RECONCILIATION_HASH_PATH = Path("research/config/macro_regime_h41_pilot_scope_reconciliation.sha256")
ALIAS_PATH = Path("research/config/macro_regime_h41_archive_alias_20050305.json")
ALIAS_HASH_PATH = Path("research/config/macro_regime_h41_archive_alias_20050305.sha256")
PARSER_AMENDMENT_PATH = Path("research/config/macro_regime_h41_ascii_parser_amendment_20050305.json")
PARSER_AMENDMENT_HASH_PATH = Path("research/config/macro_regime_h41_ascii_parser_amendment_20050305.sha256")
SIGNED_RESERVE_PATH = Path("research/config/macro_regime_h41_signed_reserve_amendment_20080703.json")
SIGNED_RESERVE_HASH_PATH = Path("research/config/macro_regime_h41_signed_reserve_amendment_20080703.sha256")
DATE_ALIAS_20161118_PATH = Path("research/config/macro_regime_h41_date_alias_20161118.json")
DATE_ALIAS_20161118_HASH_PATH = Path("research/config/macro_regime_h41_date_alias_20161118.sha256")
DATE_ALIAS_20191128_PATH = Path("research/config/macro_regime_h41_date_alias_20191128.json")
DATE_ALIAS_20191128_HASH_PATH = Path("research/config/macro_regime_h41_date_alias_20191128.sha256")
DATE_ALIAS_20200514_PATH = Path("research/config/macro_regime_h41_date_alias_20200514.json")
DATE_ALIAS_20200514_HASH_PATH = Path("research/config/macro_regime_h41_date_alias_20200514.sha256")


def frozen(repo_root: Path, data_path: Path, hash_path: Path) -> tuple[dict[str, object], str]:
    raw = (repo_root / data_path).read_bytes()
    actual = sha256_bytes(raw)
    expected = (repo_root / hash_path).read_text(encoding="ascii").split()[0]
    if actual != expected:
        raise CollectionValidationError(f"Frozen H41 hash mismatch: {data_path}")
    return json.loads(raw), actual


def validate_url(url: str, config: dict[str, object], allow_ascii: bool = False) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https" or parsed.hostname != "www.federalreserve.gov"
        or parsed.port is not None or parsed.username is not None or parsed.password is not None
        or parsed.query or parsed.fragment
        or not re.fullmatch(r"/releases/h41/\d{8}/(?:h41\.txt)?" if allow_ascii else r"/releases/h41/\d{8}/", parsed.path)
    ):
        raise CollectionValidationError(f"URL outside frozen H41 dated route: {url}")


def curl_request(url: str, header_path: Path, body_path: Path, config: dict[str, object]) -> tuple[int, str, str, int]:
    command = [
        "/usr/bin/curl", "--silent", "--show-error", "--proto", "=https",
        "--connect-timeout", str(config["connect_timeout_seconds"]),
        "--max-time", str(config["request_timeout_seconds"]), "--max-redirs", "0",
        "--user-agent", "SmartMarketScope-Research-H41/1.0",
        "--dump-header", str(header_path), "--output", str(body_path),
        "--write-out", "%{http_code}\n%{url_effective}\n%{content_type}\n", url,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    parts = result.stdout.splitlines()
    status = int(parts[0]) if parts and parts[0].isdigit() else 0
    return status, parts[1] if len(parts) > 1 else url, parts[2] if len(parts) > 2 else "", result.returncode


def identities(raw: bytes, config: dict[str, object]) -> list[str]:
    payload = json.loads(raw)
    lower = str(config["first_release_identity"])
    upper = str(config["last_release_identity"])
    result = sorted({
        value[:8]
        for year in payload for month in year["Months"] for value in month["Dates"]
        if lower <= value[:8] <= upper
    })
    if len(result) != config["expected_release_identity_count"] or result[0] != lower or result[-1] != upper:
        raise CollectionValidationError("Frozen H41 full release identity census changed")
    return result


def pilot_cache(raw_root: Path, config: dict[str, object]) -> dict[str, dict[str, object]]:
    namespace = raw_root / str(config["pilot_namespace"])
    checkpoint = json.loads((namespace / "checkpoint.json").read_text(encoding="ascii"))
    expected_hash = str(config["pilot_terminal_checkpoint_sha256"])
    if sha256_bytes((namespace / "checkpoint.json").read_bytes()) != expected_hash:
        raise CollectionValidationError("H41 pilot checkpoint hash changed")
    if checkpoint["status"] != "PILOT_RAW_COMPLETE_SCOPE_CORRECTED":
        raise CollectionValidationError("H41 pilot scope correction has not passed")
    cache: dict[str, dict[str, object]] = {}
    for identity, ordinal in config["cached_pilot_release_ordinals"].items():
        path = namespace / f"request={int(ordinal):02d}-{identity}" / "body.html"
        raw = path.read_bytes()
        parsed = parse_h41(raw)
        if parsed.release_date.replace("-", "") != identity:
            raise CollectionValidationError(f"H41 pilot cache identity mismatch: {identity}")
        attempt = json.loads(path.with_name("attempt.json").read_text(encoding="ascii"))
        if sha256_bytes(raw) != attempt["body_sha256"] or attempt["outcome"] != "SUCCESS":
            raise CollectionValidationError(f"H41 pilot cache hash/outcome mismatch: {identity}")
        cache[identity] = {
            "path": str(path), "source_run_id": f"role5-h41-pilot-{int(ordinal):02d}-{identity}",
            "body_sha256": attempt["body_sha256"], "retrieved_at_utc": attempt["completed_at_utc"],
            "source_url": attempt["source_url"],
        }
    if len(cache) != config["cached_pilot_release_count"]:
        raise CollectionValidationError("H41 pilot cache count mismatch")
    return cache


@contextmanager
def collection_lock(namespace: Path):
    namespace.mkdir(parents=True, exist_ok=True)
    with (namespace / ".collector.lock").open("a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CollectionValidationError("Another H41 collector owns the lock") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def verify_completed(namespace: Path, checkpoint: dict[str, object]) -> None:
    cached = set(checkpoint["cached_pilot_release_ids"])
    for identity in checkpoint["completed_release_ids"]:
        if identity in cached:
            continue
        if identity in checkpoint.get("alias_reconciled_release_ids", []):
            evidence = namespace / "alias_reconciliations" / f"source_index_identity={identity}" / "reconciliation.json"
            if json.loads(evidence.read_text(encoding="ascii"))["classification"] != "OFFICIAL_ARCHIVE_ALIAS_RECONCILED":
                raise CollectionValidationError(f"H41 alias reconciliation invalid: {identity}")
            continue
        if identity in checkpoint.get("semantic_reconciled_release_ids", []):
            evidence = namespace / "semantic_reconciliations" / f"source_identity={identity}" / "reconciliation.json"
            if json.loads(evidence.read_text(encoding="ascii"))["classification"] != "VALID_SIGNED_LEGACY_RESERVE_BALANCE_ACCOUNTING_IDENTITY":
                raise CollectionValidationError(f"H41 semantic reconciliation invalid: {identity}")
            continue
        if identity in checkpoint.get("date_reconciled_release_ids", []):
            evidence = namespace / "date_reconciliations" / f"source_identity={identity}" / "reconciliation.json"
            if json.loads(evidence.read_text(encoding="ascii"))["classification"] not in {
                "OFFICIAL_ARCHIVE_DIRECTORY_DATE_BODY_DATE_DIVERGENCE",
                "OFFICIAL_FEDERAL_HOLIDAY_RELEASE_SHIFT_DIRECTORY_DATE_DIVERGENCE",
            }:
                raise CollectionValidationError(f"H41 date reconciliation invalid: {identity}")
            continue
        attempts = list((namespace / f"release_date={identity[:4]}-{identity[4:6]}-{identity[6:]}").glob("source_run=*/attempt.json"))
        successes = []
        for path in attempts:
            attempt = json.loads(path.read_text(encoding="ascii"))
            body = path.with_name("release.html")
            if attempt["outcome"] == "SUCCESS" and body.is_file() and sha256_bytes(body.read_bytes()) == attempt["body_sha256"]:
                successes.append(path)
        if len(successes) != 1:
            raise CollectionValidationError(f"Completed H41 release cache invalid: {identity}")


def collect(repo_root: Path) -> dict[str, object]:
    config, config_hash = frozen(repo_root, CONFIG_PATH, CONFIG_HASH_PATH)
    pilot_config, pilot_hash = frozen(repo_root, PILOT_CONFIG_PATH, PILOT_CONFIG_HASH_PATH)
    _, scope_hash = frozen(repo_root, SCOPE_RECONCILIATION_PATH, SCOPE_RECONCILIATION_HASH_PATH)
    alias, alias_hash = frozen(repo_root, ALIAS_PATH, ALIAS_HASH_PATH)
    parser_amendment, parser_amendment_hash = frozen(repo_root, PARSER_AMENDMENT_PATH, PARSER_AMENDMENT_HASH_PATH)
    signed_reserve, signed_reserve_hash = frozen(repo_root, SIGNED_RESERVE_PATH, SIGNED_RESERVE_HASH_PATH)
    date_alias, date_alias_hash = frozen(repo_root, DATE_ALIAS_20161118_PATH, DATE_ALIAS_20161118_HASH_PATH)
    holiday_alias, holiday_alias_hash = frozen(repo_root, DATE_ALIAS_20191128_PATH, DATE_ALIAS_20191128_HASH_PATH)
    date_alias_2020, date_alias_2020_hash = frozen(repo_root, DATE_ALIAS_20200514_PATH, DATE_ALIAS_20200514_HASH_PATH)
    if config["parent_pilot_config_sha256"] != pilot_hash or config["scope_reconciliation_sha256"] != scope_hash:
        raise CollectionValidationError("H41 full traversal parent lineage mismatch")
    code_hash = sha256_bytes((repo_root / "research/src/smartmarketscope_quant/macro_regime/h41_full_collector.py").read_bytes())
    parser_hash = sha256_bytes((repo_root / "research/src/smartmarketscope_quant/macro_regime/h41_parser.py").read_bytes())
    if (
        alias["parent_full_config_sha256"] != config_hash
        or alias["parent_collector_code_sha256"] != config["collector_code_sha256"]
        or parser_amendment["parent_alias_config_sha256"] != alias_hash
        or parser_amendment["parent_collector_code_sha256"] != alias["amended_collector_code_sha256"]
        or signed_reserve["parent_parser_amendment_sha256"] != parser_amendment_hash
        or signed_reserve["parent_collector_code_sha256"] != parser_amendment["amended_collector_code_sha256"]
        or date_alias["parent_signed_reserve_amendment_sha256"] != signed_reserve_hash
        or date_alias["parent_collector_code_sha256"] != signed_reserve["amended_collector_code_sha256"]
        or holiday_alias["parent_date_alias_sha256"] != date_alias_hash
        or holiday_alias["parent_collector_code_sha256"] != date_alias["amended_collector_code_sha256"]
        or date_alias_2020["parent_date_alias_sha256"] != holiday_alias_hash
        or date_alias_2020["parent_collector_code_sha256"] != holiday_alias["amended_collector_code_sha256"]
        or date_alias_2020["amended_collector_code_sha256"] != code_hash
    ):
        raise CollectionValidationError("H41 exact alias amendment lineage mismatch")
    if (
        parser_amendment["parent_parser_code_sha256"] != config["parser_code_sha256"]
        or signed_reserve["parent_parser_code_sha256"] != parser_amendment["amended_parser_code_sha256"]
        or date_alias["parent_parser_code_sha256"] != signed_reserve["amended_parser_code_sha256"]
        or holiday_alias["parent_parser_code_sha256"] != date_alias["amended_parser_code_sha256"]
        or date_alias_2020["parent_parser_code_sha256"] != holiday_alias["amended_parser_code_sha256"]
        or date_alias_2020["amended_parser_code_sha256"] != parser_hash
    ):
        raise CollectionValidationError("H41 full collector/parser code hash mismatch")
    raw_root = Path(config["private_raw_root"])
    pilot_root = Path(pilot_config["storage_policy"]["private_raw_root"])
    if raw_root != pilot_root:
        raise CollectionValidationError("H41 pilot/full raw roots differ")
    pilot_namespace = pilot_root / pilot_config["storage_policy"]["pilot_namespace"]
    release_index_path = pilot_namespace / "request=02-release_date_index/releaseDates.json"
    release_index_raw = release_index_path.read_bytes()
    if sha256_bytes(release_index_raw) != config["release_dates_raw_sha256"]:
        raise CollectionValidationError("H41 releaseDates raw hash mismatch")
    release_ids = identities(release_index_raw, config)
    cache = pilot_cache(raw_root, config)
    namespace = raw_root / str(config["full_namespace"])

    checkpoint_path = namespace / "checkpoint.json"
    if checkpoint_path.exists() and sha256_bytes(checkpoint_path.read_bytes()) == parser_amendment["parent_stopped_checkpoint_sha256"]:
        with collection_lock(namespace):
            stopped_raw = checkpoint_path.read_bytes()
            if sha256_bytes(stopped_raw) != parser_amendment["parent_stopped_checkpoint_sha256"]:
                raise CollectionValidationError("H41 cached parser amendment checkpoint changed")
            checkpoint = json.loads(stopped_raw)
            ascii_attempt_path = namespace / "release_date=2005-03-05" / f"source_run={parser_amendment['ascii_source_run_id']}" / "attempt.json"
            ascii_attempt = json.loads(ascii_attempt_path.read_text(encoding="ascii"))
            ascii_body_path = ascii_attempt_path.with_name("release.txt")
            ascii_body = ascii_body_path.read_bytes()
            if (
                sha256_bytes(ascii_body) != parser_amendment["ascii_body_sha256"]
                or sha256_bytes(ascii_attempt_path.read_bytes()) != parser_amendment["ascii_attempt_sha256"]
            ):
                raise CollectionValidationError("H41 cached ASCII parser evidence changed")
            parsed = parse_h41(ascii_body)
            expected_values = alias["root_parsed_values_millions"]
            if (
                parsed.release_date != alias["canonical_body_release_date"]
                or parsed.reference_date != alias["canonical_reference_date"]
                or parsed.total_assets_millions != expected_values["total_assets"]
                or parsed.reserve_balances_millions != expected_values["reserve_balances"]
                or parsed.treasury_general_account_millions != expected_values["treasury_general_account"]
            ):
                raise CollectionValidationError("H41 cached ASCII parser amendment semantic proof failed")
            reconciliation = {
                "schema_version": "1.0.0", "artifact_id": "ROLE5-H41-ALIAS-RECONCILIATION-20050305-001",
                "classification": alias["classification"], "alias_config_sha256": alias_hash,
                "parser_amendment_config_sha256": parser_amendment_hash,
                "parent_stopped_checkpoint_sha256": alias["parent_stopped_checkpoint_sha256"],
                "parser_failed_checkpoint_sha256": parser_amendment["parent_stopped_checkpoint_sha256"],
                "source_index_identity": alias["source_index_identity"],
                "canonical_body_release_date": parsed.release_date,
                "canonical_reference_date": parsed.reference_date,
                "availability_date_for_j0": parsed.release_date,
                "root_body_sha256": alias["root_body_sha256"], "ascii_body_sha256": sha256_bytes(ascii_body),
                "ascii_source_run_id": parser_amendment["ascii_source_run_id"],
            }
            reconciliation_path = namespace / "alias_reconciliations/source_index_identity=20050305/reconciliation.json"
            atomic_write(reconciliation_path, canonical_json(reconciliation))
            checkpoint["successful_new_body_count"] += 1
            checkpoint["completed_release_ids"].append(alias["source_index_identity"])
            checkpoint["last_completed_release_id"] = alias["source_index_identity"]
            checkpoint["alias_reconciled_release_ids"] = [alias["source_index_identity"]]
            checkpoint["alias_config_sha256"] = alias_hash
            checkpoint["parser_amendment_config_sha256"] = parser_amendment_hash
            checkpoint["status"] = "IN_PROGRESS"
            checkpoint["failed_release_id"] = None
            checkpoint["failure_code"] = None
            checkpoint["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            atomic_write(checkpoint_path, canonical_json(checkpoint))

    if checkpoint_path.exists() and sha256_bytes(checkpoint_path.read_bytes()) == date_alias_2020["parent_stopped_checkpoint_sha256"]:
        with collection_lock(namespace):
            stopped_raw = checkpoint_path.read_bytes()
            if sha256_bytes(stopped_raw) != date_alias_2020["parent_stopped_checkpoint_sha256"]:
                raise CollectionValidationError("H41 20200514 date-alias checkpoint changed")
            checkpoint = json.loads(stopped_raw)
            identity = str(date_alias_2020["source_identity"])
            attempt_path = namespace / "release_date=2020-05-14" / f"source_run={date_alias_2020['source_run_id']}" / "attempt.json"
            body_path = attempt_path.with_name("release.html")
            if (
                sha256_bytes(attempt_path.read_bytes()) != date_alias_2020["attempt_sha256"]
                or sha256_bytes(body_path.read_bytes()) != date_alias_2020["body_sha256"]
            ):
                raise CollectionValidationError("H41 20200514 date-alias evidence changed")
            parsed = parse_h41(body_path.read_bytes())
            expected = date_alias_2020["parsed_values_millions"]
            if (
                parsed.release_date != date_alias_2020["canonical_release_date"]
                or parsed.reference_date != date_alias_2020["reference_date"]
                or parsed.total_assets_millions != expected["total_assets"]
                or parsed.reserve_balances_millions != expected["reserve_balances"]
                or parsed.treasury_general_account_millions != expected["treasury_general_account"]
            ):
                raise CollectionValidationError("H41 20200514 date-alias semantic proof failed")
            reconciliation = {
                "schema_version": "1.0.0", "artifact_id": "ROLE5-H41-DATE-RECONCILIATION-20200514-001",
                "classification": date_alias_2020["classification"], "amendment_config_sha256": date_alias_2020_hash,
                "parent_stopped_checkpoint_sha256": date_alias_2020["parent_stopped_checkpoint_sha256"],
                "source_identity": identity, "canonical_release_date": parsed.release_date,
                "reference_date": parsed.reference_date, "availability_date_for_j0": parsed.release_date,
                "body_sha256": date_alias_2020["body_sha256"],
            }
            reconciliation_path = namespace / f"date_reconciliations/source_identity={identity}/reconciliation.json"
            atomic_write(reconciliation_path, canonical_json(reconciliation))
            checkpoint["successful_new_body_count"] += 1
            checkpoint["completed_release_ids"].append(identity)
            checkpoint["last_completed_release_id"] = identity
            checkpoint.setdefault("date_reconciled_release_ids", []).append(identity)
            checkpoint["date_alias_20200514_config_sha256"] = date_alias_2020_hash
            checkpoint["status"] = "IN_PROGRESS"
            checkpoint["failed_release_id"] = None
            checkpoint["failure_code"] = None
            checkpoint["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            atomic_write(checkpoint_path, canonical_json(checkpoint))

    if checkpoint_path.exists() and sha256_bytes(checkpoint_path.read_bytes()) == holiday_alias["parent_stopped_checkpoint_sha256"]:
        with collection_lock(namespace):
            stopped_raw = checkpoint_path.read_bytes()
            if sha256_bytes(stopped_raw) != holiday_alias["parent_stopped_checkpoint_sha256"]:
                raise CollectionValidationError("H41 20191128 holiday-alias checkpoint changed")
            checkpoint = json.loads(stopped_raw)
            identity = str(holiday_alias["source_identity"])
            attempt_path = namespace / "release_date=2019-11-28" / f"source_run={holiday_alias['source_run_id']}" / "attempt.json"
            body_path = attempt_path.with_name("release.html")
            if (
                sha256_bytes(attempt_path.read_bytes()) != holiday_alias["attempt_sha256"]
                or sha256_bytes(body_path.read_bytes()) != holiday_alias["body_sha256"]
            ):
                raise CollectionValidationError("H41 20191128 holiday-alias evidence changed")
            parsed = parse_h41(body_path.read_bytes())
            expected = holiday_alias["parsed_values_millions"]
            if (
                parsed.release_date != holiday_alias["canonical_release_date"]
                or parsed.reference_date != holiday_alias["reference_date"]
                or parsed.total_assets_millions != expected["total_assets"]
                or parsed.reserve_balances_millions != expected["reserve_balances"]
                or parsed.treasury_general_account_millions != expected["treasury_general_account"]
            ):
                raise CollectionValidationError("H41 20191128 holiday-alias semantic proof failed")
            reconciliation = {
                "schema_version": "1.0.0", "artifact_id": "ROLE5-H41-DATE-RECONCILIATION-20191128-001",
                "classification": holiday_alias["classification"], "amendment_config_sha256": holiday_alias_hash,
                "parent_stopped_checkpoint_sha256": holiday_alias["parent_stopped_checkpoint_sha256"],
                "source_identity": identity, "canonical_release_date": parsed.release_date,
                "reference_date": parsed.reference_date, "availability_date_for_j0": parsed.release_date,
                "body_sha256": holiday_alias["body_sha256"], "holiday_evidence": holiday_alias["holiday_evidence"],
            }
            reconciliation_path = namespace / f"date_reconciliations/source_identity={identity}/reconciliation.json"
            atomic_write(reconciliation_path, canonical_json(reconciliation))
            checkpoint["successful_new_body_count"] += 1
            checkpoint["completed_release_ids"].append(identity)
            checkpoint["last_completed_release_id"] = identity
            checkpoint.setdefault("date_reconciled_release_ids", []).append(identity)
            checkpoint["date_alias_20191128_config_sha256"] = holiday_alias_hash
            checkpoint["status"] = "IN_PROGRESS"
            checkpoint["failed_release_id"] = None
            checkpoint["failure_code"] = None
            checkpoint["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            atomic_write(checkpoint_path, canonical_json(checkpoint))

    if checkpoint_path.exists() and sha256_bytes(checkpoint_path.read_bytes()) == date_alias["parent_stopped_checkpoint_sha256"]:
        with collection_lock(namespace):
            stopped_raw = checkpoint_path.read_bytes()
            if sha256_bytes(stopped_raw) != date_alias["parent_stopped_checkpoint_sha256"]:
                raise CollectionValidationError("H41 20161118 date-alias checkpoint changed")
            checkpoint = json.loads(stopped_raw)
            identity = str(date_alias["source_identity"])
            attempt_path = namespace / "release_date=2016-11-18" / f"source_run={date_alias['source_run_id']}" / "attempt.json"
            body_path = attempt_path.with_name("release.html")
            if (
                sha256_bytes(attempt_path.read_bytes()) != date_alias["attempt_sha256"]
                or sha256_bytes(body_path.read_bytes()) != date_alias["body_sha256"]
            ):
                raise CollectionValidationError("H41 20161118 date-alias evidence changed")
            parsed = parse_h41(body_path.read_bytes())
            expected = date_alias["parsed_values_millions"]
            if (
                parsed.release_date != date_alias["canonical_release_date"]
                or parsed.reference_date != date_alias["reference_date"]
                or parsed.total_assets_millions != expected["total_assets"]
                or parsed.reserve_balances_millions != expected["reserve_balances"]
                or parsed.treasury_general_account_millions != expected["treasury_general_account"]
            ):
                raise CollectionValidationError("H41 20161118 date-alias semantic proof failed")
            reconciliation = {
                "schema_version": "1.0.0", "artifact_id": "ROLE5-H41-DATE-RECONCILIATION-20161118-001",
                "classification": date_alias["classification"], "amendment_config_sha256": date_alias_hash,
                "parent_stopped_checkpoint_sha256": date_alias["parent_stopped_checkpoint_sha256"],
                "source_identity": identity, "canonical_release_date": parsed.release_date,
                "reference_date": parsed.reference_date, "availability_date_for_j0": parsed.release_date,
                "body_sha256": date_alias["body_sha256"], "cross_series_corroboration": date_alias["cross_series_corroboration"],
            }
            reconciliation_path = namespace / f"date_reconciliations/source_identity={identity}/reconciliation.json"
            atomic_write(reconciliation_path, canonical_json(reconciliation))
            checkpoint["successful_new_body_count"] += 1
            checkpoint["completed_release_ids"].append(identity)
            checkpoint["last_completed_release_id"] = identity
            checkpoint["date_reconciled_release_ids"] = [identity]
            checkpoint["date_alias_20161118_config_sha256"] = date_alias_hash
            checkpoint["status"] = "IN_PROGRESS"
            checkpoint["failed_release_id"] = None
            checkpoint["failure_code"] = None
            checkpoint["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            atomic_write(checkpoint_path, canonical_json(checkpoint))

    if checkpoint_path.exists() and sha256_bytes(checkpoint_path.read_bytes()) == signed_reserve["parent_stopped_checkpoint_sha256"]:
        with collection_lock(namespace):
            stopped_raw = checkpoint_path.read_bytes()
            if sha256_bytes(stopped_raw) != signed_reserve["parent_stopped_checkpoint_sha256"]:
                raise CollectionValidationError("H41 signed-reserve amendment checkpoint changed")
            checkpoint = json.loads(stopped_raw)
            source_identity = str(signed_reserve["source_identity"])
            attempt_path = namespace / "release_date=2008-07-03" / f"source_run={signed_reserve['source_run_id']}" / "attempt.json"
            body_path = attempt_path.with_name("release.html")
            attempt_raw = attempt_path.read_bytes()
            body = body_path.read_bytes()
            if (
                sha256_bytes(attempt_raw) != signed_reserve["attempt_sha256"]
                or sha256_bytes(body) != signed_reserve["body_sha256"]
            ):
                raise CollectionValidationError("H41 signed-reserve source evidence changed")
            parsed = parse_h41(body)
            expected = signed_reserve["parsed_values_millions"]
            if (
                parsed.release_date != signed_reserve["release_date"]
                or parsed.reference_date != signed_reserve["reference_date"]
                or parsed.total_assets_millions != expected["total_assets"]
                or parsed.reserve_balances_millions != expected["reserve_balances"]
                or parsed.treasury_general_account_millions != expected["treasury_general_account"]
                or signed_reserve["accounting_identity"]["supplying"] - signed_reserve["accounting_identity"]["absorbing"] != parsed.reserve_balances_millions
            ):
                raise CollectionValidationError("H41 signed-reserve semantic proof failed")
            reconciliation = {
                "schema_version": "1.0.0", "artifact_id": "ROLE5-H41-SIGNED-RESERVE-RECONCILIATION-20080703-001",
                "classification": signed_reserve["classification"], "amendment_config_sha256": signed_reserve_hash,
                "parent_stopped_checkpoint_sha256": signed_reserve["parent_stopped_checkpoint_sha256"],
                "source_identity": source_identity, "release_date": parsed.release_date,
                "reference_date": parsed.reference_date, "body_sha256": signed_reserve["body_sha256"],
                "parsed_values_millions": expected, "accounting_identity": signed_reserve["accounting_identity"],
            }
            reconciliation_path = namespace / f"semantic_reconciliations/source_identity={source_identity}/reconciliation.json"
            atomic_write(reconciliation_path, canonical_json(reconciliation))
            checkpoint["successful_new_body_count"] += 1
            checkpoint["completed_release_ids"].append(source_identity)
            checkpoint["last_completed_release_id"] = source_identity
            checkpoint["semantic_reconciled_release_ids"] = [source_identity]
            checkpoint["signed_reserve_amendment_config_sha256"] = signed_reserve_hash
            checkpoint["status"] = "IN_PROGRESS"
            checkpoint["failed_release_id"] = None
            checkpoint["failure_code"] = None
            checkpoint["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            atomic_write(checkpoint_path, canonical_json(checkpoint))

    with collection_lock(namespace):
        if checkpoint_path.exists():
            checkpoint = json.loads(checkpoint_path.read_text(encoding="ascii"))
            if checkpoint["config_sha256"] != config_hash:
                raise CollectionValidationError("H41 full checkpoint belongs to another config")
            if checkpoint["status"] == "STOPPED":
                if (
                    checkpoint["failure_code"] != "STOP_PARSER_OR_SOURCE_IDENTITY_UNRESOLVED"
                    or checkpoint["failed_release_id"] != alias["source_index_identity"]
                ):
                    return checkpoint
                stopped_raw = checkpoint_path.read_bytes()
                if sha256_bytes(stopped_raw) != alias["parent_stopped_checkpoint_sha256"]:
                    raise CollectionValidationError("H41 alias parent stopped checkpoint mismatch")
                source_identity = str(alias["source_index_identity"])
                position = release_ids.index(source_identity)
                if (
                    release_ids[position - 1] != alias["preceding_source_index_identity"]
                    or release_ids[position + 1] != alias["following_source_index_identity"]
                    or alias["canonical_body_release_date"].replace("-", "") in release_ids
                ):
                    raise CollectionValidationError("H41 alias official index proof failed")
                root_attempt_path = namespace / "release_date=2005-03-05" / f"source_run={alias['root_source_run_id']}" / "attempt.json"
                root_attempt = json.loads(root_attempt_path.read_text(encoding="ascii"))
                if root_attempt["body_sha256"] != alias["root_body_sha256"]:
                    raise CollectionValidationError("H41 alias root body proof failed")
                ordinal = checkpoint["total_h41_network_request_count"] + 1
                if ordinal != alias["ascii_network_request_ordinal"] or ordinal > config["hard_total_h41_request_ceiling"]:
                    raise CollectionValidationError("H41 alias request ordinal/ceiling mismatch")
                url = str(alias["ascii_url"])
                validate_url(url, config, allow_ascii=True)
                run_id = f"role5-h41-full-{ordinal:04d}-{source_identity}-a2"
                release_dir = namespace / "release_date=2005-03-05"
                final_dir = release_dir / f"source_run={run_id}"
                temporary = release_dir / f".{run_id}.tmp"
                if final_dir.exists() or temporary.exists():
                    raise CollectionValidationError("Immutable H41 alias source-run path collision")
                temporary.mkdir(parents=True, exist_ok=False)
                body_path = temporary / "release.txt"
                raw_headers = temporary / ".raw_headers.tmp"
                started = datetime.now(timezone.utc)
                status, effective_url, content_type, curl_exit = curl_request(url, raw_headers, body_path, config)
                body = body_path.read_bytes() if body_path.exists() else b""
                header_raw = raw_headers.read_bytes() if raw_headers.exists() else b""
                redacted_headers, _ = safe_headers(header_raw)
                raw_headers.unlink(missing_ok=True)
                outcome = "STOP_REDIRECT_OUTSIDE_FROZEN_HOST" if effective_url != url else classify(status, body, 1, config)
                parsed = None
                error = ""
                if outcome == "SUCCESS":
                    try:
                        parsed = parse_h41(body)
                        if parsed.release_date != alias["canonical_body_release_date"] or parsed.reference_date != alias["canonical_reference_date"]:
                            raise CollectionValidationError("H41 alias ASCII date proof failed")
                        expected_values = alias["root_parsed_values_millions"]
                        if (
                            parsed.total_assets_millions != expected_values["total_assets"]
                            or parsed.reserve_balances_millions != expected_values["reserve_balances"]
                            or parsed.treasury_general_account_millions != expected_values["treasury_general_account"]
                        ):
                            raise CollectionValidationError("H41 alias ASCII/root target values differ")
                        outcome = "SUCCESS_ALIAS_CORROBORATION"
                    except Exception as exc:
                        outcome = "STOP_PARSER_OR_SOURCE_IDENTITY_UNRESOLVED"
                        error = f"{type(exc).__name__}: {exc}"[:500]
                completed_at = datetime.now(timezone.utc)
                attempt = {
                    "schema_version": "1.0.0", "source_run_id": run_id, "program_id": config["program_id"],
                    "config_sha256": config_hash, "alias_config_sha256": alias_hash,
                    "collector_code_sha256": code_hash, "parser_code_sha256": parser_hash,
                    "network_request_ordinal_h41": ordinal, "source_identity": source_identity,
                    "source_url": url, "effective_url": effective_url, "attempt_number": 2,
                    "started_at_utc": started.isoformat().replace("+00:00", "Z"),
                    "completed_at_utc": completed_at.isoformat().replace("+00:00", "Z"),
                    "http_status": status, "curl_exit_code": curl_exit, "content_type": content_type,
                    "outcome": outcome, "body_filename": "release.txt", "body_byte_length": len(body),
                    "body_sha256": sha256_bytes(body), "safe_header_sha256": sha256_bytes(redacted_headers),
                    "parsed_release_date": parsed.release_date if parsed else None,
                    "parsed_reference_date": parsed.reference_date if parsed else None,
                    "parser_format": parsed.parser_format if parsed else None, "redacted_error": error,
                    "contains_credentials": False, "raw_unredacted_headers_preserved": False,
                }
                atomic_write(temporary / "safe_headers.txt", redacted_headers)
                atomic_write(temporary / "attempt.json", canonical_json(attempt))
                os.replace(temporary, final_dir)
                checkpoint["new_network_attempt_count"] += 1
                checkpoint["total_h41_network_request_count"] += 1
                checkpoint["last_updated_at_utc"] = completed_at.isoformat().replace("+00:00", "Z")
                if outcome != "SUCCESS_ALIAS_CORROBORATION":
                    checkpoint.update(status="STOPPED", failure_code=outcome)
                    atomic_write(checkpoint_path, canonical_json(checkpoint))
                    return checkpoint
                reconciliation = {
                    "schema_version": "1.0.0", "artifact_id": "ROLE5-H41-ALIAS-RECONCILIATION-20050305-001",
                    "classification": alias["classification"], "alias_config_sha256": alias_hash,
                    "parent_stopped_checkpoint_sha256": alias["parent_stopped_checkpoint_sha256"],
                    "source_index_identity": source_identity,
                    "canonical_body_release_date": parsed.release_date,
                    "canonical_reference_date": parsed.reference_date,
                    "availability_date_for_j0": parsed.release_date,
                    "root_body_sha256": alias["root_body_sha256"], "ascii_body_sha256": sha256_bytes(body),
                    "ascii_source_run_id": run_id,
                }
                reconciliation_path = namespace / "alias_reconciliations/source_index_identity=20050305/reconciliation.json"
                atomic_write(reconciliation_path, canonical_json(reconciliation))
                checkpoint["successful_new_body_count"] += 1
                checkpoint["completed_release_ids"].append(source_identity)
                checkpoint["last_completed_release_id"] = source_identity
                checkpoint["alias_reconciled_release_ids"] = [source_identity]
                checkpoint["alias_config_sha256"] = alias_hash
                checkpoint["status"] = "IN_PROGRESS"
                checkpoint["failed_release_id"] = None
                checkpoint["failure_code"] = None
                atomic_write(checkpoint_path, canonical_json(checkpoint))
            if checkpoint["status"] == "COMPLETE_RAW_SEQUENCE":
                return checkpoint
        else:
            checkpoint = {
                "schema_version": "1.0.0", "artifact_id": "ROLE5-H41-FULL-CHECKPOINT-001",
                "program_id": config["program_id"], "config_sha256": config_hash,
                "collector_code_sha256": code_hash, "parser_code_sha256": parser_hash,
                "status": "IN_PROGRESS", "identity_count": len(release_ids),
                "pilot_network_request_count": config["pilot_network_request_count"],
                "new_network_attempt_count": 0,
                "total_h41_network_request_count": config["pilot_network_request_count"],
                "cache_reuse_count": 0, "successful_new_body_count": 0, "retry_count": 0,
                "completed_release_ids": [], "cached_pilot_release_ids": sorted(cache),
                "last_completed_release_id": None, "failed_release_id": None, "failure_code": None,
            }
        verify_completed(namespace, checkpoint)
        completed_ids = set(checkpoint["completed_release_ids"])
        last_progress = time.monotonic()
        for identity in release_ids:
            if identity in completed_ids:
                continue
            if identity in cache:
                raw = Path(str(cache[identity]["path"])).read_bytes()
                if sha256_bytes(raw) != cache[identity]["body_sha256"]:
                    raise CollectionValidationError(f"H41 pilot cache changed: {identity}")
                checkpoint["cache_reuse_count"] += 1
                checkpoint["completed_release_ids"].append(identity)
                checkpoint["last_completed_release_id"] = identity
                checkpoint["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                atomic_write(checkpoint_path, canonical_json(checkpoint))
                completed_ids.add(identity)
                continue

            url = config["release_url_template"].format(release_yyyymmdd=identity)
            validate_url(url, config)
            for attempt_number in (1, 2):
                if checkpoint["total_h41_network_request_count"] >= config["hard_total_h41_request_ceiling"]:
                    checkpoint.update(status="STOPPED", failed_release_id=identity, failure_code="REQUEST_CEILING_REACHED")
                    atomic_write(checkpoint_path, canonical_json(checkpoint))
                    return checkpoint
                ordinal = checkpoint["total_h41_network_request_count"] + 1
                run_id = f"role5-h41-full-{ordinal:04d}-{identity}-a{attempt_number}"
                release_dir = namespace / f"release_date={identity[:4]}-{identity[4:6]}-{identity[6:]}"
                final_dir = release_dir / f"source_run={run_id}"
                temporary = release_dir / f".{run_id}.tmp"
                if final_dir.exists() or temporary.exists():
                    raise CollectionValidationError(f"Immutable H41 source-run path collision: {run_id}")
                temporary.mkdir(parents=True, exist_ok=False)
                body_path = temporary / "release.html"
                raw_headers = temporary / ".raw_headers.tmp"
                started = datetime.now(timezone.utc)
                monotonic_started = time.monotonic()
                status, effective_url, content_type, curl_exit = curl_request(url, raw_headers, body_path, config)
                body = body_path.read_bytes() if body_path.exists() else b""
                header_raw = raw_headers.read_bytes() if raw_headers.exists() else b""
                redacted_headers, header_values = safe_headers(header_raw)
                raw_headers.unlink(missing_ok=True)
                outcome = "STOP_REDIRECT_OUTSIDE_FROZEN_HOST" if effective_url != url else classify(status, body, attempt_number, config)
                parsed = None
                error = ""
                if outcome == "SUCCESS":
                    try:
                        parsed = parse_h41(body)
                        if parsed.release_date.replace("-", "") != identity:
                            raise CollectionValidationError("H41 declared release date mismatches source identity")
                        if not (config["first_reference_date"] <= parsed.reference_date <= config["last_reference_date"]):
                            raise CollectionValidationError("H41 parsed reference date outside frozen range")
                    except Exception as exc:
                        outcome = "STOP_PARSER_OR_SOURCE_IDENTITY_UNRESOLVED"
                        error = f"{type(exc).__name__}: {exc}"[:500]
                completed_at = datetime.now(timezone.utc)
                attempt = {
                    "schema_version": "1.0.0", "source_run_id": run_id,
                    "program_id": config["program_id"], "config_sha256": config_hash,
                    "collector_code_sha256": code_hash, "parser_code_sha256": parser_hash,
                    "network_request_ordinal_h41": ordinal, "source_identity": identity,
                    "source_url": url, "effective_url": effective_url, "attempt_number": attempt_number,
                    "started_at_utc": started.isoformat().replace("+00:00", "Z"),
                    "completed_at_utc": completed_at.isoformat().replace("+00:00", "Z"),
                    "http_status": status, "curl_exit_code": curl_exit, "content_type": content_type,
                    "outcome": outcome, "body_filename": "release.html", "body_byte_length": len(body),
                    "body_sha256": sha256_bytes(body), "safe_header_sha256": sha256_bytes(redacted_headers),
                    "parsed_release_date": parsed.release_date if parsed else None,
                    "parsed_reference_date": parsed.reference_date if parsed else None,
                    "parser_format": parsed.parser_format if parsed else None, "redacted_error": error,
                    "contains_credentials": False, "raw_unredacted_headers_preserved": False,
                }
                atomic_write(temporary / "safe_headers.txt", redacted_headers)
                atomic_write(temporary / "attempt.json", canonical_json(attempt))
                os.replace(temporary, final_dir)
                checkpoint["new_network_attempt_count"] += 1
                checkpoint["total_h41_network_request_count"] += 1
                checkpoint["last_updated_at_utc"] = completed_at.isoformat().replace("+00:00", "Z")
                if outcome == "SUCCESS":
                    checkpoint["successful_new_body_count"] += 1
                    checkpoint["completed_release_ids"].append(identity)
                    checkpoint["last_completed_release_id"] = identity
                    checkpoint["failed_release_id"] = None
                    checkpoint["failure_code"] = None
                    completed_ids.add(identity)
                    atomic_write(checkpoint_path, canonical_json(checkpoint))
                    elapsed = time.monotonic() - monotonic_started
                    if elapsed < config["minimum_pacing_seconds"]:
                        time.sleep(config["minimum_pacing_seconds"] - elapsed)
                    break
                if outcome == "RETRY":
                    checkpoint["retry_count"] += 1
                    atomic_write(checkpoint_path, canonical_json(checkpoint))
                    time.sleep(retry_delay(header_values, config))
                    continue
                checkpoint.update(status="STOPPED", failed_release_id=identity, failure_code=outcome)
                atomic_write(checkpoint_path, canonical_json(checkpoint))
                return checkpoint

            now = time.monotonic()
            if checkpoint["new_network_attempt_count"] % config["progress_every_requests"] == 0 or now - last_progress > 60:
                print(json.dumps({
                    "status": "IN_PROGRESS", "completed": len(completed_ids), "identity_count": len(release_ids),
                    "total_requests": checkpoint["total_h41_network_request_count"],
                    "last_identity": checkpoint["last_completed_release_id"],
                }, sort_keys=True), flush=True)
                last_progress = now

        checkpoint.update(status="COMPLETE_RAW_SEQUENCE", failed_release_id=None, failure_code=None)
        checkpoint["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        atomic_write(checkpoint_path, canonical_json(checkpoint))
        return checkpoint


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = collect(args.repo_root.resolve())
    print(json.dumps({
        "status": result["status"], "completed": len(result["completed_release_ids"]),
        "identity_count": result["identity_count"], "total_requests": result["total_h41_network_request_count"],
        "retries": result["retry_count"], "failure_code": result["failure_code"],
    }, sort_keys=True))
    if result["status"] != "COMPLETE_RAW_SEQUENCE":
        raise SystemExit(2)


if __name__ == "__main__":
    main()

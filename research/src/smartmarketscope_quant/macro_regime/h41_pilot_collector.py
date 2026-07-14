from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .h6_full_collector import atomic_write, canonical_json, classify, safe_headers
from .historical_collector import CollectionValidationError, sha256_bytes


CONFIG_PATH = Path("research/config/macro_regime_h41_pilot.json")
CONFIG_HASH_PATH = Path("research/config/macro_regime_h41_pilot.sha256")
H6_MANIFEST_PATH = Path("research/artifacts/macro_regime/role5/ROLE5_H6_FULL_NORMALIZED_MANIFEST.json")


def load_config(repo_root: Path) -> tuple[dict[str, object], str]:
    raw = (repo_root / CONFIG_PATH).read_bytes()
    actual = sha256_bytes(raw)
    expected = (repo_root / CONFIG_HASH_PATH).read_text(encoding="ascii").split()[0]
    if actual != expected:
        raise CollectionValidationError("Frozen H41 pilot config hash mismatch")
    config = json.loads(raw)
    h6_raw = (repo_root / H6_MANIFEST_PATH).read_bytes()
    if sha256_bytes(h6_raw) != config["parent_h6_normalized_manifest_sha256"]:
        raise CollectionValidationError("H41 pilot parent H6 manifest mismatch")
    h6 = json.loads(h6_raw)
    if h6["decision"] != config["required_parent_h6_decision"]:
        raise CollectionValidationError("H6 prerequisite decision has not passed")
    return config, actual


def validate_url(url: str, config: dict[str, object]) -> None:
    parsed = urlparse(url)
    path_ok = parsed.path in {"/releases/h41/default.htm", "/releases/h41/releaseDates.json"} or bool(
        re.fullmatch(r"/releases/h41/\d{8}/", parsed.path)
    )
    if (
        parsed.scheme != config["official_scheme"]
        or parsed.hostname != config["official_host"]
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not path_ok
    ):
        raise CollectionValidationError(f"URL outside frozen H41 pilot route: {url}")


def request(url: str, header_path: Path, body_path: Path, config: dict[str, object]) -> tuple[int, str, str, int]:
    command = [
        "/usr/bin/curl", "--silent", "--show-error", "--proto", "=https",
        "--connect-timeout", "15", "--max-time", "45", "--max-redirs", "0",
        "--user-agent", "SmartMarketScope-Research-H41/1.0",
        "--dump-header", str(header_path), "--output", str(body_path),
        "--write-out", "%{http_code}\n%{url_effective}\n%{content_type}\n", url,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    parts = result.stdout.splitlines()
    status = int(parts[0]) if parts and parts[0].isdigit() else 0
    return status, parts[1] if len(parts) > 1 else url, parts[2] if len(parts) > 2 else "", result.returncode


def release_identities(raw: bytes, cutoff: str) -> list[str]:
    payload = json.loads(raw)
    values = sorted({
        value[:8]
        for year in payload
        for month in year["Months"]
        for value in month["Dates"]
        if value[:8] <= cutoff.replace("-", "")
    })
    if not values or any(not re.fullmatch(r"\d{8}", value) for value in values):
        raise CollectionValidationError("H41 releaseDates index has no valid dated identities")
    return values


def nearest(identities: list[str], target: str) -> str:
    return min(identities, key=lambda value: abs((datetime.strptime(value, "%Y%m%d") - datetime.strptime(target, "%Y%m%d")).days))


def collect(repo_root: Path) -> dict[str, object]:
    config, config_hash = load_config(repo_root)
    raw_root = Path(config["storage_policy"]["private_raw_root"])
    namespace = raw_root / config["storage_policy"]["pilot_namespace"]
    checkpoint_path = namespace / "checkpoint.json"
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="ascii"))
        if checkpoint["config_sha256"] != config_hash:
            raise CollectionValidationError("H41 checkpoint belongs to another config")
        if checkpoint["status"] != "IN_PROGRESS":
            return checkpoint
    else:
        checkpoint = {
            "schema_version": "1.0.0", "artifact_id": "ROLE5-H41-PILOT-CHECKPOINT-001",
            "program_id": config["program_id"], "config_sha256": config_hash,
            "status": "IN_PROGRESS", "network_request_count": 0, "retry_count": 0,
            "successful_raw_body_count": 0, "request_ledger": [], "release_identities": [],
            "sampled_release_identities": [], "failure_code": None,
        }

    urls: list[tuple[str, str]] = [
        ("ARCHIVE_INDEX", "https://www.federalreserve.gov/releases/h41/default.htm"),
        ("RELEASE_DATE_INDEX", "https://www.federalreserve.gov/releases/h41/releaseDates.json"),
    ]
    identities: list[str] = []
    while urls:
        kind, url = urls.pop(0)
        validate_url(url, config)
        if checkpoint["network_request_count"] >= config["request_ceiling"]:
            checkpoint.update(status="STOPPED", failure_code="REQUEST_CEILING_REACHED")
            atomic_write(checkpoint_path, canonical_json(checkpoint))
            return checkpoint
        ordinal = checkpoint["network_request_count"] + 1
        identity = re.search(r"/(\d{8})/", url)
        label = identity.group(1) if identity else kind.lower()
        final_dir = namespace / f"request={ordinal:02d}-{label}"
        temporary = namespace / f".request={ordinal:02d}-{label}.tmp"
        if final_dir.exists() or temporary.exists():
            raise CollectionValidationError(f"Immutable H41 pilot request path collision: {ordinal}")
        temporary.mkdir(parents=True, exist_ok=False)
        body_path = temporary / ("releaseDates.json" if kind == "RELEASE_DATE_INDEX" else "body.html")
        raw_headers = temporary / ".raw_headers.tmp"
        started = datetime.now(timezone.utc)
        monotonic_started = time.monotonic()
        status, effective_url, content_type, curl_exit = request(url, raw_headers, body_path, config)
        body = body_path.read_bytes() if body_path.exists() else b""
        header_bytes = raw_headers.read_bytes() if raw_headers.exists() else b""
        redacted_headers, _ = safe_headers(header_bytes)
        raw_headers.unlink(missing_ok=True)
        outcome = "STOP_REDIRECT_OUTSIDE_FROZEN_HOST" if effective_url != url else classify(status, body, 1, config)
        completed = datetime.now(timezone.utc)
        attempt = {
            "schema_version": "1.0.0", "ordinal": ordinal, "kind": kind,
            "source_url": url, "effective_url": effective_url, "http_status": status,
            "curl_exit_code": curl_exit, "content_type": content_type, "outcome": outcome,
            "started_at_utc": started.isoformat().replace("+00:00", "Z"),
            "completed_at_utc": completed.isoformat().replace("+00:00", "Z"),
            "body_filename": body_path.name, "body_byte_length": len(body),
            "body_sha256": sha256_bytes(body), "safe_header_sha256": sha256_bytes(redacted_headers),
            "contains_credentials": False, "raw_unredacted_headers_preserved": False,
        }
        atomic_write(temporary / "safe_headers.txt", redacted_headers)
        atomic_write(temporary / "attempt.json", canonical_json(attempt))
        os.replace(temporary, final_dir)
        checkpoint["network_request_count"] += 1
        checkpoint["request_ledger"].append(attempt)
        checkpoint["last_updated_at_utc"] = completed.isoformat().replace("+00:00", "Z")
        if outcome != "SUCCESS":
            checkpoint.update(status="STOPPED", failure_code=outcome)
            atomic_write(checkpoint_path, canonical_json(checkpoint))
            return checkpoint
        checkpoint["successful_raw_body_count"] += 1
        if kind == "RELEASE_DATE_INDEX":
            try:
                identities = release_identities(body, str(config["availability_cutoff_date"]))
            except Exception as exc:
                checkpoint.update(status="STOPPED", failure_code=f"RELEASE_DATE_INDEX_PARSE_FAILED:{type(exc).__name__}")
                atomic_write(checkpoint_path, canonical_json(checkpoint))
                return checkpoint
            checkpoint["release_identities"] = identities
            samples = sorted({
                identities[0], nearest(identities, "20080918"), nearest(identities, "20140102"),
                nearest(identities, "20200319"), identities[-1],
            })
            checkpoint["sampled_release_identities"] = samples
            urls.extend(("PILOT_RELEASE", f"https://www.federalreserve.gov/releases/h41/{item}/") for item in samples)
        atomic_write(checkpoint_path, canonical_json(checkpoint))
        elapsed = time.monotonic() - monotonic_started
        if elapsed < config["minimum_pacing_seconds"]:
            time.sleep(config["minimum_pacing_seconds"] - elapsed)

    checkpoint.update(status="PILOT_RAW_COMPLETE", failure_code=None)
    atomic_write(checkpoint_path, canonical_json(checkpoint))
    return checkpoint


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = collect(args.repo_root.resolve())
    print(json.dumps({
        "status": result["status"], "requests": result["network_request_count"],
        "successful_bodies": result["successful_raw_body_count"],
        "release_identity_count": len(result["release_identities"]),
        "samples": result["sampled_release_identities"], "failure_code": result["failure_code"],
    }, sort_keys=True))
    if result["status"] != "PILOT_RAW_COMPLETE":
        raise SystemExit(2)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from .h6_full_collector import atomic_write, canonical_json, classify, safe_headers
from .h41_pilot_collector import CONFIG_PATH, CONFIG_HASH_PATH, load_config, request, validate_url
from .historical_collector import CollectionValidationError, parse_release, sha256_bytes


RECONCILIATION_PATH = Path("research/config/macro_regime_h41_pilot_scope_reconciliation.json")
RECONCILIATION_HASH_PATH = Path("research/config/macro_regime_h41_pilot_scope_reconciliation.sha256")
RESUME_PATH = Path("research/config/macro_regime_h41_pilot_scope_resume.json")
RESUME_HASH_PATH = Path("research/config/macro_regime_h41_pilot_scope_resume.sha256")


def frozen(repo_root: Path, data_path: Path, hash_path: Path) -> tuple[dict[str, object], str]:
    raw = (repo_root / data_path).read_bytes()
    actual = sha256_bytes(raw)
    expected = (repo_root / hash_path).read_text(encoding="ascii").split()[0]
    if actual != expected:
        raise CollectionValidationError(f"Frozen hash mismatch: {data_path}")
    return json.loads(raw), actual


def resume(repo_root: Path) -> dict[str, object]:
    config, config_hash = load_config(repo_root)
    reconciliation, reconciliation_hash = frozen(repo_root, RECONCILIATION_PATH, RECONCILIATION_HASH_PATH)
    resume_config, resume_hash = frozen(repo_root, RESUME_PATH, RESUME_HASH_PATH)
    if reconciliation["parent_pilot_config_sha256"] != config_hash:
        raise CollectionValidationError("Scope reconciliation parent config mismatch")
    if resume_config["parent_scope_reconciliation_sha256"] != reconciliation_hash:
        raise CollectionValidationError("Scope resume parent reconciliation mismatch")
    collector_hash = sha256_bytes((repo_root / "research/src/smartmarketscope_quant/macro_regime/h41_pilot_collector.py").read_bytes())
    resume_code_hash = sha256_bytes((repo_root / "research/src/smartmarketscope_quant/macro_regime/h41_pilot_scope_resume.py").read_bytes())
    if collector_hash != resume_config["initial_collector_code_sha256"] or resume_code_hash != resume_config["resume_code_sha256"]:
        raise CollectionValidationError("H41 pilot code hash mismatch")

    raw_root = Path(config["storage_policy"]["private_raw_root"])
    namespace = raw_root / config["storage_policy"]["pilot_namespace"]
    checkpoint_path = namespace / "checkpoint.json"
    checkpoint_raw = checkpoint_path.read_bytes()
    if sha256_bytes(checkpoint_raw) != reconciliation["parent_terminal_checkpoint_sha256"]:
        raise CollectionValidationError("Scope resume checkpoint differs from frozen failed-first parent")
    checkpoint = json.loads(checkpoint_raw)
    if checkpoint["status"] != "PILOT_RAW_COMPLETE" or checkpoint["network_request_count"] != 7:
        raise CollectionValidationError("Scope resume requires the exact seven-request pilot parent")
    if checkpoint["request_ledger"][2]["body_sha256"] != reconciliation["defective_body_sha256"]:
        raise CollectionValidationError("Out-of-scope failed-first body lineage mismatch")

    url = str(reconciliation["next_network_request_url"])
    validate_url(url, config)
    ordinal = int(reconciliation["next_network_request_ordinal"])
    final_dir = namespace / f"request={ordinal:02d}-{reconciliation['corrected_first_release_identity']}"
    temporary = namespace / f".request={ordinal:02d}-{reconciliation['corrected_first_release_identity']}.tmp"
    if final_dir.exists() or temporary.exists():
        raise CollectionValidationError("Immutable H41 corrected pilot request path collision")
    temporary.mkdir(parents=True, exist_ok=False)
    body_path = temporary / "body.html"
    raw_headers = temporary / ".raw_headers.tmp"
    started = datetime.now(timezone.utc)
    monotonic_started = time.monotonic()
    status, effective_url, content_type, curl_exit = request(url, raw_headers, body_path, config)
    body = body_path.read_bytes() if body_path.exists() else b""
    header_raw = raw_headers.read_bytes() if raw_headers.exists() else b""
    redacted_headers, _ = safe_headers(header_raw)
    raw_headers.unlink(missing_ok=True)
    outcome = "STOP_REDIRECT_OUTSIDE_FROZEN_HOST" if effective_url != url else classify(status, body, 1, config)
    validation: dict[str, object] = {}
    parse_error = ""
    if outcome == "SUCCESS":
        text = re.sub(r"<[^>]+>", " ", body.decode("utf-8", errors="replace"))
        release_match = re.search(r"Release Date:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", text, re.I)
        reference_match = re.search(r"Wednesday\s+Dec(?:ember|\.)?\s+18,?\s+2002", text, re.I)
        validation = {
            "release_date_text": release_match.group(1) if release_match else None,
            "expected_reference_date_present": bool(reference_match),
        }
        if not release_match or release_match.group(1).lower() != "december 19, 2002" or not reference_match:
            outcome = "STOP_CORRECTION_VALIDATION_FAILED"
            parse_error = "Corrected earliest H41 release/reference identity failed"
    completed = datetime.now(timezone.utc)
    attempt = {
        "schema_version": "1.0.0", "ordinal": ordinal, "kind": "PILOT_RELEASE_SCOPE_CORRECTION",
        "source_url": url, "effective_url": effective_url, "http_status": status,
        "curl_exit_code": curl_exit, "content_type": content_type, "outcome": outcome,
        "started_at_utc": started.isoformat().replace("+00:00", "Z"),
        "completed_at_utc": completed.isoformat().replace("+00:00", "Z"),
        "body_filename": body_path.name, "body_byte_length": len(body), "body_sha256": sha256_bytes(body),
        "safe_header_sha256": sha256_bytes(redacted_headers), "redacted_error": parse_error,
        "validation": validation, "pilot_config_sha256": config_hash,
        "scope_reconciliation_sha256": reconciliation_hash, "scope_resume_config_sha256": resume_hash,
        "collector_code_sha256": collector_hash, "resume_code_sha256": resume_code_hash,
        "contains_credentials": False, "raw_unredacted_headers_preserved": False,
    }
    atomic_write(temporary / "safe_headers.txt", redacted_headers)
    atomic_write(temporary / "attempt.json", canonical_json(attempt))
    os.replace(temporary, final_dir)
    checkpoint["network_request_count"] += 1
    checkpoint["successful_raw_body_count"] += int(outcome == "SUCCESS")
    checkpoint["request_ledger"].append(attempt)
    checkpoint["scope_reconciliation_sha256"] = reconciliation_hash
    checkpoint["scope_resume_config_sha256"] = resume_hash
    checkpoint["excluded_out_of_scope_release_identities"] = [reconciliation["defective_source_identity"]]
    checkpoint["sampled_release_identities"] = [
        reconciliation["corrected_first_release_identity"], *reconciliation["cached_valid_pilot_identities"]
    ]
    checkpoint["last_updated_at_utc"] = completed.isoformat().replace("+00:00", "Z")
    checkpoint["failure_code"] = None if outcome == "SUCCESS" else outcome
    checkpoint["status"] = "PILOT_RAW_COMPLETE_SCOPE_CORRECTED" if outcome == "SUCCESS" else "STOPPED"
    atomic_write(checkpoint_path, canonical_json(checkpoint))
    elapsed = time.monotonic() - monotonic_started
    if elapsed < config["minimum_pacing_seconds"]:
        time.sleep(config["minimum_pacing_seconds"] - elapsed)
    return checkpoint


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = resume(args.repo_root.resolve())
    print(json.dumps({"status": result["status"], "requests": result["network_request_count"], "failure_code": result["failure_code"]}, sort_keys=True))
    if result["status"] != "PILOT_RAW_COMPLETE_SCOPE_CORRECTED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()

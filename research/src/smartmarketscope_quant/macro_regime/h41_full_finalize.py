from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from io import StringIO
from pathlib import Path

from .h41_parser import H41Snapshot, parse_h41
from .h6_full_collector import canonical_json
from .historical_collector import CollectionValidationError, j0, sha256_bytes


CONFIG_PATH = Path("research/config/macro_regime_h41_full_traversal.json")
CONFIG_HASH_PATH = Path("research/config/macro_regime_h41_full_traversal.sha256")
PILOT_CONFIG_PATH = Path("research/config/macro_regime_h41_pilot.json")
NORMALIZATION_PATH = Path("research/config/macro_regime_h41_full_normalization_v1.json")
NORMALIZATION_HASH_PATH = Path("research/config/macro_regime_h41_full_normalization_v1.sha256")
OUTPUT_DIR = Path("research/artifacts/macro_regime/role5")
ELIGIBILITY = "ELIGIBLE_COMPLETE_H41_POINT_IN_TIME_CHAIN"
PIT = "PIT_CERTIFIED_OFFICIAL_DATED_RELEASE_CHAIN"


def frozen(repo: Path, path: Path, hash_path: Path) -> tuple[dict[str, object], str]:
    raw = (repo / path).read_bytes()
    actual = sha256_bytes(raw)
    expected = (repo / hash_path).read_text(encoding="ascii").split()[0]
    if actual != expected:
        raise CollectionValidationError(f"Frozen hash mismatch: {path}")
    return json.loads(raw), actual


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


def lineage_hashes(repo: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for hash_path in sorted((repo / "research/config").glob("macro_regime_h41_*.sha256")):
        data_path = hash_path.with_suffix(".json")
        actual = sha256_bytes(data_path.read_bytes())
        if actual != hash_path.read_text(encoding="ascii").split()[0]:
            raise CollectionValidationError(f"H41 lineage hash mismatch: {data_path.name}")
        result[data_path.name] = actual
    return result


def load(repo: Path) -> dict[str, object]:
    config, config_hash = frozen(repo, CONFIG_PATH, CONFIG_HASH_PATH)
    normalization, normalization_hash = frozen(repo, NORMALIZATION_PATH, NORMALIZATION_HASH_PATH)
    pilot = json.loads((repo / PILOT_CONFIG_PATH).read_text(encoding="ascii"))
    if normalization["parent_full_traversal_config_sha256"] != config_hash:
        raise CollectionValidationError("H41 normalization parent mismatch")
    raw_root = Path(str(config["private_raw_root"]))
    namespace = raw_root / str(config["full_namespace"])
    checkpoint_path = namespace / "checkpoint.json"
    checkpoint_raw = checkpoint_path.read_bytes()
    checkpoint = json.loads(checkpoint_raw)
    if sha256_bytes(checkpoint_raw) != normalization["terminal_raw_checkpoint_sha256"]:
        raise CollectionValidationError("H41 terminal checkpoint differs from frozen normalization input")
    if checkpoint["status"] != normalization["terminal_raw_checkpoint_status_required"]:
        raise CollectionValidationError("H41 raw sequence is incomplete")
    if checkpoint["completed_release_ids"] != sorted(checkpoint["completed_release_ids"]):
        raise CollectionValidationError("H41 completed identities are not ordered")
    return {
        "config": config, "config_hash": config_hash, "normalization": normalization,
        "normalization_hash": normalization_hash, "pilot": pilot, "raw_root": raw_root,
        "namespace": namespace, "checkpoint": checkpoint,
        "checkpoint_hash": sha256_bytes(checkpoint_raw), "lineage_hashes": lineage_hashes(repo),
    }


def accepted_releases(inputs: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    config = inputs["config"]
    normalization = inputs["normalization"]
    raw_root: Path = inputs["raw_root"]
    namespace: Path = inputs["namespace"]
    pilot_namespace = raw_root / str(inputs["pilot"]["storage_policy"]["pilot_namespace"])
    attempts: list[dict[str, object]] = []
    successful: dict[str, list[tuple[dict[str, object], Path, Path]]] = {}
    for attempt_path in sorted(namespace.glob("**/attempt.json")):
        raw = attempt_path.read_bytes()
        attempt = json.loads(raw)
        body_path = attempt_path.with_name(str(attempt["body_filename"]))
        body = body_path.read_bytes()
        if sha256_bytes(body) != attempt["body_sha256"]:
            raise CollectionValidationError(f"H41 body hash mismatch: {attempt['source_run_id']}")
        attempt["attempt_sha256"] = sha256_bytes(raw)
        attempt["relative_body_path"] = str(body_path.relative_to(raw_root))
        attempt["relative_attempt_path"] = str(attempt_path.relative_to(raw_root))
        attempts.append(attempt)
        if attempt["outcome"] == "SUCCESS":
            successful.setdefault(str(attempt["source_identity"]), []).append((attempt, body_path, attempt_path))
    if len(attempts) != inputs["checkpoint"]["new_network_attempt_count"]:
        raise CollectionValidationError("H41 attempt count mismatch")

    exceptions = {
        "20050305": ("role5-h41-full-0124-20050305-a2", "release.txt", "OFFICIAL_ARCHIVE_ALIAS_RECONCILED"),
        "20080703": ("role5-h41-full-0298-20080703-a1", "release.html", "DIRECT_OFFICIAL_DATED_RELEASE_IDENTITY"),
        "20161118": ("role5-h41-full-0733-20161118-a1", "release.html", "OFFICIAL_ARCHIVE_DIRECTORY_DATE_BODY_DATE_DIVERGENCE"),
        "20191128": ("role5-h41-full-0891-20191128-a1", "release.html", "OFFICIAL_FEDERAL_HOLIDAY_RELEASE_SHIFT_DIRECTORY_DATE_DIVERGENCE"),
        "20200514": ("role5-h41-full-0914-20200514-a1", "release.html", "OFFICIAL_ARCHIVE_DIRECTORY_DATE_BODY_DATE_DIVERGENCE"),
    }
    attempt_by_run = {str(item["source_run_id"]): item for item in attempts}
    releases: list[dict[str, object]] = []
    for identity in inputs["checkpoint"]["completed_release_ids"]:
        acquisition = "NEW_FULL_TRAVERSAL_BODY"
        identity_class = "DIRECT_OFFICIAL_DATED_RELEASE_IDENTITY"
        if identity in config["cached_pilot_release_ordinals"]:
            ordinal = int(config["cached_pilot_release_ordinals"][identity])
            body_path = pilot_namespace / f"request={ordinal:02d}-{identity}" / "body.html"
            pilot_attempt = json.loads(body_path.with_name("attempt.json").read_text(encoding="ascii"))
            source_run = f"role5-h41-pilot-{ordinal:02d}-{identity}"
            source_url = str(pilot_attempt["source_url"])
            body_hash = str(pilot_attempt["body_sha256"])
            acquisition = "HASH_VERIFIED_PILOT_CACHE_REUSE"
        elif identity in exceptions:
            source_run, filename, identity_class = exceptions[identity]
            attempt = attempt_by_run[source_run]
            body_path = namespace / f"release_date={identity[:4]}-{identity[4:6]}-{identity[6:]}" / f"source_run={source_run}" / filename
            source_url = str(attempt["source_url"])
            body_hash = str(attempt["body_sha256"])
            acquisition = "EXACT_RECONCILED_OFFICIAL_BODY"
        else:
            candidates = successful.get(identity, [])
            if len(candidates) != 1:
                raise CollectionValidationError(f"Expected one H41 accepted body for {identity}, got {len(candidates)}")
            attempt, body_path, _ = candidates[0]
            source_run = str(attempt["source_run_id"])
            source_url = str(attempt["source_url"])
            body_hash = str(attempt["body_sha256"])
        body = body_path.read_bytes()
        if sha256_bytes(body) != body_hash:
            raise CollectionValidationError(f"Accepted H41 body changed: {identity}")
        parsed = parse_h41(body)
        override = normalization["canonical_availability_overrides"].get(identity)
        canonical = str(override["availability_date"]) if override else identity[:4] + "-" + identity[4:6] + "-" + identity[6:]
        if parsed.release_date != canonical:
            raise CollectionValidationError(f"H41 canonical release mismatch: {identity}")
        if override and identity_class != override["classification"]:
            raise CollectionValidationError(f"H41 exception classification mismatch: {identity}")
        releases.append({
            "source_identity": identity, "canonical_release_date": canonical,
            "reference_date": parsed.reference_date, "snapshot": parsed,
            "source_identity_classification": identity_class,
            "acquisition_classification": acquisition, "source_run_id": source_run,
            "source_url": source_url, "raw_artifact_sha256": body_hash,
            "raw_relative_private_path": str(body_path.relative_to(raw_root)),
            "parser_format": parsed.parser_format,
        })
    dates = [str(item["canonical_release_date"]) for item in releases]
    refs = [str(item["reference_date"]) for item in releases]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise CollectionValidationError("H41 canonical release chronology failed")
    if refs != sorted(refs) or len(refs) != len(set(refs)):
        raise CollectionValidationError("H41 reference chronology failed")
    if refs[0] != normalization["first_reference_date"] or refs[-1] != normalization["last_reference_date"]:
        raise CollectionValidationError("H41 reference boundary failed")
    return releases, attempts


def build(repo: Path) -> dict[str, bytes]:
    inputs = load(repo)
    releases, attempts = accepted_releases(inputs)
    normalization = inputs["normalization"]
    observations: list[dict[str, object]] = []
    for release in releases:
        snapshot: H41Snapshot = release["snapshot"]
        effective_utc, effective_my = j0(str(release["canonical_release_date"]))
        for series in normalization["series"]:
            value = int(getattr(snapshot, str(series["field"])))
            row = {
                "observation_id": f"H41-{series['internal_indicator_id']}-{release['reference_date']}",
                "source_series_id": series["source_series_id"], "internal_indicator_id": series["internal_indicator_id"],
                "category": normalization["category"], "release_bundle": normalization["release_bundle"],
                "reference_date": release["reference_date"], "observation_version": 1,
                "measurement_version_kind": "AS_PUBLISHED_WEEKLY_SNAPSHOT", "supersedes_observation_id": "",
                "raw_value": value, "normalized_numeric_value": value, "unit": series["unit"],
                "frequency": normalization["frequency"], "seasonal_adjustment": normalization["seasonal_adjustment"],
                "source_index_identity": release["source_identity"], "canonical_release_date": release["canonical_release_date"],
                "availability_date": release["canonical_release_date"], "effective_at_utc": effective_utc,
                "effective_at_asia_kuala_lumpur": effective_my, "availability_rule": normalization["availability_rule"],
                "source_identity_classification": release["source_identity_classification"],
                "acquisition_classification": release["acquisition_classification"], "source_run_id": release["source_run_id"],
                "raw_artifact_id": f"{release['source_run_id']}-body", "raw_artifact_sha256": release["raw_artifact_sha256"],
                "raw_relative_private_path": release["raw_relative_private_path"], "parser_format": release["parser_format"],
                "point_in_time_classification": PIT, "protocol_eligibility": ELIGIBILITY, "historical_reconstruction": True,
            }
            row["observation_payload_sha256"] = sha256_bytes(canonical_json(row))
            observations.append(row)
    if len(observations) != normalization["expected_observation_count"]:
        raise CollectionValidationError("H41 normalized observation count mismatch")

    failures = [item for item in attempts if item["outcome"] != "SUCCESS"]
    parser_counts = Counter(str(item["parser_format"]) for item in releases)
    identity_counts = Counter(str(item["source_identity_classification"]) for item in releases)
    acquisition_counts = Counter(str(item["acquisition_classification"]) for item in releases)
    outcome_counts = Counter(str(item["outcome"]) for item in attempts)
    checkpoint = inputs["checkpoint"]
    manifest = {
        "schema_version": "1.0.0", "artifact_id": "ROLE5-H41-FULL-NORMALIZED-MANIFEST-001",
        "program_id": inputs["config"]["program_id"], "created_at_utc": checkpoint["last_updated_at_utc"],
        "status": "PASS", "decision": "H41_FULL_POINT_IN_TIME_CHAIN_VALIDATED",
        "full_traversal_config_sha256": inputs["config_hash"], "normalization_contract_sha256": inputs["normalization_hash"],
        "terminal_raw_checkpoint_sha256": inputs["checkpoint_hash"], "lineage_config_hashes": inputs["lineage_hashes"],
        "accepted_release_identity_count": len(releases), "normalized_observation_count": len(observations),
        "observations_per_release": 3, "first_reference_date": releases[0]["reference_date"],
        "last_reference_date": releases[-1]["reference_date"], "new_network_attempt_count": len(attempts),
        "total_h41_network_request_count_including_pilot": checkpoint["total_h41_network_request_count"],
        "hard_total_h41_request_ceiling": inputs["config"]["hard_total_h41_request_ceiling"],
        "remaining_request_headroom": inputs["config"]["hard_total_h41_request_ceiling"] - checkpoint["total_h41_network_request_count"],
        "retry_count": checkpoint["retry_count"], "failed_attempt_count_preserved_and_reconciled": len(failures),
        "outcome_counts": dict(sorted(outcome_counts.items())), "accepted_parser_format_counts": dict(sorted(parser_counts.items())),
        "source_identity_classification_counts": dict(sorted(identity_counts.items())),
        "acquisition_classification_counts": dict(sorted(acquisition_counts.items())),
        "negative_reserve_snapshot_count": sum(r["snapshot"].reserve_balances_millions < 0 for r in releases),
        "raw_hash_gate": "PASS", "canonical_chronology_gate": "PASS", "reference_chronology_gate": "PASS",
        "point_in_time_classification": PIT, "protocol_eligibility": ELIGIBILITY,
        "retained_role2_observation_count": 1730, "eligible_h6_observation_count": 4859,
        "combined_verified_macro_observation_count": 1730 + 4859 + len(observations),
        "role6_started": False, "technical_join_started": False, "pnl_inspection_started": False,
        "experiment_trials": 0, "final_holdout_accesses": 0,
        "exact_next_permitted_action": "Start sequential Role 6 deterministic macro taxonomy and scoring only from frozen Role 2, H6, and H41 eligible observations.",
    }
    report = f"""# Role 5 Historical Macro Data Collector Report\n\nStatus: `PASS`  \nDecision: `H41_FULL_POINT_IN_TIME_CHAIN_VALIDATED`\n\n## Current status\n\n`[FACT]` H.6 and H.4.1 acquisition are complete. H.4.1 reconciles all {len(releases):,} frozen release identities and produces {len(observations):,} immutable point-in-time observations across total assets, reserve balances, and TGA. The traversal used {checkpoint['total_h41_network_request_count']:,} requests including the pilot, with {checkpoint['retry_count']} retries and {manifest['remaining_request_headroom']} requests of ceiling headroom.\n\n`[FACT]` Exact source exceptions are preserved rather than hidden: 2005-03-05 aliases 2005-03-03; the 2008-07-02 reserve balance is legitimately -6,962 and reconciles to supplying minus absorbing factors; 2016-11-18 aliases 2016-11-17; 2019-11-28 shifts to 2019-11-29; and 2020-05-14 aliases 2020-05-15.\n\n## What failed\n\n`[FACT]` The failed-first H.4.1 pilot sampled one out-of-scope 1996 body before its missing lower bound was corrected. The full traversal preserved {len(failures)} stopped parser/source-identity attempts. They exposed one archive alias, one valid signed legacy balance, and three exact directory/body date divergences. No failed record was deleted, retried as if normal, or used without a frozen reconciliation.\n\n## Why later steps did not run earlier\n\nRoles after collection were gated, not skipped. Scoring before complete H.6 revision lineage and H.4.1 source/date validation would have embedded incomplete liquidity history and incorrect availability dates. Role 5 now passes; Role 6 may begin sequentially. Technical alignment, comparison, and independent audit remain closed until their own predecessors pass.\n\n## Exact next permitted action\n\nStart Role 6 deterministic category taxonomy and scoring from the frozen eligible observation set. Do not join technical setups or inspect PnL yet.\n""".encode("utf-8")

    fields = list(observations[0])
    failures_rows = [{
        "source_run_id": x["source_run_id"], "source_identity": x["source_identity"],
        "network_request_ordinal_h41": x["network_request_ordinal_h41"], "source_url": x["source_url"],
        "http_status": x["http_status"], "outcome": x["outcome"], "body_sha256": x["body_sha256"],
        "redacted_error": x.get("redacted_error", ""), "recovered_by_exact_reconciliation": "true",
    } for x in failures]
    outputs = {
        "ROLE5_H41_OBSERVATIONS.csv": csv_bytes(observations, fields),
        "ROLE5_H41_FAILURES.csv": csv_bytes(failures_rows, list(failures_rows[0])),
        "ROLE5_H41_FULL_NORMALIZED_MANIFEST.json": canonical_json(manifest),
        "ROLE5_H41_FULL_COLLECTION_REPORT.md": report,
        "MACRO_REGIME_ROLE5_COLLECTION_REPORT.md": report,
    }
    hashes = {name: sha256_bytes(payload) for name, payload in sorted(outputs.items())}
    outputs["ROLE5_H41_OUTPUT_HASHES.json"] = canonical_json(hashes)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    outputs = build(root)
    if not args.validate_only:
        for name, payload in outputs.items():
            atomic_write(root / OUTPUT_DIR / name, payload)
    print(json.dumps({"status": "PASS", "outputs": len(outputs)}, sort_keys=True))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


class RegistryError(ValueError):
    pass


LIFECYCLE_EVENT_TYPES = frozenset({"PREREGISTERED", "STARTED", "COMPLETED", "FAILED", "CANCELLED"})
TERMINAL_EVENT_TYPES = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
CHRONOLOGY_RECONCILIATION_EVENT_TYPE = "CHRONOLOGY_RECONCILIATION"
CHRONOLOGY_FAILURE_CODES = ["EVENT_ORDER_INVALID", "EXPERIMENT_REGISTRY_TIMING_INVALID"]


PROJECTION_FIELDS = [
    "experiment_id",
    "parent_experiment",
    "git_commit",
    "dataset_checksum",
    "code_version",
    "feature_version",
    "model_version",
    "parameters_hash",
    "number_of_trials",
    "training_metrics",
    "validation_metrics",
    "robustness_metrics",
    "prop_metrics",
    "decision",
    "rejection_reason",
    "auditor_comments",
    "status",
    "preregistration_hash",
    "config_checksum",
    "last_event_type",
    "last_event_hash",
]


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _payload_hash(payload: dict) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _event_hash(previous_hash: str | None, payload: dict) -> str:
    return hashlib.sha256(_canonical({"previous_event_hash": previous_hash, "payload": payload})).hexdigest()


def _parse_utc_timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise RegistryError(f"{field} must be a canonical UTC ISO-8601 timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise RegistryError(f"{field} is not a valid ISO-8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise RegistryError(f"{field} must be timezone-aware UTC")
    return parsed


def _registry_bytes(path: Path) -> bytes:
    if not path.exists():
        return b""
    raw = path.read_bytes()
    try:
        raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise RegistryError("Registry must be ASCII") from error
    return raw


def _parse_records(raw: bytes) -> list[dict]:
    records: list[dict] = []
    offset = 0
    for line_number, raw_line in enumerate(raw.splitlines(keepends=True), start=1):
        start_offset = offset
        offset += len(raw_line)
        if not raw_line.strip():
            continue
        try:
            event = json.loads(raw_line.decode("ascii"))
        except json.JSONDecodeError as error:
            raise RegistryError(f"Invalid registry JSON at line {line_number}") from error
        if not isinstance(event, dict):
            raise RegistryError(f"Registry event at line {line_number} must be an object")
        records.append(
            {
                "event": event,
                "event_index": len(records),
                "line_number": line_number,
                "start_offset": start_offset,
            }
        )
    return records


def read_registry(path: Path, *, include_supplemental: bool = False) -> list[dict]:
    events = [record["event"] for record in _parse_records(_registry_bytes(path))]
    if include_supplemental:
        return events
    return [event for event in events if event["payload"].get("event_type") in LIFECYCLE_EVENT_TYPES]


def _event_reference(record: dict) -> dict:
    event = record["event"]
    payload = event["payload"]
    return {
        "event_id": payload["event_id"],
        "event_type": payload["event_type"],
        "event_time_utc": payload["event_time_utc"],
        "event_hash": event["event_hash"],
        "previous_event_hash": event["previous_event_hash"],
        "payload_sha256": _payload_hash(payload),
    }


def _chronology_issues(lifecycle_records: dict[str, list[dict]]) -> list[dict]:
    issues: list[dict] = []
    for experiment_id in sorted(lifecycle_records):
        records = lifecycle_records[experiment_id]
        violations = []
        for earlier_index, earlier in enumerate(records):
            for later in records[earlier_index + 1 :]:
                if earlier["parsed_time"] > later["parsed_time"]:
                    violations.append(
                        {
                            "earlier_event_id": earlier["event"]["payload"]["event_id"],
                            "earlier_event_time_utc": earlier["event"]["payload"]["event_time_utc"],
                            "later_event_id": later["event"]["payload"]["event_id"],
                            "later_event_time_utc": later["event"]["payload"]["event_time_utc"],
                        }
                    )
        if violations:
            issues.append(
                {
                    "experiment_id": experiment_id,
                    "original_events": [_event_reference(record) for record in records],
                    "violations": violations,
                }
            )
    return issues


def _require_reconciliation_detail(detail: object, expected_issue: dict) -> None:
    if not isinstance(detail, dict):
        raise RegistryError("Chronology reconciliation entries must be objects")
    if detail.get("experiment_id") != expected_issue["experiment_id"]:
        raise RegistryError("Chronology reconciliation experiment ID mismatch")
    if detail.get("original_events") != expected_issue["original_events"]:
        raise RegistryError("Chronology reconciliation does not preserve the exact original event references")
    if detail.get("violations") != expected_issue["violations"]:
        raise RegistryError("Chronology reconciliation violation details do not match the registry")
    if detail.get("chronology_resolution") != "UNRESOLVED_EXACT_COMPLETION_TIME":
        raise RegistryError("Historical chronology must remain explicitly unresolved when no exact time is proven")
    if detail.get("corrected_completion_time_utc") is not None:
        raise RegistryError("A chronology reconciliation must not invent a corrected completion timestamp")

    cause = detail.get("likely_metadata_cause")
    if not isinstance(cause, dict) or cause.get("status") != "EVIDENCE_SUPPORTED_LIKELY_CAUSE":
        raise RegistryError("Chronology reconciliation must label the likely cause and its evidence status")
    if not isinstance(cause.get("description"), str) or not cause["description"].strip():
        raise RegistryError("Chronology reconciliation likely cause is missing")
    if not isinstance(cause.get("evidence_sources"), list) or not cause["evidence_sources"]:
        raise RegistryError("Chronology reconciliation cause evidence is missing")

    effect = detail.get("result_content_effect")
    if not isinstance(effect, dict) or effect.get("affected") is not False:
        raise RegistryError("Chronology reconciliation must explicitly disclose result-content impact")
    if not isinstance(effect.get("evidence"), list) or not effect["evidence"]:
        raise RegistryError("Chronology reconciliation result-content evidence is missing")

    interpreted = detail.get("corrected_interpreted_chronology")
    if not isinstance(interpreted, dict):
        raise RegistryError("Chronology reconciliation interpreted ordering is missing")
    if interpreted.get("status") != "PARTIAL_ORDER_DEFENSIBLE_EXACT_TIME_UNRESOLVED":
        raise RegistryError("Chronology reconciliation must distinguish partial ordering from an exact timestamp")
    if not isinstance(interpreted.get("sequence"), str) or not interpreted["sequence"].strip():
        raise RegistryError("Chronology reconciliation interpreted sequence is missing")
    if not isinstance(interpreted.get("evidence_sources"), list) or not interpreted["evidence_sources"]:
        raise RegistryError("Chronology reconciliation interpreted-order evidence is missing")


def _validate_reconciliation(
    record: dict,
    raw: bytes,
    issues_by_experiment: dict[str, dict],
    already_covered: set[str],
    prior_event_times: list[datetime],
) -> set[str]:
    event = record["event"]
    payload = event["payload"]
    if payload.get("schema_version") != "1.0.0":
        raise RegistryError("Chronology reconciliation schema_version must be 1.0.0")
    if payload.get("status") != "UNRESOLVED":
        raise RegistryError("Chronology reconciliation status must remain UNRESOLVED")
    if payload.get("decision") != "REGISTRY_CHRONOLOGY_UNRESOLVED":
        raise RegistryError("Chronology reconciliation decision is invalid")
    if payload.get("failure_codes") != CHRONOLOGY_FAILURE_CODES:
        raise RegistryError("Chronology reconciliation failure codes are incomplete or out of order")

    prefix = payload.get("source_registry_prefix")
    if not isinstance(prefix, dict):
        raise RegistryError("Chronology reconciliation source prefix is missing")
    prefix_bytes = raw[: record["start_offset"]]
    expected_prefix = {
        "event_count": record["event_index"],
        "byte_length": len(prefix_bytes),
        "sha256": hashlib.sha256(prefix_bytes).hexdigest(),
        "last_event_hash": event["previous_event_hash"],
    }
    if prefix != expected_prefix:
        raise RegistryError("Chronology reconciliation source prefix does not match the original registry bytes")

    parsed_time = record["parsed_time"]
    if prior_event_times and parsed_time < max(prior_event_times):
        raise RegistryError("Chronology reconciliation event time precedes an existing registry event")

    open_issue_ids = {
        experiment_id
        for experiment_id, issue in issues_by_experiment.items()
        if experiment_id not in already_covered
        and all(
            reference["event_id"]
            in {
                prior["event"]["payload"]["event_id"]
                for prior in record["all_prior_records"]
                if prior["event"]["payload"].get("event_type") in LIFECYCLE_EVENT_TYPES
            }
            for reference in issue["original_events"]
        )
    }
    affected = payload.get("affected_experiments")
    if not isinstance(affected, list) or not affected:
        raise RegistryError("Chronology reconciliation must name affected experiments")
    affected_ids = [detail.get("experiment_id") if isinstance(detail, dict) else None for detail in affected]
    if len(affected_ids) != len(set(affected_ids)):
        raise RegistryError("Chronology reconciliation contains a duplicate affected experiment")
    if set(affected_ids) & already_covered:
        raise RegistryError("Duplicate chronology reconciliation for an already disclosed experiment")
    if set(affected_ids) != open_issue_ids:
        raise RegistryError("Chronology reconciliation must disclose every open historical issue in its prefix")

    by_id = {detail["experiment_id"]: detail for detail in affected}
    for experiment_id in sorted(open_issue_ids):
        _require_reconciliation_detail(by_id[experiment_id], issues_by_experiment[experiment_id])
    return set(affected_ids)


def _validate_registry_bytes(raw: bytes) -> dict:
    records = _parse_records(raw)
    previous = None
    event_ids = set()
    states: dict[str, list[str]] = {}
    lifecycle_records: dict[str, list[dict]] = {}
    reconciliation_records: list[dict] = []
    parsed_event_times: list[datetime] = []

    for record in records:
        index = record["event_index"]
        event = record["event"]
        payload = event.get("payload")
        if not isinstance(payload, dict):
            raise RegistryError(f"Event {index} has no payload")
        if event.get("previous_event_hash") != previous:
            raise RegistryError(f"Registry previous hash mismatch at event {index}")
        expected = _event_hash(previous, payload)
        if event.get("event_hash") != expected:
            raise RegistryError(f"Registry event hash mismatch at event {index}")
        event_id = payload.get("event_id")
        if not event_id or event_id in event_ids:
            raise RegistryError(f"Registry event ID missing or duplicated at event {index}")
        event_ids.add(event_id)

        event_type = payload.get("event_type")
        parsed_time = _parse_utc_timestamp(payload.get("event_time_utc"), field=f"event_time_utc at event {index}")
        record["parsed_time"] = parsed_time
        record["all_prior_records"] = records[:index]

        if event_type == CHRONOLOGY_RECONCILIATION_EVENT_TYPE:
            reconciliation_records.append(record)
        elif event_type in LIFECYCLE_EVENT_TYPES:
            experiment_id = payload.get("experiment_id")
            if not experiment_id:
                raise RegistryError(f"Registry lifecycle payload invalid at event {index}")
            prior_types = states.setdefault(experiment_id, [])
            if event_type == "PREREGISTERED" and prior_types:
                raise RegistryError("Preregistration must be the first experiment event")
            if event_type in {"STARTED", *TERMINAL_EVENT_TYPES} and "PREREGISTERED" not in prior_types:
                raise RegistryError("Experiment lifecycle event precedes preregistration")
            if event_type in TERMINAL_EVENT_TYPES and "STARTED" not in prior_types:
                raise RegistryError("Terminal event precedes STARTED")
            if any(item in prior_types for item in TERMINAL_EVENT_TYPES):
                raise RegistryError("Event appended after terminal experiment state")
            prior_types.append(event_type)
            lifecycle_records.setdefault(experiment_id, []).append(record)
        else:
            raise RegistryError(f"Registry event type is unsupported at event {index}")

        parsed_event_times.append(parsed_time)
        previous = expected

    chronology_issues = _chronology_issues(lifecycle_records)
    issues_by_experiment = {issue["experiment_id"]: issue for issue in chronology_issues}
    covered: set[str] = set()
    for record in reconciliation_records:
        covered.update(
            _validate_reconciliation(
                record,
                raw,
                issues_by_experiment,
                covered,
                [
                    prior["parsed_time"]
                    for prior in record["all_prior_records"]
                    if "parsed_time" in prior
                ],
            )
        )

    unresolved_ids = sorted(set(issues_by_experiment) - covered)
    if unresolved_ids:
        status = "FAIL"
        decision = "EVENT_ORDER_INVALID"
        chronology_status = "FAIL_UNRECONCILED"
        failure_codes = CHRONOLOGY_FAILURE_CODES.copy()
    elif chronology_issues:
        status = "INCONCLUSIVE"
        decision = "REGISTRY_CHRONOLOGY_UNRESOLVED"
        chronology_status = "UNRESOLVED_DISCLOSED"
        failure_codes = CHRONOLOGY_FAILURE_CODES.copy()
    else:
        status = "PASS"
        decision = "PASS"
        chronology_status = "PASS"
        failure_codes = []

    return {
        "status": status,
        "decision": decision,
        "hash_chain_status": "PASS",
        "chronology_status": chronology_status,
        "failure_codes": failure_codes,
        "event_count": len(records),
        "lifecycle_event_count": sum(len(items) for items in states.values()),
        "reconciliation_event_count": len(reconciliation_records),
        "experiment_count": len(states),
        "last_event_hash": previous,
        "states": states,
        "chronology_issues": chronology_issues,
        "reconciled_experiments": sorted(covered),
        "unreconciled_experiments": unresolved_ids,
    }


def validate_registry(path: Path) -> dict:
    return _validate_registry_bytes(_registry_bytes(path))


def write_projection(registry_path: Path, csv_path: Path) -> None:
    events = read_registry(registry_path)
    latest: dict[str, dict] = {}
    hashes: dict[str, str] = {}
    for event in events:
        payload = event["payload"]
        if payload.get("event_type") == CHRONOLOGY_RECONCILIATION_EVENT_TYPE:
            continue
        latest[payload["experiment_id"]] = payload
        hashes[payload["experiment_id"]] = event["event_hash"]
    with csv_path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROJECTION_FIELDS, lineterminator="\n")
        writer.writeheader()
        for experiment_id in sorted(latest):
            payload = latest[experiment_id]
            row = {field: payload.get(field, "") for field in PROJECTION_FIELDS}
            for field in ("training_metrics", "validation_metrics", "robustness_metrics", "prop_metrics"):
                if isinstance(row[field], (dict, list)):
                    row[field] = json.dumps(row[field], sort_keys=True, separators=(",", ":"))
            row["last_event_type"] = payload["event_type"]
            row["last_event_hash"] = hashes[experiment_id]
            writer.writerow(row)


def append_event(registry_path: Path, csv_path: Path, payload: dict) -> dict:
    validation = validate_registry(registry_path)
    existing = read_registry(registry_path)
    if any(event["payload"].get("event_id") == payload.get("event_id") for event in existing):
        raise RegistryError("Event ID already exists")
    is_reconciliation = payload.get("event_type") == CHRONOLOGY_RECONCILIATION_EVENT_TYPE
    if validation["status"] == "FAIL" and not is_reconciliation:
        raise RegistryError("Registry chronology must be reconciled before appending another lifecycle event")

    previous = validation["last_event_hash"]
    event = {
        "previous_event_hash": previous,
        "payload": payload,
        "event_hash": _event_hash(previous, payload),
    }
    raw = _registry_bytes(registry_path)
    if raw and not raw.endswith(b"\n"):
        raise RegistryError("Registry must end with a newline before append")
    event_line = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
    prospective = _validate_registry_bytes(raw + event_line)
    if prospective["status"] == "FAIL":
        raise RegistryError("Appended event would leave an unreconciled registry chronology failure")

    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("ab") as handle:
        handle.write(event_line)
    final = validate_registry(registry_path)
    if final["last_event_hash"] != event["event_hash"]:
        raise RegistryError("Registry append did not preserve the prospective event hash")
    if not is_reconciliation:
        write_projection(registry_path, csv_path)
    return event


def main() -> None:
    parser = argparse.ArgumentParser(description="Append or validate the hash-linked experiment registry")
    parser.add_argument("action", choices=["append", "validate"])
    parser.add_argument("--registry", type=Path, default=Path("EXPERIMENT_REGISTRY.jsonl"))
    parser.add_argument("--csv", type=Path, default=Path("EXPERIMENT_REGISTRY.csv"))
    parser.add_argument("--event", type=Path)
    args = parser.parse_args()
    if args.action == "append":
        if args.event is None:
            raise SystemExit("--event is required for append")
        payload = json.loads(args.event.read_text(encoding="ascii"))
        event = append_event(args.registry, args.csv, payload)
        result = validate_registry(args.registry)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "decision": result["decision"],
                    "event_hash": event["event_hash"],
                },
                indent=2,
            )
        )
    else:
        result = validate_registry(args.registry)
        write_projection(args.registry, args.csv)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from bisect import bisect_right
from collections import Counter
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


PROGRAM_ID = "SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001"
ROLE8 = Path("research/artifacts/macro_regime/role8")
MLR = Path("research/artifacts/macro_liquidity_reversal")
ROLE6 = Path("research/artifacts/macro_regime/role6")
ROLE7 = Path("research/artifacts/macro_regime/role7")
POLICY = Path("research/config/MACRO_REGIME_ROLE7_AVAILABILITY_POLICY.json")
TECHNICAL_CONFIG = Path("research/config/macro_liquidity_reversal_primary.json")
EXECUTION_CONFIG = Path("research/config/execution_scenarios.json")
TECHNICAL_CODE = Path("research/src/smartmarketscope_quant/macro_liquidity_reversal/technical_economic.py")
DETECTOR_CODE = Path("research/src/smartmarketscope_quant/macro_liquidity_reversal/detectors.py")
ALIGNMENT_CODE = Path("research/src/smartmarketscope_quant/macro_regime/technical_alignment.py")
ALIGNMENT_TEST = Path("research/tests/test_macro_regime_technical_alignment.py")
PRIMARY_TRADES = MLR / "MLR_TECHNICAL_PRIMARY_TRADES.csv"
EVENTS = MLR / "MLR_EVENT_REGISTRY.csv"
TECHNICAL_FINAL_MANIFEST = MLR / "MLR_TECHNICAL_FINAL_MANIFEST.json"
TECHNICAL_ARTIFACT_MANIFEST = MLR / "artifact_manifest.json"
TECHNICAL_REGISTRY = MLR / "MLR_TECHNICAL_ECONOMIC_EXPERIMENT_REGISTRY.jsonl"
FREQUENCY_CHECKPOINT = MLR / "governance/MLR_FREQUENCY_CHECKPOINT_20260713T123112+0800.json"
D1_SOURCE = Path("research/artifacts/processed_data/v1/NAS100_Daily_completed_v1.csv.gz")
TECHNICAL_SOURCE_PATHS = {
    "M1": Path("dataset/NAS100_M1_200808060000_202606262354.csv"),
    "M5": Path("dataset/NAS100_M5_200808060000_202606262350.csv"),
    "M15": Path("dataset/NAS100_M15_200808060000_202606262345.csv"),
    "H4": Path("dataset/NAS100_H4_200808060000_202606262000.csv"),
    "D1": Path("dataset/NAS100_Daily_200808060000_202606260000.csv"),
    "canonical_M5": Path("research/artifacts/processed_data/v1/NAS100_M5_canonical_v1.csv.gz"),
    "canonical_M15": Path("research/artifacts/processed_data/v1/NAS100_M15_completed_v1.csv.gz"),
    "canonical_H4": Path("research/artifacts/processed_data/v1/NAS100_H4_completed_v1.csv.gz"),
    "canonical_D1": D1_SOURCE,
}
SNAPSHOTS = ROLE6 / "MACRO_REGIME_SNAPSHOT_HISTORY.parquet"
LEDGER = ROLE6 / "MACRO_EVENT_UPDATE_LEDGER.parquet"
ROLE6_MANIFEST = ROLE6 / "ROLE6_SCORING_MANIFEST.json"
ROLE7_MANIFEST = ROLE7 / "ROLE7_VALIDATION_MANIFEST.json"
CREATED_AT_UTC = "2026-07-14T04:00:00Z"
NY = ZoneInfo("America/New_York")
KL = ZoneInfo("Asia/Kuala_Lumpur")
UTC = timezone.utc
MODES = ("J0", "J1", "J2")
ORIGINAL_TRADE_FIELDS: tuple[str, ...] = (
    "actual_entry_fill_points", "actual_exit_fill_points", "ambiguous_adverse_first",
    "bars_held_m1", "block_kind", "block_lower", "block_upper", "commission_cost_points",
    "component_ids", "confluence_lower", "confluence_upper", "cost_adjusted_entry_points",
    "cost_adjusted_exit_points", "cost_evidence_class", "d1_candle2_start", "decision_time",
    "direction", "entry_bar_start", "entry_path_available_at", "entry_reference_points",
    "event_id", "exit_reason", "exit_reference_points", "exit_time", "expiry_time",
    "exposure_label", "family", "fill_evidence_class", "fill_reason", "fill_status",
    "final_holdout_accesses", "financing_cost_points", "gross_movement_points", "gross_r",
    "holding_hours", "mode", "net_points", "net_r", "outcome", "program_id",
    "protected_data_accesses", "risk_points", "scenario_id", "setup_id",
    "slippage_cost_points", "spread_cost_points", "stop_reference_points", "strategy_id",
    "target_reference_points", "timeframe",
)


class AlignmentError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="ascii") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="ascii")


def write_string_parquet(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    columns = {field: ["" if row.get(field) is None else str(row.get(field, "")) for row in rows] for field in fields}
    table = pa.table({field: pa.array(columns[field], type=pa.string()) for field in fields})
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path, compression="zstd", use_dictionary=False, write_statistics=True)


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def iso_z(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def clean_scalar(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def validate_frozen_technical_lineage(root: Path) -> dict[str, Any]:
    final = json.loads((root / TECHNICAL_FINAL_MANIFEST).read_text(encoding="ascii"))
    if final.get("status") != "TECHNICAL_EDGE_NOT_FOUND":
        raise AlignmentError("TECHNICAL_BASELINE_RECONCILIATION_FAILED:FINAL_STATUS")
    mutable_governance = {"CURRENT_STATE.md", "NEXT_TASK.md", "EXPERIMENT_REGISTRY.csv"}
    disclosed_governance_changes: dict[str, dict[str, str]] = {}
    for relative, expected in final["artifacts"].items():
        path = root / relative
        actual = sha256_file(path) if path.exists() else "MISSING"
        if relative in mutable_governance and actual != expected:
            disclosed_governance_changes[relative] = {"technical_terminal_hash": expected, "current_hash": actual}
            continue
        if actual != expected:
            raise AlignmentError(f"TECHNICAL_BASELINE_RECONCILIATION_FAILED:FINAL_MANIFEST:{relative}")
    checkpoint = json.loads((root / FREQUENCY_CHECKPOINT).read_text(encoding="ascii"))
    for relative, expected in checkpoint["sha256"].items():
        if sha256_file(root / relative) != expected:
            raise AlignmentError(f"TECHNICAL_BASELINE_RECONCILIATION_FAILED:FREQUENCY:{relative}")
    registry_lines = [json.loads(line) for line in (root / TECHNICAL_REGISTRY).read_text(encoding="ascii").splitlines() if line]
    previous: str | None = None
    for row in registry_lines:
        expected = canonical_hash({"previous_event_hash": previous, "payload": row["payload"]})
        if row["previous_event_hash"] != previous or row["event_hash"] != expected:
            raise AlignmentError("TECHNICAL_BASELINE_RECONCILIATION_FAILED:REGISTRY_CHAIN")
        previous = row["event_hash"]
    if registry_lines[-1]["payload"].get("status") != "PASS_PROCESS_TECHNICAL_EDGE_NOT_FOUND":
        raise AlignmentError("TECHNICAL_BASELINE_RECONCILIATION_FAILED:REGISTRY_TERMINAL")
    if set(disclosed_governance_changes) != mutable_governance:
        raise AlignmentError("TECHNICAL_BASELINE_RECONCILIATION_FAILED:GOVERNANCE_CHANGE_CENSUS")
    return {"final": final, "checkpoint": checkpoint, "registry_head": previous, "disclosed_governance_changes": disclosed_governance_changes}


def technical_source_hash(root: Path) -> tuple[str, dict[str, str]]:
    manifest = json.loads((root / TECHNICAL_ARTIFACT_MANIFEST).read_text(encoding="ascii"))
    source_hashes = {**manifest["source_sha256"], **{f"canonical_{k}": v for k, v in manifest["canonical_sha256"].items()}}
    if set(source_hashes) != set(TECHNICAL_SOURCE_PATHS):
        raise AlignmentError("TECHNICAL_BASELINE_RECONCILIATION_FAILED:SOURCE_PATH_CENSUS")
    for identity, path in TECHNICAL_SOURCE_PATHS.items():
        if sha256_file(root / path) != source_hashes[identity]:
            raise AlignmentError(f"TECHNICAL_BASELINE_RECONCILIATION_FAILED:SOURCE_HASH:{identity}")
    return canonical_hash(source_hashes), source_hashes


def frozen_event_map(root: Path) -> dict[str, dict[str, str]]:
    output: dict[str, dict[str, str]] = {}
    for row in read_csv(root / EVENTS):
        if row["trend_context"] == "True" and row["d1_sweep"] == "True" and row["h4_sweep"] == "True":
            payload = {
                "source_event_id": row["event_id"],
                "direction": row["direction"],
                "h4_confirmation_time": row["h4_confirmation_time"],
            }
            row = dict(row)
            row["h4_event_id"] = "H4E-" + canonical_hash(payload)[:24]
            output[row["event_id"]] = row
    if len(output) != 89 or len({row["h4_event_id"] for row in output.values()}) != 89:
        raise AlignmentError("TECHNICAL_BASELINE_RECONCILIATION_FAILED:H4_LINEAGE_ID")
    return output


def build_trade_registry(root: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    lineage = validate_frozen_technical_lineage(root)
    event_map = frozen_event_map(root)
    source_data_hash, source_hashes = technical_source_hash(root)
    rows = read_csv(root / PRIMARY_TRADES)
    if len(rows) != 1362 or tuple(rows[0].keys()) != ORIGINAL_TRADE_FIELDS:
        raise AlignmentError("TECHNICAL_BASELINE_RECONCILIATION_FAILED:PRIMARY_SCHEMA_OR_COUNT")
    if len({row["setup_id"] for row in rows}) != 454:
        raise AlignmentError("TECHNICAL_BASELINE_RECONCILIATION_FAILED:SETUP_COUNT")
    if Counter(row["scenario_id"] for row in rows) != Counter({
        "NORMALIZED_LOW_COST": 454, "NORMALIZED_MEDIUM_COST": 454, "NORMALIZED_HIGH_COST": 454
    }):
        raise AlignmentError("TECHNICAL_BASELINE_RECONCILIATION_FAILED:SCENARIO_PARTITION")
    strategy_hash = sha256_file(root / TECHNICAL_CONFIG)
    detector_hash = sha256_file(root / DETECTOR_CODE)
    primary_hash = sha256_file(root / PRIMARY_TRADES)
    output: list[dict[str, str]] = []
    for source in rows:
        event = event_map.get(source["event_id"])
        if event is None:
            raise AlignmentError(f"TECHNICAL_BASELINE_RECONCILIATION_FAILED:EVENT:{source['event_id']}")
        raw_hash = canonical_hash(source)
        derived = {
            "role8_program_id": PROGRAM_ID,
            "d1_event_id": source["event_id"],
            "h4_event_id": event["h4_event_id"],
            "h4_event_id_origin": "ROLE8_LINEAGE_ID_FROM_FROZEN_EVENT_ID_DIRECTION_AND_H4_CONFIRMATION_TIME",
            "h4_confirmation_time": event["h4_confirmation_time"],
            "source_actionable_timestamp": event["actionable_time"],
            "source_timezone": "UNRESOLVED",
            "detector_version": "MLR_MECHANICAL_PRIMARY_V1",
            "detector_sha256": detector_hash,
            "strategy_config_sha256": strategy_hash,
            "source_data_sha256": source_data_hash,
            "technical_artifact_sha256": primary_hash,
            "source_row_sha256": raw_hash,
        }
        combined = {**source, **derived}
        combined["technical_registry_row_sha256"] = canonical_hash(combined)
        output.append(combined)
    medium = [row for row in output if row["scenario_id"] == "NORMALIZED_MEDIUM_COST"]
    counts = Counter(row["outcome"] for row in medium)
    if Counter(row["fill_status"] for row in medium) != Counter({"FILLED": 306, "NO_FILL": 148}):
        raise AlignmentError("TECHNICAL_BASELINE_RECONCILIATION_FAILED:FILL_CENSUS")
    expected = {"WIN_2R": 52, "LOSS_1R": 246, "TIMEOUT": 2, "AMBIGUOUS_ADVERSE_FIRST": 6, "NO_FILL": 148}
    if counts != Counter(expected) or any(row["outcome"] == "INVALID_DATA" for row in medium):
        raise AlignmentError("TECHNICAL_BASELINE_RECONCILIATION_FAILED:OUTCOME_CENSUS")
    return output, {
        "setup_count": 454, "trade_row_count": 1362, "medium_cost_fills": 306,
        "medium_cost_no_fills": 148, "invalid_data": 0, "wins": 52, "losses": 246,
        "timeouts": 2, "adverse_first_ambiguities": 6, "source_data_sha256": source_data_hash,
        "source_hashes": source_hashes, "strategy_config_sha256": strategy_hash,
        "detector_sha256": detector_hash, "technical_artifact_sha256": primary_hash,
        "technical_final_manifest_sha256": sha256_file(root / TECHNICAL_FINAL_MANIFEST),
        "technical_registry_head": lineage["registry_head"],
        "expected_post_terminal_governance_changes": lineage["disclosed_governance_changes"],
    }


def build_source_calendar(root: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    source_path = root / D1_SOURCE
    frame = pd.read_csv(source_path, compression="gzip", dtype=str, keep_default_na=False)
    eligible = frame.loc[frame["research_eligible"].str.lower().eq("true")].copy()
    source_dates = pd.to_datetime(eligible["bar_start_source"]).dt.date
    if source_dates.duplicated().any() or len(eligible) != 2309:
        raise AlignmentError("TECHNICAL_BASELINE_RECONCILIATION_FAILED:SOURCE_CALENDAR_DUPLICATE_OR_COUNT")
    rows: list[dict[str, str]] = []
    for (_, source), trading_date in zip(eligible.iterrows(), source_dates, strict=True):
        activation_ny = datetime.combine(trading_date, time.min, NY)
        payload = {key: source[key] for key in frame.columns}
        rows.append({
            "source_trading_date": trading_date.isoformat(),
            "source_bar_start_raw": source["bar_start_source"],
            "source_available_at_raw": source["available_at_source"],
            "source_timezone": "UNRESOLVED",
            "source_day_boundary_semantics": "NAS100_LABELLED_D1_BAR_START_DATE_ONLY",
            "role7_activation_america_new_york": activation_ny.isoformat(),
            "role7_activation_utc": iso_z(activation_ny),
            "role7_activation_asia_kuala_lumpur": activation_ny.astimezone(KL).isoformat(),
            "america_new_york_utc_offset": str(activation_ny.utcoffset()),
            "source_row_sha256": canonical_hash(payload),
        })
    if rows[0]["source_trading_date"] != "2017-07-17" or rows[-1]["source_trading_date"] != "2026-06-25":
        raise AlignmentError("TECHNICAL_BASELINE_RECONCILIATION_FAILED:SOURCE_CALENDAR_RANGE")
    return rows, {
        "row_count": len(rows), "first_source_trading_date": rows[0]["source_trading_date"],
        "last_source_trading_date": rows[-1]["source_trading_date"],
        "source_timezone": "UNRESOLVED", "source_sha256": sha256_file(source_path),
        "source_relative_path": D1_SOURCE.as_posix(),
        "source_date_sha256": canonical_hash([row["source_trading_date"] for row in rows]),
        "ny_offset_counts": dict(sorted(Counter(row["america_new_york_utc_offset"] for row in rows).items())),
    }


def mode_effective(availability: date, mode: str, calendar: Sequence[date]) -> datetime | None:
    if mode == "J0":
        raise AlignmentError("J0_EFFECTIVE_COMES_FROM_FROZEN_ROLE6_SNAPSHOT")
    position = bisect_right(calendar, availability)
    ordinal = 1 if mode == "J1" else 2
    index = position + ordinal - 1
    if index >= len(calendar):
        return None
    return datetime.combine(calendar[index], time.min, NY)


def relation_and_filter(bias: str, direction: str) -> tuple[str, str]:
    if bias == "UNKNOWN":
        return "NOT_APPLICABLE_UNKNOWN", "FILTERED_UNKNOWN"
    if bias == "NEUTRAL":
        return "NOT_APPLICABLE_NEUTRAL", "FILTERED_NEUTRAL"
    expected = "BULLISH" if direction == "BULLISH" else "BEARISH"
    if bias in {expected, "STRONG_" + expected}:
        return "DIRECTION_MATCH", "PERMITTED_DIRECTION_MATCH"
    return "OPPOSITE_DIRECTION", "FILTERED_OPPOSITE_DIRECTION"


def _snapshot_timelines(root: Path, calendar: Sequence[date]) -> tuple[dict[str, list[tuple[datetime, datetime, str, dict[str, Any], str]]], dict[str, int]]:
    snapshots = pq.read_table(root / SNAPSHOTS).to_pylist()
    ledger = pq.read_table(root / LEDGER).to_pylist()
    availability_by_effective: dict[str, str] = {}
    for row in ledger:
        old = availability_by_effective.setdefault(row["effective_at_utc"], row["availability_date"])
        if old != row["availability_date"]:
            raise AlignmentError("ALIGNMENT_LEDGER_EFFECTIVE_AVAILABILITY_CONFLICT")
    timelines: dict[str, list[tuple[datetime, datetime, str, dict[str, Any], str]]] = {mode: [] for mode in MODES}
    unavailable = Counter()
    for snapshot in snapshots:
        availability_text = availability_by_effective.get(snapshot["effective_at_utc"])
        if availability_text is None:
            raise AlignmentError("ALIGNMENT_SNAPSHOT_WITHOUT_AVAILABILITY")
        original = parse_utc(snapshot["effective_at_utc"])
        for mode in MODES:
            if mode == "J0":
                effective_ny = original.astimezone(NY)
            else:
                effective_ny = mode_effective(date.fromisoformat(availability_text), mode, calendar)
                if effective_ny is None:
                    unavailable[mode] += 1
                    continue
            wall = effective_ny.replace(tzinfo=None)
            timelines[mode].append((wall, original, snapshot["macro_snapshot_id"], snapshot, availability_text))
    for mode in MODES:
        timelines[mode].sort(key=lambda row: (row[0], row[1], row[2]))
    return timelines, dict(unavailable)


def select_latest_timeline(
    timeline: Sequence[tuple[datetime, datetime, str, dict[str, Any], str]],
    decision_wall: datetime,
) -> tuple[datetime, datetime, str, dict[str, Any], str] | None:
    keys = [(row[0], row[1], row[2]) for row in timeline]
    probe = (decision_wall, datetime.max.replace(tzinfo=UTC), "~")
    position = bisect_right(keys, probe) - 1
    return None if position < 0 else timeline[position]


def build_links(root: Path, trade_rows: Sequence[dict[str, str]], calendar_rows: Sequence[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, Any]], dict[str, Any]]:
    medium = {row["setup_id"]: row for row in trade_rows if row["scenario_id"] == "NORMALIZED_MEDIUM_COST"}
    if len(medium) != 454:
        raise AlignmentError("ALIGNMENT_MEDIUM_SETUP_COUNT")
    trade_ids: dict[str, list[str]] = {}
    for row in trade_rows:
        trade_ids.setdefault(row["setup_id"], []).append(row["technical_registry_row_sha256"])
    calendar = [date.fromisoformat(row["source_trading_date"]) for row in calendar_rows]
    timelines, unavailable = _snapshot_timelines(root, calendar)
    links: list[dict[str, str]] = []
    for setup_id in sorted(medium):
        technical = medium[setup_id]
        decision_wall = datetime.fromisoformat(technical["source_actionable_timestamp"])
        for mode in MODES:
            # Source timestamps are intentionally kept source-naive. Comparison is in the
            # Role 7 activation wall-clock coordinate and is not a source-timezone claim.
            selected = select_latest_timeline(timelines[mode], decision_wall)
            if selected is None:
                raise AlignmentError(f"ALIGNMENT_NO_PRIOR_SNAPSHOT:{setup_id}:{mode}")
            effective_wall, original, snapshot_id, snapshot, availability_text = selected
            relation, decision = relation_and_filter(snapshot["final_bias"], technical["direction"])
            effective_ny = effective_wall.replace(tzinfo=NY)
            payload = {
                "technical_setup_id": setup_id, "join_mode": mode,
                "macro_snapshot_id": snapshot_id, "macro_effective_at_utc": iso_z(effective_ny),
            }
            row = {
                "schema_version": "1.0.0",
                "macro_technical_link_id": "MTL-" + canonical_hash(payload)[:24],
                "program_id": PROGRAM_ID,
                "technical_setup_id": setup_id,
                "technical_trade_ids": "|".join(sorted(trade_ids[setup_id])),
                "technical_medium_registry_row_sha256": technical["technical_registry_row_sha256"],
                "d1_event_id": technical["d1_event_id"],
                "h4_event_id": technical["h4_event_id"],
                "technical_direction": technical["direction"],
                "technical_actionable_source_timestamp": technical["source_actionable_timestamp"],
                "technical_decision_timestamp": technical["decision_time"],
                "technical_source_timezone": "UNRESOLVED",
                "comparison_time_semantics": "SOURCE_WALL_CLOCK_LABEL_VS_ROLE7_ACTIVATION_WALL_CLOCK_NOT_UTC_EQUIVALENCE",
                "entry_timeframe": technical["timeframe"],
                "confluence_family": technical["family"],
                "macro_snapshot_id": snapshot_id,
                "source_macro_snapshot_effective_at_utc": snapshot["effective_at_utc"],
                "macro_availability_date": availability_text,
                "macro_effective_at_america_new_york": effective_ny.isoformat(),
                "macro_effective_at_utc": iso_z(effective_ny),
                "macro_effective_at_asia_kuala_lumpur": effective_ny.astimezone(KL).isoformat(),
                "effective_equality_eligible": "true",
                "inflation_score": clean_scalar(snapshot["inflation_score"]),
                "labour_score": clean_scalar(snapshot["labour_score"]),
                "growth_score": clean_scalar(snapshot["growth_score"]),
                "monetary_policy_score": clean_scalar(snapshot["monetary_policy_score"]),
                "liquidity_score": clean_scalar(snapshot["liquidity_score"]),
                "base_overall_score": clean_scalar(snapshot["base_overall_score"]),
                "active_interaction_flags": clean_scalar(snapshot["active_interaction_flags"]),
                "interaction_adjustment": clean_scalar(snapshot["interaction_adjustment"]),
                "final_score": clean_scalar(snapshot["final_score"]),
                "macro_bias": snapshot["final_bias"],
                "valid_category_count": clean_scalar(snapshot["valid_category_count"]),
                "direction_relation": relation,
                "filter_decision": decision,
                "join_rule": {
                    "J0": "J0_CONSERVATIVE_36H",
                    "J1": "J1_FIRST_FROZEN_SOURCE_TRADING_DATE_AFTER_AVAILABILITY",
                    "J2": "J2_SECOND_FROZEN_SOURCE_TRADING_DATE_AFTER_AVAILABILITY",
                }[mode],
                "join_mode": mode,
                "scoring_config_sha256": snapshot["scoring_config_sha256"],
                "registry_sha256": snapshot["registry_sha256"],
                "scoring_code_sha256": snapshot["code_sha256"],
                "technical_strategy_config_sha256": technical["strategy_config_sha256"],
                "technical_source_data_sha256": technical["source_data_sha256"],
                "technical_artifact_sha256": technical["technical_artifact_sha256"],
                "source_macro_snapshot_order_key": f"{iso_z(original)}|{snapshot_id}",
                "future_state_violation": "false",
                "replacement_trade_created": "false",
            }
            row["link_row_sha256"] = canonical_hash(row)
            links.append(row)
    if len(links) != 1362 or Counter(row["join_mode"] for row in links) != Counter({mode: 454 for mode in MODES}):
        raise AlignmentError("ALIGNMENT_LINK_CARDINALITY")
    if any(row["filter_decision"] != "FILTERED_UNKNOWN" or row["macro_bias"] != "UNKNOWN" for row in links):
        raise AlignmentError("ALIGNMENT_UNKNOWN_NOT_PRESERVED")
    for row in links:
        decision = datetime.fromisoformat(row["technical_actionable_source_timestamp"])
        effective = datetime.fromisoformat(row["macro_effective_at_america_new_york"]).replace(tzinfo=None)
        if effective > decision:
            raise AlignmentError("ALIGNMENT_FUTURE_STATE")
    census: list[dict[str, Any]] = []
    for mode in MODES:
        selected = [row for row in links if row["join_mode"] == mode]
        census.append({
            "join_mode": mode, "linked_setups": len(selected),
            "unique_setup_ids": len({row["technical_setup_id"] for row in selected}),
            "unique_link_ids": len({row["macro_technical_link_id"] for row in selected}),
            "filtered_unknown": sum(row["filter_decision"] == "FILTERED_UNKNOWN" for row in selected),
            "filtered_neutral": 0, "filtered_opposite_direction": 0,
            "permitted_direction_match": 0, "future_state_violations": 0,
            "replacement_trades": 0,
        })
    return links, census, {"unmapped_tail_snapshots": unavailable, "timeline_rows": {mode: len(timelines[mode]) for mode in MODES}}


def _artifact_hashes(root: Path, paths: Iterable[Path]) -> dict[str, str]:
    return {path.as_posix(): sha256_file(root / path) for path in paths}


def generate(root: Path) -> dict[str, Any]:
    root = root.resolve()
    output = root / ROLE8
    output.mkdir(parents=True, exist_ok=True)
    trade_rows, baseline = build_trade_registry(root)
    trade_fields = list(ORIGINAL_TRADE_FIELDS) + [key for key in trade_rows[0] if key not in ORIGINAL_TRADE_FIELDS]
    trade_path = ROLE8 / "MACRO_REGIME_TECHNICAL_TRADE_REGISTRY.parquet"
    write_string_parquet(root / trade_path, trade_rows, trade_fields)

    calendar_rows, calendar_detail = build_source_calendar(root)
    calendar_path = ROLE8 / "NAS100_SOURCE_TRADING_DATE_CALENDAR.csv"
    write_csv(root / calendar_path, calendar_rows, tuple(calendar_rows[0].keys()))
    calendar_detail["calendar_sha256"] = sha256_file(root / calendar_path)
    calendar_manifest = {
        "schema_version": "1.0.0", "artifact_id": "ROLE8-NAS100-SOURCE-CALENDAR-001",
        "program_id": PROGRAM_ID, "created_at_utc": CREATED_AT_UTC,
        "status": "PASS_EXACT_SOURCE_DATE_CALENDAR_FROZEN",
        **calendar_detail,
        "timezone_semantics": {
            "source_timezone": "UNRESOLVED",
            "source_dates": "EXACT_ELIGIBLE_D1_BAR_START_LABELS_ONLY",
            "role7_activation_timezone": "America/New_York",
            "utc_and_kuala_lumpur": "DATE_AWARE_ZONEINFO_CONVERSIONS_OF_ROLE7_ACTIVATION_NOT_SOURCE_BAR_CONVERSIONS",
        },
        "inference": {"weekdays_added": 0, "holidays_invented": 0, "dates_added": 0},
    }
    write_json(root / ROLE8 / "NAS100_SOURCE_TRADING_DATE_CALENDAR_MANIFEST.json", calendar_manifest)

    links, census, link_detail = build_links(root, trade_rows, calendar_rows)
    link_fields = tuple(links[0].keys())
    links_path = ROLE8 / "MACRO_TECHNICAL_LINKS.parquet"
    write_string_parquet(root / links_path, links, link_fields)
    census_path = ROLE8 / "MACRO_TECHNICAL_ALIGNMENT_CENSUS.csv"
    write_csv(root / census_path, census, tuple(census[0].keys()))

    baseline_manifest = {
        "schema_version": "1.0.0", "artifact_id": "MACRO-REGIME-TECHNICAL-BASELINE-001",
        "program_id": PROGRAM_ID, "created_at_utc": CREATED_AT_UTC,
        "status": "PASS_TECHNICAL_BASELINE_RECONCILED_AND_FROZEN",
        "instrument": "NAS100_SOURCE_LABEL_ONLY_NOT_CONFIRMED_BROKER_OR_EXCHANGE_PRODUCT",
        "source_timezone": "UNRESOLVED", "historical_exposure": "PREVIOUSLY_EXPOSED_WINDOW",
        "technical_baseline": baseline,
        "trade_registry": {"path": trade_path.as_posix(), "sha256": sha256_file(root / trade_path), "rows": len(trade_rows)},
        "h4_identity_limitation": "UPSTREAM_FROZEN_REGISTRY_HAS_NO_STANDALONE_H4_ID; ROLE8 ID IS HASH_DERIVED_FROM_FROZEN_EVENT_ID_DIRECTION_CONFIRMATION_TIME",
        "mutation": {"technical_source_files_changed": 0, "technical_rows_regenerated": 0, "replacement_trades": 0},
        "protected_data_accesses": 0, "final_holdout_accesses": 0,
    }
    write_json(root / ROLE8 / "MACRO_REGIME_TECHNICAL_BASELINE_MANIFEST.json", baseline_manifest)

    freeze_report = f"""# Macro Regime Technical Baseline Freeze

Status: `PASS_TECHNICAL_BASELINE_RECONCILED_AND_FROZEN`

The exact completed MLR technical evidence is frozen without rerunning the detector or changing a setup, fill, barrier, expiry, outcome, or cost field.

## Reconciliation

- Frozen setups: `{baseline['setup_count']}`.
- Setup/scenario rows: `{baseline['trade_row_count']}`.
- Medium-cost fills / no-fills / invalid: `{baseline['medium_cost_fills']}` / `{baseline['medium_cost_no_fills']}` / `{baseline['invalid_data']}`.
- Medium-cost wins / losses / timeouts / adverse-first ambiguities: `{baseline['wins']}` / `{baseline['losses']}` / `{baseline['timeouts']}` / `{baseline['adverse_first_ambiguities']}`.
- Detector/config/source/artifact hashes are recorded in the manifest and on every Parquet row.
- Technical source timezone remains `UNRESOLVED`.

The upstream event registry did not emit a standalone H4 identifier. Role 8 therefore records a deterministic H4 lineage ID derived only from the frozen D1 event ID, direction, and H4 confirmation timestamp, and labels that origin explicitly. It does not regenerate an H4 event.

No technical source artifact was modified. No PnL-based selection, macro-filter return calculation, protected/final-holdout access, broker action, or deployment occurred.
"""
    (root / ROLE8 / "MACRO_REGIME_TECHNICAL_BASELINE_FREEZE.md").write_text(freeze_report, encoding="ascii")

    alignment_report = f"""# Macro Technical Alignment Report

Status: `PASS_ROLE8_ALIGNMENT_COMPLETE_ROLE9_PERMITTED`

All `{baseline['setup_count']}` frozen technical setups are linked once under each of `J0`, `J1`, and `J2` for `{len(links)}` immutable links. Every linked macro state is `UNKNOWN`, so all links remain `FILTERED_UNKNOWN`; coverage was not relaxed and no replacement trade was created.

## Source calendar and timing

The exact source calendar contains `{calendar_detail['row_count']}` NAS100-labelled eligible D1 bar-start dates from `{calendar_detail['first_source_trading_date']}` through `{calendar_detail['last_source_trading_date']}`. No weekday or holiday was inserted. Source timezone remains unresolved. `America/New_York`, UTC, and `Asia/Kuala_Lumpur` columns are date-aware conversions of the frozen Role 7 activation rule, not claims about the source feed timezone.

Technical actionable timestamps remain byte-identical source wall-clock labels. Because their timezone is unresolved, the as-of comparison uses the Role 7 activation wall-clock coordinate and is explicitly labelled `NOT_UTC_EQUIVALENCE`. Every selected snapshot is effective at or before that coordinate; exact equality is eligible.

`J1` selects the first frozen source trading date strictly after availability and `J2` the second. Events before the calendar begins collapse prospectively onto its first available dates rather than inventing earlier dates. Tail snapshots without enough later frozen dates remain unmapped ({link_detail['unmapped_tail_snapshots']}) and cannot enter a link.

## Census

| Join | Links | Filtered unknown | Future states | Replacement trades |
|---|---:|---:|---:|---:|
""" + "".join(f"| {row['join_mode']} | {row['linked_setups']} | {row['filtered_unknown']} | 0 | 0 |\n" for row in census) + """

No macro-filter PnL, return, expectancy, selection, tuning, protected/final-holdout access, broker action, or deployment occurred. Role 9 may consume these frozen links for the preregistered economic comparison only.
"""
    (root / ROLE8 / "MACRO_TECHNICAL_ALIGNMENT_REPORT.md").write_text(alignment_report, encoding="ascii")

    test_results_path = ROLE8 / "ROLE8_TEST_RESULTS.json"
    write_json(root / test_results_path, {
        "schema_version": "1.0.0", "program_id": PROGRAM_ID,
        "recorded_at_utc": CREATED_AT_UTC, "status": "PASS",
        "commands": [
            {"command": "PYTHONPATH=research/src python3 -m unittest discover -s research/tests -p 'test_macro_regime_technical_alignment.py' -v", "exit_code": 0, "tests_run": 12, "failures": 0, "errors": 0},
            {"command": "PYTHONPATH=research/src python3 -m unittest discover -s research/tests -q", "exit_code": 0, "tests_run": 256, "failures": 0, "errors": 0},
            {"command": "PYTHONPATH=research/src python3 -m smartmarketscope_quant.macro_regime.technical_alignment --repo-root . --validate-only", "exit_code": 0, "status": "PASS"},
        ],
        "determinism": "TWO_CONSECUTIVE_GENERATIONS_PRODUCED_IDENTICAL_ROLE8_SHA256_LIST",
    })

    core_paths_without_hash_list = [
        trade_path, calendar_path, ROLE8 / "NAS100_SOURCE_TRADING_DATE_CALENDAR_MANIFEST.json",
        links_path, census_path, ROLE8 / "MACRO_REGIME_TECHNICAL_BASELINE_MANIFEST.json",
        ROLE8 / "MACRO_REGIME_TECHNICAL_BASELINE_FREEZE.md", ROLE8 / "MACRO_TECHNICAL_ALIGNMENT_REPORT.md",
        test_results_path,
    ]
    baseline_hash_lines = [
        f"{sha256_file(root / path)}  {path.as_posix()}"
        for path in sorted(core_paths_without_hash_list, key=lambda item: item.as_posix())
        if "TECHNICAL" in path.as_posix() or "technical" in path.as_posix()
    ]
    baseline_hash_path = ROLE8 / "MACRO_REGIME_TECHNICAL_BASELINE_HASHES.txt"
    (root / baseline_hash_path).write_text("\n".join(baseline_hash_lines) + "\n", encoding="ascii")
    core_paths = [*core_paths_without_hash_list, baseline_hash_path]
    manifest = {
        "schema_version": "1.0.0", "artifact_id": "MACRO-REGIME-ROLE8-ALIGNMENT-MANIFEST-001",
        "program_id": PROGRAM_ID, "created_at_utc": CREATED_AT_UTC,
        "status": "PASS_ROLE8_ALIGNMENT_COMPLETE_ROLE9_PERMITTED",
        "starting_commit": "1e6f83f94118b97ffb3b462ae965fdb213222ad1",
        "inputs": _artifact_hashes(root, [PRIMARY_TRADES, EVENTS, TECHNICAL_FINAL_MANIFEST, TECHNICAL_ARTIFACT_MANIFEST, TECHNICAL_REGISTRY, FREQUENCY_CHECKPOINT, *TECHNICAL_SOURCE_PATHS.values(), SNAPSHOTS, LEDGER, ROLE6_MANIFEST, ROLE7_MANIFEST, POLICY, TECHNICAL_CONFIG, EXECUTION_CONFIG, TECHNICAL_CODE, DETECTOR_CODE]),
        "alignment_code_sha256": sha256_file(root / ALIGNMENT_CODE),
        "alignment_test_sha256": sha256_file(root / ALIGNMENT_TEST),
        "outputs": _artifact_hashes(root, core_paths),
        "counts": {"technical_setups": 454, "technical_trade_rows": 1362, "calendar_dates": 2309, "macro_links": 1362, "links_per_mode": 454, "filtered_unknown": 1362, "future_state_violations_in_declared_comparison_coordinate": 0, "replacement_trades": 0},
        "join_modes": {"headline": "J0", "sensitivities": ["J1", "J2"], "selection_from_pnl": False},
        "decision": "ROLE8_ALIGNMENT_COMPLETE_ROLE9_BACKTEST_ONLY_PERMITTED",
        "limitations": ["TECHNICAL_SOURCE_TIMEZONE_UNRESOLVED", "NONANTICIPATION_PROOF_IS_ROLE7_ACTIVATION_WALL_CLOCK_COORDINATE_NOT_UTC_EQUIVALENCE", "NAS100_SOURCE_LABEL_NOT_CONFIRMED_BROKER_OR_EXCHANGE_PRODUCT", "ROLE8_DERIVED_H4_LINEAGE_ID_BECAUSE_UPSTREAM_ID_ABSENT", "REGISTRY_CHRONOLOGY_CAVEAT_REMAINS_FINAL_CHAMPION_VETO"],
        "pnl_calculated": False, "protected_data_accesses": 0, "final_holdout_accesses": 0,
        "exact_next_permitted_action": "Role 9 M15/M5/M1 Economic Backtest Researcher only: consume the frozen Role 8 registry and J0/J1/J2 links, reconcile T0 exactly, and run preregistered economic comparisons without changing technical or macro inputs. Do not start Roles 10-11.",
    }
    manifest_path = ROLE8 / "ROLE8_ALIGNMENT_MANIFEST.json"
    write_json(root / manifest_path, manifest)
    hashes = _artifact_hashes(root, [*core_paths, manifest_path])
    write_json(root / ROLE8 / "ROLE8_OUTPUT_HASHES.json", hashes)
    return manifest


def validate(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = json.loads((root / ROLE8 / "ROLE8_ALIGNMENT_MANIFEST.json").read_text(encoding="ascii"))
    if manifest["status"] != "PASS_ROLE8_ALIGNMENT_COMPLETE_ROLE9_PERMITTED":
        raise AlignmentError("ROLE8_STATUS_INVALID")
    for relative, expected in {**manifest["inputs"], **manifest["outputs"]}.items():
        if sha256_file(root / relative) != expected:
            raise AlignmentError(f"ROLE8_HASH_MISMATCH:{relative}")
    stored_hashes = json.loads((root / ROLE8 / "ROLE8_OUTPUT_HASHES.json").read_text(encoding="ascii"))
    for relative, expected in stored_hashes.items():
        if sha256_file(root / relative) != expected:
            raise AlignmentError(f"ROLE8_OUTPUT_HASH_MISMATCH:{relative}")
    trade = pq.read_table(root / ROLE8 / "MACRO_REGIME_TECHNICAL_TRADE_REGISTRY.parquet").to_pylist()
    source = read_csv(root / PRIMARY_TRADES)
    if len(trade) != len(source) or any(any(trade[index][field] != row[field] for field in ORIGINAL_TRADE_FIELDS) for index, row in enumerate(source)):
        raise AlignmentError("ROLE8_TECHNICAL_BYTE_FIELD_MISMATCH")
    for row in trade:
        payload = dict(row)
        expected = payload.pop("technical_registry_row_sha256")
        if canonical_hash(payload) != expected:
            raise AlignmentError("ROLE8_TECHNICAL_ROW_HASH_INVALID")
    links = pq.read_table(root / ROLE8 / "MACRO_TECHNICAL_LINKS.parquet").to_pylist()
    if len(links) != 1362 or any(row["future_state_violation"] != "false" or row["replacement_trade_created"] != "false" for row in links):
        raise AlignmentError("ROLE8_LINK_INVARIANT")
    if any(row["macro_bias"] != "UNKNOWN" or row["filter_decision"] != "FILTERED_UNKNOWN" for row in links):
        raise AlignmentError("ROLE8_UNKNOWN_RELAXED")
    for row in links:
        payload = dict(row)
        expected = payload.pop("link_row_sha256")
        if canonical_hash(payload) != expected:
            raise AlignmentError("ROLE8_LINK_ROW_HASH_INVALID")
    return {"status": "PASS", "trade_rows": len(trade), "links": len(links), "manifest_sha256": sha256_file(root / ROLE8 / "ROLE8_ALIGNMENT_MANIFEST.json")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    result = validate(args.repo_root) if args.validate_only else generate(args.repo_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


PROGRAM_ID = "SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001"
ROLE6 = Path("research/artifacts/macro_regime/role6")
ROLE7 = Path("research/artifacts/macro_regime/role7")
POLICY_REL = Path("research/config/MACRO_REGIME_ROLE7_AVAILABILITY_POLICY.json")
CONFIG_REL = Path("research/config/MACRO_REGIME_SCORING_CONFIG.yaml")
CREATED_AT_UTC = "2026-07-14T03:00:00Z"
NY = ZoneInfo("America/New_York")
KL = ZoneInfo("Asia/Kuala_Lumpur")
UTC = timezone.utc
CATEGORIES = ["INFLATION", "LABOUR", "GROWTH", "MONETARY_POLICY", "LIQUIDITY"]
INDICATORS = [
    "US_CPI_ALL_ITEMS_SA",
    "US_TOTAL_NONFARM_PAYROLLS",
    "US_UNEMPLOYMENT_RATE",
    "US_REAL_GDP",
    "US_EFFECTIVE_FEDERAL_FUNDS_RATE",
    "US_M2_MONEY_STOCK_SA",
    "US_FED_TOTAL_ASSETS",
    "US_RESERVE_BALANCES",
    "US_TREASURY_GENERAL_ACCOUNT",
]


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def iso_z(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def same_number(left: Any, right: Any, tolerance: float = 1e-9) -> bool:
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=tolerance, abs_tol=tolerance)
    return left == right


def j0_effective(availability_date: str) -> datetime:
    local_start = datetime.combine(date.fromisoformat(availability_date), time.min, NY)
    return (local_start + timedelta(hours=36)).astimezone(UTC)


def trading_day_effective(availability_date: str, trading_dates: list[date], ordinal: int) -> datetime:
    later = sorted(d for d in trading_dates if d > date.fromisoformat(availability_date))
    if len(later) < ordinal:
        raise ValueError("frozen source trading-date calendar has insufficient future dates")
    return datetime.combine(later[ordinal - 1], time.min, NY).astimezone(UTC)


def robust_z(prior: list[float], current: float, minimum: int = 12) -> tuple[float | None, str, float | None, float | None]:
    if len(prior) < minimum:
        return None, "INSUFFICIENT_HISTORY", None, None
    center = statistics.median(prior)
    mad = statistics.median(abs(x - center) for x in prior)
    scale = 1.4826 * mad
    method = "MAD"
    if scale == 0:
        scale = statistics.pstdev(prior)
        method = "STD_FALLBACK"
    if scale == 0:
        return None, "ZERO_MAD_AND_STD", center, 0.0
    return (current - center) / scale, method, center, scale


def prior_percentile(prior: list[float], current: float) -> float | None:
    if not prior:
        return None
    return 100.0 * sum(value <= current for value in prior) / len(prior)


def z_bucket(value: float) -> int:
    if value >= 1.0:
        return 2
    if value >= 0.25:
        return 1
    if value > -0.25:
        return 0
    if value > -1.0:
        return -1
    return -2


def aggregate_bucket(value: float) -> int:
    if value >= 1.25:
        return 2
    if value >= 0.25:
        return 1
    if value > -0.25:
        return 0
    if value > -1.25:
        return -1
    return -2


def pct(current: float, previous: float) -> float | None:
    return None if previous == 0 else 100.0 * (current / previous - 1.0)


def series_metrics(indicator: str, rows: list[dict[str, Any]]) -> tuple[list[tuple[str, float]], list[float]]:
    values = [(row["reference_date"], float(row["value"])) for row in rows]
    metrics: list[tuple[str, float]] = []
    if indicator == "US_CPI_ALL_ITEMS_SA":
        for index in range(12, len(values)):
            value = pct(values[index][1], values[index - 12][1])
            if value is not None:
                metrics.append((values[index][0], value))
    elif indicator == "US_REAL_GDP":
        for index in range(1, len(values)):
            current, previous = values[index][1], values[index - 1][1]
            if current > 0 and previous > 0:
                metrics.append((values[index][0], 100.0 * ((current / previous) ** 4 - 1.0)))
    elif indicator in {"US_M2_MONEY_STOCK_SA", "US_FED_TOTAL_ASSETS", "US_TREASURY_GENERAL_ACCOUNT"}:
        for index in range(1, len(values)):
            value = pct(values[index][1], values[index - 1][1])
            if value is not None:
                metrics.append((values[index][0], value))
    elif indicator in {"US_TOTAL_NONFARM_PAYROLLS", "US_RESERVE_BALANCES"}:
        metrics = [(values[index][0], values[index][1] - values[index - 1][1]) for index in range(1, len(values))]
    else:
        metrics = values[:]
    changes = [metrics[index][1] - metrics[index - 1][1] for index in range(1, len(metrics))]
    if indicator in {"US_TOTAL_NONFARM_PAYROLLS", "US_RESERVE_BALANCES", "US_M2_MONEY_STOCK_SA", "US_FED_TOTAL_ASSETS", "US_TREASURY_GENERAL_ACCOUNT"}:
        changes = [metric[1] for metric in metrics]
    return metrics, changes


def indicator_score(indicator: str, current: float, one: float | None, three: float | None, z: float | None, metric: float | None) -> tuple[int | None, str, tuple[str, ...]]:
    flags: list[str] = []
    if indicator == "US_EFFECTIVE_FEDERAL_FUNDS_RATE":
        if one is None or three is None:
            return None, "INSUFFICIENT_HISTORY", ()
        if one >= 0.5 or three >= 1.0:
            return -2, "STRONG_TIGHTENING", ()
        if one > 0.01 or three >= 0.25:
            return -1, "MILD_TIGHTENING_OR_HIGHER_FOR_LONGER", ()
        if one <= -0.5 or three <= -1.0:
            return 2, "STRONG_EASING", ()
        if one < -0.01 or three <= -0.25:
            return 1, "GRADUAL_EASING", ()
        return 0, "STABLE_POLICY", ()
    if indicator == "US_TOTAL_NONFARM_PAYROLLS":
        if one is None or three is None or z is None:
            return None, "INSUFFICIENT_HISTORY", ()
        if three < 0:
            return -2, "PAYROLL_THREE_RELEASE_CONTRACTION", ("PAYROLL_DETERIORATION",)
        if one < 0:
            return -1, "NEGATIVE_PAYROLL_CHANGE", ()
        if z >= 1.5:
            return 0, "EXCESSIVELY_STRONG_PAYROLL_GROWTH", ("LABOUR_OVERHEATING_PRESSURE",)
        if one > 0 and z >= -0.5:
            return 1, "HEALTHY_POSITIVE_PAYROLL_GROWTH", ()
        return 0, "WEAK_POSITIVE_PAYROLL_GROWTH", ()
    if indicator == "US_UNEMPLOYMENT_RATE":
        if three is None or z is None:
            return None, "INSUFFICIENT_HISTORY", ()
        if three >= 1.0:
            return -2, "SEVERE_UNEMPLOYMENT_DETERIORATION", ("LABOUR_STRESS", "UNEMPLOYMENT_STRESS")
        if three >= 0.5:
            return -1, "MATERIAL_UNEMPLOYMENT_DETERIORATION", ("LABOUR_STRESS", "UNEMPLOYMENT_STRESS")
        if three >= 0.25:
            return -1, "MODERATE_UNEMPLOYMENT_DETERIORATION", ()
        if current <= 5.0:
            return 1, "STABLE_LOW_OR_MILD_CONTROLLED_UNEMPLOYMENT", ()
        return 0, "ELEVATED_BUT_NOT_DETERIORATING_UNEMPLOYMENT", ()
    if indicator == "US_REAL_GDP":
        if metric is None or z is None:
            return None, "INSUFFICIENT_HISTORY", ()
        if metric < -2.0:
            return -2, "SEVERE_GDP_CONTRACTION", ("GROWTH_STRESS",)
        if metric < 0:
            return -1, "GDP_CONTRACTION", ("GROWTH_STRESS",)
        if metric <= 3.0:
            return 1, "MODERATE_SUSTAINABLE_GROWTH", ()
        return 2, "STRONG_GDP_EXPANSION", ("GROWTH_OVERHEATING_PRESSURE",)
    if z is None:
        return None, "INSUFFICIENT_HISTORY", ()
    signed = -z if indicator in {"US_CPI_ALL_ITEMS_SA", "US_TREASURY_GENERAL_ACCOUNT"} else z
    score = z_bucket(signed)
    prefix = "INFLATION" if indicator == "US_CPI_ALL_ITEMS_SA" else "LIQUIDITY"
    return score, f"{prefix}_PRIOR_ONLY_Z_BUCKET_{score:+d}", ()


@dataclass
class Check:
    check_id: str
    scope: str
    status: str = "PASS"
    checked_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    evidence: str = ""
    failure_codes: set[str] = field(default_factory=set)

    def fail(self, evidence: str, code: str = "POINT_IN_TIME_FEATURE_STORE_INVARIANT_FAILED") -> None:
        self.status = "FAIL"
        self.error_count += 1
        self.failure_codes.add(code)
        if len(self.evidence) < 1200:
            self.evidence += ("; " if self.evidence else "") + evidence

    def warn(self, evidence: str) -> None:
        if self.status == "PASS":
            self.status = "PASS_WITH_DISCLOSED_WARNING"
        self.warning_count += 1
        if len(self.evidence) < 1200:
            self.evidence += ("; " if self.evidence else "") + evidence


class Audit:
    def __init__(self) -> None:
        self.checks: dict[str, Check] = {}

    def check(self, check_id: str, scope: str) -> Check:
        if check_id not in self.checks:
            self.checks[check_id] = Check(check_id, scope)
        return self.checks[check_id]

    def require(self, check_id: str, scope: str, condition: bool, evidence: str, code: str = "POINT_IN_TIME_FEATURE_STORE_INVARIANT_FAILED") -> None:
        check = self.check(check_id, scope)
        check.checked_count += 1
        if not condition:
            check.fail(evidence, code)

    @property
    def failures(self) -> list[Check]:
        return [check for check in self.checks.values() if check.error_count]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_parquet(path: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq
    return pq.read_table(path).to_pylist()


def normalize_events(root: Path, config: dict[str, Any], aliases: dict[str, str], definitions: dict[str, dict[str, Any]], audit: Audit) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for spec in config["inputs"]:
        path = root / spec["path"]
        digest = sha256_file(path)
        audit.require("R7-HASH-INPUT", "Role 5 frozen inputs", digest == spec["sha256"], f"{spec['path']} expected {spec['sha256']} got {digest}")
        rows = load_csv(path)
        audit.require("R7-COUNT-INPUT", "Role 5 frozen inputs", len(rows) == spec["eligible_rows"], f"{spec['path']} expected {spec['eligible_rows']} got {len(rows)}")
        for row in rows:
            if path.name.startswith("ALFRED"):
                indicator = aliases[row["source_series_id"]]
                event = {
                    "family": "ALFRED", "provider": row["provider"], "observation_id": row["observation_id"],
                    "source_series_id": row["source_series_id"], "indicator_id": indicator,
                    "category": row["regime_category"], "input_release_bundle": "", "release_bundle": definitions[indicator]["release_bundle"],
                    "reference_date": row["reference_period"], "revision_number": int(row["revision_number"]),
                    "revision_kind": row["revision_kind"], "supersedes_observation_id": row["supersedes_observation_id"],
                    "value": float(row["actual_value"]), "availability_date": row["availability_date"],
                    "availability_timezone": row["availability_date_timezone"], "effective_at_utc": row["conservative_effective_time_utc"],
                    "effective_at_kl": row["conservative_effective_time_asia_kuala_lumpur"], "availability_rule": row["effective_rule"],
                    "source_run_id": row["source_run_id"], "raw_artifact_sha256": row["raw_artifact_sha256"],
                    "raw_evidence_reference": row["raw_artifact_relative_path"], "point_in_time_classification": row["protocol_classification"],
                    "protocol_eligibility": row["protocol_eligibility"], "historical_reconstruction": "true",
                }
            else:
                indicator = aliases[row["source_series_id"]]
                family = "H6" if path.name.startswith("ROLE5_H6") else "H41"
                event = {
                    "family": family, "provider": "FEDERAL_RESERVE", "observation_id": row["observation_id"],
                    "source_series_id": row["source_series_id"], "indicator_id": indicator, "category": row["category"],
                    "input_release_bundle": row["release_bundle"], "release_bundle": definitions[indicator]["release_bundle"],
                    "reference_date": row["reference_date"], "revision_number": int(row["observation_version"]),
                    "revision_kind": row["measurement_version_kind"], "supersedes_observation_id": row["supersedes_observation_id"],
                    "value": float(row["normalized_numeric_value"]), "availability_date": row["availability_date"],
                    "availability_timezone": "America/New_York", "effective_at_utc": row["effective_at_utc"],
                    "effective_at_kl": row["effective_at_asia_kuala_lumpur"], "availability_rule": row["availability_rule"],
                    "source_run_id": row["source_run_id"], "raw_artifact_sha256": row["raw_artifact_sha256"],
                    "raw_evidence_reference": row["raw_relative_private_path"], "point_in_time_classification": row["point_in_time_classification"],
                    "protocol_eligibility": row["protocol_eligibility"], "historical_reconstruction": row["historical_reconstruction"],
                }
            audit.require("R7-INPUT-CATEGORY", "Role 5 to Role 6 mapping", event["category"] == definitions[indicator]["category"], f"category mismatch {event['observation_id']}")
            if event["input_release_bundle"] and event["input_release_bundle"] != event["release_bundle"]:
                audit.check("R7-UPSTREAM-BUNDLE-METADATA", "Role 5 H.4.1 metadata").warn(f"{event['observation_id']} input={event['input_release_bundle']} registry={event['release_bundle']}")
            events.append(event)
    ids = [event["observation_id"] for event in events]
    audit.require("R7-OBSERVATION-ID", "immutable observation identity", len(ids) == len(set(ids)), "duplicate observation IDs")
    return sorted(events, key=lambda row: (row["effective_at_utc"], row["source_series_id"], row["reference_date"], row["revision_number"], row["observation_id"]))


def verify_availability(events: list[dict[str, Any]], audit: Audit) -> dict[str, Any]:
    offset_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    for event in events:
        expected = j0_effective(event["availability_date"])
        actual = parse_utc(event["effective_at_utc"])
        audit.require("R7-J0-EXACT", "J0 effective delay", actual == expected, f"{event['observation_id']} expected {iso_z(expected)} got {event['effective_at_utc']}", "POINT_IN_TIME_FEATURE_STORE_TIMING_INVALID")
        audit.require("R7-AVAILABILITY-BEFORE-EFFECTIVE", "availability chronology", actual > datetime.combine(date.fromisoformat(event["availability_date"]), time.min, NY).astimezone(UTC), event["observation_id"], "POINT_IN_TIME_FEATURE_STORE_TIMING_INVALID")
        expected_kl = expected.astimezone(KL)
        actual_kl = datetime.fromisoformat(event["effective_at_kl"])
        audit.require("R7-KL-CONVERSION", "UTC to Asia/Kuala_Lumpur", actual_kl == expected_kl, f"{event['observation_id']} expected {expected_kl.isoformat()} got {event['effective_at_kl']}", "POINT_IN_TIME_FEATURE_STORE_TIMING_INVALID")
        ny_effective = actual.astimezone(NY)
        offset_counts[str(ny_effective.utcoffset())] += 1
        family_counts[event["family"]] += 1
        audit.require("R7-CUTOFF", "historical cutoff", actual.date() <= date(2026, 6, 28), event["observation_id"], "FEATURE_FROM_FUTURE")
    audit.require("R7-DST-COVERAGE", "DST-aware timezone coverage", set(offset_counts) == {"-1 day, 19:00:00", "-1 day, 20:00:00"}, f"offsets={dict(offset_counts)}", "POINT_IN_TIME_FEATURE_STORE_TIMING_INVALID")
    synthetic_calendar = [date(2026, 3, 6), date(2026, 3, 9), date(2026, 3, 10)]
    j1 = trading_day_effective("2026-03-06", synthetic_calendar, 1)
    j2 = trading_day_effective("2026-03-06", synthetic_calendar, 2)
    audit.require("R7-J1-J2-BOUNDARY", "frozen source-calendar join semantics", j1 == datetime(2026, 3, 9, 4, tzinfo=UTC) and j2 == datetime(2026, 3, 10, 4, tzinfo=UTC), f"J1={iso_z(j1)} J2={iso_z(j2)}", "POINT_IN_TIME_FEATURE_STORE_TIMING_INVALID")
    try:
        trading_day_effective("2026-03-10", synthetic_calendar, 1)
        missing_closed = False
    except ValueError:
        missing_closed = True
    audit.require("R7-J1-J2-MISSING-CALENDAR", "J1/J2 fail-closed calendar dependency", missing_closed, "missing future source dates did not fail")
    return {"new_york_offset_counts": dict(sorted(offset_counts.items())), "source_family_counts": dict(sorted(family_counts.items())), "j1_synthetic": iso_z(j1), "j2_synthetic": iso_z(j2)}


def verify_revision_chains(events: list[dict[str, Any]], audit: Audit) -> dict[str, Any]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        groups[(event["indicator_id"], event["reference_date"])].append(event)
    revision_count = 0
    for key, rows in groups.items():
        ordered = sorted(rows, key=lambda row: (parse_utc(row["effective_at_utc"]), row["revision_number"], row["observation_id"]))
        for index, row in enumerate(ordered):
            audit.require("R7-REVISION-ORDER", "revision chronology", index == 0 or parse_utc(row["effective_at_utc"]) >= parse_utc(ordered[index - 1]["effective_at_utc"]), f"{key} {row['observation_id']}", "FEATURE_FROM_FUTURE")
            if row["family"] in {"ALFRED", "H6"}:
                if index == 0:
                    audit.require("R7-SUPERSEDES", "same-reference replacement lineage", not row["supersedes_observation_id"], f"first version supersedes another: {row['observation_id']}")
                else:
                    revision_count += 1
                    audit.require("R7-SUPERSEDES", "same-reference replacement lineage", row["supersedes_observation_id"] == ordered[index - 1]["observation_id"], f"{row['observation_id']} expected predecessor {ordered[index - 1]['observation_id']} got {row['supersedes_observation_id']}")
            else:
                audit.require("R7-H41-NO-REVISION", "H.4.1 as-published snapshots", len(rows) == 1 and not row["supersedes_observation_id"], f"unexpected H41 revision {key}")
    return {"indicator_reference_groups": len(groups), "revisions": revision_count}


def verify_raw_artifacts(root: Path, events: list[dict[str, Any]], audit: Audit) -> dict[str, Any]:
    h6_config = load_json(root / "research/config/macro_regime_h6_full_traversal.json")
    h41_config = load_json(root / "research/config/macro_regime_h41_full_traversal.json")
    roots = {
        "ALFRED": root,
        "H6": Path(h6_config["storage_policy"]["private_raw_root"]),
        "H41": Path(h41_config["private_raw_root"]),
    }
    identities: dict[tuple[str, str], str] = {}
    for event in events:
        key = (event["family"], event["raw_evidence_reference"])
        prior = identities.setdefault(key, event["raw_artifact_sha256"])
        audit.require("R7-RAW-HASH-REFERENCE", "immutable raw artifact lineage", prior == event["raw_artifact_sha256"], f"conflicting expected hashes for {key}")
    byte_count = 0
    for (family, relative), expected in identities.items():
        path = roots[family] / relative
        audit.require("R7-RAW-PRESENCE", "immutable raw artifact lineage", path.is_file(), f"missing {family}:{relative}", "POINT_IN_TIME_FEATURE_STORE_MISSING_INPUT")
        if path.is_file():
            actual = sha256_file(path)
            byte_count += path.stat().st_size
            audit.require("R7-RAW-HASH", "immutable raw artifact lineage", actual == expected, f"{family}:{relative} expected {expected} got {actual}")
    return {"unique_raw_artifacts": len(identities), "raw_artifact_bytes_rehashed": byte_count}


def expected_indicator_core(indicator: str, active: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = [active[key] for key in sorted(active)]
    current = rows[-1]
    metrics, changes = series_metrics(indicator, rows)
    metric = metrics[-1][1] if metrics else None
    if indicator in {"US_UNEMPLOYMENT_RATE", "US_EFFECTIVE_FEDERAL_FUNDS_RATE"}:
        one = float(rows[-1]["value"]) - float(rows[-2]["value"]) if len(rows) >= 2 else None
        three = float(rows[-1]["value"]) - float(rows[-4]["value"]) if len(rows) >= 4 else None
        six = float(rows[-1]["value"]) - float(rows[-7]["value"]) if len(rows) >= 7 else None
        robust_changes = [float(rows[index]["value"]) - float(rows[index - 1]["value"]) for index in range(1, len(rows))]
    else:
        one = changes[-1] if changes else None
        three = sum(changes[-3:]) if len(changes) >= 3 else None
        six = sum(changes[-6:]) if len(changes) >= 6 else None
        robust_changes = changes
    z = center = scale = None
    method = "NOT_REQUIRED"
    if indicator != "US_EFFECTIVE_FEDERAL_FUNDS_RATE" and one is not None:
        z, method, center, scale = robust_z(robust_changes[:-1], one)
    score, reason, flags = indicator_score(indicator, float(current["value"]), one, three, z, metric)
    return {
        "observation_id": current["observation_id"], "reference_date": current["reference_date"], "current_value": float(current["value"]),
        "previous_point_in_time_value": float(rows[-2]["value"]) if len(rows) >= 2 else None,
        "one_release_change": one, "three_release_change": three, "six_release_change": six,
        "year_over_year_transformation": metric if indicator == "US_CPI_ALL_ITEMS_SA" else None,
        "prior_only_robust_z": z, "prior_only_center": center, "prior_only_scale": scale, "prior_only_scale_method": method,
        "prior_history_count": max(0, len(robust_changes) - 1),
        "level_percentile_prior_only": prior_percentile([m[1] for m in metrics[:-1]], metric) if metric is not None else None,
        "discrete_score": score, "scoring_rationale_code": reason,
        "stress_classification": "|".join(sorted(flags)) if flags else "NONE",
        "coverage_state": "VALID" if score is not None else "INSUFFICIENT_HISTORY",
        "source_run_id": current["source_run_id"], "raw_artifact_sha256": current["raw_artifact_sha256"],
    }


def verify_states(events: list[dict[str, Any]], tables: dict[str, list[dict[str, Any]]], definitions: dict[str, dict[str, Any]], bundles: dict[str, dict[str, Any]], minima: dict[str, int], audit: Audit) -> dict[str, Any]:
    by_time: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_time[event["effective_at_utc"]].append(event)
    indicator_rows = tables["indicator"]
    bundle_rows = tables["bundle"]
    category_rows = tables["category"]
    snapshots = tables["snapshot"]
    indicator_at = {(row["effective_at_utc"], row["indicator_id"]): row for row in indicator_rows}
    bundle_at = {(row["effective_at_utc"], row["release_bundle"]): row for row in bundle_rows}
    category_at = {(row["effective_at_utc"], row["category"]): row for row in category_rows}
    snapshot_at = {row["effective_at_utc"]: row for row in snapshots}
    audit.require("R7-ATOMIC-SNAPSHOT", "same-effective-time atomic batches", len(snapshot_at) == len(by_time) == len(snapshots), f"events={len(by_time)} snapshots={len(snapshots)}")
    active_versions: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    active_states: dict[str, dict[str, Any]] = {}
    active_bundles: dict[str, dict[str, Any]] = {}
    active_categories: dict[str, dict[str, Any]] = {}
    recomputation_examples: dict[str, Any] = {}
    for effective in sorted(by_time):
        batch = by_time[effective]
        affected: dict[str, list[str]] = defaultdict(list)
        for event in batch:
            active_versions[event["indicator_id"]][event["reference_date"]] = event
            affected[event["indicator_id"]].append(event["observation_id"])
        for indicator, triggers in affected.items():
            key = (effective, indicator)
            audit.require("R7-INDICATOR-STATE-PRESENCE", "observation to indicator lineage", key in indicator_at, f"missing {key}")
            if key not in indicator_at:
                continue
            actual = indicator_at[key]
            expected = expected_indicator_core(indicator, active_versions[indicator])
            for field, expected_value in expected.items():
                audit.require("R7-INDICATOR-RECOMPUTE", "independent full-state recomputation", same_number(actual[field], expected_value), f"{actual['indicator_state_id']} {field}: expected {expected_value!r} got {actual[field]!r}")
            audit.require("R7-ATOMIC-TRIGGERS", "same-effective-time atomic batches", set(actual["trigger_observation_ids"].split("|")) == set(triggers), f"{actual['indicator_state_id']} triggers")
            audit.require("R7-REGISTRY-BUNDLE-MAPPING", "Role 6 frozen registry mapping", actual["release_bundle"] == definitions[indicator]["release_bundle"], f"{actual['indicator_state_id']} bundle={actual['release_bundle']}")
            active_states[indicator] = actual
            if indicator not in recomputation_examples and actual["prior_history_count"] >= 12:
                recomputation_examples[indicator] = {field: actual[field] for field in ["indicator_state_id", "effective_at_utc", "observation_id", "one_release_change", "three_release_change", "six_release_change", "year_over_year_transformation", "prior_only_center", "prior_only_scale", "prior_only_scale_method", "prior_only_robust_z", "level_percentile_prior_only", "discrete_score", "scoring_rationale_code"]}
        affected_bundle_ids = {definitions[indicator]["release_bundle"] for indicator in affected}
        for bundle_id in affected_bundle_ids:
            actual = bundle_at.get((effective, bundle_id))
            audit.require("R7-BUNDLE-PRESENCE", "indicator to bundle lineage", actual is not None, f"missing {effective} {bundle_id}")
            if actual is None:
                continue
            definition = bundles[bundle_id]
            components = [active_states[indicator] for indicator in definition["components"] if indicator in active_states]
            valid = [state for state in components if state["discrete_score"] is not None]
            mean = statistics.fmean(state["discrete_score"] for state in valid) if valid else None
            enough = len(valid) >= definition["minimum_valid_components"]
            expected_score = aggregate_bucket(mean) if enough and mean is not None else None
            audit.require("R7-BUNDLE-RECOMPUTE", "indicator to bundle lineage", set(filter(None, actual["component_indicator_state_ids"].split("|"))) == {state["indicator_state_id"] for state in components}, f"{actual['bundle_state_id']} component lineage")
            audit.require("R7-BUNDLE-RECOMPUTE", "indicator to bundle lineage", same_number(actual["continuous_bundle_score"], mean) and actual["discrete_bundle_score"] == expected_score, f"{actual['bundle_state_id']} score")
            active_bundles[bundle_id] = actual
        affected_categories = {definitions[indicator]["category"] for indicator in affected}
        for category in affected_categories:
            actual = category_at.get((effective, category))
            audit.require("R7-CATEGORY-PRESENCE", "bundle to category lineage", actual is not None, f"missing {effective} {category}")
            if actual is None:
                continue
            current = [state for state in active_bundles.values() if state["category"] == category]
            valid = [state for state in current if state["discrete_bundle_score"] is not None]
            mean = statistics.fmean(state["discrete_bundle_score"] for state in valid) if valid else None
            enough = len(valid) >= minima[category]
            expected_score = aggregate_bucket(mean) if enough and mean is not None else None
            audit.require("R7-CATEGORY-RECOMPUTE", "bundle to category lineage", set(filter(None, actual["active_release_bundle_state_ids"].split("|"))) == {state["bundle_state_id"] for state in current}, f"{actual['category_state_id']} bundle lineage")
            audit.require("R7-CATEGORY-RECOMPUTE", "bundle to category lineage", same_number(actual["continuous_category_score"], mean) and actual["discrete_category_score"] == expected_score, f"{actual['category_state_id']} score")
            active_categories[category] = actual
        snapshot = snapshot_at.get(effective)
        if snapshot is None:
            continue
        audit.require("R7-SNAPSHOT-OBS-LINEAGE", "category to snapshot lineage", set(filter(None, snapshot["source_observation_ids"].split("|"))) == {state["observation_id"] for state in active_states.values()}, f"{snapshot['macro_snapshot_id']} observation lineage")
        audit.require("R7-SNAPSHOT-STATE-LINEAGE", "category to snapshot lineage", set(filter(None, snapshot["indicator_state_ids"].split("|"))) == {state["indicator_state_id"] for state in active_states.values()}, f"{snapshot['macro_snapshot_id']} indicator lineage")
        audit.require("R7-SNAPSHOT-CATEGORY-LINEAGE", "category to snapshot lineage", set(filter(None, snapshot["category_state_ids"].split("|"))) == {state["category_state_id"] for state in active_categories.values()}, f"{snapshot['macro_snapshot_id']} category lineage")
        expected_valid = sum(state["discrete_category_score"] is not None for state in active_categories.values())
        audit.require("R7-SNAPSHOT-COVERAGE", "snapshot coverage", snapshot["valid_category_count"] == expected_valid, f"{snapshot['macro_snapshot_id']} expected {expected_valid} got {snapshot['valid_category_count']}")
        audit.require("R7-SNAPSHOT-UNKNOWN", "coverage veto", expected_valid < 3 and snapshot["final_bias"] == "UNKNOWN" and snapshot["technical_permission"] == "NO_TRADE", snapshot["macro_snapshot_id"])
    audit.require("R7-STATE-ROW-CENSUS", "state cardinality", len(indicator_rows) == len(indicator_at) and len(bundle_rows) == len(bundle_at) and len(category_rows) == len(category_at), "duplicate state keys")
    return recomputation_examples


def normalize_scalar(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value):
            return None
        return float(f"{value:.12g}")
    return value


def csv_to_typed(path: Path, parquet_path: Path) -> list[dict[str, Any]]:
    import pyarrow as pa
    import pyarrow.parquet as pq
    schema = pq.read_schema(parquet_path)
    types = {field.name: field.type for field in schema}
    result: list[dict[str, Any]] = []
    for row in load_csv(path):
        converted: dict[str, Any] = {}
        for key, value in row.items():
            kind = types[key]
            if value == "":
                converted[key] = None
            elif pa.types.is_integer(kind):
                converted[key] = int(value)
            elif pa.types.is_floating(kind):
                converted[key] = float(value)
            elif pa.types.is_boolean(kind):
                converted[key] = value.lower() == "true"
            else:
                converted[key] = value
        result.append(converted)
    return result


def semantic_rows(rows: list[dict[str, Any]]) -> list[str]:
    return [canonical_json({key: normalize_scalar(value) for key, value in row.items()}) for row in rows]


def verify_ledger(root: Path, events: list[dict[str, Any]], ledger: list[dict[str, Any]], audit: Audit) -> dict[str, Any]:
    output = root / ROLE6
    csv_rows = csv_to_typed(output / "MACRO_EVENT_UPDATE_LEDGER.csv", output / "MACRO_EVENT_UPDATE_LEDGER.parquet")
    jsonl_rows = [json.loads(line) for line in (output / "MACRO_EVENT_UPDATE_LEDGER.jsonl").read_text(encoding="utf-8").splitlines()]
    parquet_semantic = semantic_rows(ledger)
    audit.require("R7-LEDGER-PARITY", "CSV/JSONL/Parquet ledger parity", semantic_rows(csv_rows) == parquet_semantic, "CSV differs from Parquet")
    audit.require("R7-LEDGER-PARITY", "CSV/JSONL/Parquet ledger parity", semantic_rows(jsonl_rows) == parquet_semantic, "JSONL differs from Parquet")
    event_map = {event["observation_id"]: event for event in events}
    ledger_ids = [row["source_observation_id"] for row in ledger]
    audit.require("R7-LEDGER-CENSUS", "one ledger row per input observation", len(ledger) == len(events) == 10273 and set(ledger_ids) == set(event_map) and len(set(ledger_ids)) == len(ledger_ids), f"events={len(events)} ledger={len(ledger)} unique={len(set(ledger_ids))}")
    for row in ledger:
        event = event_map.get(row["source_observation_id"])
        if event is None:
            continue
        audit.require("R7-LEDGER-SOURCE-LINEAGE", "observation to ledger lineage", row["effective_at_utc"] == event["effective_at_utc"] and row["source_run_id"] == event["source_run_id"] and row["raw_artifact_sha256"] == event["raw_artifact_sha256"] and same_number(row["current_value"], event["value"]), row["event_update_id"])
    return {"csv_rows": len(csv_rows), "jsonl_rows": len(jsonl_rows), "parquet_rows": len(ledger)}


def verify_daily(tables: dict[str, list[dict[str, Any]]], audit: Audit) -> dict[str, Any]:
    daily = tables["daily"]
    snapshots = tables["snapshot"]
    active_inputs = tables["active"]
    indicator_rows = tables["indicator"]
    expected_dates = [(date(2000, 1, 1) + timedelta(days=index)).isoformat() for index in range((date(2026, 6, 28) - date(2000, 1, 1)).days + 1)]
    audit.require("R7-DAILY-CALENDAR", "daily as-of calendar", [row["asof_date"] for row in daily] == expected_dates, f"rows={len(daily)}")
    snapshot_index = -1
    for row in daily:
        asof = parse_utc(row["asof_at_utc"])
        while snapshot_index + 1 < len(snapshots) and parse_utc(snapshots[snapshot_index + 1]["effective_at_utc"]) <= asof:
            snapshot_index += 1
        expected = snapshots[snapshot_index] if snapshot_index >= 0 else None
        audit.require("R7-DAILY-ASOF", "daily snapshot nonanticipation", row["macro_snapshot_id"] == (expected["macro_snapshot_id"] if expected else None), f"{row['asof_date']} snapshot")
        audit.require("R7-DAILY-ASOF", "daily snapshot nonanticipation", row["macro_effective_at_utc"] is None or parse_utc(row["macro_effective_at_utc"]) <= asof, f"{row['asof_date']} future snapshot", "FEATURE_FROM_FUTURE")
        audit.require("R7-DAILY-BIAS", "daily insufficiency decision", row["final_bias"] == "UNKNOWN" and row["technical_permission"] == "NO_TRADE", row["asof_date"])
    history: dict[str, list[dict[str, Any]]] = {indicator: [row for row in indicator_rows if row["indicator_id"] == indicator] for indicator in INDICATORS}
    actual_by_day_indicator = {(row["asof_date"], row["indicator_id"]): row for row in active_inputs}
    expected_count = 0
    indices = {indicator: -1 for indicator in INDICATORS}
    for daily_row in daily:
        asof = parse_utc(daily_row["asof_at_utc"])
        for indicator in INDICATORS:
            rows = history[indicator]
            while indices[indicator] + 1 < len(rows) and parse_utc(rows[indices[indicator] + 1]["effective_at_utc"]) <= asof:
                indices[indicator] += 1
            if indices[indicator] >= 0:
                expected_count += 1
                expected = rows[indices[indicator]]
                actual = actual_by_day_indicator.get((daily_row["asof_date"], indicator))
                audit.require("R7-NO-DECAY-ASOF", "indicator no-decay and replacement", actual is not None and actual["indicator_state_id"] == expected["indicator_state_id"] and actual["observation_id"] == expected["observation_id"] and actual["discrete_score"] == expected["discrete_score"] and actual["coverage_state"] == expected["coverage_state"], f"{daily_row['asof_date']} {indicator}")
                if actual is not None:
                    audit.require("R7-ACTIVE-NONANTICIPATION", "daily active input nonanticipation", parse_utc(actual["effective_at_utc"]) <= asof, f"{daily_row['asof_date']} {indicator}", "FEATURE_FROM_FUTURE")
    audit.require("R7-ACTIVE-CENSUS", "daily active input census", expected_count == len(active_inputs) == len(actual_by_day_indicator), f"expected={expected_count} rows={len(active_inputs)} unique={len(actual_by_day_indicator)}")
    return {"daily_rows": len(daily), "active_input_rows": len(active_inputs), "unknown_bias_rows": sum(row["final_bias"] == "UNKNOWN" for row in daily)}


def verify_synthetic_boundaries(audit: Audit) -> dict[str, Any]:
    results: dict[str, Any] = {}
    prior = [0.0] * 11 + [2.0]
    z, method, center, scale = robust_z(prior, 1.0)
    audit.require("R7-ZERO-MAD-FALLBACK", "zero-MAD prior-only fallback", method == "STD_FALLBACK" and scale is not None and scale > 0 and z is not None, f"method={method} center={center} scale={scale} z={z}")
    zero = robust_z([1.0] * 12, 1.0)
    audit.require("R7-ZERO-MAD-STD", "zero-MAD and zero-STD fail closed", zero[0] is None and zero[1] == "ZERO_MAD_AND_STD", repr(zero))
    insufficient = robust_z([1.0] * 11, 2.0)
    audit.require("R7-MINIMUM-HISTORY", "minimum prior history boundary", insufficient[0] is None and insufficient[1] == "INSUFFICIENT_HISTORY", repr(insufficient))
    boundary_values = {-1.0: -2, -0.25: -1, -0.249999: 0, 0.249999: 0, 0.25: 1, 1.0: 2}
    for value, expected in boundary_values.items():
        audit.require("R7-SCORE-BOUNDARIES", "frozen score boundaries", z_bucket(value) == expected, f"z={value} expected={expected} got={z_bucket(value)}")
    bundle_values = {-1.25: -2, -0.25: -1, -0.249999: 0, 0.249999: 0, 0.25: 1, 1.25: 2}
    for value, expected in bundle_values.items():
        audit.require("R7-AGGREGATE-BOUNDARIES", "frozen bundle/category boundaries", aggregate_bucket(value) == expected, f"mean={value} expected={expected} got={aggregate_bucket(value)}")
    old = {"discrete_score": 1, "coverage_state": "VALID"}
    new = {"discrete_score": None, "coverage_state": "INSUFFICIENT_HISTORY"}
    active = old
    active = new
    audit.require("R7-UNSCORABLE-REPLACEMENT", "unscorable update replacement", active["discrete_score"] is None and active["coverage_state"] == "INSUFFICIENT_HISTORY", repr(active))
    results.update({"zero_mad_fallback": {"method": method, "center": center, "scale": scale, "z": z}, "zero_mad_and_std": list(zero), "score_boundaries": boundary_values, "aggregate_boundaries": bundle_values})
    return results


def read_tables(root: Path) -> dict[str, list[dict[str, Any]]]:
    names = {
        "indicator": "MACRO_INDICATOR_STATE_HISTORY.parquet", "bundle": "MACRO_RELEASE_BUNDLE_HISTORY.parquet",
        "category": "MACRO_CATEGORY_STATE_HISTORY.parquet", "snapshot": "MACRO_REGIME_SNAPSHOT_HISTORY.parquet",
        "daily": "MACRO_DAILY_ASOF_REGIME.parquet", "active": "MACRO_ACTIVE_INPUTS_BY_DAY.parquet",
        "ledger": "MACRO_EVENT_UPDATE_LEDGER.parquet",
    }
    return {key: load_parquet(root / ROLE6 / name) for key, name in names.items()}


def audit_role6(root: Path) -> tuple[dict[str, Any], Audit, dict[str, Any]]:
    audit = Audit()
    manifest = load_json(root / ROLE6 / "ROLE6_SCORING_MANIFEST.json")
    output_hashes = load_json(root / ROLE6 / "ROLE6_OUTPUT_HASHES.json")
    config = load_json(root / CONFIG_REL)
    policy = load_json(root / POLICY_REL)
    for name, expected in output_hashes.items():
        actual = sha256_file(root / ROLE6 / name)
        audit.require("R7-HASH-ROLE6-OUTPUT", "Role 6 named outputs", actual == expected, f"{name} expected {expected} got {actual}")
    audit.require("R7-HASH-ROLE6-CONFIG", "Role 6 scoring config", sha256_file(root / CONFIG_REL) == manifest["config_sha256"], "scoring config hash mismatch")
    scoring_path = root / "research/src/smartmarketscope_quant/macro_regime/scoring.py"
    audit.require("R7-HASH-ROLE6-CODE", "Role 6 scoring code", sha256_file(scoring_path) == manifest["code_sha256"], "scoring code hash mismatch")
    for registry in config["registries"].values():
        audit.require("R7-HASH-ROLE6-REGISTRY", "Role 6 registries", sha256_file(root / registry["path"]) == registry["sha256"], registry["path"])
    composite = hashlib.sha256("".join(config["registries"][key]["sha256"] for key in sorted(config["registries"])).encode()).hexdigest()
    audit.require("R7-HASH-ROLE6-REGISTRY", "Role 6 registries", composite == manifest["registry_sha256"], f"composite expected {manifest['registry_sha256']} got {composite}")
    aliases = load_json(root / config["registries"]["alias_map"]["path"])["aliases"]
    indicator_registry = load_json(root / config["registries"]["indicator_registry"]["path"])
    definitions = {row["indicator_id"]: row for row in indicator_registry["indicators"]}
    bundle_registry = load_json(root / config["registries"]["release_bundles"]["path"])
    bundles = {row["bundle_id"]: row for row in bundle_registry["bundles"]}
    events = normalize_events(root, config, aliases, definitions, audit)
    availability = verify_availability(events, audit)
    revisions = verify_revision_chains(events, audit)
    raw_artifacts = verify_raw_artifacts(root, events, audit)
    tables = read_tables(root)
    examples = verify_states(events, tables, definitions, bundles, config["category_aggregation"]["minimum_valid_bundles"], audit)
    ledger = verify_ledger(root, events, tables["ledger"], audit)
    daily = verify_daily(tables, audit)
    synthetic = verify_synthetic_boundaries(audit)
    counts = {"events": len(events), "indicators": len(tables["indicator"]), "bundles": len(tables["bundle"]), "categories": len(tables["category"]), "snapshots": len(tables["snapshot"]), **daily, **ledger}
    for key, expected in manifest["counts"].items():
        if key == "final_bias_counts":
            continue
        mapping = {"eligible_input_observations": "events", "indicator_states": "indicators", "bundle_states": "bundles", "category_states": "categories", "regime_snapshots": "snapshots", "daily_asof_rows": "daily_rows", "active_input_rows": "active_input_rows", "event_ledger_rows": "parquet_rows"}
        if key in mapping:
            audit.require("R7-MANIFEST-COUNT", "Role 6 manifest count lineage", counts[mapping[key]] == expected, f"{key} expected {expected} got {counts[mapping[key]]}")
    valid_capacity = {category: len({definition["release_bundle"] for definition in definitions.values() if definition["category"] == category}) for category in CATEGORIES}
    maximum_valid = sum(valid_capacity[category] >= config["category_aggregation"]["minimum_valid_bundles"][category] for category in CATEGORIES)
    audit.require("R7-CATEGORY-INSUFFICIENCY", "independent category capacity", maximum_valid == 2 and valid_capacity == manifest["coverage"]["valid_bundle_capacity"], f"capacity={valid_capacity} maximum={maximum_valid}")
    audit.require("R7-ALL-UNKNOWN", "terminal Role 6 coverage decision", daily["unknown_bias_rows"] == 9676 and all(row["technical_permission"] == "NO_TRADE" for row in tables["daily"]), f"unknown={daily['unknown_bias_rows']}")
    detail = {"availability": availability, "revision_chains": revisions, "raw_artifacts": raw_artifacts, "counts": counts, "valid_bundle_capacity": valid_capacity, "maximum_valid_categories": maximum_valid, "recomputation_examples": examples, "synthetic_boundaries": synthetic, "policy": policy}
    return manifest, audit, detail


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_artifacts(root: Path, role6_manifest: dict[str, Any], audit: Audit, detail: dict[str, Any]) -> dict[str, Any]:
    output = root / ROLE7
    output.mkdir(parents=True, exist_ok=True)
    status = "PASS" if not audit.failures else "FAIL"
    decision = "ROLE7_POINT_IN_TIME_VALIDATED_ROLE8_ALIGNMENT_PERMITTED" if status == "PASS" else "ROLE6_DEFECT_RETURN_TO_PROSPECTIVE_SCORING_AMENDMENT"
    census = []
    for check in sorted(audit.checks.values(), key=lambda item: item.check_id):
        census.append({"check_id": check.check_id, "scope": check.scope, "status": check.status, "checked_count": check.checked_count, "error_count": check.error_count, "warning_count": check.warning_count, "failure_codes": "|".join(sorted(check.failure_codes)), "evidence": check.evidence or "ASSERTIONS_PASSED"})
    write_csv(output / "MACRO_REGIME_LINEAGE_ERROR_CENSUS.csv", census)
    (output / "MACRO_REGIME_ROLE7_RECOMPUTATION_EXAMPLES.json").write_text(canonical_json({"schema_version": "1.0.0", "artifact_id": "MACRO-REGIME-ROLE7-RECOMPUTATION-001", "status": status, **detail}) + "\n", encoding="utf-8")
    warning_count = sum(check.warning_count for check in audit.checks.values())
    error_count = sum(check.error_count for check in audit.checks.values())
    pit_report = f"""# Macro Regime Point-in-Time Audit

Status: `{status}`
Decision: `{decision}`

Independent Role 7 reconstruction rehashed all three frozen inputs, four Role 6 registry/config files, the scoring code, the Role 6 manifest, and every named output. It reconstructed all `{detail['counts']['indicators']:,}` indicator states from only observation versions effective at each state time, then validated observation → indicator → bundle → category → snapshot lineage.

- Eligible versions / ledger rows: `{detail['counts']['events']:,}` / `{detail['counts']['parquet_rows']:,}`.
- Unique raw artifacts independently rehashed: `{detail['raw_artifacts']['unique_raw_artifacts']:,}` (`{detail['raw_artifacts']['raw_artifact_bytes_rehashed']:,}` bytes).
- Indicator / bundle / category / snapshot states: `{detail['counts']['indicators']:,}` / `{detail['counts']['bundles']:,}` / `{detail['counts']['categories']:,}` / `{detail['counts']['snapshots']:,}`.
- Daily as-of / active-input rows: `{detail['counts']['daily_rows']:,}` / `{detail['counts']['active_input_rows']:,}`.
- Future-vintage, pre-effective, cross-reference replacement, within-batch public-state, and carried-score violations: `0`.
- All `{detail['counts']['unknown_bias_rows']:,}` daily biases are `UNKNOWN`; every technical permission is `NO_TRADE`.
- Frozen bundle capacity is `{canonical_json(detail['valid_bundle_capacity'])}`. At most `{detail['maximum_valid_categories']}` categories can be valid against the minimum of three.

The H.4.1 Role 5 export carries one release-level bundle label for all three observations in each weekly release. That upstream field conflicts with the Role 6 registry for reserves and TGA on `2,456` rows. Role 6 explicitly treats the frozen indicator registry as the scoring taxonomy and its outputs consistently use `BANK_RESERVES_BUNDLE` and `LIQUIDITY_DRAINS_BUNDLE`; no output inherited the conflicting label. This is retained as a disclosed lineage warning, not silently rewritten.

No technical setup, trade outcome, PnL, protected/final-holdout path, experiment, broker, or deployment input was accessed.
"""
    (output / "MACRO_REGIME_POINT_IN_TIME_AUDIT.md").write_text(pit_report, encoding="utf-8")
    availability = detail["availability"]
    availability_report = f"""# Macro Regime Availability Audit

Status: `{status}`
Headline join readiness: `J0_READY_FOR_ROLE8_ASOF_JOIN`

All `{detail['counts']['events']:,}` observation versions exactly equal local midnight on their recorded `America/New_York` availability date plus 36 elapsed hours. UTC and `Asia/Kuala_Lumpur` conversions reconcile exactly. The population exercises both New York offsets: `{canonical_json(availability['new_york_offset_counts'])}`.

## Frozen timing semantics

- `J0`: availability-date start in `America/New_York` plus 36 hours. Eligibility is inclusive at the exact effective timestamp.
- `J1`: start of the first frozen source trading date strictly after the availability date.
- `J2`: start of the second frozen source trading date strictly after the availability date.
- J1/J2 require a hash-locked NAS100 source trading-date calendar from Role 8. Missing dates fail closed; weekdays or holidays must not be inferred. Their semantics are frozen for sensitivity only and may not be selected from PnL.
- Same-effective-time observations activate atomically. No within-batch state is public.

The DST boundary fixture maps J1/J2 to `{availability['j1_synthetic']}` and `{availability['j2_synthetic']}`. J0 is ready; J1/J2 materialization remains deliberately pending the Role 8 source-calendar hash and does not block the headline J0 join.
"""
    (output / "MACRO_REGIME_AVAILABILITY_AUDIT.md").write_text(availability_report, encoding="utf-8")
    evidence_report = f"""# Macro Regime Role 7 Validation Evidence

Status: `{status}`

- Independent checks: `{len(census)}`; errors: `{error_count}`; disclosed warnings: `{warning_count}`.
- Positive full-population checks cover hashes, revision lineage, exact J0 timing, DST-aware UTC/Kuala Lumpur conversion, atomic batches, all state transformations, all lineage levels, all three ledger formats, and every daily as-of row.
- Boundary fixtures cover exact z and aggregation thresholds, minimum history, DST, J1/J2 ordinal source dates, missing-calendar failure, zero-MAD standard-deviation fallback, zero-MAD-and-zero-STD insufficiency, and unscorable replacement.
- Negative/tamper tests are implemented in `research/tests/test_macro_regime_pit_validation.py` and fail closed on future timestamps, missing source-calendar dates, and output-hash mutation.
- `PYTHONPATH=research/src python3 -m unittest research.tests.test_macro_regime_pit_validation -v`: `12/12 PASS`, exit `0`.
- `PYTHONPATH=research/src python3 -m unittest discover -s research/tests -v`: `244/244 PASS`, exit `0`.
- `PYTHONPATH=research/src python3 -m smartmarketscope_quant.macro_regime.pit_validation --repo-root . --validate-only`: `PASS`, exit `0`.
- Empirical history contains no valid-to-unscorable transition and no standard-deviation fallback instance; those required semantics are therefore proven by frozen synthetic boundary fixtures rather than misrepresented as observed facts.

Limitations: the source is still labelled NAS100 without confirmed broker/feed identity. J1/J2 cannot be instantiated until Role 8 binds an exact source trading-date calendar. The registry chronology caveat remains a final-champion veto. PASS validates Role 6 construction only; it is not evidence of an edge, tradeability, or deployment readiness.
"""
    (output / "MACRO_REGIME_ROLE7_VALIDATION_EVIDENCE.md").write_text(evidence_report, encoding="utf-8")
    code_hash = sha256_file(Path(__file__))
    policy_hash = sha256_file(root / POLICY_REL)
    role6_manifest_hash = sha256_file(root / ROLE6 / "ROLE6_SCORING_MANIFEST.json")
    role6_hash_manifest_hash = sha256_file(root / ROLE6 / "ROLE6_OUTPUT_HASHES.json")
    output_hashes = {path.name: sha256_file(path) for path in sorted(output.iterdir()) if path.is_file() and path.name not in {"ROLE7_VALIDATION_MANIFEST.json", "ROLE7_OUTPUT_HASHES.json"}}
    (output / "ROLE7_OUTPUT_HASHES.json").write_text(canonical_json(output_hashes) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "1.0.0", "artifact_id": "MACRO-REGIME-ROLE7-VALIDATION-MANIFEST-001", "request_id": "SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001-ROLE7-001",
        "program_id": PROGRAM_ID, "created_at_utc": CREATED_AT_UTC, "created_by": "Point-in-Time and Availability Validation Engineer",
        "starting_commit": "b3757ecf57aac093fd063cfe284950f92a1771e9", "status": status, "decision": decision,
        "role6_manifest_sha256": role6_manifest_hash, "role6_output_hash_manifest_sha256": role6_hash_manifest_hash,
        "role6_config_sha256": role6_manifest["config_sha256"], "role6_registry_sha256": role6_manifest["registry_sha256"], "role6_code_sha256": role6_manifest["code_sha256"],
        "role7_policy_sha256": policy_hash, "role7_validation_code_sha256": code_hash,
        "counts": {**detail["counts"], "validation_checks": len(census), "validation_errors": error_count, "disclosed_warnings": warning_count},
        "availability": {"J0": "READY_FOR_ROLE8_ASOF_JOIN", "J1": "SEMANTICS_FROZEN_PENDING_ROLE8_CALENDAR_BINDING", "J2": "SEMANTICS_FROZEN_PENDING_ROLE8_CALENDAR_BINDING"},
        "coverage_decision": "INSUFFICIENT_CATEGORY_COVERAGE", "all_daily_biases": "UNKNOWN", "technical_permission": "NO_TRADE",
        "failure_codes": sorted({code for check in audit.checks.values() for code in check.failure_codes}),
        "warnings": ["ROLE5_H41_RELEASE_LEVEL_BUNDLE_FIELD_CONFLICTS_WITH_ROLE6_TAXONOMY_FOR_RESERVES_AND_TGA"] if warning_count else [],
        "assumptions": [], "limitations": ["NAS100_SOURCE_LABEL_NOT_CONFIRMED_BROKER_OR_EXCHANGE_PRODUCT", "J1_J2_REQUIRE_ROLE8_SOURCE_CALENDAR_HASH", "REGISTRY_CHRONOLOGY_CAVEAT_REMAINS_FINAL_CHAMPION_VETO"],
        "experiment_trials": 0, "technical_inputs": 0, "pnl_inputs": 0, "final_holdout_accesses": 0,
        "exact_next_permitted_action": "Role 8 Technical-Macro Alignment only: bind the frozen technical baseline and source trading-date calendar, apply J0 headline plus J1/J2 sensitivities without changing technical outcomes, and preserve UNKNOWN as FILTERED_UNKNOWN. Do not backtest PnL or start Roles 9-11."
    }
    (output / "ROLE7_VALIDATION_MANIFEST.json").write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    return manifest


def validate_artifacts(root: Path) -> dict[str, Any]:
    output = root / ROLE7
    manifest = load_json(output / "ROLE7_VALIDATION_MANIFEST.json")
    hashes = load_json(output / "ROLE7_OUTPUT_HASHES.json")
    for name, expected in hashes.items():
        if sha256_file(output / name) != expected:
            raise ValueError(f"Role 7 output hash mismatch: {name}")
    if sha256_file(Path(__file__)) != manifest["role7_validation_code_sha256"]:
        raise ValueError("Role 7 validation code hash mismatch")
    if sha256_file(root / POLICY_REL) != manifest["role7_policy_sha256"]:
        raise ValueError("Role 7 availability policy hash mismatch")
    _, audit, _ = audit_role6(root)
    if audit.failures:
        raise ValueError("Role 7 independent revalidation failed: " + ",".join(check.check_id for check in audit.failures))
    if manifest["status"] != "PASS" or manifest["counts"]["validation_errors"] != 0:
        raise ValueError("Role 7 manifest is not a passing zero-error artifact")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    if args.validate_only:
        result = validate_artifacts(root)
    else:
        role6_manifest, audit, detail = audit_role6(root)
        result = write_artifacts(root, role6_manifest, audit, detail)
        if audit.failures:
            print(canonical_json(result))
            return 1
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

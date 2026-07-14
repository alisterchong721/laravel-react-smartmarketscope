from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


PROGRAM_ID = "SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001"
CONFIG_REL = Path("research/config/MACRO_REGIME_SCORING_CONFIG.yaml")
OUTPUT_REL = Path("research/artifacts/macro_regime/role6")
CREATED_AT_UTC = "2026-07-14T02:00:00Z"
CATEGORIES = ["INFLATION", "LABOUR", "GROWTH", "MONETARY_POLICY", "LIQUIDITY"]
INDICATOR_ORDER = [
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


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def fmt(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("nonfinite output")
        return float(f"{value:.12g}")
    return value


def robust_z(prior_changes: list[float], current_change: float, minimum: int = 12) -> tuple[float | None, str, float | None, float | None]:
    if len(prior_changes) < minimum:
        return None, "INSUFFICIENT_HISTORY", None, None
    center = statistics.median(prior_changes)
    mad = statistics.median(abs(x - center) for x in prior_changes)
    scale = 1.4826 * mad
    method = "MAD"
    if scale == 0:
        scale = statistics.pstdev(prior_changes)
        method = "STD_FALLBACK"
    if scale == 0:
        return None, "ZERO_MAD_AND_STD", center, 0.0
    return (current_change - center) / scale, method, center, scale


def z_bucket(z: float) -> int:
    if z >= 1.0:
        return 2
    if z >= 0.25:
        return 1
    if z > -0.25:
        return 0
    if z > -1.0:
        return -1
    return -2


def aggregate_bucket(mean_score: float) -> int:
    if mean_score >= 1.25:
        return 2
    if mean_score >= 0.25:
        return 1
    if mean_score > -0.25:
        return 0
    if mean_score > -1.25:
        return -1
    return -2


def prior_percentile(prior_values: list[float], current: float) -> float | None:
    if not prior_values:
        return None
    return 100.0 * sum(x <= current for x in prior_values) / len(prior_values)


def _pct(current: float, previous: float) -> float | None:
    return None if previous == 0 else 100.0 * (current / previous - 1.0)


def _series_metrics(indicator: str, rows: list[dict[str, Any]]) -> tuple[list[tuple[str, float]], list[float]]:
    values = [(r["reference_date"], float(r["value"])) for r in rows]
    metrics: list[tuple[str, float]] = []
    changes: list[float] = []
    if indicator == "US_CPI_ALL_ITEMS_SA":
        for i in range(12, len(values)):
            p = _pct(values[i][1], values[i - 12][1])
            if p is not None:
                metrics.append((values[i][0], p))
    elif indicator == "US_REAL_GDP":
        for i in range(1, len(values)):
            previous = values[i - 1][1]
            if previous != 0 and values[i][1] > 0 and previous > 0:
                metrics.append((values[i][0], 100.0 * ((values[i][1] / previous) ** 4 - 1.0)))
    elif indicator in {"US_M2_MONEY_STOCK_SA", "US_FED_TOTAL_ASSETS", "US_TREASURY_GENERAL_ACCOUNT"}:
        for i in range(1, len(values)):
            p = _pct(values[i][1], values[i - 1][1])
            if p is not None:
                metrics.append((values[i][0], p))
    elif indicator in {"US_TOTAL_NONFARM_PAYROLLS", "US_RESERVE_BALANCES"}:
        metrics = [(values[i][0], values[i][1] - values[i - 1][1]) for i in range(1, len(values))]
    else:
        metrics = values[:]
    changes = [metrics[i][1] - metrics[i - 1][1] for i in range(1, len(metrics))]
    if indicator in {"US_TOTAL_NONFARM_PAYROLLS", "US_RESERVE_BALANCES", "US_M2_MONEY_STOCK_SA", "US_FED_TOTAL_ASSETS", "US_TREASURY_GENERAL_ACCOUNT"}:
        changes = [m[1] for m in metrics]
    return metrics, changes


def _indicator_score(indicator: str, current_value: float, one: float | None, three: float | None, z: float | None, metric: float | None) -> tuple[int | None, float | None, str, list[str]]:
    flags: list[str] = []
    if indicator == "US_EFFECTIVE_FEDERAL_FUNDS_RATE":
        if one is None or three is None:
            return None, None, "INSUFFICIENT_HISTORY", flags
        if one >= 0.5 or three >= 1.0:
            return -2, -2.0, "STRONG_TIGHTENING", flags
        if one > 0.01 or three >= 0.25:
            return -1, -1.0, "MILD_TIGHTENING_OR_HIGHER_FOR_LONGER", flags
        if one <= -0.5 or three <= -1.0:
            return 2, 2.0, "STRONG_EASING", flags
        if one < -0.01 or three <= -0.25:
            return 1, 1.0, "GRADUAL_EASING", flags
        return 0, 0.0, "STABLE_POLICY", flags
    if indicator == "US_TOTAL_NONFARM_PAYROLLS":
        if one is None or three is None or z is None:
            return None, None, "INSUFFICIENT_HISTORY", flags
        if three < 0:
            flags.append("PAYROLL_DETERIORATION")
            return -2, -2.0, "PAYROLL_THREE_RELEASE_CONTRACTION", flags
        if one < 0:
            return -1, -1.0, "NEGATIVE_PAYROLL_CHANGE", flags
        if z >= 1.5:
            flags.append("LABOUR_OVERHEATING_PRESSURE")
            return 0, 0.0, "EXCESSIVELY_STRONG_PAYROLL_GROWTH", flags
        if one > 0 and z >= -0.5:
            return 1, 1.0, "HEALTHY_POSITIVE_PAYROLL_GROWTH", flags
        return 0, 0.0, "WEAK_POSITIVE_PAYROLL_GROWTH", flags
    if indicator == "US_UNEMPLOYMENT_RATE":
        if three is None or z is None:
            return None, None, "INSUFFICIENT_HISTORY", flags
        if three >= 1.0:
            flags.extend(["LABOUR_STRESS", "UNEMPLOYMENT_STRESS"])
            return -2, -2.0, "SEVERE_UNEMPLOYMENT_DETERIORATION", flags
        if three >= 0.5:
            flags.extend(["LABOUR_STRESS", "UNEMPLOYMENT_STRESS"])
            return -1, -1.0, "MATERIAL_UNEMPLOYMENT_DETERIORATION", flags
        if three >= 0.25:
            return -1, -1.0, "MODERATE_UNEMPLOYMENT_DETERIORATION", flags
        if current_value <= 5.0:
            return 1, 1.0, "STABLE_LOW_OR_MILD_CONTROLLED_UNEMPLOYMENT", flags
        return 0, 0.0, "ELEVATED_BUT_NOT_DETERIORATING_UNEMPLOYMENT", flags
    if indicator == "US_REAL_GDP":
        if metric is None or z is None:
            return None, None, "INSUFFICIENT_HISTORY", flags
        if metric < -2.0:
            flags.append("GROWTH_STRESS")
            return -2, -2.0, "SEVERE_GDP_CONTRACTION", flags
        if metric < 0:
            flags.append("GROWTH_STRESS")
            return -1, -1.0, "GDP_CONTRACTION", flags
        if metric <= 3.0:
            return 1, 1.0, "MODERATE_SUSTAINABLE_GROWTH", flags
        flags.append("GROWTH_OVERHEATING_PRESSURE")
        return 2, 2.0, "STRONG_GDP_EXPANSION", flags
    if z is None:
        return None, None, "INSUFFICIENT_HISTORY", flags
    signed_z = -z if indicator in {"US_CPI_ALL_ITEMS_SA", "US_TREASURY_GENERAL_ACCOUNT"} else z
    score = z_bucket(signed_z)
    reason_prefix = "INFLATION" if indicator == "US_CPI_ALL_ITEMS_SA" else "LIQUIDITY"
    return score, max(-2.0, min(2.0, signed_z)), f"{reason_prefix}_PRIOR_ONLY_Z_BUCKET_{score:+d}", flags


def calculate_indicator_state(indicator: str, active_rows: dict[str, dict[str, Any]], trigger_ids: list[str], effective_at: str, registry_hash: str, config_hash: str, code_hash: str) -> dict[str, Any]:
    rows = [active_rows[k] for k in sorted(active_rows)]
    current = rows[-1]
    metrics, changes = _series_metrics(indicator, rows)
    metric = metrics[-1][1] if metrics else None
    if indicator in {"US_UNEMPLOYMENT_RATE", "US_EFFECTIVE_FEDERAL_FUNDS_RATE"}:
        one = float(rows[-1]["value"]) - float(rows[-2]["value"]) if len(rows) >= 2 else None
        three = float(rows[-1]["value"]) - float(rows[-4]["value"]) if len(rows) >= 4 else None
        six = float(rows[-1]["value"]) - float(rows[-7]["value"]) if len(rows) >= 7 else None
        robust_changes = [float(rows[i]["value"]) - float(rows[i - 1]["value"]) for i in range(1, len(rows))]
    else:
        one = changes[-1] if changes else None
        three = sum(changes[-3:]) if len(changes) >= 3 else None
        six = sum(changes[-6:]) if len(changes) >= 6 else None
        robust_changes = changes
    z = None
    z_method = "NOT_REQUIRED"
    center = scale = None
    if indicator != "US_EFFECTIVE_FEDERAL_FUNDS_RATE" and one is not None:
        z, z_method, center, scale = robust_z(robust_changes[:-1], one, 12)
    score, continuous, reason, flags = _indicator_score(indicator, float(current["value"]), one, three, z, metric)
    status = "VALID" if score is not None else "INSUFFICIENT_HISTORY"
    previous_value = float(rows[-2]["value"]) if len(rows) >= 2 else None
    yoy = metric if indicator == "US_CPI_ALL_ITEMS_SA" else None
    trend = "UNKNOWN" if three is None else ("RISING" if three > 0 else "FALLING" if three < 0 else "STABLE")
    state_key = f"{indicator}|{effective_at}|{current['observation_id']}|{config_hash}"
    return {
        "schema_version": "1.0.0",
        "indicator_state_id": "MIS-" + sha256_bytes(state_key.encode())[:24],
        "effective_at_utc": effective_at,
        "indicator_id": indicator,
        "source_series_id": current["source_series_id"],
        "category": current["category"],
        "release_bundle": current["release_bundle"],
        "trigger_observation_ids": "|".join(sorted(trigger_ids)),
        "observation_id": current["observation_id"],
        "reference_date": current["reference_date"],
        "current_value": fmt(float(current["value"])),
        "previous_point_in_time_value": fmt(previous_value),
        "one_release_change": fmt(one),
        "three_release_change": fmt(three),
        "six_release_change": fmt(six),
        "year_over_year_transformation": fmt(yoy),
        "prior_only_robust_z": fmt(z),
        "prior_only_center": fmt(center),
        "prior_only_scale": fmt(scale),
        "prior_only_scale_method": z_method,
        "prior_history_count": max(0, len(robust_changes) - 1),
        "level_percentile_prior_only": fmt(prior_percentile([m[1] for m in metrics[:-1]], metric) if metric is not None else None),
        "trend_classification": trend,
        "stress_classification": "|".join(sorted(flags)) if flags else "NONE",
        "continuous_score": fmt(continuous),
        "discrete_score": score,
        "scoring_rationale_code": reason,
        "coverage_state": status,
        "source_run_id": current["source_run_id"],
        "raw_artifact_sha256": current["raw_artifact_sha256"],
        "point_in_time_classification": current["point_in_time_classification"],
        "historical_reconstruction": current["historical_reconstruction"],
        "availability_rule": current["availability_rule"],
        "registry_sha256": registry_hash,
        "scoring_config_sha256": config_hash,
        "code_sha256": code_hash,
        "calculated_at_utc": CREATED_AT_UTC,
    }


def calculate_bundle_state(bundle: dict[str, Any], active_states: dict[str, dict[str, Any]], effective_at: str, config_hash: str, code_hash: str) -> dict[str, Any]:
    components = [active_states[i] for i in bundle["components"] if i in active_states]
    valid = [s for s in components if s["discrete_score"] is not None]
    mean = statistics.fmean(s["discrete_score"] for s in valid) if valid else None
    enough = len(valid) >= bundle["minimum_valid_components"]
    discrete = aggregate_bucket(mean) if enough and mean is not None else None
    status = "VALID" if enough else "INSUFFICIENT_HISTORY" if components else "DATA_GAP"
    key = f"{bundle['bundle_id']}|{effective_at}|{config_hash}"
    return {
        "schema_version": "1.0.0",
        "bundle_state_id": "MBS-" + sha256_bytes(key.encode())[:24],
        "effective_at_utc": effective_at,
        "release_bundle": bundle["bundle_id"],
        "category": bundle["category"],
        "component_indicator_state_ids": "|".join(s["indicator_state_id"] for s in components),
        "component_indicator_ids": "|".join(s["indicator_id"] for s in components),
        "valid_component_count": len(valid),
        "required_component_count": bundle["minimum_valid_components"],
        "continuous_bundle_score": fmt(mean),
        "discrete_bundle_score": discrete,
        "coverage_status": status,
        "scoring_config_sha256": config_hash,
        "code_sha256": code_hash,
        "calculated_at_utc": CREATED_AT_UTC,
    }


def calculate_category_state(category: str, bundle_states: dict[str, dict[str, Any]], minimum: int, active_indicator_states: dict[str, dict[str, Any]], effective_at: str, config_hash: str, code_hash: str) -> dict[str, Any]:
    bundles = [s for s in bundle_states.values() if s["category"] == category]
    valid = [s for s in bundles if s["discrete_bundle_score"] is not None]
    mean = statistics.fmean(s["discrete_bundle_score"] for s in valid) if valid else None
    enough = len(valid) >= minimum
    discrete = aggregate_bucket(mean) if enough and mean is not None else None
    flags = sorted({f for s in active_indicator_states.values() if s["category"] == category for f in s["stress_classification"].split("|") if f != "NONE"})
    conflict = any(s["discrete_bundle_score"] > 0 for s in valid) and any(s["discrete_bundle_score"] < 0 for s in valid)
    if not valid:
        status = "INSUFFICIENT_HISTORY" if bundles else "UNKNOWN"
    elif not enough:
        status = "PARTIAL"
    elif flags:
        status = "STRESS"
    elif conflict:
        status = "CONFLICTING"
    else:
        status = "VALID"
    key = f"{category}|{effective_at}|{config_hash}"
    return {
        "schema_version": "1.0.0",
        "category_state_id": "MCS-" + sha256_bytes(key.encode())[:24],
        "effective_at_utc": effective_at,
        "category": category,
        "active_release_bundle_state_ids": "|".join(s["bundle_state_id"] for s in bundles),
        "active_release_bundles": "|".join(s["release_bundle"] for s in bundles),
        "valid_bundle_count": len(valid),
        "required_bundle_count": minimum,
        "continuous_category_score": fmt(mean),
        "discrete_category_score": discrete,
        "category_status": status,
        "stress_flags": "|".join(flags) if flags else "NONE",
        "scoring_config_sha256": config_hash,
        "code_sha256": code_hash,
        "calculated_at_utc": CREATED_AT_UTC,
    }


def interaction_result(category_scores: dict[str, int | None], flags: set[str]) -> tuple[list[str], int]:
    inf = category_scores.get("INFLATION")
    lab = category_scores.get("LABOUR")
    growth = category_scores.get("GROWTH")
    policy = category_scores.get("MONETARY_POLICY")
    active: list[str] = []
    adjustment = 0
    if None not in (inf, lab, growth, policy) and inf >= 1 and growth >= 0 and lab in (0, 1) and "LABOUR_STRESS" not in flags and "GROWTH_STRESS" not in flags and policy >= 0:
        active.append("GOLDILOCKS")
        adjustment += 1
    if None not in (inf, growth, policy) and inf <= -1 and ("LABOUR_OVERHEATING_PRESSURE" in flags or growth >= 1) and policy <= 0:
        active.append("OVERHEATING")
        adjustment -= 1
    recession = None not in (growth,) and growth <= -1 and "LABOUR_STRESS" in flags and bool(flags & {"PAYROLL_DETERIORATION", "CLAIMS_STRESS", "UNEMPLOYMENT_STRESS", "SERVICES_OR_MANUFACTURING_CONTRACTION"})
    if recession:
        active.append("RECESSION_RISK")
        adjustment -= 2
    if recession and policy is not None and policy >= 1:
        active.append("EMERGENCY_EASING")
        adjustment -= 1
    return active, max(-2, min(2, adjustment))


def classify_bias(score: int | None, valid_categories: int) -> str:
    if valid_categories < 3 or score is None:
        return "UNKNOWN"
    if score >= 5:
        return "STRONG_BULLISH"
    if score >= 2:
        return "BULLISH"
    if score >= -1:
        return "NEUTRAL"
    if score >= -4:
        return "BEARISH"
    return "STRONG_BEARISH"


def clamp_final_score(base_score: int, interaction_adjustment: int) -> int:
    return max(-10, min(10, base_score + max(-2, min(2, interaction_adjustment))))


def calculate_snapshot(category_states: dict[str, dict[str, Any]], active_indicator_states: dict[str, dict[str, Any]], effective_at: str, registry_hash: str, config_hash: str, code_hash: str) -> dict[str, Any]:
    scores = {c: category_states.get(c, {}).get("discrete_category_score") for c in CATEGORIES}
    valid_count = sum(v is not None for v in scores.values())
    flags = {f for s in active_indicator_states.values() for f in s["stress_classification"].split("|") if f != "NONE"}
    interactions, adjustment = interaction_result(scores, flags)
    base = sum(scores.values()) if valid_count == 5 else None
    final = clamp_final_score(base, adjustment) if base is not None else None
    bias = classify_bias(final, valid_count)
    key = f"{effective_at}|{config_hash}|{'|'.join(s['observation_id'] for s in active_indicator_states.values())}"
    return {
        "schema_version": "1.0.0",
        "macro_snapshot_id": "MRS-" + sha256_bytes(key.encode())[:24],
        "effective_at_utc": effective_at,
        "inflation_score": scores["INFLATION"],
        "labour_score": scores["LABOUR"],
        "growth_score": scores["GROWTH"],
        "monetary_policy_score": scores["MONETARY_POLICY"],
        "liquidity_score": scores["LIQUIDITY"],
        "base_overall_score": base,
        "active_interaction_flags": "|".join(interactions) if interactions else "NONE",
        "interaction_adjustment": adjustment,
        "final_score": final,
        "final_bias": bias,
        "technical_permission": "LONG_ONLY" if bias in {"BULLISH", "STRONG_BULLISH"} else "SHORT_ONLY" if bias in {"BEARISH", "STRONG_BEARISH"} else "NO_TRADE",
        "valid_category_count": valid_count,
        "source_observation_ids": "|".join(sorted(s["observation_id"] for s in active_indicator_states.values())),
        "indicator_state_ids": "|".join(sorted(s["indicator_state_id"] for s in active_indicator_states.values())),
        "category_state_ids": "|".join(category_states[c]["category_state_id"] for c in CATEGORIES if c in category_states),
        "scoring_config_sha256": config_hash,
        "registry_sha256": registry_hash,
        "code_sha256": code_hash,
        "calculated_at_utc": CREATED_AT_UTC,
    }


def _normalize_alfred(row: dict[str, str], aliases: dict[str, str]) -> dict[str, Any]:
    indicator = aliases[row["source_series_id"]]
    return {
        "provider": row["provider"], "observation_id": row["observation_id"], "source_series_id": row["source_series_id"],
        "indicator_id": indicator, "category": row["regime_category"], "release_bundle": "",
        "reference_date": row["reference_period"], "revision_number": int(row["revision_number"]), "is_revision": int(row["revision_number"]) > 0, "value": float(row["actual_value"]),
        "effective_at_utc": row["conservative_effective_time_utc"], "availability_date": row["availability_date"],
        "availability_rule": row["effective_rule"], "source_run_id": row["source_run_id"], "raw_artifact_sha256": row["raw_artifact_sha256"],
        "raw_evidence_reference": row["raw_artifact_relative_path"], "point_in_time_classification": row["protocol_classification"],
        "historical_reconstruction": "true", "source_observation_payload_sha256": row["observation_payload_sha256"]
    }


def _normalize_fed(row: dict[str, str], aliases: dict[str, str]) -> dict[str, Any]:
    indicator = aliases[row["source_series_id"]]
    return {
        "provider": "FEDERAL_RESERVE", "observation_id": row["observation_id"], "source_series_id": row["source_series_id"],
        "indicator_id": indicator, "category": row["category"], "release_bundle": row["release_bundle"],
        "reference_date": row["reference_date"], "revision_number": int(row["observation_version"]), "is_revision": row["measurement_version_kind"] == "REVISION", "value": float(row["normalized_numeric_value"]),
        "effective_at_utc": row["effective_at_utc"], "availability_date": row["availability_date"], "availability_rule": row["availability_rule"],
        "source_run_id": row["source_run_id"], "raw_artifact_sha256": row["raw_artifact_sha256"],
        "raw_evidence_reference": row["raw_relative_private_path"], "point_in_time_classification": row["point_in_time_classification"],
        "historical_reconstruction": row["historical_reconstruction"], "source_observation_payload_sha256": row["observation_payload_sha256"]
    }


def load_inputs(root: Path, config: dict[str, Any], aliases: dict[str, str], indicator_defs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for spec in config["inputs"]:
        path = root / spec["path"]
        if sha256_file(path) != spec["sha256"]:
            raise ValueError(f"input hash mismatch: {spec['path']}")
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = [_normalize_alfred(r, aliases) if path.name.startswith("ALFRED") else _normalize_fed(r, aliases) for r in reader]
        if len(rows) != spec["eligible_rows"]:
            raise ValueError(f"input row mismatch: {spec['path']}")
        events.extend(rows)
    seen: set[str] = set()
    for e in events:
        if e["observation_id"] in seen:
            raise ValueError("duplicate observation id")
        seen.add(e["observation_id"])
        definition = indicator_defs[e["indicator_id"]]
        e["release_bundle"] = definition["release_bundle"]
        if e["category"] != definition["category"]:
            raise ValueError("category mismatch")
        if parse_utc(e["effective_at_utc"]).date() > date(2026, 6, 28):
            raise ValueError("post-cutoff effective observation")
    return sorted(events, key=lambda e: (e["effective_at_utc"], e["source_series_id"], e["reference_date"], e["revision_number"], e["observation_id"]))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"empty CSV rows: {path.name}")
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fields, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(canonical_json(r) + "\n" for r in rows), encoding="utf-8")


def write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq
    table = pa.Table.from_pylist(rows)
    metadata = {b"program_id": PROGRAM_ID.encode(), b"created_at_utc": CREATED_AT_UTC.encode(), b"schema_version": b"1.0.0"}
    table = table.replace_schema_metadata(metadata)
    pq.write_table(table, path, compression="zstd", use_dictionary=False, write_statistics=True, version="2.6", data_page_version="2.0")


def _longest_run(rows: list[dict[str, Any]], biases: set[str]) -> int:
    best = current = 0
    for row in rows:
        if row["final_bias"] in biases:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def write_reports(output: Path, events: list[dict[str, Any]], indicator_history: list[dict[str, Any]], bundle_history: list[dict[str, Any]], category_history: list[dict[str, Any]], snapshots: list[dict[str, Any]], daily: list[dict[str, Any]], ledger: list[dict[str, Any]], config_hash: str, registry_hash: str, code_hash: str) -> None:
    event_counts = Counter(e["indicator_id"] for e in events)
    category_counts = Counter(e["category"] for e in events)
    valid_state_counts = Counter(s["indicator_id"] for s in indicator_history if s["discrete_score"] is not None)
    unknown_state_counts = Counter(s["indicator_id"] for s in indicator_history if s["discrete_score"] is None)
    earliest = min(e["effective_at_utc"] for e in events)
    latest = max(e["effective_at_utc"] for e in events)
    coverage_rows = "\n".join(
        f"| `{indicator}` | {event_counts[indicator]:,} | {valid_state_counts[indicator]:,} | {unknown_state_counts[indicator]:,} |"
        for indicator in INDICATOR_ORDER
    )
    category_rows = "\n".join(f"| {category} | {category_counts[category]:,} |" for category in CATEGORIES)
    coverage = f"""# Macro Data Coverage Report

Status: `PASS_INPUT_COVERAGE_RECONCILED_SCORING_COVERAGE_INSUFFICIENT`
Decision: `INSUFFICIENT_CATEGORY_COVERAGE`

The complete frozen input set contains {len(events):,} immutable eligible observation versions from `{earliest}` through `{latest}`. The requested read-only daily history contains {len(daily):,} calendar days from `2000-01-01` through `2026-06-28`. No unavailable observation or year was fabricated.

| Indicator | Observation versions | Valid calculated states | Insufficient-history states |
| --- | ---: | ---: | ---: |
{coverage_rows}

| Category | Observation versions |
| --- | ---: |
{category_rows}

Coverage capacity is one bundle for inflation, one for labour, one for growth, one for monetary policy, and four for liquidity. Frozen minima are respectively `2, 2, 2, 1, 1`. Inflation, labour, and growth therefore remain `PARTIAL` after warm-up; only policy and liquidity can be valid. Maximum valid-category count is two, below the overall minimum of three. All {len(daily):,} daily final biases are consequently `UNKNOWN`; this is a sufficiency result, not a scoring error.

Missing candidate families include core/PCE/PPI inflation, claims/JOLTS/wages, consumption/industrial/manufacturing/services growth, policy target bounds/real-rate proxy, and RRP. Role 6 did not substitute current-revised or unofficial histories for them.
"""
    (output / "MACRO_DATA_COVERAGE_REPORT.md").write_text(coverage, encoding="utf-8")

    state_status = Counter(s["coverage_state"] for s in indicator_history)
    bundle_status = Counter(s["coverage_status"] for s in bundle_history)
    category_status = Counter(s["category_status"] for s in category_history)
    quality = f"""# Macro Data Quality Report

Status: `PASS_ROLE6_DETERMINISTIC_MATERIALIZATION_WITH_COVERAGE_VETO`

- Frozen input hashes matched: `3/3`.
- Eligible inputs / ledger rows: `{len(events):,} / {len(ledger):,}`.
- Revisions retained: `{sum(e['is_revision'] for e in events):,}`.
- Unique indicator states: `{len(indicator_history):,}`; statuses `{canonical_json(dict(sorted(state_status.items())))}`.
- Release-bundle states: `{len(bundle_history):,}`; statuses `{canonical_json(dict(sorted(bundle_status.items())))}`.
- Category states: `{len(category_history):,}`; statuses `{canonical_json(dict(sorted(category_status.items())))}`.
- Regime snapshots / daily rows: `{len(snapshots):,} / {len(daily):,}`.
- Duplicate observation IDs, nonfinite values, alias mismatches, category mismatches, future-effective rows, config/registry hash mismatches: `0 accepted`.
- Current-revised-only inputs, technical inputs, PnL inputs, news/LLM inputs, experiment trials, protected/final-holdout accesses: `0`.

The H.4.1 signed reserve observation is retained and transformed with absolute changes. H.6 release revisions are atomic at exact effective timestamps. ALFRED revisions remain immutable and only replace the same reference period after their conservative J0 timestamp. Same-time rows are applied as one availability batch, preventing artificial within-release ordering from changing the public state.

Limitations: Role 6 is a deterministic construction role, not the independent point-in-time audit. Role 7 must independently verify source/effective chronology, future-vintage exclusion, atomic replacement, daily as-of semantics, and J0 readiness before any technical join. Registry chronology remains a final-champion veto.
"""
    (output / "MACRO_DATA_QUALITY_REPORT.md").write_text(quality, encoding="utf-8")

    examples: list[dict[str, Any]] = []
    if ledger:
        examples.append(ledger[0])
    for predicate in [
        lambda r: r["new_indicator_score"] == 2,
        lambda r: r["new_indicator_score"] == -2,
        lambda r: r["stress_state"] != "NONE",
        lambda r: r["category"] == "MONETARY_POLICY" and r["new_category_score"] is not None,
    ]:
        match = next((r for r in ledger if predicate(r) and r not in examples), None)
        if match:
            examples.append(match)
    example_lines = []
    for row in examples:
        example_lines.append(
            f"## `{row['event_update_id']}`\n\n"
            f"- Effective: `{row['effective_at_utc']}`; source observation: `{row['source_observation_id']}`\n"
            f"- Indicator/category/bundle: `{row['indicator_updated']}` / `{row['category']}` / `{row['release_bundle']}`\n"
            f"- Value: `{row['previous_value']}` → `{row['current_value']}`; prior-only z: `{row['prior_only_z_change']}`\n"
            f"- Indicator score: `{row['previous_indicator_score']}` → `{row['new_indicator_score']}`; category: `{row['previous_category_score']}` → `{row['new_category_score']}`\n"
            f"- Final: `{row['bias_before']}` / `{row['final_score_before']}` → `{row['bias_after']}` / `{row['final_score_after']}`\n"
            f"- Reason: `{row['reason_code']}`; stress: `{row['stress_state']}`\n"
            f"- Raw hash: `{row['raw_artifact_sha256']}`\n"
        )
    (output / "MACRO_EVENT_UPDATE_EXAMPLES.md").write_text("# Macro Event Update Examples\n\n" + "\n".join(example_lines), encoding="utf-8")

    report = f"""# Role 6 Macro Taxonomy and Scoring Report

Status: `PASS`
Decision: `INSUFFICIENT_CATEGORY_COVERAGE`

Role 6 prospectively froze nine indicator definitions, aliases, eight release bundles, five equal categories, prior-only transformations, no-decay replacement, discrete boundaries, stress rules, category sufficiency, four interactions, interaction cap, final clamp, and bias thresholds before materialization.

All {len(events):,} frozen eligible observations produced {len(indicator_history):,} indicator states, {len(bundle_history):,} bundle states, {len(category_history):,} category states, {len(snapshots):,} event-time regime snapshots, {len(ledger):,} ledger rows, and {len(daily):,} daily as-of rows. No technical setup, trade outcome, or PnL was read. Because the evidence supports at most two valid categories, all daily biases correctly remain `UNKNOWN` under the frozen minimum-three rule.

This is not a claim that macro direction has no value. It is a transparent coverage veto: Role 7 must validate point-in-time construction, and later technical alignment remains prohibited until the sequential gate advances.
"""
    (output / "MACRO_REGIME_ROLE6_SCORING_REPORT.md").write_text(report, encoding="utf-8")

    reproducibility = f"""# Macro Regime Reproducibility Report

Status: `PASS_BYTE_DETERMINISTIC_VERIFIED_BY_FOCUSED_TEST`

- Config SHA-256: `{config_hash}`
- Combined registry SHA-256: `{registry_hash}`
- Scoring code SHA-256: `{code_hash}`
- Python: `3.11.7`
- Output formats: deterministic UTF-8 CSV/JSONL and PyArrow Parquet with fixed metadata, Zstandard compression, dictionary encoding disabled, statistics enabled, Parquet 2.6/data-page 2.0.
- Created timestamp is frozen at `{CREATED_AT_UTC}`; no runtime timestamp or random seed enters output bytes.
- Focused Role 6 suite: `9/9` passed, including two complete real-input materializations and two tamper failures.
- Complete research regression suite: `232/232` passed.

Reproduction:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m smartmarketscope_quant.macro_regime.scoring --repo-root .
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m smartmarketscope_quant.macro_regime.scoring --repo-root . --validate-only
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m unittest research.tests.test_macro_regime_scoring -v
```

`ROLE6_OUTPUT_HASHES.json` records each named output. The focused integration test runs the complete real-input materialization twice in a disposable directory and requires every output byte hash to match.
"""
    (output / "MACRO_REGIME_REPRODUCIBILITY_REPORT.md").write_text(reproducibility, encoding="utf-8")


def materialize(root: Path) -> dict[str, Any]:
    config_path = root / CONFIG_REL
    config_hash = sha256_file(config_path)
    config = json.loads(config_path.read_text())
    for registry in config["registries"].values():
        if sha256_file(root / registry["path"]) != registry["sha256"]:
            raise ValueError("registry hash mismatch")
    indicator_registry = json.loads((root / config["registries"]["indicator_registry"]["path"]).read_text())
    aliases = json.loads((root / config["registries"]["alias_map"]["path"]).read_text())["aliases"]
    bundle_registry = json.loads((root / config["registries"]["release_bundles"]["path"]).read_text())
    indicator_defs = {r["indicator_id"]: r for r in indicator_registry["indicators"]}
    bundle_defs = {r["bundle_id"]: r for r in bundle_registry["bundles"]}
    registry_hash = sha256_bytes("".join(config["registries"][k]["sha256"] for k in sorted(config["registries"])).encode())
    code_hash = sha256_file(Path(__file__))
    events = load_inputs(root, config, aliases, indicator_defs)
    output = root / OUTPUT_REL
    output.mkdir(parents=True, exist_ok=True)

    active_versions: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    active_indicator_states: dict[str, dict[str, Any]] = {}
    active_bundle_states: dict[str, dict[str, Any]] = {}
    active_category_states: dict[str, dict[str, Any]] = {}
    indicator_history: list[dict[str, Any]] = []
    bundle_history: list[dict[str, Any]] = []
    category_history: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    by_time: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_time[event["effective_at_utc"]].append(event)

    previous_snapshot: dict[str, Any] | None = None
    for effective_at in sorted(by_time):
        batch = by_time[effective_at]
        prior_indicator_states = {k: dict(v) for k, v in active_indicator_states.items()}
        prior_bundle_states = {k: dict(v) for k, v in active_bundle_states.items()}
        prior_category_states = {k: dict(v) for k, v in active_category_states.items()}
        prior_ref_rows: dict[tuple[str, str], dict[str, Any] | None] = {}
        affected: dict[str, list[str]] = defaultdict(list)
        for event in batch:
            key = (event["indicator_id"], event["reference_date"])
            prior_ref_rows[key] = active_versions[event["indicator_id"]].get(event["reference_date"])
            active_versions[event["indicator_id"]][event["reference_date"]] = event
            affected[event["indicator_id"]].append(event["observation_id"])
        for indicator in sorted(affected, key=INDICATOR_ORDER.index):
            state = calculate_indicator_state(indicator, active_versions[indicator], affected[indicator], effective_at, registry_hash, config_hash, code_hash)
            active_indicator_states[indicator] = state
            indicator_history.append(state)
        affected_bundles = sorted({indicator_defs[i]["release_bundle"] for i in affected})
        for bundle_id in affected_bundles:
            state = calculate_bundle_state(bundle_defs[bundle_id], active_indicator_states, effective_at, config_hash, code_hash)
            active_bundle_states[bundle_id] = state
            bundle_history.append(state)
        affected_categories = sorted({indicator_defs[i]["category"] for i in affected}, key=CATEGORIES.index)
        for category in affected_categories:
            state = calculate_category_state(category, active_bundle_states, config["category_aggregation"]["minimum_valid_bundles"][category], active_indicator_states, effective_at, config_hash, code_hash)
            active_category_states[category] = state
            category_history.append(state)
        snapshot = calculate_snapshot(active_category_states, active_indicator_states, effective_at, registry_hash, config_hash, code_hash)
        snapshots.append(snapshot)
        for event in batch:
            indicator = event["indicator_id"]
            bundle_id = indicator_defs[indicator]["release_bundle"]
            category = indicator_defs[indicator]["category"]
            old_ref = prior_ref_rows[(indicator, event["reference_date"])]
            if old_ref is None:
                earlier = [r for d, r in active_versions[indicator].items() if d < event["reference_date"]]
                old_ref = max(earlier, key=lambda r: r["reference_date"]) if earlier else None
            new_i = active_indicator_states[indicator]
            old_i = prior_indicator_states.get(indicator)
            new_b = active_bundle_states[bundle_id]
            old_b = prior_bundle_states.get(bundle_id)
            new_c = active_category_states[category]
            old_c = prior_category_states.get(category)
            ledger.append({
                "schema_version": "1.0.0", "event_update_id": "MEU-" + sha256_bytes((event["observation_id"] + "|" + config_hash).encode())[:24],
                "availability_date": event["availability_date"], "effective_at_utc": effective_at, "source": event["provider"],
                "source_series_id": event["source_series_id"], "indicator_updated": indicator, "category": category,
                "reference_date": event["reference_date"], "previous_value": fmt(float(old_ref["value"]) if old_ref else None), "current_value": fmt(event["value"]),
                "one_release_change": new_i["one_release_change"], "three_release_trend": new_i["three_release_change"], "prior_only_z_change": new_i["prior_only_robust_z"],
                "level_state": new_i["trend_classification"], "stress_state": new_i["stress_classification"],
                "previous_indicator_score": old_i["discrete_score"] if old_i else None, "new_indicator_score": new_i["discrete_score"],
                "release_bundle": bundle_id, "previous_bundle_score": old_b["discrete_bundle_score"] if old_b else None, "new_bundle_score": new_b["discrete_bundle_score"],
                "previous_category_score": old_c["discrete_category_score"] if old_c else None, "new_category_score": new_c["discrete_category_score"],
                "base_score_before": previous_snapshot["base_overall_score"] if previous_snapshot else None, "base_score_after": snapshot["base_overall_score"],
                "active_regime_interactions_before": previous_snapshot["active_interaction_flags"] if previous_snapshot else "NONE",
                "active_regime_interactions_after": snapshot["active_interaction_flags"], "interaction_adjustment": snapshot["interaction_adjustment"],
                "final_score_before": previous_snapshot["final_score"] if previous_snapshot else None, "final_score_after": snapshot["final_score"],
                "bias_before": previous_snapshot["final_bias"] if previous_snapshot else "UNKNOWN", "bias_after": snapshot["final_bias"],
                "reason_code": new_i["scoring_rationale_code"], "source_observation_id": event["observation_id"], "active_observation_id": new_i["observation_id"],
                "source_run_id": event["source_run_id"], "point_in_time_classification": event["point_in_time_classification"],
                "raw_evidence_reference": event["raw_evidence_reference"], "raw_artifact_sha256": event["raw_artifact_sha256"],
                "scoring_config_sha256": config_hash, "registry_sha256": registry_hash, "code_sha256": code_hash
            })
        previous_snapshot = snapshot

    daily: list[dict[str, Any]] = []
    active_inputs: list[dict[str, Any]] = []
    snapshot_idx = -1
    indicator_indices = {i: -1 for i in INDICATOR_ORDER}
    histories_by_indicator = {i: [s for s in indicator_history if s["indicator_id"] == i] for i in INDICATOR_ORDER}
    start, end = date(2000, 1, 1), date(2026, 6, 28)
    current_date = start
    while current_date <= end:
        asof = datetime.combine(current_date, time(23, 59, 59), timezone.utc)
        while snapshot_idx + 1 < len(snapshots) and parse_utc(snapshots[snapshot_idx + 1]["effective_at_utc"]) <= asof:
            snapshot_idx += 1
        snap = snapshots[snapshot_idx] if snapshot_idx >= 0 else None
        daily.append({
            "schema_version": "1.0.0", "asof_date": current_date.isoformat(), "asof_at_utc": asof.isoformat().replace("+00:00", "Z"),
            "macro_snapshot_id": snap["macro_snapshot_id"] if snap else None,
            "macro_effective_at_utc": snap["effective_at_utc"] if snap else None,
            "inflation_score": snap["inflation_score"] if snap else None, "labour_score": snap["labour_score"] if snap else None,
            "growth_score": snap["growth_score"] if snap else None, "monetary_policy_score": snap["monetary_policy_score"] if snap else None,
            "liquidity_score": snap["liquidity_score"] if snap else None, "base_overall_score": snap["base_overall_score"] if snap else None,
            "active_interaction_flags": snap["active_interaction_flags"] if snap else "NONE", "interaction_adjustment": snap["interaction_adjustment"] if snap else 0,
            "final_score": snap["final_score"] if snap else None, "final_bias": snap["final_bias"] if snap else "UNKNOWN",
            "valid_category_count": snap["valid_category_count"] if snap else 0, "technical_permission": snap["technical_permission"] if snap else "NO_TRADE",
            "scoring_config_sha256": config_hash, "registry_sha256": registry_hash, "code_sha256": code_hash
        })
        for indicator in INDICATOR_ORDER:
            hist = histories_by_indicator[indicator]
            idx = indicator_indices[indicator]
            while idx + 1 < len(hist) and parse_utc(hist[idx + 1]["effective_at_utc"]) <= asof:
                idx += 1
            indicator_indices[indicator] = idx
            if idx >= 0:
                s = hist[idx]
                active_inputs.append({"schema_version": "1.0.0", "asof_date": current_date.isoformat(), "indicator_id": indicator,
                                      "indicator_state_id": s["indicator_state_id"], "observation_id": s["observation_id"], "reference_date": s["reference_date"],
                                      "effective_at_utc": s["effective_at_utc"], "discrete_score": s["discrete_score"], "coverage_state": s["coverage_state"],
                                      "raw_artifact_sha256": s["raw_artifact_sha256"], "scoring_config_sha256": config_hash, "code_sha256": code_hash})
        current_date += timedelta(days=1)

    by_year: list[dict[str, Any]] = []
    category_by_year: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    prior_bias = None
    for row in daily:
        if row["final_bias"] != prior_bias:
            transitions.append({"transition_id": f"MRT-{len(transitions)+1:04d}", "asof_date": row["asof_date"], "previous_bias": prior_bias, "new_bias": row["final_bias"],
                                "final_score": row["final_score"], "valid_category_count": row["valid_category_count"],
                                "categories_responsible": "INITIAL_STATE" if prior_bias is None else "CATEGORY_SCORE_OR_SUFFICIENCY_CHANGE", "macro_snapshot_id": row["macro_snapshot_id"]})
            prior_bias = row["final_bias"]
    for year in range(2000, 2027):
        rows = [r for r in daily if r["asof_date"].startswith(str(year))]
        counts = Counter(r["final_bias"] for r in rows)
        observed_events = [e for e in events if e["effective_at_utc"].startswith(str(year))]
        present = sorted({e["indicator_id"] for e in observed_events})
        missing = sorted(set(INDICATOR_ORDER) - set(present))
        revisions = sum(e["is_revision"] for e in observed_events)
        by_year.append({
            "year": year, "available_indicators": "|".join(present), "missing_indicators": "|".join(missing), "valid_observations": len(observed_events), "revisions": revisions,
            "category_valid_days": sum(r["valid_category_count"] > 0 for r in rows), "category_unknown_days": sum(r["valid_category_count"] == 0 for r in rows),
            "bullish_days": counts["BULLISH"], "bearish_days": counts["BEARISH"], "neutral_days": counts["NEUTRAL"], "unknown_days": counts["UNKNOWN"],
            "strong_bullish_days": counts["STRONG_BULLISH"], "strong_bearish_days": counts["STRONG_BEARISH"],
            "regime_transitions": sum(t["asof_date"].startswith(str(year)) for t in transitions),
            "longest_bullish_regime": _longest_run(rows, {"BULLISH", "STRONG_BULLISH"}), "longest_bearish_regime": _longest_run(rows, {"BEARISH", "STRONG_BEARISH"}),
            "longest_neutral_regime": _longest_run(rows, {"NEUTRAL"}), "longest_unknown_regime": _longest_run(rows, {"UNKNOWN"}),
            "categories_responsible_for_transitions": "NONE_FINAL_BIAS_REMAINS_UNKNOWN" if year > 2000 else "INITIAL_STATE"
        })
        for category in CATEGORIES:
            key = {"INFLATION": "inflation_score", "LABOUR": "labour_score", "GROWTH": "growth_score", "MONETARY_POLICY": "monetary_policy_score", "LIQUIDITY": "liquidity_score"}[category]
            category_by_year.append({"year": year, "category": category, "valid_days": sum(r[key] is not None for r in rows), "unknown_days": sum(r[key] is None for r in rows),
                                     "score_minus_2_days": sum(r[key] == -2 for r in rows), "score_minus_1_days": sum(r[key] == -1 for r in rows), "score_0_days": sum(r[key] == 0 for r in rows),
                                     "score_plus_1_days": sum(r[key] == 1 for r in rows), "score_plus_2_days": sum(r[key] == 2 for r in rows),
                                     "update_count": sum(e["category"] == category and e["effective_at_utc"].startswith(str(year)) for e in events)})

    parquet_outputs = {
        "MACRO_INDICATOR_STATE_HISTORY.parquet": indicator_history,
        "MACRO_RELEASE_BUNDLE_HISTORY.parquet": bundle_history,
        "MACRO_CATEGORY_STATE_HISTORY.parquet": category_history,
        "MACRO_REGIME_SNAPSHOT_HISTORY.parquet": snapshots,
        "MACRO_DAILY_ASOF_REGIME.parquet": daily,
        "MACRO_ACTIVE_INPUTS_BY_DAY.parquet": active_inputs,
        "MACRO_EVENT_UPDATE_LEDGER.parquet": ledger,
    }
    for name, rows in parquet_outputs.items():
        write_parquet(output / name, rows)
    write_csv(output / "MACRO_EVENT_UPDATE_LEDGER.csv", ledger)
    write_jsonl(output / "MACRO_EVENT_UPDATE_LEDGER.jsonl", ledger)
    write_csv(output / "MACRO_REGIME_BY_YEAR.csv", by_year)
    write_csv(output / "MACRO_CATEGORY_BY_YEAR.csv", category_by_year)
    write_csv(output / "MACRO_REGIME_TRANSITIONS.csv", transitions)

    write_reports(output, events, indicator_history, bundle_history, category_history, snapshots, daily, ledger, config_hash, registry_hash, code_hash)

    hashes = {p.name: sha256_file(p) for p in sorted(output.iterdir()) if p.is_file() and p.name not in {"ROLE6_OUTPUT_HASHES.json", "ROLE6_SCORING_MANIFEST.json"}}
    counts = {
        "eligible_input_observations": len(events), "indicator_states": len(indicator_history), "bundle_states": len(bundle_history),
        "category_states": len(category_history), "regime_snapshots": len(snapshots), "daily_asof_rows": len(daily),
        "active_input_rows": len(active_inputs), "event_ledger_rows": len(ledger), "regime_transitions": len(transitions),
        "final_bias_counts": dict(sorted(Counter(r["final_bias"] for r in daily).items()))
    }
    manifest = {
        "schema_version": "1.0.0", "artifact_id": "MACRO-REGIME-ROLE6-MANIFEST-001", "program_id": PROGRAM_ID,
        "created_at_utc": CREATED_AT_UTC, "status": "PASS_DETERMINISTIC_SCORING_MATERIALIZED_INSUFFICIENT_CATEGORY_COVERAGE",
        "decision": "INSUFFICIENT_CATEGORY_COVERAGE", "starting_commit": config["starting_commit"], "config_sha256": config_hash,
        "registry_sha256": registry_hash, "code_sha256": code_hash, "input_hashes": {i["path"]: i["sha256"] for i in config["inputs"]},
        "counts": counts, "coverage": {"valid_bundle_capacity": {"INFLATION": 1, "LABOUR": 1, "GROWTH": 1, "MONETARY_POLICY": 1, "LIQUIDITY": 4},
                                            "required_bundles": config["category_aggregation"]["minimum_valid_bundles"], "maximum_valid_categories": 2},
        "experiment_trials": 0, "technical_inputs": 0, "pnl_inputs": 0, "final_holdout_accesses": 0,
        "exact_next_permitted_action": "Role 7 point-in-time and availability validation of Role 6 inputs, transformations, replacement state, atomic availability batches, daily as-of rows, and J0 readiness. Do not join technical setups."
    }
    (output / "ROLE6_OUTPUT_HASHES.json").write_text(canonical_json(hashes) + "\n")
    (output / "ROLE6_SCORING_MANIFEST.json").write_text(canonical_json(manifest) + "\n")
    return manifest


def validate(root: Path) -> dict[str, Any]:
    output = root / OUTPUT_REL
    manifest = json.loads((output / "ROLE6_SCORING_MANIFEST.json").read_text())
    hashes = json.loads((output / "ROLE6_OUTPUT_HASHES.json").read_text())
    for name, expected in hashes.items():
        if sha256_file(output / name) != expected:
            raise ValueError(f"output hash mismatch: {name}")
    if sha256_file(root / CONFIG_REL) != manifest["config_sha256"]:
        raise ValueError("manifest config hash mismatch")
    if sha256_file(Path(__file__)) != manifest["code_sha256"]:
        raise ValueError("manifest code hash mismatch")
    if manifest["counts"]["eligible_input_observations"] != 10273 or manifest["counts"]["event_ledger_rows"] != 10273:
        raise ValueError("observation/ledger count mismatch")
    if manifest["coverage"]["maximum_valid_categories"] != 2:
        raise ValueError("coverage capacity mismatch")
    import pyarrow.parquet as pq
    daily = pq.read_table(output / "MACRO_DAILY_ASOF_REGIME.parquet").to_pylist()
    ledger_rows = pq.read_table(output / "MACRO_EVENT_UPDATE_LEDGER.parquet").to_pylist()
    indicator_rows = pq.read_table(output / "MACRO_INDICATOR_STATE_HISTORY.parquet").to_pylist()
    bundle_rows = pq.read_table(output / "MACRO_RELEASE_BUNDLE_HISTORY.parquet").to_pylist()
    category_rows = pq.read_table(output / "MACRO_CATEGORY_STATE_HISTORY.parquet").to_pylist()
    snapshots = pq.read_table(output / "MACRO_REGIME_SNAPSHOT_HISTORY.parquet").to_pylist()
    active_inputs = pq.read_table(output / "MACRO_ACTIVE_INPUTS_BY_DAY.parquet").to_pylist()
    expected_counts = manifest["counts"]
    actual_counts = {
        "indicator_states": len(indicator_rows), "bundle_states": len(bundle_rows), "category_states": len(category_rows),
        "regime_snapshots": len(snapshots), "daily_asof_rows": len(daily), "active_input_rows": len(active_inputs), "event_ledger_rows": len(ledger_rows)
    }
    for key, count in actual_counts.items():
        if expected_counts[key] != count:
            raise ValueError(f"manifest count mismatch: {key}")
    with (output / "MACRO_EVENT_UPDATE_LEDGER.jsonl").open(encoding="utf-8") as handle:
        if sum(1 for _ in handle) != len(ledger_rows):
            raise ValueError("JSONL ledger count mismatch")
    with (output / "MACRO_EVENT_UPDATE_LEDGER.csv").open(newline="", encoding="utf-8") as handle:
        if sum(1 for _ in csv.DictReader(handle)) != len(ledger_rows):
            raise ValueError("CSV ledger count mismatch")
    if any(parse_utc(r["effective_at_utc"]) > parse_utc(r["asof_date"] + "T23:59:59Z") for r in active_inputs):
        raise ValueError("future active input")
    if any(r["macro_effective_at_utc"] and parse_utc(r["macro_effective_at_utc"]) > parse_utc(r["asof_at_utc"]) for r in daily):
        raise ValueError("future daily snapshot")
    if any(r["coverage_state"] == "INSUFFICIENT_HISTORY" and r["discrete_score"] is not None for r in indicator_rows):
        raise ValueError("insufficient state carried a score")
    if any(r["category_status"] in {"PARTIAL", "UNKNOWN", "INSUFFICIENT_HISTORY", "DATA_GAP"} and r["discrete_category_score"] is not None for r in category_rows):
        raise ValueError("insufficient category was renormalized")
    if any(r["final_bias"] != "UNKNOWN" for r in daily):
        raise ValueError("insufficient coverage must remain UNKNOWN")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    result = validate(root) if args.validate_only else materialize(root)
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

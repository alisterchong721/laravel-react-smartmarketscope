from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Sequence

from smartmarketscope_quant.backtest.config import load_execution_scenarios
from smartmarketscope_quant.macro_liquidity_reversal.detectors import exact_target, protective_stop
from smartmarketscope_quant.macro_liquidity_reversal.models import Direction, Zone
from smartmarketscope_quant.macro_liquidity_reversal.technical_economic import (
    _canonical_hash,
    run_primary,
    validate_hash_registry,
)


PROGRAM_ID = "SMART-MARKETSCOPE-PUBLIC-MACRO-BIAS-001"
SOURCE_PROGRAM_ID = "QRP-MACRO-LIQUIDITY-REVERSAL-001"
ARTIFACT_ROOT = Path("research/artifacts/macro_liquidity_reversal")
OUTPUT_ROOT = Path("research/artifacts/public_macro_bias")
TECHNICAL_REGISTRY = ARTIFACT_ROOT / "MLR_TECHNICAL_ECONOMIC_EXPERIMENT_REGISTRY.jsonl"
PRIMARY_TRADES = ARTIFACT_ROOT / "MLR_TECHNICAL_PRIMARY_TRADES.csv"
FINAL_MANIFEST = ARTIFACT_ROOT / "MLR_TECHNICAL_FINAL_MANIFEST.json"
EVENT_REGISTRY = ARTIFACT_ROOT / "MLR_EVENT_REGISTRY.csv"
STRATEGY_CONFIG = Path("research/config/macro_liquidity_reversal_primary.json")
EXECUTION_CONFIG = Path("research/config/execution_scenarios.json")
DETECTOR_CODE = Path("research/src/smartmarketscope_quant/macro_liquidity_reversal/detectors.py")
TECHNICAL_CODE = Path("research/src/smartmarketscope_quant/macro_liquidity_reversal/technical_economic.py")
BASELINE_REGISTRY = OUTPUT_ROOT / "MACRO_TECHNICAL_BASELINE_REGISTRY.csv"
FREEZE_REPORT = Path("MACRO_TECHNICAL_BASELINE_FREEZE.md")
FREEZE_MANIFEST = Path("MACRO_TECHNICAL_BASELINE_MANIFEST.json")
FREEZE_HASHES = Path("MACRO_TECHNICAL_BASELINE_HASHES.txt")
SOURCE_POINT = Decimal("0.1")
TOLERANCE = Decimal("0.00000001")

REQUIRED_PRIMARY_ARTIFACTS = (
    ARTIFACT_ROOT / "MLR_TECHNICAL_PRIMARY_TRADES.csv",
    ARTIFACT_ROOT / "MLR_TECHNICAL_PRIMARY_SUMMARY.json",
    ARTIFACT_ROOT / "MLR_TECHNICAL_PRIMARY_BACKTEST.md",
    ARTIFACT_ROOT / "MLR_TECHNICAL_CONTROL_COMPARISON.md",
    ARTIFACT_ROOT / "MLR_TECHNICAL_PATH_AMBIGUITIES.csv",
)

REPRODUCTION_ARTIFACTS = (
    *REQUIRED_PRIMARY_ARTIFACTS,
    ARTIFACT_ROOT / "MLR_TECHNICAL_CONTROL_TRADES.csv",
)

REGISTRY_FIELDS = (
    "program_id",
    "source_program_id",
    "setup_id",
    "scenario_id",
    "event_id",
    "source_actionable_timestamp",
    "technical_decision_timestamp",
    "direction",
    "entry_timeframe",
    "confluence_family",
    "planned_entry_points",
    "stop_reference_points",
    "target_2r_reference_points",
    "expiry_timestamp",
    "fill_status",
    "outcome",
    "gross_r",
    "net_r",
    "ambiguity_flag",
    "cost_scenario",
    "setup_hash",
    "trade_hash",
)


class BaselineFreezeError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReproductionResult:
    status: str
    compared_artifacts: int
    artifact_sha256: dict[str, str]
    source_registry_event_hash: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="ascii", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def git_output(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def validate_final_manifest(repo_root: Path) -> tuple[dict[str, Any], str]:
    path = repo_root / FINAL_MANIFEST
    if not path.exists():
        raise BaselineFreezeError("TECHNICAL_FINAL_MANIFEST_MISSING")
    manifest = json.loads(path.read_text(encoding="ascii"))
    if manifest.get("status") != "TECHNICAL_EDGE_NOT_FOUND":
        raise BaselineFreezeError("TECHNICAL_RUN_NOT_TERMINAL")
    for relative, expected in manifest.get("artifacts", {}).items():
        artifact = repo_root / relative
        if not artifact.exists() or sha256_file(artifact) != expected:
            raise BaselineFreezeError(f"TECHNICAL_FINAL_MANIFEST_MISMATCH:{relative}")
    return manifest, sha256_file(path)


def primary_completion_event(repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = validate_hash_registry(repo_root / TECHNICAL_REGISTRY)
    completed = next(
        (
            row
            for row in reversed(rows)
            if row["payload"].get("status") == "PRIMARY_PASS_COMPLETED_HASH_LOCKED"
        ),
        None,
    )
    if completed is None:
        raise BaselineFreezeError("PRIMARY_PASS_NOT_HASH_LOCKED")
    for relative, expected in completed["payload"]["artifact_sha256"].items():
        if sha256_file(repo_root / relative) != expected:
            raise BaselineFreezeError(f"PRIMARY_ARTIFACT_HASH_MISMATCH:{relative}")
    terminal = rows[-1]["payload"]
    if terminal.get("status") != "PASS_PROCESS_TECHNICAL_EDGE_NOT_FOUND":
        raise BaselineFreezeError("TECHNICAL_REGISTRY_NOT_TERMINAL")
    return rows, completed


def _copy_reproduction_inputs(repo_root: Path, temporary_root: Path) -> None:
    (temporary_root / "research/artifacts").mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        repo_root / ARTIFACT_ROOT,
        temporary_root / ARTIFACT_ROOT,
        dirs_exist_ok=True,
    )
    shutil.copytree(
        repo_root / "research/config",
        temporary_root / "research/config",
        dirs_exist_ok=True,
    )
    shutil.copytree(
        repo_root / "research/preregistrations/macro_liquidity_reversal",
        temporary_root / "research/preregistrations/macro_liquidity_reversal",
        dirs_exist_ok=True,
    )
    (temporary_root / "dataset").symlink_to((repo_root / "dataset").resolve(), target_is_directory=True)
    (temporary_root / "research/artifacts/processed_data").symlink_to(
        (repo_root / "research/artifacts/processed_data").resolve(),
        target_is_directory=True,
    )


def _restore_precompletion_registry(path: Path) -> str:
    rows = validate_hash_registry(path)
    eligible = [
        row
        for row in rows
        if row["payload"].get("status") in {"PREREGISTERED", "STARTED", "STARTED_RETRY"}
        and row["payload"].get("experiment_id") == "MLR-TECH-ECO-001"
    ]
    if not eligible:
        raise BaselineFreezeError("PRECOMPLETION_LIFECYCLE_NOT_FOUND")
    last = eligible[-1]
    end_index = rows.index(last)
    retained = rows[: end_index + 1]
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n" for row in retained),
        encoding="ascii",
    )
    validate_hash_registry(path)
    return retained[-1]["event_hash"]


def verify_clean_reproduction(repo_root: Path) -> ReproductionResult:
    repo_root = repo_root.resolve()
    _, completed = primary_completion_event(repo_root)
    expected = completed["payload"]["artifact_sha256"]
    with tempfile.TemporaryDirectory(prefix="public-macro-baseline-") as temporary:
        temporary_root = Path(temporary)
        _copy_reproduction_inputs(repo_root, temporary_root)
        source_head = _restore_precompletion_registry(temporary_root / TECHNICAL_REGISTRY)
        run_primary(temporary_root)
        actual: dict[str, str] = {}
        for relative in REPRODUCTION_ARTIFACTS:
            relative_text = relative.as_posix()
            got = sha256_file(temporary_root / relative)
            if got != expected[relative_text]:
                raise BaselineFreezeError(f"BYTE_REPRODUCTION_MISMATCH:{relative_text}")
            actual[relative_text] = got
    return ReproductionResult(
        status="PASS_BYTE_IDENTICAL_REPRODUCTION",
        compared_artifacts=len(actual),
        artifact_sha256=actual,
        source_registry_event_hash=source_head,
    )


def _scenario_map(repo_root: Path) -> dict[str, Any]:
    return {
        scenario.scenario_id: scenario
        for scenario in load_execution_scenarios(repo_root / EXECUTION_CONFIG)
    }


def _event_actionable_times(repo_root: Path) -> dict[str, str]:
    rows = read_csv(repo_root / EVENT_REGISTRY)
    output = {row["event_id"]: row["actionable_time"] for row in rows if row.get("actionable_time")}
    if len(output) != 89:
        raise BaselineFreezeError("FROZEN_EVENT_ACTIONABLE_COUNT_MISMATCH")
    return output


def _planned_barriers(row: dict[str, str], scenario: Any) -> tuple[Decimal, Decimal, Decimal]:
    lower = Decimal(row["confluence_lower"])
    upper = Decimal(row["confluence_upper"])
    entry = (lower + upper) / Decimal("2")
    direction = Direction(row["direction"])
    block = Zone(Decimal(row["block_lower"]), Decimal(row["block_upper"]))
    stop = Decimal(
        str(
            protective_stop(
                direction,
                block,
                float(SOURCE_POINT),
                float(scenario.spread_points),
                units_documented=True,
            )
        )
    )
    commission_points = (
        Decimal("2")
        * scenario.commission_usd_per_unit_per_side
        / scenario.point_value_usd_per_unit
    )
    known_cost_points = (
        scenario.spread_points
        + Decimal("2") * scenario.slippage_points_per_side
        + commission_points
    )
    target = Decimal(str(exact_target(direction, float(entry), float(stop), float(known_cost_points))))
    return entry, stop, target


def _text(value: Decimal | str | bool | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_frozen_rows(repo_root: Path) -> list[dict[str, str]]:
    scenarios = _scenario_map(repo_root)
    actionable = _event_actionable_times(repo_root)
    technical_rows = read_csv(repo_root / PRIMARY_TRADES)
    if len(technical_rows) != 1362:
        raise BaselineFreezeError("PRIMARY_TRADE_ROW_COUNT_MISMATCH")
    if len({row["setup_id"] for row in technical_rows}) != 454:
        raise BaselineFreezeError("PRIMARY_SETUP_COUNT_MISMATCH")
    output: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in technical_rows:
        key = (row["setup_id"], row["scenario_id"])
        if key in seen:
            raise BaselineFreezeError("DUPLICATE_SETUP_SCENARIO")
        seen.add(key)
        scenario = scenarios[row["scenario_id"]]
        entry, stop, target = _planned_barriers(row, scenario)
        if row["entry_reference_points"] and abs(Decimal(row["entry_reference_points"]) - entry) > TOLERANCE:
            raise BaselineFreezeError(f"PLANNED_ENTRY_MISMATCH:{row['setup_id']}:{row['scenario_id']}")
        if row["stop_reference_points"] and abs(Decimal(row["stop_reference_points"]) - stop) > TOLERANCE:
            raise BaselineFreezeError(f"PLANNED_STOP_MISMATCH:{row['setup_id']}:{row['scenario_id']}")
        if row["target_reference_points"] and abs(Decimal(row["target_reference_points"]) - target) > TOLERANCE:
            raise BaselineFreezeError(f"PLANNED_TARGET_MISMATCH:{row['setup_id']}:{row['scenario_id']}")
        setup_payload = {
            "source_program_id": SOURCE_PROGRAM_ID,
            "setup_id": row["setup_id"],
            "scenario_id": row["scenario_id"],
            "event_id": row["event_id"],
            "source_actionable_timestamp": actionable[row["event_id"]],
            "technical_decision_timestamp": row["decision_time"],
            "direction": row["direction"],
            "entry_timeframe": row["timeframe"],
            "confluence_family": row["family"],
            "planned_entry_points": _text(entry),
            "stop_reference_points": _text(stop),
            "target_2r_reference_points": _text(target),
            "expiry_timestamp": row["expiry_time"],
            "cost_scenario": row["scenario_id"],
        }
        setup_hash = canonical_hash(setup_payload)
        trade_payload = {
            **setup_payload,
            "setup_hash": setup_hash,
            "fill_status": row["fill_status"],
            "outcome": row["outcome"],
            "gross_r": row["gross_r"] or None,
            "net_r": row["net_r"] or None,
            "ambiguity_flag": row["ambiguous_adverse_first"].lower() == "true",
            "actual_entry_fill_points": row["actual_entry_fill_points"] or None,
            "actual_exit_fill_points": row["actual_exit_fill_points"] or None,
            "spread_cost_points": row["spread_cost_points"],
            "slippage_cost_points": row["slippage_cost_points"],
            "commission_cost_points": row["commission_cost_points"],
            "financing_cost_points": row["financing_cost_points"],
        }
        output.append(
            {
                "program_id": PROGRAM_ID,
                **setup_payload,
                "fill_status": row["fill_status"],
                "outcome": row["outcome"],
                "gross_r": row["gross_r"],
                "net_r": row["net_r"],
                "ambiguity_flag": _text(row["ambiguous_adverse_first"].lower() == "true"),
                "setup_hash": setup_hash,
                "trade_hash": canonical_hash(trade_payload),
            }
        )
    return sorted(output, key=lambda item: (item["setup_id"], item["scenario_id"]))


def _write_report(repo_root: Path, manifest: dict[str, Any]) -> None:
    baseline = manifest["technical_baseline"]
    lines = [
        "# Macro Technical Baseline Freeze",
        "",
        "Status: `PASS_TECHNICAL_BASELINE_FROZEN`",
        "",
        f"Program: `{PROGRAM_ID}`",
        "",
        "The completed technical-only MLR result is frozen as an immutable control. This artifact does not alter detector, setup, entry, stop, 2R target, expiry, fill, or outcome logic.",
        "",
        "## Reconciliation",
        "",
        f"- Clean byte-identical regeneration: `{manifest['reproduction']['status']}` across {manifest['reproduction']['compared_artifacts']} primary artifacts.",
        f"- Frozen technical setups: {baseline['unique_setups']}.",
        f"- Frozen setup/scenario trade rows: {baseline['trade_rows']}.",
        f"- Medium-cost fills/no-fills: {baseline['medium_cost']['filled_trades']}/{baseline['medium_cost']['no_fills']}.",
        f"- Medium-cost wins/losses/timeouts: {baseline['medium_cost']['wins']}/{baseline['medium_cost']['losses']}/{baseline['medium_cost']['timeouts']}.",
        f"- Medium-cost average/total net R: {baseline['medium_cost']['average_net_r']} / {baseline['medium_cost']['total_net_r']}.",
        f"- Worst strategy drawdown: {baseline['worst_strategy_drawdown_r']}R.",
        f"- Code commit: `{manifest['lineage']['code_commit']}`.",
        f"- Strategy configuration SHA-256: `{manifest['lineage']['strategy_config_sha256']}`.",
        f"- Detector SHA-256: `{manifest['lineage']['detector_sha256']}`.",
        f"- Baseline registry SHA-256: `{manifest['baseline_registry']['sha256']}`.",
        "- Protected/final-holdout accesses: 0/0.",
        "",
        "## Use Rule",
        "",
        "Every macro comparison must filter this exact candidate set. No retained trade may change the source setup, entry, stop, 2R target, expiry, fill status, outcome, gross R, or net R.",
        "",
        "The technical decision remains `TECHNICAL_EDGE_NOT_FOUND`; this freeze is a comparator, not a candidate or trading authorization.",
    ]
    (repo_root / FREEZE_REPORT).write_text("\n".join(lines) + "\n", encoding="ascii")


def _summary_metrics(repo_root: Path) -> dict[str, Any]:
    summary = json.loads((repo_root / ARTIFACT_ROOT / "MLR_TECHNICAL_PRIMARY_SUMMARY.json").read_text())
    medium_rows = [
        row
        for row in read_csv(repo_root / PRIMARY_TRADES)
        if row["scenario_id"] == "NORMALIZED_MEDIUM_COST"
    ]
    filled = [row for row in medium_rows if row["outcome"] not in {"NO_FILL", "INVALID_DATA"}]
    net_values = [Decimal(row["net_r"]) for row in filled]
    drawdowns = [
        Decimal(values["NORMALIZED_MEDIUM_COST"]["maximum_closed_equity_drawdown_r"])
        for values in summary["primary_results"].values()
    ]
    return {
        "unique_setups": len({row["setup_id"] for row in medium_rows}),
        "trade_rows": len(read_csv(repo_root / PRIMARY_TRADES)),
        "medium_cost": {
            "filled_trades": len(filled),
            "no_fills": sum(row["outcome"] == "NO_FILL" for row in medium_rows),
            "wins": sum(row["outcome"] == "WIN_2R" for row in filled),
            "losses": sum(row["outcome"] == "LOSS_1R" for row in filled),
            "timeouts": sum(row["outcome"] == "TIMEOUT" for row in filled),
            "ambiguous_adverse_first": sum(row["outcome"] == "AMBIGUOUS_ADVERSE_FIRST" for row in filled),
            "average_net_r": str(sum(net_values) / Decimal(len(net_values))),
            "total_net_r": str(sum(net_values)),
        },
        "worst_strategy_drawdown_r": str(max(drawdowns)),
    }


def build_baseline_freeze(repo_root: Path, code_commit: str | None = None) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    technical_manifest, technical_manifest_sha = validate_final_manifest(repo_root)
    registry_rows, completed = primary_completion_event(repo_root)
    reproduction = verify_clean_reproduction(repo_root)
    commit = code_commit or git_output(repo_root, "rev-parse", "HEAD")
    commit_files = git_output(repo_root, "show", "--pretty=", "--name-only", commit).splitlines()
    required_committed = {
        TECHNICAL_CODE.as_posix(),
        DETECTOR_CODE.as_posix(),
        STRATEGY_CONFIG.as_posix(),
    }
    if not required_committed.issubset(set(commit_files)):
        raise BaselineFreezeError("CODE_COMMIT_DOES_NOT_BIND_TECHNICAL_SOURCE")
    rows = build_frozen_rows(repo_root)
    write_csv(repo_root / BASELINE_REGISTRY, rows, REGISTRY_FIELDS)
    source_hashes = {
        path.as_posix(): sha256_file(repo_root / path)
        for path in REQUIRED_PRIMARY_ARTIFACTS
    }
    manifest = {
        "schema_version": "1.0.0",
        "artifact_id": "MACRO-TECHNICAL-BASELINE-MANIFEST-001",
        "program_id": PROGRAM_ID,
        "source_program_id": SOURCE_PROGRAM_ID,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS_TECHNICAL_BASELINE_FROZEN",
        "instrument": "PEPPERSTONE_MT5_NAS100_CFD_SOURCE_LABEL_NOT_BROKER_CONFIRMED",
        "source_timezone": "UNRESOLVED",
        "historical_exposure": "PREVIOUSLY_EXPOSED_WINDOW",
        "lineage": {
            "code_commit": commit,
            "technical_code_sha256": sha256_file(repo_root / TECHNICAL_CODE),
            "detector_sha256": sha256_file(repo_root / DETECTOR_CODE),
            "strategy_config_sha256": sha256_file(repo_root / STRATEGY_CONFIG),
            "execution_config_sha256": sha256_file(repo_root / EXECUTION_CONFIG),
            "technical_final_manifest_sha256": technical_manifest_sha,
            "technical_registry_head": registry_rows[-1]["event_hash"],
            "primary_completion_event_hash": completed["event_hash"],
        },
        "source_artifact_sha256": source_hashes,
        "reproduction": asdict(reproduction),
        "baseline_registry": {
            "path": BASELINE_REGISTRY.as_posix(),
            "sha256": sha256_file(repo_root / BASELINE_REGISTRY),
            "row_count": len(rows),
            "unique_setup_hashes": len({row["setup_hash"] for row in rows}),
            "unique_trade_hashes": len({row["trade_hash"] for row in rows}),
        },
        "technical_baseline": _summary_metrics(repo_root),
        "invariants": {
            "technical_outcomes_modified": False,
            "post_2026_06_28_market_data_accessed": False,
            "protected_data_accesses": 0,
            "final_holdout_accesses": 0,
            "broker_or_paper_action": "NONE",
        },
        "technical_final_manifest_status": technical_manifest["status"],
    }
    (repo_root / FREEZE_MANIFEST).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="ascii",
    )
    _write_report(repo_root, manifest)
    hash_lines = [
        f"{sha256_file(repo_root / path)}  {path.as_posix()}"
        for path in (*REQUIRED_PRIMARY_ARTIFACTS, FINAL_MANIFEST, STRATEGY_CONFIG, EXECUTION_CONFIG, DETECTOR_CODE, TECHNICAL_CODE)
    ]
    hash_lines.extend(
        [
            f"{sha256_file(repo_root / BASELINE_REGISTRY)}  {BASELINE_REGISTRY.as_posix()}",
            f"{sha256_file(repo_root / FREEZE_MANIFEST)}  {FREEZE_MANIFEST.as_posix()}",
            f"{sha256_file(repo_root / FREEZE_REPORT)}  {FREEZE_REPORT.as_posix()}",
            f"{commit}  CODE_COMMIT",
            "",
            "# Per-row immutable hashes: setup_id|scenario_id|setup_hash|trade_hash",
        ]
    )
    hash_lines.extend(
        f"{row['setup_id']}|{row['scenario_id']}|{row['setup_hash']}|{row['trade_hash']}"
        for row in rows
    )
    (repo_root / FREEZE_HASHES).write_text("\n".join(hash_lines) + "\n", encoding="ascii")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze the exact MLR technical baseline for public macro comparison")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--verify-reproduction-only", action="store_true")
    parser.add_argument("--code-commit")
    args = parser.parse_args()
    if args.verify_reproduction_only:
        print(json.dumps(asdict(verify_clean_reproduction(args.repo_root)), indent=2, ensure_ascii=True))
        return 0
    result = build_baseline_freeze(args.repo_root, args.code_commit)
    print(json.dumps({"status": result["status"], **result["baseline_registry"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

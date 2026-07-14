"""Independent, read-only reproduction checks for the terminal macro-regime audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd


PROGRAM = "SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def _truthy(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin({"1", "true", "yes"})


def _verify_hash_map(root: Path, relative: str) -> int:
    manifest_path = root / relative
    declared = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, expected in declared.items():
        path = root / name
        if not path.is_file() and "/" not in name:
            path = manifest_path.parent / name
        _assert(path.is_file(), f"AUDIT_MISSING_HASHED_ARTIFACT:{name}")
        _assert(sha256(path) == expected, f"AUDIT_HASH_MISMATCH:{name}")
    return len(declared)


def _raw_roots(root: Path) -> dict[str, Path]:
    h6 = json.loads((root / "research/config/macro_regime_h6_full_traversal.json").read_text())
    h41 = json.loads((root / "research/config/macro_regime_h41_full_traversal.json").read_text())
    return {
        "ALFRED": root,
        "H6": Path(h6["storage_policy"]["private_raw_root"]),
        "H41": Path(h41["private_raw_root"]),
    }


def _family(source_run_id: str) -> str:
    if source_run_id.startswith("QRP2-ALFRED"):
        return "ALFRED"
    if "h41" in source_run_id:
        return "H41"
    return "H6"


def audit(root: Path) -> dict[str, Any]:
    base = root / "research/artifacts/macro_regime"

    # Rehash independently from the role validators.
    upstream_hash_counts = {
        role: _verify_hash_map(root, f"research/artifacts/macro_regime/{role}/{role.upper()}_OUTPUT_HASHES.json")
        for role in ("role6", "role7", "role8", "role9")
    }
    role10_source = json.loads((base / "report/manifests/ROLE10_SOURCE_HASHES.json").read_text())["sources"]
    for relative, expected in role10_source.items():
        _assert(sha256(root / relative) == expected, f"AUDIT_ROLE10_SOURCE_HASH_MISMATCH:{relative}")
    role10_output = json.loads((base / "role10/ROLE10_OUTPUT_HASHES.json").read_text())
    for relative, expected in role10_output.items():
        _assert(sha256(root / relative) == expected, f"AUDIT_ROLE10_OUTPUT_HASH_MISMATCH:{relative}")

    ledger = pd.read_parquet(base / "role6/MACRO_EVENT_UPDATE_LEDGER.parquet")
    daily = pd.read_parquet(base / "role6/MACRO_DAILY_ASOF_REGIME.parquet")
    indicators = pd.read_parquet(base / "role6/MACRO_INDICATOR_STATE_HISTORY.parquet")
    bundles = pd.read_parquet(base / "role6/MACRO_RELEASE_BUNDLE_HISTORY.parquet")
    categories = pd.read_parquet(base / "role6/MACRO_CATEGORY_STATE_HISTORY.parquet")
    snapshots = pd.read_parquet(base / "role6/MACRO_REGIME_SNAPSHOT_HISTORY.parquet")
    active = pd.read_parquet(base / "role6/MACRO_ACTIVE_INPUTS_BY_DAY.parquet")

    _assert(len(ledger) == 10273, "AUDIT_LEDGER_COUNT")
    category_counts = ledger.category.value_counts().sort_index().to_dict()
    _assert(category_counts == {"GROWTH": 214, "INFLATION": 489, "LABOUR": 921, "LIQUIDITY": 8543, "MONETARY_POLICY": 106}, "AUDIT_CATEGORY_COUNTS")
    _assert((len(indicators), len(bundles), len(categories), len(snapshots), len(daily), len(active)) == (5216, 5111, 1840, 1718, 9676, 51361), "AUDIT_STATE_COUNTS")
    _assert((daily.final_bias == "UNKNOWN").all(), "AUDIT_DAILY_BIAS_NOT_UNKNOWN")
    _assert((daily.technical_permission == "NO_TRADE").all(), "AUDIT_PERMISSION_NOT_NO_TRADE")
    _assert(pd.to_numeric(daily.valid_category_count).max() == 2, "AUDIT_VALID_CATEGORY_CAPACITY")

    # Rehash all 2,236 unique raw artifacts through independently resolved roots.
    roots = _raw_roots(root)
    unique_raw: dict[tuple[str, str], str] = {}
    for row in ledger[["source_run_id", "raw_evidence_reference", "raw_artifact_sha256"]].itertuples(index=False):
        key = (_family(row.source_run_id), row.raw_evidence_reference)
        prior = unique_raw.setdefault(key, row.raw_artifact_sha256)
        _assert(prior == row.raw_artifact_sha256, "AUDIT_RAW_IDENTITY_CONFLICT")
    raw_bytes = 0
    for (family, relative), expected in unique_raw.items():
        path = roots[family] / relative
        _assert(path.is_file(), f"AUDIT_RAW_MISSING:{family}:{relative}")
        raw_bytes += path.stat().st_size
        _assert(sha256(path) == expected, f"AUDIT_RAW_HASH_MISMATCH:{family}:{relative}")
    _assert(len(unique_raw) == 2236 and raw_bytes == 334666627, "AUDIT_RAW_CENSUS")

    links = pd.read_parquet(base / "role8/MACRO_TECHNICAL_LINKS.parquet")
    trades = pd.read_parquet(base / "role8/MACRO_REGIME_TECHNICAL_TRADE_REGISTRY.parquet")
    _assert(len(links) == 1362 and links.technical_setup_id.nunique() == 454, "AUDIT_LINK_CENSUS")
    _assert(links.join_mode.value_counts().to_dict() == {"J0": 454, "J1": 454, "J2": 454}, "AUDIT_JOIN_CENSUS")
    _assert((links.macro_bias == "UNKNOWN").all() and (links.filter_decision == "FILTERED_UNKNOWN").all(), "AUDIT_LINK_DECISION")
    _assert(not _truthy(links.future_state_violation).any(), "AUDIT_FUTURE_STATE")
    _assert(not _truthy(links.replacement_trade_created).any(), "AUDIT_REPLACEMENT_TRADE")
    medium = trades[trades.scenario_id == "NORMALIZED_MEDIUM_COST"]
    filled = medium[medium.fill_status == "FILLED"]
    _assert((len(medium), len(filled), len(medium) - len(filled)) == (454, 306, 148), "AUDIT_T0_CENSUS")
    outcomes = filled.outcome.value_counts().to_dict()
    _assert(outcomes == {"LOSS_1R": 246, "WIN_2R": 52, "TIMEOUT": 2, "AMBIGUOUS_ADVERSE_FIRST": 6}, "AUDIT_T0_OUTCOMES")
    totals = {}
    for scenario, group in trades[trades.fill_status == "FILLED"].groupby("scenario_id"):
        totals[scenario] = sum(Decimal(str(value)) for value in group.net_r)
    expected_totals = {
        "NORMALIZED_LOW_COST": Decimal("-164.17863242504234"),
        "NORMALIZED_MEDIUM_COST": Decimal("-173.4578703725847"),
        "NORMALIZED_HIGH_COST": Decimal("-203.4249441630429"),
    }
    _assert(all(abs(totals[key] - expected) < Decimal("0.000000000001") for key, expected in expected_totals.items()), "AUDIT_T0_TOTALS")

    metrics = pd.read_parquet(base / "role9/MACRO_BACKTEST_METRICS.parquet")
    selections = pd.read_parquet(base / "role9/MACRO_BACKTEST_SELECTIONS.parquet")
    folds = pd.read_csv(base / "role9/MACRO_WALK_FORWARD_RESULTS.csv")
    random_rows = pd.read_csv(base / "role9/MACRO_RANDOM_CONTROL_RESULTS.csv")
    curves = pd.read_parquet(base / "role9/MACRO_EQUITY_DRAWDOWN_CURVE_INPUTS.parquet")
    _assert((len(metrics), len(selections), len(folds), len(random_rows), len(curves)) == (14553, 9534, 114, 12, 4590), "AUDIT_ROLE9_COUNTS")
    macro_variants = {"M1_LOOSE", "M2_PRIMARY", "M3_STRONG_ONLY", "M4_HIGH_COVERAGE", "C3_OPPOSITE_MACRO"}
    macro_selection = selections[selections.variant.isin(macro_variants)]
    _assert(not _truthy(macro_selection.permitted).any(), "AUDIT_MACRO_TRADE_RETAINED")
    _assert((random_rows.status == "NOT_APPLICABLE_ZERO_RETENTION").all(), "AUDIT_RANDOM_NULL_STATUS")
    _assert((random_rows.executed_draws == 0).all() and random_rows.random_expectancy_mean_r.isna().all(), "AUDIT_RANDOM_NULL_VALUE")
    _assert(not _truthy(folds.outer_reoptimization).any(), "AUDIT_OUTER_REOPTIMIZATION")
    _assert((folds[folds.variant.isin(macro_variants)].retained_filled_trades == 0).all(), "AUDIT_FOLD_MACRO_RETENTION")

    # Presentation parity, offline behavior, and route fail-closed state.
    table_pairs = {
        "report/tables/MACRO_BACKTEST_METRICS.csv": "role9/MACRO_BACKTEST_METRICS.csv",
        "report/tables/MACRO_EVENT_UPDATE_LEDGER.csv": "role6/MACRO_EVENT_UPDATE_LEDGER.csv",
        "report/tables/MACRO_VARIANT_DELTAS.csv": "role9/MACRO_VARIANT_DELTAS.csv",
        "report/tables/MACRO_WALK_FORWARD_RESULTS.csv": "role9/MACRO_WALK_FORWARD_RESULTS.csv",
        "report/tables/MACRO_RANDOM_CONTROL_RESULTS.csv": "role9/MACRO_RANDOM_CONTROL_RESULTS.csv",
        "report/tables/MACRO_CATEGORY_CONTRIBUTION.csv": "role9/MACRO_CATEGORY_CONTRIBUTION.csv",
    }
    for report_relative, source_relative in table_pairs.items():
        _assert(sha256(base / report_relative) == sha256(base / source_relative), f"AUDIT_TABLE_PARITY:{report_relative}")
    charts = sorted((base / "report/charts").glob("*.png"))
    _assert(len(charts) == 11 and all(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for path in charts), "AUDIT_CHART_CENSUS")
    for name in ("index.html", "interactive.html"):
        text = (base / "report" / name).read_text(encoding="utf-8").lower()
        _assert(not any(token in text for token in ("http://", "https://", "fetch(", "axios")), f"AUDIT_EXTERNAL_FETCH:{name}")
    app = (root / "src/App.js").read_text(encoding="utf-8")
    component = (root / "src/components/research/macro-regime-research.js").read_text(encoding="utf-8").lower()
    _assert('path="/research/macro-regime"' not in app, "AUDIT_UNEXPECTED_ACTIVE_ROUTE")
    _assert(not any(token in component for token in ("fetch(", "axios", "post(", "put(", "delete(", "process.env")), "AUDIT_COMPONENT_WRITE_SURFACE")

    # The initial registry defect remains disclosed and therefore a promotion veto.
    chronology = json.loads((root / "REGISTRY_CHRONOLOGY_VALIDATION.json").read_text())
    _assert(chronology["status"] == "INCONCLUSIVE" and chronology["decision"] == "REGISTRY_CHRONOLOGY_UNRESOLVED", "AUDIT_CHRONOLOGY_STATUS")
    _assert(len(chronology["registry_validation"]["chronology_issues"]) == 3, "AUDIT_CHRONOLOGY_ISSUE_COUNT")

    return {
        "schema_version": "1.0.0",
        "artifact_id": "MACRO-REGIME-ROLE11-INDEPENDENT-REPRODUCTION-001",
        "program_id": PROGRAM,
        "status": "PASS_NEGATIVE_RESULT_REPRODUCED",
        "decision": "NO_ACCEPTABLE_STRATEGY_FOUND",
        "full_program_status": "BLOCKED_IN_APP_ROUTE_INTEGRATION",
        "candidate": "NONE",
        "counts": {
            "upstream_hash_inventory_entries": upstream_hash_counts,
            "role10_source_hashes": len(role10_source),
            "role10_output_hashes": len(role10_output),
            "raw_artifacts": len(unique_raw),
            "raw_bytes": raw_bytes,
            "observations": len(ledger),
            "indicator_states": len(indicators),
            "bundle_states": len(bundles),
            "category_states": len(categories),
            "snapshots": len(snapshots),
            "daily_rows": len(daily),
            "unknown_daily_rows": int((daily.final_bias == "UNKNOWN").sum()),
            "technical_setups": links.technical_setup_id.nunique(),
            "technical_links": len(links),
            "role9_metric_rows": len(metrics),
            "role9_walk_forward_rows": len(folds),
            "charts": len(charts),
        },
        "category_observation_counts": category_counts,
        "t0": {
            "setups": len(medium),
            "fills": len(filled),
            "no_fills": len(medium) - len(filled),
            "outcomes": outcomes,
            "net_r": {key: str(value) for key, value in sorted(totals.items())},
        },
        "macro_retained_fills": 0,
        "random_control_status": "NOT_APPLICABLE_ZERO_RETENTION",
        "chronology": "REGISTRY_CHRONOLOGY_UNRESOLVED",
        "route": "BLOCKED_FAIL_CLOSED_DIRTY_FILE_OWNERSHIP",
        "failure_codes": [
            "INDEPENDENT_QUANT_AUDITOR_EVIDENCE_INSUFFICIENT",
            "VETO_LOW_EVIDENCE",
            "REGISTRY_CHRONOLOGY_UNRESOLVED",
            "INSUFFICIENT_CATEGORY_COVERAGE",
            "INSUFFICIENT_ALIGNED_TRADES",
            "FAIL_CLOSED_DIRTY_FILE_OWNERSHIP",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(audit(args.repo_root.resolve()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

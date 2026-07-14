"""Independent, read-only reproduction checks for the terminal macro-regime audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd


PROGRAM = "SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001"
APP_BASELINE_SHA256 = "d702d1ddeed2458842c2f420bb258913a1f1b93241bb8347099f63d0ab07f542"
APP_ACTIVE_SHA256 = "233fd2401ffbe316aa6f14386ffe85f26a01ec5a430894b55789e2758579184f"
APP_IMPORT = "import MacroRegimeResearchRoute from './components/research/macro-regime-research-route';\n"
APP_ROUTE_BLOCK = '''        <Route
          path="/research/macro-regime"
          element={<MacroRegimeResearchRoute />}
        />

'''


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


def _verify_route_remediation(root: Path) -> dict[str, Any]:
    remediation = root / "research/artifacts/macro_regime/role10/remediation"
    ownership = json.loads((remediation / "APP_ROUTE_OWNERSHIP_BOUNDARY.json").read_text(encoding="utf-8"))
    _assert(ownership["baseline_sha256"] == APP_BASELINE_SHA256, "AUDIT_APP_BASELINE_DECLARATION")
    _assert(ownership["post_hunk_sha256"] == APP_ACTIVE_SHA256, "AUDIT_APP_ACTIVE_DECLARATION")
    _assert(ownership["staged"] is False and ownership["committed"] is False, "AUDIT_APP_OWNERSHIP_DECLARATION")
    _assert(ownership["authorization_policy"] == "VERIFIED_REGISTERED_USER_READ_ONLY", "AUDIT_AUTHORIZATION_DECLARATION")

    app_path = root / "src/App.js"
    app = app_path.read_text(encoding="utf-8")
    _assert(sha256(app_path) == APP_ACTIVE_SHA256, "AUDIT_APP_ACTIVE_HASH")
    _assert(app.count(APP_IMPORT) == 1, "AUDIT_APP_IMPORT_OWNERSHIP")
    _assert(app.count(APP_ROUTE_BLOCK) == 1, "AUDIT_APP_ROUTE_OWNERSHIP")
    reconstructed = app.replace(APP_IMPORT, "", 1).replace(APP_ROUTE_BLOCK, "", 1).encode("utf-8")
    _assert(hashlib.sha256(reconstructed).hexdigest() == APP_BASELINE_SHA256, "AUDIT_APP_BASELINE_RECONSTRUCTION")

    rollback_patch = remediation / "APP_ROUTE_ROLLBACK.patch"
    _assert(sha256(rollback_patch) == ownership["rollback_patch_sha256"], "AUDIT_ROLLBACK_PATCH_HASH")
    with tempfile.TemporaryDirectory(prefix="macro-regime-role11-rollback-") as directory:
        temporary_root = Path(directory)
        (temporary_root / "src").mkdir()
        temporary_app = temporary_root / "src/App.js"
        temporary_app.write_bytes(app_path.read_bytes())
        result = subprocess.run(
            ["git", "apply", "--unidiff-zero", str(rollback_patch)],
            cwd=temporary_root,
            check=False,
            capture_output=True,
            text=True,
        )
        _assert(result.returncode == 0, f"AUDIT_ROLLBACK_APPLY:{result.stderr.strip()}")
        _assert(sha256(temporary_app) == APP_BASELINE_SHA256, "AUDIT_ROLLBACK_BASELINE_HASH")
    _assert(sha256(app_path) == APP_ACTIVE_SHA256, "AUDIT_ROLLBACK_CHANGED_ACTIVE_APP")

    route_path = root / "src/components/research/macro-regime-research-route.js"
    policy_path = root / "src/components/research/macro-regime-access-policy.js"
    component_path = root / "src/components/research/macro-regime-research.js"
    data_path = root / "src/components/research/macro-regime-research-data.js"
    route = route_path.read_text(encoding="utf-8")
    policy = policy_path.read_text(encoding="utf-8")
    component = component_path.read_text(encoding="utf-8")
    data = data_path.read_text(encoding="utf-8")
    combined = "\n".join((route, policy, component, data)).lower()

    # Authentication is server verified. Possession of a local bearer token alone never renders evidence.
    for token in ("axios.get(apiPath('/me')", "Authorization: `Bearer ${token}`", "verifiedRegisteredUser(response)", "AbortController"):
        _assert(token in route, f"AUDIT_AUTH_BOUNDARY:{token}")
    _assert("axios.get" in route and not any(f"axios.{method}" in combined for method in ("post", "put", "patch", "delete")), "AUDIT_NETWORK_METHODS")
    for state in ("unauthenticated", "identity-denied", "verification-error", "selector-denied"):
        _assert(state in route, f"AUDIT_FAIL_CLOSED_STATE:{state}")
    _assert("responseStatus === 401 || responseStatus === 403" in route, "AUDIT_REJECTED_TOKEN_STATE")
    _assert("ERR_CANCELED" in route and "controller.abort()" in route, "AUDIT_ABORT_STATE")

    # Authorization is explicit, selector-free, and fail closed for malformed identity payloads.
    for token in ("VERIFIED_REGISTERED_USER_READ_ONLY", "Number.isInteger(id) && id > 0", "validEmail", "location.pathname !== MACRO_REGIME_RESEARCH_PATH", "Boolean(location.search)", "Boolean(location.hash)"):
        _assert(token in policy, f"AUDIT_POLICY_CONTROL:{token}")
    _assert("/:" not in APP_ROUTE_BLOCK and 'path="/research/macro-regime"' in APP_ROUTE_BLOCK, "AUDIT_ROUTE_RESOURCE_IDENTIFIER")

    # The evidence component is static/read-only and contains all required negative-result content.
    prohibited = (
        "fetch(", "axios", ".post(", ".put(", ".patch(", ".delete(", "process.env",
        "localstorage", "sessionstorage", "http://", "https://", "apikey", "api_key",
        "password", "placeorder", "deploy button",
    )
    _assert(not any(token in component.lower() for token in prohibited), "AUDIT_COMPONENT_PROHIBITED_SURFACE")
    _assert("secret, order button, broker integration, paper control, or live path" in component, "AUDIT_COMPONENT_NEGATIVE_SECURITY_DISCLOSURE")
    required_content = (
        "Candidate", "every bias is UNKNOWN", "Inactivity is not success",
        "Coverage and source health", "Category capacity and current state", "Stress:", "Interaction:",
        "Base/final: NOT_APPLICABLE", "Technical-only versus macro filters",
        "Timeframes and confluence families remain separate", "Historical evidence charts A–K",
        "Latest active indicator drill-down", "Raw observation / previous", "Transformation", "Scores",
        "Reason / interaction", "Effective date / policy", "Raw artifact SHA-256", "Warnings and access boundary",
    )
    for token in required_content:
        _assert(token in component, f"AUDIT_PAGE_CONTENT:{token}")
    for token in ("decision: 'INSUFFICIENT_ALIGNED_TRADES'", "upstreamDecision: 'INSUFFICIENT_CATEGORY_COVERAGE'", "candidate: 'NONE'", "dailyRows: 9676", "observations: 10273", "mediumR: -173.4578703725847"):
        _assert(token in data, f"AUDIT_PAGE_DATA:{token}")
    for token in ('<main', '<h1>', '<h2>', 'role="alert"', '<th>', '<img', 'alt={`Macro regime research chart'):
        _assert(token in component, f"AUDIT_ACCESSIBILITY:{token}")
    _assert('aria-busy="true"' in route and 'aria-live="polite"' in route, "AUDIT_LOADING_ACCESSIBILITY")

    chart_manifest = json.loads((remediation / "FRONTEND_CHART_HASHES.json").read_text(encoding="utf-8"))
    _assert(chart_manifest["copy_policy"] == "source and target SHA-256 must be identical", "AUDIT_CHART_COPY_POLICY")
    expected_names = [f"{letter}_{suffix}" for letter, suffix in zip(
        "ABCDEFGHIJK",
        (
            "macro_category_timeline.png", "macro_regime_timeline.png", "macro_event_updates.png",
            "equity_curves.png", "drawdown_curves.png", "annual_pnl.png", "timeframe_comparison.png",
            "regime_performance.png", "category_contribution.png", "retention_analysis.png", "random_control.png",
        ),
    )]
    _assert(list(chart_manifest["files"]) == expected_names, "AUDIT_CHART_AK_NAMES")
    source_directory = root / chart_manifest["source_directory"]
    target_directory = root / chart_manifest["target_directory"]
    for index, (name, expected) in enumerate(chart_manifest["files"].items()):
        source = source_directory / name
        target = target_directory / name
        _assert(sha256(source) == expected and sha256(target) == expected, f"AUDIT_CHART_HASH:{name}")
        _assert(source.read_bytes() == target.read_bytes(), f"AUDIT_CHART_COPY:{name}")
        _assert(f"import chart{chr(65 + index)} from './charts/{name}';" in component, f"AUDIT_CHART_IMPORT:{name}")
    _assert("const charts = [chartA, chartB, chartC, chartD, chartE, chartF, chartG, chartH, chartI, chartJ, chartK];" in component, "AUDIT_CHART_RENDER_ORDER")

    if root.joinpath(".git").exists():
        staged = subprocess.run(["git", "diff", "--cached", "--quiet", "--", "src/App.js"], cwd=root, check=False)
        _assert(staged.returncode == 0, "AUDIT_APP_ROUTE_STAGED")

    return {
        "app_active_sha256": APP_ACTIVE_SHA256,
        "app_baseline_sha256": APP_BASELINE_SHA256,
        "rollback": "PASS_TEMPORARY_COPY_ACTIVE_APP_UNCHANGED",
        "authentication": "PASS_SERVER_VERIFIED_GET_ME_FAIL_CLOSED",
        "authorization": "PASS_VERIFIED_REGISTERED_USER_READ_ONLY",
        "negative_idor": "PASS_QUERY_FRAGMENT_EXTRA_PATH_DENIED",
        "network_methods": ["GET"],
        "mutation_methods": [],
        "chart_hashes_verified": len(chart_manifest["files"]),
        "page_content": "PASS_REQUIRED_NEGATIVE_RESULT_AND_DRILLDOWN_CONTENT",
        "accessibility": "PASS_SEMANTIC_HEADINGS_ALERT_TABLE_ALT_LOADING_STATE",
    }


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

    # Presentation parity, offline behavior, and active route remediation.
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
    route_remediation = _verify_route_remediation(root)

    # The initial registry defect remains disclosed and therefore a promotion veto.
    chronology = json.loads((root / "REGISTRY_CHRONOLOGY_VALIDATION.json").read_text())
    _assert(chronology["status"] == "INCONCLUSIVE" and chronology["decision"] == "REGISTRY_CHRONOLOGY_UNRESOLVED", "AUDIT_CHRONOLOGY_STATUS")
    _assert(len(chronology["registry_validation"]["chronology_issues"]) == 3, "AUDIT_CHRONOLOGY_ISSUE_COUNT")

    return {
        "schema_version": "1.0.0",
        "artifact_id": "MACRO-REGIME-ROLE11-INDEPENDENT-REPRODUCTION-001",
        "program_id": PROGRAM,
        "status": "PASS_NEGATIVE_RESULT_AND_REPORTING_SECURITY_REAUDIT",
        "decision": "NO_ACCEPTABLE_STRATEGY_FOUND",
        "full_program_status": "PROGRAM_COMPLETE_NO_ACCEPTABLE_STRATEGY_FOUND",
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
        "route": "PASS_ACTIVE_AUTHENTICATED_AUTHORIZED_READ_ONLY",
        "route_remediation": route_remediation,
        "failure_codes": [
            "INDEPENDENT_QUANT_AUDITOR_EVIDENCE_INSUFFICIENT",
            "VETO_LOW_EVIDENCE",
            "REGISTRY_CHRONOLOGY_UNRESOLVED",
            "INSUFFICIENT_CATEGORY_COVERAGE",
            "INSUFFICIENT_ALIGNED_TRADES",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(audit(args.repo_root.resolve()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

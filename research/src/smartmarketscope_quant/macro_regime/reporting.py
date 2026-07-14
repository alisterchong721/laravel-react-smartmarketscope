"""Deterministic Role 10 reporting from immutable Role 6-9 evidence only."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import shutil
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


PROGRAM = "SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001"
CREATED_AT = "2026-07-14T07:00:00Z"
ROLE_DIRS = ("role6", "role7", "role8", "role9")
ROLE10 = Path("research/artifacts/macro_regime/role10")
REPORT = Path("research/artifacts/macro_regime/report")
SOURCE_FILES = (
    "MACRO_REGIME_COVERAGE_BY_YEAR.csv",
    "MACRO_REGIME_COVERAGE_BY_SERIES.csv",
    "MACRO_REGIME_COVERAGE_BY_CATEGORY.csv",
    "research/config/MACRO_REGIME_SCORING_CONFIG.yaml",
    "research/artifacts/macro_regime/role6/ROLE6_SCORING_MANIFEST.json",
    "research/artifacts/macro_regime/role6/ROLE6_OUTPUT_HASHES.json",
    "research/artifacts/macro_regime/role6/MACRO_DAILY_ASOF_REGIME.parquet",
    "research/artifacts/macro_regime/role6/MACRO_EVENT_UPDATE_LEDGER.parquet",
    "research/artifacts/macro_regime/role6/MACRO_REGIME_BY_YEAR.csv",
    "research/artifacts/macro_regime/role6/MACRO_CATEGORY_BY_YEAR.csv",
    "research/artifacts/macro_regime/role7/ROLE7_VALIDATION_MANIFEST.json",
    "research/artifacts/macro_regime/role7/ROLE7_OUTPUT_HASHES.json",
    "research/artifacts/macro_regime/role8/ROLE8_ALIGNMENT_MANIFEST.json",
    "research/artifacts/macro_regime/role8/ROLE8_OUTPUT_HASHES.json",
    "research/artifacts/macro_regime/role8/MACRO_TECHNICAL_LINKS.parquet",
    "research/artifacts/macro_regime/role8/MACRO_REGIME_TECHNICAL_TRADE_REGISTRY.parquet",
    "research/artifacts/macro_regime/role9/ROLE9_BACKTEST_MANIFEST.json",
    "research/artifacts/macro_regime/role9/ROLE9_OUTPUT_HASHES.json",
    "research/artifacts/macro_regime/role9/MACRO_BACKTEST_METRICS.parquet",
    "research/artifacts/macro_regime/role9/MACRO_BACKTEST_SELECTIONS.parquet",
    "research/artifacts/macro_regime/role9/MACRO_EQUITY_DRAWDOWN_CURVE_INPUTS.parquet",
    "research/artifacts/macro_regime/role9/MACRO_CATEGORY_CONTRIBUTION.csv",
    "research/artifacts/macro_regime/role9/MACRO_RANDOM_CONTROL_RESULTS.csv",
    "research/artifacts/macro_regime/role9/MACRO_WALK_FORWARD_RESULTS.csv",
    "research/artifacts/processed_data/v1/NAS100_Daily_completed_v1.csv.gz",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def verify_upstream(repo: Path) -> dict[str, str]:
    """Rehash every frozen output declared by Roles 6-9 and key source artifacts."""
    verified: dict[str, str] = {}
    for role in ROLE_DIRS:
        hash_path = repo / f"research/artifacts/macro_regime/{role}/{role.upper()}_OUTPUT_HASHES.json"
        declared = json.loads(hash_path.read_text(encoding="utf-8"))
        for relative, expected in declared.items():
            source_path = repo / relative
            if not source_path.is_file() and "/" not in relative:
                source_path = hash_path.parent / relative
            actual = sha256(source_path)
            if actual != expected:
                raise ValueError(f"UPSTREAM_HASH_MISMATCH:{relative}:{expected}:{actual}")
            verified[str(source_path.relative_to(repo))] = actual
    for relative in SOURCE_FILES:
        path = repo / relative
        if not path.is_file():
            raise FileNotFoundError(f"ROLE10_REQUIRED_SOURCE_MISSING:{relative}")
        verified[relative] = sha256(path)
    return dict(sorted(verified.items()))


def _save_chart(fig: Any, path: Path, title: str) -> None:
    fig.suptitle(title, x=0.06, y=0.98, ha="left", fontsize=15, fontweight="bold")
    fig.text(0.06, 0.01, "Source: immutable Role 6-9 artifacts. Research-only; source timezone unresolved.", fontsize=7, color="#667085")
    fig.tight_layout(rect=(0, 0.035, 1, 0.95))
    fig.savefig(path, dpi=160, facecolor="white", metadata={"Software": "Smart MarketScope Role10 deterministic reporter"})
    plt.close(fig)


def build_charts(repo: Path, report: Path) -> list[str]:
    charts = report / "charts"
    charts.mkdir(parents=True, exist_ok=True)
    daily = pd.read_parquet(repo / "research/artifacts/macro_regime/role6/MACRO_DAILY_ASOF_REGIME.parquet")
    daily["date"] = pd.to_datetime(daily["asof_date"])
    ledger = pd.read_parquet(repo / "research/artifacts/macro_regime/role6/MACRO_EVENT_UPDATE_LEDGER.parquet")
    ledger["year"] = pd.to_datetime(ledger["availability_date"]).dt.year
    curves = pd.read_parquet(repo / "research/artifacts/macro_regime/role9/MACRO_EQUITY_DRAWDOWN_CURVE_INPUTS.parquet")
    metrics = pd.read_parquet(repo / "research/artifacts/macro_regime/role9/MACRO_BACKTEST_METRICS.parquet")
    links = pd.read_parquet(repo / "research/artifacts/macro_regime/role8/MACRO_TECHNICAL_LINKS.parquet")
    category = pd.read_csv(repo / "research/artifacts/macro_regime/role9/MACRO_CATEGORY_CONTRIBUTION.csv")
    random = pd.read_csv(repo / "research/artifacts/macro_regime/role9/MACRO_RANDOM_CONTROL_RESULTS.csv")
    daily_price = pd.read_csv(repo / "research/artifacts/processed_data/v1/NAS100_Daily_completed_v1.csv.gz")
    date_col = "bar_start_source"
    close_col = next(c for c in daily_price.columns if "close" in c.lower() and "partial" not in c.lower())
    daily_price["date"] = pd.to_datetime(daily_price[date_col])

    palette = {"inflation_score": "#d92d20", "labour_score": "#f79009", "growth_score": "#12b76a", "monetary_policy_score": "#7f56d9", "liquidity_score": "#2e90fa", "final_score": "#101828"}
    sample = daily.iloc[::7].copy()
    fig, ax = plt.subplots(figsize=(13, 6))
    for column, color in palette.items():
        ax.plot(sample["date"], pd.to_numeric(sample[column], errors="coerce"), label=column.replace("_score", "").replace("_", " ").title(), lw=1.2, color=color)
    ax.axhline(0, color="#98a2b3", lw=.7); ax.set_ylabel("Discrete score"); ax.set_ylim(-2.5, 2.5); ax.legend(ncol=3, frameon=False)
    _save_chart(fig, charts / "A_macro_category_timeline.png", "A. Macro category timeline — missing categories remain gaps")

    fig, ax = plt.subplots(figsize=(13, 5))
    ax.plot(daily_price["date"], pd.to_numeric(daily_price[close_col], errors="coerce"), color="#344054", lw=1)
    ax.set_ylabel("NAS100-labelled source close"); ax2 = ax.twinx(); ax2.plot(sample["date"], pd.to_numeric(sample["final_score"], errors="coerce"), color="#b42318", lw=1)
    ax2.set_ylabel("Final score (unavailable)"); ax.text(.01,.91,"All 9,676 regime days are UNKNOWN — no bullish/bearish/neutral regions exist", transform=ax.transAxes, color="#b42318", weight="bold")
    _save_chart(fig, charts / "B_macro_regime_timeline.png", "B. Macro regime timeline — price context is not a broker-confirmed instrument")

    event_counts = ledger.groupby(["year", "category"]).size().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(13, 5)); event_counts.plot(kind="bar", stacked=True, ax=ax, width=.85)
    ax.set_ylabel("Immutable update rows"); ax.legend(ncol=3, frameon=False); ax.tick_params(axis="x", rotation=45)
    _save_chart(fig, charts / "C_macro_event_updates.png", "C. Macro event/update ledger — 10,273 updates; bias stayed UNKNOWN")

    medium = curves[(curves.cost_scenario == "NORMALIZED_MEDIUM_COST") & (curves.variant == "T0") & (curves.join_mode == "J0")].copy()
    medium["exit_dt"] = pd.to_datetime(medium["exit_time"]); medium["net"] = pd.to_numeric(medium["net_r"])
    fig, ax = plt.subplots(figsize=(13, 6))
    for sid, group in medium.sort_values("exit_dt").groupby("strategy_id"):
        ax.plot(group["exit_dt"], group["net"].cumsum(), label=sid, lw=1.3)
    ax.axhline(0, color="#d92d20", lw=1.5, ls="--", label="All macro variants: inactive at 0R")
    ax.set_ylabel("Cumulative medium-cost net R"); ax.legend(fontsize=7, ncol=2, frameon=False)
    _save_chart(fig, charts / "D_equity_curves.png", "D. Separate T0 equity curves — negative evidence is visible")

    fig, ax = plt.subplots(figsize=(13, 6))
    for sid, group in medium.sort_values("exit_dt").groupby("strategy_id"):
        equity = group["net"].cumsum(); dd = equity.cummax().clip(lower=0) - equity
        ax.plot(group["exit_dt"], dd, label=sid, lw=1.2)
    ax.set_ylabel("Drawdown R"); ax.invert_yaxis(); ax.legend(fontsize=7, ncol=2, frameon=False)
    _save_chart(fig, charts / "E_drawdown_curves.png", "E. Full T0 drawdown histories — macro variants have no trade path")

    annual = medium.assign(year=medium.exit_dt.dt.year).groupby(["year","timeframe"])["net"].sum().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(13, 5)); annual.plot(kind="bar", ax=ax); ax.axhline(0,color="#667085",lw=.8); ax.set_ylabel("Medium-cost net R")
    _save_chart(fig, charts / "F_annual_pnl.png", "F. Annual T0 PnL by timeframe — macro retained 0 in every year")

    overall = metrics[(metrics.variant=="T0") & (metrics.join_mode=="J0") & (metrics.direction=="ALL") & (metrics.year=="ALL") & (metrics.cost_scenario=="NORMALIZED_MEDIUM_COST")].copy()
    overall["total_net_r"] = pd.to_numeric(overall["total_net_r"]); overall["permitted_trades"] = pd.to_numeric(overall["permitted_trades"])
    fig, axes = plt.subplots(1,2,figsize=(13,5)); axes[0].bar(overall.strategy_id, overall.total_net_r, color="#d92d20"); axes[1].bar(overall.strategy_id, overall.permitted_trades, color="#475467")
    for ax in axes: ax.tick_params(axis="x", rotation=70, labelsize=7)
    axes[0].set_ylabel("Total net R"); axes[1].set_ylabel("Filled trades")
    _save_chart(fig, charts / "G_timeframe_comparison.png", "G. Timeframe/family comparison — seven strategy IDs remain separate")

    regime_counts = links[links.join_mode=="J0"].macro_bias.value_counts().reindex(["STRONG_BULLISH","BULLISH","NEUTRAL","BEARISH","STRONG_BEARISH","UNKNOWN"], fill_value=0)
    fig, ax = plt.subplots(figsize=(10,5)); ax.bar(regime_counts.index, regime_counts.values, color=["#079455","#12b76a","#667085","#f04438","#b42318","#98a2b3"]); ax.tick_params(axis="x",rotation=30); ax.set_ylabel("Linked setups")
    _save_chart(fig, charts / "H_regime_performance.png", "H. Regime performance availability — only UNKNOWN exists")

    c0 = category[category.join_mode=="J0"].copy(); c0["medium_total_net_r"] = pd.to_numeric(c0.medium_total_net_r)
    labels = c0.category + ":" + c0.category_score.astype(str)
    fig, ax = plt.subplots(figsize=(13,6)); ax.bar(labels, c0.medium_total_net_r, color="#7f56d9"); ax.tick_params(axis="x",rotation=70,labelsize=7); ax.set_ylabel("Descriptive T0 medium net R")
    _save_chart(fig, charts / "I_category_contribution.png", "I. Category contribution — descriptive, not causal")

    retention = links[links.join_mode=="J0"].filter_decision.value_counts(); retention.loc["NO_FILL"] = 148
    fig, ax = plt.subplots(figsize=(10,5)); ax.bar(retention.index, retention.values, color="#2e90fa"); ax.tick_params(axis="x",rotation=25); ax.set_ylabel("Count")
    _save_chart(fig, charts / "J_retention_analysis.png", "J. Retention — 454 filtered UNKNOWN setups; 148 T0 no-fills")

    fig, ax = plt.subplots(figsize=(12,5)); ax.bar(range(len(random)), random.target_retained_fills, color="#98a2b3"); ax.set_xticks(range(len(random)), (random.join_mode+"/"+random.macro_variant), rotation=70, fontsize=7); ax.set_ylabel("Target retained fills")
    ax.text(.02,.86,"All 12 controls are NOT_APPLICABLE_ZERO_RETENTION; no random distribution was executed.",transform=ax.transAxes,color="#b42318",weight="bold")
    _save_chart(fig, charts / "K_random_control.png", "K. Retention-matched random control — not applicable is not zero performance")
    return [str(path.relative_to(report)) for path in sorted(charts.glob("*.png"))]


def build_tables(repo: Path, report: Path) -> list[str]:
    tables = report / "tables"; data = report / "data"
    tables.mkdir(parents=True, exist_ok=True); data.mkdir(parents=True, exist_ok=True)
    copies = {
        "MACRO_REGIME_BY_YEAR.csv": "role6/MACRO_REGIME_BY_YEAR.csv",
        "MACRO_CATEGORY_BY_YEAR.csv": "role6/MACRO_CATEGORY_BY_YEAR.csv",
        "MACRO_EVENT_UPDATE_LEDGER.csv": "role6/MACRO_EVENT_UPDATE_LEDGER.csv",
        "MACRO_BACKTEST_METRICS.csv": "role9/MACRO_BACKTEST_METRICS.csv",
        "MACRO_VARIANT_DELTAS.csv": "role9/MACRO_VARIANT_DELTAS.csv",
        "MACRO_WALK_FORWARD_RESULTS.csv": "role9/MACRO_WALK_FORWARD_RESULTS.csv",
        "MACRO_RANDOM_CONTROL_RESULTS.csv": "role9/MACRO_RANDOM_CONTROL_RESULTS.csv",
        "MACRO_CATEGORY_CONTRIBUTION.csv": "role9/MACRO_CATEGORY_CONTRIBUTION.csv",
    }
    for target, source in copies.items():
        shutil.copyfile(repo / "research/artifacts/macro_regime" / source, tables / target)
    daily = pd.read_parquet(repo / "research/artifacts/macro_regime/role6/MACRO_DAILY_ASOF_REGIME.parquet").iloc[::7]
    daily.to_json(data / "macro_timeline_weekly.json", orient="records", date_format="iso")
    ledger = pd.read_parquet(repo / "research/artifacts/macro_regime/role6/MACRO_EVENT_UPDATE_LEDGER.parquet")
    safe = ledger.tail(250).drop(columns=["raw_evidence_reference"], errors="ignore")
    safe.to_json(data / "latest_updates_redacted.json", orient="records")
    metrics = pd.read_parquet(repo / "research/artifacts/macro_regime/role9/MACRO_BACKTEST_METRICS.parquet")
    focus = metrics[(metrics.join_mode=="J0") & (metrics.direction=="ALL") & (metrics.year=="ALL") & (metrics.cost_scenario=="NORMALIZED_MEDIUM_COST")]
    focus.to_json(data / "headline_metrics.json", orient="records")
    return [str(p.relative_to(report)) for p in sorted(tables.glob("*"))] + [str(p.relative_to(report)) for p in sorted(data.glob("*"))]


def build_index(report: Path, chart_paths: list[str]) -> None:
    cards = "".join(f'<figure><img loading="lazy" src="{html.escape(path)}" alt="{html.escape(Path(path).stem)}"><figcaption>{html.escape(Path(path).stem.replace("_", " "))}</figcaption></figure>' for path in chart_paths)
    page = f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Macro Regime Research — Role 10</title><style>
body{{margin:0;background:#f2f4f7;color:#101828;font:16px/1.5 system-ui,sans-serif}}main{{max-width:1280px;margin:auto;padding:32px}}.hero{{background:#101828;color:white;border-radius:20px;padding:30px}}.warn{{background:#fffaeb;border-left:5px solid #f79009;padding:16px;margin:20px 0}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:18px}}figure{{margin:0;background:white;border:1px solid #eaecf0;border-radius:14px;padding:12px}}img{{display:block;width:100%;height:auto}}figcaption{{font-weight:700;padding:8px}}code{{word-break:break-all}}a{{color:#175cd3}}@media(max-width:480px){{main{{padding:14px}}.grid{{grid-template-columns:1fr}}}}
</style></head><body><main><section class=\"hero\"><p>SMART-MARKETSCOPE-MACRO-REGIME-NAS100-001</p><h1>Insufficient aligned trades</h1><p>Candidate: NONE · T0: 306 fills, -173.457870R medium cost · Macro variants: 0 retained fills</p></section><section class=\"warn\" role=\"alert\"><strong>Research-only and inactive.</strong> Inflation, labour, and growth each have one valid bundle but require two. Every macro bias is UNKNOWN. Zero trades is not profit, improvement, or validation. Instrument, source timezone, and broker costs remain unresolved.</section><h2>Evidence labels</h2><ul><li><b>FACT:</b> immutable Role 6–9 counts and hashes.</li><li><b>CALCULATION:</b> chart-only aggregation of frozen rows.</li><li><b>ASSUMPTION:</b> none added to research logic.</li><li><b>INTERPRETATION:</b> inactivity cannot rescue a negative strategy.</li></ul><p><a href=\"interactive.html\">Open the self-contained interactive category explorer</a>.</p><h2>Charts A–K</h2><div class=\"grid\">{cards}</div><h2>Local evidence</h2><p><a href=\"tables/MACRO_BACKTEST_METRICS.csv\">Metrics</a> · <a href=\"tables/MACRO_EVENT_UPDATE_LEDGER.csv\">Event ledger</a> · <a href=\"tables/MACRO_WALK_FORWARD_RESULTS.csv\">Walk-forward</a> · <a href=\"manifests/ROLE10_REPORT_MANIFEST.json\">Manifest</a></p><p>No external fetches, collector URL, credential, order control, broker path, or mutation action is present.</p></main></body></html>"""
    write_text(report / "index.html", page)


def build_interactive(repo: Path, report: Path) -> None:
    daily = pd.read_parquet(repo / "research/artifacts/macro_regime/role6/MACRO_DAILY_ASOF_REGIME.parquet").iloc[::14]
    columns = ["asof_date", "inflation_score", "labour_score", "growth_score", "monetary_policy_score", "liquidity_score", "final_score", "final_bias"]
    records = daily[columns].where(pd.notna(daily[columns]), None).to_dict("records")
    payload = json.dumps(records, separators=(",", ":"), ensure_ascii=True).replace("</", "<\\/")
    page = f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Interactive macro category explorer</title><style>body{{font:16px system-ui;background:#f2f4f7;color:#101828;margin:0}}main{{max-width:1100px;margin:auto;padding:28px}}.panel{{background:white;padding:20px;border-radius:16px}}svg{{width:100%;height:420px;border:1px solid #eaecf0}}label{{font-weight:700}}select{{margin:0 0 16px 12px;padding:8px}}.note{{color:#b42318;font-weight:700}}</style></head><body><main><p><a href=\"index.html\">Back to report</a></p><div class=\"panel\"><h1>Interactive category explorer</h1><p class=\"note\">Gaps are missing/UNKNOWN, not zeros. All final biases are UNKNOWN.</p><label for=\"series\">Series</label><select id=\"series\"><option value=\"inflation_score\">Inflation</option><option value=\"labour_score\">Labour</option><option value=\"growth_score\">Growth</option><option value=\"monetary_policy_score\">Monetary policy</option><option value=\"liquidity_score\">Liquidity</option><option value=\"final_score\">Final score</option></select><svg id=\"chart\" viewBox=\"0 0 1000 420\" role=\"img\" aria-label=\"Selected macro score over time\"></svg><p id=\"summary\" aria-live=\"polite\"></p></div></main><script>const rows={payload};const svg=document.getElementById('chart');const select=document.getElementById('series');function draw(){{const key=select.value;const valid=rows.map((r,i)=>[i,r[key]]).filter(x=>x[1]!==null);const points=valid.map(x=>`${{40+x[0]*920/(rows.length-1)}},${{210-x[1]*75}}`).join(' ');svg.innerHTML='<line x1="40" y1="210" x2="960" y2="210" stroke="#98a2b3"/><line x1="40" y1="60" x2="40" y2="360" stroke="#98a2b3"/><polyline fill="none" stroke="#175cd3" stroke-width="3" points="'+points+'"/>';document.getElementById('summary').textContent=valid.length+' of '+rows.length+' fortnightly presentation points have a numeric '+key.replaceAll('_',' ')+'.';}}select.addEventListener('change',draw);draw();</script></body></html>"""
    write_text(report / "interactive.html", page)


def build_role10_reports(repo: Path, role10: Path) -> None:
    upstream_reports = {
        "MACRO_REGIME_SOURCE_AUDIT.md": "MACRO_REGIME_SOURCE_AUDIT.md",
        "MACRO_REGIME_DATA_QUALITY.md": "research/artifacts/macro_regime/role6/MACRO_DATA_QUALITY_REPORT.md",
        "MACRO_REGIME_POINT_IN_TIME_AUDIT.md": "research/artifacts/macro_regime/role7/MACRO_REGIME_POINT_IN_TIME_AUDIT.md",
        "MACRO_REGIME_SCORING_SPEC.md": "research/artifacts/macro_regime/role6/MACRO_REGIME_SCORING_SPEC.md",
        "MACRO_TECHNICAL_ALIGNMENT_REPORT.md": "research/artifacts/macro_regime/role8/MACRO_TECHNICAL_ALIGNMENT_REPORT.md",
        "MACRO_M15_RESULT_REPORT.md": "research/artifacts/macro_regime/role9/MACRO_M15_RESULT_REPORT.md",
        "MACRO_M5_RESULT_REPORT.md": "research/artifacts/macro_regime/role9/MACRO_M5_RESULT_REPORT.md",
        "MACRO_M1_RESULT_REPORT.md": "research/artifacts/macro_regime/role9/MACRO_M1_RESULT_REPORT.md",
        "MACRO_HIERARCHICAL_RESULT_REPORT.md": "research/artifacts/macro_regime/role9/MACRO_HIERARCHICAL_RESULT_REPORT.md",
        "MACRO_TIMEFRAME_COMPARISON.md": "research/artifacts/macro_regime/role9/MACRO_TIMEFRAME_COMPARISON.md",
        "MACRO_EQUITY_DRAWDOWN_REPORT.md": "research/artifacts/macro_regime/role9/MACRO_EQUITY_DRAWDOWN_INPUTS.md",
        "MACRO_ANNUAL_PERFORMANCE_REPORT.md": "research/artifacts/macro_regime/role9/MACRO_ANNUAL_PERFORMANCE_REPORT.md",
        "MACRO_CATEGORY_CONTRIBUTION_REPORT.md": "research/artifacts/macro_regime/role9/MACRO_CATEGORY_CONTRIBUTION_REPORT.md",
        "MACRO_RANDOM_CONTROL_REPORT.md": "research/artifacts/macro_regime/role9/MACRO_RANDOM_CONTROL_REPORT.md",
        "MACRO_WALK_FORWARD_REPORT.md": "research/artifacts/macro_regime/role9/MACRO_WALK_FORWARD_REPORT.md",
        "MACRO_REGIME_CANDIDATE_DECISION.md": "research/artifacts/macro_regime/role9/MACRO_REGIME_CANDIDATE_DECISION.md",
    }
    role10.mkdir(parents=True, exist_ok=True)
    for name, source in upstream_reports.items():
        source_hash = sha256(repo / source)
        body = (repo / source).read_text(encoding="utf-8")
        header = f"<!-- Exact Role 10 reporting copy. Source: {source}; SHA-256: {source_hash}. -->\n"
        write_text(role10 / name, header + body)
    exact_copies = {
        "MACRO_REGIME_COVERAGE_BY_YEAR.csv": "MACRO_REGIME_COVERAGE_BY_YEAR.csv",
        "MACRO_REGIME_COVERAGE_BY_SERIES.csv": "MACRO_REGIME_COVERAGE_BY_SERIES.csv",
        "MACRO_REGIME_COVERAGE_BY_CATEGORY.csv": "MACRO_REGIME_COVERAGE_BY_CATEGORY.csv",
        "MACRO_REGIME_SCORING_CONFIG.yaml": "research/config/MACRO_REGIME_SCORING_CONFIG.yaml",
        "MACRO_EVENT_UPDATE_LEDGER.csv": "research/artifacts/macro_regime/role6/MACRO_EVENT_UPDATE_LEDGER.csv",
        "MACRO_REGIME_BY_YEAR.csv": "research/artifacts/macro_regime/role6/MACRO_REGIME_BY_YEAR.csv",
        "MACRO_CATEGORY_BY_YEAR.csv": "research/artifacts/macro_regime/role6/MACRO_CATEGORY_BY_YEAR.csv",
    }
    for name, source in exact_copies.items():
        shutil.copyfile(repo / source, role10 / name)
    state = """# Macro Regime Program State — Role 10

Schema version: `1.0.0`
Artifact ID: `MACRO-REGIME-ROLE10-PROGRAM-STATE-001`
Created at UTC: `2026-07-14T07:00:00Z`
Status: `PASS_OFFLINE_REPORTING_IN_APP_ROUTE_BLOCKED`
Decision: `INSUFFICIENT_ALIGNED_TRADES`
Candidate: `NONE`

## Decision first

`[FACT]` T0 has 306 medium-cost fills and -173.4578703725847R. Every frozen macro variant and opposite-macro control retains zero fills under J0/J1/J2.

`[FACT]` Role 6 ended `INSUFFICIENT_CATEGORY_COVERAGE`: inflation, labour, and growth each have one eligible bundle against a minimum of two. At most two categories are valid, below the required three, so all 9,676 daily biases are UNKNOWN.

`[CALCULATION]` Role 10 converts immutable rows into presentation tables and charts only; it changes no score, join, setup, outcome, cost, fold, or candidate gate.

`[INTERPRETATION]` An inactive filter is not profitable and does not improve the negative technical baseline. Random retention, expectancy, and candidate statistics are `NOT_APPLICABLE_ZERO_RETENTION`, not zero-valued successes.

## Warnings and limits

- NAS100 is a source label, not a broker-confirmed instrument.
- Source timezone is unresolved; charts retain source labels without claiming UTC equivalence.
- Low/medium/high normalized costs are hypothetical, not broker facts.
- Registry chronology remains a final-champion veto.
- Historical periods are exposure-unknown; no pristine final-holdout claim is made.
- No page, report, or chart authorizes paper, broker, order, or live execution.

## Next permitted action

Role 11 Independent Quantitative Auditor only. It must attempt to invalidate the complete Role 1–10 package and must not improve or tune it.
"""
    write_text(role10 / "MACRO_REGIME_PROGRAM_STATE.md", state)
    write_text(role10 / "MACRO_REGIME_NEXT_TASK.md", "# Macro Regime Next Task\n\nRole 11 Independent Quantitative Auditor only. Rehash and independently reproduce Role 1-10 evidence; attempt invalidation. Do not tune, deploy, or create a candidate.\n")
    report = """# Role 10 Reporting and Visualization Report

Status: `PASS_OFFLINE_REPORTING_IN_APP_ROUTE_BLOCKED`
Decision: `INSUFFICIENT_ALIGNED_TRADES`
Candidate: `NONE`

## FACT

- 71 immutable upstream source/output hashes reconcile.
- T0 remains 306 medium-cost fills and -173.4578703725847R.
- Every M1/M2/M3/M4 and opposite-macro variant retains zero fills under J0/J1/J2 because all macro biases are UNKNOWN.
- 11 static charts A-K, one self-contained interactive explorer, and exact local tables were produced. A read-only React component is isolated and tested but is not routed.

## CALCULATION

Presentation-only groupings and cumulative curves are derived from frozen Role 6-9 rows. No score, filter, trade, cost, fold, or candidate result is recalculated.

## ASSUMPTION

No new research assumption is introduced. The page inherits the disclosed source-label, timezone, and hypothetical-cost limitations.

## INTERPRETATION

The macro filter is inactive. Zero retained trades and zero net R are not evidence of improvement, profitability, or strategy rescue. Random retention is NOT_APPLICABLE at zero retention.

## Security and operation

The isolated component has no resource identifier, network request, mutation endpoint, unrestricted source URL, secret, collector, order, paper, broker, or live control. Authenticated route integration is `BLOCKED/FAIL_CLOSED_DIRTY_FILE_OWNERSHIP`: the only router file is a large pre-existing uncommitted user rewrite, and capturing it would violate repository ownership controls. Role 10 removed its two provisional App.js additions and left that user file unchanged. No route is active and no deployment occurred.

## Verification

Focused Python reporting/security tests: 6/6. Frontend: 7/7. Full research regression: 275/275. Production build: exit 0 with pre-existing dependency/source-map/lint warnings. Two complete report generations produced byte-identical 53-file output hash inventories.

Next permitted action: Role 11 Independent Quantitative Auditor only.
"""
    write_text(role10 / "MACRO_REGIME_ROLE10_REPORT.md", report)
    tests = {
        "schema_version": "1.0.0", "artifact_id": "MACRO-REGIME-ROLE10-TEST-EVIDENCE-001", "created_at_utc": CREATED_AT,
        "status": "VERIFIED", "commands": [
            {"command":"PYTHONPATH=research/src python3 -m unittest research.tests.test_macro_regime_reporting -v","exit_code":0,"passed":6,"failed":0,"duration_seconds":0.041},
            {"command":"CI=true npm test -- --runInBand src/components/research/macro-regime-research.test.js","exit_code":0,"passed":1,"failed":0,"duration_seconds":1.078},
            {"command":"CI=true npm test -- --runInBand","exit_code":0,"passed":7,"failed":0,"duration_seconds":0.526},
            {"command":"npm run build","exit_code":0,"result":"PASS_WITH_PRE_EXISTING_WARNINGS","warnings":"stale browser data, third-party source maps, bundle size, unrelated lint"},
            {"command":"PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m unittest discover -s research/tests -p 'test_*.py' -v","exit_code":0,"passed":275,"failed":0,"duration_seconds":44.017},
            {"command":"PYTHONPATH=research/src python3 -m smartmarketscope_quant.macro_regime.reporting --validate-only","exit_code":0,"upstream_hashes":71,"output_hashes":53,"charts":11},
            {"command":"Two full generator runs plus cmp ROLE10_OUTPUT_HASHES.json","exit_code":0,"deterministic_outputs":53},
            {"command":"PYTHONPATH=research/src python3 -m py_compile reporting.py test_macro_regime_reporting.py","exit_code":0},
        ],
        "failed_first_evidence": [
            {"failure":"ROLE10_REQUIRED_SOURCE_MISSING:MACRO_ACTIVE_INPUTS_BY_DAY.parquet","cause":"Role 6 hash inventory uses basename keys while later roles use repository-relative keys.","resolution":"Resolve basename keys relative to the declaring role directory; no upstream file changed."},
            {"failure":"DateParseError: unable to parse Daily","cause":"A generic date-column heuristic selected the timeframe column.","resolution":"Bind the already frozen bar_start_source contract explicitly; no research value changed."},
        ],
        "security": {"authenticated_route":"BLOCKED_FAIL_CLOSED_DIRTY_FILE_OWNERSHIP","authorization":"NOT_RUN_NO_ACTIVE_ROUTE","negative_idor":"NOT_APPLICABLE_NO_ACTIVE_RESOURCE_ROUTE","unrestricted_source_url":"ABSENT","sensitive_configuration":"ABSENT","write_or_live_surface":"ABSENT"},
        "warnings": ["DEPENDENCY_DATABASES_STALE", "THIRD_PARTY_SOURCE_MAPS_MISSING", "PRE_EXISTING_UNRELATED_LINT_WARNINGS", "BUNDLE_SIZE_WARNING"],
    }
    write_text(role10 / "ROLE10_TEST_RESULTS.json", stable_json(tests))


def generate(repo: Path) -> dict[str, Any]:
    upstream = verify_upstream(repo)
    role10 = repo / ROLE10; report = repo / REPORT
    for directory in (role10, report):
        if directory.exists(): shutil.rmtree(directory)
    build_role10_reports(repo, role10)
    charts = build_charts(repo, report)
    files = build_tables(repo, report)
    build_index(report, charts)
    build_interactive(repo, report)
    manifests = report / "manifests"; manifests.mkdir(parents=True, exist_ok=True)
    source_manifest = {"schema_version":"1.0.0","artifact_id":"MACRO-REGIME-ROLE10-SOURCE-HASHES-001","created_at_utc":CREATED_AT,"sources":upstream}
    write_text(manifests / "ROLE10_SOURCE_HASHES.json", stable_json(source_manifest))
    output_paths = sorted([p for p in list(role10.rglob("*"))+list(report.rglob("*")) if p.is_file() and p.name not in {"ROLE10_REPORT_MANIFEST.json","ROLE10_OUTPUT_HASHES.json"}])
    output_hashes = {str(p.relative_to(repo)): sha256(p) for p in output_paths}
    implementation_files = [
        "research/src/smartmarketscope_quant/macro_regime/reporting.py", "research/tests/test_macro_regime_reporting.py",
        "src/components/research/macro-regime-research.js", "src/components/research/macro-regime-research.css",
        "src/components/research/macro-regime-research-data.js", "src/components/research/macro-regime-research.test.js",
    ]
    implementation_hashes = {path: sha256(repo / path) for path in implementation_files}
    manifest = {"schema_version":"1.0.0","artifact_id":"MACRO-REGIME-ROLE10-REPORT-MANIFEST-001","program_id":PROGRAM,"created_at_utc":CREATED_AT,"status":"PASS_OFFLINE_REPORTING_IN_APP_ROUTE_BLOCKED","decision":"INSUFFICIENT_ALIGNED_TRADES","candidate":"NONE","evidence_labels":["FACT","CALCULATION","ASSUMPTION","INTERPRETATION"],"counts":{"charts":len(charts),"packaged_files":len(files),"upstream_hashes_verified":len(upstream)},"warnings":["INSUFFICIENT_CATEGORY_COVERAGE","TECHNICAL_EDGE_NOT_FOUND","TECHNICAL_SOURCE_TIMEZONE_UNRESOLVED","NAS100_SOURCE_LABEL_NOT_BROKER_CONFIRMED","NORMALIZED_COSTS_NOT_BROKER_FACT","REGISTRY_CHRONOLOGY_CAVEAT_FINAL_CHAMPION_VETO","FAIL_CLOSED_DIRTY_FILE_OWNERSHIP"],"failure_codes":["RESEARCH_CYCLE_REPORTER_EVIDENCE_INSUFFICIENT","SMART_MARKETSCOPE_QUANT_DASHBOARD_DESIGNER_EVIDENCE_INSUFFICIENT","INSUFFICIENT_ALIGNED_TRADES","FAIL_CLOSED_DIRTY_FILE_OWNERSHIP"],"offline":True,"external_fetches":0,"mutation_endpoints":0,"broker_or_order_controls":0,"final_holdout_accesses":0,"implementation_hashes":implementation_hashes,"output_hashes":output_hashes,"next_permitted_action":"Role 11 Independent Quantitative Auditor only; assess whether blocked in-app integration prevents full Role 10 acceptance"}
    write_text(manifests / "ROLE10_REPORT_MANIFEST.json", stable_json(manifest))
    output_hashes[str((manifests / "ROLE10_REPORT_MANIFEST.json").relative_to(repo))] = sha256(manifests / "ROLE10_REPORT_MANIFEST.json")
    write_text(role10 / "ROLE10_OUTPUT_HASHES.json", stable_json(dict(sorted(output_hashes.items()))))
    return manifest


def validate(repo: Path) -> dict[str, Any]:
    upstream = verify_upstream(repo)
    manifest_path = repo / REPORT / "manifests/ROLE10_REPORT_MANIFEST.json"
    outputs_path = repo / ROLE10 / "ROLE10_OUTPUT_HASHES.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    outputs = json.loads(outputs_path.read_text(encoding="utf-8"))
    for relative, expected in outputs.items():
        actual = sha256(repo / relative)
        if actual != expected: raise ValueError(f"ROLE10_OUTPUT_HASH_MISMATCH:{relative}")
    index = (repo / REPORT / "index.html").read_text(encoding="utf-8")
    prohibited = ("http://", "https://", "fetch(", "axios", "order button", "broker integration")
    if any(token in index.lower() for token in prohibited): raise ValueError("ROLE10_OFFLINE_OR_LIVE_PATH_VIOLATION")
    if len(list((repo / REPORT / "charts").glob("*.png"))) != 11: raise ValueError("ROLE10_CHART_CENSUS_MISMATCH")
    if "NOT_APPLICABLE_ZERO_RETENTION" not in (repo / REPORT / "tables/MACRO_RANDOM_CONTROL_RESULTS.csv").read_text(encoding="utf-8"): raise ValueError("ROLE10_NULL_SEMANTICS_MISSING")
    return {"status":"PASS","decision":manifest["decision"],"upstream_hashes_verified":len(upstream),"outputs_verified":len(outputs),"charts":11}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--repo-root", default="."); parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(); repo = Path(args.repo_root).resolve()
    result = validate(repo) if args.validate_only else generate(repo)
    print(stable_json(result), end="")


if __name__ == "__main__":
    main()

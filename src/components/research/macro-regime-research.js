import React from 'react';
import './macro-regime-research.css';
import { macroRegimeResearch as data } from './macro-regime-research-data';

const Metric = ({ label, value, className = '' }) => <article className="macro-research__card"><div>{label}</div><div className={`macro-research__value ${className}`}>{value}</div></article>;

const MacroRegimeResearch = () => (
  <main className="macro-research" data-testid="macro-regime-research">
    <header className="macro-research__header">
      <div className="macro-research__eyebrow">Read-only research · integration blocked</div>
      <h1>Macro regime evidence</h1>
      <p>{data.programId}</p>
      <p>As-of evidence: {data.asOf}. No current/live market claim.</p>
    </header>
    <section className="macro-research__warning" role="alert"><strong>{data.decision}.</strong> Candidate {data.candidate}. Coverage never produced three valid categories, so every bias is UNKNOWN and all macro variants retain zero trades. Inactivity is not success.</section>
    <div className="macro-research__grid">
      <Metric label="T0 medium net R" value={`${data.baseline.mediumR.toFixed(6)}R`} className="macro-research__bad" />
      <Metric label="T0 fills / no-fills" value={`${data.baseline.fills} / ${data.baseline.noFills}`} />
      <Metric label="Macro retained fills" value="0" className="macro-research__unknown" />
      <Metric label="Current bias" value={data.current.bias} className="macro-research__unknown" />
      <Metric label="Valid categories" value={data.current.validCategories} />
      <Metric label="Final score" value={data.current.finalScore} />
    </div>

    <section className="macro-research__section"><h2>Coverage and source health</h2><p>Requested {data.coverage.requested}; {data.coverage.observations.toLocaleString()} immutable observations and {data.coverage.dailyRows.toLocaleString()} daily as-of rows.</p><ul>{data.sourceHealth.map(([name, status]) => <li key={name}><strong>{name}:</strong> {status}</li>)}</ul></section>

    <section className="macro-research__section"><h2>Category capacity and current state</h2><div className="macro-research__table-scroll"><table><thead><tr><th>Category</th><th>Bundles</th><th>Score</th><th>Status</th></tr></thead><tbody>{data.categoryCapacity.map(row => <tr key={row.category}><td>{row.category}</td><td>{row.active} / {row.required} required</td><td>{row.score}</td><td>{row.status}</td></tr>)}</tbody></table></div><p>Stress: {data.current.stress} · Interaction: {data.current.interaction} · Base/final: NOT_APPLICABLE · Permission: {data.current.permission}</p></section>

    <section className="macro-research__section"><h2>Technical-only versus macro filters</h2><div className="macro-research__bars">{data.variants.map(([name, fills, netR, status]) => <div className="macro-research__bar" key={name}><span>{name}</span><div className="macro-research__track" aria-label={`${name}: ${fills} fills`}><div className="macro-research__fill" style={{ width: `${fills / data.baseline.fills * 100}%` }} /></div><span>{fills} fills · {netR.toFixed(3)}R · {status}</span></div>)}</div><p>J0 is headline. J1/J2 are sensitivities. Random retention is <strong>NOT_APPLICABLE_ZERO_RETENTION</strong>; it is not a zero-return distribution.</p></section>

    <section className="macro-research__section"><h2>Timeframes and confluence families remain separate</h2><ul>{data.strategies.map(([label, id]) => <li key={id}><strong>{label}</strong> — <code>{id}</code></li>)}</ul><p>Annual and expanding walk-forward macro rows are zero-trade in every fold. T0 is positive only in 2021 and negative overall. Full equity, drawdown, annual, category, and random-control evidence is in the offline package.</p></section>

    <section className="macro-research__section"><h2>Latest active indicator drill-down</h2><p>Raw source URLs are intentionally not exposed. Hashes provide immutable lineage.</p>{data.latestUpdates.map(([series, category, previous, current, change, indicator, bundle, categoryScore, reason, hash]) => <details key={series}><summary><strong>{series}</strong> · {category} · indicator {indicator}</summary><dl><dt>Raw observation / previous</dt><dd>{current} / {previous}</dd><dt>Transformation</dt><dd>One-release change: {change}</dd><dt>Scores</dt><dd>Indicator {indicator}; release bundle {bundle}; category {categoryScore}; final NOT_APPLICABLE; bias UNKNOWN</dd><dt>Reason / interaction</dt><dd>{reason}; interaction NONE</dd><dt>Effective policy</dt><dd>J0 +36h; latest evidence no later than {data.asOf}</dd><dt>Raw artifact SHA-256</dt><dd><code>{hash}</code></dd></dl></details>)}</section>

    <section className="macro-research__section"><h2>Warnings and access boundary</h2><ul>{data.warnings.map(warning => <li key={warning}><code>{warning}</code></li>)}</ul><p>The isolated component has no resource identifier, mutation request, collector URL, secret, order button, broker integration, paper control, or live path. Authenticated in-app route integration is fail-closed because the only router file contains unrelated uncommitted user changes that Role 10 is not permitted to capture.</p></section>
  </main>
);

export default MacroRegimeResearch;

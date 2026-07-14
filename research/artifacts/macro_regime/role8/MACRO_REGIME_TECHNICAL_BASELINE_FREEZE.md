# Macro Regime Technical Baseline Freeze

Status: `PASS_TECHNICAL_BASELINE_RECONCILED_AND_FROZEN`

The exact completed MLR technical evidence is frozen without rerunning the detector or changing a setup, fill, barrier, expiry, outcome, or cost field.

## Reconciliation

- Frozen setups: `454`.
- Setup/scenario rows: `1362`.
- Medium-cost fills / no-fills / invalid: `306` / `148` / `0`.
- Medium-cost wins / losses / timeouts / adverse-first ambiguities: `52` / `246` / `2` / `6`.
- Detector/config/source/artifact hashes are recorded in the manifest and on every Parquet row.
- Technical source timezone remains `UNRESOLVED`.

The upstream event registry did not emit a standalone H4 identifier. Role 8 therefore records a deterministic H4 lineage ID derived only from the frozen D1 event ID, direction, and H4 confirmation timestamp, and labels that origin explicitly. It does not regenerate an H4 event.

No technical source artifact was modified. No PnL-based selection, macro-filter return calculation, protected/final-holdout access, broker action, or deployment occurred.

# Macro Regime Role 7 Validation Evidence

Status: `PASS`

- Independent checks: `55`; errors: `0`; disclosed warnings: `2456`.
- Positive full-population checks cover hashes, revision lineage, exact J0 timing, DST-aware UTC/Kuala Lumpur conversion, atomic batches, all state transformations, all lineage levels, all three ledger formats, and every daily as-of row.
- Boundary fixtures cover exact z and aggregation thresholds, minimum history, DST, J1/J2 ordinal source dates, missing-calendar failure, zero-MAD standard-deviation fallback, zero-MAD-and-zero-STD insufficiency, and unscorable replacement.
- Negative/tamper tests are implemented in `research/tests/test_macro_regime_pit_validation.py` and fail closed on future timestamps, missing source-calendar dates, and output-hash mutation.
- `PYTHONPATH=research/src python3 -m unittest research.tests.test_macro_regime_pit_validation -v`: `12/12 PASS`, exit `0`.
- `PYTHONPATH=research/src python3 -m unittest discover -s research/tests -v`: `244/244 PASS`, exit `0`.
- `PYTHONPATH=research/src python3 -m smartmarketscope_quant.macro_regime.pit_validation --repo-root . --validate-only`: `PASS`, exit `0`.
- Empirical history contains no valid-to-unscorable transition and no standard-deviation fallback instance; those required semantics are therefore proven by frozen synthetic boundary fixtures rather than misrepresented as observed facts.

Limitations: the source is still labelled NAS100 without confirmed broker/feed identity. J1/J2 cannot be instantiated until Role 8 binds an exact source trading-date calendar. The registry chronology caveat remains a final-champion veto. PASS validates Role 6 construction only; it is not evidence of an edge, tradeability, or deployment readiness.

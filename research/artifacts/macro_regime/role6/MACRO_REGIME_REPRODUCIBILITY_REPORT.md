# Macro Regime Reproducibility Report

Status: `PASS_BYTE_DETERMINISTIC_VERIFIED_BY_FOCUSED_TEST`

- Config SHA-256: `dbbe0d01ac22bbc05aef8b7d3c44867ecf265fddf9e427a94bb4488d9e643f2d`
- Combined registry SHA-256: `7a9098c819481db4e38dfae42f0de6ff79bc209fa2dd21f7cd0a034c6aca7524`
- Scoring code SHA-256: `b13e60d93fcfee8d2609625341d532845248af7bfeffc0ab2f86dd1cc6029aef`
- Python: `3.11.7`
- Output formats: deterministic UTF-8 CSV/JSONL and PyArrow Parquet with fixed metadata, Zstandard compression, dictionary encoding disabled, statistics enabled, Parquet 2.6/data-page 2.0.
- Created timestamp is frozen at `2026-07-14T02:00:00Z`; no runtime timestamp or random seed enters output bytes.
- Focused Role 6 suite: `9/9` passed, including two complete real-input materializations and two tamper failures.
- Complete research regression suite: `232/232` passed.

Reproduction:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m smartmarketscope_quant.macro_regime.scoring --repo-root .
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m smartmarketscope_quant.macro_regime.scoring --repo-root . --validate-only
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=research/src python3 -m unittest research.tests.test_macro_regime_scoring -v
```

`ROLE6_OUTPUT_HASHES.json` records each named output. The focused integration test runs the complete real-input materialization twice in a disposable directory and requires every output byte hash to match.

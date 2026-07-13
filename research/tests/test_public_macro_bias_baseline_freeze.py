from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from smartmarketscope_quant.public_macro_bias.baseline_freeze import (
    BaselineFreezeError,
    canonical_hash,
    build_frozen_rows,
    read_csv,
    validate_final_manifest,
)


class PublicMacroBaselineFreezeTests(unittest.TestCase):
    def test_canonical_hash_is_order_invariant(self) -> None:
        self.assertEqual(canonical_hash({"a": 1, "b": 2}), canonical_hash({"b": 2, "a": 1}))

    def test_canonical_hash_changes_with_outcome(self) -> None:
        base = {"setup_id": "S1", "outcome": "WIN_2R"}
        changed = {"setup_id": "S1", "outcome": "LOSS_1R"}
        self.assertNotEqual(canonical_hash(base), canonical_hash(changed))

    def test_read_csv_preserves_blank_not_applicable_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "rows.csv"
            path.write_text("setup_id,gross_r\nS1,\n", encoding="ascii")
            self.assertEqual(read_csv(path), [{"setup_id": "S1", "gross_r": ""}])

    def test_final_manifest_rejects_changed_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "artifact.txt"
            artifact.write_text("original", encoding="ascii")
            manifest_root = root / "research/artifacts/macro_liquidity_reversal"
            manifest_root.mkdir(parents=True)
            expected = hashlib.sha256(artifact.read_bytes()).hexdigest()
            manifest = {
                "status": "TECHNICAL_EDGE_NOT_FOUND",
                "artifacts": {"artifact.txt": expected},
            }
            (manifest_root / "MLR_TECHNICAL_FINAL_MANIFEST.json").write_text(
                json.dumps(manifest), encoding="ascii"
            )
            artifact.write_text("changed", encoding="ascii")
            with self.assertRaisesRegex(BaselineFreezeError, "TECHNICAL_FINAL_MANIFEST_MISMATCH"):
                validate_final_manifest(root)

    def test_repository_baseline_rows_are_complete_and_hash_unique(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        rows = build_frozen_rows(repo_root)
        self.assertEqual(len(rows), 1362)
        self.assertEqual(len({row["setup_id"] for row in rows}), 454)
        self.assertEqual(len({row["setup_hash"] for row in rows}), 1362)
        self.assertEqual(len({row["trade_hash"] for row in rows}), 1362)
        for row in rows:
            self.assertTrue(row["planned_entry_points"])
            self.assertTrue(row["stop_reference_points"])
            self.assertTrue(row["target_2r_reference_points"])
            self.assertLessEqual(
                datetime.fromisoformat(row["source_actionable_timestamp"]),
                datetime.fromisoformat(row["technical_decision_timestamp"]),
            )
            if row["outcome"] == "NO_FILL":
                self.assertEqual(row["gross_r"], "")
                self.assertEqual(row["net_r"], "")


if __name__ == "__main__":
    unittest.main()

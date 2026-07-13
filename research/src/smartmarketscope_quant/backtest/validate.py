from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .config import load_execution_scenarios, load_prop_rule_scenarios
from .golden import run_golden_harness


class HarnessValidationError(RuntimeError):
    pass


def validate_harness(repo_root: Path, golden_path: Path) -> dict:
    expected = json.loads(golden_path.read_text(encoding="ascii"))
    actual = run_golden_harness(repo_root)
    for field in (
        "status",
        "code_checksum",
        "execution_config_checksum",
        "prop_config_checksum",
        "core_results_checksum",
        "core_results",
    ):
        if expected[field] != actual[field]:
            raise HarnessValidationError(f"Golden harness mismatch in {field}")
    if actual["status"] != "PASS":
        raise HarnessValidationError("Golden harness is not passing")

    execution = load_execution_scenarios(repo_root / "research/config/execution_scenarios.json")
    prop = load_prop_rule_scenarios(repo_root / "research/config/prop_scenarios.json")
    core = actual["core_results"]
    required_trade_reasons = {
        core["trades"]["winning_long"]["exit_reason"],
        core["trades"]["adverse_first_same_bar"]["exit_reason"],
        core["trades"]["gap_through_stop"]["exit_reason"],
    }
    if required_trade_reasons != {"TARGET", "STOP", "STOP_GAP"}:
        raise HarnessValidationError("Required execution outcomes are missing")
    if core["validation_interfaces"]["cpcv_identity_left"] != core["validation_interfaces"]["cpcv_identity_right"]:
        raise HarnessValidationError("CPCV coverage identity failed")

    return {
        "schema_version": "1.0.0",
        "artifact_id": "PHASE-F-VALIDATION-QRP-20260712",
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "PASS",
        "execution_scenarios_validated": len(execution),
        "prop_scenarios_validated": len(prop),
        "core_results_checksum": actual["core_results_checksum"],
        "checks": [
            "golden code/config/result checksums",
            "gross/cost/net reconciliation",
            "adverse-first same-bar outcome",
            "gap-open stop outcome",
            "long and short fixtures",
            "position sizing and margin fixture",
            "target/drawdown/timeout state paths",
            "walk-forward and purged K-fold interfaces",
            "CPCV split/path/coverage identities",
            "hypothetical-only scenario labels",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate deterministic Phase F golden evidence")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--golden",
        type=Path,
        default=Path("research/artifacts/validation_harness/golden_results.json"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    golden = args.golden if args.golden.is_absolute() else repo_root / args.golden
    result = validate_harness(repo_root, golden)
    content = json.dumps(result, indent=2, ensure_ascii=True) + "\n"
    if args.output:
        output = args.output if args.output.is_absolute() else repo_root / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="ascii")
    print(content, end="")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .frequency import _load_m1_windows


SOURCE_INDEX_SHA256 = "3654b47e1a9b715952747abaf2eb0e6df8fadb9e1f6262a8275168d5006c9b9e"
SOURCE_M1_SHA256 = "9ca414716a7c30b20006052af651d1f06f77ce23f62e7072feebd79896567f65"
SOURCE_D1_SHA256 = "2de323fa640b3afef2f32c4aad69309e6583848ab938e3920619bd1242510a75"
SOURCE_MANIFEST_SHA256 = "6241d1752c61b43a5b94904efc01da397b7d7d1183a28601e98ff29222c93558"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify(path: Path, expected: str) -> None:
    actual = _sha256(path)
    if actual != expected:
        raise RuntimeError(f"SOURCE_HASH_MISMATCH:{path}:{actual}")


def _chart_candles(frame: pd.DataFrame, start: str, end: str) -> list[dict[str, Any]]:
    interval_start = pd.Timestamp(start)
    interval_end = pd.Timestamp(end)
    selected = frame.loc[
        (frame["bar_start_source"] >= interval_start)
        & (frame["bar_start_source"] < interval_end)
    ]
    return [
        {
            "timestamp": row.bar_start_source.strftime("%Y-%m-%d %H:%M:%S"),
            "availableAt": row.available_at_source.strftime("%Y-%m-%d %H:%M:%S"),
            "open": float(row.open_completed),
            "high": float(row.high_completed),
            "low": float(row.low_completed),
            "close": float(row.close_completed),
            "eligibleWindow": True,
            "role": None,
        }
        for row in selected.itertuples(index=False)
    ]


def _d1_context_candles(
    frame: pd.DataFrame,
    candle1_start: str,
    frozen_swing_candles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return three completed predecessors plus the frozen C1/C2 evidence.

    The frozen parent candles are retained verbatim because they are the exact
    evidence used by the detector. Context is restricted to bars strictly
    before C1 so this presentation projection cannot introduce a later bar.
    """
    c1_start = pd.Timestamp(candle1_start)
    predecessors = frame.loc[frame["bar_start_source"] < c1_start].tail(3)
    context = [
        {
            "timestamp": row.bar_start_source.strftime("%Y-%m-%d %H:%M:%S"),
            "availableAt": row.available_at_source.strftime("%Y-%m-%d %H:%M:%S"),
            "open": float(row.open_completed),
            "high": float(row.high_completed),
            "low": float(row.low_completed),
            "close": float(row.close_completed),
            "eligibleWindow": False,
            "role": "CONTEXT",
        }
        for row in predecessors.itertuples(index=False)
    ]
    return context + [dict(candle) for candle in frozen_swing_candles]


def _load_daily_context(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, sep="\t")
    frame["bar_start_source"] = pd.to_datetime(frame["<DATE>"], format="%Y.%m.%d")
    frame["available_at_source"] = frame["bar_start_source"] + pd.Timedelta(days=1)
    frame.rename(
        columns={
            "<OPEN>": "open_completed",
            "<HIGH>": "high_completed",
            "<LOW>": "low_completed",
            "<CLOSE>": "close_completed",
        },
        inplace=True,
    )
    return frame.sort_values("bar_start_source").reset_index(drop=True)


def build_projection(repo_root: Path, output_dir: Path) -> dict[str, Any]:
    source_root = repo_root / "research/artifacts/m1_intrabar_h4_breaker_fvg"
    source_index_path = source_root / "index.json"
    source_manifest_path = source_root / "manifest.json"
    m1_path = repo_root / "dataset/NAS100_M1_200808060000_202606262354.csv"
    d1_path = repo_root / "dataset/NAS100_Daily_200808060000_202606260000.csv"
    _verify(source_index_path, SOURCE_INDEX_SHA256)
    _verify(source_manifest_path, SOURCE_MANIFEST_SHA256)
    _verify(m1_path, SOURCE_M1_SHA256)
    _verify(d1_path, SOURCE_D1_SHA256)

    source_index = json.loads(source_index_path.read_text(encoding="utf-8"))
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    events = source_index.get("sweeps", [])
    if len(events) != 658:
        raise RuntimeError(f"UNEXPECTED_PARENT_EVENT_COUNT:{len(events)}")

    requests = [
        {
            "actionable_time": event["h4WindowOpen"],
            "expiry_time": event["h4WindowExpiry"],
        }
        for event in events
    ]
    m1 = _load_m1_windows(m1_path, requests)
    d1 = _load_daily_context(d1_path)
    sweep_dir = output_dir / "sweeps"
    sweep_dir.mkdir(parents=True, exist_ok=True)

    summaries: list[dict[str, Any]] = []
    total_candles = 0
    empty_windows = 0
    insufficient_d1_context = 0
    for event in events:
        candles = _chart_candles(m1, event["h4WindowOpen"], event["h4WindowExpiry"])
        parent_detail_path = source_root / "sweeps" / f"{event['sweepHash']}.json"
        expected_parent_hash = source_manifest["files"][
            f"sweeps/{event['sweepHash']}.json"
        ]["sha256"]
        _verify(parent_detail_path, expected_parent_hash)
        parent_detail = json.loads(parent_detail_path.read_text(encoding="utf-8"))
        d1_context_candles = _d1_context_candles(
            d1,
            event["candle1Start"],
            parent_detail["candles"]["D1"],
        )
        total_candles += len(candles)
        empty_windows += int(not candles)
        insufficient_d1_context += int(len(d1_context_candles) < 5)
        payload = {
            "schemaVersion": "1.0.0",
            "artifactId": "MLR-M1-H4-WINDOW-REVIEW-001",
            "sourceExperimentId": source_index["experimentId"],
            "historicalOnly": True,
            "chartOnly": True,
            "executionAuthorized": False,
            "sweepHash": event["sweepHash"],
            "eventId": event["eventId"],
            "direction": event["direction"],
            "h4IntervalStart": event["h4WindowOpen"],
            "h4ActivationTime": event["h4ConfirmationTime"],
            "h4IntervalEnd": event["h4WindowExpiry"],
            "candleCount": len(candles),
            "candles": candles,
            "d1ContextCandleCount": len(d1_context_candles),
            "d1ContextCandles": d1_context_candles,
            "limitations": [
                "Display-only M1 evidence for the complete owning H4 interval.",
                "Three native Daily predecessor bars are presentation context only; frozen C1/C2 evidence is unchanged.",
                "No setup, entry, stop, target, fill, or outcome is inferred by this projection.",
                "Previously exposed source; not a pristine holdout.",
                "Source clock, broker identity, price side, spread, and contract terms remain unresolved.",
            ],
        }
        detail_path = sweep_dir / f"{event['sweepHash']}.json"
        detail_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        summaries.append(
            {
                "sweepHash": event["sweepHash"],
                "eventId": event["eventId"],
                "h4IntervalStart": event["h4WindowOpen"],
                "h4ActivationTime": event["h4ConfirmationTime"],
                "h4IntervalEnd": event["h4WindowExpiry"],
                "candleCount": len(candles),
                "d1ContextCandleCount": len(d1_context_candles),
            }
        )

    index = {
        "schemaVersion": "1.0.0",
        "artifactId": "MLR-M1-H4-WINDOW-REVIEW-001",
        "sourceExperimentId": source_index["experimentId"],
        "historicalOnly": True,
        "chartOnly": True,
        "executionAuthorized": False,
        "newTrialCount": 0,
        "parentEventCount": len(summaries),
        "detailCount": len(summaries),
        "totalCandleCount": total_candles,
        "emptyWindowCount": empty_windows,
        "insufficientD1ContextCount": insufficient_d1_context,
        "events": summaries,
        "inputs": {
            str(source_index_path.relative_to(repo_root)): {"sha256": SOURCE_INDEX_SHA256},
            str(source_manifest_path.relative_to(repo_root)): {"sha256": SOURCE_MANIFEST_SHA256},
            str(m1_path.relative_to(repo_root)): {"sha256": SOURCE_M1_SHA256},
            str(d1_path.relative_to(repo_root)): {"sha256": SOURCE_D1_SHA256},
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "artifactId": "MLR-M1-H4-WINDOW-REVIEW-MANIFEST-001",
        "sourceResultIndexSha256": SOURCE_INDEX_SHA256,
        "sourceResultManifestSha256": SOURCE_MANIFEST_SHA256,
        "sourceM1Sha256": SOURCE_M1_SHA256,
        "sourceD1Sha256": SOURCE_D1_SHA256,
        "indexSha256": _sha256(output_dir / "index.json"),
        "detailCount": len(summaries),
        "detailSha256": {
            path.stem: _sha256(path)
            for path in sorted(sweep_dir.glob("*.json"))
        },
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research/artifacts/m1_h4_window_review"),
    )
    arguments = parser.parse_args()
    repo_root = arguments.repo_root.resolve()
    output_dir = arguments.output_dir if arguments.output_dir.is_absolute() else repo_root / arguments.output_dir
    result = build_projection(repo_root, output_dir)
    print(json.dumps({
        "artifactId": result["artifactId"],
        "parentEventCount": result["parentEventCount"],
        "totalCandleCount": result["totalCandleCount"],
        "emptyWindowCount": result["emptyWindowCount"],
        "insufficientD1ContextCount": result["insufficientD1ContextCount"],
    }))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


CONFIG_PATH = Path("research/config/macro_regime_h6_pilot.json")
OUTPUT_DIR = Path("research/artifacts/macro_regime/role5")
MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "june": 6, "jul": 7, "july": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}


class CollectionValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ParsedValue:
    reference_date: str
    value: str
    raw_label: str


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def _month_number(raw: str) -> int:
    key = raw.lower().replace(".", "").strip()
    if key not in MONTHS:
        raise CollectionValidationError(f"Unknown H6 month label: {raw}")
    return MONTHS[key]


def _reference_date(label: str, prior_year: int | None = None) -> tuple[str, int]:
    cleaned = re.sub(r"\s+[per]+$", "", label.strip(), flags=re.I)
    full = re.search(r"([A-Za-z.]+)\s+(\d{4})", cleaned)
    if full:
        year = int(full.group(2))
        return date(year, _month_number(full.group(1)), 1).isoformat(), year
    old = re.search(r"(\d{4})-([A-Za-z.]+)", cleaned)
    if old:
        year = int(old.group(1))
        return date(year, _month_number(old.group(2)), 1).isoformat(), year
    month = re.fullmatch(r"([A-Za-z.]+)", cleaned)
    if month and prior_year is not None:
        return date(prior_year, _month_number(month.group(1)), 1).isoformat(), prior_year
    raise CollectionValidationError(f"Unparseable H6 reference label: {label}")


def parse_modern_table(raw: str) -> list[ParsedValue]:
    match = re.search(r"<table\b[^>]*\bid=[\"']t1tg1[\"'][^>]*>(.*?)</table>", raw, re.I | re.S)
    if not match:
        raise CollectionValidationError("Modern H6 Table 1 not found")
    rows: list[ParsedValue] = []
    prior_year: int | None = None
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", match.group(1), re.I | re.S):
        headers = re.findall(r"<th\b[^>]*>(.*?)</th>", row, re.I | re.S)
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.I | re.S)
        if not headers or len(cells) < 2:
            continue
        label = _text(headers[-1])
        try:
            reference, prior_year = _reference_date(label, prior_year)
        except CollectionValidationError:
            continue
        value = _text(cells[1]).replace(",", "")
        if not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
            raise CollectionValidationError(f"Invalid modern H6 M2 value: {value}")
        rows.append(ParsedValue(reference, value, label))
    if not rows:
        raise CollectionValidationError("Modern H6 Table 1 yielded no M2 rows")
    return rows


def parse_legacy_pre(raw: str) -> list[ParsedValue]:
    match = re.search(r"<pre\b[^>]*>(.*?)</pre>", raw, re.I | re.S)
    if not match:
        raise CollectionValidationError("Legacy H6 PRE Table 1 not found")
    text = html.unescape(match.group(1)).replace("\r", "")
    if "Table 1" not in text or "M2" not in text:
        raise CollectionValidationError("Legacy H6 Table 1 identity missing")
    lines = text.splitlines()
    rows: list[ParsedValue] = []
    prior_year: int | None = None
    started = False
    for line in lines:
        lower = line.lower()
        if started and ("percent change" in lower or lower.strip().startswith("not seasonally adjusted")):
            break
        if "seasonally adjusted" in lower and "not seasonally adjusted" in lower:
            # Later legacy releases place the SA and NSA headings on the same
            # line and then publish both pairs of columns in each data row.
            # The first two numeric columns remain M1 SA and M2 SA.
            started = True
            continue
        if "seasonally adjusted" in lower and "not seasonally" not in lower:
            started = True
            continue
        if not started:
            continue
        full = re.match(r"\s*(?:(\d{4})-)?([A-Za-z.]+)\s+(.+?)\s*$", line)
        if not full:
            continue
        year_text, month_text, tail = full.groups()
        if year_text:
            prior_year = int(year_text)
        if prior_year is None:
            continue
        numbers = re.findall(r"-?\d+(?:\.\d+)?", tail)
        if len(numbers) < 2:
            continue
        try:
            reference, _ = _reference_date(f"{prior_year}-{month_text}")
        except CollectionValidationError:
            continue
        rows.append(ParsedValue(reference, numbers[1], f"{prior_year}-{month_text}"))
    if not rows:
        raise CollectionValidationError("Legacy H6 Table 1 yielded no M2 rows")
    return rows


def parse_release(raw: bytes) -> tuple[str, str, list[ParsedValue]]:
    text = raw.decode("utf-8", errors="replace")
    release_match = re.search(r"Release Date:\s*</?[^>]*>?\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", text, re.I)
    if not release_match:
        release_match = re.search(r"Release Date:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", _text(text), re.I)
    if not release_match:
        release_match = re.search(r"Table 1[^\n]*\n\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", text, re.I)
    if not release_match:
        raise CollectionValidationError("Dated H6 release identity missing")
    release = datetime.strptime(release_match.group(1), "%B %d, %Y").date().isoformat()
    if re.search(r"<table\b[^>]*\bid=[\"']t1tg1[\"']", text, re.I):
        return release, "MODERN_HTML_TABLE", parse_modern_table(text)
    return release, "LEGACY_PRE", parse_legacy_pre(text)


def j0(release_date: str) -> tuple[str, str]:
    local = datetime.combine(date.fromisoformat(release_date), datetime.min.time(), ZoneInfo("America/New_York"))
    effective = local + timedelta(hours=36)
    return (
        effective.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        effective.astimezone(ZoneInfo("Asia/Kuala_Lumpur")).isoformat(),
    )


def _artifact_path(raw_root: Path, entry: dict[str, object]) -> Path | None:
    if entry.get("raw_body") is None and "body_name" not in entry:
        return None
    if entry["kind"] in {"ARCHIVE_INDEX", "RELEASE_DATE_INDEX"}:
        return raw_root / "vintage_year=2026" / f"source_run={entry['run_id']}" / str(entry["body_name"])
    release = re.search(r"/(\d{8})/", str(entry["url"]))
    if not release:
        raise CollectionValidationError(f"Release URL lacks dated identity: {entry['url']}")
    return raw_root / f"vintage_year={release.group(1)[:4]}" / f"source_run={entry['run_id']}" / str(entry["body_name"])


def build(repo_root: Path) -> dict[str, bytes]:
    config = json.loads((repo_root / CONFIG_PATH).read_text(encoding="ascii"))
    if config["actual_request_count"] != config["request_ceiling"]:
        raise CollectionValidationError("Pilot must stop exactly at the frozen request ceiling")
    if config["concurrency"] != 1 or config["retry_count"] != 0:
        raise CollectionValidationError("Sequential/no-retry pilot invariant failed")
    raw_root = Path(config["raw_root"])
    allowlisted = json.loads((repo_root / "research/config/macro_regime_source_audit.json").read_text(encoding="ascii"))
    route = next(item for item in allowlisted["candidates"] if item["route_id"] == config["route_id"])
    if route["source_decision"] != config["source_decision_required"]:
        raise CollectionValidationError("H6 route is not in the frozen bounded allowlist")

    runs: list[dict[str, object]] = []
    artifacts: list[dict[str, object]] = []
    parsed: list[dict[str, object]] = []
    parser_formats: dict[str, str] = {}
    for entry in sorted(config["request_ledger"], key=lambda item: item["ordinal"]):
        path = _artifact_path(raw_root, entry)
        run = {
            "source_run_id": entry.get("run_id", "role5-access-0001"),
            "ordinal": entry["ordinal"], "route_id": config["route_id"], "url": entry["url"],
            "status": entry["status"], "attempt_count": 1, "retry_count": 0,
            "contains_secrets": False, "checkpoint": f"REQUEST_{entry['ordinal']}_OF_{config['request_ceiling']}",
        }
        if path is not None:
            if not path.is_file() or raw_root not in path.parents:
                raise CollectionValidationError(f"Missing or unsafe raw artifact: {path}")
            raw = path.read_bytes()
            if not raw or b"captcha" in raw.lower():
                raise CollectionValidationError(f"Empty/CAPTCHA raw artifact: {path}")
            header_path = path.with_name("headers.txt")
            header_raw = header_path.read_bytes()
            artifact = {
                "raw_artifact_id": f"{run['source_run_id']}-body", "source_run_id": run["source_run_id"],
                "relative_private_path": str(path.relative_to(raw_root)), "byte_length": len(raw),
                "sha256": sha256_bytes(raw), "header_byte_length": len(header_raw),
                "header_sha256": sha256_bytes(header_raw), "source_url": entry["url"],
            }
            artifacts.append(artifact)
            run.update({"raw_payload_sha256": artifact["sha256"], "byte_length": len(raw)})
            if entry["kind"] == "PILOT_RELEASE":
                release, format_name, values = parse_release(raw)
                if release.replace("-", "") not in str(entry["url"]):
                    raise CollectionValidationError("Release date does not match dated archive URL")
                if release > config["cutoff_release_date"]:
                    raise CollectionValidationError("Post-cutoff release detected")
                parser_formats[release] = format_name
                effective_utc, effective_my = j0(release)
                for value in values:
                    if config["requested_start_date"] <= value.reference_date <= config["requested_end_date"]:
                        parsed.append({
                            "route_id": config["route_id"], "source_run_id": run["source_run_id"],
                            "raw_artifact_id": artifact["raw_artifact_id"], "source_series_id": "H6/M2SL",
                            "internal_indicator_id": "US_M2_MONEY_STOCK_SA", "category": "LIQUIDITY",
                            "release_bundle": "MONEY_SUPPLY_BUNDLE", "reference_date": value.reference_date,
                            "vintage_date": release, "raw_value": value.value, "normalized_numeric_value": value.value,
                            "unit": config["unit"], "frequency": config["frequency"],
                            "seasonal_adjustment": config["seasonal_adjustment"], "raw_label": value.raw_label,
                            "availability_date": release, "effective_at_utc": effective_utc,
                            "effective_at_asia_kuala_lumpur": effective_my,
                            "availability_rule": config["availability_rule"], "parser_format": format_name,
                            "point_in_time_classification": "SOURCE_VERSION_UNRESOLVED",
                            "protocol_eligibility": "INELIGIBLE_PILOT_SPARSE_REVISION_CHAIN",
                            "historical_reconstruction": True, "raw_artifact_sha256": artifact["sha256"],
                        })
        runs.append(run)

    parsed.sort(key=lambda row: (row["reference_date"], row["vintage_date"], row["source_run_id"]))
    previous_by_reference: dict[str, str] = {}
    versions: dict[str, int] = {}
    for row in parsed:
        reference = str(row["reference_date"])
        versions[reference] = versions.get(reference, -1) + 1
        row["pilot_version_number"] = versions[reference]
        row["supersedes_pilot_observation_id"] = previous_by_reference.get(reference)
        identity = f"H6-M2-{reference}-{row['vintage_date']}-{versions[reference]}"
        row["pilot_observation_id"] = identity
        previous_by_reference[reference] = identity
        row["version_kind"] = "FIRST_SEEN_IN_SPARSE_PILOT" if versions[reference] == 0 else "LATER_SPARSE_PILOT_SNAPSHOT"
        row["observation_payload_sha256"] = sha256_bytes(canonical_json(row))

    release_index_path = _artifact_path(raw_root, config["request_ledger"][2])
    release_dates = json.loads(release_index_path.read_text(encoding="utf-8"))
    eligible_dates = sorted(
        datetime.strptime(value[:8], "%Y%m%d").date().isoformat()
        for year in release_dates for month in year["Months"] for value in month["Dates"]
        if "20000101" <= value[:8] <= "20260628"
    )
    collected_dates = sorted(parser_formats)
    missing_dates = sorted(set(eligible_dates) - set(collected_dates))

    def csv_bytes(rows: list[dict[str, object]], fields: list[str]) -> bytes:
        from io import StringIO
        stream = StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)
        return stream.getvalue().encode("ascii")

    artifact_fields = ["raw_artifact_id", "source_run_id", "relative_private_path", "byte_length", "sha256", "header_byte_length", "header_sha256", "source_url"]
    observation_fields = list(parsed[0]) if parsed else []
    source_runs = b"".join(canonical_json(run) for run in runs)
    raw_manifest = {
        "schema_version": "1.0.0", "private_raw_root": str(raw_root), "new_source_run_count": len(runs),
        "successful_raw_artifact_count": len(artifacts), "failed_attempt_count": sum("404" in str(run["status"]) for run in runs),
        "artifacts": artifacts,
    }
    normalized_manifest = {
        "schema_version": "1.0.0", "route_id": config["route_id"], "parser_version": config["parser_version"],
        "parsed_sparse_version_count": len(parsed), "eligible_observation_count": 0,
        "classification": "SOURCE_VERSION_UNRESOLVED", "parser_formats": parser_formats,
        "reference_start": min((row["reference_date"] for row in parsed), default=None),
        "reference_end": max((row["reference_date"] for row in parsed), default=None),
        "vintage_start": min(collected_dates), "vintage_end": max(collected_dates),
        "missing_release_count": len(missing_dates), "expected_release_count": len(eligible_dates),
    }
    checkpoint = {
        "status": "STOPPED_AT_FROZEN_PILOT_CEILING", "last_request_ordinal": config["request_ceiling"],
        "last_release_date": max(collected_dates), "full_traversal_started": False, "h41_started": False,
        "resume_policy": "New append-only source run; verify cached raw hashes; traverse remaining dated identities in chronological order",
        "dead_letter": [{"ordinal": 1, "error": "HTTP_404_ROBOTS_METADATA", "retryable": False}],
    }
    missing_rows = [{"release_date": item, "status": "NOT_REQUESTED_FROZEN_PILOT_CEILING"} for item in missing_dates]
    coverage_rows = []
    for year in range(2000, 2027):
        year_rows = [row for row in parsed if str(row["reference_date"]).startswith(str(year))]
        coverage_rows.append({
            "year": year, "category": "LIQUIDITY", "route_id": config["route_id"],
            "sparse_pilot_versions": len(year_rows), "eligible_versions": 0,
            "classification": "SOURCE_VERSION_UNRESOLVED" if year_rows else "NOT_COLLECTED",
        })

    outputs = {
        "ROLE5_MACRO_SOURCE_RUNS.jsonl": source_runs,
        "ROLE5_MACRO_RAW_ARTIFACT_MANIFEST.csv": csv_bytes(artifacts, artifact_fields),
        "ROLE5_MACRO_OBSERVATION_PILOT.csv": csv_bytes(parsed, observation_fields),
        "ROLE5_RAW_MANIFEST.json": canonical_json(raw_manifest),
        "ROLE5_NORMALIZED_MANIFEST.json": canonical_json(normalized_manifest),
        "ROLE5_SOURCE_HEALTH_CHECKPOINT.json": canonical_json(checkpoint),
        "ROLE5_H6_MISSING_RELEASES.csv": csv_bytes(missing_rows, ["release_date", "status"]),
        "ROLE5_COVERAGE_BY_YEAR.csv": csv_bytes(coverage_rows, ["year", "category", "route_id", "sparse_pilot_versions", "eligible_versions", "classification"]),
    }
    report = f"""# Role 5 Historical Macro Data Collector Report

Status: `INCONCLUSIVE_PARTIAL_H6_PILOT_REVISION_CHAIN_INCOMPLETE`  
Decision: `STOP_BEFORE_FULL_H6_TRAVERSAL_AND_ROLE6`

## Decision

`[FACT]` Phase A passed against disposable MariaDB 10.4.28: 11 tables, 28 triggers, 70/70 target-driver Laravel tests, populated rollback refusal, clean empty rollback, and idempotent reapply. The isolated server and datadir were deleted.

`[FACT]` Phase B made exactly {config['actual_request_count']} sequential requests at concurrency one: one robots metadata 404 with no retry, one H.6 index, one official `releaseDates.json`, and seven dated H.6 releases spanning 2000, 2012, the 2020/2021 weekly-to-monthly transition, a seasonal-revision release, and 2026. There were zero retries, 403s, 429s, CAPTCHAs, redirects outside the official host, H.4.1 requests, experiments, holdout accesses, scores, joins, or PnL calculations.

`[FACT]` The parser successfully extracted {len(parsed)} seasonally adjusted monthly M2 snapshot values in billions of dollars across `LEGACY_PRE` and `MODERN_HTML_TABLE`. Requested-range reference coverage in the sparse pilot is {normalized_manifest['reference_start']} through {normalized_manifest['reference_end']}; dated release coverage is {normalized_manifest['vintage_start']} through {normalized_manifest['vintage_end']}.

`[INTERPRETATION]` These are parse-valid sparse snapshots, not a complete immutable H.6 revision ledger. The official index exposes {len(eligible_dates)} dated releases in range; {len(missing_dates)} were deliberately not requested when the frozen pilot ceiling was reached. Assigning true first-print/revision numbers from seven non-contiguous releases would fabricate lineage. Therefore all {len(parsed)} parsed versions are `SOURCE_VERSION_UNRESOLVED` and ineligible; verified LIQUIDITY remains zero.

`[ASSUMPTION]` A future continuation may reuse every cached body only after hash verification and collect the {len(missing_dates)} remaining dated identities under a prospectively approved ceiling. It must freeze full traversal, checkpoint, and revision semantics before requests resume.

## Existing plus new lineage counts

- Retained Role 2 source runs/raw artifacts/eligible observations: `25 / 25 / 1730`.
- New Role 5 terminal request attempts/successful raw bodies: `{len(runs)} / {len(artifacts)}`.
- Combined identity counts: `{25 + len(runs)} source runs / {25 + len(artifacts)} raw artifacts`.
- New parse-valid sparse H.6 versions: `{len(parsed)}`; new eligible H.6 versions: `0`.
- Combined eligible observations remain `1730`; LIQUIDITY remains `0`.

## Failure and stop evidence

- `HTTP_404_ROBOTS_METADATA`: recorded once; terminal, no retry, not an explicit access block.
- `H6_SPARSE_PILOT_REVISION_CHAIN_INCOMPLETE`: {len(missing_dates)} dated releases uncollected.
- `SOURCE_VERSION_UNRESOLVED`: true first-print/correction/revision ordering cannot be certified from sparse snapshots.
- The full traversal and H.4.1 gates did not open. Role 6 scoring is blocked because no eligible LIQUIDITY observation was added.

## Exact next permitted action

Continue Role 5, not Role 6: prospectively freeze a capacity-approved ceiling of at least {len(missing_dates)} remaining H.6 dated requests, resume chronologically from the official release index with cached-body hash reuse, reconstruct the complete reference-date revision chain, independently validate it, and only then consider H.4.1. Do not score, align, or inspect PnL before that gate passes.
""".encode("ascii")
    outputs["MACRO_REGIME_ROLE5_COLLECTION_REPORT.md"] = report
    return outputs


def write_outputs(repo_root: Path, outputs: dict[str, bytes], validate_only: bool) -> None:
    target = repo_root / OUTPUT_DIR
    if validate_only:
        for name, content in outputs.items():
            if (target / name).read_bytes() != content:
                raise CollectionValidationError(f"Output mismatch: {name}")
        return
    target.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        temporary = target / f".{name}.tmp"
        with temporary.open("wb") as handle:
            handle.write(content); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, target / name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    outputs = build(args.repo_root.resolve())
    write_outputs(args.repo_root.resolve(), outputs, args.validate_only)
    print(json.dumps({"status": "PASS_PARTIAL_PILOT", "outputs": len(outputs)}, sort_keys=True))


if __name__ == "__main__":
    main()

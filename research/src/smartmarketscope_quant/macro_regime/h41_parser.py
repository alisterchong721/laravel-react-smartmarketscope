from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime

from .historical_collector import CollectionValidationError


@dataclass(frozen=True)
class H41Snapshot:
    release_date: str
    reference_date: str
    total_assets_millions: int
    reserve_balances_millions: int
    treasury_general_account_millions: int
    parser_format: str


def clean(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def parse_date(value: str) -> str:
    normalized = re.sub(r"\bSept\.?\b", "Sep", value).replace(".", "")
    for pattern in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(normalized, pattern).date().isoformat()
        except ValueError:
            continue
    raise CollectionValidationError(f"Unparseable H41 date: {value}")


def number(value: str) -> int:
    normalized = value.replace(",", "").replace("$", "").strip()
    if not re.fullmatch(r"-?\d+", normalized):
        raise CollectionValidationError(f"Invalid H41 numeric cell: {value}")
    return int(normalized)


def numeric_tokens(line: str) -> list[str]:
    return re.findall(r"\([0-9][0-9,]*\)|-?[0-9][0-9,]*", line)


def row_value_last(lines: list[str], label: str) -> int:
    pattern = re.compile(rf"^\s*{label}(?:\s*\(\d+\))?\s+", re.I)
    for line in lines:
        if pattern.search(line):
            tokens = numeric_tokens(line)
            if len(tokens) < 2:
                raise CollectionValidationError(f"H41 row lacks expected columns: {label}")
            return number(tokens[-1])
    raise CollectionValidationError(f"H41 row missing: {label}")


def total_assets_legacy(lines: list[str]) -> int:
    for line in lines:
        if re.match(r"^\s*Total assets\s+", line, re.I):
            tokens = numeric_tokens(line)
            current = next((token for token in tokens if not token.startswith("(")), None)
            if current is None:
                raise CollectionValidationError("H41 total-assets row lacks current value")
            return number(current)
    raise CollectionValidationError("H41 total-assets row missing")


def table_rows(raw: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for fragment in re.findall(r"<tr\b[^>]*>(.*?)</tr>", raw, re.I | re.S):
        cells = [clean(cell) for cell in re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", fragment, re.I | re.S)]
        if cells:
            rows.append(cells)
    return rows


def modern_row_last(rows: list[list[str]], label: str) -> int:
    for cells in rows:
        if cells[0].lower() == label.lower() and len(cells) == 5:
            return number(cells[-1])
    raise CollectionValidationError(f"Modern H41 row missing: {label}")


def modern_total_assets(rows: list[list[str]]) -> int:
    for cells in rows:
        if cells[0].lower() != "total assets" or len(cells) != 5:
            continue
        for cell in cells[1:]:
            if re.fullmatch(r"\([0-9,]+\)", cell):
                continue
            if re.fullmatch(r"[0-9][0-9,]*", cell):
                return number(cell)
    raise CollectionValidationError("Modern H41 consolidated total-assets row missing")


def parse_h41(raw: bytes) -> H41Snapshot:
    source = raw.decode("utf-8", errors="replace").replace("\r", "")
    flattened = clean(source)
    release_match = re.search(r"Release Date:\s*([A-Za-z.]+\s+\d{1,2},\s+\d{4})", flattened, re.I)
    if not release_match:
        release_match = re.search(r"For Release at.*?([A-Za-z.]+\s+\d{1,2},\s+\d{4})", flattened, re.I)
    if not release_match:
        release_match = re.search(
            r"Condition Statement of Federal Reserve Banks\s+([A-Za-z.]+\s+\d{1,2},\s+\d{4})\s+1\.",
            flattened,
            re.I,
        )
    if not release_match:
        raise CollectionValidationError("H41 release date missing")
    release_date = parse_date(release_match.group(1))

    reference_match = re.search(
        r"Wednesday.{0,350}?([A-Za-z.]+\s+\d{1,2},\s+\d{4})",
        flattened,
        re.I,
    )
    if not reference_match:
        raise CollectionValidationError("H41 Wednesday reference date missing")
    reference_date = parse_date(reference_match.group(1))

    rows = table_rows(source)
    if any(cells and cells[0].lower() == "reserve balances with federal reserve banks" for cells in rows):
        parser_format = "MODERN_HTML_TABLE"
        reserve = modern_row_last(rows, "Reserve balances with Federal Reserve Banks")
        tga = modern_row_last(rows, "U.S. Treasury, General Account")
        total = modern_total_assets(rows)
    else:
        parser_format = "LEGACY_PRE"
        lines = [html.unescape(re.sub(r"<[^>]+>", " ", line)) for line in source.splitlines()]
        reserve = row_value_last(lines, r"Reserve balances with Federal Reserve Banks")
        tga = row_value_last(lines, r"U\.S\. Treasury, [Gg]eneral [Aa]ccount")
        total = total_assets_legacy(lines)

    if not (-total <= reserve <= total and 0 <= tga <= total and total > 0):
        raise CollectionValidationError("H41 balance-sheet magnitude invariant failed")
    return H41Snapshot(release_date, reference_date, total, reserve, tga, parser_format)

from __future__ import annotations

import hashlib
import io
import re

from pypdf import PdfReader


VALIDATOR_VERSION = "H6_PDF_EXACT_20161118_PYPDF_6_10_0_V1"


class ExactPdfValidationError(RuntimeError):
    pass


def validate_exact_20161118(
    raw: bytes,
    required_body_sha256: str,
    required_text_sha256: str,
) -> dict[str, object]:
    if hashlib.sha256(raw).hexdigest() != required_body_sha256 or not raw.startswith(b"%PDF-"):
        raise ExactPdfValidationError("Exact PDF body identity/signature mismatch")
    reader = PdfReader(io.BytesIO(raw), strict=True)
    if reader.is_encrypted or len(reader.pages) != 8:
        raise ExactPdfValidationError("Exact PDF encryption/page-count mismatch")
    page_text = [page.extract_text() or "" for page in reader.pages]
    extracted = "\n\f\n".join(page_text).replace("\r\n", "\n").replace("\r", "\n")
    text_sha256 = hashlib.sha256(extracted.encode("utf-8")).hexdigest()
    if text_sha256 != required_text_sha256:
        raise ExactPdfValidationError("Exact PDF extracted-text hash mismatch")
    normalized_for_matching = re.sub(r"\s+", " ", extracted).strip()
    required_patterns = {
        "release_date": r"November\s+17,\s+2016",
        "table_1_glyph_split": r"T\s*able\s+1",
        "money_stock": r"Money\s+Stock\s+Measures",
        "billions_of_dollars": r"Billions\s+of\s+dollars",
        "seasonally_adjusted": r"Seasonally\s+adjusted",
        "m1": r"\bM1\b",
        "m2": r"\bM2\b",
    }
    missing = [name for name, pattern in required_patterns.items() if not re.search(pattern, normalized_for_matching, re.I)]
    if missing:
        raise ExactPdfValidationError(f"Exact PDF semantic evidence missing: {','.join(missing)}")
    return {
        "validator_version": VALIDATOR_VERSION,
        "extraction_mode": "PYPDF_DEFAULT_PAGE_EXTRACT_TEXT",
        "page_join": "LF_FF_LF",
        "normalization": "CRLF_AND_CR_TO_LF_ONLY_UTF8",
        "page_count": len(reader.pages),
        "extracted_text_sha256": text_sha256,
        "release_date": "2016-11-17",
        "table_1_identified": True,
        "m1_m2_identified": True,
        "seasonally_adjusted_identified": True,
        "billions_of_dollars_identified": True,
    }

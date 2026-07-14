from __future__ import annotations

import hashlib
import io
import re

from pypdf import PdfReader


VALIDATOR_VERSION = "H6_PDF_PYPDF_6_10_0_V1"


class PdfValidationError(RuntimeError):
    pass


def validate_h6_pdf(raw: bytes, required_release_date: str) -> dict[str, object]:
    if not raw.startswith(b"%PDF-"):
        raise PdfValidationError("PDF signature missing")
    reader = PdfReader(io.BytesIO(raw), strict=True)
    if reader.is_encrypted:
        raise PdfValidationError("Encrypted PDF is not admissible")
    pages = [page.extract_text(extraction_mode="layout") or "" for page in reader.pages]
    text = "\n\f\n".join(pages)
    normalized = re.sub(r"\s+", " ", text).strip()
    required_patterns = {
        "release_date": re.escape(required_release_date),
        "table_1": r"Table\s+1",
        "m2": r"\bM2\b",
        "money_stock": r"MONEY\s+STOCK",
        "billions_of_dollars": r"Billions\s+of\s+dollars",
        "seasonally_adjusted": r"Seasonally\s+adjusted",
    }
    missing = [name for name, pattern in required_patterns.items() if not re.search(pattern, normalized, re.I)]
    if missing:
        raise PdfValidationError(f"Required H6 PDF text missing: {','.join(missing)}")
    return {
        "validator_version": VALIDATOR_VERSION,
        "page_count": len(reader.pages),
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "normalized_text_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "release_date": required_release_date,
        "table_1_identified": True,
        "m2_identified": True,
        "seasonally_adjusted_identified": True,
        "billions_of_dollars_identified": True,
    }

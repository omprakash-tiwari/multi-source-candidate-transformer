"""Date normalization.

Experience dates are normalized to ``YYYY-MM``. We refuse to invent a month:
a year-only token returns ``None`` for the month form (use ``normalize_year``
to capture the year as an int, e.g. for education ``end_year``). Parsing is
fully explicit/deterministic -- no locale-dependent libraries.
"""
from __future__ import annotations

import re
from typing import Optional

PRESENT_TOKENS = {
    "present", "current", "now", "ongoing", "till date", "to date",
    "till now", "currently",
}

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def normalize_month(raw: object) -> Optional[str]:
    """Return ``YYYY-MM`` or ``None``. ``None`` also represents "ongoing"."""
    if raw is None:
        return None
    text = str(raw).strip().strip(",.")
    if not text:
        return None
    if text.lower() in PRESENT_TOKENS:
        return None

    # YYYY-MM / YYYY/MM / YYYY-MM-DD
    m = re.match(r"^(\d{4})[-/](\d{1,2})(?:[-/]\d{1,2})?$", text)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        return f"{year:04d}-{month:02d}" if 1 <= month <= 12 else None

    # MM/YYYY or M-YYYY
    m = re.match(r"^(\d{1,2})[-/](\d{4})$", text)
    if m:
        month, year = int(m.group(1)), int(m.group(2))
        return f"{year:04d}-{month:02d}" if 1 <= month <= 12 else None

    # "Mar 2021" / "March 2021"
    m = re.match(r"^([A-Za-z]{3,9})\.?\s+(\d{4})$", text)
    if m:
        month = _MONTHS.get(m.group(1).lower())
        if month:
            return f"{int(m.group(2)):04d}-{month:02d}"
        return None

    # Year-only: we will NOT fabricate a month.
    return None


def normalize_year(raw: object) -> Optional[int]:
    """Best-effort 4-digit year as an int (for education end_year)."""
    if raw is None:
        return None
    m = re.search(r"(?:19|20)\d{2}", str(raw))
    return int(m.group(0)) if m else None

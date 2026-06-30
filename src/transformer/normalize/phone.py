"""Phone normalization to E.164.

We only ever emit a number that `phonenumbers` can both parse AND validate.
If we cannot, we return ``None`` -- an honestly-empty phone beats a
wrong-but-confident one. National-format numbers need a region hint; callers
pass the candidate's country when known, otherwise we assume the export's
default region (documented assumption).
"""
from __future__ import annotations

from typing import Optional

import phonenumbers

DEFAULT_REGION = "US"


def normalize_phone(raw: object, default_region: str = DEFAULT_REGION) -> Optional[str]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None

    # If it carries an explicit international prefix, parse without a region.
    region = None if text.startswith("+") else (default_region or DEFAULT_REGION)
    try:
        parsed = phonenumbers.parse(text, region)
    except phonenumbers.NumberParseException:
        return None

    if not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

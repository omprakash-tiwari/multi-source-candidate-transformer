"""Country normalization to ISO-3166 alpha-2.

Uses ``pycountry`` for the heavy lifting plus a small alias table for the
informal names people actually type (USA, UK, England, ...). Unknown -> None.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

import pycountry

# Informal names pycountry does not resolve on its own.
_ALIASES = {
    "usa": "US", "u.s.a": "US", "u.s.a.": "US", "u.s": "US", "u.s.": "US",
    "us": "US", "united states of america": "US", "america": "US",
    "uk": "GB", "u.k": "GB", "u.k.": "GB", "england": "GB", "scotland": "GB",
    "wales": "GB", "britain": "GB", "great britain": "GB",
    "uae": "AE", "south korea": "KR", "north korea": "KP", "russia": "RU",
}


@lru_cache(maxsize=512)
def normalize_country(raw: object) -> Optional[str]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None

    low = text.lower().strip(".")
    if low in _ALIASES:
        return _ALIASES[low]

    if len(text) == 2 and text.isalpha():
        match = pycountry.countries.get(alpha_2=text.upper())
        if match:
            return match.alpha_2

    try:
        return pycountry.countries.lookup(text).alpha_2
    except LookupError:
        return None

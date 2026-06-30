"""Name / company normalization and the keys used by entity resolution."""
from __future__ import annotations

import re
from typing import Optional

# Generic company suffixes/words stripped so "Acme Corp" == "Acme Corporation".
_COMPANY_SUFFIXES = {
    "inc", "corp", "corporation", "ltd", "limited", "llc", "co", "company",
    "gmbh", "plc", "group", "holdings", "technologies", "technology", "labs",
    "systems", "solutions", "the",
}


def normalize_name(raw: object) -> Optional[str]:
    if not raw:
        return None
    text = re.sub(r"\s+", " ", str(raw)).strip()
    return text or None


def name_key(raw: object) -> Optional[str]:
    """Lowercased, punctuation-stripped name used as a weak match key."""
    name = normalize_name(raw)
    if not name:
        return None
    key = re.sub(r"[^a-z ]", "", name.lower())
    key = re.sub(r"\s+", " ", key).strip()
    return key or None


def company_key(raw: object) -> Optional[str]:
    """Normalized company token used to match experience entries across sources."""
    if not raw:
        return None
    text = re.sub(r"[^a-z0-9 ]", " ", str(raw).lower())
    tokens = [t for t in text.split() if t and t not in _COMPANY_SUFFIXES]
    return " ".join(tokens) or None

"""Skill canonicalization.

Strategy: exact alias/canonical hit first (confidence 1.0), then a fuzzy
fallback against the alias dictionary (confidence = match score). If nothing
clears the threshold the *original* token is kept verbatim at reduced
confidence and flagged non-canonical -- we preserve what the source actually
said rather than invent or drop it. The dictionary lives in data/skills and is
editable without touching code.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple, Optional

from rapidfuzz import fuzz, process

_DEFAULT_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "skills" / "skill_aliases.json"
)


class SkillMatch(NamedTuple):
    name: str
    confidence: float   # match certainty in [0, 1]
    canonical: bool     # True if resolved to a dictionary entry


class SkillIndex(NamedTuple):
    choices: list[str]                 # all searchable forms (normalized)
    choice_to_canon: dict[str, str]    # normalized form -> canonical name


def _norm(text: object) -> str:
    return re.sub(r"\s+", " ", str(text).strip().lower())


@lru_cache(maxsize=8)
def load_skill_index(path: Optional[str] = None) -> SkillIndex:
    src = Path(path) if path else _DEFAULT_PATH
    raw = json.loads(src.read_text(encoding="utf-8"))
    choice_to_canon: dict[str, str] = {}
    for canonical, aliases in raw.items():
        if canonical.startswith("$"):
            continue
        choice_to_canon[_norm(canonical)] = canonical
        for alias in aliases:
            choice_to_canon[_norm(alias)] = canonical
    return SkillIndex(choices=list(choice_to_canon.keys()), choice_to_canon=choice_to_canon)


def canonicalize_skill(
    raw: object,
    index: Optional[SkillIndex] = None,
    threshold: int = 86,
) -> Optional[SkillMatch]:
    if index is None:
        index = load_skill_index()
    token = _norm(raw)
    if not token:
        return None

    # Exact alias / canonical hit.
    if token in index.choice_to_canon:
        return SkillMatch(index.choice_to_canon[token], 1.0, True)

    # Fuzzy fallback.
    best = process.extractOne(token, index.choices, scorer=fuzz.WRatio)
    if best and best[1] >= threshold:
        return SkillMatch(index.choice_to_canon[best[0]], best[1] / 100.0, True)

    # Unknown but real: keep the original token, don't invent a canonical name.
    return SkillMatch(str(raw).strip(), 0.5, False)

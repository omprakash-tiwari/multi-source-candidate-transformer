"""Unstructured source: recruiter notes (.txt free text).

The weakest source by design. We only pull things we can extract with high
precision (emails, phones, a "N years" mention) and skills that match the
canonical dictionary with a word boundary and length >= 4 -- deliberately
conservative so free text never invents a skill the recruiter didn't mention.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..models import MatchKeys, Method, RawCandidate
from ..normalize import normalize_phone
from ..normalize.skills import load_skill_index
from .base import SourceAdapter, v

_M = Method.HEURISTIC
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\-.\s()]{7,}\d")
_YEARS_RE = re.compile(r"(\d{1,2})\+?\s*(?:years|yrs)\b", re.I)


class RecruiterNotesAdapter(SourceAdapter):
    source_type = "recruiter_notes"

    def _parse(self, source_ref: str) -> list[RawCandidate]:
        text = Path(source_ref).read_text(encoding="utf-8", errors="ignore")
        if not text.strip():
            return []
        low = text.lower()

        scalars: dict = {}
        lists: dict = {}

        emails = sorted({m.group(0).lower() for m in _EMAIL_RE.finditer(text)})
        if emails:
            lists["emails"] = [v(e, _M, e) for e in emails]

        phones: list[str] = []
        for m in _PHONE_RE.finditer(text):
            normalized = normalize_phone(m.group(0))
            if normalized and normalized not in phones:
                phones.append(normalized)
        if phones:
            lists["phones"] = [v(p, _M, p) for p in phones]

        years = _YEARS_RE.search(text)
        if years:
            scalars["years_experience"] = v(float(years.group(1)), _M, years.group(0))

        index = load_skill_index()
        found: dict[str, str] = {}
        for choice, canonical in index.choice_to_canon.items():
            if len(choice) < 4:
                continue  # avoid ambiguous short tokens (go, ml, js, c...)
            if re.search(rf"\b{re.escape(choice)}\b", low):
                found.setdefault(canonical, choice)
        for canonical in sorted(found):
            lists.setdefault("skills", []).append(v(canonical, _M, found[canonical]))

        if not (scalars or lists):
            return []

        match_keys = MatchKeys(emails=emails, phones=phones)
        return [
            RawCandidate(
                source=f"{self.source_type}#{Path(source_ref).name}",
                source_type=self.source_type,
                reliability=self.reliability,
                scalars=scalars,
                lists=lists,
                match_keys=match_keys,
            )
        ]

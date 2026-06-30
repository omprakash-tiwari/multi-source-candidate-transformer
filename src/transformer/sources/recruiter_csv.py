"""Structured source: recruiter CSV export.

Columns: name, email, phone, current_company, title. Phones have no country
code, so we normalize with the export's default region (US) -- a documented
assumption; numbers that don't validate are dropped rather than guessed.
"""
from __future__ import annotations

import csv
from pathlib import Path

from ..models import MatchKeys, Method, RawCandidate
from ..normalize import (
    company_key,
    name_key,
    normalize_name,
    normalize_phone,
)
from .base import SourceAdapter, v


class RecruiterCsvAdapter(SourceAdapter):
    source_type = "recruiter_csv"

    def _parse(self, source_ref: str) -> list[RawCandidate]:
        path = Path(source_ref)
        out: list[RawCandidate] = []
        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for i, row in enumerate(reader):
                candidate = self._row_to_candidate(row, i)
                if candidate is not None:
                    out.append(candidate)
        return out

    def _row_to_candidate(self, row: dict, index: int) -> RawCandidate | None:
        name = normalize_name(row.get("name"))
        email = (row.get("email") or "").strip().lower() or None
        if not name and not (email and "@" in email):
            return None  # no anchor to identify this candidate

        scalars: dict = {}
        lists: dict = {}

        if name:
            scalars["full_name"] = v(name, Method.DIRECT_FIELD, row.get("name"))

        emails = [email] if email and "@" in email else []
        if emails:
            lists["emails"] = [v(email, Method.DIRECT_FIELD, row.get("email"))]

        phone = normalize_phone(row.get("phone"))
        if phone:
            lists["phones"] = [v(phone, Method.DIRECT_FIELD, row.get("phone"))]

        company = (row.get("current_company") or "").strip() or None
        title = (row.get("title") or "").strip() or None
        if company or title:
            exp = {
                "company": company,
                "title": title,
                "start": None,
                "end": None,
                "summary": None,
            }
            lists["experience"] = [v(exp, Method.DIRECT_FIELD, dict(row))]

        match_keys = MatchKeys(
            emails=emails,
            phones=[phone] if phone else [],
            name=name_key(name),
            company=company_key(company),
        )
        return RawCandidate(
            source=f"{self.source_type}#row{index + 1}",
            source_type=self.source_type,
            reliability=self.reliability,
            scalars=scalars,
            lists=lists,
            match_keys=match_keys,
        )

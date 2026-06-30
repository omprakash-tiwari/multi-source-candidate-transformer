"""Structured source: ATS JSON blob.

Deliberately uses *foreign* field names that do NOT match our schema
(``fullName``, ``currentEmployer``, ``skillTags`` ...). The mapping table below
is the entire adaptation layer -- everything downstream sees canonical fields.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..models import MatchKeys, Method, RawCandidate
from ..normalize import (
    clean_url,
    company_key,
    github_key,
    linkedin_key,
    name_key,
    normalize_country,
    normalize_month,
    normalize_name,
    normalize_phone,
)
from .base import SourceAdapter, v

_M = Method.STRUCTURED_MAP


class AtsJsonAdapter(SourceAdapter):
    source_type = "ats_json"

    def _parse(self, source_ref: str) -> list[RawCandidate]:
        data = json.loads(Path(source_ref).read_text(encoding="utf-8"))
        records = data.get("records") if isinstance(data, dict) else data
        if not isinstance(records, list):
            raise ValueError("ATS blob has no 'records' array")
        return [self._record_to_candidate(rec, i) for i, rec in enumerate(records)]

    def _record_to_candidate(self, rec: dict, index: int) -> RawCandidate:
        contact = rec.get("contact") or {}
        address = rec.get("address") or {}
        socials = rec.get("socials") or {}

        country = normalize_country(address.get("country"))
        name = normalize_name(rec.get("fullName"))

        scalars: dict = {}
        lists: dict = {}

        if name:
            scalars["full_name"] = v(name, _M, rec.get("fullName"))
        if rec.get("headline"):
            scalars["headline"] = v(str(rec["headline"]).strip(), _M, rec.get("headline"))
        if rec.get("yearsOfExperience") is not None:
            try:
                scalars["years_experience"] = v(
                    float(rec["yearsOfExperience"]), _M, rec.get("yearsOfExperience")
                )
            except (TypeError, ValueError):
                pass

        if address.get("city"):
            scalars["location.city"] = v(str(address["city"]).strip(), _M, address.get("city"))
        if address.get("state"):
            scalars["location.region"] = v(str(address["state"]).strip(), _M, address.get("state"))
        if country:
            scalars["location.country"] = v(country, _M, address.get("country"))

        linkedin = clean_url(socials.get("linkedinUrl"))
        github = clean_url(socials.get("githubUrl"))
        if linkedin:
            scalars["links.linkedin"] = v(linkedin, _M, socials.get("linkedinUrl"))
        if github:
            scalars["links.github"] = v(github, _M, socials.get("githubUrl"))

        email = (contact.get("primaryEmail") or "").strip().lower() or None
        emails = [email] if email and "@" in email else []
        if emails:
            lists["emails"] = [v(email, _M, contact.get("primaryEmail"))]

        phone = normalize_phone(contact.get("mobile"), default_region=country or "US")
        if phone:
            lists["phones"] = [v(phone, _M, contact.get("mobile"))]

        for tag in rec.get("skillTags") or []:
            lists.setdefault("skills", []).append(v(str(tag), _M, tag))

        employer = rec.get("currentEmployer")
        title = rec.get("jobTitle")
        if employer or title:
            exp = {
                "company": (str(employer).strip() if employer else None),
                "title": (str(title).strip() if title else None),
                "start": normalize_month(rec.get("startedOn")),
                "end": None,  # current role
                "summary": None,
            }
            lists["experience"] = [v(exp, _M, {"currentEmployer": employer, "jobTitle": title})]

        match_keys = MatchKeys(
            emails=emails,
            phones=[phone] if phone else [],
            github=github_key(github),
            linkedin=linkedin_key(linkedin),
            name=name_key(name),
            company=company_key(employer),
        )
        cid = rec.get("candidateId") or f"idx{index}"
        return RawCandidate(
            source=f"{self.source_type}#{cid}",
            source_type=self.source_type,
            reliability=self.reliability,
            scalars=scalars,
            lists=lists,
            match_keys=match_keys,
        )

"""Unstructured source: resume (PDF / DOCX / TXT).

A heuristic, section-aware parser. Resumes are messy, so this is best-effort by
design: it extracts name, contacts, a SKILLS list, EXPERIENCE blocks (with
normalized YYYY-MM dates) and EDUCATION. Anything it cannot parse is simply left
out -- never guessed.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from ..models import MatchKeys, Method, RawCandidate
from ..normalize import (
    github_key,
    name_key,
    normalize_month,
    normalize_name,
    normalize_phone,
    normalize_year,
)
from ..normalize.date import PRESENT_TOKENS
from .base import SourceAdapter, v

_M = Method.REGEX_EXTRACT
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\-.\s()]{7,}\d")
_BULLET_RE = re.compile(r"^[\-*•·]\s*")
_SEP_RE = re.compile(r"\s*(?:-|–|—|to)\s*", re.I)


class ResumeAdapter(SourceAdapter):
    source_type = "resume"

    def _parse(self, source_ref: str) -> list[RawCandidate]:
        path = Path(source_ref)
        text = self._read_text(path)
        if not text or not text.strip():
            return []

        lines = [ln.rstrip() for ln in text.splitlines()]
        sections = self._sectionize(lines)

        scalars: dict = {}
        lists: dict = {}

        name = self._extract_name(lines)
        if name:
            scalars["full_name"] = v(name, _M, lines[0] if lines else None)

        emails = sorted({m.group(0).lower() for m in _EMAIL_RE.finditer(text)})
        if emails:
            lists["emails"] = [v(e, _M, e) for e in emails]

        phones = self._extract_phones(text)
        if phones:
            lists["phones"] = [v(p, _M, p) for p in phones]

        gh_login = github_key(text)
        if gh_login:
            scalars["links.github"] = v(f"https://github.com/{gh_login}", _M, gh_login)

        city, region = self._extract_location(lines)
        if city:
            scalars["location.city"] = v(city, _M, city)
        if region:
            scalars["location.region"] = v(region, _M, region)

        if sections.get("summary"):
            summary_line = " ".join(s.strip() for s in sections["summary"] if s.strip())
            if summary_line:
                scalars["headline"] = v(summary_line[:160].strip(), _M, summary_line)

        for skill in self._extract_skills(sections.get("skills", [])):
            lists.setdefault("skills", []).append(v(skill, _M, skill))

        for exp in self._extract_experience(sections.get("experience", [])):
            lists.setdefault("experience", []).append(v(exp, _M, exp))

        for edu in self._extract_education(sections.get("education", [])):
            lists.setdefault("education", []).append(v(edu, _M, edu))

        match_keys = MatchKeys(
            emails=emails,
            phones=phones,
            github=gh_login,
            name=name_key(name) if name else None,
        )
        return [
            RawCandidate(
                source=f"{self.source_type}#{path.name}",
                source_type=self.source_type,
                reliability=self.reliability,
                scalars=scalars,
                lists=lists,
                match_keys=match_keys,
            )
        ]

    # -- text extraction ----------------------------------------------------
    @staticmethod
    def _read_text(path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".txt":
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".docx":
            from docx import Document

            return "\n".join(p.text for p in Document(str(path)).paragraphs)
        if suffix == ".pdf":
            import pdfplumber

            with pdfplumber.open(str(path)) as pdf:
                return "\n".join((page.extract_text() or "") for page in pdf.pages)
        raise ValueError(f"unsupported resume format: {suffix}")

    # -- sectionizer --------------------------------------------------------
    @staticmethod
    def _header_key(line: str) -> Optional[str]:
        s = line.strip()
        if not s or len(s.split()) > 3:
            return None
        if not re.fullmatch(r"[A-Z][A-Z &/]+", s):
            return None
        up = s.upper()
        if "SKILL" in up:
            return "skills"
        if "EXPERIENCE" in up or "EMPLOYMENT" in up:
            return "experience"
        if "EDUCATION" in up:
            return "education"
        if "SUMMARY" in up or "PROFILE" in up or "OBJECTIVE" in up:
            return "summary"
        return None

    def _sectionize(self, lines: list[str]) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {}
        current = "_top"
        buf: list[str] = []
        for line in lines:
            key = self._header_key(line)
            if key:
                sections[current] = buf
                current = key
                buf = []
            else:
                buf.append(line)
        sections[current] = buf
        return sections

    # -- field extractors ---------------------------------------------------
    @staticmethod
    def _extract_name(lines: list[str]) -> Optional[str]:
        for line in lines:
            s = line.strip()
            if not s:
                continue
            if _EMAIL_RE.search(s) or _PHONE_RE.search(s) or "|" in s:
                return None  # contact line reached before a name line
            if 1 <= len(s.split()) <= 5 and re.fullmatch(r"[A-Za-z .,'-]+", s):
                return normalize_name(s)
            return None
        return None

    @staticmethod
    def _extract_phones(text: str) -> list[str]:
        out: list[str] = []
        for m in _PHONE_RE.finditer(text):
            normalized = normalize_phone(m.group(0))
            if normalized and normalized not in out:
                out.append(normalized)
        return out

    @staticmethod
    def _extract_location(lines: list[str]) -> tuple[Optional[str], Optional[str]]:
        for line in lines[:6]:
            for segment in re.split(r"[|]", line):
                seg = segment.strip()
                m = re.fullmatch(r"([A-Za-z .'-]+),\s*([A-Za-z]{2,})", seg)
                if m:
                    return m.group(1).strip(), m.group(2).strip()
        return None, None

    @staticmethod
    def _extract_skills(skill_lines: list[str]) -> list[str]:
        joined = " ".join(skill_lines)
        tokens = re.split(r"[,;/|•]", joined)
        out: list[str] = []
        for tok in tokens:
            s = tok.strip()
            if s and s not in out:
                out.append(s)
        return out

    def _parse_date_range(self, line: str) -> Optional[tuple[Optional[str], Optional[str]]]:
        if not re.search(r"\d{4}", line):
            return None
        parts = _SEP_RE.split(line.strip(), maxsplit=1)
        if len(parts) != 2:
            return None
        start = normalize_month(parts[0])
        end_raw = parts[1].strip()
        end = None if end_raw.lower() in PRESENT_TOKENS else normalize_month(end_raw)
        if start is None and end is None and end_raw.lower() not in PRESENT_TOKENS:
            return None
        return start, end

    @staticmethod
    def _split_company_title(line: str) -> tuple[Optional[str], Optional[str]]:
        parts = re.split(r"\s*[-–—|·]\s*", line.strip(), maxsplit=1)
        company = parts[0].strip() or None
        title = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
        return company, title

    def _extract_experience(self, exp_lines: list[str]) -> list[dict]:
        entries: list[dict] = []
        current: Optional[dict] = None
        for line in exp_lines:
            s = line.strip()
            if not s:
                continue
            if _BULLET_RE.match(s):
                if current is not None:
                    current["_bullets"].append(_BULLET_RE.sub("", s).strip())
                continue
            date_range = self._parse_date_range(s)
            if date_range is not None:
                if current is not None:
                    current["start"], current["end"] = date_range
                continue
            if current is not None:
                entries.append(current)
            company, title = self._split_company_title(s)
            current = {
                "company": company,
                "title": title,
                "start": None,
                "end": None,
                "_bullets": [],
            }
        if current is not None:
            entries.append(current)

        for e in entries:
            bullets = e.pop("_bullets")
            e["summary"] = "; ".join(bullets) if bullets else None
        return entries

    @staticmethod
    def _extract_education(edu_lines: list[str]) -> list[dict]:
        # Split into blocks separated by blank lines.
        blocks: list[list[str]] = []
        buf: list[str] = []
        for line in edu_lines:
            if line.strip():
                buf.append(line.strip())
            elif buf:
                blocks.append(buf)
                buf = []
        if buf:
            blocks.append(buf)

        out: list[dict] = []
        for block in blocks:
            institution = block[0] if block else None
            rest = " ".join(block[1:]) if len(block) > 1 else ""
            degree_m = re.search(
                r"(Ph\.?D\.?|B\.?S\.?|M\.?S\.?|B\.?A\.?|M\.?A\.?|B\.?Tech|M\.?Tech|"
                r"Bachelor[^,]*|Master[^,]*|Diploma[^,]*)",
                rest,
                re.I,
            )
            field_m = re.search(r"\b(?:in|of)\s+([A-Za-z &]+?)(?:,|$)", rest)
            out.append(
                {
                    "institution": institution,
                    "degree": degree_m.group(1).strip() if degree_m else None,
                    "field": field_m.group(1).strip() if field_m else None,
                    "end_year": normalize_year(rest),
                }
            )
        return out

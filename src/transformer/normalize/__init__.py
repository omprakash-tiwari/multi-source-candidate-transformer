"""Deterministic, single-purpose normalizers. Each returns a clean value or
``None`` -- never a guessed/invented value."""

from .country import normalize_country
from .date import normalize_month, normalize_year
from .links import clean_url, github_key, linkedin_key
from .name import company_key, name_key, normalize_name
from .phone import normalize_phone
from .skills import canonicalize_skill, load_skill_index

__all__ = [
    "normalize_country",
    "normalize_month",
    "normalize_year",
    "clean_url",
    "github_key",
    "linkedin_key",
    "company_key",
    "name_key",
    "normalize_name",
    "normalize_phone",
    "canonicalize_skill",
    "load_skill_index",
]

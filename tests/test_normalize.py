"""Normalizer unit tests -- the deterministic atoms of the pipeline."""
from transformer.normalize import (
    canonicalize_skill,
    normalize_country,
    normalize_month,
    normalize_phone,
    normalize_year,
)


def test_phone_us_national_format():
    assert normalize_phone("(415) 555-0132") == "+14155550132"


def test_phone_uk_needs_region_hint():
    assert normalize_phone("020 7946 0958", default_region="GB") == "+442079460958"


def test_phone_international_prefix():
    assert normalize_phone("+1 415-555-0132") == "+14155550132"


def test_phone_invalid_returns_none_not_invented():
    assert normalize_phone("not a phone") is None
    assert normalize_phone("") is None
    # A UK national number under the US default region must NOT be mis-coerced.
    assert normalize_phone("020 7946 0958", default_region="US") is None


def test_month_formats():
    assert normalize_month("2021-02-15") == "2021-02"
    assert normalize_month("Mar 2021") == "2021-03"
    assert normalize_month("March 2021") == "2021-03"
    assert normalize_month("03/2021") == "2021-03"
    assert normalize_month("Present") is None


def test_month_year_only_is_not_invented():
    # We refuse to fabricate a month from a year-only token.
    assert normalize_month("2021") is None


def test_year_extraction():
    assert normalize_year("B.S. in Computer Science, 2018") == 2018
    assert normalize_year("no year here") is None


def test_country_iso():
    assert normalize_country("United States") == "US"
    assert normalize_country("USA") == "US"
    assert normalize_country("United Kingdom") == "GB"
    assert normalize_country("England") == "GB"
    assert normalize_country("Narnia") is None


def test_skill_alias_canonicalization():
    assert canonicalize_skill("JS").name == "JavaScript"
    assert canonicalize_skill("ReactJS").name == "React"
    assert canonicalize_skill("k8s").name == "Kubernetes"
    assert canonicalize_skill("Postgres").name == "PostgreSQL"
    assert canonicalize_skill("golang").name == "Go"


def test_unknown_skill_is_kept_not_invented():
    match = canonicalize_skill("Roadmapping")
    assert match.canonical is False
    assert match.name == "Roadmapping"

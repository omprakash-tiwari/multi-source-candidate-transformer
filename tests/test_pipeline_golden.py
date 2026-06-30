"""End-to-end golden + determinism tests on the bundled sample inputs."""
from pathlib import Path

from transformer.pipeline import output_hash, run_pipeline

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = str(ROOT / "data" / "samples")


def _run():
    return run_pipeline(SAMPLES, github_ref="janedoe", use_live_github=False)


def _profile(result, name):
    return next(c.profile for c in result.candidates if c.profile.full_name == name)


def test_two_candidates_resolved():
    result = _run()
    names = sorted(c.profile.full_name for c in result.candidates)
    assert names == ["Jane Doe", "John Smith"]


def test_jane_golden_profile():
    jane = _profile(_run(), "Jane Doe")

    # Phones from CSV/ATS/resume/notes all dedup to one E.164 number.
    assert jane.phones == ["+14155550132"]
    # Two distinct emails are unioned across sources.
    assert set(jane.emails) == {"j.doe@work.com", "jane.doe@gmail.com"}
    assert jane.location.country == "US"

    # Skills canonicalized + merged across CSV/ATS/GitHub/resume/notes.
    names = {s.name for s in jane.skills}
    for expected in {"JavaScript", "React", "Node.js", "PostgreSQL", "Kubernetes", "Python", "Go"}:
        assert expected in names

    # EDGE CASE: conflicting current role. Agreement (CSV+resume) wins over the
    # single higher-trust ATS value.
    current = jane.experience[0]
    assert current.company == "Acme Corp"          # over "Acme Corporation"
    assert current.title == "Senior Software Engineer"  # over "Staff Software Engineer"

    assert jane.education[0].end_year == 2018
    assert 0.0 < jane.overall_confidence <= 0.99


def test_provenance_covers_every_populated_field():
    jane = _profile(_run(), "Jane Doe")
    prov_fields = {p.field for p in jane.provenance}
    for field in {"full_name", "emails", "phones", "skills", "experience", "location.country"}:
        assert field in prov_fields


def test_run_is_deterministic():
    h1 = output_hash({"candidates": _run().canonical()})
    h2 = output_hash({"candidates": _run().canonical()})
    assert h1 == h2

"""Projection engine + schema validation tests (the configurable-output twist)."""
import pytest

from transformer.config_models import OutputConfig
from transformer.projection import _MISSING, ProjectionError, project, resolve_path
from transformer.validation import validate_projection

CANON = {
    "full_name": "Jane Doe",
    "emails": ["a@x.com", "b@y.com"],
    "phones": ["+14155550132"],
    "location": {"city": "SF", "region": "CA", "country": "US"},
    "links": {"github": "https://github.com/janedoe", "linkedin": None},
    "skills": [{"name": "Python", "confidence": 0.9}, {"name": "Go", "confidence": 0.8}],
    "experience": [{"title": "SWE"}],
}


def _cfg(data: dict) -> OutputConfig:
    return OutputConfig.model_validate(data)


def test_resolve_index_map_and_nested():
    assert resolve_path(CANON, "emails[0]") == "a@x.com"
    assert resolve_path(CANON, "skills[].name") == ["Python", "Go"]
    assert resolve_path(CANON, "location.city") == "SF"
    assert resolve_path(CANON, "experience[0].title") == "SWE"


def test_resolve_missing_is_sentinel():
    assert resolve_path(CANON, "phones[5]") is _MISSING
    assert resolve_path(CANON, "does.not.exist") is _MISSING


def test_rename_and_omit_missing():
    cfg = _cfg(
        {
            "fields": [
                {"path": "primary_email", "from": "emails[0]", "type": "string"},
                {"path": "linkedin", "from": "links.linkedin", "type": "string"},
            ],
            "on_missing": "omit",
        }
    )
    out = project(CANON, cfg)
    assert out["primary_email"] == "a@x.com"
    assert "linkedin" not in out  # None source value -> omitted


def test_on_missing_null():
    cfg = _cfg(
        {
            "fields": [{"path": "linkedin", "from": "links.linkedin", "type": "string"}],
            "on_missing": "null",
        }
    )
    assert project(CANON, cfg)["linkedin"] is None


def test_required_missing_raises():
    cfg = _cfg(
        {"fields": [{"path": "li", "from": "links.linkedin", "type": "string", "required": True}]}
    )
    with pytest.raises(ProjectionError):
        project(CANON, cfg)


def test_normalize_e164_at_projection():
    cfg = _cfg(
        {"fields": [{"path": "phone", "from": "phones[0]", "type": "string", "normalize": "E164"}]}
    )
    assert project(CANON, cfg)["phone"] == "+14155550132"


def test_validation_catches_type_mismatch():
    cfg = _cfg({"fields": [{"path": "emails", "from": "emails", "type": "string"}]})
    out = project(CANON, cfg)
    errors = validate_projection(out, cfg)
    assert errors and "emails" in errors[0]


def test_validation_passes_for_matching_types():
    cfg = _cfg(
        {
            "fields": [
                {"path": "full_name", "type": "string", "required": True},
                {"path": "skills", "from": "skills[].name", "type": "string[]"},
            ]
        }
    )
    out = project(CANON, cfg)
    assert validate_projection(out, cfg) == []

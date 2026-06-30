"""Merge / conflict-resolution tests -- the trust ladder + agreement boost."""
from transformer.merge import merge_cluster
from transformer.models import MatchKeys, Method, RawCandidate, Value


def _rc(source, stype, rel, scalars=None, lists=None, emails=None, phones=None):
    return RawCandidate(
        source=source,
        source_type=stype,
        reliability=rel,
        scalars=scalars or {},
        lists=lists or {},
        match_keys=MatchKeys(emails=emails or [], phones=phones or []),
    )


def test_agreement_beats_single_high_trust_source():
    # Two weaker sources agree on 'Senior'; one stronger source says 'Staff'.
    csv = _rc("csv#1", "recruiter_csv", 0.85,
              scalars={"headline": Value(value="Senior", method=Method.DIRECT_FIELD)},
              emails=["j@x.com"])
    resume = _rc("resume#1", "resume", 0.70,
                 scalars={"headline": Value(value="Senior", method=Method.REGEX_EXTRACT)},
                 emails=["j@x.com"])
    ats = _rc("ats#1", "ats_json", 0.90,
              scalars={"headline": Value(value="Staff", method=Method.STRUCTURED_MAP)},
              emails=["j@x.com"])
    merged = merge_cluster([csv, resume, ats])
    assert merged.profile.headline == "Senior"


def test_single_high_trust_wins_without_agreement():
    csv = _rc("csv#1", "recruiter_csv", 0.85,
              scalars={"headline": Value(value="A", method=Method.DIRECT_FIELD)},
              emails=["j@x.com"])
    ats = _rc("ats#1", "ats_json", 0.90,
              scalars={"headline": Value(value="B", method=Method.STRUCTURED_MAP)},
              emails=["j@x.com"])
    merged = merge_cluster([csv, ats])
    assert merged.profile.headline == "B"


def test_emails_union_and_phone_dedup():
    a = _rc("csv#1", "recruiter_csv", 0.85,
            lists={
                "emails": [Value(value="a@x.com", method=Method.DIRECT_FIELD)],
                "phones": [Value(value="+14155550132", method=Method.DIRECT_FIELD)],
            },
            emails=["a@x.com"], phones=["+14155550132"])
    b = _rc("ats#1", "ats_json", 0.90,
            lists={
                "emails": [Value(value="b@y.com", method=Method.STRUCTURED_MAP)],
                "phones": [Value(value="+14155550132", method=Method.STRUCTURED_MAP)],
            },
            emails=["b@y.com"], phones=["+14155550132"])
    merged = merge_cluster([a, b])
    assert merged.profile.phones == ["+14155550132"]
    assert sorted(merged.profile.emails) == ["a@x.com", "b@y.com"]


def test_confidence_is_capped_below_one():
    cands = [
        _rc(f"s{i}", "ats_json", 0.90,
            scalars={"full_name": Value(value="Jane Doe", method=Method.DIRECT_FIELD)},
            emails=["j@x.com"])
        for i in range(8)
    ]
    merged = merge_cluster(cands)
    assert merged.field_confidence["full_name"] <= 0.99

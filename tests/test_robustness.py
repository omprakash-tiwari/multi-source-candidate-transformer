"""Robustness: a malformed/garbage source must never crash the run."""
from pathlib import Path

from transformer.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = str(ROOT / "data" / "samples")


def _run():
    return run_pipeline(SAMPLES, github_ref="janedoe", use_live_github=False)


def test_garbage_source_is_flagged_not_fatal():
    result = _run()
    errors = [h for h in result.health if h.status == "error"]
    # The intentionally broken JSON is reported as an error...
    assert any("garbage" in h.source for h in errors)
    # ...and the run still produces the real candidates.
    assert len(result.candidates) == 2


def test_garbage_values_are_not_invented():
    # No candidate should carry data attributable to the garbage source.
    result = _run()
    for cand in result.candidates:
        for prov in cand.profile.provenance:
            assert "garbage" not in prov.source


def test_missing_input_dir_degrades_gracefully():
    result = run_pipeline(str(ROOT / "data" / "does_not_exist"))
    assert result.candidates == []
    assert result.health == []

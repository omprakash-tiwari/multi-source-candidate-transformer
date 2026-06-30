"""Source detection / routing.

Maps each input file to an adapter by extension + filename convention, and
optionally adds a GitHub source. The scan is non-recursive, so helper folders
like ``github_cache/`` are ignored.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .ats_json import AtsJsonAdapter
from .base import SourceAdapter
from .github_api import GithubApiAdapter
from .recruiter_csv import RecruiterCsvAdapter
from .recruiter_notes import RecruiterNotesAdapter
from .resume import ResumeAdapter


def adapter_for_file(path: Path) -> Optional[SourceAdapter]:
    suffix = path.suffix.lower()
    name = path.name.lower()
    if suffix == ".csv":
        return RecruiterCsvAdapter()
    if suffix == ".json":
        return AtsJsonAdapter()
    if suffix in {".pdf", ".docx"}:
        return ResumeAdapter()
    if suffix == ".txt":
        if "resume" in name or "cv" in name:
            return ResumeAdapter()
        return RecruiterNotesAdapter()
    return None


def plan_inputs(
    input_path: str,
    github_ref: Optional[str] = None,
    use_live_github: bool = False,
) -> list[tuple[SourceAdapter, str]]:
    """Return an ordered list of ``(adapter, source_ref)`` to run."""
    plan: list[tuple[SourceAdapter, str]] = []
    root = Path(input_path)
    if root.is_dir():
        for child in sorted(root.iterdir()):
            if child.is_dir() or child.name.startswith("."):
                continue
            adapter = adapter_for_file(child)
            if adapter is not None:
                plan.append((adapter, str(child)))
    elif root.is_file():
        adapter = adapter_for_file(root)
        if adapter is not None:
            plan.append((adapter, str(root)))

    if github_ref:
        plan.append((GithubApiAdapter(use_live=use_live_github), github_ref))
    return plan

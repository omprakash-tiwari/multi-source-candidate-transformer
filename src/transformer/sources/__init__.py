"""Source adapters: one plugin per input type."""

from .ats_json import AtsJsonAdapter
from .base import SOURCE_RELIABILITY, AdapterResult, SourceAdapter
from .github_api import GithubApiAdapter
from .recruiter_csv import RecruiterCsvAdapter
from .recruiter_notes import RecruiterNotesAdapter
from .registry import adapter_for_file, plan_inputs
from .resume import ResumeAdapter

__all__ = [
    "AtsJsonAdapter",
    "GithubApiAdapter",
    "RecruiterCsvAdapter",
    "RecruiterNotesAdapter",
    "ResumeAdapter",
    "SourceAdapter",
    "AdapterResult",
    "SOURCE_RELIABILITY",
    "adapter_for_file",
    "plan_inputs",
]

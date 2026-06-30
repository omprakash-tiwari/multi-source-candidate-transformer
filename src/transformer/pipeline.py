"""Pipeline orchestration.

    detect -> extract -> normalize -> match -> merge -> confidence
            -> [project -> validate]

Everything is deterministic: stable ordering throughout and no wall-clock or
randomness in the output, so identical inputs yield byte-identical results
(verifiable via ``output_hash``).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config_models import OutputConfig
from .matching import cluster
from .merge import MergedProfile, merge_cluster
from .models import SourceHealth
from .projection import project
from .sources import plan_inputs
from .validation import validate_projection


@dataclass
class PipelineResult:
    candidates: list[MergedProfile] = field(default_factory=list)
    health: list[SourceHealth] = field(default_factory=list)

    def canonical(self) -> list[dict]:
        return [c.profile.model_dump() for c in self.candidates]

    def health_report(self) -> list[dict]:
        return [h.model_dump() for h in self.health]


def run_pipeline(
    input_path: str,
    github_ref: Optional[str] = None,
    use_live_github: bool = False,
) -> PipelineResult:
    plan = plan_inputs(input_path, github_ref=github_ref, use_live_github=use_live_github)

    raw_candidates = []
    health: list[SourceHealth] = []
    for adapter, ref in plan:
        result = adapter.parse(ref)  # never raises -- robustness boundary
        health.append(result.health)
        raw_candidates.extend(result.candidates)

    merged = [merge_cluster(group) for group in cluster(raw_candidates)]
    merged.sort(key=lambda m: m.profile.candidate_id)
    return PipelineResult(candidates=merged, health=health)


def project_candidate(merged: MergedProfile, config: OutputConfig) -> tuple[dict, list[str]]:
    canonical = merged.profile.model_dump()
    output = project(
        canonical,
        config,
        field_confidence=merged.field_confidence,
        provenance=canonical.get("provenance"),
    )
    errors = validate_projection(output, config)
    return output, errors


def load_config(path: str) -> OutputConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return OutputConfig.model_validate(data)


def output_hash(obj) -> str:
    """Stable content hash -- proof of determinism across runs."""
    payload = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

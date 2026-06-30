"""Source adapter framework.

Every source is a small plugin that turns one raw input into zero or more
``RawCandidate`` records. The base class wraps each parse in a robustness
boundary: a malformed/garbage source can never crash the run -- it is caught,
recorded in a ``SourceHealth`` row, and the pipeline keeps going.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from pathlib import Path

from ..models import RawCandidate, SourceHealth, Value

# Trust ladder: how much we believe each source by default, in [0, 1].
SOURCE_RELIABILITY: dict[str, float] = {
    "ats_json": 0.90,        # system of record, structured
    "recruiter_csv": 0.85,   # human-entered but structured
    "github_api": 0.80,      # authoritative for code/links, typed API
    "resume": 0.70,          # self-reported prose
    "recruiter_notes": 0.55, # weakest: free-text, lossy
}


@dataclass
class AdapterResult:
    candidates: list[RawCandidate]
    health: SourceHealth


def v(value: object, method: str, raw: object | None = None) -> Value:
    """Shorthand for building an extraction Value."""
    return Value(value=value, method=method, raw=raw)


class SourceAdapter(abc.ABC):
    source_type: str = "base"

    @property
    def reliability(self) -> float:
        return SOURCE_RELIABILITY.get(self.source_type, 0.5)

    def label(self, source_ref: str) -> str:
        try:
            name = Path(source_ref).name
        except Exception:
            name = source_ref
        return f"{self.source_type}:{name or source_ref}"

    def parse(self, source_ref: str) -> AdapterResult:
        """Robustness boundary: never raises."""
        label = self.label(source_ref)
        try:
            candidates = self._parse(source_ref)
        except Exception as exc:  # noqa: BLE001 - intentional catch-all per spec
            return AdapterResult(
                candidates=[],
                health=SourceHealth(
                    source=label,
                    source_type=self.source_type,
                    status="error",
                    records=0,
                    detail=f"{type(exc).__name__}: {exc}",
                ),
            )
        status = "ok" if candidates else "empty"
        return AdapterResult(
            candidates=candidates,
            health=SourceHealth(
                source=label,
                source_type=self.source_type,
                status=status,
                records=len(candidates),
            ),
        )

    @abc.abstractmethod
    def _parse(self, source_ref: str) -> list[RawCandidate]:
        ...

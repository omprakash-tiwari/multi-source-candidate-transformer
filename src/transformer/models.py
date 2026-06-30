"""Core data models.

Two layers live here, kept deliberately separate (this separation is the whole
point of the "configurable output" twist):

* The **internal** extraction model (`RawCandidate`, `Value`, `MatchKeys`) is
  what every source adapter emits. It is rich, lossy-nothing, and carries the
  provenance and method needed to score confidence and resolve conflicts.

* The **canonical** model (`CanonicalProfile` and friends) is the single,
  fixed-shape record produced after matching + merging. The projection layer
  (see ``projection.py``) reads from this canonical record only.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# Extraction methods (how a value was obtained -> feeds the confidence model)
# --------------------------------------------------------------------------- #
class Method:
    DIRECT_FIELD = "direct_field"      # structured column/field read verbatim
    STRUCTURED_MAP = "structured_map"  # mapped from a foreign structured schema (ATS)
    API_FIELD = "api_field"            # field from a typed API response (GitHub)
    REGEX_EXTRACT = "regex_extract"    # pulled from prose with a pattern
    FUZZY_MATCH = "fuzzy_match"        # resolved via fuzzy/canonical lookup
    HEURISTIC = "heuristic"            # weak inference from free text
    INFERRED = "inferred"             # derived/computed from other values


# --------------------------------------------------------------------------- #
# Internal extraction layer
# --------------------------------------------------------------------------- #
class Value(BaseModel):
    """A single extracted fact, before merge. ``raw`` keeps the original token
    for explainability; ``confidence`` is filled in centrally during merge."""

    value: Any
    method: str
    raw: Optional[Any] = None
    confidence: float = 0.0


class MatchKeys(BaseModel):
    """Keys used by entity resolution to decide whether two source records
    describe the same candidate. Strong keys (email/phone/url) union eagerly;
    weak keys (name+company) only corroborate."""

    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    github: Optional[str] = None
    linkedin: Optional[str] = None
    name: Optional[str] = None
    company: Optional[str] = None


class RawCandidate(BaseModel):
    """Everything one source knows about one candidate."""

    source: str          # unique label, e.g. "ats_json#ats-1001"
    source_type: str     # adapter type, e.g. "ats_json"
    reliability: float   # source trust weight in [0, 1]
    scalars: dict[str, Value] = Field(default_factory=dict)        # path -> Value
    lists: dict[str, list[Value]] = Field(default_factory=dict)    # field -> [Value]
    match_keys: MatchKeys = Field(default_factory=MatchKeys)


class SourceHealth(BaseModel):
    """One row of the per-source health report (robustness signal)."""

    source: str
    source_type: str
    status: str               # "ok" | "empty" | "error"
    records: int = 0
    detail: Optional[str] = None


# --------------------------------------------------------------------------- #
# Canonical layer (the fixed output schema from the assignment)
# --------------------------------------------------------------------------- #
class Location(BaseModel):
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None  # ISO-3166 alpha-2


class Links(BaseModel):
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    other: list[str] = Field(default_factory=list)


class Skill(BaseModel):
    name: str                       # canonical skill name
    confidence: float
    sources: list[str] = Field(default_factory=list)


class Experience(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    start: Optional[str] = None     # YYYY-MM
    end: Optional[str] = None       # YYYY-MM, or None for ongoing
    summary: Optional[str] = None


class Education(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    end_year: Optional[int] = None


class Provenance(BaseModel):
    field: str
    source: str
    method: str


class CanonicalProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    full_name: Optional[str] = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    location: Location = Field(default_factory=Location)
    links: Links = Field(default_factory=Links)
    headline: Optional[str] = None
    years_experience: Optional[float] = None
    skills: list[Skill] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)
    overall_confidence: float = 0.0

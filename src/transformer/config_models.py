"""Runtime output configuration models (the "configurable output" twist).

A config reshapes the canonical record into an arbitrary projection WITHOUT any
code change. It can select a subset of fields, rename/remap them from a
canonical path (``from``), apply per-field normalization, toggle
provenance/confidence, and decide what happens when a value is missing.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

OnMissing = Literal["null", "omit", "error"]


class FieldSpec(BaseModel):
    # Ignore documentation keys like "$comment"; accept the reserved word "from".
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    path: str                                   # output key
    from_: Optional[str] = Field(default=None, alias="from")  # canonical source path
    type: Optional[str] = None                  # declared output type for validation
    required: bool = False
    normalize: Optional[str] = None             # e.g. "E164", "canonical"

    @property
    def source_path(self) -> str:
        """The canonical path to read from (defaults to the output path)."""
        return self.from_ if self.from_ else self.path


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fields: list[FieldSpec]
    include_confidence: bool = False
    include_provenance: bool = False
    on_missing: OnMissing = "null"

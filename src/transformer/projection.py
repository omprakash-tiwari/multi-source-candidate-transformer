"""Projection layer (the "configurable output" twist).

Reads ONLY from the canonical record and reshapes it per a runtime config:
field subset, rename/remap via a path expression (``from``), per-field
normalization, provenance/confidence toggles, and a missing-value policy.

The path mini-language supports: ``full_name``, ``emails[0]``,
``location.city``, ``links.github``, ``skills[].name``, ``experience[0].title``.
"""
from __future__ import annotations

import re
from typing import Any

from .config_models import OutputConfig
from .normalize import canonicalize_skill, normalize_phone

_MISSING = object()
_SEGMENT_RE = re.compile(r"^([A-Za-z_]\w*)(?:\[(\d*)\])?$")


class ProjectionError(ValueError):
    """Raised when on_missing='error' or a required field cannot be produced."""


# --------------------------------------------------------------------------- #
# Path resolver
# --------------------------------------------------------------------------- #
def _parse_segments(path: str) -> list[tuple[str, str, int]]:
    segments: list[tuple[str, str, int]] = []
    for raw in path.split("."):
        m = _SEGMENT_RE.match(raw.strip())
        if not m:
            segments.append((raw, "scalar", -1))
            continue
        key, idx = m.group(1), m.group(2)
        if idx is None:
            segments.append((key, "scalar", -1))
        elif idx == "":
            segments.append((key, "map", -1))
        else:
            segments.append((key, "index", int(idx)))
    return segments


def _resolve(current: Any, segments: list[tuple[str, str, int]]) -> Any:
    if not segments:
        return current
    key, kind, idx = segments[0]
    rest = segments[1:]
    if not isinstance(current, dict) or key not in current:
        return _MISSING
    value = current[key]

    if kind == "scalar":
        return _resolve(value, rest)
    if kind == "index":
        if not isinstance(value, list) or idx >= len(value):
            return _MISSING
        return _resolve(value[idx], rest)
    if kind == "map":
        if not isinstance(value, list):
            return _MISSING
        out = []
        for item in value:
            r = _resolve(item, rest)
            if r is not _MISSING:
                out.append(r)
        return out
    return _MISSING


def resolve_path(data: dict, path: str) -> Any:
    """Return the value at ``path`` or the ``_MISSING`` sentinel."""
    return _resolve(data, _parse_segments(path))


# --------------------------------------------------------------------------- #
# Per-field normalization (applied at projection time)
# --------------------------------------------------------------------------- #
def _apply_normalize(value: Any, norm: str | None) -> Any:
    if norm is None or value is None or value is _MISSING:
        return value
    if isinstance(value, list):
        normalized = [_apply_normalize(v, norm) for v in value]
        return [v for v in normalized if v not in (None, _MISSING)]
    key = norm.lower()
    if key == "e164":
        return normalize_phone(value)
    if key == "canonical":
        match = canonicalize_skill(value)
        return match.name if match else value
    return value


# --------------------------------------------------------------------------- #
# Confidence / provenance lookups
# --------------------------------------------------------------------------- #
def _clean_path(source_path: str) -> str:
    return re.sub(r"\[\d*\]", "", source_path)


def _lookup(source_path: str, table: dict) -> Any:
    clean = _clean_path(source_path)
    if clean in table:
        return table[clean]
    return table.get(clean.split(".")[0])


# --------------------------------------------------------------------------- #
# Projection
# --------------------------------------------------------------------------- #
def _is_missing(value: Any) -> bool:
    return value is _MISSING or value is None or value == []


def project(
    canonical: dict,
    config: OutputConfig,
    field_confidence: dict[str, float] | None = None,
    provenance: list[dict] | None = None,
) -> dict:
    field_confidence = field_confidence or {}
    prov_by_field = {p["field"]: p for p in (provenance or [])}

    output: dict[str, Any] = {}
    confidence_out: dict[str, Any] = {}
    provenance_out: dict[str, Any] = {}

    for spec in config.fields:
        value = resolve_path(canonical, spec.source_path)
        if spec.normalize:
            value = _apply_normalize(value, spec.normalize)

        if _is_missing(value):
            if spec.required:
                raise ProjectionError(f"required field '{spec.path}' is missing")
            if config.on_missing == "error":
                raise ProjectionError(
                    f"field '{spec.path}' is missing and on_missing='error'"
                )
            if config.on_missing == "omit":
                continue
            output[spec.path] = None
        else:
            output[spec.path] = value

        if config.include_confidence:
            confidence_out[spec.path] = _lookup(spec.source_path, field_confidence)
        if config.include_provenance:
            prov = _lookup(spec.source_path, prov_by_field)
            if prov is not None:
                provenance_out[spec.path] = {
                    "source": prov["source"],
                    "method": prov["method"],
                }

    if config.include_confidence:
        output["_confidence"] = confidence_out
    if config.include_provenance:
        output["_provenance"] = provenance_out
    return output

"""Validate a projected output against the requested config's declared schema.

This is the second half of the twist: after projecting, we prove the result
actually matches the types/required flags the caller asked for. Returns a list
of human-readable errors (empty == valid).
"""
from __future__ import annotations

from typing import Any

from .config_models import OutputConfig

_SCALARS = {
    "string": str,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
}


def _type_ok(value: Any, declared: str) -> bool:
    if declared.endswith("[]"):
        if not isinstance(value, list):
            return False
        inner = declared[:-2]
        return all(_type_ok(item, inner) for item in value)
    expected = _SCALARS.get(declared)
    if expected is None:
        return True  # unknown declared type -> don't block
    if declared == "number" and isinstance(value, bool):
        return False  # bools are ints in Python; reject for 'number'
    return isinstance(value, expected)


def validate_projection(output: dict, config: OutputConfig) -> list[str]:
    errors: list[str] = []
    for spec in config.fields:
        present = spec.path in output
        value = output.get(spec.path)

        if spec.required and (not present or value is None):
            errors.append(f"'{spec.path}': required but missing/null")
            continue
        if not present or value is None:
            continue  # legitimately absent (omit) or null (allowed)
        if spec.type and not _type_ok(value, spec.type):
            errors.append(
                f"'{spec.path}': expected {spec.type}, got {type(value).__name__}"
            )
    return errors

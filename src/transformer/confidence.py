"""The confidence model -- deliberately simple, transparent, and explainable.

    confidence(value) = source_reliability x method_weight, then boosted by
    cross-source agreement and capped below 1.0 (we never claim certainty).

Winner selection between conflicting values uses the SAME score, so a value
backed by several independent sources can out-rank a single higher-trust source.
"""
from __future__ import annotations

# How much we trust the *way* a value was obtained.
METHOD_WEIGHT: dict[str, float] = {
    "direct_field": 1.00,    # structured column read verbatim
    "structured_map": 0.95,  # mapped from a foreign structured schema
    "api_field": 0.95,       # typed API response
    "regex_extract": 0.75,   # pulled from prose
    "fuzzy_match": 0.70,     # fuzzy/canonical lookup
    "heuristic": 0.55,       # weak free-text inference
    "inferred": 0.50,        # computed/derived
}

AGREEMENT_BONUS = 0.08  # per extra agreeing source
CONFIDENCE_CAP = 0.99   # honest ceiling -- never 1.0


def base_confidence(reliability: float, method: str) -> float:
    return reliability * METHOD_WEIGHT.get(method, 0.5)


def with_agreement(confidence: float, supporting_sources: int) -> float:
    """Boost a confidence by the number of independent sources that agree."""
    extra = max(0, supporting_sources - 1)
    boosted = confidence * (1.0 + AGREEMENT_BONUS * extra)
    return round(min(CONFIDENCE_CAP, boosted), 4)


def aggregate_overall(field_confidences: list[float]) -> float:
    if not field_confidences:
        return 0.0
    return round(sum(field_confidences) / len(field_confidences), 4)

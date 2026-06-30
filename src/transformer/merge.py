"""Merge + conflict resolution: turn a cluster of source records into ONE
canonical profile, with provenance, confidence, and a human-readable audit
trail of every decision (including how each conflict was settled).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, NamedTuple, Optional

from .confidence import aggregate_overall, base_confidence, with_agreement
from .models import (
    CanonicalProfile,
    Education,
    Experience,
    Method,
    Provenance,
    RawCandidate,
    Skill,
)
from .normalize import canonicalize_skill, company_key
from .normalize.skills import load_skill_index


class Contribution(NamedTuple):
    reliability: float
    source: str
    source_type: str
    method: str
    value: Any


class Resolved(NamedTuple):
    value: Any
    confidence: float
    source: str
    source_type: str
    method: str
    n_support: int
    conflict: Optional[str]


@dataclass
class MergedProfile:
    profile: CanonicalProfile
    field_confidence: dict[str, float]
    audit: list[str]


# --------------------------------------------------------------------------- #
# Generic single-value resolver (the trust ladder)
# --------------------------------------------------------------------------- #
def _cmp_key(value: Any):
    if isinstance(value, bool):
        return ("b", value)
    if isinstance(value, (int, float)):
        return ("n", float(value))
    return ("s", str(value).strip().lower())


def _best_member(members: list[Contribution]) -> Contribution:
    return sorted(
        members,
        key=lambda m: (-base_confidence(m.reliability, m.method), -m.reliability, m.source),
    )[0]


def _resolve(field_name: str, contribs: list[Contribution]) -> Optional[Resolved]:
    contribs = [c for c in contribs if c.value not in (None, "", [])]
    if not contribs:
        return None

    groups: dict[Any, list[Contribution]] = {}
    for c in contribs:
        groups.setdefault(_cmp_key(c.value), []).append(c)

    options = []
    for members in groups.values():
        best = _best_member(members)
        best_base = base_confidence(best.reliability, best.method)
        score = with_agreement(best_base, len(members))
        options.append((score, best_base, best, len(members)))
    options.sort(key=lambda o: (-o[0], -o[1], -o[2].reliability, o[2].source))

    score, _, best, n = options[0]
    conflict = None
    if len(options) > 1:
        losers = ", ".join(f"'{o[2].value}'({o[2].source_type})" for o in options[1:])
        conflict = (
            f"{field_name}: chose '{best.value}'({best.source_type}, conf {score:.2f}) "
            f"over {losers}"
        )
    return Resolved(best.value, score, best.source, best.source_type, best.method, n, conflict)


def _audit_line(path: str, r: Resolved) -> str:
    extra = f" (+{r.n_support - 1} agree)" if r.n_support > 1 else ""
    return f"{path} = {r.value!r} <- {r.source_type} [{r.method}] conf {r.confidence:.2f}{extra}"


# --------------------------------------------------------------------------- #
# Profile assembly helpers
# --------------------------------------------------------------------------- #
def _blank_profile(candidate_id: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "full_name": None,
        "emails": [],
        "phones": [],
        "location": {"city": None, "region": None, "country": None},
        "links": {"linkedin": None, "github": None, "portfolio": None, "other": []},
        "headline": None,
        "years_experience": None,
        "skills": [],
        "experience": [],
        "education": [],
        "provenance": [],
        "overall_confidence": 0.0,
    }


def _set_path(data: dict, path: str, value: Any) -> None:
    if "." in path:
        head, tail = path.split(".", 1)
        data[head][tail] = value
    else:
        data[path] = value


def _candidate_id(cluster: list[RawCandidate]) -> str:
    keys: set[str] = set()
    for rec in cluster:
        keys.update(rec.match_keys.emails)
        if rec.match_keys.github:
            keys.add("gh:" + rec.match_keys.github)
        if rec.match_keys.linkedin:
            keys.add("li:" + rec.match_keys.linkedin)
    if not keys:
        keys = {rec.source for rec in cluster}
    digest = hashlib.sha1("|".join(sorted(keys)).encode("utf-8")).hexdigest()
    return "cand-" + digest[:10]


# --------------------------------------------------------------------------- #
# List-field mergers
# --------------------------------------------------------------------------- #
def _merge_multivalue(cluster: list[RawCandidate], field_name: str):
    best_per_value: dict[str, tuple[float, RawCandidate, Any]] = {}
    for rec in cluster:
        for val in rec.lists.get(field_name, []):
            key = str(val.value).strip().lower()
            score = base_confidence(rec.reliability, val.method)
            if key not in best_per_value or score > best_per_value[key][0]:
                best_per_value[key] = (score, rec, val)
    if not best_per_value:
        return None
    values = sorted(best_per_value.keys())
    contributors = [rec for rec in cluster if rec.lists.get(field_name)]
    n_src = len({rec.source for rec in contributors})
    top = sorted(best_per_value.values(), key=lambda t: (-t[0], t[1].source))[0]
    confidence = with_agreement(top[0], n_src)
    prov = Provenance(field=field_name, source=top[1].source, method=top[2].method)
    return values, confidence, prov, n_src


def _merge_skills(cluster: list[RawCandidate]):
    index = load_skill_index()
    agg: dict[str, dict] = {}
    contributors: list = []
    for rec in cluster:
        skills = rec.lists.get("skills", [])
        if skills:
            contributors.append(rec)
        for val in skills:
            match = canonicalize_skill(val.value, index=index)
            if match is None:
                continue
            contributor = base_confidence(rec.reliability, val.method) * match.confidence
            entry = agg.setdefault(match.name, {"sources": set(), "best": 0.0})
            entry["sources"].add(rec.source_type)
            entry["best"] = max(entry["best"], contributor)
    if not agg:
        return None
    rep_source = sorted(contributors, key=lambda r: (-r.reliability, r.source))[0].source
    skills: list[Skill] = []
    for name, entry in agg.items():
        conf = with_agreement(entry["best"], len(entry["sources"]))
        skills.append(Skill(name=name, confidence=conf, sources=sorted(entry["sources"])))
    skills.sort(key=lambda s: (-s.confidence, s.name))
    confidence = aggregate_overall([s.confidence for s in skills])
    return skills, confidence, rep_source


def _merge_grouped(cluster: list[RawCandidate], field_name: str, model, fields: list[str]):
    """Generic merge for experience/education: group entries by key, resolve
    each sub-field with the trust ladder, return models + audit + confidence."""
    key_fn = company_key if field_name == "experience" else (lambda x: str(x).strip().lower() if x else None)
    primary = "company" if field_name == "experience" else "institution"

    buckets: dict[str, list[tuple[RawCandidate, dict, str]]] = {}
    contributors: list[tuple[RawCandidate, str]] = []
    for rec in cluster:
        for i, val in enumerate(rec.lists.get(field_name, [])):
            entry = val.value
            bkey = key_fn(entry.get(primary)) or f"__{rec.source}#{i}"
            buckets.setdefault(bkey, []).append((rec, entry, val.method))
            contributors.append((rec, val.method))
    if not buckets:
        return None
    rep = sorted(contributors, key=lambda t: (-t[0].reliability, t[0].source))[0]
    rep_source, rep_method = rep[0].source, rep[1]

    built: list[tuple[Any, float, Optional[str]]] = []
    audit: list[str] = []
    for members in buckets.values():
        resolved: dict[str, Optional[Resolved]] = {}
        for fname in fields:
            contribs = [
                Contribution(rec.reliability, rec.source, rec.source_type, method, entry.get(fname))
                for rec, entry, method in members
            ]
            resolved[fname] = _resolve(f"{field_name}.{fname}", contribs)
        kwargs = {f: (resolved[f].value if resolved[f] else None) for f in fields}
        built.append((model(**kwargs), _entry_confidence(resolved), kwargs))
        for r in resolved.values():
            if r and r.conflict:
                audit.append("CONFLICT " + r.conflict)

    entries, confidence = _order_entries(field_name, built)
    return entries, confidence, audit, rep_source, rep_method


def _entry_confidence(resolved: dict[str, Optional[Resolved]]) -> float:
    confs = [r.confidence for r in resolved.values() if r]
    return aggregate_overall(confs) if confs else 0.0


def _order_entries(field_name: str, built: list[tuple[Any, float, dict]]):
    if field_name == "experience":
        built = sorted(built, key=lambda t: (t[2].get("start") or ""), reverse=True)
    else:
        built = sorted(built, key=lambda t: (t[2].get("end_year") or 0), reverse=True)
    entries = [t[0] for t in built]
    confidence = aggregate_overall([t[1] for t in built])
    return entries, confidence


# --------------------------------------------------------------------------- #
# Top-level merge
# --------------------------------------------------------------------------- #
def merge_cluster(cluster: list[RawCandidate]) -> MergedProfile:
    data = _blank_profile(_candidate_id(cluster))
    field_conf: dict[str, float] = {}
    provenance: list[Provenance] = []
    audit: list[str] = []

    # Scalars (full_name, headline, years_experience, location.*, links.*)
    scalar_paths: set[str] = set()
    for rec in cluster:
        scalar_paths.update(rec.scalars.keys())
    for path in sorted(scalar_paths):
        contribs = [
            Contribution(rec.reliability, rec.source, rec.source_type, val.method, val.value)
            for rec in cluster
            if (val := rec.scalars.get(path)) is not None
        ]
        resolved = _resolve(path, contribs)
        if resolved is None:
            continue
        _set_path(data, path, resolved.value)
        field_conf[path] = resolved.confidence
        provenance.append(Provenance(field=path, source=resolved.source, method=resolved.method))
        audit.append(_audit_line(path, resolved))
        if resolved.conflict:
            audit.append("  -> resolved conflict: " + resolved.conflict)

    # Multi-value: emails, phones
    for field_name in ("emails", "phones"):
        merged = _merge_multivalue(cluster, field_name)
        if merged is None:
            continue
        values, confidence, prov, n_src = merged
        data[field_name] = values
        field_conf[field_name] = confidence
        provenance.append(prov)
        audit.append(f"{field_name} = {values} <- {n_src} source(s), conf {confidence:.2f}")

    # Skills
    skills_result = _merge_skills(cluster)
    if skills_result is not None:
        skills, confidence, rep_source = skills_result
        data["skills"] = [s.model_dump() for s in skills]
        field_conf["skills"] = confidence
        provenance.append(Provenance(field="skills", source=rep_source, method=Method.FUZZY_MATCH))
        audit.append(
            f"skills = {[s.name for s in skills]} "
            f"({len(skills)} canonical), conf {confidence:.2f}"
        )

    # Experience + Education
    exp_result = _merge_grouped(
        cluster, "experience", Experience, ["company", "title", "start", "end", "summary"]
    )
    if exp_result is not None:
        entries, confidence, exp_audit, rep_source, rep_method = exp_result
        data["experience"] = [e.model_dump() for e in entries]
        field_conf["experience"] = confidence
        provenance.append(Provenance(field="experience", source=rep_source, method=rep_method))
        audit.extend(exp_audit)

    edu_result = _merge_grouped(
        cluster, "education", Education, ["institution", "degree", "field", "end_year"]
    )
    if edu_result is not None:
        entries, confidence, _, rep_source, rep_method = edu_result
        data["education"] = [e.model_dump() for e in entries]
        field_conf["education"] = confidence
        provenance.append(Provenance(field="education", source=rep_source, method=rep_method))

    data["overall_confidence"] = aggregate_overall(list(field_conf.values()))
    data["provenance"] = [
        p.model_dump() for p in sorted(provenance, key=lambda x: x.field)
    ]

    profile = CanonicalProfile(**data)
    return MergedProfile(profile=profile, field_confidence=field_conf, audit=audit)

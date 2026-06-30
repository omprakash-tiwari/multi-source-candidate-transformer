"""Entity resolution: group source records that describe the same candidate.

Only STRONG, identifying keys union records: email, phone, github, linkedin.
We deliberately do NOT merge on name+company alone -- two different people named
"John Smith" at "Acme" must not be fused. A wrong merge is "wrong-but-confident",
the exact failure mode we are told to avoid, so when only weak signals exist we
keep candidates separate.
"""
from __future__ import annotations

from .models import RawCandidate


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def cluster(records: list[RawCandidate]) -> list[list[RawCandidate]]:
    """Return clusters of records, deterministically ordered."""
    n = len(records)
    uf = _UnionFind(n)

    def link(index_map: dict, key, i: int) -> None:
        if key is None:
            return
        if key in index_map:
            uf.union(index_map[key], i)
        else:
            index_map[key] = i

    emails: dict = {}
    phones: dict = {}
    github: dict = {}
    linkedin: dict = {}
    for i, rec in enumerate(records):
        mk = rec.match_keys
        for e in mk.emails:
            link(emails, e, i)
        for p in mk.phones:
            link(phones, p, i)
        link(github, mk.github, i)
        link(linkedin, mk.linkedin, i)

    groups: dict[int, list[RawCandidate]] = {}
    for i in range(n):
        groups.setdefault(uf.find(i), []).append(records[i])

    clustered = []
    for root in sorted(groups, key=lambda r: min(rc.source for rc in groups[r])):
        clustered.append(sorted(groups[root], key=lambda rc: rc.source))
    return clustered

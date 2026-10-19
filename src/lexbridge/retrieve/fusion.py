"""Reciprocal rank fusion of several ranked lists.

RRF uses ranks, not scores, so a cosine similarity and a BM25 score never need to be put
on one scale. k=60 is the constant from Cormack et al. (2009), not tuned here.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from lexbridge.retrieve.base import Hit

RRF_K = 60


def rrf(rankings: Sequence[Sequence[Hit]], k: int) -> list[Hit]:
    fused: dict[str, float] = defaultdict(float)
    first_seen: dict[str, int] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, 1):
            fused[hit.section_id] += 1 / (RRF_K + rank)
            first_seen.setdefault(hit.section_id, len(first_seen))
    # Ties broken by first appearance, so the dense list (passed first) wins them.
    order = sorted(fused, key=lambda s: (-fused[s], first_seen[s]))
    return [Hit(s, fused[s]) for s in order[:k]]

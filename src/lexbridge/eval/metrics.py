"""Retrieval metrics over the golden set, per category and averaged.

hit@k is the share of cases with any target in the first k results: a case lists every
section that answers it, so "recall" of the full list would punish finding one. MRR is
cut at the largest k. wrong_regime@1 is the share of cases whose first result is the
right provision from the wrong code, the failure a date router exists to remove.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import fmean

from lexbridge.eval.cases import Case

KS = (1, 5, 10)
MACRO = "macro"


@dataclass(frozen=True)
class Scores:
    n: int
    hit: dict[int, float]
    mrr: float
    # None where no case in the group has a wrong-regime counterpart.
    wrong_regime_at_1: float | None


def first_rank(targets: Sequence[str], ranked: Sequence[str]) -> int | None:
    """1-based rank of the first target in the top max(KS), or None."""
    wanted = set(targets)
    return next((i for i, s in enumerate(ranked[: max(KS)], 1) if s in wanted), None)


def _score(pairs: Sequence[tuple[Case, Sequence[str]]]) -> Scores:
    ranks = [first_rank(c.targets, ranked) for c, ranked in pairs]
    can_be_wrong = [(c, ranked) for c, ranked in pairs if c.wrong_regime]
    return Scores(
        n=len(pairs),
        hit={k: fmean(r is not None and r <= k for r in ranks) for k in KS},
        mrr=fmean(1 / r if r else 0.0 for r in ranks),
        wrong_regime_at_1=fmean(bool(ranked) and ranked[0] in c.wrong_regime
                                for c, ranked in can_be_wrong) if can_be_wrong else None,
    )


def score(cases: Sequence[Case], rankings: Sequence[Sequence[str]]) -> dict[str, Scores]:
    """Scores per category plus their unweighted mean under MACRO.

    The macro mean weighs categories equally: 534 generated map lookups would otherwise
    drown the 28 hand-written lay questions. Cases without targets are not retrieval cases.
    """
    if len(cases) != len(rankings):
        raise ValueError(f"{len(cases)} cases for {len(rankings)} rankings")
    groups: dict[str, list[tuple[Case, Sequence[str]]]] = defaultdict(list)
    for case, ranked in zip(cases, rankings, strict=True):
        if case.targets:
            groups[case.category.value].append((case, ranked))
    by_category = {name: _score(pairs) for name, pairs in sorted(groups.items())}
    wrong = [s.wrong_regime_at_1 for s in by_category.values()
             if s.wrong_regime_at_1 is not None]
    by_category[MACRO] = Scores(
        n=sum(s.n for s in by_category.values()),
        hit={k: fmean(s.hit[k] for s in by_category.values()) for k in KS},
        mrr=fmean(s.mrr for s in by_category.values()),
        wrong_regime_at_1=fmean(wrong) if wrong else None,
    )
    return by_category

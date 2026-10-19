"""Retrieval metrics over the golden set, per category and averaged.

hit@k is the share of cases with any target in the first k results: a case lists every
section that answers it, so "recall" of the full list would punish finding one. MRR is
cut at the largest k. wrong_regime@1 is the share of cases whose first result is the
right provision from the wrong code, the failure a date router exists to remove.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from statistics import fmean

from lexbridge.eval.cases import Case, Category
from lexbridge.schema import Act

KS = (1, 5, 10)
MACRO = "macro"
# Answered from the graph, not by searching text: a text retriever scores ~0 on them by
# construction, so averaging them in would depress every text-retrieval headline.
GRAPH_LOOKUPS = frozenset({Category.MAP_IPC_TO_BNS.value, Category.MAP_BNS_TO_IPC.value})


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
    """Scores per category plus, under MACRO, the unweighted mean of the text categories.

    Equal weights stop hundreds of templated questions drowning a few dozen hand-written
    ones. Cases without targets are not retrieval cases; map lookups are reported per
    category but kept out of MACRO (see GRAPH_LOOKUPS).
    """
    if len(cases) != len(rankings):
        raise ValueError(f"{len(cases)} cases for {len(rankings)} rankings")
    groups: dict[str, list[tuple[Case, Sequence[str]]]] = defaultdict(list)
    for case, ranked in zip(cases, rankings, strict=True):
        if case.targets:
            groups[case.category.value].append((case, ranked))
    by_category = {name: _score(pairs) for name, pairs in sorted(groups.items())}
    text = [s for name, s in by_category.items() if name not in GRAPH_LOOKUPS]
    wrong = [s.wrong_regime_at_1 for s in text if s.wrong_regime_at_1 is not None]
    by_category[MACRO] = Scores(
        n=sum(s.n for s in text),
        hit={k: fmean(s.hit[k] for s in text) for k in KS},
        mrr=fmean(s.mrr for s in text),
        wrong_regime_at_1=fmean(wrong) if wrong else None,
    )
    return by_category


def routing(cases: Sequence[Case], act_of: Callable[[str], Act | None]) -> dict[str, int]:
    """How the router decided against each case's known code.

    wrong (the other code) and over_routed (a code chosen where the answer must ask for
    the date) are the errors that matter: both answer confidently from the wrong law.
    unrouted means the router asked when the code was knowable, which costs a round trip.
    """
    counts = {"correct": 0, "wrong": 0, "over_routed": 0, "unrouted": 0}
    for case in cases:
        if case.category is Category.OUT_OF_SCOPE:
            continue
        got = act_of(case.question)
        if got == case.answer_act:
            counts["correct"] += 1
        elif got is None:
            counts["unrouted"] += 1
        elif case.answer_act is None:
            counts["over_routed"] += 1
        else:
            counts["wrong"] += 1
    return counts

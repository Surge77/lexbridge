"""Decide which code a question must be answered from, or that it cannot be known yet.

The costs are asymmetric. Routing to the wrong code answers, confidently, from the wrong
law; asking for the date costs one turn. So the router routes only on consistent
evidence and abstains on anything else:

1. A question that cites a section of one code and names the other code is about the
   counterpart, whatever date it also gives.
2. A month named without its year means the dates were not fully read: ask.
3. A date just after a word about the case ("arrested on", "FIR filed in") is not the
   offence date. It can only veto: an offence dated after a case step means a date was
   misread, so ask. It never decides a code, because a keyword cannot tell this case's
   arrest from an unrelated filing or an old judgment. Birth dates are ignored. If no
   date is left that could be the offence date, ask.

A veto can only turn an answer into a question, so no rule in step 3 can produce a
confident wrong code; positive routes come only from steps 1, 4, 5, 6 and 7.
4. Specific dates (a day, a month, a bound) decide, and the earliest wins, because the
   offence comes before the complaint, the FIR and the trial. Before 1 July 2024 is the
   IPC, from then the BNS (BNS s.358); a period that straddles the cutover decides
   nothing. A bare year that points to the other code makes the question ambiguous.
5. Bare years decide only when there is nothing more specific.
6. A citation with words asking what it became ("replaced", "new law") routes to the
   other code when no offence date decided it.
7. With no date, a question that names exactly one code is about that code.

Every route carries the period it relied on, so an answer can state its assumption
("assuming the offence was on 5 August 2024") and a misread can be corrected.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from lexbridge.query.dates import Period, Role
from lexbridge.query.understand import Facts
from lexbridge.schema import BNS_IN_FORCE_FROM, Act


class Reason(StrEnum):
    MAP = "map"
    DATE = "date"
    NAMED_CODE = "named_code"
    STRADDLES = "straddles"  # the deciding period spans 1 July 2024
    # Dates disagree: a bare year against the dates, or an offence after its own arrest.
    CONFLICT = "conflict"
    UNPLACED = "unplaced"  # dates were given, but none of them is the offence date
    INCOMPLETE = "incomplete"  # a month without its year
    UNKNOWN = "unknown"  # no date and no single code named


@dataclass(frozen=True)
class Route:
    act: Act | None
    reason: Reason
    # The period a DATE route relied on; the answer states it as its assumption.
    basis: Period | None = None


def _act_for(period: Period) -> Act | None:
    if period.end < BNS_IN_FORCE_FROM:
        return Act.IPC
    if period.start >= BNS_IN_FORCE_FROM:
        return Act.BNS
    return None


def _counterpart(facts: Facts) -> tuple[Act, bool] | None:
    """The other code, and whether the question names it (strong) or only asks (weak)."""
    cited = {Act(section.partition(":")[0]) for section in facts.references}
    if len(cited) != 1:
        return None
    [source] = cited
    other = Act.BNS if source is Act.IPC else Act.IPC
    if other in facts.codes:
        return other, True
    return (other, False) if facts.counterpart else None


def _by_date(facts: Facts) -> Route | None:
    if facts.incomplete_date:
        return Route(None, Reason.INCOMPLETE)
    evidence = [p for p in facts.periods if p.role is Role.EVENT]
    if not evidence:
        return Route(None, Reason.UNPLACED) if facts.periods else None
    specific = [p for p in evidence if p.specific]
    years = [p for p in evidence if not p.specific]
    basis = min(specific or years, key=lambda p: p.start)
    # A case step comes after its offence, so an offence dated after one means a date was
    # misread. The step only ever vetoes, never decides or narrows: a keyword cannot tell
    # this case's arrest from an unrelated divorce filing or a 2018 judgment.
    if any(p.role is Role.CASE and basis.start > p.end for p in facts.periods):
        return Route(None, Reason.CONFLICT, basis)
    act = _act_for(basis)
    if act is None:
        return Route(None, Reason.STRADDLES, basis)
    if specific and any(_act_for(y) not in (None, act) for y in years):
        return Route(None, Reason.CONFLICT, basis)
    return Route(act, Reason.DATE, basis)


def route(facts: Facts, *, maps: bool = False) -> Route:
    """maps=False is rung v2's router, kept so its ablation row reproduces."""
    counterpart = _counterpart(facts) if maps else None
    if counterpart and counterpart[1]:
        return Route(counterpart[0], Reason.MAP)
    decided = _by_date(facts)
    if decided and decided.act:
        return decided
    if counterpart:
        return Route(counterpart[0], Reason.MAP)
    if decided:
        return decided
    if len(facts.codes) == 1:
        return Route(next(iter(facts.codes)), Reason.NAMED_CODE)
    return Route(None, Reason.UNKNOWN)

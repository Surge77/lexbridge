"""Decide which code a question must be answered from, or that it cannot be known yet.

The costs are asymmetric. Routing to the wrong code answers, confidently, from the wrong
law; asking for the date costs one turn. So the router routes only on consistent
evidence and abstains on anything else:

1. A question that cites a section of one code and either names the other code or asks
   what the section became is about the counterpart, whatever date it also gives.
2. A month named without its year means the dates were not fully read: ask.
3. Specific dates (a day, a month, a bound) decide, and the earliest wins, because the
   offence comes before the complaint, the FIR and the trial. Before 1 July 2024 is the
   IPC, from then the BNS (BNS s.358); a period that straddles the cutover decides
   nothing. A bare year that points to the other code makes the question ambiguous.
4. Bare years decide only when there is nothing more specific.
5. With no date, a question that names exactly one code is about that code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from lexbridge.query.dates import Period
from lexbridge.query.understand import Facts
from lexbridge.schema import BNS_IN_FORCE_FROM, Act


class Reason(StrEnum):
    MAP = "map"
    DATE = "date"
    NAMED_CODE = "named_code"
    STRADDLES = "straddles"  # the deciding period spans 1 July 2024
    CONFLICT = "conflict"  # a bare year points to the other code than the dates do
    INCOMPLETE = "incomplete"  # a month without its year
    UNKNOWN = "unknown"  # no date and no single code named


@dataclass(frozen=True)
class Route:
    act: Act | None
    reason: Reason


def _act_for(period: Period) -> Act | None:
    if period.end < BNS_IN_FORCE_FROM:
        return Act.IPC
    if period.start >= BNS_IN_FORCE_FROM:
        return Act.BNS
    return None


def _counterpart(facts: Facts) -> Act | None:
    cited = {Act(section.partition(":")[0]) for section in facts.references}
    if len(cited) != 1:
        return None
    [source] = cited
    other = Act.BNS if source is Act.IPC else Act.IPC
    return other if other in facts.codes or facts.counterpart else None


def _by_date(facts: Facts) -> Route | None:
    if facts.incomplete_date:
        return Route(None, Reason.INCOMPLETE)
    specific = [p for p in facts.periods if p.specific]
    years = [p for p in facts.periods if not p.specific]
    deciding = specific or years
    if not deciding:
        return None
    act = _act_for(min(deciding, key=lambda p: p.start))
    if act is None:
        return Route(None, Reason.STRADDLES)
    if specific and any(_act_for(y) not in (None, act) for y in years):
        return Route(None, Reason.CONFLICT)
    return Route(act, Reason.DATE)


def route(facts: Facts, *, maps: bool = False) -> Route:
    """maps=False is rung v2's router, kept so its ablation row reproduces."""
    if maps and (other := _counterpart(facts)):
        return Route(other, Reason.MAP)
    if (decided := _by_date(facts)) is not None:
        return decided
    if len(facts.codes) == 1:
        return Route(next(iter(facts.codes)), Reason.NAMED_CODE)
    return Route(None, Reason.UNKNOWN)

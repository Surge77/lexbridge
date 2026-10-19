"""Decide which code a question must be answered from, or that it cannot be known yet.

The offence date decides: before 1 July 2024 the IPC, from then the BNS (BNS s.358).
A question with several dates is about the earliest one, because the offence comes
before the complaint, the FIR and the trial. A period that straddles the cutover ("in
2024") decides nothing. With no date, a question that names exactly one code is about
that code. Otherwise the code is unknown and the answer must ask for the date.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from lexbridge.query.understand import Facts, Period
from lexbridge.schema import BNS_IN_FORCE_FROM, Act


class Reason(StrEnum):
    DATE = "date"
    NAMED_CODE = "named_code"
    STRADDLES = "straddles"  # the earliest period spans 1 July 2024
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


def route(facts: Facts) -> Route:
    if facts.periods:
        earliest = min(facts.periods, key=lambda p: p.start)
        act = _act_for(earliest)
        return Route(act, Reason.DATE if act else Reason.STRADDLES)
    if len(facts.codes) == 1:
        return Route(next(iter(facts.codes)), Reason.NAMED_CODE)
    return Route(None, Reason.UNKNOWN)

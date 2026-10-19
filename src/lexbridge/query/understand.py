"""Read the facts a question states: when, which code, which sections.

Rules, not a model. Every rule is visible, testable and wrong in a predictable way, and
the router built on it has to be right close to 100% of the time. Dates are read by
lexbridge.query.dates, codes and citations by lexbridge.query.citations.
"""

from __future__ import annotations

from dataclasses import dataclass

from lexbridge.query.citations import asks_for_counterpart, codes, references
from lexbridge.query.dates import Period, read_dates
from lexbridge.schema import Act


@dataclass(frozen=True)
class Facts:
    periods: tuple[Period, ...]
    codes: frozenset[Act]
    # Sections cited with their code, as ids ("IPC:420"), in order of first mention.
    references: tuple[str, ...] = ()
    # A month was named without its year: the dates read are not the whole story.
    incomplete_date: bool = False
    # Words asking what a section became ("replaced", "equivalent", "new law").
    counterpart: bool = False


def understand(text: str) -> Facts:
    dates = read_dates(text)
    return Facts(periods=dates.periods, codes=codes(text), references=references(text),
                 incomplete_date=dates.incomplete, counterpart=asks_for_counterpart(text))

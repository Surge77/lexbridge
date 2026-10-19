"""Read the periods a question states, and say when the reading is incomplete.

Two kinds of evidence, kept apart because they deserve different trust. A specific date
(a day or a month, or a bound such as "before 1 July 2024") is almost always about the
events. A bare four-digit year is weak: it may be the year of an Act, a birth year, or
an amount nobody masked. The router lets weak evidence decide only when nothing
specific exists, and abstains when the two disagree.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta

MONTHS = {
    **{m.lower(): i for i, m in enumerate(calendar.month_name) if m},
    **{m.lower(): i for i, m in enumerate(calendar.month_abbr) if m},
    "sept": 9,
    "जनवरी": 1, "फ़रवरी": 2, "फरवरी": 2, "मार्च": 3, "अप्रैल": 4, "मई": 5, "जून": 6,
    "जुलाई": 7, "अगस्त": 8, "सितंबर": 9, "सितम्बर": 9, "अक्टूबर": 10, "अक्तूबर": 10,
    "नवंबर": 11, "नवम्बर": 11, "दिसंबर": 12, "दिसम्बर": 12,
}
# Also ordinary English words ("the court may", "a protest march"): a month only when a
# number stands next to it.
WORD_MONTHS = frozenset({"may", "march", "mar"})
_MONTH = "|".join(sorted(map(re.escape, MONTHS), key=len, reverse=True))
# Not \b: Python's word boundary falls inside Devanagari words at every vowel sign.
_L, _R = r"(?<![\wऀ-ॿ])", r"(?![\wऀ-ॿ])"
_YEAR = r"((?:18|19|20)\d{2})"
DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
PATTERNS = (
    ("iso", re.compile(_L + r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})" + _R)),
    # Day first, as written in India: 3/5/2024 is 3 May.
    ("numeric", re.compile(_L + r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})" + _R)),
    ("day_month", re.compile(_L + r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + _MONTH
                             + r")[\s,]+" + _YEAR + _R, re.IGNORECASE)),
    ("month_day", re.compile(_L + r"(" + _MONTH + r")\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+"
                             + _YEAR + _R, re.IGNORECASE)),
    ("month", re.compile(_L + r"(" + _MONTH + r")[\s,-]+" + _YEAR + _R, re.IGNORECASE)),
    ("numeric_month", re.compile(_L + r"(\d{1,2})/" + _YEAR + _R)),
    ("year", re.compile(_L + _YEAR + _R)),
)
# Text that contains a year but states no date: an Act's own year in any of the ways it
# is cited, and money. Masked before anything is read.
NOT_DATES = re.compile(
    _L + r"(?:sanhita|code|संहिता|act|adhiniyam|अधिनियम|bns|ipc)\s*(?:\([^)]{0,20}\))?\s*,?"
    r"\s*(?:no\.?\s*\d+\s+of\s+)?(?:18|19|20)\d{2}"
    r"|" + _L + r"(?:18|19|20)\d{2}\s+(?:sanhita|code|act)" + _R
    + r"|" + _L + r"\d+\s+of\s+(?:18|19|20)\d{2}"
    r"|(?:" + _L + r"(?:rs\.?|inr|rupees?)|₹)\s*[\d,]+(?:\.\d+)?"
    r"|" + _L + r"[\d,]+\s*(?:rupees?|rs\b|/-)",
    re.IGNORECASE)
_BEFORE = re.compile(r"(?:before|prior\s+to|earlier\s+than)\s+(?:the\s+)?$", re.IGNORECASE)
_UNTIL = re.compile(r"(?:until|till|up\s+to|upto|by)\s+(?:the\s+)?$", re.IGNORECASE)
_AFTER = re.compile(r"after\s+(?:the\s+)?$", re.IGNORECASE)
_SINCE = re.compile(r"(?:since|from|on\s+or\s+after|starting)\s+(?:the\s+)?$",
                    re.IGNORECASE)
_LEFTOVER_MONTH = re.compile(_L + r"(" + _MONTH + r")" + _R, re.IGNORECASE)


@dataclass(frozen=True)
class Period:
    start: date
    end: date
    # False for a bare year: weak evidence, see the module docstring.
    specific: bool = True


@dataclass(frozen=True)
class Dates:
    periods: tuple[Period, ...]
    # A month was named without the year that would place it ("between 15 June and 15
    # August 2024"): what was read is not the whole story.
    incomplete: bool


def _read(kind: str, g: tuple[str, ...]) -> Period | None:
    try:
        if kind == "iso":
            day = date(int(g[0]), int(g[1]), int(g[2]))
        elif kind == "numeric":
            day = date(int(g[2]), int(g[1]), int(g[0]))
        elif kind == "day_month":
            day = date(int(g[2]), MONTHS[g[1].lower()], int(g[0]))
        elif kind == "month_day":
            day = date(int(g[2]), MONTHS[g[0].lower()], int(g[1]))
        else:
            day = None
        if day is not None:
            return Period(day, day)
        if kind in ("month", "numeric_month"):
            month = MONTHS[g[0].lower()] if kind == "month" else int(g[0])
            year = int(g[1])
            return Period(date(year, month, 1),
                          date(year, month, calendar.monthrange(year, month)[1]))
        return Period(date(int(g[0]), 1, 1), date(int(g[0]), 12, 31), specific=False)
    except (ValueError, KeyError):  # 31/02/2024, month 13: not a date, so not a fact
        return None


def _bounded(period: Period, before: str) -> Period:
    if _BEFORE.search(before):
        return Period(date.min, period.start - timedelta(days=1), period.specific)
    if _UNTIL.search(before):
        return Period(date.min, period.end, period.specific)
    if _AFTER.search(before):
        return Period(period.end + timedelta(days=1), date.max, period.specific)
    if _SINCE.search(before):
        return Period(period.start, date.max, period.specific)
    return period


def _blank(text: str, start: int, end: int) -> str:
    return text[:start] + " " * (end - start) + text[end:]


def read_dates(text: str) -> Dates:
    text = NOT_DATES.sub(lambda m: " " * len(m.group()), text.translate(DIGITS))
    found: list[tuple[int, Period]] = []
    for kind, pattern in PATTERNS:
        for match in pattern.finditer(text):
            if (period := _read(kind, match.groups())) is not None:
                found.append((match.start(), _bounded(period, text[:match.start()])))
            # Blanked so "May 2024" inside "3 May 2024" is not read a second time.
            text = _blank(text, *match.span())
    incomplete = any(
        m.group(1).lower() not in WORD_MONTHS
        or re.search(r"\d\s*$", text[:m.start()]) or re.match(r"\s*\d", text[m.end():])
        for m in _LEFTOVER_MONTH.finditer(text))
    return Dates(tuple(p for _, p in sorted(found, key=lambda pair: pair[0])),
                 bool(incomplete))

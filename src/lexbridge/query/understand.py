"""Read the facts a question states: when it happened and which code it names.

Rules, not a model. Every rule is visible, testable and wrong in a predictable way, and
the router built on it has to be right close to 100% of the time.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date

from lexbridge.schema import Act

MONTHS = {
    **{m.lower(): i for i, m in enumerate(calendar.month_name) if m},
    **{m.lower(): i for i, m in enumerate(calendar.month_abbr) if m},
    "sept": 9,
    "जनवरी": 1, "फ़रवरी": 2, "फरवरी": 2, "मार्च": 3, "अप्रैल": 4, "मई": 5, "जून": 6,
    "जुलाई": 7, "अगस्त": 8, "सितंबर": 9, "सितम्बर": 9, "अक्टूबर": 10, "अक्तूबर": 10,
    "नवंबर": 11, "नवम्बर": 11, "दिसंबर": 12, "दिसम्बर": 12,
}
_MONTH = "|".join(sorted(map(re.escape, MONTHS), key=len, reverse=True))
# Not \b: Python's word boundary falls inside Devanagari words at every vowel sign.
_EDGE_L, _EDGE_R = r"(?<![\wऀ-ॿ])", r"(?![\wऀ-ॿ])"
_YEAR = r"((?:18|19|20)\d{2})"
DATE_PATTERNS = (
    ("iso", re.compile(_EDGE_L + r"(\d{4})-(\d{1,2})-(\d{1,2})" + _EDGE_R)),
    # Day first, as written in India: 3/5/2024 is 3 May.
    ("numeric", re.compile(_EDGE_L + r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})" + _EDGE_R)),
    ("day_month", re.compile(
        _EDGE_L + r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + _MONTH + r"),?\s+" + _YEAR
        + _EDGE_R, re.IGNORECASE)),
    ("month_day", re.compile(
        _EDGE_L + r"(" + _MONTH + r")\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+" + _YEAR + _EDGE_R,
        re.IGNORECASE)),
    ("month", re.compile(_EDGE_L + r"(" + _MONTH + r"),?\s+" + _YEAR + _EDGE_R,
                         re.IGNORECASE)),
    ("year", re.compile(_EDGE_L + _YEAR + _EDGE_R)),
)
# "Bharatiya Nyaya Sanhita, 2023", "45 of 1860" and "Act 2 of 1974" name an Act, not when
# anything happened. Read as dates, the citation year is usually the earliest one in the
# question, and the router would answer from the wrong code.
ACT_TITLE_YEAR = re.compile(
    r"(?:sanhita|code|संहिता|act|bns|ipc)\s*,?\s*(?:1860|2023)"
    r"|\d+\s+of\s+(?:18|19|20)\d{2}", re.IGNORECASE)
CODE_NAMES = {
    Act.IPC: re.compile(r"\bIPC\b|indian\s+penal\s+code|भारतीय\s+दंड\s+संहिता|आईपीसी",
                        re.IGNORECASE),
    Act.BNS: re.compile(r"\bBNS\b|(?:bharatiya\s+)?nyaya\s+sanhita|भारतीय\s+न्याय\s+संहिता|"
                        r"बीएनएस", re.IGNORECASE),
}


@dataclass(frozen=True)
class Period:
    start: date
    end: date


@dataclass(frozen=True)
class Facts:
    periods: tuple[Period, ...]
    codes: frozenset[Act]


def _period(kind: str, groups: tuple[str, ...]) -> Period | None:
    try:
        if kind == "iso":
            day = date(int(groups[0]), int(groups[1]), int(groups[2]))
        elif kind == "numeric":
            day = date(int(groups[2]), int(groups[1]), int(groups[0]))
        elif kind == "day_month":
            day = date(int(groups[2]), MONTHS[groups[1].lower()], int(groups[0]))
        elif kind == "month_day":
            day = date(int(groups[2]), MONTHS[groups[0].lower()], int(groups[1]))
        elif kind == "month":
            year, month = int(groups[1]), MONTHS[groups[0].lower()]
            last = calendar.monthrange(year, month)[1]
            return Period(date(year, month, 1), date(year, month, last))
        else:
            return Period(date(int(groups[0]), 1, 1), date(int(groups[0]), 12, 31))
    except ValueError:  # 31/02/2024 and the like: not a date, so not a fact
        return None
    return Period(day, day)


def periods(text: str) -> tuple[Period, ...]:
    """Every period the text states, most specific reading first, in order of position."""
    remaining = ACT_TITLE_YEAR.sub(lambda m: " " * len(m.group()), text)
    found: list[tuple[int, Period]] = []
    for kind, pattern in DATE_PATTERNS:
        for match in pattern.finditer(remaining):
            period = _period(kind, match.groups())
            if period:
                found.append((match.start(), period))
            # Masked so "May 2024" inside "3 May 2024" is not read a second time.
            remaining = remaining[:match.start()] + " " * len(match.group()) \
                + remaining[match.end():]
    return tuple(p for _, p in sorted(found, key=lambda pair: pair[0]))


def understand(text: str) -> Facts:
    return Facts(periods=periods(text),
                 codes=frozenset(act for act, name in CODE_NAMES.items() if name.search(text)))

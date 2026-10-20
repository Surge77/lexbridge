"""Read the codes a question names and the sections it cites.

A number is a section only when a code is named beside it: a bare "section 138" belongs
to neither code (it is the cheque-bounce section of another Act). Each number is claimed
by one code at most, nearest first, so "IPC 302 BNS equivalent" cites IPC 302 and not
also a BNS 302 that nobody asked about.
"""

from __future__ import annotations

import re

from lexbridge.query.dates import DIGITS
from lexbridge.schema import Act

_CODE = {
    Act.IPC: r"\bIPC\b|indian\s+penal\s+code|भारतीय\s+दंड\s+संहिता|आईपीसी",
    Act.BNS: r"\bBNS\b|(?:bharatiya\s+)?nyaya\s+sanhita|भारतीय\s+न्याय\s+संहिता|बीएनएस",
}
CODE_NAMES = {act: re.compile(pattern, re.IGNORECASE) for act, pattern in _CODE.items()}
# A section number as cited: 420, 498A, 318(4). The sub-section is read past, not kept:
# retrieval is section-level. (?!\d) stops "2023" being read as section 202, and a unit
# after it ("IPC 10 years") means a quantity, not a section.
NOT_A_QUANTITY = (r"(?!\s*(?:years?|yrs?|months?|weeks?|days?|hours?|"
                  r"times|persons?|people|lakhs?|crores?|rupees?)\b)")
_NUMBER = rf"(\d{{1,3}}[A-Z]{{0,3}})(?!\d){NOT_A_QUANTITY}(?:\s*\(\w{{1,3}}\))*"
_SECTION = r"(?:section|sec\.?|s\.|§|धारा|dhara)"
_ACT_YEAR = r"(?:\s*,?\s*(?:18|19|20)\d{2})?"
# Ordered by how tightly the number is bound to its code; a number is claimed once.
PATTERNS = tuple(
    (act, re.compile(pattern, re.IGNORECASE))
    for kind in range(3)
    for act, code in _CODE.items()
    for pattern in [(
        # "IPC 420", "BNS section 303", "IPC 1860 section 420"
        rf"(?:{code}){_ACT_YEAR}\s*{_SECTION}?\s*{_NUMBER}\b",
        # "section 124A of the IPC", "Section 303 BNS", "धारा 420 आईपीसी"
        rf"{_SECTION}\s*{_NUMBER}\s*(?:of\s+(?:the\s+)?)?(?:{code})",
        # "420 IPC"
        rf"(?<![\w(]){_NUMBER}\s+(?:of\s+(?:the\s+)?)?(?:{code})",
    )[kind]]
)
# Asking what a section became, even when only its own code is named.
MAP_CUES = re.compile(
    r"\b(?:replaced|replaces|replacement|equivalent|counterpart|corresponding|"
    r"correspond(?:s|ed)?\s+(?:to|with)|"
    r"new\s+(?:law|code|section|sanhita)|old\s+(?:law|code|section))\b|के\s+बदले|नई\s+धारा",
    re.IGNORECASE)


def codes(text: str) -> frozenset[Act]:
    return frozenset(act for act, name in CODE_NAMES.items() if name.search(text))


def references(text: str) -> tuple[str, ...]:
    """Cited sections as ids ("IPC:420"), in order of first mention."""
    text = text.translate(DIGITS)
    claimed: list[tuple[int, int]] = []
    found: list[tuple[int, str]] = []
    for act, pattern in PATTERNS:
        for match in pattern.finditer(text):
            span = match.span(1)
            if any(s < span[1] and span[0] < e for s, e in claimed):
                continue
            claimed.append(span)
            found.append((span[0], f"{act}:{match.group(1).upper()}"))
    return tuple(dict.fromkeys(section for _, section in sorted(found)))


def asks_for_counterpart(text: str) -> bool:
    return MAP_CUES.search(text) is not None

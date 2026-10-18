"""Find the sections of the same code that a provision's text refers to.

A false reference is worse than a missing one: it sends retrieval to an unrelated
provision whose number happens to exist. So a mention counts only when nothing says
it belongs to another Act. Any "of ..." after it that is not this code naming itself
("of this Code", "of the Indian Penal Code") marks another Act: the General Clauses
Act, the Code of Criminal Procedure, "that Act", "the said Act".

All whitespace is matched with \\s+ because statute text wraps anywhere: the review
found "section 3 of\\nthe General Clauses Act" read as BNS 2 citing BNS 3.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from lexbridge.schema import Act, section_key

NUMBER = r"\d{1,3}[A-Z]{0,3}(?![\dA-Z])"
JOIN = r"\s*,?\s*(?:and|or|to)\s+|\s*,\s*"
MENTION = re.compile(rf"(?i:\bsections?)\s+({NUMBER}(?:(?:{JOIN}){NUMBER})*)")
# Sub-references between a number and what follows: "section 197(1) of the Code ...".
SUB_REFS = re.compile(r"(?:\s*\(\w+\))*")
# "section 3 and section 4 of the Arms Act", "section 3, section 4 of ...": the mentions
# share one fate.
CHAIN = re.compile(
    r"(?:\s*\(\w+\))*\s*(?:,\s*(?:and\s+|or\s+)?|(?:and|or)\s+)(?=(?i:sections?)\s+\d)"
)
OF = re.compile(r"\s*,?\s*of\b")
SAME_CODE = {
    Act.IPC: re.compile(r"\s*,?\s*of\s+(?:this\s+Code|(?:the\s+)?Indian\s+Penal\s+Code)\b"),
    Act.BNS: re.compile(
        r"\s*,?\s*of\s+(?:this\s+Sanhita|(?:the\s+)?Bharatiya\s+Nyaya\s+Sanhita)\b"
    ),
}
ITEM = re.compile(rf"({NUMBER})|\bto\b")


def _numbers(listed: str, known: Sequence[str] | None) -> list[str]:
    """"76, 79, and 81" -> 76, 79, 81; "8 to 52A" -> every known section in between."""
    out: list[str] = []
    pending_range = False
    for item in ITEM.finditer(listed):
        if item.group(1) is None:
            pending_range = True
            continue
        number = item.group(1)
        if pending_range and out and known is not None:
            low, high = section_key(out[-1]), section_key(number)
            out.extend(n for n in known if low < section_key(n) < high)
        out.append(number)
        pending_range = False
    return out


def _chained(text: str, first: re.Match[str], second: re.Match[str]) -> bool:
    # match, not fullmatch with endpos: CHAIN's lookahead must see "section" past the gap.
    joint = CHAIN.match(text, first.end())
    return joint is not None and joint.end() == second.start()


def cross_references(
    text: str, act: Act, known: Sequence[str] | None = None
) -> tuple[str, ...]:
    """Same-code section numbers mentioned in text, in order of first appearance.

    known: the code's section numbers in order, used to expand "8 to 52A". Without it a
    range keeps only its endpoints.
    """
    ordered = sorted(known, key=section_key) if known is not None else None
    mentions = list(MENTION.finditer(text))
    found: list[str] = []
    i = 0
    while i < len(mentions):
        group = [mentions[i]]
        while i + 1 < len(mentions) and _chained(text, group[-1], mentions[i + 1]):
            i += 1
            group.append(mentions[i])
        end = SUB_REFS.match(text, group[-1].end()).end()  # type: ignore[union-attr]
        foreign = OF.match(text, end) and not SAME_CODE[act].match(text, end)
        if not foreign:
            for mention in group:
                found.extend(_numbers(mention.group(1), ordered))
        i += 1
    return tuple(dict.fromkeys(found))

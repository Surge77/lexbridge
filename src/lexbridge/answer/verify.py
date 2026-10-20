"""Every section number an answer mentions must come from its sources or the question.

The model cites by source number, so its citation list cannot leave the retrieved set.
Its prose can: "punishable under section 420" is a claim, and a wrong number in a legal
answer is the failure this project exists to prevent. So the prose is checked too.
"""

from __future__ import annotations

import re
from collections.abc import Collection

from lexbridge.query.citations import NOT_A_QUANTITY, references
from lexbridge.query.dates import DIGITS

# "318, 7 years" lists one section and a term of imprisonment, not sections 318 and 7.
_NUMBER = rf"\d{{1,3}}[A-Z]{{0,3}}(?!\d){NOT_A_QUANTITY}(?:\(\w{{1,4}}\))*"
# "section 318", "sections 303 and 304", "s. 498A", "§ 420", "धारा 420".
# Not "sub-section (4)".
_BARE = re.compile(rf"(?<![\w-])(?:sections?|secs?\.?|ss?\.|§|धारा|dhara)\s*({_NUMBER}"
                   rf"(?:\s*(?:,|and|or|&|to)\s*{_NUMBER})*)", re.IGNORECASE)
# A number right after "(" is a sub-section: the 2 of "117(2)" is not section 2.
_EACH = re.compile(r"(?<![(\w])(\d{1,3}[A-Z]{0,3})(?!\d)", re.IGNORECASE)
# A sentence ends at . ! ? or the Hindi danda, but not at the stop of "s." or "Sec.":
# splitting there would part a mention from its number and let it survive the cut.
_SENTENCE = re.compile(r"(?<!\bs\.)(?<!\bss\.)(?<!\bsec\.)(?<!\bsecs\.)(?<=[.!?।])\s+",
                       re.IGNORECASE)


def mentions(text: str) -> tuple[frozenset[str], frozenset[str]]:
    """(sections named with their code as ids, bare section numbers)."""
    text = text.translate(DIGITS)
    coded = frozenset(references(text))
    bare = frozenset(n.upper() for m in _BARE.finditer(text) for n in _EACH.findall(m.group(1)))
    return coded, bare


def unsupported(text: str, allowed: Collection[str]) -> list[str]:
    """Mentions that no source and nothing in the question supports, as written."""
    numbers = {s.partition(":")[2] for s in allowed}
    coded, bare = mentions(text)
    coded_numbers = {s.partition(":")[2] for s in coded}
    return sorted([s for s in coded if s not in allowed]
                  + [n for n in bare - coded_numbers if n not in numbers])


def strip_unsupported(text: str, allowed: Collection[str]) -> tuple[str, list[str]]:
    """Drop every sentence that still mentions an unsupported section."""
    kept, removed = [], []
    for sentence in _SENTENCE.split(text.strip()):
        bad = unsupported(sentence, allowed)
        if bad:
            removed.extend(bad)
        else:
            kept.append(sentence)
    return " ".join(kept), sorted(set(removed))

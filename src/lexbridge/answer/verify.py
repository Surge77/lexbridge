"""Every section number an answer mentions must come from its sources or the question.

The model cites by source number, so its citation list cannot leave the retrieved set.
Its prose can: "punishable under section 420" is a claim, and a wrong number in a legal
answer is the failure this project exists to prevent. So the prose is checked too.
"""

from __future__ import annotations

import re
from collections.abc import Collection

from lexbridge.query.citations import references

_NUMBER = r"\d{1,3}[A-Z]{0,3}(?!\d)(?:\(\w{1,4}\))*"
# "section 318", "sections 303 and 304", "s. 498A", "§ 420". Not "sub-section (4)".
_BARE = re.compile(rf"(?<![\w-])(?:sections?|secs?\.?|ss?\.|§)\s*({_NUMBER}"
                   rf"(?:\s*(?:,|and|or|&|to)\s*{_NUMBER})*)", re.IGNORECASE)
_EACH = re.compile(r"(\d{1,3}[A-Z]{0,3})(?!\d)", re.IGNORECASE)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def mentions(text: str) -> tuple[frozenset[str], frozenset[str]]:
    """(sections named with their code as ids, bare section numbers)."""
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

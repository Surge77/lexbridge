"""Split an IndiaCode consolidated Act (current IPC, current BNS) into sections.

Layout, as measured on both files:
- footnotes and the watermark are removed upstream (read_lines with footnote_rule and
  max_size); a bare integer line left over is a page number;
- a heading is inline: "420. Cheating and dishonestly inducing delivery of property.—
  Whoever", the title ending at ".—", sometimes a line or two later;
- inserted provisions carry a superscript footnote marker: "2[376DB.Punishment";
- omitted or repealed provisions keep their number: "13. [Definition of “Queen”.]
  Omitted by the A. O. 1950." / "15. [...] Rep. by the A. O. 1937.";
- an "ARRANGEMENT OF SECTIONS" list precedes the text. Its entries have no ".—", so
  the heading test never accepts them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lexbridge.ingest.layout import Line
from lexbridge.schema import Act, Section, Status, section_key

EM_DASH, EN_DASH = chr(0x2014), chr(0x2013)
PAGE_NUMBER = re.compile(r"\d{1,3}")
MARKER = re.compile(r"\b\d+\[")
NUMBER = r"(\d{1,3}[A-Z]{0,3})"
# The stop after the number can be missing, but only seen behind an amendment marker:
# "1[17 “Government”.—" (IPC 17). Unmarked lines still need it, so a body line like
# "100 rupees" can never pass for a heading.
HEADING = re.compile(rf"(?:\d+\[{NUMBER}(?:\.\s*|\s+)|{NUMBER}\.\s*)(\S.*)")
# An em dash ends titles in the IPC; two en dashes in the consolidated BNS.
# The stop before the dash is sometimes missing: "to injury of another person—Whoever"
# (BNS 217).
TITLE_END = re.compile(rf"[.:]?\s*(?:{EM_DASH}|{EN_DASH}{{1,2}})")
REPEALED = re.compile(r"\[(.+?)\.?\]\s*(?:Rep\.|Omitted)")
CHAPTER = re.compile(r"(?:\d+\[)?CHAPTER ([IVXLC]+[A-Z]?)")
# A title can run three lines before its ".—" (IPC 511).
TITLE_LOOKAHEAD = 3


@dataclass
class _Draft:
    number: str
    page: int
    chapter: str | None
    status: Status
    title: str
    lines: list[str] = field(default_factory=list)


def _follows(number: str, last: str | None) -> bool:
    if last is None:
        return number == "1"
    base, last_base = section_key(number)[0], section_key(last)[0]
    return section_key(number) > section_key(last) and base - last_base <= 1


def _continuation(body: list[Line], i: int, number: str) -> list[str]:
    """Lines after a candidate heading, stopping at a line that could be the next one.

    Only a line numbered to follow this heading stops the lookahead. A title can wrap
    onto a cross-reference that merely looks like a heading: IPC 472's runs "...under
    section" / "467.—Whoever makes".
    """
    following: list[str] = []
    for line in body[i + 1 : i + 1 + TITLE_LOOKAHEAD]:
        found = HEADING.fullmatch(line.text)
        if found and _follows(found.group(1) or found.group(2), number):
            break
        following.append(line.text)
    return following


def _heading(body: list[Line], i: int, last: str | None) -> tuple[str, Status, str] | None:
    """(number, status, title) if body[i] starts the next section, else None."""
    found = HEADING.fullmatch(body[i].text)
    if not found:
        return None
    # A stray dash can follow the number itself: "255.—Public servant disobeying" (BNS).
    number, rest = found.group(1) or found.group(2), found.group(3).lstrip(f"{EM_DASH}{EN_DASH} ")
    if not _follows(number, last):
        return None
    joined = " ".join([rest, *_continuation(body, i, number)])
    # The bracketed old title can wrap before "] Rep." (IPC 56).
    if rest.startswith("[") and (repealed := REPEALED.match(joined)):
        return number, Status.REPEALED, repealed.group(1)
    if end := TITLE_END.search(joined):
        return number, Status.IN_FORCE, joined[: end.start()]
    return None


def split_consolidated(lines: list[Line], *, act: Act, source_key: str) -> list[Section]:
    body = [line for line in lines if not PAGE_NUMBER.fullmatch(line.text)]
    drafts: list[_Draft] = []
    chapter: str | None = None
    numeral: str | None = None

    for i, line in enumerate(body):
        if found := CHAPTER.fullmatch(line.text):
            numeral = found.group(1)
            continue
        if numeral is not None:
            # Some chapter names are set below body size and filtered out, so the line
            # after "CHAPTER II" can already be a heading. Only a capitalised non-heading
            # line is a name.
            is_name = line.text.isupper() and not HEADING.fullmatch(line.text)
            chapter, numeral = (f"{numeral} — {line.text}" if is_name else numeral), None
            if is_name:
                continue
        heading = _heading(body, i, drafts[-1].number if drafts else None)
        if heading:
            number, status, title = heading
            drafts.append(_Draft(number, line.page, chapter, status, MARKER.sub("[", title)))
        if drafts:
            drafts[-1].lines.append(line.text)

    return [
        Section(
            act=act,
            number=d.number,
            title=d.title.replace("[", "").strip(),
            text=MARKER.sub("[", "\n".join(d.lines)),
            chapter=d.chapter,
            status=d.status,
            source_key=source_key,
            page=d.page,
        )
        for d in drafts
    ]

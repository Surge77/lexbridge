"""Split the BNS gazette into sections.

Gazette layout, as measured on the PRS copy:
- section headings are body lines starting "N. ", in strict sequence 1..358;
- each title is an 8pt margin note level with its heading (left margin on even pages,
  right on odd);
- chapters are a "CHAPTER XVII" line followed by the chapter name on the next line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from lexbridge.ingest.layout import Line
from lexbridge.schema import Act, Section, Status

# The space after the full stop is optional: the gazette prints "192.Whoever" with none.
# A digit straight after it is a decimal ("2.5 per cent"), never a heading.
HEADING = re.compile(r"(\d{1,3})\.\s*[^\d\s]")
CHAPTER = re.compile(r"CHAPTER ([IVXLC]+)")
# A margin note can start above its heading: "Stalking." sits 3.4pt above "78.".
# Body lines are 12pt apart, so 5pt cannot reach the previous section's note.
NOTE_TOLERANCE = 5.0
# Margin references to other Acts ("28 of 1961.") sit in the same column as titles,
# sometimes on the same line as one: "Persons subject 45 of 1950.".
ACT_CITATION = re.compile(r"\s*\b\d{1,3} of \d{4}\.")
# The gazette closes with a rule of dashes, then the signature and the printer's
# colophon. None of that is enacted text.
EM_DASH, EN_DASH = chr(0x2014), chr(0x2013)
END_RULE = re.compile(f"[{EM_DASH}{EN_DASH}-]{{4,}}")


@dataclass
class _Draft:
    number: int
    page: int
    top: float
    chapter: str | None
    lines: list[str] = field(default_factory=list)


def _title(draft: _Draft, next_draft: _Draft | None, notes: list[Line]) -> str:
    """Join the margin lines between this heading and the next one on the same page."""
    end = next_draft.top if next_draft and next_draft.page == draft.page else float("inf")
    picked = [
        n.text
        for n in notes
        if n.page == draft.page and draft.top - NOTE_TOLERANCE <= n.top < end - NOTE_TOLERANCE
    ]
    return " ".join(picked)


def _before_end_rule(lines: list[Line]) -> list[Line]:
    for rule in lines:
        if rule.column == "body" and END_RULE.fullmatch(rule.text):
            return [line for line in lines if (line.page, line.top) < (rule.page, rule.top)]
    return lines


def split_bns(lines: list[Line], *, source_key: str) -> list[Section]:
    lines = _before_end_rule(lines)
    notes = [
        replace(line, text=ACT_CITATION.sub("", line.text).strip())
        for line in lines
        if line.column == "margin"
    ]
    notes = [line for line in notes if line.text]
    drafts: list[_Draft] = []
    chapter: str | None = None
    chapter_numeral: str | None = None

    for line in (line for line in lines if line.column == "body"):
        heading = CHAPTER.fullmatch(line.text)
        if heading:
            chapter_numeral = heading.group(1)
            continue
        if chapter_numeral is not None:
            # The line after "CHAPTER XVII" is the chapter's name.
            chapter = f"{chapter_numeral} — {line.text}"
            chapter_numeral = None
            continue

        start = HEADING.match(line.text)
        expected = drafts[-1].number + 1 if drafts else 1
        if start and int(start.group(1)) == expected:
            drafts.append(_Draft(number=expected, page=line.page, top=line.top, chapter=chapter))
        if drafts:
            drafts[-1].lines.append(line.text)

    sections = []
    for i, draft in enumerate(drafts):
        following = drafts[i + 1] if i + 1 < len(drafts) else None
        sections.append(
            Section(
                act=Act.BNS,
                number=str(draft.number),
                title=_title(draft, following, notes),
                text="\n".join(draft.lines),
                chapter=draft.chapter,
                status=Status.IN_FORCE,
                source_key=source_key,
                page=draft.page,
            )
        )
    return sections

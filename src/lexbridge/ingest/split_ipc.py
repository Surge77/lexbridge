"""Split IndiaCode's IPC typescript into sections.

Layout, as measured on IndiaCode's copy (Courier 10 throughout, so size is no help):
- a heading reads "420. Cheating and dishonestly inducing delivery of property.--Whoever";
  the title ends at ".--" (sometimes ".-" plus a soft hyphen), possibly a line later;
- each heading is preceded by a margin repeat: a bare "420." line, then the title;
- inserted sections carry amendment markers: "1*[124A. Sedition.--", "2***", "3*[India]";
- footnotes sit below a rule of dashes, or, when they overflow, above a rule that is
  followed directly by the page number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from lexbridge.ingest.layout import Line
from lexbridge.schema import Act, Section, Status, section_key

SOFT_HYPHEN, EM_DASH = chr(0x00AD), chr(0x2014)
RULE = re.compile(r"-{20,}")
PAGE_NUMBER = re.compile(r"\d{1,3}")
MARKER = re.compile(r"\d+\*+")
NUMBER = r"(\d{1,3}[A-Z]{0,3})"
# The stop after the number can be missing on amended sections: '2*[17 "Government".--'.
# Amendment markers before a number: "1*[124A." usually, "1*479." on IPC 479.
INSERT_MARK = r"(?:\d+\*+\[?)?"
HEADING = re.compile(rf"{INSERT_MARK}{NUMBER}(?:\.\s*|\s+)(\S.*)")
BARE_NUMBER = re.compile(rf"{INSERT_MARK}{NUMBER}\.")
RANGE_REPEAL = re.compile(rf"{NUMBER}\s+to\s+{NUMBER}\.\s*Rep\.")
# ".--" usually, "riot;--" on IPC 158, ".-" plus a soft hyphen in places, and a lone
# ".-" before the body on IPC 92 ("consent.-Nothing"). A double dash appears nowhere
# else in a heading line, so any clause punctuation (or none) may precede it.
TITLE_END = re.compile(
    rf"[.;:,]?\s*(?:--|-{SOFT_HYPHEN}|{EM_DASH})|\.\s*-(?=\s*[A-Z\"\[(])"
)
REPEALED = re.compile(r"\[(.+?)\.?\]\s*Rep\.")
# Some repealed sections exist only as a margin entry: "13." then the bracketed old
# title, whose opening bracket IndiaCode sometimes loses.
MARGIN_REPEAL = re.compile(r"\[?(.+?)\.?\]\s*Rep\.")
CHAPTER = re.compile(r"CHAPTER ([IVXLC]+[A-Z]?)")
# A margin repeat is the bare number plus a title of at most a few lines.
MAX_MARGIN_REPEAT = 6
# A title can run to three lines before its ".--" or "] Rep." (IPC 56, 269).
TITLE_LOOKAHEAD = 3
# Enough of a title to tell two sections apart; short titles are never trusted.
TITLE_MATCH_CHARS = 25


@dataclass
class _Draft:
    number: str
    page: int
    chapter: str | None
    status: Status
    title: str
    lines: list[str] = field(default_factory=list)


def drop_page_furniture(lines: list[Line]) -> list[Line]:
    """Remove footnotes, rules and page numbers, page by page."""
    kept: list[Line] = []
    for page in sorted({line.page for line in lines}):
        on_page = [line for line in lines if line.page == page]
        numbers = [i for i, line in enumerate(on_page) if PAGE_NUMBER.fullmatch(line.text)]
        drop = set(numbers)
        rules = [i for i, line in enumerate(on_page) if RULE.fullmatch(line.text)]
        for i in rules:
            if i + 1 in numbers:
                # Only the page's first rule can close an overflow from the previous
                # page. A later one closes this page's own footnote block, which the
                # opening rule has already dropped.
                if i == rules[0]:
                    drop.update(range(i + 1))
            else:
                # Footnotes run from the rule to the page number; the page's own body
                # can follow it (page 5: "10." tail, rule, footnotes, "103", "11.").
                stop = next((k for k in numbers if k > i), len(on_page) - 1)
                drop.update(range(i, stop + 1))
        kept.extend(line for i, line in enumerate(on_page) if i not in drop)
    return kept


def _heading_number(line: Line) -> str | None:
    heading = HEADING.fullmatch(line.text)
    return heading.group(1) if heading else None


def _misnumbered(heading: Line, margin_title: str) -> bool:
    """The heading carries a typo'd number but the same title as the margin repeat.

    IndiaCode prints "320. Voluntarily causing hurt to extort confession" for section
    330; its margin repeat says "330." correctly.
    """
    found = HEADING.fullmatch(heading.text)
    prefix = margin_title[:TITLE_MATCH_CHARS]
    return bool(found and len(prefix) == TITLE_MATCH_CHARS and found.group(2).startswith(prefix))


def _drop_margin_repeats(lines: list[Line], corrections: list[str]) -> list[Line]:
    """Remove each heading's margin repeat; a margin-only repeal becomes a heading.

    A heading whose number disagrees with its margin repeat but whose title matches is
    renumbered to the margin's number, and the change is appended to `corrections`.
    """
    out: list[Line] = []
    i = 0
    while i < len(lines):
        bare = BARE_NUMBER.fullmatch(lines[i].text.strip())
        if not bare:
            out.append(lines[i])
            i += 1
            continue
        number = bare.group(1)
        following = lines[i + 1] if i + 1 < len(lines) else None
        window = range(i + 1, min(i + 1 + MAX_MARGIN_REPEAT, len(lines)))
        target = next((j for j in window if _heading_number(lines[j]) == number), None)
        if target is None and following is not None:
            typo = next((j for j in window if _misnumbered(lines[j], following.text)), None)
            if typo is not None:
                wrong = _heading_number(lines[typo])
                lines = [*lines[:typo], _renumber(lines[typo], number), *lines[typo + 1 :]]
                corrections.append(f"IPC {number}: heading printed as {wrong}")
                target = typo
        repeal = MARGIN_REPEAL.match(following.text) if following else None
        if target is not None:
            i = target
        elif repeal and following:
            out.append(replace(following, text=f"{number}. [{repeal.group(1)}.] Rep."))
            i += 2
        else:
            i += 1
    return out


def _renumber(line: Line, number: str) -> Line:
    found = HEADING.fullmatch(line.text)
    assert found is not None
    return replace(line, text=f"{number}. {found.group(2)}")


def _continuation(body: list[Line], i: int) -> list[str]:
    """The lines after a candidate heading, up to the next line that is itself one.

    Stopping there keeps a footnote-shaped line ("2. Subs. by Act 26 of 1955") from
    borrowing the ".--" of the real heading below it.
    """
    following: list[str] = []
    for line in body[i + 1 : i + 1 + TITLE_LOOKAHEAD]:
        if HEADING.fullmatch(line.text):
            break
        following.append(line.text)
    return following


def _follows(number: str, last: str | None) -> bool:
    if last is None:
        return number == "1"
    base, last_base = section_key(number)[0], section_key(last)[0]
    return section_key(number) > section_key(last) and base - last_base <= 1


def _range(start: str, end: str) -> list[str]:
    first, _ = section_key(start)
    last, letters = section_key(end)
    numbers = [start] + [str(n) for n in range(first + 1, last + 1)]
    return [*numbers, end] if letters else numbers


def split_ipc(
    lines: list[Line], *, source_key: str, corrections: list[str] | None = None
) -> list[Section]:
    """Sections in order. Typo fixes applied to the source are appended to corrections."""
    fixes = corrections if corrections is not None else []
    body = _drop_margin_repeats(drop_page_furniture(lines), fixes)
    drafts: list[_Draft] = []
    chapter: str | None = None
    numeral: str | None = None

    for i, line in enumerate(body):
        text = line.text
        last = drafts[-1].number if drafts else None
        if found := CHAPTER.fullmatch(text):
            numeral = found.group(1)
            continue
        if numeral is not None:
            chapter, numeral = f"{numeral} — {text}", None
            continue

        if (span := RANGE_REPEAL.match(text)) and _follows(span.group(1), last):
            for number in _range(span.group(1), span.group(2)):
                drafts.append(_Draft(number, line.page, chapter, Status.REPEALED, "", [text]))
            continue

        heading = HEADING.fullmatch(text)
        if heading and _follows(heading.group(1), last):
            rest = heading.group(2)
            joined = " ".join([rest, *_continuation(body, i)])
            repealed = REPEALED.match(joined)
            title_end = TITLE_END.search(joined)
            if repealed or title_end:
                title = repealed.group(1) if repealed else joined[: title_end.start()]  # type: ignore[union-attr]
                status = Status.REPEALED if repealed else Status.IN_FORCE
                drafts.append(
                    _Draft(heading.group(1), line.page, chapter, status, MARKER.sub("", title))
                )
        if drafts:
            drafts[-1].lines.append(text)

    return [
        Section(
            act=Act.IPC,
            number=d.number,
            title=d.title.strip().replace("[", "").strip(),
            text=MARKER.sub("", "\n".join(d.lines)),
            chapter=d.chapter,
            status=d.status,
            source_key=source_key,
            page=d.page,
        )
        for d in drafts
    ]

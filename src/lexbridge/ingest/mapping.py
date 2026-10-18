"""Parse the CAPT Bhopal BNS-to-IPC correspondence table into correspondences.

The table has four columns: BNS section or sub-section | subject | IPC section(s) |
summary of the change. The IPC column uses a small, informal grammar, measured on all 38
pages: lists joined by ",", "&", "and" or "/", ranges ("230 to 232"), sub-references
("376(1)", "228A (1)/(2)", "23 Clause-1", "498A Explanation") and markers of a provision
with no IPC counterpart ("New", "-"). The parser is strict: a token it does not know
raises, so a cell can never be dropped without anyone noticing.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Set
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

NO_COUNTERPART = re.compile(r"(?i)new(\s*sub-?\s*section)?|-")
SEPARATORS = re.compile(r"\s*(?:,|&|/|\band\b)\s*")
RANGE = re.compile(r"(\d{1,3})\s+to\s+(\d{1,3})")
# A section number, then any sub-reference the table adds ("(1)", "Clause-1",
# "Explanation"); "171-I" is how the table writes section 171I.
IPC_TOKEN = re.compile(
    r"(\d{1,3})(?:-?([A-Z]{1,3}))?\s*(?:\(\d+\)|Clause-\d+|Explanat\s*ion)?"
)
SUB_ONLY = re.compile(r"\(\d+\)")
BNS_REF = re.compile(r"(\d{1,3})\s*((?:\(\d+\))*)\s*\(?([a-z])?\)?")


class MappingParseError(ValueError):
    """A correspondence-table cell outside the grammar measured on the table."""


@dataclass(frozen=True)
class Correspondence:
    bns_section: str
    bns_sub: str
    ipc: tuple[str, ...]
    subject: str
    summary: str
    page: int


def parse_ipc_cell(cell: str) -> tuple[str, ...]:
    """IPC section numbers named by one cell; () when the BNS provision is new."""
    text = cell.strip()
    if not text:
        raise MappingParseError("empty IPC cell")
    if NO_COUNTERPART.fullmatch(text):
        return ()
    numbers: list[str] = []
    for token in SEPARATORS.split(text):
        if not token:
            continue  # a trailing separator: "363A,"
        if SUB_ONLY.fullmatch(token):
            continue  # "228A (1)/(2)": the "(2)" refers back to 228A.
        if span := RANGE.fullmatch(token):
            first, last = int(span.group(1)), int(span.group(2))
            numbers.extend(str(n) for n in range(first, last + 1))
            continue
        found = IPC_TOKEN.fullmatch(token)
        if not found:
            raise MappingParseError(f"unrecognised IPC reference {token!r} in {cell!r}")
        numbers.append(found.group(1) + (found.group(2) or ""))
    return tuple(dict.fromkeys(numbers))  # "376(1) & 376(2)" names 376 once


def parse_bns_ref(cell: str) -> tuple[str, str] | None:
    """("103", "(2)") for "103 (2)"; None for header fragments and wrapped text."""
    found = BNS_REF.fullmatch(cell.strip())
    if not found:
        return None
    clause = f"({found.group(3)})" if found.group(3) else ""
    return found.group(1), found.group(2) + clause


def correspondences(rows: Iterable[tuple[int, list[str]]]) -> list[Correspondence]:
    """Rows as (page, non-empty cells). One-cell rows continue the previous summary."""
    out: list[Correspondence] = []
    for page, cells in rows:
        if len(cells) == 1 and out:
            last = out[-1]
            out[-1] = Correspondence(
                last.bns_section, last.bns_sub, last.ipc, last.subject,
                f"{last.summary} {cells[0]}", last.page,
            )
            continue
        ref = parse_bns_ref(cells[0]) if len(cells) == 4 else None
        if ref is None:
            continue
        out.append(
            Correspondence(
                bns_section=ref[0],
                bns_sub=ref[1],
                ipc=parse_ipc_cell(cells[2]),
                subject=cells[1],
                summary=cells[3],
                page=page,
            )
        )
    return out


def read_rows(path: Path) -> list[tuple[int, list[str]]]:
    """Every table row in the PDF as (page, non-empty cells), wrapped lines unfolded."""
    rows: list[tuple[int, list[str]]] = []
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            for table in page.extract_tables():
                for row in table:
                    cells = [" ".join((c or "").split()) for c in row]
                    if filled := [c for c in cells if c]:
                        rows.append((number, filled))
    return rows


def require_consistent(
    found: list[Correspondence], *, bns: Set[str], ipc: Set[str]
) -> list[Correspondence]:
    """The table must cover every BNS section and cite only IPC sections we parsed.

    The second check is what found 171I and 376C missing from the IPC split, after
    that split had passed all of its own gates.
    """
    unmentioned = sorted(bns - {c.bns_section for c in found}, key=_numeric)
    if unmentioned:
        raise MappingParseError(f"BNS sections not in the table: {', '.join(unmentioned)}")
    unparsed = sorted({n for c in found for n in c.ipc} - ipc, key=_numeric)
    if unparsed:
        raise MappingParseError(f"IPC sections cited but not parsed: {', '.join(unparsed)}")
    return found


def _numeric(number: str) -> tuple[int, str]:
    digits = re.match(r"\d+", number)
    return (int(digits.group()) if digits else 0, number)

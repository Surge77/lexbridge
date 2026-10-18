"""Build the section corpus from the pinned PDFs, failing loudly if any split is short.

The splitters accept a heading only when it is next in sequence, so one malformed
heading in a new PDF revision silently drops every section after it. This module is the
only production path that runs them, and it refuses any result that does not cover the
code from section 1 to its last.
"""

from __future__ import annotations

from pathlib import Path

from lexbridge.ingest.layout import read_lines
from lexbridge.ingest.split_bns import split_bns
from lexbridge.ingest.split_consolidated import split_consolidated
from lexbridge.schema import Act, Section, section_key

# Base section numbers run 1..N in each code; lettered inserts (498A) come on top.
LAST_SECTION = {Act.BNS: 358, Act.IPC: 511}

# Measured on the PRS gazette: margin notes sit within 112pt of either edge (body text
# starts at x 118), and the running header ends above 75pt.
GAZETTE_MARGIN_WIDTH = 112.0
GAZETTE_SKIP_TOP = 75.0
# IndiaCode's watermark letters are 27-37pt; no text in either code is above 12pt.
WATERMARK_MAX_SIZE = 20.0


class IncompleteSplitError(ValueError):
    """A split did not cover every base section number from 1 to the last."""


def require_complete(
    sections: list[Section], *, source_key: str, expected_last: int
) -> list[Section]:
    found = {section_key(s.number)[0] for s in sections}
    missing = [n for n in range(1, expected_last + 1) if n not in found]
    if missing:
        last = sections[-1].number if sections else "nothing"
        raise IncompleteSplitError(
            f"{source_key}: parsed up to {last}, {len(missing)} missing from {missing[0]}"
        )
    return sections


def load_sections(raw_dir: Path) -> dict[str, list[Section]]:
    """Every corpus text, keyed by source, each verified complete."""
    gazette = read_lines(
        raw_dir / "bns_original.pdf",
        margin_width=GAZETTE_MARGIN_WIDTH,
        skip_top=GAZETTE_SKIP_TOP,
    )
    corpus = {"bns_original": split_bns(gazette, source_key="bns_original")}
    for key, act in (("bns_current", Act.BNS), ("ipc", Act.IPC)):
        lines = read_lines(
            raw_dir / f"{key}.pdf", max_size=WATERMARK_MAX_SIZE, footnote_rule=True
        )
        corpus[key] = split_consolidated(lines, act=act, source_key=key)
    act_of = {"bns_original": Act.BNS, "bns_current": Act.BNS, "ipc": Act.IPC}
    return {
        key: require_complete(found, source_key=key, expected_last=LAST_SECTION[act_of[key]])
        for key, found in corpus.items()
    }

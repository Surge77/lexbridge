"""Build the section corpus from the pinned PDFs, failing loudly if any split is short.

The splitters accept a heading only when it is next in sequence, so one malformed
heading in a new PDF revision silently drops every section after it. This module is the
only production path that runs them, and it refuses any result that does not cover the
code from section 1 to its last.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path

from lexbridge.ingest.fetch import PinMismatchError
from lexbridge.ingest.layout import read_lines
from lexbridge.ingest.mapping import (
    Correspondence,
    correspondences,
    read_rows,
    require_consistent,
)
from lexbridge.ingest.split_bns import split_bns
from lexbridge.ingest.split_consolidated import split_consolidated
from lexbridge.schema import Act, Section, section_key

# Base section numbers run 1..N in each code; lettered inserts (498A) come on top.
LAST_SECTION = {Act.BNS: 358, Act.IPC: 511}
ACT_OF = {"bns_original": Act.BNS, "bns_current": Act.BNS, "ipc": Act.IPC}
# Every section including lettered inserts and repealed ones, as measured on the pinned
# files. Base coverage cannot see a dropped insert (a malformed "354D." does not break
# the sequence), so the exact count is checked too. A new pin means re-measuring this.
SECTION_COUNT = {"bns_original": 358, "bns_current": 358, "ipc": 581}

# Measured on the PRS gazette: margin notes sit within 112pt of either edge (body text
# starts at x 118), and the running header ends above 75pt.
GAZETTE_MARGIN_WIDTH = 112.0
GAZETTE_SKIP_TOP = 75.0
# IndiaCode's watermark letters are 27-37pt; no text in either code is above 12pt.
WATERMARK_MAX_SIZE = 20.0


class IncompleteSplitError(ValueError):
    """A split is short, has a gap or a duplicate, or differs from the measured count."""


def require_complete(
    sections: list[Section], *, source_key: str, expected_last: int, expected_count: int
) -> list[Section]:
    found = {section_key(s.number)[0] for s in sections}
    missing = [n for n in range(1, expected_last + 1) if n not in found]
    if missing:
        last = sections[-1].number if sections else "nothing"
        raise IncompleteSplitError(
            f"{source_key}: parsed up to {last}, {len(missing)} missing from {missing[0]}"
        )
    repeated = sorted(n for n, k in Counter(s.number for s in sections).items() if k > 1)
    if repeated:
        raise IncompleteSplitError(f"{source_key}: duplicated: {', '.join(repeated)}")
    if len(sections) != expected_count:
        raise IncompleteSplitError(
            f"{source_key}: {len(sections)} sections, expected {expected_count}"
        )
    return sections


def verify_pins(raw_dir: Path, pins: Mapping[str, str], keys: Iterable[str]) -> None:
    """Refuse to parse a PDF that differs from its committed pin.

    fetch_all checks pins when it fetches, but a file edited or replaced in data/raw
    afterwards would otherwise be parsed as if it were the pinned statute.
    """
    for key in keys:
        if key not in pins:
            raise PinMismatchError(f"{key}: no pin in data/sources.json")
        actual = hashlib.sha256((raw_dir / f"{key}.pdf").read_bytes()).hexdigest()
        if actual != pins[key]:
            raise PinMismatchError(f"{key}: on disk {actual[:12]}, pinned {pins[key][:12]}")


def load_sections(raw_dir: Path, pins: Mapping[str, str]) -> dict[str, list[Section]]:
    """Every corpus text, keyed by source, each verified against its pin and complete."""
    verify_pins(raw_dir, pins, ACT_OF)
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
    return {
        key: require_complete(
            found,
            source_key=key,
            expected_last=LAST_SECTION[ACT_OF[key]],
            expected_count=SECTION_COUNT[key],
        )
        for key, found in corpus.items()
    }


def load_correspondences(
    raw_dir: Path, pins: Mapping[str, str], corpus: Mapping[str, list[Section]]
) -> list[Correspondence]:
    """The CAPT BNS-IPC table, verified against its pin and against the parsed codes."""
    verify_pins(raw_dir, pins, ["capt_correspondence"])
    found = correspondences(read_rows(raw_dir / "capt_correspondence.pdf"))
    return require_consistent(
        found,
        bns={s.number for s in corpus["bns_current"]},
        ipc={s.number for s in corpus["ipc"]},
    )

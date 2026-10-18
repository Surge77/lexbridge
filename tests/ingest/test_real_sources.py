"""The build's correctness gates, run against the real government PDFs.

Opt-in (`pytest -m integration`): the files are downloaded once into data/raw and reused.

Counts alone are not enough. The first IPC source parsed to a perfect 1..511 and was
still the wrong law: a pre-2013 consolidation without 354A-D or 376DB. So the IPC gate
also asserts that provisions inserted in 2013 and 2018 are present.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lexbridge.ingest.fetch import SOURCES, fetch_all, load_pins
from lexbridge.ingest.layout import read_lines
from lexbridge.ingest.split_bns import split_bns
from lexbridge.ingest.split_consolidated import split_consolidated
from lexbridge.schema import Act, Section, Status, section_key

pytestmark = pytest.mark.integration

DATA = Path(__file__).resolve().parents[2] / "data"
RAW = DATA / "raw"
# Inserted by the Criminal Law (Amendment) Acts of 2013 and 2018. Their absence means
# the source predates them, whatever the section count says.
IPC_LATE_INSERTS = ("166A", "354A", "354B", "354C", "354D", "376DB")


@pytest.fixture(scope="module")
def raw_dir() -> Path:
    # Verified against the committed pins: CI's cache must hold exactly those bytes.
    _, failures = fetch_all(SOURCES, RAW, pins=load_pins(DATA / "sources.json"))
    if failures:
        pytest.fail(f"could not fetch: {sorted(failures)}")
    return RAW


def _bases(sections: list[Section]) -> set[int]:
    return {section_key(s.number)[0] for s in sections}


def test_bns_gazette_has_sections_1_to_358_in_order_all_titled(raw_dir: Path) -> None:
    lines = read_lines(raw_dir / "bns_original.pdf", margin_width=112, skip_top=75)
    sections = split_bns(lines, source_key="bns_original")

    assert [s.number for s in sections] == [str(n) for n in range(1, 359)]
    assert all(s.title for s in sections)


def test_bns_consolidated_has_sections_1_to_358(raw_dir: Path) -> None:
    lines = read_lines(raw_dir / "bns_current.pdf", max_size=20, footnote_rule=True)
    sections = split_consolidated(lines, act=Act.BNS, source_key="bns_current")

    assert _bases(sections) == set(range(1, 359))
    assert all(s.title for s in sections)


def test_ipc_covers_1_to_511_and_is_the_last_amended_text(raw_dir: Path) -> None:
    lines = read_lines(raw_dir / "ipc.pdf", max_size=20, footnote_rule=True)
    sections = split_consolidated(lines, act=Act.IPC, source_key="ipc")
    by_number = {s.number: s for s in sections}

    assert _bases(sections) == set(range(1, 512))
    for number in IPC_LATE_INSERTS:
        assert number in by_number, f"IPC {number} missing: source predates 2013/2018"
        assert by_number[number].status is Status.IN_FORCE
    assert by_number["354D"].title == "Stalking"

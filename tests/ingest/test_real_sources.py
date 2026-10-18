"""The build's correctness gates, run against the real government PDFs.

Opt-in (`pytest -m integration`): the files are fetched once into data/raw, verified
against the committed pins, and reused.

load_sections already refuses any split that does not cover 1..N. Counts alone are not
enough, though. The first IPC source parsed to a perfect 1..511 and was still the wrong
law: a pre-2013 consolidation without 354A-D or 376DB. So the IPC gate also asserts
that provisions inserted in 2013 and 2018 are present.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lexbridge.ingest.corpus import load_sections
from lexbridge.ingest.fetch import SOURCES, fetch_all, load_pins
from lexbridge.schema import Section, Status

pytestmark = pytest.mark.integration

DATA = Path(__file__).resolve().parents[2] / "data"
# Inserted by the Criminal Law (Amendment) Acts of 2013 and 2018. Their absence means
# the source predates them, whatever the section count says.
IPC_LATE_INSERTS = ("166A", "354A", "354B", "354C", "354D", "376DB")


@pytest.fixture(scope="module")
def corpus() -> dict[str, list[Section]]:
    raw = DATA / "raw"
    _, failures = fetch_all(SOURCES, raw, pins=load_pins(DATA / "sources.json"))
    if failures:
        pytest.fail(f"could not fetch: {sorted(failures)}")
    return load_sections(raw)


@pytest.mark.parametrize("key", ["bns_original", "bns_current", "ipc"])
def test_every_section_has_a_title_and_text(corpus: dict[str, list[Section]], key: str) -> None:
    untitled = [s.number for s in corpus[key] if not s.title or not s.text]
    assert untitled == []


def test_the_bns_gazette_runs_1_to_358_in_order(corpus: dict[str, list[Section]]) -> None:
    assert [s.number for s in corpus["bns_original"]] == [str(n) for n in range(1, 359)]


def test_the_ipc_is_the_last_amended_text(corpus: dict[str, list[Section]]) -> None:
    by_number = {s.number: s for s in corpus["ipc"]}

    for number in IPC_LATE_INSERTS:
        assert number in by_number, f"IPC {number} missing: source predates 2013/2018"
        assert by_number[number].status is Status.IN_FORCE
    assert by_number["354D"].title == "Stalking"
    assert by_number["420"].title == "Cheating and dishonestly inducing delivery of property"

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from lexbridge.ingest.corpus import IncompleteSplitError, require_complete, verify_pins
from lexbridge.ingest.fetch import PinMismatchError
from lexbridge.schema import Act, Section, Status


def sections(*numbers: str) -> list[Section]:
    return [
        Section(act=Act.IPC, number=n, title=f"T{n}", text=f"{n}. T.", chapter=None,
                status=Status.IN_FORCE, source_key="ipc", page=1)
        for n in numbers
    ]


def test_a_complete_split_is_returned_unchanged() -> None:
    parsed = sections("1", "2", "2A", "3")

    assert require_complete(parsed, source_key="ipc", expected_last=3, expected_count=4) == parsed


def test_a_split_that_stops_early_is_an_error_naming_where_it_stopped() -> None:
    # A broken heading drops every later section; this must fail the build, not shrink it.
    with pytest.raises(IncompleteSplitError, match=r"ipc: parsed up to 2, 2 missing from 3"):
        require_complete(sections("1", "2"), source_key="ipc", expected_last=4, expected_count=4)


def test_a_gap_in_the_middle_is_an_error() -> None:
    with pytest.raises(IncompleteSplitError, match="1 missing from 2"):
        require_complete(sections("1", "3"), source_key="ipc", expected_last=3, expected_count=3)


def test_an_empty_split_is_an_error() -> None:
    with pytest.raises(IncompleteSplitError, match="parsed up to nothing"):
        require_complete([], source_key="bns_current", expected_last=358, expected_count=358)


def test_a_dropped_lettered_insert_is_an_error_even_with_every_base_present() -> None:
    # A malformed "2A." heading does not cascade, so base coverage alone cannot see it.
    with pytest.raises(IncompleteSplitError, match="3 sections, expected 4"):
        require_complete(sections("1", "2", "3"), source_key="ipc", expected_last=3,
                         expected_count=4)


def test_a_duplicated_section_is_an_error() -> None:
    with pytest.raises(IncompleteSplitError, match="duplicated: 2"):
        require_complete(sections("1", "2", "2", "3"), source_key="ipc", expected_last=3,
                         expected_count=4)


def test_a_pdf_that_changed_on_disk_after_fetch_is_refused(tmp_path: Path) -> None:
    (tmp_path / "ipc.pdf").write_bytes(b"%PDF-1.7 edited")
    pinned = hashlib.sha256(b"%PDF-1.7 original").hexdigest()

    with pytest.raises(PinMismatchError, match="ipc"):
        verify_pins(tmp_path, {"ipc": pinned}, ["ipc"])


def test_a_source_without_a_pin_is_refused(tmp_path: Path) -> None:
    (tmp_path / "ipc.pdf").write_bytes(b"%PDF-1.7")

    with pytest.raises(PinMismatchError, match="no pin"):
        verify_pins(tmp_path, {}, ["ipc"])


def test_files_matching_their_pins_pass(tmp_path: Path) -> None:
    (tmp_path / "ipc.pdf").write_bytes(b"%PDF-1.7")

    verify_pins(tmp_path, {"ipc": hashlib.sha256(b"%PDF-1.7").hexdigest()}, ["ipc"])

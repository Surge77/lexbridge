from __future__ import annotations

import pytest

from lexbridge.ingest.corpus import IncompleteSplitError, require_complete
from lexbridge.schema import Act, Section, Status


def sections(*numbers: str) -> list[Section]:
    return [
        Section(act=Act.IPC, number=n, title=f"T{n}", text=f"{n}. T.", chapter=None,
                status=Status.IN_FORCE, source_key="ipc", page=1)
        for n in numbers
    ]


def test_a_complete_split_is_returned_unchanged() -> None:
    parsed = sections("1", "2", "2A", "3")

    assert require_complete(parsed, source_key="ipc", expected_last=3) == parsed


def test_a_split_that_stops_early_is_an_error_naming_where_it_stopped() -> None:
    # A broken heading drops every later section; this must fail the build, not shrink it.
    with pytest.raises(IncompleteSplitError, match=r"ipc: parsed up to 2, 2 missing from 3"):
        require_complete(sections("1", "2"), source_key="ipc", expected_last=4)


def test_a_gap_in_the_middle_is_an_error() -> None:
    with pytest.raises(IncompleteSplitError, match="1 missing from 2"):
        require_complete(sections("1", "3"), source_key="ipc", expected_last=3)


def test_an_empty_split_is_an_error() -> None:
    with pytest.raises(IncompleteSplitError, match="parsed up to nothing"):
        require_complete([], source_key="bns_current", expected_last=358)

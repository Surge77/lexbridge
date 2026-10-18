"""Every cell below is copied from the CAPT Bhopal BNS-IPC correspondence table."""

from __future__ import annotations

import pytest

from lexbridge.ingest.mapping import (
    MappingParseError,
    correspondences,
    parse_bns_ref,
    parse_ipc_cell,
    require_consistent,
)


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ("420", ("420",)),
        ("366A", ("366A",)),
        ("363A,", ("363A",)),
        ("29 and 29A", ("29", "29A")),
        ("54 & 55", ("54", "55")),
        ("23 Clause-1", ("23",)),
        ("376(1) & 376(2)", ("376",)),
        ("228A (1)/(2)", ("228A",)),
        ("498A Explanat ion", ("498A",)),
        ("171-I", ("171I",)),
        ("428/ 429", ("428", "429")),
        ("233 / 234 / 235 / 256 / 257 / 489D", ("233", "234", "235", "256", "257", "489D")),
        ("230 to 232, 246 to 249, 255, 489A",
         ("230", "231", "232", "246", "247", "248", "249", "255", "489A")),
    ],
)
def test_ipc_cells_parse_to_section_numbers(cell: str, expected: tuple[str, ...]) -> None:
    assert parse_ipc_cell(cell) == expected


@pytest.mark.parametrize("cell", ["New", "new", "-", "New sub- section"])
def test_markers_of_a_new_provision_map_to_nothing(cell: str) -> None:
    assert parse_ipc_cell(cell) == ()


@pytest.mark.parametrize("cell", ["see notes", "420 or so", ""])
def test_an_unrecognised_cell_is_an_error_not_a_silent_drop(cell: str) -> None:
    with pytest.raises(MappingParseError):
        parse_ipc_cell(cell)


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ("318", ("318", "")),
        ("1(2)", ("1", "(2)")),
        ("103 (2)", ("103", "(2)")),
        ("197 (1)d", ("197", "(1)(d)")),
        ("2(36)", ("2", "(36)")),
        ("309 (1), (2), (3)", ("309", "(1)/(2)/(3)")),
        ("351 (2)/ (3)", ("351", "(2)/(3)")),
        ("189 (8)/ (9)", ("189", "(8)/(9)")),
        ("Explanati on to section 5", ("5", "Explanation")),
    ],
)
def test_bns_references_split_into_section_and_subsection(
    cell: str, expected: tuple[str, str]
) -> None:
    assert parse_bns_ref(cell) == expected


def test_bns_references_that_are_not_references_are_none() -> None:
    assert parse_bns_ref("Sections/") is None
    assert parse_bns_ref("BNS") is None


ROWS = [
    (1, ["BNS", "Subject", "IPC / Sections", "Summary of comparison"]),
    (1, ["Sections/"]),
    (11, ["94", "Concealment of birth by secret disposal of dead body.", "318", "No change."]),
    (11, ["95", "Hiring, employing or engaging a child to commit an offence.", "-",
          "“Whoever hires, employs or engages any child"]),
    (12, ["to commit an offence shall be punished.”"]),
    (11, ["103 (2)", "Punishment for murder.", "-", "Mob lynching is a new offence."]),
]


def test_rows_become_correspondences_and_wrapped_summaries_are_joined() -> None:
    found = correspondences(ROWS)

    assert [(c.bns_section, c.bns_sub, c.ipc) for c in found] == [
        ("94", "", ("318",)),
        ("95", "", ()),
        ("103", "(2)", ()),
    ]
    assert found[1].summary.endswith("shall be punished.”")
    assert found[0].page == 11


def test_a_consistent_table_passes() -> None:
    found = correspondences(ROWS[2:])

    assert require_consistent(found, bns={"94", "95", "103"}, ipc={"318"}) == found


def test_a_bns_section_the_table_never_mentions_is_an_error() -> None:
    with pytest.raises(MappingParseError, match="BNS sections not in the table: 96"):
        require_consistent(correspondences(ROWS[2:]), bns={"94", "95", "96", "103"},
                           ipc={"318"})


def test_an_ipc_section_cited_but_absent_from_the_corpus_is_an_error() -> None:
    # How 171I and 376C were found missing from the IPC split.
    with pytest.raises(MappingParseError, match="IPC sections cited but not parsed: 318"):
        require_consistent(correspondences(ROWS[2:]), bns={"94", "95", "103"}, ipc=set())


def test_a_data_row_whose_bns_reference_cannot_be_read_is_an_error() -> None:
    # Rows like "351 (2)/ (3)" were once skipped silently, losing IPC 506 -> BNS 351.
    rows = [(37, ["351 (2) or so", "Criminal intimidation punishment.", "506", "Ditto."])]

    with pytest.raises(MappingParseError, match="BNS reference"):
        correspondences(rows)

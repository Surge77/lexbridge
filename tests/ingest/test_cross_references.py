"""Inputs below are taken from the real statute text, where the review found false edges."""

from __future__ import annotations

import pytest

from lexbridge.ingest.graph import cross_references
from lexbridge.schema import Act

KNOWN = ["8", "9", "52", "52A", "53", "255", "256", "263", "263A"]


@pytest.mark.parametrize(
    "text",
    [
        "within the meaning of section 3 of\nthe General Clauses Act, 1897",
        "under section 109 of the Code of Criminal Procedure, 1973",
        "a proclamation under section 84 of Bharatiya Nagarik Suraksha Sanhita, 2023",
        "as defined in section 3 of that Act",
        "the provisions of section 13 of the said Act",
        "section 2 of Motor Vehicles Act 1988",
        "section 3 and section 4 of the Arms Act",
        "sections 3 and 4 of the Arms Act",
    ],
)
def test_a_section_of_another_act_is_not_a_reference(text: str) -> None:
    assert cross_references(text, Act.IPC) == ()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("as defined in section 2", ("2",)),
        ("under sections 115 and 117", ("115", "117")),
        ("sections 76, 79, and 81", ("76", "79", "81")),
        ("Section 354, 354A, 354B", ("354", "354A", "354B")),
        ("section 498A of this Code", ("498A",)),
        ("section 124A of the Indian Penal Code", ("124A",)),
        ("or sub-section (2), or section 5", ("5",)),
    ],
)
def test_same_code_references_are_found(text: str, expected: tuple[str, ...]) -> None:
    assert cross_references(text, Act.IPC) == expected


def test_the_bns_names_itself_and_not_the_bnss() -> None:
    text = ("section 64 of the Bharatiya Nyaya Sanhita, or section 84 of the Bharatiya "
            "Nagarik Suraksha Sanhita")

    assert cross_references(text, Act.BNS) == ("64",)


def test_a_range_expands_over_the_sections_that_exist() -> None:
    assert cross_references("sections 8 to 52A", Act.IPC, KNOWN) == ("8", "9", "52", "52A")


def test_without_the_known_sections_a_range_keeps_its_endpoints() -> None:
    assert cross_references("sections 255 to 263", Act.IPC) == ("255", "263")


def test_a_longer_number_is_not_truncated_to_a_section() -> None:
    assert cross_references("section 12345", Act.IPC) == ()

from __future__ import annotations

from lexbridge.ingest.layout import Column, Line
from lexbridge.ingest.split_bns import split_bns
from lexbridge.schema import Act, Status


def body(page: int, top: float, text: str, x0: float = 142) -> Line:
    return Line(page=page, top=top, x0=x0, size=10, text=text, column="body")


def note(page: int, top: float, text: str, column: Column = "margin") -> Line:
    return Line(page=page, top=top, x0=58, size=8, text=text, column=column)


LINES = [
    body(1, 90, "THE BHARATIYA NYAYA SANHITA, 2023", x0=200),
    body(1, 110, "CHAPTER I", x0=272),
    body(1, 122, "PRELIMINARY", x0=266),
    body(1, 140, "1. (1) This Act may be called the Bharatiya Nyaya Sanhita, 2023."),
    note(1, 141, "Short title and"),
    note(1, 150, "commencement."),
    body(1, 152, "(2) It shall come into force on such date.", x0=142),
    body(1, 170, "2. In this Sanhita, unless the context otherwise requires,—"),
    note(1, 171, "Definitions."),
    # A numbered clause inside section 2, not a new section: out of sequence.
    body(1, 182, "5. \"Court\" means a Judge who is empowered by law;", x0=166),
    body(2, 90, "CHAPTER II", x0=272),
    body(2, 102, "OF PUNISHMENTS", x0=266),
    body(2, 120, "3. The punishments to which offenders are liable are—"),
    note(2, 121, "Punishments."),
    body(2, 132, "(a) Death;", x0=166),
]


def test_each_numbered_heading_in_sequence_starts_a_section() -> None:
    sections = split_bns(LINES, source_key="bns_original")

    assert [s.number for s in sections] == ["1", "2", "3"]
    assert all(s.act is Act.BNS and s.status is Status.IN_FORCE for s in sections)


def test_a_numbered_clause_out_of_sequence_stays_in_its_section() -> None:
    sections = split_bns(LINES, source_key="bns_original")

    assert '5. "Court" means a Judge' in sections[1].text


def test_titles_come_from_the_margin_note_beside_the_heading() -> None:
    sections = split_bns(LINES, source_key="bns_original")

    assert [s.title for s in sections] == [
        "Short title and commencement.",
        "Definitions.",
        "Punishments.",
    ]


def test_chapter_headings_are_attached_not_left_in_the_text() -> None:
    sections = split_bns(LINES, source_key="bns_original")

    assert sections[0].chapter == "I — PRELIMINARY"
    assert sections[2].chapter == "II — OF PUNISHMENTS"
    assert all("CHAPTER" not in s.text for s in sections)


def test_text_keeps_the_heading_and_its_continuation_lines() -> None:
    sections = split_bns(LINES, source_key="bns_original")

    assert sections[2].text == "3. The punishments to which offenders are liable are—\n(a) Death;"
    assert sections[2].page == 2


def test_preamble_before_section_one_is_dropped() -> None:
    sections = split_bns(LINES, source_key="bns_original")

    assert all("BHARATIYA NYAYA SANHITA, 2023" not in s.text for s in sections)


def test_a_heading_with_no_space_after_the_full_stop_still_starts_a_section() -> None:
    # Measured on the gazette: "192.Whoever malignantly..." has no space at any tolerance.
    lines = [body(1, 100, "1. First."), body(1, 120, "2.Whoever malignantly gives provocation")]

    assert [s.number for s in split_bns(lines, source_key="x")] == ["1", "2"]


def test_a_decimal_is_not_mistaken_for_a_heading() -> None:
    lines = [body(1, 100, "1. First."), body(1, 120, "2.5 per cent of the value.", x0=118)]

    assert [s.number for s in split_bns(lines, source_key="x")] == ["1"]


def test_a_margin_note_slightly_above_its_heading_is_still_its_title() -> None:
    lines = [body(1, 128, "1. Any man who follows a woman"), note(1, 124.6, "Stalking.")]

    assert split_bns(lines, source_key="x")[0].title == "Stalking."


def test_margin_references_to_other_acts_are_not_part_of_the_title() -> None:
    lines = [
        body(1, 100, "1. Where the death of a woman is caused"),
        note(1, 101, "Dowry death."),
        note(1, 110, "28 of 1961."),
        body(1, 130, "2. Persons subject to certain Acts."),
        note(1, 131, "Persons subject 45 of 1950."),
        note(1, 140, "to certain Acts."),
    ]

    titles = [s.title for s in split_bns(lines, source_key="x")]
    assert titles == ["Dowry death.", "Persons subject to certain Acts."]


def test_the_signature_and_colophon_after_the_closing_rule_are_dropped() -> None:
    lines = [
        body(1, 100, "1. Repeal and savings."),
        note(1, 101, "Repeal and"),
        note(1, 110, "savings."),
        body(1, 130, "—————", x0=280),
        body(1, 140, "DIWAKAR SINGH,", x0=400),
        note(1, 300, "UP 002 MGIPMRND"),
    ]

    section = split_bns(lines, source_key="x")[0]
    assert section.text == "1. Repeal and savings."
    assert section.title == "Repeal and savings."


def test_a_section_without_a_margin_note_gets_an_empty_title() -> None:
    lines = [body(1, 100, "1. Untitled provision.")]

    assert split_bns(lines, source_key="x")[0].title == ""

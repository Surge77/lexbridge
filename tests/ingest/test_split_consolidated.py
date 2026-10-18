"""Fixtures reproduce forms measured in IndiaCode's consolidated IPC and BNS PDFs."""

from __future__ import annotations

from lexbridge.ingest.layout import Line
from lexbridge.ingest.split_consolidated import split_consolidated
from lexbridge.schema import Act, Status


def page(number: int, *texts: str | tuple[str, float]) -> list[Line]:
    lines = []
    for i, item in enumerate(texts):
        text, size = item if isinstance(item, tuple) else (item, 11.0)
        lines.append(Line(page=number, top=70 + 13 * i, x0=72, size=size, text=text,
                          column="body"))
    return lines


TOC = page(1, "ARRANGEMENT OF SECTIONS", "CHAPTER I", "INTRODUCTION",
           "1. Title and extent of operation of the Code.",
           "2. Punishment of offences committed within India.",
           "3. [Omitted.].")

BODY = page(
    14,
    "CHAPTER I", "INTRODUCTION",
    "1. Title and extent of operation of the Code.—This Act shall be called the",
    "Indian Penal Code.",
    "2. Punishment of offences committed within India.—Every person shall be",
    "liable to punishment under this Code.",
    "3. [Definition of “Queen”.] Omitted by the A. O. 1950.",
    "4. [Definition of “British India”.] Rep. by the A. O. 1937.",
    "14",
) + page(
    15,
    "1[CHAPTER VA", "CRIMINAL CONSPIRACY",
    "1[4A. Definition of criminal conspiracy.—When two or more persons agree,]",
    "2[4B.Punishment for gang rape on woman under twelve years of age.—Where a",
    "woman under twelve years of age is raped.]",
    "5. Punishment for attempting to commit offences punishable with imprisonment",
    "for life or other imprisonment.—Whoever attempts to commit an offence.",
)


def split(lines: list[Line]):
    return {s.number: s for s in split_consolidated(lines, act=Act.IPC, source_key="ipc")}


def test_headings_in_sequence_become_sections_and_the_contents_list_is_skipped() -> None:
    sections = split(TOC + BODY)

    assert list(sections) == ["1", "2", "3", "4", "4A", "4B", "5"]
    assert sections["1"].page == 14


def test_titles_end_at_the_em_dash_even_a_line_later() -> None:
    sections = split(TOC + BODY)

    assert sections["1"].title == "Title and extent of operation of the Code"
    assert sections["4B"].title == "Punishment for gang rape on woman under twelve years of age"
    assert sections["5"].title == (
        "Punishment for attempting to commit offences punishable with imprisonment "
        "for life or other imprisonment"
    )


def test_omitted_and_repealed_sections_are_recorded_as_repealed() -> None:
    sections = split(TOC + BODY)

    assert sections["3"].status is Status.REPEALED
    assert sections["3"].title == "Definition of “Queen”"
    assert sections["4"].status is Status.REPEALED
    assert sections["2"].status is Status.IN_FORCE


def test_page_numbers_stay_out_of_the_text() -> None:
    sections = split(TOC + BODY)

    assert sections["4"].text == "4. [Definition of “British India”.] Rep. by the A. O. 1937."


def test_amendment_markers_are_reduced_to_their_bracket() -> None:
    sections = split(TOC + BODY)

    assert sections["4A"].text == (
        "[4A. Definition of criminal conspiracy.—When two or more persons agree,]"
    )


def test_chapters_attach_including_an_inserted_one() -> None:
    sections = split(TOC + BODY)

    assert sections["2"].chapter == "I — INTRODUCTION"
    assert sections["4A"].chapter == "VA — CRIMINAL CONSPIRACY"


def test_the_act_is_taken_from_the_caller() -> None:
    lines = page(1, "1. Short title.—(1) This Act may be called the Sanhita.")

    (section,) = split_consolidated(lines, act=Act.BNS, source_key="bns_current")

    assert section.id == "BNS:1"
    assert section.source_key == "bns_current"


def test_a_chapter_whose_name_was_filtered_out_does_not_swallow_the_next_heading() -> None:
    # IPC p15: the chapter name is set below body size, so "6." follows "CHAPTER II".
    lines = page(1, "1. First.—Text.", "CHAPTER II", "2. Definitions.—Throughout this Code.")

    sections = split(lines)

    assert list(sections) == ["1", "2"]
    assert sections["2"].chapter == "II"


def test_two_en_dashes_also_end_a_title() -> None:
    # The consolidated BNS ends titles with U+2013 twice, not an em dash.
    lines = page(1, "1. Short title, commencement and application.\u2013\u2013(1) This Act.")

    (section,) = split_consolidated(lines, act=Act.BNS, source_key="bns_current")

    assert section.title == "Short title, commencement and application"


def test_a_title_missing_its_stop_before_the_dash_still_ends_there() -> None:
    lines = page(1, "1. False information to injury of", "another person\u2014Whoever gives.")

    (section,) = split_consolidated(lines, act=Act.BNS, source_key="bns_current")

    assert section.title == "False information to injury of another person"


def test_a_marked_heading_may_omit_the_stop_after_its_number() -> None:
    lines = page(1, "1. First.\u2014Text.", "1[2 \u201cGovernment\u201d.\u2014The word denotes.]")

    assert list(split(lines)) == ["1", "2"]


def test_an_unmarked_line_without_the_stop_is_never_a_heading() -> None:
    lines = page(1, "1. First.\u2014Text.", "2 rupees, or with both\u2014and the fine.")

    assert list(split(lines)) == ["1"]


def test_a_repealed_title_wrapping_onto_the_next_line_is_recorded() -> None:
    lines = page(1, "1. First.\u2014Text.",
                 "2. [Sentence of Europeans to penal servitude. Proviso as to",
                 "term exceeding ten years.] Rep. by Act 17 of 1949.", "3. Third.\u2014Text.")

    sections = split(lines)
    assert list(sections) == ["1", "2", "3"]
    assert sections["2"].status is Status.REPEALED


def test_a_title_wrapping_onto_a_cross_reference_still_ends_at_its_dash() -> None:
    lines = page(1, "1. First.\u2014Text.",
                 "2. Making counterfeit seal to commit forgery punishable under section",
                 "1.\u2014Whoever makes or counterfeits any seal.")

    sections = split(lines)
    assert list(sections) == ["1", "2"]
    assert sections["2"].title.endswith("punishable under section 1")


def test_a_stray_dash_straight_after_the_number_is_not_the_title_end() -> None:
    lines = page(1, "1.\u2014Public servant disobeying direction of law.\u2014Whoever, being.")

    (section,) = split_consolidated(lines, act=Act.BNS, source_key="bns_current")

    assert section.title == "Public servant disobeying direction of law"

"""Each fixture below reproduces a structure measured in IndiaCode's IPC typescript."""

from __future__ import annotations

from lexbridge.ingest.layout import Line
from lexbridge.ingest.split_ipc import drop_page_furniture, split_ipc
from lexbridge.schema import Act, Status

RULE = "-" * 60


def page(number: int, *texts: str) -> list[Line]:
    return [
        Line(page=number, top=80 + 11 * i, x0=90, size=10, text=t, column="body")
        for i, t in enumerate(texts)
    ]


def texts(lines: list[Line]) -> list[str]:
    return [line.text for line in lines]


def test_footnotes_after_the_rule_are_dropped_with_the_page_number() -> None:
    lines = page(10, "23. Wrongful gain.--Gain by unlawful means.", RULE,
                 "1. Ins. by Act 39 of 1920, s. 2.", "106")

    assert texts(drop_page_furniture(lines)) == ["23. Wrongful gain.--Gain by unlawful means."]


def test_overflow_footnotes_before_a_rule_that_is_followed_by_the_page_number() -> None:
    # Page 55: the previous page's footnotes spill onto the top, then rule, then "128".
    lines = page(55, "3. The words \"or to deprive the Queen\" omitted by the A. O. 1950.",
                 RULE, "128", "shall be punished with imprisonment.")

    assert texts(drop_page_furniture(lines)) == ["shall be punished with imprisonment."]


SAMPLE = (
    page(1, "CHAPTER I", "INTRODUCTION",
         "1. Title and extent.--This Act shall be called the Indian Penal Code.",
         "2. Punishment of offences.--Every person shall be liable.")
    + page(2, "CHAPTER VA", "CRIMINAL CONSPIRACY",
           # Margin repeat of the heading, which must not leak into section 2's text.
           "3.", "Punishment of conspiracy.",
           "3. Punishment of conspiracy.--Whoever is a party.",
           "3A.", "Sedition.",
           "1*[3A. Sedition.--Whoever by words brings into 2***hatred",
           "3*[India], shall be punished.]",
           "4. [Transportation instead of imprisonment.] Rep. by Act 26 of 1955.",
           "5 to 6A.Rep. by the Prevention of Corruption Act, 1988.",
           "7. Negligent act likely to spread infection of disease",
           "dangerous to life.--Whoever unlawfully does any act.")
)


def test_headings_in_sequence_become_sections_including_inserted_ones() -> None:
    sections = split_ipc(SAMPLE, source_key="ipc")

    assert [s.number for s in sections] == ["1", "2", "3", "3A", "4", "5", "6", "6A", "7"]
    assert all(s.act is Act.IPC for s in sections)


def test_the_margin_repeat_of_a_heading_is_not_left_in_the_previous_section() -> None:
    sections = {s.number: s for s in split_ipc(SAMPLE, source_key="ipc")}

    assert sections["2"].text == "2. Punishment of offences.--Every person shall be liable."
    assert "Sedition." not in sections["3"].text


def test_titles_are_the_words_before_the_double_dash_even_across_a_line_break() -> None:
    sections = {s.number: s for s in split_ipc(SAMPLE, source_key="ipc")}

    assert sections["1"].title == "Title and extent"
    assert sections["3A"].title == "Sedition"
    assert sections["7"].title == (
        "Negligent act likely to spread infection of disease dangerous to life"
    )


def test_amendment_markers_are_removed_from_the_text() -> None:
    sections = {s.number: s for s in split_ipc(SAMPLE, source_key="ipc")}

    assert sections["3A"].text == (
        "[3A. Sedition.--Whoever by words brings into hatred\n[India], shall be punished.]"
    )


def test_repealed_sections_and_ranges_are_recorded_as_repealed() -> None:
    sections = {s.number: s for s in split_ipc(SAMPLE, source_key="ipc")}

    assert sections["4"].status is Status.REPEALED
    assert sections["4"].title == "Transportation instead of imprisonment"
    assert [sections[n].status for n in ("5", "6", "6A")] == [Status.REPEALED] * 3
    assert sections["3"].status is Status.IN_FORCE


def test_chapters_include_lettered_ones() -> None:
    sections = {s.number: s for s in split_ipc(SAMPLE, source_key="ipc")}

    assert sections["1"].chapter == "I — INTRODUCTION"
    assert sections["3"].chapter == "VA — CRIMINAL CONSPIRACY"


def test_a_footnote_numbered_like_the_next_section_is_not_a_heading() -> None:
    lines = page(1, "1. Title.--Text.", "2. Subs. by Act 26 of 1955, for \"transportation\".")

    assert [s.number for s in split_ipc(lines, source_key="ipc")] == ["1"]


def test_body_after_the_page_number_survives_a_mid_page_footnote_block() -> None:
    # Page 5: the previous page's tail, rule, footnotes, page number, then this page.
    lines = page(5, "10. Man.--The word man denotes a male.", RULE,
                 "1. Subs. by Act 3 of 1951.", "103",
                 "11. Person.--The word person includes any Company.")

    assert texts(drop_page_furniture(lines)) == [
        "10. Man.--The word man denotes a male.",
        "11. Person.--The word person includes any Company.",
    ]


def test_a_marked_heading_missing_its_full_stop_still_counts() -> None:
    lines = page(1, "1. First.--Text.", "2*[2 \"Government\".--The word Government denotes.]")

    sections = split_ipc(lines, source_key="ipc")
    assert [s.number for s in sections] == ["1", "2"]
    assert sections[1].title == '"Government"'


def test_a_section_repealed_with_only_its_margin_entry_is_still_recorded() -> None:
    # Page 5/6: "13." then "[Definition of "Queen".] Rep. by the A. O. 1950." and nothing
    # else; IndiaCode sometimes drops the opening bracket too.
    lines = page(1, "1. First.--Text.",
                 "2.", "[Definition of \"Queen\".] Rep. by the A. O. 1950.",
                 "3.", "Definition of \"Government of India\".] Rep., ibid.",
                 "4. Fourth.--Text.")

    sections = {s.number: s for s in split_ipc(lines, source_key="ipc")}
    assert list(sections) == ["1", "2", "3", "4"]
    assert sections["2"].status is Status.REPEALED
    assert sections["2"].title == 'Definition of "Queen"'
    assert sections["3"].title == 'Definition of "Government of India"'
    assert "Rep." not in sections["1"].text


def test_a_repealed_title_spanning_lines_is_still_a_heading() -> None:
    lines = page(1, "1. First.--Text.",
                 "2. [Sentence of Europeans and Americans to penal servitude.",
                 "Proviso as to sentence for term exceeding ten years.]",
                 "Rep. by the Criminal Law Act, 1949 (17 of 1949).",
                 "3. Third.--Text.")

    sections = {s.number: s for s in split_ipc(lines, source_key="ipc")}
    assert list(sections) == ["1", "2", "3"]
    assert sections["2"].status is Status.REPEALED


def test_a_footnote_line_does_not_borrow_the_next_headings_double_dash() -> None:
    lines = page(1, "1. First.--Text.", "2. Subs. by Act 26 of 1955.", "2. Second.--Text.")

    sections = split_ipc(lines, source_key="ipc")
    assert [s.number for s in sections] == ["1", "2"]
    assert sections[1].title == "Second"


def test_a_rule_closing_this_pages_footnotes_does_not_drop_the_page_top() -> None:
    # Page 111: "58." at the top, rule, footnotes, a second rule, page number, "59.".
    lines = page(111, "58. [Offenders sentenced.] Rep. by Act 26 of 1955.", RULE,
                 "1. Ins. by Act 26 of 1955.", RULE, "111",
                 "59. [Transportation.] Rep. by Act 26 of 1955.")

    assert texts(drop_page_furniture(lines)) == [
        "58. [Offenders sentenced.] Rep. by Act 26 of 1955.",
        "59. [Transportation.] Rep. by Act 26 of 1955.",
    ]


def test_a_single_hyphen_after_the_title_ends_it_when_the_body_follows() -> None:
    lines = page(1, "1. First.--Text.", "2. Act done in good faith without",
                 "consent.-Nothing is an offence by reason of any harm.")

    sections = split_ipc(lines, source_key="ipc")
    assert sections[1].title == "Act done in good faith without consent"


def test_a_semicolon_before_the_double_dash_ends_the_title() -> None:
    lines = page(1, "1. First.--Text.",
                 "2. Being hired to take part in an unlawful assembly or riot;--",
                 "Whoever is engaged.")

    assert split_ipc(lines, source_key="ipc")[1].title == (
        "Being hired to take part in an unlawful assembly or riot"
    )


def test_a_misprinted_heading_number_is_corrected_from_its_margin_repeat() -> None:
    # IndiaCode prints "320." for section 330; the margin repeat says "330.".
    lines = page(1, "1. First.--Text.",
                 "2.", "Voluntarily causing hurt to extort confession or to compel",
                 "restoration of property.",
                 "9. Voluntarily causing hurt to extort confession or to compel",
                 "restoration of property.--Whoever voluntarily causes hurt.")
    corrections: list[str] = []

    sections = split_ipc(lines, source_key="ipc", corrections=corrections)

    assert [s.number for s in sections] == ["1", "2"]
    assert sections[1].text.startswith("2. Voluntarily causing hurt")
    assert corrections == ["IPC 2: heading printed as 9"]


def test_an_insert_marker_without_a_bracket_is_still_a_heading() -> None:
    lines = page(1, "1. First.--Text.", "2.", "Property mark.",
                 "1*2. Property mark.--A mark used for denoting that movable property.")

    sections = split_ipc(lines, source_key="ipc")
    assert [s.number for s in sections] == ["1", "2"]
    assert sections[1].title == "Property mark"

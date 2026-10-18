from __future__ import annotations

from pathlib import Path

import pytest

from lexbridge.ingest.layout import read_lines

from .pdf_factory import Rule, Text, write_pdf


@pytest.fixture
def gazette(tmp_path: Path) -> Path:
    """Two pages shaped like the BNS gazette: header, margin note beside the body."""
    return write_pdf(
        tmp_path / "gazette.pdf",
        [
            [
                Text(122, 40, 8, "8 THE GAZETTE OF INDIA EXTRAORDINARY"),
                Text(58, 160, 8, "Punishments."),
                Text(142, 160, 10, "4. The punishments to which offenders are liable"),
                Text(118, 172, 10, "are as follows."),
            ],
            [
                Text(142, 200, 10, "5. The appropriate Government may commute"),
                Text(490, 200, 8, "Commutation"),
                Text(490, 209, 8, "of sentence."),
            ],
        ],
    )


def test_margin_notes_are_kept_apart_from_the_body_line_beside_them(gazette: Path) -> None:
    lines = read_lines(gazette, margin_width=112, skip_top=75)

    margin = [line.text for line in lines if line.column == "margin"]
    body = [line.text for line in lines if line.column == "body"]
    assert margin == ["Punishments.", "Commutation", "of sentence."]
    assert body[0] == "4. The punishments to which offenders are liable"


def test_lines_carry_page_position_and_font_size(gazette: Path) -> None:
    lines = read_lines(gazette, margin_width=112, skip_top=75)

    first = next(line for line in lines if line.text.startswith("4."))
    assert first.page == 1
    assert first.size == pytest.approx(10)
    assert first.top == pytest.approx(160, abs=2)
    assert next(line for line in lines if line.text.startswith("5.")).page == 2


def test_the_running_header_is_skipped(gazette: Path) -> None:
    lines = read_lines(gazette, margin_width=112, skip_top=75)

    assert not any("GAZETTE" in line.text for line in lines)


def test_without_a_margin_everything_is_body(gazette: Path) -> None:
    lines = read_lines(gazette)

    assert {line.column for line in lines} == {"body"}
    assert any("GAZETTE" in line.text for line in lines)


def test_lines_come_back_in_reading_order(gazette: Path) -> None:
    lines = read_lines(gazette, margin_width=112, skip_top=75)

    positions = [(line.page, line.top) for line in lines]
    assert positions == sorted(positions)


def test_oversized_watermark_glyphs_are_dropped_before_lines_are_built(tmp_path: Path) -> None:
    # IndiaCode stamps a vertical "India Code" in 27-37pt letters across the text column;
    # left in, a stray "d" turns "contrary" into "contrardy".
    pdf = write_pdf(tmp_path / "w.pdf", [[
        Text(72, 300, 11, "acting contrary to law"),
        Text(160, 296, 34, "d"),
    ]])

    lines = read_lines(pdf, max_size=20)

    assert [line.text for line in lines] == ["acting contrary to law"]


def test_a_superscript_marker_does_not_set_the_line_size(tmp_path: Path) -> None:
    pdf = write_pdf(tmp_path / "m.pdf", [[
        Text(90, 300, 7, "2"),
        Text(94, 300, 11, "[376DB. Punishment for gang rape."),
    ]])

    (line,) = read_lines(pdf)

    assert line.size == pytest.approx(11)


def test_text_below_the_footnote_rule_is_dropped(tmp_path: Path) -> None:
    # IndiaCode draws a short rule at x 72-216 above each page's footnotes. On page 109
    # of the IPC the body and footnotes are both 8pt, so size cannot tell them apart.
    pdf = write_pdf(tmp_path / "f.pdf", [[
        Text(72, 700, 8, "465. Punishment for forgery.--Whoever commits forgery"),
        Rule(72, 216, 728),
        Text(72, 734, 8, "1. Ins. by Act 21 of 2000, s. 91."),
        Text(300, 781, 11, "109"),
    ]])

    lines = read_lines(pdf, footnote_rule=True)

    assert [line.text for line in lines] == [
        "465. Punishment for forgery.--Whoever commits forgery"
    ]


def test_a_full_width_rule_is_not_mistaken_for_the_footnote_rule(tmp_path: Path) -> None:
    pdf = write_pdf(tmp_path / "g.pdf", [[
        Rule(72, 523, 100),
        Text(72, 120, 11, "1. First.--Text."),
    ]])

    assert [line.text for line in read_lines(pdf, footnote_rule=True)] == ["1. First.--Text."]

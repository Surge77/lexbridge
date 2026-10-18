"""Read a PDF as positioned lines, with margin notes separated from the body.

Splitters work on these lines rather than on a text dump, because the BNS gazette puts
each section's title in the margin beside it. Only geometry connects the two.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pdfplumber
from pdfplumber.page import Page

# pdfplumber's default (3) merges words separated by a narrow gap: the gazette's
# "4. The" came out as "4.The". 1.5 restores the space without splitting words.
X_TOLERANCE = 1.5
# IndiaCode separates footnotes with a hairline rule from the left margin: measured at
# x 72-216, 0.7pt thick. Frames drawn around amended text are 13pt tall and start at
# x 90, and their bottom edge once passed for this rule (IPC page 92 lost 376C). So the
# rule must be thin, start at the margin, and be far narrower than the page.
FOOTNOTE_RULE_MAX_LEFT = 80.0
FOOTNOTE_RULE_MAX_THICKNESS = 2.0
FOOTNOTE_RULE_WIDTH = (100.0, 250.0)

Column = Literal["body", "margin"]


@dataclass(frozen=True)
class Line:
    page: int
    top: float
    x0: float
    size: float
    text: str
    column: Column


def read_lines(
    path: Path,
    *,
    margin_width: float | None = None,
    skip_top: float = 0.0,
    max_size: float | None = None,
    footnote_rule: bool = False,
) -> list[Line]:
    """Every non-blank line in reading order (page, then top to bottom).

    margin_width: strips of this width on both page edges are read as margin notes.
    None reads the whole page as body (the IPC typescript has no margin column).
    skip_top: drop everything above this line, e.g. the gazette's running header.
    max_size: drop glyphs larger than this before lines are built. IndiaCode's
    watermark letters (27-37pt) otherwise merge into body words: "contrardy".
    footnote_rule: drop everything below the page's footnote rule (footnotes and the
    page number). Size cannot do this: IPC page 109 sets body and footnotes both at 8pt.
    """
    lines: list[Line] = []
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            width = float(page.width)
            cut = _footnote_top(page) if footnote_rule else None

            # Chars are assigned to a column by their midpoint. Cropping at the boundary
            # instead clipped the full stop of "Punishments." into the body line.
            def column_of(
                obj: dict, width: float = width, cut: float | None = cut
            ) -> Column | None:
                if obj["top"] < skip_top:
                    return None
                if max_size is not None and obj["size"] > max_size:
                    return None
                if cut is not None and obj["top"] >= cut:
                    return None
                if margin_width is None:
                    return "body"
                middle = (obj["x0"] + obj["x1"]) / 2
                inside = margin_width <= middle <= width - margin_width
                return "body" if inside else "margin"

            for column in ("margin", "body"):
                region = page.filter(
                    lambda obj, column=column: obj.get("object_type") == "char"
                    and column_of(obj) == column
                )
                for raw in region.extract_text_lines(x_tolerance=X_TOLERANCE, return_chars=True):
                    text = raw["text"].strip()
                    if not text:
                        continue
                    lines.append(
                        Line(
                            page=number,
                            top=float(raw["top"]),
                            x0=float(raw["x0"]),
                            size=_dominant_size(raw["chars"]),
                            text=text,
                            column=column,
                        )
                    )
    return sorted(lines, key=lambda line: (line.page, line.top, line.x0))


def _dominant_size(chars: list[dict]) -> float:
    """The most common glyph size, so a 7pt superscript marker opening an 11pt body
    line ("2[376DB.") does not make the line look like a 9pt footnote."""
    return float(Counter(round(c["size"], 1) for c in chars).most_common(1)[0][0])


def _footnote_top(page: Page) -> float | None:
    """Top of the footnote rule in the page's lower half, if there is one."""
    low, high = FOOTNOTE_RULE_WIDTH
    # A rule is drawn either as a stroked line or as a hairline-thin filled rectangle.
    thin = [*page.lines, *(r for r in page.rects if r["height"] < FOOTNOTE_RULE_MAX_THICKNESS)]
    tops = [
        float(obj["top"])
        for obj in thin
        if obj["x0"] <= FOOTNOTE_RULE_MAX_LEFT
        and low <= obj["x1"] - obj["x0"] <= high
        and obj["top"] > float(page.height) / 2
    ]
    return min(tops) if tops else None

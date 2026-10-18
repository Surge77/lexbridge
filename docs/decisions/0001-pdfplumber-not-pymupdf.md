# 0001 — Extract statute text with pdfplumber, not PyMuPDF

**Status:** accepted · 2026-10-18

## Context
Splitting a statute into sections needs more than the raw text. Each line also needs its
position and font size. In the BNS gazette PDF the section titles are 8pt margin notes
at x≈58 (even pages) or x≈490 (odd pages), sitting next to a 10pt body. You can only
pair a title with its section by geometry.

PyMuPDF was the first choice: it's fast and its text quality is excellent. It is
licensed **AGPL-3.0**, though. LexBridge will run as a web service, and an AGPL
dependency would require publishing the source of the whole service. That conflicts
with the project's MIT licence.

## Decision
Use **pdfplumber** (MIT, built on pdfminer.six, MIT) for extraction. Its
dependencies are permissive (pypdfium2: Apache-2.0/BSD-3, Pillow: HPND).

pdfplumber merges a margin note into the body line at the same height
(`"Punishments. 4.The punishments…"`), so each page is cropped into margin and body
columns before lines are extracted. `x_tolerance=1.5` instead of the default 3
restores the dropped space in `4.The`.

## Consequences
- Extraction takes about 14 s for the 102-page BNS gazette, slower than PyMuPDF. That
  doesn't matter for an offline build that runs once per amendment.
- Text came out identical in the spot checks: `’` (U+2019) and `—` (U+2014) are
  preserved. The `�` seen during exploration was the Windows console failing to
  render them; the extracted text was fine.

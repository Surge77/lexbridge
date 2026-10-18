"""Write small but real PDFs for tests, with text placed at exact positions and sizes.

Hand-assembled rather than generated with a PDF library, so the tests need no writer
dependency and the bytes are fully under the test's control. Coordinates are given the
way pdfplumber reports them: `top` measured down from the top edge of the page.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PAGE_WIDTH = 595.0
PAGE_HEIGHT = 842.0
HELVETICA_ASCENT = 0.718


@dataclass(frozen=True)
class Text:
    x: float
    top: float
    size: float
    text: str


@dataclass(frozen=True)
class Rule:
    """A horizontal line, like the short rule above a page's footnotes."""

    x0: float
    x1: float
    top: float


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _content(items: list[Text | Rule]) -> bytes:
    ops = []
    for t in items:
        if isinstance(t, Rule):
            y = PAGE_HEIGHT - t.top
            ops.append(f"0.5 w {t.x0} {y} m {t.x1} {y} l S")
            continue
        # PDF y runs upward from the bottom, and pdfplumber's `top` is the top of the
        # glyph box: the baseline sits one ascender below it (Helvetica: 718/1000 em).
        baseline = PAGE_HEIGHT - t.top - HELVETICA_ASCENT * t.size
        ops.append(f"BT /F1 {t.size} Tf {t.x} {baseline} Td ({_escape(t.text)}) Tj ET")
    return "\n".join(ops).encode("latin-1")


def write_pdf(path: Path, pages: list[list[Text | Rule]]) -> Path:
    objects: list[bytes] = []
    page_ids = [4 + 2 * i for i in range(len(pages))]
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, texts in enumerate(pages):
        stream = _content(texts)
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {page_ids[i] + 1} 0 R >>".encode()
        )
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
        )

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode()
    out += f"startxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path

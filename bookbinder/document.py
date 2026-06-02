"""Loading source documents (PDF and EPUB) into a uniform interface."""

from __future__ import annotations

import os
from dataclasses import dataclass

import fitz  # PyMuPDF


# EPUB / MOBI / FB2 are reflowable: PyMuPDF lays them out into pages at a
# chosen "page size". We default to a trade-paperback-ish A5 at 11pt so the
# pagination is reasonable before imposition.
REFLOWABLE_EXTS = {".epub", ".mobi", ".fb2", ".xps", ".cbz"}

# A5 in points (1pt = 1/72").
DEFAULT_REFLOW_SIZE = (419.53, 595.28)


@dataclass
class SourceDocument:
    """A loaded document, normalized so the rest of the app does not care
    whether it began life as a PDF or an EPUB."""

    path: str
    doc: fitz.Document
    is_reflowable: bool

    @property
    def page_count(self) -> int:
        return self.doc.page_count

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    def median_page_size(self) -> tuple[float, float]:
        """Representative (width, height) in points across the document."""
        widths, heights = [], []
        for i in range(min(self.page_count, 25)):
            r = self.doc[i].rect
            widths.append(r.width)
            heights.append(r.height)
        if not widths:
            return DEFAULT_REFLOW_SIZE
        widths.sort()
        heights.sort()
        mid = len(widths) // 2
        return widths[mid], heights[mid]

    def render_page_png(self, index: int, max_dim: int = 900) -> bytes:
        """Render one page to PNG bytes for preview."""
        page = self.doc[index]
        rect = page.rect
        scale = max_dim / max(rect.width, rect.height) if max(rect.width, rect.height) else 1
        scale = min(scale, 4.0)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return pix.tobytes("png")

    def close(self) -> None:
        self.doc.close()


def load_document(
    path: str,
    reflow_size: tuple[float, float] = DEFAULT_REFLOW_SIZE,
    font_size: int = 11,
) -> SourceDocument:
    """Open ``path`` as a :class:`SourceDocument`.

    Raises ``ValueError`` for unsupported types and ``FileNotFoundError`` if
    the path is missing.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    ext = os.path.splitext(path)[1].lower()
    doc = fitz.open(path)
    is_reflowable = ext in REFLOWABLE_EXTS or doc.is_reflowable

    if is_reflowable:
        # Lay the reflowable content out at a fixed page size so it paginates,
        # then bake it into a real PDF: imposition (show_pdf_page) requires a
        # PDF source, and EPUB/MOBI/etc. are not PDFs.
        w, h = reflow_size
        doc.layout(width=w, height=h, fontsize=font_size)
        pdf_bytes = doc.convert_to_pdf()
        doc.close()
        doc = fitz.open("pdf", pdf_bytes)

    if doc.page_count == 0:
        doc.close()
        raise ValueError(f"{os.path.basename(path)} has no pages to bind")

    return SourceDocument(path=path, doc=doc, is_reflowable=is_reflowable)

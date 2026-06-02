"""Imposition: arrange source pages onto folded sheets for binding.

Supports folio (1 fold), quarto (2 folds), and octavo (3 folds) signatures via
the physically-verified layout engine in :mod:`bookbinder.folding`. Each output
PDF page is one printed *side* of a sheet, holding a grid of source pages
(rotated as the fold requires). Sides are emitted front, back, front, back …
in outer-sheet-first order, suitable for duplex printing.
"""

from __future__ import annotations

from dataclasses import dataclass

import fitz

from . import folding
from .document import SourceDocument
from .layout import FOLDS, SignaturePlan


# Common paper sizes in points (width, height) portrait. The imposed sheet is
# oriented (portrait/landscape) to match the fold's cell grid.
PAPER_SIZES: dict[str, tuple[float, float]] = {
    "A4": (595.28, 841.89),
    "A3": (841.89, 1190.55),
    "A5": (419.53, 595.28),
    "Letter": (612.0, 792.0),
    "Legal": (612.0, 1008.0),
    "Tabloid": (792.0, 1224.0),
}


@dataclass
class ImposeOptions:
    paper: str = "A4"
    sheets_per_signature: int = 4
    fold: str = "folio"
    fit: str = "proportional"        # "proportional" (preserve aspect) or "snug"
    center: bool = True
    margin_pt: float = 18.0          # outer margin around the whole sheet
    gutter_pt: float = 0.0           # gap between cells (at folds/spine)
    duplex: str = "long-edge"        # affects back-side flipping
    crop_marks: bool = True
    fold_line: bool = True


@dataclass
class _OutputPage:
    cols: int
    rows: int
    # (col, row, source page index or None, rotation degrees)
    cells: list[tuple[int, int, int | None, int]]


def build_plan(source_pages: int, opts: ImposeOptions) -> SignaturePlan:
    return SignaturePlan(source_pages, opts.fold, opts.sheets_per_signature)


def _output_pages(plan: SignaturePlan, opts: ImposeOptions) -> list[_OutputPage]:
    """Every printed side across all signatures, in print order."""
    k = FOLDS[opts.fold]
    sheets = opts.sheets_per_signature
    template = folding.signature_layout(k, sheets)  # same for every signature
    pps = plan.pages_per_signature

    pages: list[_OutputPage] = []
    for sig in range(plan.signatures):
        base = sig * pps
        for lay in template:  # outer sheet first
            for cells in (lay.front, lay.back):
                out_cells = []
                for c in cells:
                    gp = base + c.page
                    src_idx = gp if gp < plan.source_pages else None
                    out_cells.append((c.col, c.row, src_idx, c.rot))
                pages.append(_OutputPage(lay.cols, lay.rows, out_cells))
    return pages


def _sheet_size(cols: int, rows: int, paper: str) -> tuple[float, float]:
    pw, ph = PAPER_SIZES[paper]
    long_, short = max(pw, ph), min(pw, ph)
    if cols > rows:
        return long_, short        # landscape
    if rows > cols:
        return short, long_        # portrait
    return pw, ph                  # square grid: keep paper's own orientation


def _placement_rect(cell: fitz.Rect, src: fitz.Rect, fit: str, center: bool) -> fitz.Rect:
    """Rectangle inside ``cell`` where a source page of size ``src`` is drawn."""
    if fit == "snug":
        return cell
    if src.width <= 0 or src.height <= 0:
        return cell
    scale = min(cell.width / src.width, cell.height / src.height)
    w, h = src.width * scale, src.height * scale
    if center:
        x0 = cell.x0 + (cell.width - w) / 2
        y0 = cell.y0 + (cell.height - h) / 2
    else:
        x0, y0 = cell.x0, cell.y0
    return fitz.Rect(x0, y0, x0 + w, y0 + h)


def _draw_marks(
    page: fitz.Page, cols: int, rows: int, m: float, sw: float, sh: float,
    opts: ImposeOptions,
) -> None:
    shape = page.new_shape()
    cw = (sw - 2 * m) / cols
    ch = (sh - 2 * m) / rows
    if opts.fold_line:
        for i in range(1, cols):
            x = m + i * cw
            y = page.rect.y0
            while y < page.rect.y1:
                shape.draw_line(fitz.Point(x, y), fitz.Point(x, min(y + 4, page.rect.y1)))
                y += 8
        for j in range(1, rows):
            y = m + j * ch
            x = page.rect.x0
            while x < page.rect.x1:
                shape.draw_line(fitz.Point(x, y), fitz.Point(min(x + 4, page.rect.x1), y))
                x += 8
        shape.finish(color=(0.6, 0.6, 0.6), width=0.5)
    if opts.crop_marks:
        r = page.rect
        t = 12
        for x in (r.x0, r.x1):
            shape.draw_line(fitz.Point(x, r.y0), fitz.Point(x, r.y0 + t))
            shape.draw_line(fitz.Point(x, r.y1 - t), fitz.Point(x, r.y1))
        for y in (r.y0, r.y1):
            shape.draw_line(fitz.Point(r.x0, y), fitz.Point(r.x0 + t, y))
            shape.draw_line(fitz.Point(r.x1 - t, y), fitz.Point(r.x1, y))
        shape.finish(color=(0, 0, 0), width=0.5)
    shape.commit()


def impose_to_doc(
    src: SourceDocument, opts: ImposeOptions, max_sides: int | None = None
) -> tuple[fitz.Document, SignaturePlan]:
    """Build the imposed PDF in memory. Caller closes the returned document."""
    if opts.fold not in FOLDS:
        raise ValueError(f"unknown fold {opts.fold!r}")
    if opts.paper not in PAPER_SIZES:
        raise ValueError(f"unknown paper size {opts.paper!r}")

    plan = build_plan(src.page_count, opts)
    pages = _output_pages(plan, opts)
    if max_sides is not None:
        pages = pages[:max_sides]

    m = opts.margin_pt
    g = opts.gutter_pt
    out = fitz.open()
    for op in pages:
        sw, sh = _sheet_size(op.cols, op.rows, opts.paper)
        page = out.new_page(width=sw, height=sh)
        cw = (sw - 2 * m) / op.cols
        ch = (sh - 2 * m) / op.rows
        for col, row, src_idx, rot in op.cells:
            if src_idx is None:
                continue
            cell = fitz.Rect(
                m + col * cw + g, m + row * ch + g,
                m + (col + 1) * cw - g, m + (row + 1) * ch - g,
            )
            src_rect = src.doc[src_idx].rect
            dest = _placement_rect(cell, src_rect, opts.fit, opts.center)
            page.show_pdf_page(dest, src.doc, src_idx, rotate=rot)
        _draw_marks(page, op.cols, op.rows, m, sw, sh, opts)

    return out, plan


def impose(src: SourceDocument, opts: ImposeOptions, out_path: str) -> SignaturePlan:
    """Produce an imposed PDF at ``out_path``. Returns the plan used."""
    out, plan = impose_to_doc(src, opts)
    out.save(out_path, deflate=True, garbage=4)
    out.close()
    return plan

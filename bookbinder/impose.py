"""Imposition: arrange source pages onto folded sheets for binding.

Currently implements folio imposition (the standard 2-up booklet/signature
layout), which covers saddle-stitch booklets and multi-signature sewn books —
the overwhelmingly common cases for hand binding.

The output PDF has one page per *printed side*. Each output sheet is laid out
landscape with two source pages side by side; sides are emitted in
front, back, front, back... order suitable for duplex printing.
"""

from __future__ import annotations

from dataclasses import dataclass

import fitz

from .document import SourceDocument
from .layout import SignaturePlan, signature_page_order


# Common paper sizes in points (width, height) portrait. The imposed sheet is
# rotated to landscape automatically.
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
    margin_pt: float = 18.0          # outer margin around the pair of pages
    gutter_pt: float = 0.0           # extra gap at the spine (added each side)
    duplex: str = "long-edge"        # affects back-side flipping
    crop_marks: bool = True
    fold_line: bool = True


def build_plan(source_pages: int, opts: ImposeOptions) -> SignaturePlan:
    return SignaturePlan(source_pages, opts.fold, opts.sheets_per_signature)


def _global_page_sequence(plan: SignaturePlan) -> list[list[int | None]]:
    """Map the whole document into per-signature (left, right) side lists.

    Returns a list of "sides", each a 2-element list of 0-based source page
    indices or ``None`` for a blank padding page. Signatures are concatenated
    in reading order.
    """
    pps = plan.pages_per_signature
    sides: list[list[int | None]] = []
    for sig in range(plan.signatures):
        base = sig * pps  # 0-based start of this signature in the global slots
        for left, right in signature_page_order(pps):
            # left/right are 1-based within the signature
            gl = base + (left - 1)
            gr = base + (right - 1)
            sides.append([
                gl if gl < plan.source_pages else None,
                gr if gr < plan.source_pages else None,
            ])
    return sides


def _placement_rect(
    cell: fitz.Rect, src: fitz.Rect, fit: str, center: bool
) -> fitz.Rect:
    """Rectangle inside ``cell`` where a source page of size ``src`` is drawn."""
    if fit == "snug":
        return cell
    # proportional: scale to fit while preserving aspect ratio
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


def _draw_marks(page: fitz.Page, mid_x: float, opts: ImposeOptions) -> None:
    r = page.rect
    shape = page.new_shape()
    if opts.fold_line:
        # dotted fold line down the spine
        y = r.y0
        while y < r.y1:
            shape.draw_line(fitz.Point(mid_x, y), fitz.Point(mid_x, min(y + 4, r.y1)))
            y += 8
        shape.finish(color=(0.6, 0.6, 0.6), width=0.5)
    if opts.crop_marks:
        m = 12
        for x in (r.x0, r.x1):
            shape.draw_line(fitz.Point(x, r.y0), fitz.Point(x, r.y0 + m))
            shape.draw_line(fitz.Point(x, r.y1 - m), fitz.Point(x, r.y1))
        for y in (r.y0, r.y1):
            shape.draw_line(fitz.Point(r.x0, y), fitz.Point(r.x0 + m, y))
            shape.draw_line(fitz.Point(r.x1 - m, y), fitz.Point(r.x1, y))
        shape.finish(color=(0, 0, 0), width=0.5)
    shape.commit()


def impose_to_doc(
    src: SourceDocument, opts: ImposeOptions, max_sides: int | None = None
) -> tuple[fitz.Document, SignaturePlan]:
    """Build the imposed PDF in memory.

    ``max_sides`` limits how many printed sides are produced (used for fast
    previews). Returns the open document and the plan; caller closes the doc.
    """
    plan = build_plan(src.page_count, opts)
    if opts.paper not in PAPER_SIZES:
        raise ValueError(f"unknown paper size {opts.paper!r}")

    pw, ph = PAPER_SIZES[opts.paper]
    # Landscape sheet: long side horizontal.
    sheet_w, sheet_h = max(pw, ph), min(pw, ph)

    out = fitz.open()
    mid_x = sheet_w / 2
    m = opts.margin_pt
    g = opts.gutter_pt

    # Two cells: left page and right page, with margins + spine gutter.
    left_cell = fitz.Rect(m, m, mid_x - g, sheet_h - m)
    right_cell = fitz.Rect(mid_x + g, m, sheet_w - m, sheet_h - m)

    sides = _global_page_sequence(plan)
    if max_sides is not None:
        sides = sides[:max_sides]

    for lp, rp in sides:
        page = out.new_page(width=sheet_w, height=sheet_h)
        for src_idx, cell in ((lp, left_cell), (rp, right_cell)):
            if src_idx is None:
                continue
            src_rect = src.doc[src_idx].rect
            dest = _placement_rect(cell, src_rect, opts.fit, opts.center)
            page.show_pdf_page(dest, src.doc, src_idx)
        _draw_marks(page, mid_x, opts)

    return out, plan


def impose(src: SourceDocument, opts: ImposeOptions, out_path: str) -> SignaturePlan:
    """Produce an imposed PDF at ``out_path``. Returns the plan used."""
    out, plan = impose_to_doc(src, opts)
    out.save(out_path, deflate=True, garbage=4)
    out.close()
    return plan

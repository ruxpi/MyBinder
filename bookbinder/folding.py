"""General fold imposition via physical fold simulation.

Folio imposition (1 fold) is simple enough to lay out by hand, but quarto
(2 folds) and octavo (3 folds) require page *rotations* and an exact fold
order. Rather than transcribe imposition tables (and risk a subtle error that
only shows up after someone folds and sews a book), we simulate the physical
act of folding, then read the resulting booklet to learn which page belongs in
which cell — and :func:`verify_signature` re-folds the computed layout to prove
the pages read 1, 2, 3, … N in order.

A *signature* here is ``sheets`` sheets stacked together and folded ``k`` times
as a unit (exactly how a hand binder makes a multi-sheet signature). One fold
collapses a stack to a stack of twice as many leaves.

Fold model
----------
Folds alternate axis, starting vertical, so one sheet is a grid of
``cols x rows`` cells::

    cols = 2 ** ((k + 1) // 2)
    rows = 2 ** (k // 2)

A vertical fold turns a leaf like a page (no rotation); a horizontal fold flips
it head-over-heels (180°). Either way the moved flap turns over (front<->back)
and lands on top of the stack with its layer order reversed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Cell:
    """One printed cell on a flat sheet."""

    col: int
    row: int
    page: int | None      # 0-based page index within the signature, or None (blank)
    rot: int              # 0 or 180


@dataclass
class SheetLayout:
    """Front and back cell layouts for one physical sheet of a signature."""

    sheet: int
    cols: int
    rows: int
    front: list[Cell]
    back: list[Cell]


@dataclass
class _Leaf:
    sheet: int
    ox: int            # origin column on its flat sheet
    oy: int            # origin row
    rot: int           # accumulated content rotation (0/180)
    flipped: bool      # True => original FRONT now faces down


def grid_dims(k: int) -> tuple[int, int]:
    cols = 2 ** ((k + 1) // 2)
    rows = 2 ** (k // 2)
    return cols, rows


def pages_per_sheet(k: int) -> int:
    cols, rows = grid_dims(k)
    return 2 * cols * rows


def _collapse(k: int, sheets: int) -> list[_Leaf]:
    """Stack ``sheets`` sheets and fold ``k`` times; return the leaf stack,
    bottom (index 0) to top."""
    cols, rows = grid_dims(k)

    # stacks: footprint cell -> list of leaves, bottom..top.
    # Sheet 0 starts on top of the pile (so it becomes the outer sheet).
    stacks: dict[tuple[int, int], list[_Leaf]] = {}
    for y in range(rows):
        for x in range(cols):
            stacks[(x, y)] = [
                _Leaf(sheet=s, ox=x, oy=y, rot=0, flipped=False)
                for s in reversed(range(sheets))
            ]

    width, height = cols, rows
    for i in range(k):
        vertical = (i % 2 == 0)
        new: dict[tuple[int, int], list[_Leaf]] = {}
        if vertical:
            fold = width // 2
            for (cx, cy), layers in stacks.items():
                if cx >= fold:
                    dest = (2 * fold - 1 - cx, cy)
                    moved = [
                        _Leaf(lf.sheet, lf.ox, lf.oy, lf.rot, not lf.flipped)
                        for lf in reversed(layers)
                    ]
                    new[dest] = new.get(dest, []) + moved        # on top
                else:
                    new[(cx, cy)] = layers + new.get((cx, cy), [])  # at bottom
            width = fold
        else:
            fold = height // 2
            for (cx, cy), layers in stacks.items():
                if cy >= fold:
                    dest = (cx, 2 * fold - 1 - cy)
                    moved = [
                        _Leaf(lf.sheet, lf.ox, lf.oy, (lf.rot + 180) % 360, not lf.flipped)
                        for lf in reversed(layers)
                    ]
                    new[dest] = new.get(dest, []) + moved
                else:
                    new[(cx, cy)] = layers + new.get((cx, cy), [])
            height = fold
        stacks = new

    assert len(stacks) == 1, "fold did not collapse to a single column"
    return next(iter(stacks.values()))


def _reading_order(k: int, sheets: int) -> list[tuple[int, int, int, str]]:
    """Global page index -> (sheet, origin col, row, side 'F'/'B')."""
    stack = _collapse(k, sheets)
    order: list[tuple[int, int, int, str]] = []
    for lf in reversed(stack):  # top of pile = front of booklet
        up = "B" if lf.flipped else "F"
        down = "F" if lf.flipped else "B"
        # verso then recto: puts page 1 on the outside front of the outer sheet.
        order.append((lf.sheet, lf.ox, lf.oy, down))
        order.append((lf.sheet, lf.ox, lf.oy, up))
    return order


def signature_layout(k: int, sheets: int = 1) -> list[SheetLayout]:
    """Per-sheet front/back layouts for a signature of ``sheets`` sheets."""
    cols, rows = grid_dims(k)
    stack = _collapse(k, sheets)
    rot_of = {(lf.sheet, lf.ox, lf.oy): lf.rot for lf in stack}

    front_page: dict[tuple[int, int, int], int] = {}
    back_page: dict[tuple[int, int, int], int] = {}
    for page, (s, ox, oy, side) in enumerate(_reading_order(k, sheets)):
        (front_page if side == "F" else back_page)[(s, ox, oy)] = page

    layouts: list[SheetLayout] = []
    for s in range(sheets):
        front = [
            Cell(col=x, row=y, page=front_page[(s, x, y)], rot=rot_of[(s, x, y)])
            for y in range(rows)
            for x in range(cols)
        ]
        # The back is printed on the flip side; mirror columns so a duplex
        # long-edge flip lands each page above its front counterpart.
        back = [
            Cell(col=cols - 1 - x, row=y, page=back_page[(s, x, y)], rot=rot_of[(s, x, y)])
            for y in range(rows)
            for x in range(cols)
        ]
        layouts.append(SheetLayout(sheet=s, cols=cols, rows=rows, front=front, back=back))

    # Order sheets outer-first (the outer sheet carries page 0) so callers can
    # print them in a natural sequence. The ``sheet`` field keeps its original
    # index (it is tied to the page numbers), so its print position is its
    # place in this list, not its label.
    layouts.sort(key=lambda lay: min(c.page for c in lay.front + lay.back))
    return layouts


def verify_signature(k: int, sheets: int = 1) -> bool:
    """Re-fold the computed layout and confirm pages read 0..N-1 in order."""
    cols, rows = grid_dims(k)
    layouts = signature_layout(k, sheets)
    front = {}
    back = {}
    for lay in layouts:
        for c in lay.front:
            front[(lay.sheet, c.col, c.row)] = c.page
        for c in lay.back:
            back[(lay.sheet, cols - 1 - c.col, c.row)] = c.page

    stack = _collapse(k, sheets)
    read: list[int] = []
    for lf in reversed(stack):
        up = back[(lf.sheet, lf.ox, lf.oy)] if lf.flipped else front[(lf.sheet, lf.ox, lf.oy)]
        down = front[(lf.sheet, lf.ox, lf.oy)] if lf.flipped else back[(lf.sheet, lf.ox, lf.oy)]
        read.append(down)
        read.append(up)
    return read == list(range(len(read)))

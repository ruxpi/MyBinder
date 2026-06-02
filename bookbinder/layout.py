"""Signature math and binding recommendations.

This module is pure logic with no PDF dependencies, so it is fast and easy
to test. It answers two questions:

1. Given a page count and a chosen fold + sheets-per-signature, how do the
   pages get laid out (how many signatures, how much blank padding)?
2. Given just a page count, what are the *sensible* ways to bind it? (the
   "recommended bindings" table).

Terminology
-----------
sheet      A single physical piece of paper that goes through the printer.
fold       How many times a sheet is folded. Each fold doubles the leaves:
             folio   = 1 fold  -> 2 leaves  -> 4 pages per sheet
             quarto  = 2 folds -> 4 leaves  -> 8 pages per sheet
             octavo  = 3 folds -> 8 leaves  -> 16 pages per sheet
leaf       One half of a folded sheet; has a page on each side.
signature  A bundle of sheets nested together and folded as one unit. A book
           is bound by sewing/gluing several signatures in sequence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil


# fold name -> number of folds. Pages-per-sheet = 4 * 2**(folds-1)  -> 4, 8, 16.
FOLDS: dict[str, int] = {"folio": 1, "quarto": 2, "octavo": 3}


def pages_per_sheet(fold: str) -> int:
    """Pages printed on a single sheet (both sides) for a given fold."""
    folds = FOLDS[fold]
    return 4 * (2 ** (folds - 1))


@dataclass(frozen=True)
class SignaturePlan:
    """A concrete plan for binding ``source_pages`` pages."""

    source_pages: int
    fold: str
    sheets_per_signature: int

    @property
    def pages_per_sheet(self) -> int:
        return pages_per_sheet(self.fold)

    @property
    def pages_per_signature(self) -> int:
        return self.pages_per_sheet * self.sheets_per_signature

    @property
    def signatures(self) -> int:
        return max(1, ceil(self.source_pages / self.pages_per_signature))

    @property
    def total_slots(self) -> int:
        """Total page slots once rounded up to whole signatures."""
        return self.signatures * self.pages_per_signature

    @property
    def padding(self) -> int:
        """Blank pages added to fill out the final signature."""
        return self.total_slots - self.source_pages

    @property
    def total_sheets(self) -> int:
        return self.signatures * self.sheets_per_signature

    def describe(self) -> str:
        pad = (
            "no blank pages"
            if self.padding == 0
            else f"{self.padding} blank page{'s' if self.padding != 1 else ''} of padding"
        )
        return (
            f"{self.signatures} signature{'s' if self.signatures != 1 else ''} of "
            f"{self.sheets_per_signature} sheet{'s' if self.sheets_per_signature != 1 else ''} "
            f"({self.pages_per_signature} pages each) "
            f"= {self.total_slots} page slots, {pad}, "
            f"{self.total_sheets} sheets of paper."
        )


@dataclass(frozen=True)
class Recommendation(SignaturePlan):
    """A scored recommendation, ready to sort and present in a table."""

    score: float = field(default=0.0, compare=False)
    note: str = field(default="", compare=False)


def recommend(
    source_pages: int,
    fold: str = "folio",
    min_sheets: int = 1,
    max_sheets: int = 8,
) -> list[Recommendation]:
    """Return candidate bindings for ``source_pages``, best first.

    We score each candidate by how little blank padding it wastes, with a
    gentle preference for the comfortable 4-6 sheets-per-signature range that
    hand binders actually like to sew (thick signatures are hard to fold
    cleanly; single-sheet signatures mean a lot of sewing).
    """
    if source_pages < 1:
        return []

    recs: list[Recommendation] = []
    for sheets in range(min_sheets, max_sheets + 1):
        plan = SignaturePlan(source_pages, fold, sheets)
        # Lower is better: padding hurts most; very thick or very thin
        # signatures get a mild penalty.
        comfort_penalty = 0.0
        if sheets > 6:
            comfort_penalty = (sheets - 6) * 1.5
        elif sheets < 3:
            comfort_penalty = (3 - sheets) * 0.75
        score = plan.padding + comfort_penalty

        note = ""
        if plan.padding == 0:
            note = "perfect fit — no blank pages"
        elif plan.padding <= plan.pages_per_sheet:
            note = "very tight fit"
        if 4 <= sheets <= 6:
            note = (note + "; " if note else "") + "comfortable to fold & sew"

        recs.append(
            Recommendation(
                source_pages=source_pages,
                fold=fold,
                sheets_per_signature=sheets,
                score=score,
                note=note,
            )
        )

    recs.sort(key=lambda r: (r.score, r.sheets_per_signature))
    return recs


def signature_page_order(pages_in_signature: int) -> list[tuple[int, int]]:
    """Folding order for one folio signature.

    ``pages_in_signature`` must be a multiple of 4. Returns one ``(left, right)``
    tuple per printed side, in the order the sides are printed. Page numbers are
    1-based within the signature; the imposition layer maps them to real pages
    (or to ``None`` blanks when padding).

    For an 8-page signature the result is::

        [(8, 1), (2, 7), (6, 3), (4, 5)]

    i.e. the outermost sheet carries the last and first pages, working inward.
    """
    if pages_in_signature % 4 != 0:
        raise ValueError("a folio signature must hold a multiple of 4 pages")

    sides: list[tuple[int, int]] = []
    sheets = pages_in_signature // 4
    for i in range(sheets):
        # Front of sheet i: (last - 2i, first + 2i)
        front = (pages_in_signature - 2 * i, 1 + 2 * i)
        # Back of sheet i: (2 + 2i, last - 1 - 2i)
        back = (2 + 2 * i, pages_in_signature - 1 - 2 * i)
        sides.append(front)
        sides.append(back)
    return sides

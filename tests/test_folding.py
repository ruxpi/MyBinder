import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from bookbinder.folding import (  # noqa: E402
    grid_dims,
    pages_per_sheet,
    signature_layout,
    verify_signature,
)


@pytest.mark.parametrize("k", [1, 2, 3])
@pytest.mark.parametrize("sheets", [1, 2, 3, 4])
def test_refold_reads_in_order(k, sheets):
    # The physical proof: laying pages out per the computed layout and folding
    # again must read 1, 2, 3, … with no gaps or repeats.
    assert verify_signature(k, sheets)


def test_grid_and_capacity():
    assert grid_dims(1) == (2, 1) and pages_per_sheet(1) == 4
    assert grid_dims(2) == (2, 2) and pages_per_sheet(2) == 8
    assert grid_dims(3) == (4, 2) and pages_per_sheet(3) == 16


def test_folio_matches_standard_layout():
    # folio: FRONT (4,1) BACK (2,3) in 1-based page numbers
    lay = signature_layout(1, 1)[0]
    front = [c.page + 1 for c in sorted(lay.front, key=lambda c: c.col)]
    back = [c.page + 1 for c in sorted(lay.back, key=lambda c: c.col)]
    assert front == [4, 1]
    assert back == [2, 3]


def test_every_page_used_once_per_signature():
    for k in (1, 2, 3):
        for sheets in (1, 2, 3):
            layouts = signature_layout(k, sheets)
            pages = []
            for lay in layouts:
                pages += [c.page for c in lay.front] + [c.page for c in lay.back]
            assert sorted(pages) == list(range(pages_per_sheet(k) * sheets))


def test_outer_sheet_carries_page_one():
    # sheet 0 should be the outermost (holds page 0)
    layouts = signature_layout(2, 3)
    assert min(c.page for c in layouts[0].front + layouts[0].back) == 0


def test_quarto_and_octavo_have_rotations():
    # the bottom row of a multi-row fold must be rotated 180
    for k in (2, 3):
        lay = signature_layout(k, 1)[0]
        assert any(c.rot == 180 for c in lay.front)
        assert any(c.rot == 0 for c in lay.front)

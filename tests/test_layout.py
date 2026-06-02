import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bookbinder.layout import (  # noqa: E402
    SignaturePlan,
    pages_per_sheet,
    recommend,
    signature_page_order,
)


def test_pages_per_sheet():
    assert pages_per_sheet("folio") == 4
    assert pages_per_sheet("quarto") == 8
    assert pages_per_sheet("octavo") == 16


def test_plan_basic():
    # 68 pages, folio, 4 sheets/sig -> 16 pages/sig -> 5 sigs (80 slots), 12 blank
    p = SignaturePlan(68, "folio", 4)
    assert p.pages_per_signature == 16
    assert p.signatures == 5
    assert p.total_slots == 80
    assert p.padding == 12
    assert p.total_sheets == 20


def test_perfect_fit_has_no_padding():
    p = SignaturePlan(80, "folio", 4)
    assert p.padding == 0
    assert p.signatures == 5


def test_recommend_orders_by_least_waste_and_returns_all():
    recs = recommend(68, "folio", min_sheets=1, max_sheets=8)
    assert len(recs) == 8
    # best recommendation should waste no more than the worst
    assert recs[0].padding <= recs[-1].padding
    # a single page still produces a valid plan
    assert recommend(1)[0].signatures == 1


def test_recommend_prefers_zero_padding():
    # 64 = 16*4 perfect at 4 sheets; should rank at or near the top
    recs = recommend(64, "folio")
    assert any(r.padding == 0 for r in recs)
    assert recs[0].padding == 0


def test_signature_order_4_pages():
    assert signature_page_order(4) == [(4, 1), (2, 3)]


def test_signature_order_8_pages():
    assert signature_page_order(8) == [(8, 1), (2, 7), (6, 3), (4, 5)]


def test_signature_order_is_a_permutation():
    n = 16
    sides = signature_page_order(n)
    flat = [p for side in sides for p in side]
    assert sorted(flat) == list(range(1, n + 1))


def test_signature_order_requires_multiple_of_four():
    try:
        signature_page_order(6)
    except ValueError:
        return
    raise AssertionError("expected ValueError")

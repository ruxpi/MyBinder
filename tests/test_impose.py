import os
import sys

import fitz

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bookbinder.document import load_document  # noqa: E402
from bookbinder.impose import ImposeOptions, impose  # noqa: E402


def _make_numbered_pdf(path, pages):
    doc = fitz.open()
    for i in range(1, pages + 1):
        page = doc.new_page(width=300, height=420)
        page.insert_text((140, 210), str(i), fontsize=48)
    doc.save(path)
    doc.close()


def test_impose_page_count(tmp_path):
    src_path = str(tmp_path / "src.pdf")
    out_path = str(tmp_path / "out.pdf")
    _make_numbered_pdf(src_path, 68)

    src = load_document(src_path)
    opts = ImposeOptions(paper="A4", sheets_per_signature=4, fold="folio")
    plan = impose(src, opts, out_path)

    assert plan.padding == 12
    out = fitz.open(out_path)
    # one output page per printed side = 2 * total_sheets
    assert out.page_count == plan.total_sheets * 2
    # sheets are landscape A4
    r = out[0].rect
    assert r.width > r.height
    out.close()
    src.close()


def test_impose_quarto(tmp_path):
    src_path = str(tmp_path / "src.pdf")
    out_path = str(tmp_path / "out.pdf")
    _make_numbered_pdf(src_path, 68)

    src = load_document(src_path)
    opts = ImposeOptions(paper="A4", sheets_per_signature=2, fold="quarto")
    plan = impose(src, opts, out_path)

    # quarto: 8 pages/sheet * 2 sheets = 16 pages/signature -> 5 signatures
    assert plan.pages_per_signature == 16
    assert plan.signatures == 5
    out = fitz.open(out_path)
    # 2 sides per sheet, sheets per signature * signatures sheets total
    assert out.page_count == plan.signatures * opts.sheets_per_signature * 2
    out.close()
    src.close()


def test_impose_octavo(tmp_path):
    src_path = str(tmp_path / "src.pdf")
    out_path = str(tmp_path / "out.pdf")
    _make_numbered_pdf(src_path, 40)

    src = load_document(src_path)
    opts = ImposeOptions(paper="Letter", sheets_per_signature=1, fold="octavo")
    plan = impose(src, opts, out_path)

    assert plan.pages_per_signature == 16  # one octavo sheet = 16 pages
    out = fitz.open(out_path)
    assert out.page_count == plan.signatures * 1 * 2
    out.close()
    src.close()


def test_impose_small_booklet(tmp_path):
    src_path = str(tmp_path / "src.pdf")
    out_path = str(tmp_path / "out.pdf")
    _make_numbered_pdf(src_path, 4)

    src = load_document(src_path)
    opts = ImposeOptions(paper="Letter", sheets_per_signature=1)
    plan = impose(src, opts, out_path)

    assert plan.signatures == 1
    assert plan.padding == 0
    out = fitz.open(out_path)
    assert out.page_count == 2  # one sheet, two sides
    out.close()
    src.close()

"""Command-line interface for MyBinder.

    python -m bookbinder recommend book.pdf
    python -m bookbinder impose book.epub -o out.pdf --sheets 4 --paper A4
"""

from __future__ import annotations

import argparse
import os
import sys

from .document import load_document
from .impose import PAPER_SIZES, ImposeOptions, impose
from .layout import FOLDS, recommend


def _cmd_recommend(args: argparse.Namespace) -> int:
    src = load_document(args.input)
    print(f"{src.name}: {src.page_count} pages\n")
    recs = recommend(src.page_count, args.fold, 1, args.max_sheets)
    print(f"{'Sheets':>6} {'Pages/sig':>10} {'Sigs':>5} {'Blank':>6}  Notes")
    print("-" * 60)
    for r in recs:
        print(
            f"{r.sheets_per_signature:>6} {r.pages_per_signature:>10} "
            f"{r.signatures:>5} {r.padding:>6}  {r.note}"
        )
    src.close()
    return 0


def _cmd_impose(args: argparse.Namespace) -> int:
    src = load_document(args.input)
    out = args.output or os.path.splitext(args.input)[0] + "_imposed.pdf"
    opts = ImposeOptions(
        paper=args.paper,
        sheets_per_signature=args.sheets,
        fold=args.fold,
        fit=args.fit,
        center=not args.no_center,
        margin_pt=args.margin,
        gutter_pt=args.gutter,
        crop_marks=not args.no_crop,
        fold_line=not args.no_fold_line,
    )
    plan = impose(src, opts, out)
    print(f"Wrote {out}")
    print(plan.describe())
    src.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="bookbinder", description="PDF/EPUB imposition for bookbinding")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("recommend", help="show recommended signature sizes")
    r.add_argument("input")
    r.add_argument("--fold", choices=FOLDS, default="folio")
    r.add_argument("--max-sheets", type=int, default=10)
    r.set_defaults(func=_cmd_recommend)

    i = sub.add_parser("impose", help="impose a document into a print-ready PDF")
    i.add_argument("input")
    i.add_argument("-o", "--output")
    i.add_argument("--sheets", type=int, default=4, help="sheets per signature")
    i.add_argument("--fold", choices=FOLDS, default="folio")
    i.add_argument("--paper", choices=PAPER_SIZES, default="A4")
    i.add_argument("--fit", choices=["proportional", "snug"], default="proportional")
    i.add_argument("--margin", type=float, default=18.0)
    i.add_argument("--gutter", type=float, default=0.0)
    i.add_argument("--no-center", action="store_true")
    i.add_argument("--no-crop", action="store_true")
    i.add_argument("--no-fold-line", action="store_true")
    i.set_defaults(func=_cmd_impose)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

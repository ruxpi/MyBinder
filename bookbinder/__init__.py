"""MyBinder — PDF/EPUB imposition for hand bookbinding."""

from .layout import (
    FOLDS,
    Recommendation,
    SignaturePlan,
    pages_per_sheet,
    recommend,
    signature_page_order,
)
from .document import SourceDocument, load_document
from .folding import signature_layout, verify_signature
from .impose import PAPER_SIZES, ImposeOptions, impose, impose_to_doc

__version__ = "0.1.0"

__all__ = [
    "FOLDS",
    "Recommendation",
    "SignaturePlan",
    "pages_per_sheet",
    "recommend",
    "signature_page_order",
    "SourceDocument",
    "load_document",
    "PAPER_SIZES",
    "ImposeOptions",
    "impose",
    "impose_to_doc",
    "signature_layout",
    "verify_signature",
    "__version__",
]

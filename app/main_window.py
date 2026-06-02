"""MyBinder desktop GUI (PySide6).

A two-pane window: controls + binding recommendations on the left, a live
preview of the imposed sheets on the right.
"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPixmap, QAction
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# Allow running as a loose script (python app/main_window.py) as well as a module.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bookbinder.document import SourceDocument, load_document  # noqa: E402
from bookbinder.impose import PAPER_SIZES, ImposeOptions, impose, impose_to_doc  # noqa: E402
from bookbinder.layout import FOLDS, recommend  # noqa: E402
from app.classic import ClassicTitleBar, apply_classic_theme  # noqa: E402

SUPPORTED_FILTER = "Books (*.pdf *.epub *.mobi *.fb2 *.cbz *.xps);;All files (*)"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MyBinder — Bookbinding Imposition")
        self.resize(1180, 820)
        # Frameless: we draw our own classic Mac OS title bar.
        self.setWindowFlag(Qt.FramelessWindowHint, True)

        self.source: SourceDocument | None = None
        self.preview_side = 0
        self._preview_doc = None

        self._build_menu()
        self._build_ui()
        self._update_enabled(False)

        # Debounce timer so dragging sliders doesn't re-impose on every tick.
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(180)
        self._debounce.timeout.connect(self._refresh)

    # ----- construction -------------------------------------------------
    def _build_menu(self) -> None:
        open_act = QAction("Open…", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self.open_file)
        save_act = QAction("Impose && Save…", self)
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self.save_imposed)
        m = self.menuBar().addMenu("File")
        m.addAction(open_act)
        m.addAction(save_act)

    def _build_ui(self) -> None:
        frame = QWidget()
        frame.setObjectName("windowFrame")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.titlebar = ClassicTitleBar("MyBinder")
        self.titlebar.closeClicked.connect(self.close)
        outer.addWidget(self.titlebar)

        content = QWidget()
        content.setObjectName("content")
        layout = QHBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(12)
        layout.addWidget(self._build_controls(), 0)
        layout.addWidget(self._build_preview(), 1)
        outer.addWidget(content, 1)

        # bottom strip with a classic resize grip (frameless windows need one)
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 3, 3)
        bottom.addStretch(1)
        bottom.addWidget(QSizeGrip(frame), 0, Qt.AlignBottom | Qt.AlignRight)
        outer.addLayout(bottom)

        self.setCentralWidget(frame)
        self.setContentsMargins(0, 0, 0, 0)

    def _build_controls(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(440)
        v = QVBoxLayout(panel)
        v.setSpacing(10)

        # --- document ---
        open_btn = QPushButton("Open PDF or EPUB…")
        open_btn.clicked.connect(self.open_file)
        v.addWidget(open_btn)

        self.doc_label = QLabel("No document loaded.")
        self.doc_label.setWordWrap(True)
        self.doc_label.setStyleSheet("color:#888;")
        v.addWidget(self.doc_label)

        # --- binding options ---
        box = QGroupBox("Binding options")
        form = QVBoxLayout(box)

        self.fold = QComboBox()
        self.fold.addItems(sorted(FOLDS, key=lambda k: FOLDS[k]))
        self.fold.setCurrentText("folio")
        form.addLayout(_row("Fold", self.fold))

        self.sheets = QSpinBox()
        self.sheets.setRange(1, 25)
        self.sheets.setValue(4)
        form.addLayout(_row("Sheets / signature", self.sheets))

        self.paper = QComboBox()
        self.paper.addItems(PAPER_SIZES.keys())
        self.paper.setCurrentText("A4")
        form.addLayout(_row("Paper", self.paper))

        self.fit = QComboBox()
        self.fit.addItems(["proportional", "snug"])
        form.addLayout(_row("Fit", self.fit))

        self.margin = QDoubleSpinBox()
        self.margin.setRange(0, 144)
        self.margin.setValue(18)
        self.margin.setSuffix(" pt")
        form.addLayout(_row("Margin", self.margin))

        self.gutter = QDoubleSpinBox()
        self.gutter.setRange(0, 144)
        self.gutter.setValue(0)
        self.gutter.setSuffix(" pt")
        form.addLayout(_row("Spine gutter", self.gutter))

        checks = QHBoxLayout()
        self.center = QCheckBox("Center")
        self.center.setChecked(True)
        self.crop = QCheckBox("Crop marks")
        self.crop.setChecked(True)
        self.foldline = QCheckBox("Fold line")
        self.foldline.setChecked(True)
        for c in (self.center, self.crop, self.foldline):
            checks.addWidget(c)
        form.addLayout(checks)
        v.addWidget(box)

        # --- recommendations ---
        rec_box = QGroupBox("Recommended bindings")
        rv = QVBoxLayout(rec_box)
        self.rec_table = QTableWidget(0, 5)
        self.rec_table.setHorizontalHeaderLabels(
            ["Sheets", "Pages/sig", "Sigs", "Blank", "Notes"]
        )
        self.rec_table.verticalHeader().setVisible(False)
        self.rec_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.rec_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rec_table.horizontalHeader().setStretchLastSection(True)
        self.rec_table.setMinimumHeight(220)
        self.rec_table.cellClicked.connect(self._apply_recommendation)
        rv.addWidget(self.rec_table)
        hint = QLabel("Click a row to use that signature size.")
        hint.setStyleSheet("color:#888; font-size:11px;")
        rv.addWidget(hint)
        v.addWidget(rec_box)

        # --- plan summary + save ---
        self.plan_label = QLabel("")
        self.plan_label.setWordWrap(True)
        self.plan_label.setStyleSheet("font-weight:600;")
        v.addWidget(self.plan_label)

        self.save_btn = QPushButton("Impose && Save PDF…")
        self.save_btn.clicked.connect(self.save_imposed)
        v.addWidget(self.save_btn)

        v.addStretch(1)

        # react to changes
        self.fold.currentTextChanged.connect(self._on_change)
        self.sheets.valueChanged.connect(self._on_change)
        self.paper.currentTextChanged.connect(self._on_change)
        self.fit.currentTextChanged.connect(self._on_change)
        self.margin.valueChanged.connect(self._on_change)
        self.gutter.valueChanged.connect(self._on_change)
        for c in (self.center, self.crop, self.foldline):
            c.stateChanged.connect(self._on_change)

        return panel

    def _build_preview(self) -> QWidget:
        panel = QWidget()
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("previewWell")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.preview_label = QLabel("Open a document to see the imposed sheets.")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("color:#e8e8e8;")
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scroll.setWidget(self.preview_label)
        v.addWidget(self.scroll, 1)

        nav = QHBoxLayout()
        self.prev_btn = QPushButton("◀ Prev side")
        self.next_btn = QPushButton("Next side ▶")
        self.prev_btn.clicked.connect(lambda: self._step(-1))
        self.next_btn.clicked.connect(lambda: self._step(1))
        self.side_label = QLabel("")
        self.side_label.setAlignment(Qt.AlignCenter)
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.side_label, 1)
        nav.addWidget(self.next_btn)
        v.addLayout(nav)
        return panel

    # ----- options snapshot --------------------------------------------
    def _opts(self) -> ImposeOptions:
        return ImposeOptions(
            paper=self.paper.currentText(),
            sheets_per_signature=self.sheets.value(),
            fold=self.fold.currentText(),
            fit=self.fit.currentText(),
            center=self.center.isChecked(),
            margin_pt=self.margin.value(),
            gutter_pt=self.gutter.value(),
            crop_marks=self.crop.isChecked(),
            fold_line=self.foldline.isChecked(),
        )

    # ----- actions ------------------------------------------------------
    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open document", os.path.expanduser("~"), SUPPORTED_FILTER
        )
        if not path:
            return
        try:
            if self.source:
                self.source.close()
            self.source = load_document(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Could not open", str(e))
            self.source = None
            return

        w, h = self.source.median_page_size()
        kind = "EPUB (reflowed)" if self.source.is_reflowable else "PDF"
        self.doc_label.setText(
            f"<b>{self.source.name}</b><br>{kind} · {self.source.page_count} pages · "
            f"{w:.0f}×{h:.0f} pt"
        )
        self.doc_label.setStyleSheet("color:#111;")
        self.preview_side = 0
        self._update_enabled(True)
        self._refresh()

    def _on_change(self) -> None:
        if self.source:
            self._debounce.start()

    def _apply_recommendation(self, row: int, _col: int) -> None:
        item = self.rec_table.item(row, 0)
        if item:
            self.sheets.setValue(int(item.text()))

    def _step(self, delta: int) -> None:
        if not self._preview_doc:
            return
        n = self._preview_doc.page_count
        self.preview_side = max(0, min(n - 1, self.preview_side + delta))
        self._render_preview_side()

    def _refresh(self) -> None:
        if not self.source:
            return
        self._refresh_recommendations()
        self._refresh_preview()

    def _refresh_recommendations(self) -> None:
        fold = self.fold.currentText()
        recs = recommend(self.source.page_count, fold, 1, 10)
        self.rec_table.setRowCount(len(recs))
        for i, r in enumerate(recs):
            cells = [
                str(r.sheets_per_signature),
                str(r.pages_per_signature),
                str(r.signatures),
                str(r.padding),
                r.note,
            ]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if r.padding == 0:
                    item.setForeground(QColor("#007000"))
                self.rec_table.setItem(i, c, item)
        self.rec_table.resizeColumnsToContents()

    def _refresh_preview(self) -> None:
        opts = self._opts()
        try:
            if self._preview_doc:
                self._preview_doc.close()
            # Cap preview to the first signature's sides for speed.
            cap = opts.sheets_per_signature * 2
            self._preview_doc, plan = impose_to_doc(self.source, opts, max_sides=cap)
        except Exception as e:  # noqa: BLE001
            self.preview_label.setText(f"Preview error:\n{e}")
            return

        self.plan_label.setText(plan.describe())
        self.preview_side = min(self.preview_side, self._preview_doc.page_count - 1)
        self._render_preview_side()

    def _render_preview_side(self) -> None:
        if not self._preview_doc or self._preview_doc.page_count == 0:
            return
        import fitz

        page = self._preview_doc[self.preview_side]
        target = max(self.scroll.viewport().width() - 40, 400)
        scale = min(target / page.rect.width, 2.5)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
        self.preview_label.setPixmap(QPixmap.fromImage(img.copy()))
        self.preview_label.setText("")
        total = self._preview_doc.page_count
        sheet = self.preview_side // 2 + 1
        face = "front" if self.preview_side % 2 == 0 else "back"
        self.side_label.setText(
            f"Sheet {sheet}, {face}  ·  preview side {self.preview_side + 1}/{total} "
            f"(first signature)"
        )

    def save_imposed(self) -> None:
        if not self.source:
            return
        default = os.path.splitext(self.source.path)[0] + "_imposed.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save imposed PDF", default, "PDF (*.pdf)"
        )
        if not path:
            return
        try:
            plan = impose(self.source, self._opts(), path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Imposition failed", str(e))
            return
        QMessageBox.information(
            self,
            "Done",
            f"Imposed PDF saved.\n\n{plan.describe()}",
        )

    def _update_enabled(self, on: bool) -> None:
        for w in (self.save_btn, self.prev_btn, self.next_btn):
            w.setEnabled(on)


def _row(label: str, widget: QWidget) -> QHBoxLayout:
    h = QHBoxLayout()
    lab = QLabel(label)
    lab.setFixedWidth(140)
    h.addWidget(lab)
    h.addWidget(widget, 1)
    return h


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("MyBinder")
    apply_classic_theme(app)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

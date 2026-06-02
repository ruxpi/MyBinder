"""Classic Mac OS (System 7 / Platinum) look-and-feel for the GUI.

Provides:
- ``CLASSIC_QSS`` — a Qt stylesheet emulating beveled Platinum controls.
- ``ClassicTitleBar`` — a pinstriped title bar with a square close box.
- ``apply_classic_theme(app)`` — sets the Geneva font and the stylesheet.

The window itself is frameless; ``ClassicTitleBar`` draws the iconic striped
bar and handles dragging. macOS keeps the menu bar at the top of the screen,
which is exactly where classic Mac OS put it, so we leave that native.
"""

from __future__ import annotations

import os
import tempfile

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget


# --- Platinum palette -------------------------------------------------------
GRAY = "#dcdcdc"      # window / content background
GRAY_DK = "#808080"   # engraved shadow
WHITE = "#ffffff"
BLACK = "#000000"

GENERATED_DIR = os.path.join(tempfile.gettempdir(), "mybinder_classic")


def _generate_indicator_images() -> tuple[str, str]:
    """Render the classic square checkbox (empty and X-checked) to PNGs.

    Returns ``(off_path, on_path)``. QSS can't draw an 'X', so we bake tiny
    bitmaps once and reference them from the stylesheet.
    """
    os.makedirs(GENERATED_DIR, exist_ok=True)
    off_path = os.path.join(GENERATED_DIR, "check_off.png")
    on_path = os.path.join(GENERATED_DIR, "check_on.png")
    size = 14

    def _box() -> QImage:
        img = QImage(size, size, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, False)
        # raised white square with a 1px black border
        p.fillRect(1, 1, size - 2, size - 2, QColor(WHITE))
        p.setPen(QPen(QColor(BLACK), 1))
        p.drawRect(1, 1, size - 3, size - 3)
        return img, p

    img, p = _box()
    p.end()
    img.save(off_path)

    img, p = _box()
    # classic 'X'
    p.setPen(QPen(QColor(BLACK), 2))
    p.drawLine(3, 3, size - 4, size - 4)
    p.drawLine(size - 4, 3, 3, size - 4)
    p.end()
    img.save(on_path)

    # QSS wants forward slashes even on the rare path that has backslashes.
    return off_path.replace(os.sep, "/"), on_path.replace(os.sep, "/")


def build_qss() -> str:
    off_img, on_img = _generate_indicator_images()
    return f"""
    * {{
        font-family: "Geneva";
        font-size: 12px;
        color: {BLACK};
        outline: 0;
    }}

    QWidget#windowFrame {{
        background: {GRAY};
        border: 1px solid {BLACK};
    }}
    QWidget#content {{ background: {GRAY}; }}

    /* Platinum push buttons: glossy gray pill, 1px black outline */
    QPushButton {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {WHITE}, stop:0.5 #e0e0e0, stop:1 #bdbdbd);
        border: 1px solid {BLACK};
        border-radius: 8px;
        padding: 4px 14px;
        min-height: 16px;
    }}
    QPushButton:hover {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {WHITE}, stop:1 #cfcfcf);
    }}
    QPushButton:pressed {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #9a9a9a, stop:1 #c4c4c4);
    }}
    QPushButton:disabled {{ color: #9a9a9a; border-color: #9a9a9a; }}

    /* Engraved group frames with a plain bold-ish title */
    QGroupBox {{
        background: transparent;
        border: 1px solid {GRAY_DK};
        border-bottom-color: {WHITE};
        border-right-color: {WHITE};
        margin-top: 12px;
        padding: 8px 6px 6px 6px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 8px;
        padding: 0 4px;
        background: {GRAY};
    }}

    /* Sunken white fields */
    QComboBox, QSpinBox, QDoubleSpinBox {{
        background: {WHITE};
        border: 1px solid {GRAY_DK};
        border-top-color: {BLACK};
        border-left-color: {BLACK};
        border-radius: 0;
        padding: 1px 4px;
        min-height: 16px;
    }}
    QComboBox::drop-down {{
        width: 16px;
        border-left: 1px solid {GRAY_DK};
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {WHITE}, stop:1 #bdbdbd);
    }}
    QComboBox::down-arrow {{
        width: 0; height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {BLACK};
    }}
    QComboBox QAbstractItemView {{
        background: {WHITE};
        border: 1px solid {BLACK};
        selection-background-color: #000080;
        selection-color: {WHITE};
    }}
    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        width: 14px;
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {WHITE}, stop:1 #bdbdbd);
        border: 1px solid {GRAY_DK};
    }}

    /* Classic square checkboxes with a baked 'X' */
    QCheckBox {{ spacing: 6px; }}
    QCheckBox::indicator {{ width: 14px; height: 14px; }}
    QCheckBox::indicator:unchecked {{ image: url({off_img}); }}
    QCheckBox::indicator:checked {{ image: url({on_img}); }}

    /* List / table: white well, beveled header sections */
    QTableWidget, QTableView {{
        background: {WHITE};
        gridline-color: #c8c8c8;
        border: 1px solid {BLACK};
        selection-background-color: #000080;
        selection-color: {WHITE};
    }}
    QHeaderView::section {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {WHITE}, stop:1 #c4c4c4);
        border: 1px solid {GRAY_DK};
        padding: 2px 4px;
        font-weight: bold;
    }}

    /* Sunken preview well */
    QScrollArea#previewWell {{
        background: #9a9a9a;
        border: 1px solid {GRAY_DK};
        border-top-color: {BLACK};
        border-left-color: {BLACK};
    }}

    /* Classic beveled scrollbars */
    QScrollBar:vertical {{
        background: #cdcdcd; width: 16px; margin: 16px 0 16px 0;
        border: 1px solid {GRAY_DK};
    }}
    QScrollBar:horizontal {{
        background: #cdcdcd; height: 16px; margin: 0 16px 0 16px;
        border: 1px solid {GRAY_DK};
    }}
    QScrollBar::handle {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {WHITE}, stop:1 #b0b0b0);
        border: 1px solid {GRAY_DK};
        min-height: 20px; min-width: 20px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {WHITE}, stop:1 #bdbdbd);
        border: 1px solid {GRAY_DK};
        width: 16px; height: 16px;
    }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: #cdcdcd; }}

    QLabel {{ background: transparent; }}
    """


class ClassicTitleBar(QWidget):
    """A System 7 style pinstriped title bar with a square close box."""

    closeClicked = Signal()

    BAR_H = 22
    CLOSE = 13

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self.setFixedHeight(self.BAR_H)
        self.setAutoFillBackground(False)

    def _close_rect(self) -> QRect:
        y = (self.BAR_H - self.CLOSE) // 2
        return QRect(8, y, self.CLOSE, self.CLOSE)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        r = self.rect()
        p.fillRect(r, QColor(GRAY))

        # six pinstripes across the bar
        p.setPen(QPen(QColor(BLACK), 1))
        mid = r.center().y()
        gap = 2
        n = 6
        top = mid - (n * gap) // 2
        for i in range(n):
            y = top + i * gap
            p.drawLine(r.left() + 2, y, r.right() - 2, y)

        # title plate: interrupt the stripes behind centered text
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(self._title)
        plate = QRect(0, 0, tw + 20, self.BAR_H - 6)
        plate.moveCenter(QPoint(r.center().x(), mid))
        p.fillRect(plate, QColor(GRAY))
        p.setPen(QColor(BLACK))
        p.drawText(plate, Qt.AlignCenter, self._title)

        # close box: gray clear-out, then white square with black border
        cb = self._close_rect()
        clear = cb.adjusted(-2, -2, 2, 2)
        p.fillRect(clear, QColor(GRAY))
        p.fillRect(cb, QColor(WHITE))
        p.setPen(QPen(QColor(BLACK), 1))
        p.drawRect(cb)

        # bottom separator
        p.setPen(QPen(QColor(BLACK), 1))
        p.drawLine(r.left(), r.bottom(), r.right(), r.bottom())
        p.end()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            if self._close_rect().adjusted(-2, -2, 2, 2).contains(e.position().toPoint()):
                self.closeClicked.emit()
                return
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemMove()


def apply_classic_theme(app: QApplication) -> None:
    app.setFont(QFont("Geneva", 12))
    app.setStyleSheet(build_qss())

from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, QPoint, QRect, QSize, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontMetrics,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkDiskCache, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QStyleOptionButton,
    QStyleOptionComboBox,
    QStylePainter,
    QStatusBar,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .desktop_services import AppController, DesktopServices
from .repository import SPANISH_LANGUAGE_CODES, SPANISH_LANGUAGE_FILTER


YOUTUBE_FIRST_YEAR = 2005
CATALOG_CARD_BATCH_SIZE = 32
CATALOG_PAGE_SIZE = 160
STARTUP_BACKFILL_DELAY_MS = 2500
MANUAL_DISCOVERY_CANDIDATE_LIMIT = 250
THUMBNAIL_RENDER_SCALE = 1.0
CATALOG_BACKGROUND_COUNT_MAX_VIDEOS = 100_000
CATALOG_THUMBNAIL_PREFETCH_ROWS = 30
THUMBNAIL_MAX_ACTIVE_REQUESTS = 6
THUMBNAIL_MAX_PIXMAPS_PER_FRAME = 6
CATALOG_WHEEL_STEP_PX = 72
CATALOG_PIXEL_WHEEL_SCALE = 0.55

CatalogScrollAnchor = tuple[str | None, int, int, int | None, int]


def youtube_thumbnail_candidates(video_id: str | None, preferred_url: str | None = None) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def add(url: str | None) -> None:
        normalized = str(url or "").strip()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        candidates.append(normalized)

    add(preferred_url)
    video_key = str(video_id or "").strip()
    if video_key:
        add(f"https://i.ytimg.com/vi/{video_key}/hq720.jpg")
        add(f"https://i.ytimg.com/vi/{video_key}/sddefault.jpg")
        add(f"https://i.ytimg.com/vi/{video_key}/hqdefault.jpg")
        add(f"https://i.ytimg.com/vi/{video_key}/mqdefault.jpg")
        add(f"https://i.ytimg.com/vi/{video_key}/default.jpg")
    return candidates


APP_STYLE = """
QMainWindow {
    background: #070b10;
}
QWidget {
    color: #f4f7fc;
    font-family: "Segoe UI";
    font-size: 16px;
    background: transparent;
}
QWidget#appRoot,
QWidget#pageRoot {
    background: #070b10;
}
QMenuBar {
    background: transparent;
    color: #a6afbf;
}
QStatusBar {
    background: #0a1016;
    color: #aeb7c7;
    border-top: 1px solid #1a2530;
    min-height: 40px;
    padding-left: 22px;
    font-size: 14px;
}
QStatusBar::item {
    border: none;
}
QLineEdit, QComboBox, QSpinBox, QTextEdit {
    background: #10161e;
    border: 1px solid #2c3846;
    border-radius: 8px;
    padding: 12px 16px;
    color: #f4f7fc;
    min-height: 26px;
    selection-background-color: #1d7df2;
    selection-color: #ffffff;
}
QLineEdit[compactSource="true"], QComboBox[compactSource="true"], QSpinBox[compactSource="true"] {
    background: #0f2131;
    border: 2px solid #526b85;
    border-bottom: 3px solid #25c8f5;
    border-radius: 8px;
    color: #f6f9ff;
    padding: 8px 16px;
    min-height: 24px;
}
QLineEdit[compactSource="true"]:focus, QComboBox[compactSource="true"]:focus, QSpinBox[compactSource="true"]:focus {
    background: #12283c;
    border: 2px solid #6ce2ff;
    border-bottom: 3px solid #6ce2ff;
}
QComboBox[compactSource="true"]::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 52px;
    border-left: 1px solid #65809b;
    background: #173a55;
    border-top-right-radius: 7px;
    border-bottom-right-radius: 7px;
}
QSpinBox[compactSource="true"]::up-button, QSpinBox[compactSource="true"]::down-button {
    width: 52px;
    background: #173a55;
    border-left: 1px solid #65809b;
}
QSpinBox[compactSource="true"]::up-button:hover, QSpinBox[compactSource="true"]::down-button:hover {
    background: #1f4a6c;
}
QPushButton[sourceAction="true"] {
    background: #172638;
    border: 2px solid #52687f;
    border-bottom: 3px solid #2ea9d4;
    border-radius: 8px;
    color: #eef4ff;
}
QPushButton[sourceAction="true"]:hover {
    background: #1d3147;
    border: 2px solid #6d86a0;
    border-bottom: 3px solid #65dfff;
}
QPushButton[sourceAction="true"]:disabled {
    background: #121d2a;
    border: 2px solid #3f5062;
    border-bottom: 3px solid #45627c;
    color: #b2bdcb;
}
QPushButton[sourcePrimary="true"] {
    background: #237dee;
    color: #ffffff;
    border: 2px solid #52aeff;
    border-bottom: 3px solid #99e8ff;
    border-radius: 8px;
}
QPushButton[sourcePrimary="true"]:hover {
    background: #2688ff;
    border: 2px solid #75c5ff;
    border-bottom: 3px solid #b9f1ff;
}
QPushButton[sourcePrimary="true"]:disabled {
    background: #174978;
    border: 2px solid #38698f;
    border-bottom: 3px solid #4f89b8;
    color: #c0ccd8;
}
QLineEdit[compactCatalog="true"] {
    padding: 6px 12px;
    min-height: 22px;
}
QComboBox[compactCatalog="true"] {
    padding: 6px 34px 6px 12px;
    min-height: 22px;
}
QPushButton[compactCatalog="true"] {
    padding: 7px 14px;
    min-height: 20px;
}
QLabel[filterLabel="true"] {
    color: #a6afbf;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.08em;
}
QLabel[filterHint="true"] {
    color: #7e899a;
    font-size: 11px;
}
QComboBox {
    padding-right: 34px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border: none;
    background: transparent;
}
QComboBox QAbstractItemView {
    background: #10161e;
    color: #f2f4f8;
    border: 1px solid #2c3846;
    selection-background-color: #173a58;
    selection-color: #ffffff;
    outline: 0;
    padding: 0;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
    border: 1px solid #25c8f5;
}
QPushButton {
    background: #10161e;
    border: 1px solid #2c3846;
    border-radius: 8px;
    padding: 11px 18px;
    color: #dfe6f1;
    font-weight: 700;
}
QPushButton:hover {
    background: #151d27;
    border: 1px solid #3a4858;
}
QPushButton[role="primary"] {
    background: #1f75ee;
    color: #ffffff;
    border: 1px solid #2386ff;
    border-radius: 8px;
}
QPushButton[role="primary"]:hover {
    background: #2688ff;
}
QPushButton[role="topPrimary"] {
    background: #24c7f3;
    color: #071018;
    border: 1px solid #24c7f3;
    border-radius: 9px;
    font-weight: 800;
}
QPushButton[role="topPrimary"]:hover {
    background: #45d4ff;
    border: 1px solid #45d4ff;
}
QPushButton[role="ghost"] {
    background: #10161e;
    color: #d8e0ed;
    border: 1px solid #2c3846;
}
QPushButton[role="ghost"]:hover {
    background: #151d27;
    border: 1px solid #3a4858;
}
QPushButton[nav="true"] {
    background: transparent;
    color: #8892a5;
    border: 1px solid transparent;
    border-radius: 0px;
    padding: 15px 16px 12px 16px;
    font-size: 16px;
    font-weight: 700;
    text-align: center;
}
QPushButton[nav="true"]:hover {
    color: #d0d6e2;
}
QPushButton[active="true"] {
    color: #ffffff;
    border-bottom: 2px solid #25c8f5;
}
QCheckBox {
    spacing: 12px;
    color: #f4f7fc;
    font-size: 16px;
}
QCheckBox::indicator {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    border: 1px solid #3a4655;
    background: #10161e;
}
QCheckBox::indicator:checked {
    background: #1f75ee;
    border: 1px solid #2386ff;
}
QCheckBox[topbarAutoSearch="true"] {
    color: #aeb8c9;
    font-size: 13px;
    font-weight: 700;
    spacing: 8px;
    padding: 0px 8px;
}
QCheckBox[topbarAutoSearch="true"]::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid #3f5062;
    background: #0f1720;
}
QCheckBox[topbarAutoSearch="true"]::indicator:checked {
    background: #0f1720;
    border: 1px solid #25c8f5;
}
QCheckBox[catalogFavoriteFilter="true"] {
    color: #d8e0ed;
    font-size: 14px;
    font-weight: 700;
    spacing: 8px;
    padding-bottom: 6px;
}
QCheckBox[catalogFavoriteFilter="true"]::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid #3f5062;
    background: #10161e;
}
QCheckBox[catalogFavoriteFilter="true"]::indicator:checked {
    background: #1f75ee;
    border: 1px solid #4ba3ff;
}
QTableWidget {
    background: transparent;
    border: none;
    gridline-color: #2a3542;
    color: #f0f4fa;
    selection-background-color: #173a58;
    selection-color: #ffffff;
    font-size: 16px;
}
QHeaderView::section {
    background: transparent;
    color: #aab3c3;
    border: none;
    border-bottom: 1px solid #2a3542;
    padding: 16px 22px;
    font-size: 16px;
    font-weight: 700;
}
QTableCornerButton::section {
    background: transparent;
    border: none;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background: #0a1016;
    width: 12px;
    border-radius: 6px;
    margin: 4px 0 4px 0;
}
QScrollBar::handle:vertical {
    background: #283544;
    border-radius: 6px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover {
    background: #35485d;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QProgressBar {
    background: #0d1319;
    border: 1px solid #1e2a38;
    border-radius: 999px;
    min-height: 8px;
    max-height: 8px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1a8fb8, stop:0.5 #25c8f5, stop:1 #48d4ff);
    border-radius: 999px;
}
"""


SOURCE_TEXT_CONTROL_STYLE = """
QLineEdit {
    background: #0f2131;
    border: 2px solid #526b85;
    border-bottom: 3px solid #25c8f5;
    border-radius: 8px;
    color: #f6f9ff;
    padding: 8px 16px;
}
QLineEdit:focus {
    background: #12283c;
    border: 2px solid #6ce2ff;
    border-bottom: 3px solid #6ce2ff;
}
"""

SOURCE_COMBO_STYLE = """
QComboBox {
    background: #0f2131;
    border: 2px solid #526b85;
    border-bottom: 3px solid #25c8f5;
    border-radius: 8px;
    color: #f6f9ff;
    padding: 8px 58px 8px 16px;
}
QComboBox:focus {
    background: #12283c;
    border: 2px solid #6ce2ff;
    border-bottom: 3px solid #6ce2ff;
}
QComboBox::drop-down {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 54px;
    background: #173a55;
    border-left: 1px solid #65809b;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}
QComboBox::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
}
"""

SOURCE_SPIN_STYLE = """
QSpinBox {
    background: #0f2131;
    border: 2px solid #526b85;
    border-bottom: 3px solid #25c8f5;
    border-radius: 8px;
    color: #f6f9ff;
    padding: 8px 58px 8px 16px;
}
QSpinBox:focus {
    background: #12283c;
    border: 2px solid #6ce2ff;
    border-bottom: 3px solid #6ce2ff;
}
QSpinBox::up-button, QSpinBox::down-button {
    subcontrol-origin: border;
    width: 54px;
    background: #173a55;
    border-left: 1px solid #65809b;
}
QSpinBox::up-button {
    subcontrol-position: top right;
    border-top-right-radius: 6px;
}
QSpinBox::down-button {
    subcontrol-position: bottom right;
    border-bottom-right-radius: 6px;
}
QSpinBox::up-arrow, QSpinBox::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
}
"""

SOURCE_SECONDARY_BUTTON_STYLE = """
QPushButton {
    background: #172638;
    border: 2px solid #52687f;
    border-bottom: 3px solid #2ea9d4;
    border-radius: 8px;
    color: #eef4ff;
    font-weight: 800;
}
QPushButton:hover {
    background: #1d3147;
    border: 2px solid #6d86a0;
    border-bottom: 3px solid #65dfff;
}
QPushButton:pressed {
    background: #102236;
    border: 2px solid #39cfff;
}
QPushButton:disabled {
    background: #121d2a;
    border: 2px solid #3f5062;
    border-bottom: 3px solid #45627c;
    color: #b2bdcb;
}
"""

SOURCE_PRIMARY_BUTTON_STYLE = """
QPushButton {
    background: #237dee;
    color: #ffffff;
    border: 2px solid #52aeff;
    border-bottom: 3px solid #99e8ff;
    border-radius: 8px;
    font-weight: 800;
}
QPushButton:hover {
    background: #2688ff;
    border: 2px solid #75c5ff;
    border-bottom: 3px solid #b9f1ff;
}
QPushButton:pressed {
    background: #1766d3;
    border: 2px solid #9ce7ff;
}
QPushButton:disabled {
    background: #174978;
    border: 2px solid #38698f;
    border-bottom: 3px solid #4f89b8;
    color: #c0ccd8;
}
"""


def card_frame(name: str = "card") -> QFrame:
    frame = QFrame()
    frame.setObjectName(name)
    return frame


def apply_card_style(widget: QWidget, border_accent: bool = False) -> None:
    border = "#25c8f5" if border_accent else "#2a3542"
    widget.setStyleSheet(
        f"""
        QWidget#{widget.objectName()} {{
            background: #111820;
            border: 1px solid {border};
            border-radius: 10px;
        }}
        """
    )


def status_chip(status: str) -> str:
    mapping = {
        "running": "#2ea3c6",
        "completed": "#32d296",
        "failed": "#ff6f76",
        "queued": "#f2c46d",
    }
    color = mapping.get(status, "#a6adbb")
    return f"● {status}", color

class ComboItemDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):  # type: ignore[override]
        size = super().sizeHint(option, index)
        size.setHeight(max(size.height(), 48))
        return size


class CatalogFilterComboBox(QComboBox):
    def __init__(self, display_prefix: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._display_prefix = display_prefix

    def set_display_prefix(self, prefix: str) -> None:
        self._display_prefix = prefix
        self.update()

    def display_text(self) -> str:
        current = self.currentText()
        if self._display_prefix and current:
            return f"{self._display_prefix}: {current}"
        return current

    def paintEvent(self, event: Any) -> None:  # type: ignore[override]
        painter = QStylePainter(self)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        option.currentText = self.display_text()
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)
        painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, option)
        self._draw_chevron(painter, option)

    def _draw_chevron(self, painter: QPainter, option: QStyleOptionComboBox) -> None:
        arrow_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxArrow,
            self,
        )
        if arrow_rect.isNull() or arrow_rect.width() < 10:
            arrow_rect = QRect(self.width() - 32, 0, 24, self.height())
        center = arrow_rect.center()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(
            QPen(
                QColor("#aeb8c9"),
                2,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.drawLine(QPoint(center.x() - 5, center.y() - 3), QPoint(center.x(), center.y() + 3))
        painter.drawLine(QPoint(center.x(), center.y() + 3), QPoint(center.x() + 5, center.y() - 3))
        painter.restore()


def style_combo_popup(combo: QComboBox) -> None:
    combo.setView(QListView(combo))
    combo.view().setItemDelegate(ComboItemDelegate(combo.view()))
    combo.view().setSpacing(0)
    combo.view().setUniformItemSizes(True)
    combo.view().setContentsMargins(0, 0, 0, 0)
    combo.setMaxVisibleItems(12)
    combo.view().setStyleSheet(
        """
        QListView {
            background: #10161e;
            color: #f2f4f8;
            border: 1px solid #2c3846;
            outline: 0;
            padding: 0;
            font-size: 15px;
        }
        QListView::item {
            border: none;
            min-height: 24px;
            padding: 12px 14px;
        }
        QListView::item:selected {
            background: #173a58;
            color: #ffffff;
        }
        QListView::item:hover {
            background: #151d27;
        }
        """
    )


def make_year_combo(empty_text: str) -> CatalogFilterComboBox:
    combo = CatalogFilterComboBox()
    combo.setEditable(False)
    combo.addItem(empty_text, None)
    current_year = datetime.now().year
    for year in range(current_year, YOUTUBE_FIRST_YEAR - 1, -1):
        combo.addItem(str(year), year)
    style_combo_popup(combo)
    combo.setMaxVisibleItems(14)
    combo.setCurrentIndex(0)
    return combo


def make_max_duration_combo() -> CatalogFilterComboBox:
    combo = CatalogFilterComboBox()
    combo.setEditable(False)
    combo.addItem("Cualquier duración", None)
    for minutes in range(10, 61, 10):
        combo.addItem(f"Hasta {minutes} min", minutes * 60)
    style_combo_popup(combo)
    combo.setMaxVisibleItems(8)
    combo.setCurrentIndex(0)
    return combo


def combo_year_value(combo: QComboBox) -> int | None:
    data = combo.currentData()
    if isinstance(data, int):
        return data
    text = combo.currentText().strip()
    if not text:
        return None
    if text.isdigit():
        year = int(text)
        current_year = datetime.now().year
        if YOUTUBE_FIRST_YEAR <= year <= current_year:
            return year
    return None


def combo_duration_value(combo: QComboBox) -> int | None:
    data = combo.currentData()
    if isinstance(data, int) and data > 0:
        return data
    return None


def inline_field(label_text: str, control: QWidget) -> QWidget:
    shell = QWidget()
    layout = QVBoxLayout(shell)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    label = QLabel(label_text)
    label.setProperty("filterLabel", "true")
    layout.addWidget(label)
    layout.addWidget(control)
    return shell


def form_field(label_text: str, control: QWidget) -> tuple[QWidget, QLabel]:
    shell = QWidget()
    layout = QVBoxLayout(shell)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    label = QLabel(label_text)
    label.setStyleSheet("color: #f4f7fc; font-size: 16px; font-weight: 700;")
    layout.addWidget(label)
    layout.addWidget(control)
    return shell, label


def pretty_source_type(value: str) -> str:
    mapping = {
        "channel": "Canal",
        "search": "Búsqueda",
    }
    return mapping.get(value, value)


FULL_SOURCE_STATE = 'LLENO - Presiona "Aumentar Límite"'


def source_is_full(source: dict[str, Any]) -> bool:
    return bool(int(source.get("is_full") or 0))


def pretty_source_state(enabled: bool, is_full: bool = False) -> str:
    if is_full:
        return FULL_SOURCE_STATE
    return "Activa" if enabled else "Pausada"


def pretty_run_scope(scope: str, source_lookup: dict[int, str] | None = None) -> str:
    if scope == "all":
        return "Todas tus búsquedas"
    if scope == "metadata":
        return "actualizando fechas"
    if scope.startswith("source:"):
        try:
            source_id = int(scope.split(":", 1)[1])
        except ValueError:
            return scope
        if source_lookup and source_id in source_lookup:
            return source_lookup[source_id]
        return f"Búsqueda #{source_id}"
    return scope


def friendly_status_text(status: str) -> str:
    mapping = {
        "running": "En curso",
        "completed": "Listo",
        "failed": "Con error",
        "queued": "En espera",
    }
    return mapping.get(status, status)


def clear_layout(layout: QGridLayout | QVBoxLayout | QHBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child_widget = item.widget()
        child_layout = item.layout()
        if child_widget is not None:
            child_widget.hide()
            child_widget.setParent(None)
            child_widget.deleteLater()
        elif child_layout is not None:
            clear_layout(child_layout)


def format_duration(seconds: int | None) -> str:
    if not seconds:
        return ""
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def short_timestamp(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).replace("T", " ")
    return text[:16]


def format_published_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        normalized = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            dt = datetime.strptime(str(value)[:10], "%Y-%m-%d")
        except ValueError:
            return str(value)
    months = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    return f"{dt.day} {months[dt.month - 1]} {dt.year}"


def truncate_text(value: str | None, limit: int) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def relative_time(value: str | None) -> str:
    if not value:
        return ""
    try:
        timestamp = datetime.fromisoformat(str(value))
    except ValueError:
        return short_timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 60:
        return "hace unos segundos"
    if seconds < 3600:
        return f"hace {seconds // 60} min"
    if seconds < 86400:
        return f"hace {seconds // 3600} h"
    return f"hace {seconds // 86400} d"


def latest_timestamp(*values: str | None) -> str | None:
    latest_value: str | None = None
    latest_dt: datetime | None = None
    for value in values:
        if not value:
            continue
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        parsed = parsed.astimezone(timezone.utc)
        if latest_dt is None or parsed > latest_dt:
            latest_dt = parsed
            latest_value = str(value)
    return latest_value


def humanize_exception(error: Exception) -> str:
    raw = str(error).strip()
    if not raw:
        return "Ha ocurrido un error inesperado."

    normalized = raw.lower()
    normalized = normalized.replace("ejecuciã³n", "ejecución").replace("bãºsqueda", "búsqueda")
    if "ya hay un scraping en ejecución" in normalized or "ya hay un scraping en ejecuci" in normalized:
        return "Ya hay una búsqueda en curso. Espera a que termine la actual."
    if "no hay fuentes habilitadas" in normalized:
        return "No hay búsquedas activas para revisar."
    if "fuente no encontrada" in normalized:
        return "Esa búsqueda ya no existe."
    if "invalid channel url format" in normalized:
        return "Ese enlace de YouTube no parece un canal válido."
    if "ytinitialplayerresponse" in normalized:
        return "YouTube no devolvió la información esperada para ese video."
    if "node.js" in normalized:
        return "No se encontró Node.js y la comprobación del video no pudo completarse."

    return (
        raw.replace("Fuente", "Búsqueda")
        .replace("fuente", "búsqueda")
        .replace("scraping", "búsqueda")
        .replace("run", "búsqueda")
    )


class CatalogCard(QFrame):
    def __init__(
        self,
        item: dict[str, Any],
        card_width: int,
        size_mode: str,
        on_open: Callable[[dict[str, Any]], None],
        on_toggle_favorite: Callable[[dict[str, Any], bool], None],
    ) -> None:
        super().__init__()
        self.item = item
        self._on_open = on_open
        self._on_toggle_favorite = on_toggle_favorite
        self._hovered = False
        size_tokens = {
            "Grande": {
                "thumb_min": 184,
                "title_size": 15,
                "title_height": 62,
                "channel_size": 14,
                "meta_size": 13,
                "badge_size": 13,
                "badge_padding": "5px 10px",
                "body_padding": 14,
            },
            "Compacto": {
                "thumb_min": 128,
                "title_size": 14,
                "title_height": 48,
                "channel_size": 12,
                "meta_size": 11,
                "badge_size": 11,
                "badge_padding": "3px 7px",
                "body_padding": 12,
            },
        }
        token = size_tokens.get(
            size_mode,
            {
                "thumb_min": 164,
                "title_size": 16,
                "title_height": 62,
                "channel_size": 13,
                "meta_size": 12,
                "badge_size": 12,
                "badge_padding": "4px 8px",
                "body_padding": 14,
            },
        )
        self.thumbnail_size = QSize(card_width, max(token["thumb_min"], round(card_width * 9 / 16)))

        self.setObjectName("catalogCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedWidth(card_width)
        self.setStyleSheet(
            """
            QFrame#catalogCard {
                background: #151a1f;
                border: 1px solid #2a3542;
                border-radius: 8px;
            }
            QFrame#catalogCard:hover {
                border: 1px solid #25c8f5;
                background: #171e25;
            }
            QLabel[role="title"] {
                color: #f4f7fc;
                font-size: %dpx;
                font-weight: 700;
            }
            QLabel[role="channel"] {
                color: #a2abb9;
                font-size: %dpx;
            }
            QLabel[role="meta"] {
                color: #a0a8b5;
                font-size: %dpx;
            }
            QLabel[role="open"] {
                color: #aab3c3;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel[role="badge"] {
                background: rgba(10, 12, 18, 0.92);
                border: 1px solid #2d3440;
                border-radius: 5px;
                color: #ffffff;
                font-size: %dpx;
                font-weight: 700;
                padding: %s;
            }
            """
            % (
                token["title_size"],
                token["channel_size"],
                token["meta_size"],
                token["badge_size"],
                token["badge_padding"],
            )
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, token["body_padding"])
        layout.setSpacing(12 if size_mode != "Compacto" else 10)

        thumb_shell = QFrame()
        thumb_shell.setObjectName("thumbnailShell")
        thumb_shell.setFixedSize(self.thumbnail_size)
        thumb_shell.setStyleSheet(
            """
            QFrame#thumbnailShell {
                background: #10161e;
                border: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            """
        )
        thumb_layout = QGridLayout(thumb_shell)
        thumb_layout.setContentsMargins(0, 0, 0, 0)

        self.thumbnail_label = QLabel("Cargando thumbnail")
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setFixedSize(self.thumbnail_size)
        self.thumbnail_label.setStyleSheet(
            "color: #758091; background: #10161e; border-top-left-radius: 8px; border-top-right-radius: 8px;"
        )
        thumb_layout.addWidget(self.thumbnail_label, 0, 0)

        self.favorite_button = QPushButton()
        self.favorite_button.setObjectName("favoriteButton")
        self.favorite_button.setFocusPolicy(Qt.NoFocus)
        self.favorite_button.setCursor(Qt.PointingHandCursor)
        self.favorite_button.setFixedSize(34, 34)
        self.favorite_button.clicked.connect(self.handle_favorite_clicked)
        thumb_layout.addWidget(self.favorite_button, 0, 0, alignment=Qt.AlignRight | Qt.AlignTop)
        self.sync_favorite_button()

        duration_text = format_duration(item.get("duration_seconds"))
        if duration_text:
            duration_badge = QLabel(duration_text)
            duration_badge.setProperty("role", "badge")
            thumb_layout.addWidget(duration_badge, 0, 0, alignment=Qt.AlignRight | Qt.AlignBottom)

        layout.addWidget(thumb_shell)

        body = QVBoxLayout()
        body.setContentsMargins(token["body_padding"], 0, token["body_padding"], 0)
        body.setSpacing(6 if size_mode != "Compacto" else 5)

        title = QLabel(item["title"])
        title.setProperty("role", "title")
        title.setWordWrap(True)
        title.setMaximumHeight(token["title_height"])
        title.setToolTip(item["title"])
        body.addWidget(title)

        channel = QLabel(item.get("channel") or "Canal desconocido")
        channel.setProperty("role", "channel")
        channel.setToolTip(item.get("channel") or "")
        body.addWidget(channel)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 2, 0, 0)
        footer.setSpacing(8)
        meta = QLabel(format_published_date(item.get("published_at")) or "Fecha desconocida")
        meta.setProperty("role", "meta")
        footer.addWidget(meta)
        footer.addStretch(1)
        open_hint = QLabel("↗")
        open_hint.setProperty("role", "open")
        footer.addWidget(open_hint)
        body.addLayout(footer)
        layout.addLayout(body)

    def is_favorite(self) -> bool:
        return bool(self.item.get("is_favorite"))

    def sync_favorite_button(self) -> None:
        favorite = self.is_favorite()
        self.favorite_button.setText("★" if favorite else "☆")
        self.favorite_button.setToolTip("Quitar de favoritos" if favorite else "Agregar a favoritos")
        self.favorite_button.setVisible(favorite or self._hovered)
        color = "#ffd75a" if favorite else "#f4f7fc"
        border = "#6a5621" if favorite else "#384656"
        self.favorite_button.setStyleSheet(
            f"""
            QPushButton#favoriteButton {{
                background: rgba(9, 12, 17, 0.88);
                border: 1px solid {border};
                border-radius: 7px;
                color: {color};
                font-size: 20px;
                font-weight: 800;
                padding: 0px;
            }}
            QPushButton#favoriteButton:hover {{
                background: rgba(14, 18, 24, 0.96);
                border: 1px solid #ffd75a;
                color: #ffd75a;
            }}
            """
        )

    def handle_favorite_clicked(self) -> None:
        next_value = not self.is_favorite()
        self.item["is_favorite"] = 1 if next_value else 0
        self.sync_favorite_button()
        self._on_toggle_favorite(self.item, next_value)

    def enterEvent(self, event: Any) -> None:
        self._hovered = True
        self.sync_favorite_button()
        super().enterEvent(event)

    def leaveEvent(self, event: Any) -> None:
        self._hovered = False
        self.sync_favorite_button()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._on_open(self.item)
        super().mousePressEvent(event)


CATALOG_ITEM_ROLE = Qt.ItemDataRole.UserRole + 1
CATALOG_PIXMAP_ROLE = Qt.ItemDataRole.UserRole + 2


class CatalogListModel(QAbstractListModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.items: list[dict[str, Any]] = []
        self._pixmaps: dict[str, QPixmap] = {}
        self._url_rows: dict[str, set[int]] = {}

    def _index_thumbnail_rows(self) -> None:
        self._url_rows = {}
        for row, item in enumerate(self.items):
            url = str(item.get("thumbnail_url") or "")
            if url:
                self._url_rows.setdefault(url, set()).add(row)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(self.items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # type: ignore[override]
        if not index.isValid() or index.row() < 0 or index.row() >= len(self.items):
            return None
        item = self.items[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, CATALOG_ITEM_ROLE):
            return item
        if role == CATALOG_PIXMAP_ROLE:
            url = str(item.get("thumbnail_url") or "")
            return self._pixmaps.get(url)
        return None

    def set_items(self, items: list[dict[str, Any]]) -> None:
        if self.items == list(items):
            return
        self.beginResetModel()
        self.items = list(items)
        self._index_thumbnail_rows()
        self.endResetModel()

    def append_items(self, items: list[dict[str, Any]]) -> None:
        if not items:
            return
        start = len(self.items)
        self.beginInsertRows(QModelIndex(), start, start + len(items) - 1)
        self.items.extend(items)
        for offset, item in enumerate(items):
            url = str(item.get("thumbnail_url") or "")
            if url:
                self._url_rows.setdefault(url, set()).add(start + offset)
        self.endInsertRows()

    def set_thumbnail(self, url: str, pixmap: QPixmap) -> None:
        self.set_thumbnails_batch({url: pixmap})

    def set_thumbnail_url(self, row: int, url: str) -> None:
        if row < 0 or row >= len(self.items):
            return
        normalized = str(url or "").strip()
        if not normalized:
            return
        item = self.items[row]
        old_url = str(item.get("thumbnail_url") or "")
        if old_url == normalized:
            return
        if old_url:
            rows = self._url_rows.get(old_url)
            if rows is not None:
                rows.discard(row)
                if not rows:
                    self._url_rows.pop(old_url, None)
        item["thumbnail_url"] = normalized
        self._url_rows.setdefault(normalized, set()).add(row)
        index = self.index(row, 0)
        self.dataChanged.emit(index, index, [CATALOG_ITEM_ROLE, CATALOG_PIXMAP_ROLE])

    def set_thumbnails_batch(self, pixmaps: dict[str, QPixmap]) -> None:
        changed_rows: set[int] = set()
        for url, pixmap in pixmaps.items():
            if not url or pixmap.isNull():
                continue
            self._pixmaps[url] = pixmap
            changed_rows.update(self._url_rows.get(url, set()))
        if not changed_rows:
            return
        ranges: list[tuple[int, int]] = []
        start: int | None = None
        previous: int | None = None
        for row in sorted(changed_rows):
            if start is None:
                start = previous = row
                continue
            if previous is not None and row == previous + 1:
                previous = row
                continue
            ranges.append((start, previous if previous is not None else start))
            start = previous = row
        if start is not None:
            ranges.append((start, previous if previous is not None else start))
        for first_row, last_row in ranges:
            self.dataChanged.emit(
                self.index(first_row, 0),
                self.index(last_row, 0),
                [CATALOG_PIXMAP_ROLE],
            )

    def set_favorite(self, video_id: str, is_favorite: bool) -> None:
        for row, item in enumerate(self.items):
            if str(item.get("video_id")) != video_id:
                continue
            item["is_favorite"] = 1 if is_favorite else 0
            index = self.index(row, 0)
            self.dataChanged.emit(index, index, [CATALOG_ITEM_ROLE])
            return

    def item_at(self, row: int) -> dict[str, Any] | None:
        if row < 0 or row >= len(self.items):
            return None
        return self.items[row]


class CatalogCardDelegate(QStyledItemDelegate):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.card_width = 300
        self.card_height = 360
        self.size_mode = "Medio"
        self.hovered_row = -1
        self._font_cache: dict[tuple[int, bool], QFont] = {}
        self._metrics_cache: dict[tuple[int, bool], QFontMetrics] = {}
        self._elided_cache: OrderedDict[tuple[str, int, bool, int, int], list[str]] = OrderedDict()
        self._duration_cache: dict[tuple[Any, Any], str] = {}
        self._date_cache: dict[tuple[Any, Any], str] = {}

    def configure(self, card_width: int, size_mode: str) -> None:
        self.card_width = max(200, int(card_width))
        self.size_mode = size_mode
        thumb_height = self.thumbnail_height()
        body_height = 104 if size_mode != "Compacto" else 92
        self.card_height = thumb_height + body_height

    def thumbnail_height(self) -> int:
        minimum = 128 if self.size_mode == "Compacto" else 164
        return max(minimum, round(self.card_width * 9 / 16))

    def sizeHint(self, option: Any, index: QModelIndex) -> QSize:  # type: ignore[override]
        return QSize(self.card_width, self.card_height)

    def star_rect(self, item_rect: QRect) -> QRect:
        return QRect(item_rect.right() - 44, item_rect.top() + 10, 34, 34)

    def _font(self, pixel_size: int, *, bold: bool = False) -> QFont:
        key = (int(pixel_size), bool(bold))
        font = self._font_cache.get(key)
        if font is None:
            font = QFont("Segoe UI")
            font.setPixelSize(pixel_size)
            font.setBold(bold)
            self._font_cache[key] = font
        return font

    def _font_metrics(self, pixel_size: int, *, bold: bool = False) -> QFontMetrics:
        key = (int(pixel_size), bool(bold))
        metrics = self._metrics_cache.get(key)
        if metrics is None:
            metrics = QFontMetrics(self._font(pixel_size, bold=bold))
            self._metrics_cache[key] = metrics
        return metrics

    def _elided_lines(
        self,
        text: str,
        font_metrics: QFontMetrics,
        width: int,
        max_lines: int,
        *,
        font_key: tuple[int, bool],
    ) -> list[str]:
        cache_key = (str(text or ""), font_key[0], font_key[1], int(width), int(max_lines))
        cached = self._elided_cache.get(cache_key)
        if cached is not None:
            self._elided_cache.move_to_end(cache_key)
            return cached
        words = str(text or "").strip().split()
        if not words:
            return []
        lines: list[str] = []
        current = ""
        index = 0
        while index < len(words) and len(lines) < max_lines:
            word = words[index]
            candidate = f"{current} {word}".strip()
            if not current or font_metrics.horizontalAdvance(candidate) <= width:
                current = candidate
                index += 1
                continue
            if len(lines) == max_lines - 1:
                remainder = f"{current} {' '.join(words[index:])}".strip()
                lines.append(font_metrics.elidedText(remainder, Qt.TextElideMode.ElideRight, width))
                return lines
            lines.append(current)
            current = ""
        if current and len(lines) < max_lines:
            if index < len(words):
                current = f"{current} {' '.join(words[index:])}".strip()
            lines.append(font_metrics.elidedText(current, Qt.TextElideMode.ElideRight, width))
        self._elided_cache[cache_key] = lines
        if len(self._elided_cache) > 2048:
            self._elided_cache.popitem(last=False)
        return lines

    def _draw_elided_lines(
        self,
        painter: QPainter,
        text: str,
        rect: QRect,
        font: QFont,
        color: QColor,
        max_lines: int,
    ) -> int:
        painter.setFont(font)
        painter.setPen(color)
        pixel_size = max(1, font.pixelSize())
        font_key = (pixel_size, bool(font.bold()))
        metrics = self._font_metrics(pixel_size, bold=font_key[1])
        line_height = metrics.lineSpacing()
        lines = self._elided_lines(text, metrics, rect.width(), max_lines, font_key=font_key)
        for offset, line in enumerate(lines):
            line_rect = QRect(rect.left(), rect.top() + offset * line_height, rect.width(), line_height)
            painter.drawText(
                line_rect,
                Qt.TextFlag.TextSingleLine | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                line,
            )
        return max(1, len(lines)) * line_height

    def _duration_text(self, item: dict[str, Any]) -> str:
        key = (item.get("video_id"), item.get("duration_seconds"))
        cached = self._duration_cache.get(key)
        if cached is None:
            cached = format_duration(item.get("duration_seconds"))
            self._duration_cache[key] = cached
        return cached

    def _published_text(self, item: dict[str, Any]) -> str:
        key = (item.get("video_id"), item.get("published_at"))
        cached = self._date_cache.get(key)
        if cached is None:
            cached = format_published_date(item.get("published_at")) or "Fecha desconocida"
            self._date_cache[key] = cached
        return cached

    def paint(self, painter: QPainter, option: Any, index: QModelIndex) -> None:  # type: ignore[override]
        item = index.data(CATALOG_ITEM_ROLE)
        if not item:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        card_rect = option.rect.adjusted(4, 4, -4, -4)
        bg = QColor("#181e26") if index.row() == self.hovered_row else QColor("#131920")
        border = QColor("#30b8e8") if index.row() == self.hovered_row else QColor("#222d3a")
        painter.setPen(border)
        painter.setBrush(bg)
        painter.drawRoundedRect(card_rect, 10, 10)

        thumb_height = self.thumbnail_height()
        thumb_rect = QRect(card_rect.left(), card_rect.top(), card_rect.width(), thumb_height)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#10161e"))
        painter.drawRoundedRect(thumb_rect, 8, 8)

        pixmap = index.data(CATALOG_PIXMAP_ROLE)
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            painter.setClipRect(thumb_rect)
            source = QRect(
                max(0, (pixmap.width() - thumb_rect.width()) // 2),
                max(0, (pixmap.height() - thumb_rect.height()) // 2),
                min(thumb_rect.width(), pixmap.width()),
                min(thumb_rect.height(), pixmap.height()),
            )
            painter.drawPixmap(thumb_rect, pixmap, source)
            painter.setClipping(False)
        else:
            painter.setPen(QColor("#758091"))
            painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, "")

        duration = self._duration_text(item)
        if duration:
            font = self._font(14, bold=True)
            painter.setFont(font)
            fm = self._font_metrics(14, bold=True)
            badge_width = fm.horizontalAdvance(duration) + 16
            badge_rect = QRect(
                thumb_rect.right() - badge_width - 8,
                thumb_rect.bottom() - 30,
                badge_width,
                24,
            )
            painter.setPen(QColor("#2d3440"))
            painter.setBrush(QColor(10, 12, 18, 235))
            painter.drawRoundedRect(badge_rect, 5, 5)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, duration)

        favorite = bool(item.get("is_favorite"))
        if favorite or index.row() == self.hovered_row:
            star_rect = self.star_rect(card_rect)
            painter.setPen(QColor("#6a5621" if favorite else "#384656"))
            painter.setBrush(QColor(9, 12, 17, 225))
            painter.drawRoundedRect(star_rect, 7, 7)
            star_font = self._font(20, bold=True)
            painter.setFont(star_font)
            painter.setPen(QColor("#ffd75a" if favorite else "#f4f7fc"))
            painter.drawText(star_rect, Qt.AlignmentFlag.AlignCenter, "★" if favorite else "☆")

        left = card_rect.left() + 14
        right = card_rect.right() - 14
        content_top = thumb_rect.bottom() + (8 if self.size_mode != "Compacto" else 6)
        title_font = self._font(16 if self.size_mode != "Compacto" else 14, bold=True)
        title_metrics = self._font_metrics(16 if self.size_mode != "Compacto" else 14, bold=True)
        max_title_lines = 2
        title_rect = QRect(
            left,
            content_top,
            right - left,
            title_metrics.lineSpacing() * max_title_lines,
        )
        used_title_height = self._draw_elided_lines(
            painter,
            str(item.get("title") or ""),
            title_rect,
            title_font,
            QColor("#f4f7fc"),
            max_title_lines,
        )

        channel_font = self._font(13 if self.size_mode != "Compacto" else 12)
        painter.setFont(channel_font)
        painter.setPen(QColor("#a2abb9"))
        channel_metrics = self._font_metrics(13 if self.size_mode != "Compacto" else 12)
        channel_top = content_top + used_title_height + 4
        channel_rect = QRect(left, channel_top, right - left, channel_metrics.lineSpacing())
        channel_text = channel_metrics.elidedText(
            str(item.get("channel") or "Canal desconocido"),
            Qt.TextElideMode.ElideRight,
            channel_rect.width(),
        )
        painter.drawText(
            channel_rect,
            Qt.TextFlag.TextSingleLine | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            channel_text,
        )

        meta_font = self._font(12 if self.size_mode != "Compacto" else 11)
        painter.setFont(meta_font)
        painter.setPen(QColor("#a0a8b5"))
        meta_metrics = self._font_metrics(12 if self.size_mode != "Compacto" else 11)
        meta_top = min(
            channel_rect.bottom() + 3,
            card_rect.bottom() - meta_metrics.lineSpacing() - 6,
        )
        meta_rect = QRect(left, meta_top, right - left - 28, meta_metrics.lineSpacing())
        meta_text = self._published_text(item)
        painter.drawText(
            meta_rect,
            Qt.TextFlag.TextSingleLine | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            meta_metrics.elidedText(meta_text, Qt.TextElideMode.ElideRight, meta_rect.width()),
        )
        painter.setPen(QColor("#aab3c3"))
        painter.drawText(
            QRect(card_rect.right() - 36, meta_rect.top(), 24, meta_rect.height()),
            Qt.AlignmentFlag.AlignCenter,
            "↗",
        )
        painter.restore()


class CatalogListView(QListView):
    favoriteToggled = Signal(dict, bool)
    openRequested = Signal(dict)
    nearBottom = Signal()
    visibleRowsChanged = Signal()

    def __init__(self, delegate: CatalogCardDelegate, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._delegate = delegate
        self.setMouseTracking(True)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setWrapping(True)
        self.setLayoutMode(QListView.LayoutMode.Batched)
        self.setBatchSize(48)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSpacing(12)
        self.verticalScrollBar().setSingleStep(CATALOG_WHEEL_STEP_PX)
        self._wheel_remainder = 0.0
        self.verticalScrollBar().valueChanged.connect(self._handle_scroll)
        self.setStyleSheet(
            """
            QListView {
                background: #0c1218;
                border: 1px solid #161f29;
                border-radius: 10px;
                padding: 14px;
            }
            QListView::item {
                background: transparent;
                border: none;
            }
            """
        )

    def set_card_geometry(self, card_width: int, card_height: int) -> None:
        grid_size = QSize(card_width + self.spacing(), card_height + self.spacing())
        if self.gridSize() == grid_size:
            return
        self.setGridSize(grid_size)
        self.viewport().update()
        self.visibleRowsChanged.emit()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        index = self.indexAt(event.pos())
        hovered_row = index.row() if index.isValid() else -1
        if hovered_row != self._delegate.hovered_row:
            old_row = self._delegate.hovered_row
            self._delegate.hovered_row = hovered_row
            for row in (old_row, hovered_row):
                if row >= 0:
                    rect = self.visualRect(self.model().index(row, 0))
                    self.viewport().update(rect)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: Any) -> None:  # type: ignore[override]
        if self._delegate.hovered_row >= 0 and self.model() is not None:
            rect = self.visualRect(self.model().index(self._delegate.hovered_row, 0))
            self._delegate.hovered_row = -1
            self.viewport().update(rect)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            index = self.indexAt(event.pos())
            if index.isValid():
                item = index.data(CATALOG_ITEM_ROLE)
                if item:
                    card_rect = self.visualRect(index).adjusted(4, 4, -4, -4)
                    if self._delegate.star_rect(card_rect).contains(event.pos()):
                        self.favoriteToggled.emit(item, not bool(item.get("is_favorite")))
                    else:
                        self.openRequested.emit(item)
                    return
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self.visibleRowsChanged.emit()

    def wheelEvent(self, event: QWheelEvent) -> None:  # type: ignore[override]
        bar = self.verticalScrollBar()
        pixel_delta = event.pixelDelta().y()
        if pixel_delta:
            delta = float(pixel_delta) * CATALOG_PIXEL_WHEEL_SCALE
        else:
            delta = (float(event.angleDelta().y()) / 120.0) * CATALOG_WHEEL_STEP_PX
        if not delta:
            event.accept()
            return
        adjusted_delta = delta + self._wheel_remainder
        whole_delta = int(adjusted_delta)
        self._wheel_remainder = adjusted_delta - whole_delta
        old_value = bar.value()
        if whole_delta:
            target_value = max(bar.minimum(), min(bar.maximum(), old_value - whole_delta))
            bar.setValue(target_value)
            if (
                whole_delta < 0
                and target_value == old_value
                and bar.maximum() - target_value < max(240, self.height())
            ):
                self.nearBottom.emit()
        event.accept()

    def _handle_scroll(self, value: int) -> None:
        bar = self.verticalScrollBar()
        if bar.maximum() - value < max(240, self.height()):
            self.nearBottom.emit()
        self.visibleRowsChanged.emit()


class TickCheckBox(QCheckBox):
    def paintEvent(self, event: Any) -> None:  # type: ignore[override]
        super().paintEvent(event)
        if not self.isChecked():
            return
        option = QStyleOptionButton()
        self.initStyleOption(option)
        indicator = self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, self)
        if indicator.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(
            QPen(
                QColor("#f4f7fc"),
                max(2, round(indicator.width() * 0.14)),
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        left = indicator.left()
        top = indicator.top()
        width = indicator.width()
        height = indicator.height()
        painter.drawLine(
            QPoint(left + round(width * 0.24), top + round(height * 0.54)),
            QPoint(left + round(width * 0.43), top + round(height * 0.72)),
        )
        painter.drawLine(
            QPoint(left + round(width * 0.43), top + round(height * 0.72)),
            QPoint(left + round(width * 0.76), top + round(height * 0.30)),
        )


class ThumbnailService(QObject):
    decodedReady = Signal(object, object)

    def __init__(
        self,
        owner: QWidget,
        cache_dir: Any,
        *,
        max_memory_bytes: int = 128 * 1024 * 1024,
        max_active_requests: int = THUMBNAIL_MAX_ACTIVE_REQUESTS,
        max_decoders: int = 2,
        max_pixmaps_per_frame: int = THUMBNAIL_MAX_PIXMAPS_PER_FRAME,
    ) -> None:
        super().__init__(owner)
        self.owner = owner
        self.max_memory_bytes = max_memory_bytes
        self.max_active_requests = max(1, int(max_active_requests))
        self.max_pixmaps_per_frame = max(1, int(max_pixmaps_per_frame))
        self._memory_bytes = 0
        self._cache: OrderedDict[tuple[str, int, int], QPixmap] = OrderedDict()
        self._inflight: dict[tuple[str, int, int], list[Callable[[QPixmap], None]]] = {}
        self._inflight_failures: dict[tuple[str, int, int], list[Callable[[], None]]] = {}
        self._pending: OrderedDict[tuple[str, int, int], list[Callable[[QPixmap], None]]] = OrderedDict()
        self._pending_failures: dict[tuple[str, int, int], list[Callable[[], None]]] = {}
        self._active_replies: dict[tuple[str, int, int], Any] = {}
        self._decoded_queue: OrderedDict[tuple[str, int, int], QImage] = OrderedDict()
        self._dropped_pending = 0
        self._decode_pool = ThreadPoolExecutor(max_workers=max(1, int(max_decoders)), thread_name_prefix="thumbnail-decode")
        self._closed = False
        self.manager = QNetworkAccessManager(owner)
        self.disk_cache = QNetworkDiskCache(owner)
        self.disk_cache.setCacheDirectory(str(cache_dir))
        self.disk_cache.setMaximumCacheSize(2 * 1024 * 1024 * 1024)
        self.manager.setCache(self.disk_cache)
        self._pixmap_timer = QTimer(self)
        self._pixmap_timer.setSingleShot(True)
        self._pixmap_timer.setInterval(0)
        self._pixmap_timer.timeout.connect(self._flush_decoded_queue)
        self.decodedReady.connect(self._handle_decoded)

    def request(
        self,
        url: str,
        target_size: QSize,
        callback: Callable[[QPixmap], None],
        error_callback: Callable[[], None] | None = None,
    ) -> None:
        if not url or self._closed:
            return
        key = (url, max(1, target_size.width()), max(1, target_size.height()))
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            QTimer.singleShot(0, lambda pixmap=cached: callback(pixmap))
            return
        if key in self._inflight:
            self._inflight[key].append(callback)
            if error_callback is not None:
                self._inflight_failures.setdefault(key, []).append(error_callback)
            return
        if key in self._pending:
            self._pending[key].append(callback)
            if error_callback is not None:
                self._pending_failures.setdefault(key, []).append(error_callback)
            return
        self._pending[key] = [callback]
        if error_callback is not None:
            self._pending_failures[key] = [error_callback]
        self._pump_requests()

    def request_with_fallbacks(
        self,
        urls: list[str],
        target_size: QSize,
        callback: Callable[[QPixmap], None],
    ) -> None:
        candidates: list[str] = []
        seen: set[str] = set()
        for url in urls:
            normalized = str(url or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            candidates.append(normalized)
        if not candidates or self._closed:
            return

        def request_at(index: int) -> None:
            if self._closed or index >= len(candidates):
                return
            self.request(
                candidates[index],
                target_size,
                callback,
                error_callback=lambda next_index=index + 1: request_at(next_index),
            )

        request_at(0)

    def active_request_count(self) -> int:
        return len(self._active_replies)

    def pending_request_count(self) -> int:
        return len(self._pending)

    def dropped_pending_count(self) -> int:
        return self._dropped_pending

    def prune_pending(self, allowed_keys: set[tuple[str, int, int]]) -> None:
        if not allowed_keys:
            dropped = len(self._pending)
            self._pending.clear()
            self._pending_failures.clear()
            self._dropped_pending += dropped
            return
        for key in list(self._pending.keys()):
            if key not in allowed_keys:
                self._pending.pop(key, None)
                self._pending_failures.pop(key, None)
                self._dropped_pending += 1

    def _pump_requests(self) -> None:
        if self._closed:
            return
        while len(self._active_replies) < self.max_active_requests and self._pending:
            key, callbacks = self._pending.popitem(last=False)
            failure_callbacks = self._pending_failures.pop(key, [])
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                for callback in callbacks:
                    QTimer.singleShot(0, lambda pixmap=cached, callback=callback: callback(pixmap))
                continue
            self._inflight[key] = callbacks
            self._inflight_failures[key] = failure_callbacks
            reply = self.manager.get(QNetworkRequest(QUrl(key[0])))
            self._active_replies[key] = reply
            reply.finished.connect(lambda reply=reply, key=key: self._finish(reply, key))

    def _finish(self, reply: QNetworkReply, key: tuple[str, int, int]) -> None:
        try:
            self._active_replies.pop(key, None)
            if self._closed:
                self._inflight.pop(key, None)
                self._inflight_failures.pop(key, None)
                return
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self._fail_request(key)
                return
            data = bytes(reply.readAll())
            try:
                self._decode_pool.submit(self._decode_and_emit, key, data)
            except RuntimeError:
                self._fail_request(key)
        finally:
            reply.deleteLater()
            self._pump_requests()

    def _decode_and_emit(self, key: tuple[str, int, int], data: bytes) -> None:
        if self._closed:
            return
        image = QImage()
        try:
            decoded = QImage()
            if decoded.loadFromData(data):
                image = decoded.scaled(
                    QSize(key[1], key[2]),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.FastTransformation,
                )
        except Exception:
            image = QImage()
        if not self._closed:
            self.decodedReady.emit(key, image)

    def _handle_decoded(self, key: tuple[str, int, int], image: QImage) -> None:
        if self._closed:
            self._inflight.pop(key, None)
            return
        self._decoded_queue[key] = image
        if not self._pixmap_timer.isActive():
            self._pixmap_timer.start()

    def _flush_decoded_queue(self) -> None:
        if self._closed:
            self._decoded_queue.clear()
            return
        processed = 0
        while self._decoded_queue and processed < self.max_pixmaps_per_frame:
            key, image = self._decoded_queue.popitem(last=False)
            callbacks = self._inflight.pop(key, [])
            processed += 1
            if image.isNull():
                self._fail_request(key)
                continue
            pixmap = QPixmap.fromImage(image)
            self._remember(key, pixmap)
            self._inflight_failures.pop(key, None)
            for callback in callbacks:
                callback(pixmap)
        if self._decoded_queue:
            self._pixmap_timer.start()

    def _fail_request(self, key: tuple[str, int, int]) -> None:
        self._inflight.pop(key, None)
        failure_callbacks = self._inflight_failures.pop(key, [])
        for callback in failure_callbacks:
            QTimer.singleShot(0, callback)

    def shutdown(self) -> None:
        self._closed = True
        self._pixmap_timer.stop()
        self._pending.clear()
        self._pending_failures.clear()
        self._inflight.clear()
        self._inflight_failures.clear()
        for reply in list(self._active_replies.values()):
            try:
                if hasattr(reply, "abort"):
                    reply.abort()
            except Exception:
                pass
            try:
                if hasattr(reply, "deleteLater"):
                    reply.deleteLater()
            except Exception:
                pass
        self._active_replies.clear()
        self._decoded_queue.clear()
        self._decode_pool.shutdown(wait=False, cancel_futures=True)

    def _remember(self, key: tuple[str, int, int], pixmap: QPixmap) -> None:
        if key in self._cache:
            old = self._cache.pop(key)
            self._memory_bytes -= self._pixmap_bytes(old)
        self._cache[key] = pixmap
        self._memory_bytes += self._pixmap_bytes(pixmap)
        while self._memory_bytes > self.max_memory_bytes and self._cache:
            _old_key, old_pixmap = self._cache.popitem(last=False)
            self._memory_bytes -= self._pixmap_bytes(old_pixmap)

    @staticmethod
    def _pixmap_bytes(pixmap: QPixmap) -> int:
        return max(0, pixmap.width()) * max(0, pixmap.height()) * 4


class UiJankProbe(QObject):
    def __init__(
        self,
        parent: QObject | None = None,
        *,
        interval_ms: int = 16,
        report_ms: int = 10_000,
        jsonl_path: Path | None = None,
        context_provider: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(parent)
        self._interval_ms = max(1, int(interval_ms))
        self._report_ms = max(1000, int(report_ms))
        self._jsonl_path = jsonl_path
        self._context_provider = context_provider
        self._samples: list[float] = []
        self._last = time.perf_counter()
        self._last_report = self._last
        self._timer = QTimer(self)
        self._timer.setInterval(self._interval_ms)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._last = time.perf_counter()
        self._last_report = self._last
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        now = time.perf_counter()
        gap_ms = max(0.0, (now - self._last) * 1000.0)
        self._last = now
        self._samples.append(gap_ms)
        if (now - self._last_report) * 1000.0 < self._report_ms:
            return
        self._last_report = now
        if not self._samples:
            return
        ordered = sorted(self._samples)
        p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
        p99 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.99))]
        max_gap = ordered[-1]
        over_100 = sum(1 for sample in ordered if sample > 100.0)
        payload = {
            "event": "ui_jank",
            "samples": len(ordered),
            "p95_ms": round(p95, 2),
            "p99_ms": round(p99, 2),
            "max_gap_ms": round(max_gap, 2),
            "over_100": over_100,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if self._context_provider is not None:
            try:
                payload.update(self._context_provider())
            except Exception:
                pass
        if self._jsonl_path is not None:
            try:
                self._jsonl_path.parent.mkdir(parents=True, exist_ok=True)
                with self._jsonl_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            except Exception:
                pass
        print(
            f"[ui-jank] samples={len(ordered)} p95={p95:.1f}ms p99={p99:.1f}ms "
            f"max={max_gap:.1f}ms over100={over_100}",
            flush=True,
        )
        self._samples.clear()


class MetricCard(QFrame):
    def __init__(self, title: str, accent: bool = False, icon_text: str | None = None, icon_bg: str | None = None) -> None:
        super().__init__()
        self.setObjectName("metricCard")
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedWidth(232)
        self.setFixedHeight(100)
        self.setStyleSheet(
            f"""
            QFrame#metricCard {{
                background: #0f151d;
                border: 1px solid {'#234b68' if accent else '#263442'};
                border-radius: 9px;
            }}
            """
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(16)

        if icon_text:
            icon = QLabel(icon_text)
            icon.setAlignment(Qt.AlignCenter)
            icon.setFixedSize(52, 52)
            icon.setStyleSheet(
                f"background: {icon_bg or '#14293e'}; border: 1px solid #26364a; border-radius: 9px; color: #25c8f5; font-size: 24px; font-weight: 800;"
            )
            layout.addWidget(icon, 0, Qt.AlignVCenter)

        copy = QVBoxLayout()
        copy.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #aab3c3; font-size: 15px; font-weight: 700;")
        self.value_label = QLabel("0")
        self.value_label.setStyleSheet(
            f"font-size: 26px; font-weight: 800; color: {'#f4f7fc' if accent else '#f4f7fc'};"
        )
        copy.addWidget(self.title_label)
        copy.addWidget(self.value_label)
        copy.setAlignment(Qt.AlignVCenter)
        layout.addLayout(copy, 1)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class SectionCard(QFrame):
    def __init__(self, title: str, subtitle: str | None = None, action_text: str | None = None) -> None:
        super().__init__()
        self.setObjectName("sectionCard")
        self.setStyleSheet(
            """
            QFrame#sectionCard {
                background: #111820;
                border: 1px solid #2a3542;
                border-radius: 10px;
            }
            """
        )
        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(38, 34, 38, 30)
        self.outer_layout.setSpacing(24)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-size: 28px; font-weight: 800; color: #f7f9fc;")
        title_box.addWidget(self.title_label)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setWordWrap(True)
            sub.setStyleSheet("color: #d7deea; font-size: 18px; line-height: 1.45;")
            title_box.addWidget(sub)
        header.addLayout(title_box)
        header.addStretch(1)

        self.action_label = None
        if action_text:
            self.action_label = QLabel(action_text)
            self.action_label.setStyleSheet("color: #a6afbf; font-size: 15px;")
            header.addWidget(self.action_label)

        self.outer_layout.addLayout(header)


class FlexibleStackedWidget(QStackedWidget):
    def minimumSizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(0, 0)


class SourceComboBox(QComboBox):
    def paintEvent(self, event: Any) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = painter.pen()
        pen.setColor(QColor("#e8f7ff"))
        pen.setWidth(3)
        painter.setPen(pen)
        center_x = self.width() - 28
        center_y = self.height() // 2 + 1
        painter.drawLine(center_x - 7, center_y - 4, center_x, center_y + 4)
        painter.drawLine(center_x + 7, center_y - 4, center_x, center_y + 4)


class SourceSpinBox(QSpinBox):
    def paintEvent(self, event: Any) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = painter.pen()
        pen.setColor(QColor("#e8f7ff"))
        pen.setWidth(3)
        painter.setPen(pen)
        center_x = self.width() - 28
        center_y = self.height() // 2
        painter.drawLine(center_x - 7, center_y - 8, center_x, center_y - 16)
        painter.drawLine(center_x + 7, center_y - 8, center_x, center_y - 16)
        painter.drawLine(center_x - 7, center_y + 8, center_x, center_y + 16)
        painter.drawLine(center_x + 7, center_y + 8, center_x, center_y + 16)


class MainWindow(QMainWindow):
    catalogCountReady = Signal(int, int)
    catalogFiltersReady = Signal(int, dict)
    catalogPageReady = Signal(int, dict, bool)
    activeRunSnapshotReady = Signal(int, dict)
    manualDiscoveryReady = Signal(dict)
    interestDiscoveryReady = Signal(dict)
    summaryRefreshReady = Signal(int, dict)
    metadataBackfillReady = Signal(dict)
    updateCheckReady = Signal(dict)
    updateApplyReady = Signal(dict)
    uiActionReady = Signal(int, object)

    def __init__(self, controller: AppController, services: DesktopServices) -> None:
        super().__init__()
        self.controller = controller
        self.services = services
        self._source_rows: list[dict[str, Any]] = []
        self._catalog_rows: list[dict[str, Any]] = []
        self._run_rows: list[dict[str, Any]] = []
        self._nav_buttons: dict[str, QPushButton] = {}
        self._editing_source_id: int | None = None
        self._catalog_card_widgets: list[CatalogCard] = []
        self._thumbnail_pixmaps: dict[str, QPixmap] = {}
        self._latest_stats: dict[str, Any] = {}
        self._last_active_run_id: int | None = None
        self._last_catalog_signature: tuple[Any, ...] = ()
        self._catalog_filter_state: dict[str, Any] = {}
        self._catalog_next_cursor: str | None = None
        self._catalog_total_count = 0
        self._catalog_count_pending = False
        self._catalog_count_exact = False
        self._catalog_loading_page = False
        self._catalog_loading_append = False
        self._catalog_refresh_deferred_after_append = False
        self._catalog_query_generation = 0
        self._current_page_key: str | None = None
        self._catalog_dirty = True
        self._catalog_filters_dirty = True
        self._catalog_filters_generation = 0
        self._catalog_filters_loading = False
        self._catalog_filter_threads: list[threading.Thread] = []
        self._catalog_page_threads: list[threading.Thread] = []
        self._summary_refresh_threads: list[threading.Thread] = []
        self._manual_discovery_threads: list[threading.Thread] = []
        self._interest_discovery_threads: list[threading.Thread] = []
        self._metadata_backfill_threads: list[threading.Thread] = []
        self._update_threads: list[threading.Thread] = []
        self._summary_refresh_generation = 0
        self._summary_refresh_loading = False
        self._summary_refresh_dirty = False
        self._manual_discovery_running = False
        self._interest_discovery_active = 0
        self._metadata_backfill_loading = False
        self._update_running = False
        self._pending_update_manifest: Any | None = None
        self._catalog_has_manual_interest = False
        self._catalog_render_token = 0
        self._catalog_row_stretch_index: int | None = None
        self._catalog_layout_signature: tuple[Any, ...] | None = None
        self._catalog_batch_state: tuple[int, int, int, int, str] | None = None
        self._thumbnail_scaled_pixmaps: dict[tuple[str, int, int], QPixmap] = {}
        self._catalog_count_threads: list[threading.Thread] = []
        self._active_run_snapshot_threads: list[threading.Thread] = []
        self._active_run_snapshot_loading = False
        self._active_run_progress: dict[str, Any] | None = None
        self._active_discovery_progress: dict[str, Any] | None = None
        self._ui_action_threads: list[threading.Thread] = []
        self._ui_action_handlers: dict[int, dict[str, Any]] = {}
        self._ui_action_generation = 0
        self._busy_buttons: set[QPushButton] = set()
        self._favorite_action_versions: dict[str, int] = {}
        self._catalog_visible_thumbnail_urls: set[str] = set()
        self._catalog_pending_thumbnail_pixmaps: dict[str, QPixmap] = {}
        self._ui_jank_probe: UiJankProbe | None = None
        self._last_worker_pause_sent = 0.0
        self._catalog_restore_scroll_generation: int | None = None
        self._catalog_restore_scroll_anchor: CatalogScrollAnchor | None = None
        self._catalog_append_scroll_anchor: CatalogScrollAnchor | None = None
        self._catalog_scroll_restore_token = 0
        self._catalog_scroll_range_restore_handler: Callable[[int, int], None] | None = None
        self._suppress_next_catalog_near_bottom = False
        self.topbar_quick_input: QLineEdit | None = None
        self._sources_layout_mode: str | None = None
        self._closing = False

        self.setWindowTitle(services.settings.app_title or " ")
        self.catalogCountReady.connect(self.handle_catalog_count_ready)
        self.catalogFiltersReady.connect(self.handle_catalog_filters_ready)
        self.catalogPageReady.connect(self.handle_catalog_page_ready)
        self.activeRunSnapshotReady.connect(self.handle_active_run_snapshot_ready)
        self.manualDiscoveryReady.connect(self.handle_manual_discovery_ready)
        self.interestDiscoveryReady.connect(self.handle_interest_discovery_ready)
        self.summaryRefreshReady.connect(self.handle_summary_refresh_ready)
        self.metadataBackfillReady.connect(self.handle_metadata_backfill_ready)
        self.updateCheckReady.connect(self.handle_update_check_ready)
        self.updateApplyReady.connect(self.handle_update_apply_ready)
        self.uiActionReady.connect(self._handle_ui_action_ready)
        self.resize(1680, 980)
        status_bar = QStatusBar()
        status_bar.setSizeGripEnabled(False)
        status_bar.hide()
        self.setStatusBar(status_bar)

        thumb_cache_dir = self.services.settings.data_dir / "thumb_cache_v1"
        thumb_cache_dir.mkdir(parents=True, exist_ok=True)
        self.thumbnail_service = ThumbnailService(self, thumb_cache_dir)

        root = QWidget()
        root.setObjectName("appRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        top_host = QWidget()
        top_host.setObjectName("topHost")
        top_host_layout = QHBoxLayout(top_host)
        top_host_layout.setContentsMargins(16, 8, 16, 0)
        top_host_layout.setSpacing(0)

        top_shell = card_frame("topShell")
        top_shell.setStyleSheet(
            """
            QFrame#topShell {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0d1319, stop:0.4 #0e1520, stop:1 #101822);
                border: 1px solid #1e2a38;
                border-bottom: 1px solid #25c8f5;
                border-radius: 10px;
            }
            """
        )
        top_shell.setFixedHeight(52)
        shell_layout = QHBoxLayout(top_shell)
        shell_layout.setContentsMargins(20, 0, 16, 0)
        shell_layout.setSpacing(6)

        brand_label = QLabel("\U0001F3AC")
        brand_label.setStyleSheet("font-size: 22px; padding-right: 2px;")
        shell_layout.addWidget(brand_label)

        nav_separator = QFrame()
        nav_separator.setFrameShape(QFrame.Shape.VLine)
        nav_separator.setFixedHeight(28)
        nav_separator.setStyleSheet("color: #283340; background: #283340; max-width: 1px;")
        shell_layout.addWidget(nav_separator)

        for key, label in [
            ("dashboard", "Inicio"),
            ("catalog", "Descubrir"),
        ]:
            button = QPushButton(label)
            button.setProperty("nav", "true")
            button.setMinimumHeight(48)
            button.clicked.connect(lambda _checked=False, nav_key=key: self.switch_page(nav_key))
            self._nav_buttons[key] = button
            shell_layout.addWidget(button)

        self.automatic_discovery_toggle = TickCheckBox("Búsqueda Automática")
        self.automatic_discovery_toggle.setProperty("topbarAutoSearch", "true")
        self.automatic_discovery_toggle.setToolTip("Activa o pausa la búsqueda automática en segundo plano")
        self.automatic_discovery_toggle.setChecked(self.controller.automatic_discovery_enabled())
        self.automatic_discovery_toggle.toggled.connect(self.handle_automatic_discovery_toggled)
        shell_layout.addWidget(self.automatic_discovery_toggle)

        shell_layout.addStretch(1)

        self.update_button = QPushButton("Actualizar")
        self.update_button.setProperty("compactCatalog", "true")
        self.update_button.setToolTip("Buscar una actualizacion de app y base de datos")
        self.update_button.clicked.connect(self.handle_update_button)
        shell_layout.addWidget(self.update_button)

        progress_box = QVBoxLayout()
        progress_box.setSpacing(3)
        progress_box.setContentsMargins(0, 0, 0, 0)
        self.topbar_status_label = QLabel("Aún no has buscado videos")
        self.topbar_status_label.setStyleSheet("font-size: 12px; color: #7e8a9c;")
        self.topbar_status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.topbar_status_label.setWordWrap(True)
        self.topbar_progress = QProgressBar()
        self.topbar_progress.setTextVisible(False)
        self.topbar_progress.setFixedWidth(260)
        self.topbar_progress.hide()
        progress_box.addWidget(self.topbar_status_label)
        progress_box.addWidget(self.topbar_progress, 0, Qt.AlignRight)
        shell_layout.addLayout(progress_box)

        top_host_layout.addWidget(top_shell)
        root_layout.addWidget(top_host)

        self.pages = FlexibleStackedWidget()
        root_layout.addWidget(self.pages, 1)

        self.dashboard_tab = self._build_dashboard_tab()
        self.sources_tab = self._build_sources_tab()
        self.runs_tab = self._build_runs_tab()
        self.catalog_tab = self._build_catalog_tab()

        self.pages.addWidget(self.dashboard_tab)
        self.pages.addWidget(self.sources_tab)
        self.pages.addWidget(self.runs_tab)
        self.pages.addWidget(self.catalog_tab)
        self.page_index = {
            "dashboard": 0,
            "sources": 1,
            "runs": 2,
            "catalog": 3,
        }
        self.switch_page("catalog")

        self.catalog_relayout_timer = QTimer(self)
        self.catalog_relayout_timer.setSingleShot(True)
        self.catalog_relayout_timer.setInterval(120)
        self.catalog_relayout_timer.timeout.connect(self.render_catalog_cards_if_visible)

        self.catalog_page_refresh_timer = QTimer(self)
        self.catalog_page_refresh_timer.setSingleShot(True)
        self.catalog_page_refresh_timer.setInterval(0)
        self.catalog_page_refresh_timer.timeout.connect(self.refresh_catalog)

        self.catalog_batch_timer = QTimer(self)
        self.catalog_batch_timer.setSingleShot(True)
        self.catalog_batch_timer.setInterval(8)
        self.catalog_batch_timer.timeout.connect(self._continue_catalog_card_batch)

        self.catalog_thumbnail_timer = QTimer(self)
        self.catalog_thumbnail_timer.setSingleShot(True)
        self.catalog_thumbnail_timer.setInterval(45)
        self.catalog_thumbnail_timer.timeout.connect(self.request_visible_catalog_thumbnails)

        self.catalog_thumbnail_apply_timer = QTimer(self)
        self.catalog_thumbnail_apply_timer.setSingleShot(True)
        self.catalog_thumbnail_apply_timer.setInterval(0)
        self.catalog_thumbnail_apply_timer.timeout.connect(self.flush_catalog_thumbnail_updates)

        self.timer = QTimer(self)
        self.timer.setInterval(1600)
        self.timer.timeout.connect(self._tick_refresh)
        self.timer.start()

        self.startup_backfill_timer = QTimer(self)
        self.startup_backfill_timer.setSingleShot(True)
        self.startup_backfill_timer.setInterval(STARTUP_BACKFILL_DELAY_MS)
        self.startup_backfill_timer.timeout.connect(self.start_metadata_backfill_if_needed)

        self.refresh_all()
        self.startup_backfill_timer.start()
        if os.environ.get("DUBINDEX_PERF_PROBE") == "1":
            raw_path = os.environ.get("DUBINDEX_PERF_PROBE_PATH", "").strip()
            jsonl_path = Path(raw_path) if raw_path else self.services.settings.data_dir / "ui_jank_probe.jsonl"
            self._ui_jank_probe = UiJankProbe(self, jsonl_path=jsonl_path, context_provider=self._ui_perf_context)
            self._ui_jank_probe.start()

    def _ui_perf_context(self) -> dict[str, Any]:
        thumbnail_service = getattr(self, "thumbnail_service", None)
        return {
            "active_run_id": self.controller.active_run_id(),
            "manual_discovery_running": self._manual_discovery_running,
            "interest_discovery_active": self._interest_discovery_active,
            "catalog_rows": len(self._catalog_rows),
            "catalog_loading_page": self._catalog_loading_page,
            "thumbnail_pending": len(getattr(thumbnail_service, "_pending", {}) or {}),
            "thumbnail_inflight": len(getattr(thumbnail_service, "_inflight", {}) or {}),
            "thumbnail_decode_queue": len(getattr(thumbnail_service, "_decoded_queue", {}) or {}),
        }

    def _configure_table(self, table: QTableWidget, stretch_column: int | None = None) -> None:
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(False)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setHighlightSections(False)
        table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        table.verticalHeader().setDefaultSectionSize(52)
        table.setFrameShape(QFrame.NoFrame)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        if stretch_column is not None:
            header.setSectionResizeMode(stretch_column, QHeaderView.Stretch)

    def _build_dashboard_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("pageRoot")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(34, 0, 34, 24)
        layout.setSpacing(0)
        layout.addStretch(1)

        content = QWidget()
        content.setMaximumWidth(1160)
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(28)

        # ── Hero: Quick-add CTA ──────────────────────────────
        hero = card_frame("dashHero")
        hero.setStyleSheet(
            """
            QFrame#dashHero {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0c1926, stop:0.5 #0e1d30, stop:1 #111f33);
                border: 1px solid #1a3050;
                border-radius: 14px;
            }
            """
        )
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(42, 38, 42, 34)
        hero_layout.setSpacing(16)
        hero_title = QLabel("Encuentra videos doblados en YouTube")
        hero_title.setStyleSheet(
            "font-size: 26px; font-weight: 800; color: #f7f9fc;"
        )
        hero_title.setWordWrap(True)
        hero_subtitle = QLabel(
            "Pega un canal o escribe lo que te interesa. La app revisará los videos y te dirá cuáles tienen doblaje."
        )
        hero_subtitle.setWordWrap(True)
        hero_subtitle.setStyleSheet("color: #c0cadb; font-size: 15px;")
        hero_layout.addWidget(hero_title)
        hero_layout.addWidget(hero_subtitle)

        hero_row = QHBoxLayout()
        hero_row.setSpacing(12)
        self.dashboard_quick_input = QLineEdit()
        self.dashboard_quick_input.setPlaceholderText("Canal de YouTube o término de búsqueda…")
        self.dashboard_quick_input.setMinimumHeight(48)
        self.dashboard_quick_input.setStyleSheet(
            """
            QLineEdit {
                background: #0f1c2e;
                border: 2px solid #2a4468;
                border-radius: 10px;
                padding: 10px 18px;
                color: #f4f7fc;
                font-size: 16px;
            }
            QLineEdit:focus {
                border: 2px solid #25c8f5;
                background: #111f33;
            }
            """
        )
        self.dashboard_quick_input.returnPressed.connect(self.handle_dashboard_quick_submit)
        hero_row.addWidget(self.dashboard_quick_input, 1)
        dashboard_quick_btn = QPushButton("▶  Buscar")
        dashboard_quick_btn.setProperty("role", "topPrimary")
        dashboard_quick_btn.setMinimumHeight(48)
        dashboard_quick_btn.setFixedWidth(160)
        dashboard_quick_btn.clicked.connect(self.handle_dashboard_quick_submit)
        hero_row.addWidget(dashboard_quick_btn)
        hero_layout.addLayout(hero_row)
        content_layout.addWidget(hero)

        # ── Metric cards row ─────────────────────────────────
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(16)
        self.metric_dubbed = MetricCard("Videos doblados", accent=True, icon_text="🎙", icon_bg="#0d2a3f")
        self.metric_sources = MetricCard("Búsquedas activas", icon_text="🔍", icon_bg="#14293e")
        self.metric_scanned = MetricCard("Videos revisados", icon_text="📊", icon_bg="#14293e")
        self.metric_last_run = MetricCard("Última actividad", icon_text="⏱", icon_bg="#14293e")
        for metric in (self.metric_dubbed, self.metric_sources, self.metric_scanned, self.metric_last_run):
            metrics_row.addWidget(metric)
        metrics_row.addStretch(1)
        content_layout.addLayout(metrics_row)

        # ── Compact tutorial ─────────────────────────────────
        guide_card = card_frame("guideCard")
        guide_card.setStyleSheet(
            """
            QFrame#guideCard {
                background: transparent;
                border: none;
            }
            """
        )
        guide_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        guide_layout = QVBoxLayout(guide_card)
        guide_layout.setContentsMargins(0, 0, 0, 0)
        guide_layout.setSpacing(14)
        guide_title = QLabel("Cómo funciona")
        guide_title.setStyleSheet("font-size: 18px; font-weight: 800; color: #a6afbf;")
        guide_layout.addWidget(guide_title)
        steps = QHBoxLayout()
        steps.setSpacing(18)
        for number, title, subtitle in [
            ("1", "Busca o pega un canal", "Queda guardado como interés permanente."),
            ("2", "Exploración automática", "El índice crece con relacionados y canales."),
            ("3", "Revisa resultados", "Descubrir muestra los videos con dub disponibles."),
        ]:
            step_card = card_frame(f"stepCard{number}")
            step_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            step_card.setFixedHeight(82)
            step_card.setStyleSheet(
                f"""
                QFrame#{step_card.objectName()} {{
                    background: #0c1218;
                    border: 1px solid #1e2c3c;
                    border-radius: 10px;
                }}
                """
            )
            step_layout = QHBoxLayout(step_card)
            step_layout.setContentsMargins(16, 10, 16, 10)
            step_layout.setSpacing(12)
            number_badge = QLabel(number)
            number_badge.setAlignment(Qt.AlignCenter)
            number_badge.setFixedSize(38, 38)
            number_badge.setStyleSheet(
                "background: #10253a; border: 1px solid #1b354f; border-radius: 19px; color: #25c8f5; font-size: 20px; font-weight: 800;"
            )
            step_layout.addWidget(number_badge, 0, Qt.AlignVCenter)
            copy_box = QVBoxLayout()
            copy_box.setSpacing(2)
            title_label = QLabel(title)
            title_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #e0e4ec;")
            hint_label = QLabel(subtitle)
            hint_label.setWordWrap(True)
            hint_label.setStyleSheet("color: #8a94a6; font-size: 13px;")
            copy_box.addWidget(title_label)
            copy_box.addWidget(hint_label)
            copy_box.setAlignment(Qt.AlignVCenter)
            step_layout.addLayout(copy_box, 1)
            steps.addWidget(step_card)
        guide_layout.addLayout(steps)
        content_layout.addWidget(guide_card)

        layout.addWidget(content, 0, Qt.AlignHCenter)
        layout.addStretch(2)

        self.dashboard_more_info = QWidget()
        self.dashboard_more_info.hide()
        self.dashboard_more_info_button = QPushButton("Mas info")
        self.dashboard_history_toggle = QPushButton("Mostrar ultimas revisiones")
        self.latest_runs_table = QTableWidget(0, 6)
        self.latest_runs_table.setHorizontalHeaderLabels(
            ["ID", "Que buscaste", "Estado", "Videos vistos", "Con doblaje", "Inicio"]
        )
        self._configure_table(self.latest_runs_table, stretch_column=1)
        self.latest_runs_table.hide()

        return tab

    def _build_sources_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("pageRoot")
        outer_layout = QVBoxLayout(tab)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.sources_scroll = QScrollArea()
        self.sources_scroll.setWidgetResizable(True)
        self.sources_scroll.setFrameShape(QFrame.NoFrame)
        self.sources_scroll.setMinimumSize(0, 0)
        self.sources_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sources_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sources_scroll.setStyleSheet("background: transparent; border: none;")
        outer_layout.addWidget(self.sources_scroll, 1)

        sources_page = QWidget()
        self.sources_page = sources_page
        sources_page.setObjectName("pageRoot")
        sources_page.setMinimumSize(0, 0)
        sources_page.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.sources_scroll.setWidget(sources_page)

        layout = QGridLayout(sources_page)
        self.sources_layout = layout
        layout.setContentsMargins(34, 26, 34, 24)
        layout.setHorizontalSpacing(20)
        layout.setVerticalSpacing(20)
        layout.setAlignment(Qt.AlignTop)

        form_card = SectionCard(
            "Nueva búsqueda",
            "Guarda un canal o una búsqueda para revisarla automáticamente.",
        )
        self.source_form_card = form_card
        form_card.setMinimumWidth(610)
        form_card.setMaximumWidth(610)
        form_card.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        form_card.outer_layout.setContentsMargins(38, 34, 38, 30)
        form_card.outer_layout.setSpacing(24)

        self.source_advanced_box = QWidget()
        advanced_layout = QVBoxLayout(self.source_advanced_box)
        self.source_advanced_layout = advanced_layout
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(22)

        self.source_type = SourceComboBox()
        self.source_type.addItem("Canal de YouTube", "channel")
        self.source_type.addItem("Búsqueda por palabras", "search")
        style_combo_popup(self.source_type)
        self.source_value = QLineEdit()
        self.source_value_label = QLabel("Canal")
        self.source_max_label = QLabel("Videos a revisar")
        self.source_max_candidates = SourceSpinBox()
        self.source_max_candidates.setRange(1, 10000)
        self.source_max_candidates.setValue(self.controller.get_last_max_candidates())
        self.source_enabled = QCheckBox("Activa")
        self.source_enabled.setChecked(True)
        self.source_type.currentIndexChanged.connect(self.update_source_value_copy)
        self.source_value.returnPressed.connect(self.save_source)
        self.source_type.setStyleSheet(SOURCE_COMBO_STYLE)
        self.source_value.setStyleSheet(SOURCE_TEXT_CONTROL_STYLE)
        self.source_max_candidates.setStyleSheet(SOURCE_SPIN_STYLE)

        for control in (self.source_type, self.source_value, self.source_max_candidates):
            control.setProperty("compactSource", "true")
            control.setMinimumHeight(58)
            control.setMaximumHeight(58)

        source_type_field, _source_type_label = form_field("Tipo", self.source_type)
        self.source_value_field, self.source_value_field_label = form_field("Canal", self.source_value)
        source_max_field, _source_max_label = form_field("Videos a revisar", self.source_max_candidates)
        fields_layout = QVBoxLayout()
        self.source_fields_layout = fields_layout
        fields_layout.setSpacing(24)
        fields_layout.addWidget(source_type_field)
        fields_layout.addWidget(self.source_value_field)
        fields_layout.addWidget(source_max_field)
        advanced_layout.addLayout(fields_layout)
        advanced_layout.addWidget(self.source_enabled, 0, Qt.AlignLeft)
        advanced_layout.addStretch(1)

        action_row = QHBoxLayout()
        self.source_save_button = QPushButton("Guardar búsqueda")
        self.source_save_button.setProperty("role", "primary")
        self.source_save_button.setProperty("sourcePrimary", "true")
        self.source_save_button.setStyleSheet(SOURCE_PRIMARY_BUTTON_STYLE)
        self.source_save_button.setMinimumHeight(60)
        self.source_save_button.setMinimumWidth(270)
        self.source_save_button.setMaximumWidth(270)
        self.source_save_button.clicked.connect(self.save_source)
        self.source_cancel_edit_button = QPushButton("Cancelar")
        self.source_cancel_edit_button.setProperty("sourceAction", "true")
        self.source_cancel_edit_button.setStyleSheet(SOURCE_SECONDARY_BUTTON_STYLE)
        self.source_cancel_edit_button.setMinimumHeight(60)
        self.source_cancel_edit_button.setFixedWidth(126)
        self.source_cancel_edit_button.clicked.connect(self.cancel_source_edit)
        self.source_cancel_edit_button.hide()
        action_row.addStretch(1)
        action_row.addWidget(self.source_cancel_edit_button)
        action_row.addWidget(self.source_save_button)
        advanced_layout.addLayout(action_row)
        form_card.outer_layout.addWidget(self.source_advanced_box)
        self.update_source_value_copy()

        right_host = QWidget()
        self.sources_right_host = right_host
        right_host.setMinimumWidth(0)
        right_host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_column = QVBoxLayout()
        right_host.setLayout(right_column)
        right_column.setContentsMargins(0, 0, 0, 0)
        right_column.setSpacing(18)

        table_card = SectionCard(
            "Canales y búsquedas guardadas",
            "Gestiona tus fuentes guardadas.",
        )
        table_card.title_label.setText("Canales y búsquedas guardadas")
        self.sources_table_card = table_card
        table_card.setMinimumWidth(0)
        table_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        table_card.outer_layout.setContentsMargins(44, 38, 44, 30)
        table_card.outer_layout.setSpacing(28)
        quick_actions = QHBoxLayout()
        quick_actions.setSpacing(10)
        quick_actions.setContentsMargins(0, 0, 0, 0)
        self.source_edit_button = QPushButton("Editar")
        self.source_edit_button.setProperty("sourceAction", "true")
        self.source_edit_button.setStyleSheet(SOURCE_SECONDARY_BUTTON_STYLE)
        self.source_edit_button.setMinimumHeight(44)
        self.source_edit_button.setFixedWidth(132)
        self.source_edit_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.source_edit_button.clicked.connect(self.edit_selected_source)
        self.source_toggle_button = QPushButton("Reactivar")
        self.source_toggle_button.setProperty("sourceAction", "true")
        self.source_toggle_button.setStyleSheet(SOURCE_SECONDARY_BUTTON_STYLE)
        self.source_toggle_button.setMinimumHeight(44)
        self.source_toggle_button.setFixedWidth(132)
        self.source_toggle_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.source_toggle_button.setToolTip("Pausar o reactivar la búsqueda seleccionada")
        self.source_toggle_button.clicked.connect(self.toggle_selected_source)
        self.source_delete_button = QPushButton("Borrar")
        self.source_delete_button.setProperty("sourceAction", "true")
        self.source_delete_button.setStyleSheet(SOURCE_SECONDARY_BUTTON_STYLE)
        self.source_delete_button.setMinimumHeight(44)
        self.source_delete_button.setFixedWidth(132)
        self.source_delete_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.source_delete_button.clicked.connect(self.delete_selected_sources)
        self.source_increase_limit_button = QPushButton("Aumentar Límite")
        self.source_increase_limit_button.setProperty("sourcePrimary", "true")
        self.source_increase_limit_button.setStyleSheet(SOURCE_PRIMARY_BUTTON_STYLE)
        self.source_increase_limit_button.setMinimumHeight(44)
        self.source_increase_limit_button.setFixedWidth(160)
        self.source_increase_limit_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.source_increase_limit_button.setToolTip("Sube en 500 el límite de todas las fuentes llenas")
        self.source_increase_limit_button.clicked.connect(self.increase_full_source_limits)
        self.source_increase_limit_button.hide()
        quick_actions.addWidget(self.source_edit_button)
        quick_actions.addWidget(self.source_toggle_button)
        quick_actions.addWidget(self.source_delete_button)
        quick_actions.addStretch(1)
        quick_actions.addWidget(self.source_increase_limit_button)
        table_card.outer_layout.addLayout(quick_actions)
        table_shell = card_frame("sourcesTableShell")
        table_shell.setMinimumWidth(0)
        table_shell.setStyleSheet(
            """
            QFrame#sourcesTableShell {
                background: #111820;
                border: 1px solid #2a3542;
                border-radius: 8px;
            }
            """
        )
        table_shell_layout = QVBoxLayout(table_shell)
        table_shell_layout.setContentsMargins(0, 0, 0, 0)
        self.sources_table = QTableWidget(0, 5)
        self.sources_table.setMinimumWidth(0)
        self.sources_table.setHorizontalHeaderLabels(
            ["Nombre", "Tipo", "Canal o búsqueda", "Estado", "Límite"]
        )
        self._configure_table(self.sources_table, stretch_column=2)
        sources_header = self.sources_table.horizontalHeader()
        sources_header.setMinimumSectionSize(48)
        for section in range(5):
            sources_header.setSectionResizeMode(section, QHeaderView.Stretch)
        self.sources_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.sources_table.itemSelectionChanged.connect(self.update_source_actions)
        self.sources_table.setMinimumHeight(430)
        self.sources_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        table_shell_layout.addWidget(self.sources_table)
        table_card.outer_layout.addWidget(table_shell, 1)
        right_column.addWidget(table_card, 1)

        self.sources_recent_runs_table = QTableWidget(0, 5)
        self.sources_recent_runs_table.setHorizontalHeaderLabels(
            ["Qué buscaste", "Estado", "Revisados", "Con doblaje", "Inicio"]
        )
        self._configure_table(self.sources_recent_runs_table, stretch_column=0)
        self.sources_recent_runs_table.hide()

        self.sources_history_toggle = QPushButton("Ver historial completo")
        self.sources_history_toggle.setProperty("role", "ghost")
        self.sources_history_toggle.clicked.connect(self.toggle_history_details)
        self.sources_history_toggle.hide()

        self.sources_full_history_table = QTableWidget(0, 7)
        self.sources_full_history_table.setHorizontalHeaderLabels(
            ["Qué buscaste", "Estado", "Videos vistos", "Videos revisados", "Con doblaje", "Inicio", "Problema"]
        )
        self._configure_table(self.sources_full_history_table, stretch_column=6)
        self.sources_full_history_table.hide()

        self._update_sources_layout(force=True)
        return tab

    def _build_runs_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("pageRoot")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(34, 24, 34, 24)
        layout.setSpacing(18)

        runs_card = SectionCard("Historial", "Aquí ves cada búsqueda que lanzó la app y qué encontró.")
        top_row = QHBoxLayout()
        refresh_button = QPushButton("Actualizar")
        refresh_button.setProperty("role", "ghost")
        refresh_button.clicked.connect(self.refresh_runs)
        top_row.addStretch(1)
        top_row.addWidget(refresh_button)
        runs_card.outer_layout.addLayout(top_row)

        self.runs_table = QTableWidget(0, 8)
        self.runs_table.setHorizontalHeaderLabels(
            ["ID", "Qué buscaste", "Estado", "Videos vistos", "Videos revisados", "Con doblaje", "Inicio", "Problema"]
        )
        self._configure_table(self.runs_table, stretch_column=7)
        runs_card.outer_layout.addWidget(self.runs_table)
        layout.addWidget(runs_card)
        return tab

    def _build_catalog_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("pageRoot")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 0)
        layout.setSpacing(8)

        # ── Catalog header ───────────────────────────────────
        intro = QWidget()
        intro_layout = QHBoxLayout(intro)
        intro_layout.setContentsMargins(0, 2, 0, 0)
        intro_layout.setSpacing(12)
        intro_title = QLabel("Descubrir")
        self.catalog_intro_title = intro_title
        intro_title.setStyleSheet("font-size: 24px; font-weight: 800; color: #f7f9fc;")
        self.catalog_intro_hint = QLabel()
        self.catalog_intro_hint.setStyleSheet("font-size: 14px; color: #a6afbf;")
        self.catalog_intro_hint.hide()
        intro_layout.addWidget(intro_title)
        intro_layout.addStretch(1)
        self.catalog_results_count = QLabel("0 encontrados")
        self.catalog_results_count.setStyleSheet(
            "color: #25c8f5; font-size: 13px; font-weight: 800; "
            "background: #0b2a33; border: 1px solid #164a58; border-radius: 7px; padding: 6px 16px;"
        )
        intro_layout.addWidget(self.catalog_results_count)
        layout.addWidget(intro)

        # ── Filter combos ───────────────────────────────────
        self.catalog_query = QLineEdit()
        self.catalog_query.setProperty("compactCatalog", "true")
        self.catalog_query.setPlaceholderText("Buscar por título o canal")
        self.catalog_query.setMinimumWidth(240)
        self.catalog_query.setMinimumHeight(36)
        self.catalog_query.setMaximumHeight(36)
        self.catalog_query.returnPressed.connect(self.refresh_catalog)

        self.catalog_lang = CatalogFilterComboBox("Idioma")
        self.catalog_lang.setProperty("compactCatalog", "true")
        self.catalog_lang.addItem("Todos los idiomas", "")
        self.catalog_lang.addItem("Español", SPANISH_LANGUAGE_FILTER)
        self.catalog_lang.setCurrentIndex(1)
        self.catalog_lang.setMinimumWidth(200)
        self.catalog_lang.setMinimumHeight(36)
        self.catalog_lang.setMaximumHeight(36)

        self.catalog_channel = CatalogFilterComboBox()
        self.catalog_channel.addItem("Todos los canales", "")
        self.catalog_channel.setMinimumWidth(220)

        self.catalog_source = CatalogFilterComboBox()
        self.catalog_source.addItem("Todos los intereses", None)
        self.catalog_source.setMinimumWidth(220)

        self.catalog_visibility = CatalogFilterComboBox()
        self.catalog_visibility.addItem("Solo doblados", True)
        self.catalog_visibility.addItem("Todos los videos revisados", False)
        self.catalog_visibility.setMinimumWidth(220)

        self.catalog_dub_kind = CatalogFilterComboBox()
        self.catalog_dub_kind.addItem("Todos los dubs", "")
        self.catalog_dub_kind.addItem("Doblaje automático", "automatic")
        self.catalog_dub_kind.addItem("Doblaje manual", "manual")
        self.catalog_dub_kind.setMinimumWidth(220)

        self.catalog_sort = CatalogFilterComboBox("Ordenar por")
        self.catalog_sort.setProperty("compactCatalog", "true")
        self.catalog_sort.addItem("Más recientes", "recent")
        self.catalog_sort.addItem("Más antiguos", "oldest")
        self.catalog_sort.addItem("Más vistos", "views")
        self.catalog_sort.addItem("Random", "random")
        self.catalog_sort.setMinimumWidth(270)
        self.catalog_sort.setMinimumHeight(36)
        self.catalog_sort.setMaximumHeight(36)

        self.catalog_year = make_year_combo("Cualquier año")
        self.catalog_year.setMinimumWidth(180)

        self.catalog_after_year = make_year_combo("Sin fecha mínima")
        self.catalog_after_year.setMinimumWidth(180)

        self.catalog_before_year = make_year_combo("Sin fecha máxima")
        self.catalog_before_year.setMinimumWidth(180)

        self.catalog_max_duration = make_max_duration_combo()
        self.catalog_max_duration.setMinimumWidth(190)

        self.catalog_favorites_only = QCheckBox("Mostrar solo favoritos")
        self.catalog_favorites_only.setProperty("catalogFavoriteFilter", "true")

        # Display prefs — hardcoded to sensible defaults, hidden
        self.catalog_columns = QComboBox()
        self.catalog_columns.addItem("5 por fila", 5)
        self.catalog_columns.hide()
        self.catalog_card_size = QComboBox()
        self.catalog_card_size.addItem("Medio", 300)
        self.catalog_card_size.hide()

        for combo in (
            self.catalog_lang,
            self.catalog_source,
            self.catalog_channel,
            self.catalog_visibility,
            self.catalog_dub_kind,
            self.catalog_sort,
            self.catalog_year,
            self.catalog_after_year,
            self.catalog_before_year,
            self.catalog_max_duration,
        ):
            style_combo_popup(combo)
        for combo in (self.catalog_year, self.catalog_after_year, self.catalog_before_year):
            combo.setMaxVisibleItems(14)

        # ── Single-row controls bar ─────────────────────────
        self.catalog_controls_shell = card_frame("catalogControlsShell")
        self.catalog_controls_shell.setMaximumHeight(48)
        self.catalog_controls_shell.setStyleSheet(
            """
            QFrame#catalogControlsShell {
                background: #111820;
                border: 1px solid #202a35;
                border-radius: 10px;
            }
            """
        )
        controls_layout = QHBoxLayout(self.catalog_controls_shell)
        controls_layout.setContentsMargins(12, 5, 12, 5)
        controls_layout.setSpacing(10)
        controls_layout.addWidget(self.catalog_query, 3)
        controls_layout.addWidget(self.catalog_lang, 1)
        controls_layout.addWidget(self.catalog_sort)
        self.catalog_manual_discovery_button = QPushButton(f"Explorar {MANUAL_DISCOVERY_CANDIDATE_LIMIT}")
        self.catalog_manual_discovery_button.setProperty("role", "ghost")
        self.catalog_manual_discovery_button.setProperty("compactCatalog", "true")
        self.catalog_manual_discovery_button.setMinimumHeight(36)
        self.catalog_manual_discovery_button.setMaximumHeight(36)
        self.catalog_manual_discovery_button.clicked.connect(self.handle_manual_feed_expansion)
        controls_layout.addWidget(self.catalog_manual_discovery_button)
        self.catalog_filters_toggle = QPushButton("Mas filtros")
        self.catalog_filters_toggle.setProperty("role", "ghost")
        self.catalog_filters_toggle.setProperty("compactCatalog", "true")
        self.catalog_filters_toggle.setMinimumHeight(36)
        self.catalog_filters_toggle.setMaximumHeight(36)
        self.catalog_filters_toggle.clicked.connect(self.toggle_catalog_filters)
        controls_layout.addWidget(self.catalog_filters_toggle)
        self.catalog_clear_filters_button = QPushButton("Limpiar filtros")
        self.catalog_clear_filters_button.setProperty("role", "ghost")
        self.catalog_clear_filters_button.setProperty("compactCatalog", "true")
        self.catalog_clear_filters_button.setMinimumHeight(36)
        self.catalog_clear_filters_button.setMaximumHeight(36)
        self.catalog_clear_filters_button.clicked.connect(self.clear_catalog_filters)
        layout.addWidget(self.catalog_controls_shell)

        self.catalog_filters_panel = card_frame("catalogFiltersPanel")
        self.catalog_filters_panel.setStyleSheet(
            """
            QFrame#catalogFiltersPanel {
                background: #111820;
                border: 1px solid #202a35;
                border-radius: 10px;
            }
            """
        )
        filters_layout = QGridLayout(self.catalog_filters_panel)
        filters_layout.setContentsMargins(18, 16, 18, 16)
        filters_layout.setHorizontalSpacing(14)
        filters_layout.setVerticalSpacing(12)
        filters_layout.addWidget(inline_field("Canal", self.catalog_channel), 0, 0, 1, 2)
        filters_layout.addWidget(inline_field("Mostrar", self.catalog_visibility), 0, 2)
        filters_layout.addWidget(inline_field("Año de subida", self.catalog_year), 0, 3)
        filters_layout.addWidget(inline_field("Subidos desde", self.catalog_after_year), 1, 0)
        filters_layout.addWidget(inline_field("Subidos hasta", self.catalog_before_year), 1, 1)
        filters_layout.addWidget(inline_field("Tipo de dub", self.catalog_dub_kind), 1, 2)
        filters_layout.addWidget(inline_field("Duración máxima", self.catalog_max_duration), 1, 3)
        filters_layout.addWidget(self.catalog_favorites_only, 2, 2, alignment=Qt.AlignBottom)
        filters_layout.addWidget(self.catalog_clear_filters_button, 2, 3, alignment=Qt.AlignBottom)
        self.catalog_filters_panel.hide()
        layout.addWidget(self.catalog_filters_panel)

        self.catalog_empty_stack = QStackedWidget()
        self.catalog_empty_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        empty_page = QWidget()
        empty_layout = QVBoxLayout(empty_page)
        empty_layout.setContentsMargins(0, 32, 0, 32)
        empty_layout.addStretch(1)
        empty_card = SectionCard(
            "Pega un canal o escribe lo que te interesa",
            "La app buscará videos con doblaje y te los dejará aquí listos para abrir.",
        )
        self.catalog_empty_input = QLineEdit()
        self.catalog_empty_input.setPlaceholderText("Canal de YouTube o búsqueda")
        self.catalog_empty_input.returnPressed.connect(self.handle_catalog_quick_submit)
        self.catalog_empty_button = QPushButton("Buscar videos doblados")
        self.catalog_empty_button.setProperty("role", "primary")
        self.catalog_empty_button.clicked.connect(self.handle_catalog_quick_submit)
        empty_row = QHBoxLayout()
        empty_row.setSpacing(10)
        empty_row.addWidget(self.catalog_empty_input, 1)
        empty_row.addWidget(self.catalog_empty_button)
        empty_card.outer_layout.addLayout(empty_row)
        self.catalog_empty_advanced = QPushButton("Opciones avanzadas")
        self.catalog_empty_advanced.setProperty("role", "ghost")
        self.catalog_empty_advanced.clicked.connect(self.open_sources_advanced)
        empty_card.outer_layout.addWidget(self.catalog_empty_advanced, 0, Qt.AlignLeft)
        empty_layout.addWidget(empty_card, 0, Qt.AlignHCenter)
        empty_layout.addStretch(1)
        self.catalog_empty_stack.addWidget(empty_page)

        loading_page = QWidget()
        loading_layout = QVBoxLayout(loading_page)
        loading_layout.setContentsMargins(0, 32, 0, 32)
        loading_layout.addStretch(1)
        loading_card = SectionCard(
            "Estamos buscando tus primeros videos doblados",
            "Puedes dejar la app abierta. El progreso aparece arriba mientras revisamos nuevos videos.",
        )
        self.catalog_loading_hint = QLabel("Cuando aparezcan resultados, se mostrarán aquí automáticamente.")
        self.catalog_loading_hint.setWordWrap(True)
        self.catalog_loading_hint.setStyleSheet("color: #c8d0de; font-size: 15px;")
        loading_card.outer_layout.addWidget(self.catalog_loading_hint)
        loading_layout.addWidget(loading_card, 0, Qt.AlignHCenter)
        loading_layout.addStretch(1)
        self.catalog_empty_stack.addWidget(loading_page)
        layout.addWidget(self.catalog_empty_stack, 1)

        self.catalog_grid_host = QWidget()
        self.catalog_grid_host.setObjectName("catalogGridHost")
        self.catalog_grid_host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.catalog_grid_host.setStyleSheet(
            """
            QWidget#catalogGridHost {
                background: transparent;
                border: none;
            }
            """
        )
        catalog_grid_layout = QVBoxLayout(self.catalog_grid_host)
        catalog_grid_layout.setContentsMargins(0, 0, 0, 0)
        catalog_grid_layout.setSpacing(0)
        self.catalog_model = CatalogListModel(self)
        self.catalog_delegate = CatalogCardDelegate(self)
        self.catalog_view = CatalogListView(self.catalog_delegate, self.catalog_grid_host)
        self.catalog_view.setModel(self.catalog_model)
        self.catalog_view.setItemDelegate(self.catalog_delegate)
        self.catalog_view.openRequested.connect(self.open_catalog_video)
        self.catalog_view.favoriteToggled.connect(self.toggle_catalog_favorite)
        self.catalog_view.nearBottom.connect(self.load_next_catalog_page)
        self.catalog_view.visibleRowsChanged.connect(self.handle_catalog_visible_rows_changed)
        catalog_grid_layout.addWidget(self.catalog_view)
        layout.addWidget(self.catalog_grid_host, 1)

        for combo in (
            self.catalog_lang,
            self.catalog_source,
            self.catalog_channel,
            self.catalog_visibility,
            self.catalog_dub_kind,
            self.catalog_sort,
            self.catalog_max_duration,
        ):
            combo.currentIndexChanged.connect(self.refresh_catalog)
        self.catalog_year.currentIndexChanged.connect(self.handle_exact_year_filter_changed)
        self.catalog_after_year.currentIndexChanged.connect(self.handle_year_range_filter_changed)
        self.catalog_before_year.currentIndexChanged.connect(self.handle_year_range_filter_changed)
        self.catalog_favorites_only.stateChanged.connect(self.refresh_catalog)

        return tab

    def _update_sources_layout(self, force: bool = False) -> None:
        if not hasattr(self, "sources_layout"):
            return

        mode = "wide"
        if force or self._sources_layout_mode != mode:
            self.sources_layout.removeWidget(self.source_form_card)
            self.sources_layout.removeWidget(self.sources_right_host)
            for index in range(2):
                self.sources_layout.setColumnStretch(index, 0)
                self.sources_layout.setRowStretch(index, 0)

            self.source_form_card.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            self.sources_layout.addWidget(self.source_form_card, 0, 0)
            self.sources_layout.addWidget(self.sources_right_host, 0, 1)
            self.sources_layout.setColumnStretch(1, 1)
            self.sources_layout.setRowStretch(0, 1)
            self._sources_layout_mode = mode

        self._sync_sources_dimensions()

    def _sync_sources_dimensions(self) -> None:
        if not hasattr(self, "sources_scroll"):
            return

        viewport = self.sources_scroll.viewport().rect()
        viewport_width = max(1, viewport.width())
        viewport_height = max(1, viewport.height())
        margins = self.sources_layout.contentsMargins()
        spacing = self.sources_layout.horizontalSpacing() or 20
        available_width = max(620, viewport_width - margins.left() - margins.right() - spacing)
        compact = viewport_width < 1380 or viewport_height < 720
        very_compact = viewport_height < 620

        left_width = int(available_width * 0.38)
        left_width = max(360, min(610, left_width))
        if available_width - left_width < 520:
            left_width = max(330, available_width - 520)
        self.source_form_card.setFixedWidth(left_width)

        if very_compact:
            form_margins = (24, 16, 24, 14)
            table_margins = (24, 16, 24, 14)
            form_spacing = 8
            advanced_spacing = 8
            fields_spacing = 8
            control_height = 38
            action_height = 40
            save_width = max(190, min(230, int(left_width * 0.44)))
            table_min_height = 170
        elif compact:
            form_margins = (30, 22, 30, 20)
            table_margins = (32, 24, 32, 22)
            form_spacing = 14
            advanced_spacing = 12
            fields_spacing = 12
            control_height = 44
            action_height = 46
            save_width = max(210, min(250, int(left_width * 0.46)))
            table_min_height = 230
        else:
            form_margins = (38, 34, 38, 30)
            table_margins = (44, 38, 44, 30)
            form_spacing = 24
            advanced_spacing = 22
            fields_spacing = 24
            control_height = 58
            action_height = 60
            save_width = max(240, min(270, int(left_width * 0.45)))
            table_min_height = 360

        self.source_form_card.outer_layout.setContentsMargins(*form_margins)
        self.source_form_card.outer_layout.setSpacing(form_spacing)
        self.source_advanced_layout.setSpacing(advanced_spacing)
        self.source_fields_layout.setSpacing(fields_spacing)
        for control in (self.source_type, self.source_value, self.source_max_candidates):
            control.setMinimumHeight(control_height)
            control.setMaximumHeight(control_height)
        self.source_save_button.setMinimumHeight(action_height)
        self.source_save_button.setMaximumHeight(action_height)
        self.source_save_button.setFixedWidth(save_width)
        self.source_cancel_edit_button.setMinimumHeight(action_height)
        self.source_cancel_edit_button.setMaximumHeight(action_height)
        self.source_cancel_edit_button.setFixedWidth(max(108, min(126, int(save_width * 0.55))))

        self.sources_table_card.outer_layout.setContentsMargins(*table_margins)
        self.sources_table_card.outer_layout.setSpacing(16 if compact else 28)
        self.sources_table.setMinimumHeight(table_min_height)

        right_width = max(420, available_width - left_width - spacing)
        action_width = max(320, right_width - table_margins[0] - table_margins[2])
        gap_total = 30
        increase_width = max(142, min(180, int(action_width * 0.30)))
        secondary_width = max(82, min(154, int((action_width - increase_width - gap_total) / 3)))
        total_width = secondary_width * 3 + increase_width + gap_total
        if total_width > action_width:
            overflow = total_width - action_width
            increase_width = max(118, increase_width - overflow)
        for button in (self.source_edit_button, self.source_toggle_button, self.source_delete_button):
            button.setMinimumHeight(action_height)
            button.setMaximumHeight(action_height)
            button.setFixedWidth(secondary_width)
        self.source_increase_limit_button.setMinimumHeight(action_height)
        self.source_increase_limit_button.setMaximumHeight(action_height)
        self.source_increase_limit_button.setFixedWidth(increase_width)

    def switch_page(self, key: str) -> None:
        previous_page = self._current_page_key
        self._current_page_key = key
        self.pages.setCurrentIndex(self.page_index[key])
        for name, button in self._nav_buttons.items():
            button.setProperty("active", "true" if name == key else "false")
            button.style().unpolish(button)
            button.style().polish(button)
        if key == "sources":
            QTimer.singleShot(0, self._update_sources_layout)
        if key == "catalog" and previous_page != "catalog":
            if self._catalog_filters_dirty:
                QTimer.singleShot(80, self.request_catalog_filters_refresh)
            if hasattr(self, "catalog_page_refresh_timer"):
                self.catalog_page_refresh_timer.start()

    def handle_automatic_discovery_toggled(self, enabled: bool) -> None:
        desired = bool(enabled)

        def action() -> bool:
            self.controller.set_automatic_discovery_enabled(desired)
            return desired

        def rollback(error: Exception) -> None:
            self.automatic_discovery_toggle.blockSignals(True)
            self.automatic_discovery_toggle.setChecked(not desired)
            self.automatic_discovery_toggle.blockSignals(False)
            self.show_error("No se pudo cambiar la busqueda automatica", error)

        self._run_ui_action_async(
            "automatic-discovery",
            action,
            on_error=rollback,
            busy_widgets=[self.automatic_discovery_toggle],
        )

    def selected_source(self) -> dict[str, Any] | None:
        selected = self.selected_sources()
        if not selected:
            return None
        return selected[0]

    def selected_sources(self) -> list[dict[str, Any]]:
        selection_model = self.sources_table.selectionModel()
        if selection_model is None:
            return []
        selected_rows = selection_model.selectedRows()
        rows: list[dict[str, Any]] = []
        for selected_row in selected_rows:
            row = selected_row.row()
            if row < 0 or row >= len(self._source_rows):
                continue
            rows.append(self._source_rows[row])
        return rows

    def editing_source(self) -> dict[str, Any] | None:
        if self._editing_source_id is None:
            return None
        self.catalog_source.setItemText(0, "Todos los intereses")
        for source in self._source_rows:
            if int(source["id"]) == int(self._editing_source_id):
                return source
        self._editing_source_id = None
        return None

    def current_catalog_columns(self) -> int:
        preferred = int(self.catalog_columns.currentData() or 5)
        if not hasattr(self, "catalog_view"):
            return preferred
        viewport_width = max(1, self.catalog_view.viewport().width())
        minimum_card_width = 200
        spacing = 16
        possible = max(1, viewport_width // (minimum_card_width + spacing))
        return max(1, min(preferred, possible))

    def current_catalog_card_width(self) -> int:
        columns = max(1, self.current_catalog_columns())
        spacing = 16
        viewport_width = self.catalog_view.viewport().width() if hasattr(self, "catalog_view") else 0
        if viewport_width <= 0:
            return int(self.catalog_card_size.currentData() or 300)
        available_width = max(200, viewport_width - spacing * columns - 28)
        return min(320, max(200, available_width // columns))

    def configure_catalog_view(self) -> None:
        if not hasattr(self, "catalog_view"):
            return
        card_width = self.current_catalog_card_width()
        size_mode = self.catalog_card_size.currentText()
        self.catalog_delegate.configure(card_width, size_mode)
        self.catalog_view.set_card_geometry(card_width, self.catalog_delegate.card_height)

    def toggle_catalog_filters(self, *_args: object) -> None:
        visible = not self.catalog_filters_panel.isVisible()
        self.catalog_filters_panel.setVisible(visible)
        self.catalog_filters_toggle.setText("Ocultar filtros" if visible else "Mas filtros")

    def handle_exact_year_filter_changed(self, *_args: object) -> None:
        if combo_year_value(self.catalog_year) is not None:
            self.catalog_after_year.blockSignals(True)
            self.catalog_before_year.blockSignals(True)
            self.set_combo_by_data(self.catalog_after_year, None)
            self.set_combo_by_data(self.catalog_before_year, None)
            self.catalog_after_year.blockSignals(False)
            self.catalog_before_year.blockSignals(False)
        self.refresh_catalog()

    def handle_year_range_filter_changed(self, *_args: object) -> None:
        if combo_year_value(self.catalog_after_year) is not None or combo_year_value(self.catalog_before_year) is not None:
            self.catalog_year.blockSignals(True)
            self.set_combo_by_data(self.catalog_year, None)
            self.catalog_year.blockSignals(False)
        self.refresh_catalog()

    def set_combo_by_data(self, combo: QComboBox, value: Any) -> None:
        combo.setCurrentIndex(max(0, combo.findData(value)))

    def clear_catalog_filters(self, *_args: object) -> None:
        widgets = [
            self.catalog_lang,
            self.catalog_source,
            self.catalog_channel,
            self.catalog_visibility,
            self.catalog_dub_kind,
            self.catalog_sort,
            self.catalog_year,
            self.catalog_after_year,
            self.catalog_before_year,
            self.catalog_max_duration,
            self.catalog_favorites_only,
        ]
        for widget in widgets:
            widget.blockSignals(True)

        self.catalog_query.blockSignals(True)
        self.catalog_query.clear()
        self.catalog_query.blockSignals(False)
        self.set_combo_by_data(self.catalog_lang, "")
        self.set_combo_by_data(self.catalog_source, None)
        self.set_combo_by_data(self.catalog_channel, "")
        self.set_combo_by_data(self.catalog_visibility, True)
        self.set_combo_by_data(self.catalog_dub_kind, "")
        self.set_combo_by_data(self.catalog_sort, "recent")
        self.set_combo_by_data(self.catalog_year, None)
        self.set_combo_by_data(self.catalog_after_year, None)
        self.set_combo_by_data(self.catalog_before_year, None)
        self.set_combo_by_data(self.catalog_max_duration, None)
        self.catalog_favorites_only.setChecked(False)

        for widget in widgets:
            widget.blockSignals(False)

        self.refresh_catalog()

    def handle_manual_feed_expansion(self, *_args: object) -> None:
        if self._manual_discovery_running:
            return
        self._manual_discovery_running = True
        self.catalog_manual_discovery_button.setEnabled(False)
        self.catalog_manual_discovery_button.setText("Explorando...")
        self.statusBar().showMessage(
            f"Explorando {MANUAL_DISCOVERY_CANDIDATE_LIMIT} videos recomendados",
            4000,
        )

        def worker() -> None:
            payload: dict[str, Any]
            try:
                payload = {
                    "summary": self.controller.run_manual_feed_expansion(
                        candidate_limit=MANUAL_DISCOVERY_CANDIDATE_LIMIT,
                    )
                }
            except Exception as exc:
                payload = {"error": humanize_exception(exc)}
            self.manualDiscoveryReady.emit(payload)

        self._manual_discovery_threads = [
            thread for thread in self._manual_discovery_threads if thread.is_alive()
        ]
        thread = threading.Thread(target=worker, daemon=True, name="manual-feed-expansion")
        self._manual_discovery_threads.append(thread)
        thread.start()

    def handle_manual_discovery_ready(self, payload: dict[str, Any]) -> None:
        self._manual_discovery_threads = [
            thread for thread in self._manual_discovery_threads if thread.is_alive()
        ]
        self._manual_discovery_running = False
        self.catalog_manual_discovery_button.setEnabled(True)
        self.catalog_manual_discovery_button.setText(f"Explorar {MANUAL_DISCOVERY_CANDIDATE_LIMIT}")
        error = payload.get("error")
        if error:
            self.statusBar().showMessage(str(error), 6000)
            return

        summary = payload.get("summary")
        if not isinstance(summary, dict):
            summary = {}
        inspected = int(summary.get("inspected") or 0)
        verified = int(summary.get("verified") or 0)
        related = int(summary.get("related_candidates") or 0)
        self.statusBar().showMessage(
            f"Exploracion lista: {inspected} revisados, {verified} publicados, {related} candidatos",
            6000,
        )
        self.request_catalog_filters_refresh()
        self.refresh_catalog()
        self.request_summary_refresh()

    def handle_update_button(self, *_args: object) -> None:
        if self._update_running:
            return
        self._update_running = True
        self.update_button.setEnabled(False)
        self.update_button.setText("Revisando...")

        def worker() -> None:
            try:
                payload = self.controller.check_for_update()
            except Exception as exc:
                payload = {"error": humanize_exception(exc)}
            self.updateCheckReady.emit(payload)

        self._update_threads = [thread for thread in self._update_threads if thread.is_alive()]
        thread = threading.Thread(target=worker, daemon=True, name="update-check")
        self._update_threads.append(thread)
        thread.start()

    def handle_update_check_ready(self, payload: dict[str, Any]) -> None:
        self._update_threads = [thread for thread in self._update_threads if thread.is_alive()]
        if self._closing:
            return
        error = payload.get("error")
        if error:
            self._update_running = False
            self.update_button.setEnabled(True)
            self.update_button.setText("Actualizar")
            self.statusBar().showMessage(str(error), 7000)
            return
        if not payload.get("configured"):
            self._update_running = False
            self.update_button.setEnabled(True)
            self.update_button.setText("Actualizar")
            self.statusBar().showMessage("No hay canal de actualizacion configurado.", 6000)
            return
        if not payload.get("update_available"):
            self._update_running = False
            self.update_button.setEnabled(True)
            self.update_button.setText("Actualizar")
            self.statusBar().showMessage("Ya tienes la version mas reciente.", 6000)
            return

        manifest = payload.get("manifest")
        if manifest is None:
            self._update_running = False
            self.update_button.setEnabled(True)
            self.update_button.setText("Actualizar")
            self.statusBar().showMessage("El manifest de actualizacion no es valido.", 6000)
            return

        version = str(payload.get("version") or "")
        answer = QMessageBox.question(
            self,
            "Actualizar",
            f"Hay una actualizacion disponible ({version}). La app se cerrara, se reemplazara y se abrira de nuevo.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            self._update_running = False
            self.update_button.setEnabled(True)
            self.update_button.setText("Actualizar")
            return

        self.update_button.setText("Descargando...")

        def worker() -> None:
            try:
                result = self.controller.download_update_and_restart(manifest)
            except Exception as exc:
                result = {"error": humanize_exception(exc)}
            self.updateApplyReady.emit(result)

        thread = threading.Thread(target=worker, daemon=True, name="update-apply")
        self._update_threads.append(thread)
        thread.start()

    def handle_update_apply_ready(self, payload: dict[str, Any]) -> None:
        self._update_threads = [thread for thread in self._update_threads if thread.is_alive()]
        error = payload.get("error")
        if error:
            self._update_running = False
            self.update_button.setEnabled(True)
            self.update_button.setText("Actualizar")
            self.statusBar().showMessage(str(error), 7000)
            return
        self.statusBar().showMessage("Actualizacion descargada. Reiniciando...", 3000)
        QTimer.singleShot(200, QApplication.instance().quit)

    def start_interest_initial_discovery(self, seed_id: int) -> None:
        self._interest_discovery_active += 1

        def worker() -> None:
            payload: dict[str, Any]
            try:
                payload = {
                    "seed_id": seed_id,
                    "summary": self.controller.run_interest_initial_discovery(
                        seed_id,
                        candidate_limit=150,
                    ),
                }
            except Exception as exc:
                payload = {"seed_id": seed_id, "error": humanize_exception(exc)}
            self.interestDiscoveryReady.emit(payload)

        self._interest_discovery_threads = [
            thread for thread in self._interest_discovery_threads if thread.is_alive()
        ]
        thread = threading.Thread(target=worker, daemon=True, name=f"interest-discovery-{seed_id}")
        self._interest_discovery_threads.append(thread)
        thread.start()

    def handle_interest_discovery_ready(self, payload: dict[str, Any]) -> None:
        self._interest_discovery_threads = [
            thread for thread in self._interest_discovery_threads if thread.is_alive()
        ]
        self._interest_discovery_active = max(0, self._interest_discovery_active - 1)
        if self._closing:
            return
        error = payload.get("error")
        if error:
            self.statusBar().showMessage(str(error), 6000)
            return
        summary = payload.get("summary")
        if not isinstance(summary, dict):
            summary = {}
        related = int(summary.get("related_candidates") or 0)
        self.statusBar().showMessage(
            f"Busqueda inicial lista: {related} candidatos en cola",
            6000,
        )
        self.request_catalog_filters_refresh()
        self.refresh_catalog()
        self.request_summary_refresh()

    def toggle_dashboard_more_info(self, *_args: object) -> None:
        visible = not self.dashboard_more_info.isVisible()
        self.dashboard_more_info.setVisible(visible)
        self.dashboard_more_info_button.setText("Ocultar info" if visible else "Mas info")

    def show_source_advanced(self, visible: bool) -> None:
        self.source_advanced_box.setVisible(True)

    def toggle_source_advanced(self, *_args: object) -> None:
        self.show_source_advanced(True)

    def open_sources_advanced(self, *_args: object) -> None:
        self.switch_page("sources")
        self.show_source_advanced(True)
        self.source_value.setFocus()

    def update_source_value_copy(self, *_args: object) -> None:
        source_type = str(self.source_type.currentData())
        if source_type == "search":
            self.source_value_label.setText("Búsqueda")
            self.source_value_field_label.setText("Búsqueda")
            self.source_value.setPlaceholderText("Escribe el término que quieres buscar")
        else:
            self.source_value_label.setText("Canal")
            self.source_value_field_label.setText("Canal")
            self.source_value.setPlaceholderText("Pega el link del canal o escribe @canal")

    def update_source_actions(self) -> None:
        selected = self.selected_sources()
        selection_count = len(selected)
        single_source = selected[0] if selection_count == 1 else None
        self.source_edit_button.setEnabled(selection_count == 1)
        self.source_toggle_button.setEnabled(selection_count == 1)
        self.source_delete_button.setEnabled(selection_count > 0)
        if single_source is None:
            self.source_toggle_button.setText("Reactivar")
            self._apply_busy_widgets()
            return
        self.source_toggle_button.setText(
            "Pausar" if single_source["enabled"] else "Reactivar"
        )
        self._apply_busy_widgets()

    def _set_widgets_busy(self, widgets: list[QWidget], busy: bool) -> None:
        for widget in widgets:
            if busy:
                self._busy_buttons.add(widget)  # type: ignore[arg-type]
                widget.setEnabled(False)
            else:
                self._busy_buttons.discard(widget)  # type: ignore[arg-type]
                widget.setEnabled(True)
        self._apply_busy_widgets()

    def _apply_busy_widgets(self) -> None:
        for widget in list(self._busy_buttons):
            widget.setEnabled(False)

    def _run_ui_action_async(
        self,
        name: str,
        action: Callable[[], Any],
        *,
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        busy_widgets: list[QWidget] | None = None,
    ) -> None:
        if self._closing:
            return
        self._ui_action_generation += 1
        action_id = self._ui_action_generation
        widgets = list(busy_widgets or [])
        self._ui_action_handlers[action_id] = {
            "name": name,
            "on_success": on_success,
            "on_error": on_error,
            "widgets": widgets,
        }
        self._set_widgets_busy(widgets, True)

        def worker() -> None:
            try:
                result = action()
                payload: dict[str, Any] = {"ok": True, "result": result}
            except Exception as exc:
                payload = {"ok": False, "error": exc}
            self.uiActionReady.emit(action_id, payload)

        self._ui_action_threads = [thread for thread in self._ui_action_threads if thread.is_alive()]
        thread = threading.Thread(target=worker, daemon=True, name=f"ui-action-{name}-{action_id}")
        self._ui_action_threads.append(thread)
        thread.start()

    def _handle_ui_action_ready(self, action_id: int, payload: object) -> None:
        self._ui_action_threads = [thread for thread in self._ui_action_threads if thread.is_alive()]
        handler = self._ui_action_handlers.pop(action_id, None)
        if handler is None:
            return
        widgets = list(handler.get("widgets") or [])
        try:
            if self._closing:
                return
            data = payload if isinstance(payload, dict) else {}
            if data.get("ok"):
                callback = handler.get("on_success")
                if callable(callback):
                    callback(data.get("result"))
            else:
                error = data.get("error")
                if not isinstance(error, Exception):
                    error = RuntimeError(str(error or "Error desconocido"))
                callback = handler.get("on_error")
                if callable(callback):
                    callback(error)
                else:
                    self.show_error("No se pudo completar la accion", error)
        finally:
            self._set_widgets_busy(widgets, False)
            if hasattr(self, "source_edit_button"):
                self.update_source_actions()

    def toggle_dashboard_history(self, *_args: object) -> None:
        visible = not self.latest_runs_table.isVisible()
        self.latest_runs_table.setVisible(visible)
        self.dashboard_history_toggle.setText("Ocultar ultimas revisiones" if visible else "Mostrar ultimas revisiones")

    def toggle_history_details(self, *_args: object) -> None:
        visible = not self.sources_full_history_table.isVisible()
        self.sources_full_history_table.setVisible(visible)
        self.sources_history_toggle.setText("Ocultar historial completo" if visible else "Ver historial completo")

    def reset_source_form(self) -> None:
        self._editing_source_id = None
        self.sources_table.blockSignals(True)
        self.sources_table.clearSelection()
        self.sources_table.setCurrentItem(None)
        self.sources_table.blockSignals(False)
        self.source_form_card.title_label.setText("Nueva búsqueda")
        self.source_type.setCurrentIndex(max(0, self.source_type.findData("channel")))
        self.source_value.clear()
        self.source_max_candidates.setValue(self.controller.get_last_max_candidates())
        self.source_enabled.setChecked(True)
        self.source_save_button.setText("Guardar búsqueda")
        self.source_cancel_edit_button.hide()
        self.update_source_value_copy()
        self.update_source_actions()

    def populate_source_form_from_selection(self) -> None:
        source = self.selected_source()
        if not source:
            return
        self._editing_source_id = int(source["id"])
        self.source_form_card.title_label.setText(f"Editar búsqueda #{source['id']}")
        self.source_type.setCurrentIndex(max(0, self.source_type.findData(source["type"])))
        self.source_value.setText(source["value"])
        self.source_max_candidates.setValue(int(source["max_candidates_per_run"]))
        self.source_enabled.setChecked(bool(source["enabled"]))
        self.source_save_button.setText("Guardar cambios")
        self.source_cancel_edit_button.show()
        self.update_source_value_copy()

    def edit_selected_source(self, *_args: object) -> None:
        source = self.selected_source()
        if not source:
            self.show_info("Selecciona una búsqueda primero.")
            return
        self.populate_source_form_from_selection()

    def cancel_source_edit(self, *_args: object) -> None:
        if self._editing_source_id is None:
            return
        self.reset_source_form()
        self.statusBar().showMessage("Edición cancelada", 3000)

    def handle_sources_quick_submit(self, *_args: object) -> None:
        self.switch_page("sources")
        self.source_value.setFocus()

    def handle_catalog_quick_submit(self, *_args: object) -> None:
        self.submit_quick_source(self.catalog_empty_input)

    def handle_topbar_quick_submit(self, *_args: object) -> None:
        self.submit_quick_source(self.topbar_quick_input)

    def handle_dashboard_quick_submit(self, *_args: object) -> None:
        self.submit_quick_source(self.dashboard_quick_input)

    def _update_dashboard_stats(self, stats: dict[str, Any]) -> None:
        if not hasattr(self, "metric_dubbed"):
            return
        self.metric_dubbed.set_value(str(stats.get("dubbed_videos", 0)))
        active_sources = len([s for s in self._source_rows if s.get("enabled")])
        self.metric_sources.set_value(str(active_sources))
        self.metric_scanned.set_value(str(stats.get("total_videos", 0)))
        latest_run = stats.get("latest_run")
        latest_run_at = latest_run.get("finished_at") or latest_run.get("started_at") if latest_run else None
        latest_activity_at = latest_timestamp(stats.get("latest_discovery_at"), latest_run_at)
        if latest_activity_at:
            self.metric_last_run.set_value(relative_time(latest_activity_at))
        else:
            self.metric_last_run.set_value("—")

    def submit_quick_source(self, field: QLineEdit) -> None:
        raw_value = field.text().strip()
        if not raw_value:
            self.show_info("Pega un canal o escribe una búsqueda.")
            return

        def action() -> dict[str, Any]:
            return self.controller.submit_interest(raw_value)

        def on_success(result: Any) -> None:
            seed_payload = result if isinstance(result, dict) else {}
            for f in (self.catalog_empty_input, self.topbar_quick_input, self.dashboard_quick_input):
                if f is not None:
                    f.clear()
            self._catalog_has_manual_interest = True
            self.statusBar().showMessage("Interes guardado. Buscando 150 candidatos iniciales.", 4000)
            self.request_summary_refresh()
            self.switch_page("catalog")
            self.refresh_catalog()
            if hasattr(self, "catalog_empty_stack"):
                self.catalog_empty_stack.setCurrentIndex(1)
            self.start_interest_initial_discovery(int(seed_payload["seed_id"]))

        def on_error(exc: Exception) -> None:
            self.show_error("No se pudo guardar el interes", exc)

        self._run_ui_action_async(
            "submit-interest",
            action,
            on_success=on_success,
            on_error=on_error,
            busy_widgets=[field],
        )

    def save_source(self, *_args: object) -> None:
        source = self.editing_source()
        try:
            payload = {
                "source_type": str(self.source_type.currentData()),
                "label": None,
                "value": self.source_value.text(),
                "max_candidates_per_run": int(self.source_max_candidates.value()),
                "enabled": self.source_enabled.isChecked(),
            }
            if not str(payload["value"]).strip():
                raise ValueError("Escribe un canal o una busqueda.")

            source_id_to_update = int(source["id"]) if source else None
            last_max_candidates = int(self.source_max_candidates.value())

            def action() -> dict[str, Any]:
                if source_id_to_update is not None:
                    source_id = source_id_to_update
                    self.controller.update_source(source_id, **payload)
                    saved_message = f"Busqueda #{source_id} actualizada"
                else:
                    source_id = self.controller.create_source(**payload)
                    saved_message = f"Busqueda #{source_id} guardada"
                self.controller.set_last_max_candidates(last_max_candidates)
                run_error: Exception | None = None
                if bool(payload["enabled"]):
                    try:
                        self.controller.run_source(source_id)
                    except Exception as exc:
                        run_error = exc
                return {
                    "source_id": source_id,
                    "saved_message": saved_message,
                    "enabled": bool(payload["enabled"]),
                    "run_error": run_error,
                }

            def on_success(result: Any) -> None:
                data = result if isinstance(result, dict) else {}
                saved_message = str(data.get("saved_message") or "Busqueda guardada")
                run_error = data.get("run_error")
                self.reset_source_form()
                self.request_summary_refresh()
                self.refresh_catalog()
                if isinstance(run_error, Exception):
                    self.statusBar().showMessage(saved_message, 4000)
                    self.show_error("Se guardo, pero no pudo empezar la revision automatica", run_error)
                    return
                if bool(data.get("enabled")):
                    self.statusBar().showMessage(f"{saved_message}. Revisando videos.", 4000)
                else:
                    self.statusBar().showMessage(saved_message, 4000)

            def on_error(exc: Exception) -> None:
                self.show_error("No se pudo guardar la busqueda", exc)

            self._run_ui_action_async(
                "save-source",
                action,
                on_success=on_success,
                on_error=on_error,
                busy_widgets=[self.source_save_button],
            )
            return

        except Exception as exc:
            self.show_error("No se pudo guardar la búsqueda", exc)

    def delete_selected_sources(self, *_args: object) -> None:
        selected = self.selected_sources()
        if not selected:
            self.show_info("Selecciona al menos una busqueda para borrarla.")
            return

        delete_videos = self.confirm_delete_sources(selected)
        if delete_videos is None:
            return

        source_ids = [int(source["id"]) for source in selected]

        def action() -> None:
            self.controller.delete_sources(source_ids, delete_videos=delete_videos)

        def on_success(_result: Any) -> None:
            if delete_videos:
                self.statusBar().showMessage("Busquedas y videos guardados borrados", 4000)
            else:
                self.statusBar().showMessage("Busquedas borradas. Videos conservados.", 4000)
            self.reset_source_form()
            self.request_summary_refresh()
            self.refresh_catalog()

        def on_error(exc: Exception) -> None:
            self.show_error("No se pudieron borrar las busquedas", exc)

        self._run_ui_action_async(
            "delete-sources",
            action,
            on_success=on_success,
            on_error=on_error,
            busy_widgets=[self.source_delete_button],
        )
        return

    def confirm_delete_sources(self, selected: list[dict[str, Any]]) -> bool | None:
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Question)
        message.setWindowTitle("Borrar busquedas")
        if len(selected) > 1:
            message.setText(f"¿Quieres borrar o conservar los videos de estas {len(selected)} fuentes?")
            message.setInformativeText(
                "Las busquedas seleccionadas se quitaran de la lista. Elige que hacer con sus videos guardados."
            )
        else:
            message.setText("¿Quieres borrar o conservar los videos de esta fuente?")
            message.setInformativeText(
                f"La busqueda '{selected[0]['label']}' se quitara de la lista. Elige que hacer con sus videos guardados."
            )

        cancel_button = message.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        keep_button = message.addButton("Conservar videos", QMessageBox.ButtonRole.AcceptRole)
        delete_button = message.addButton("Borrar videos guardados", QMessageBox.ButtonRole.DestructiveRole)
        message.setDefaultButton(cancel_button)
        message.setEscapeButton(cancel_button)
        delete_button.setStyleSheet(
            """
            QPushButton {
                background: #b92b2b;
                color: #ffffff;
                border: 2px solid #ff6b6b;
                border-bottom: 3px solid #ff9c9c;
                border-radius: 8px;
                padding: 10px 18px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: #d43b3b;
                border: 2px solid #ff8585;
                border-bottom: 3px solid #ffd0d0;
            }
            """
        )
        cancel_button.setStyleSheet(SOURCE_SECONDARY_BUTTON_STYLE)
        keep_button.setStyleSheet(SOURCE_SECONDARY_BUTTON_STYLE)

        message.exec()
        clicked = message.clickedButton()
        if clicked == delete_button:
            return True
        if clicked == keep_button:
            return False
        if clicked == cancel_button:
            return None
        return None

    def toggle_selected_source(self, *_args: object) -> None:
        source = self.selected_source()
        if not source:
            self.show_info("Selecciona una búsqueda primero.")
            return
        try:
            if source["enabled"]:
                answer = QMessageBox.question(
                    self,
                    "Pausar búsqueda",
                    f"¿Quieres pausar “{source['label']}”? Dejará de revisarse hasta que la reactives.",
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
            source_id = int(source["id"])
            was_enabled = bool(source["enabled"])
            label = str(source["label"])

            def action() -> None:
                self.controller.toggle_source(source_id)

            def on_success(_result: Any) -> None:
                self.request_summary_refresh()
                state = "pausada" if was_enabled else "reactivada"
                self.statusBar().showMessage(f"Busqueda {state}: {label}", 4000)

            def on_error(exc: Exception) -> None:
                self.show_error("No se pudo cambiar el estado de la busqueda", exc)

            self._run_ui_action_async(
                "toggle-source",
                action,
                on_success=on_success,
                on_error=on_error,
                busy_widgets=[self.source_toggle_button],
            )
            return

        except Exception as exc:
            self.show_error("No se pudo cambiar el estado de la búsqueda", exc)

    def increase_full_source_limits(self, *_args: object) -> None:
        def action() -> int:
            return self.controller.increase_full_source_limits(500)

        def on_success(result: Any) -> None:
            changed = int(result or 0)
            self.request_summary_refresh()
            if changed:
                self.source_increase_limit_button.hide()
                self.statusBar().showMessage(
                    f"Limite aumentado en 500 para {changed} fuente{'s' if changed != 1 else ''}",
                    4000,
                )
            else:
                self.statusBar().showMessage("No hay fuentes llenas", 4000)

        def on_error(exc: Exception) -> None:
            self.show_error("No se pudo aumentar el limite", exc)

        self.source_increase_limit_button.hide()
        self._run_ui_action_async(
            "increase-source-limits",
            action,
            on_success=on_success,
            on_error=on_error,
            busy_widgets=[self.source_increase_limit_button],
        )
        return

    def run_selected_source(self, *_args: object) -> None:
        source = self.selected_source()
        if not source:
            self.show_info("Selecciona una búsqueda primero.")
            return
        source_id = int(source["id"])
        label = str(source["label"])

        def action() -> int:
            return self.controller.run_source(source_id)

        def on_success(_result: Any) -> None:
            self.statusBar().showMessage(f"Busqueda iniciada para \"{label}\"", 4000)
            self.request_summary_refresh()
            self.refresh_catalog()

        def on_error(exc: Exception) -> None:
            self.show_error("No se pudo iniciar la busqueda", exc)

        self._run_ui_action_async(
            "run-source",
            action,
            on_success=on_success,
            on_error=on_error,
            busy_widgets=[],
        )
        return

    def handle_run_all(self, *_args: object) -> None:
        def action() -> int:
            return self.controller.run_all()

        def on_success(_result: Any) -> None:
            self.statusBar().showMessage("Busqueda iniciada para todas tus busquedas activas", 4000)
            self.request_summary_refresh()
            self.refresh_catalog()

        def on_error(exc: Exception) -> None:
            self.show_error("No se pudo iniciar la busqueda general", exc)

        self._run_ui_action_async(
            "run-all",
            action,
            on_success=on_success,
            on_error=on_error,
            busy_widgets=[],
        )
        return

    def _populate_runs_table(self, table: QTableWidget, runs: list[dict[str, Any]], mode: str) -> None:
        source_lookup = {int(source["id"]): source["label"] for source in self._source_rows}
        table.setRowCount(len(runs))
        for row, run in enumerate(runs):
            _status_chip, color = status_chip(run["status"])
            status_text = friendly_status_text(run["status"])
            if mode == "latest":
                values = [
                    str(run["id"]),
                    pretty_run_scope(run["scope"], source_lookup),
                    status_text,
                    str(run["candidates_found"]),
                    str(run["dubbed_found"]),
                    short_timestamp(run["started_at"]),
                ]
            elif mode == "recent":
                values = [
                    pretty_run_scope(run["scope"], source_lookup),
                    status_text,
                    str(run["videos_checked"]),
                    str(run["dubbed_found"]),
                    short_timestamp(run["started_at"]),
                ]
            elif mode == "full":
                values = [
                    pretty_run_scope(run["scope"], source_lookup),
                    status_text,
                    str(run["candidates_found"]),
                    str(run["videos_checked"]),
                    str(run["dubbed_found"]),
                    short_timestamp(run["started_at"]),
                    run["error"] or "",
                ]
            else:
                values = [
                    str(run["id"]),
                    pretty_run_scope(run["scope"], source_lookup),
                    status_text,
                    str(run["candidates_found"]),
                    str(run["videos_checked"]),
                    str(run["dubbed_found"]),
                    short_timestamp(run["started_at"]),
                    run["error"] or "",
                ]

            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 1 or (mode == "latest" and col == 2) or (mode != "latest" and col == 1):
                    if status_text == value:
                        item.setForeground(QColor(color))
                table.setItem(row, col, item)
        table.resizeColumnsToContents()

    def update_topbar_status(self) -> None:
        active_run_id = self.controller.active_run_id()
        if active_run_id is None:
            self.apply_topbar_status(None)
        else:
            self.request_active_run_snapshot(active_run_id)

    def apply_topbar_status(self, active_run: dict[str, Any] | None) -> None:
        source_lookup = {int(source["id"]): source["label"] for source in self._source_rows}
        if active_run:
            self._active_run_progress = dict(active_run)
            scope = pretty_run_scope(active_run["scope"], source_lookup)
            checked = int(active_run.get("videos_checked") or 0)
            total = int(active_run.get("candidates_found") or 0)
            dubbed = int(active_run.get("dubbed_found") or 0)
            if total > 0:
                safe_total = max(total, checked, 1)
                self.topbar_progress.setRange(0, safe_total)
                self.topbar_progress.setValue(min(checked, safe_total))
                self.topbar_status_label.setText(f"Buscando en {scope}… {checked}/{safe_total} · {dubbed} doblados")
            else:
                self.topbar_progress.setRange(0, 0)
                self.topbar_status_label.setText(f"Buscando en {scope}… preparando revisión")
            self.topbar_progress.show()
            return

        if self._active_discovery_progress is not None:
            self.apply_discovery_progress(self._active_discovery_progress)
            return

        self._active_run_progress = None
        self.topbar_progress.hide()
        latest_run = self._latest_stats.get("latest_run")
        latest_run_at = latest_run.get("finished_at") or latest_run.get("started_at") if latest_run else None
        latest_discovery_at = self._latest_stats.get("latest_discovery_at")
        latest_activity_at = latest_timestamp(latest_discovery_at, latest_run_at)
        if latest_activity_at:
            when = relative_time(latest_activity_at)
            label = "automática" if latest_activity_at == latest_discovery_at else "búsqueda"
            self.topbar_status_label.setText(f"Última {label}: {when}")
        else:
            self.topbar_status_label.setText("Aún no has buscado videos")

    def apply_run_progress_event(self, event: dict[str, Any]) -> None:
        source_lookup = {int(source["id"]): source["label"] for source in self._source_rows}
        progress = dict(self._active_run_progress or {})
        progress.update(event)
        self._active_run_progress = progress
        scope = pretty_run_scope(str(progress.get("scope") or progress.get("run_scope") or "metadata"), source_lookup)
        checked = int(progress.get("videos_checked") or 0)
        total = int(progress.get("candidates_found") or 0)
        dubbed = int(progress.get("dubbed_found") or 0)
        if total > 0:
            safe_total = max(total, checked, 1)
            self.topbar_progress.setRange(0, safe_total)
            self.topbar_progress.setValue(min(checked, safe_total))
            self.topbar_status_label.setText(f"Buscando en {scope}… {checked}/{safe_total} · {dubbed} doblados")
        else:
            self.topbar_progress.setRange(0, 0)
            self.topbar_status_label.setText(f"Buscando en {scope}… preparando revisión")
        self.topbar_progress.show()

    def apply_discovery_progress(self, event: dict[str, Any]) -> None:
        inspected = int(event.get("inspected") or 0)
        target = max(int(event.get("target") or 0), inspected, 1)
        verified = int(event.get("verified") or 0)
        failed = int(event.get("failed") or 0)
        self.topbar_progress.setRange(0, target)
        self.topbar_progress.setValue(min(inspected, target))
        suffix = f"{inspected}/{target} · {verified} doblados"
        if failed:
            suffix += f" · {failed} fallidos"
        self.topbar_status_label.setText(f"Explorando videos… {suffix}")
        self.topbar_progress.show()

    def request_active_run_snapshot(self, active_run_id: int) -> None:
        if self._active_run_snapshot_loading or self._closing:
            return
        self._active_run_snapshot_loading = True

        def worker() -> None:
            try:
                run = self.controller.active_run_snapshot()
            except Exception:
                run = None
            self.activeRunSnapshotReady.emit(active_run_id, {"run": run})

        self._active_run_snapshot_threads = [
            thread for thread in self._active_run_snapshot_threads if thread.is_alive()
        ]
        thread = threading.Thread(target=worker, daemon=True, name=f"active-run-{active_run_id}")
        self._active_run_snapshot_threads.append(thread)
        thread.start()

    def handle_active_run_snapshot_ready(self, active_run_id: int, payload: dict[str, Any]) -> None:
        self._active_run_snapshot_threads = [
            thread for thread in self._active_run_snapshot_threads if thread.is_alive()
        ]
        self._active_run_snapshot_loading = False
        if self._closing or self.controller.active_run_id() != active_run_id:
            return
        run = payload.get("run")
        self.apply_topbar_status(run if isinstance(run, dict) else None)

    def refresh_all(self, *_args: object) -> None:
        self.request_summary_refresh()
        self._catalog_dirty = True
        if self._current_page_key == "catalog":
            self.refresh_catalog()

    def invalidate_summary_refresh(self) -> None:
        self._summary_refresh_generation += 1
        self._summary_refresh_loading = False
        self._summary_refresh_dirty = False

    def refresh_dashboard(self, *_args: object) -> None:
        self.invalidate_summary_refresh()
        stats = self.controller.dashboard_stats()
        latest_runs = self.controller.list_runs(limit=5)
        self.apply_dashboard_stats(stats, latest_runs=latest_runs)

    def apply_dashboard_stats(self, stats: dict[str, Any], *, latest_runs: list[dict[str, Any]] | None = None) -> None:
        self._latest_stats = stats
        active_run_id = self.controller.active_run_id()
        if active_run_id is None:
            self.apply_topbar_status(None)
        else:
            self.request_active_run_snapshot(active_run_id)
        if latest_runs is not None:
            self._populate_runs_table(self.latest_runs_table, latest_runs[:5], "latest")
        self._update_dashboard_stats(stats)

    def refresh_sources(self, *_args: object) -> None:
        self.invalidate_summary_refresh()
        selected_source_ids = {int(source["id"]) for source in self.selected_sources()}
        self.apply_source_rows(self.controller.list_sources(), selected_source_ids=selected_source_ids)

    def apply_source_rows(
        self,
        source_rows: list[dict[str, Any]],
        *,
        selected_source_ids: set[int] | None = None,
    ) -> None:
        selected_source_ids = set() if selected_source_ids is None else selected_source_ids
        self._source_rows = source_rows
        editing_source_id = self._editing_source_id
        full_sources = [source for source in self._source_rows if source_is_full(source)]
        self.source_increase_limit_button.setVisible(bool(full_sources))

        self.sources_table.blockSignals(True)
        self.sources_table.setRowCount(len(self._source_rows))
        for row, source in enumerate(self._source_rows):
            is_full = source_is_full(source)
            values = [
                source["label"],
                pretty_source_type(source["type"]),
                source["value"],
                pretty_source_state(bool(source["enabled"]), is_full),
                str(source["max_candidates_per_run"]),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 3:
                    if is_full:
                        item.setForeground(QColor("#ffcf5a"))
                        item.setToolTip("Esta fuente ya alcanzó su límite actual.")
                    else:
                        item.setForeground(Qt.GlobalColor.cyan if source["enabled"] else Qt.GlobalColor.lightGray)
                self.sources_table.setItem(row, col, item)

        self.sources_table.clearSelection()
        if editing_source_id is not None:
            matched_row = next(
                (index for index, source in enumerate(self._source_rows) if int(source["id"]) == int(editing_source_id)),
                None,
            )
            if matched_row is not None:
                self.sources_table.selectRow(matched_row)
            else:
                self.sources_table.setCurrentItem(None)
                self._editing_source_id = None
        elif selected_source_ids:
            for index, source in enumerate(self._source_rows):
                if int(source["id"]) in selected_source_ids:
                    self.sources_table.selectRow(index)
        else:
            self.sources_table.setCurrentItem(None)

        self.sources_table.blockSignals(False)
        if self._current_page_key == "catalog":
            self.request_catalog_filters_refresh()
        else:
            self._catalog_filters_dirty = True
        self.update_source_actions()

    def refresh_runs(self, *_args: object) -> None:
        self.invalidate_summary_refresh()
        self.apply_run_rows(self.controller.list_runs(limit=100))

    def apply_run_rows(self, run_rows: list[dict[str, Any]]) -> None:
        self._run_rows = run_rows
        self._populate_runs_table(self.latest_runs_table, self._run_rows[:5], "latest")
        self._populate_runs_table(self.runs_table, self._run_rows, "runs")
        self._populate_runs_table(self.sources_recent_runs_table, self._run_rows[:3], "recent")
        self._populate_runs_table(self.sources_full_history_table, self._run_rows, "full")

    def request_summary_refresh(self, *_args: object) -> None:
        if self._closing or not self.services.settings.db_path.parent.exists():
            return
        if self._summary_refresh_loading:
            self._summary_refresh_dirty = True
            return

        self._summary_refresh_generation += 1
        generation = self._summary_refresh_generation
        selected_source_ids = {int(source["id"]) for source in self.selected_sources()}
        self._summary_refresh_loading = True
        self._summary_refresh_dirty = False

        def worker() -> None:
            payload: dict[str, Any]
            try:
                sources = self.controller.list_sources()
                runs = self.controller.list_runs(limit=100)
                stats = self.controller.dashboard_stats()
                payload = {
                    "sources": sources,
                    "runs": runs,
                    "stats": stats,
                    "selected_source_ids": selected_source_ids,
                }
            except Exception as exc:
                payload = {"error": humanize_exception(exc)}
            self.summaryRefreshReady.emit(generation, payload)

        self._summary_refresh_threads = [
            thread for thread in self._summary_refresh_threads if thread.is_alive()
        ]
        thread = threading.Thread(target=worker, daemon=True, name=f"summary-refresh-{generation}")
        self._summary_refresh_threads.append(thread)
        thread.start()

    def handle_summary_refresh_ready(self, generation: int, payload: dict[str, Any]) -> None:
        self._summary_refresh_threads = [
            thread for thread in self._summary_refresh_threads if thread.is_alive()
        ]
        if generation != self._summary_refresh_generation:
            return
        self._summary_refresh_loading = False
        if self._closing:
            return
        error = payload.get("error")
        if error:
            self.statusBar().showMessage(str(error), 6000)
        else:
            source_rows = payload.get("sources")
            run_rows = payload.get("runs")
            stats = payload.get("stats")
            selected_source_ids = payload.get("selected_source_ids")
            if not isinstance(selected_source_ids, set):
                selected_source_ids = set()
            if isinstance(source_rows, list):
                self.apply_source_rows(source_rows, selected_source_ids=selected_source_ids)
            if isinstance(run_rows, list):
                self.apply_run_rows(run_rows)
            if isinstance(stats, dict):
                self.apply_dashboard_stats(stats, latest_runs=run_rows if isinstance(run_rows, list) else None)

        if self._summary_refresh_dirty:
            self._summary_refresh_dirty = False
            QTimer.singleShot(0, self.request_summary_refresh)

    def refresh_catalog_filters(self, *_args: object) -> None:
        if self._closing or not self.services.settings.db_path.parent.exists():
            return
        self._catalog_filters_generation += 1
        self._catalog_filters_loading = False
        filters = self.controller.list_catalog_filters()
        self._apply_catalog_filters(filters)

    def request_catalog_filters_refresh(self, *_args: object) -> None:
        if self._closing or not self.services.settings.db_path.parent.exists():
            return
        if self._catalog_filters_loading:
            self._catalog_filters_dirty = True
            return

        self._catalog_filters_generation += 1
        generation = self._catalog_filters_generation
        source_rows = list(self._source_rows)
        self._catalog_filters_loading = True
        self._catalog_filters_dirty = False

        def worker() -> None:
            try:
                filters = self.controller.list_catalog_filters()
            except Exception:
                filters = None
            self.catalogFiltersReady.emit(
                generation,
                {"filters": filters, "source_rows": source_rows},
            )

        self._catalog_filter_threads = [thread for thread in self._catalog_filter_threads if thread.is_alive()]
        thread = threading.Thread(target=worker, daemon=True, name=f"catalog-filters-{generation}")
        self._catalog_filter_threads.append(thread)
        thread.start()

    def handle_catalog_filters_ready(self, generation: int, payload: dict[str, Any]) -> None:
        self._catalog_filter_threads = [thread for thread in self._catalog_filter_threads if thread.is_alive()]
        if generation != self._catalog_filters_generation:
            return
        self._catalog_filters_loading = False
        filters = payload.get("filters")
        if not isinstance(filters, dict) or self._closing:
            return
        source_rows = payload.get("source_rows")
        if not isinstance(source_rows, list):
            source_rows = self._source_rows
        should_refresh_again = self._catalog_filters_dirty
        self._apply_catalog_filters(filters, source_rows)
        if should_refresh_again:
            QTimer.singleShot(0, self.request_catalog_filters_refresh)

    def _apply_catalog_filters(
        self,
        filters: dict[str, list[Any]],
        source_rows: list[dict[str, Any]] | None = None,
    ) -> None:
        source_rows = self._source_rows if source_rows is None else source_rows

        current_lang = self.catalog_lang.currentData()
        current_source = self.catalog_source.currentData()
        current_channel = self.catalog_channel.currentData()
        current_year = combo_year_value(self.catalog_year)
        current_after_year = combo_year_value(self.catalog_after_year)
        current_before_year = combo_year_value(self.catalog_before_year)

        self.catalog_lang.blockSignals(True)
        self.catalog_source.blockSignals(True)
        self.catalog_channel.blockSignals(True)
        self.catalog_year.blockSignals(True)
        self.catalog_after_year.blockSignals(True)
        self.catalog_before_year.blockSignals(True)

        self.catalog_lang.clear()
        self.catalog_lang.addItem("Todos los idiomas", "")
        for lang in filters["languages"]:
            label = "Español" if lang == SPANISH_LANGUAGE_FILTER else lang
            self.catalog_lang.addItem(label, lang)

        self.catalog_source.clear()
        self.catalog_source.addItem("Todos los intereses", None)
        for source in source_rows:
            self.catalog_source.addItem(source["label"], source["id"])

        self.catalog_channel.clear()
        self.catalog_channel.addItem("Todos los canales", "")
        for channel in filters["channels"]:
            self.catalog_channel.addItem(channel, channel)

        for combo, empty_text in (
            (self.catalog_year, "Cualquier año"),
            (self.catalog_after_year, "Sin fecha mínima"),
            (self.catalog_before_year, "Sin fecha máxima"),
        ):
            combo.clear()
            combo.addItem(empty_text, None)
            for year in range(datetime.now().year, YOUTUBE_FIRST_YEAR - 1, -1):
                combo.addItem(str(year), year)

        if current_lang in SPANISH_LANGUAGE_CODES:
            current_lang = SPANISH_LANGUAGE_FILTER

        if current_lang:
            self.catalog_lang.setCurrentIndex(max(0, self.catalog_lang.findData(current_lang)))
        else:
            preferred_lang = (
                SPANISH_LANGUAGE_FILTER
                if self.catalog_lang.findData(SPANISH_LANGUAGE_FILTER) >= 0
                else ""
            )
            self.catalog_lang.setCurrentIndex(max(0, self.catalog_lang.findData(preferred_lang)))
        self.catalog_source.setCurrentIndex(max(0, self.catalog_source.findData(current_source)))
        self.catalog_channel.setCurrentIndex(max(0, self.catalog_channel.findData(current_channel)))
        self.catalog_year.setCurrentIndex(max(0, self.catalog_year.findData(current_year)))
        self.catalog_after_year.setCurrentIndex(max(0, self.catalog_after_year.findData(current_after_year)))
        self.catalog_before_year.setCurrentIndex(max(0, self.catalog_before_year.findData(current_before_year)))

        self.catalog_lang.blockSignals(False)
        self.catalog_source.blockSignals(False)
        self.catalog_channel.blockSignals(False)
        self.catalog_year.blockSignals(False)
        self.catalog_after_year.blockSignals(False)
        self.catalog_before_year.blockSignals(False)
        self._catalog_filters_dirty = False


    def update_catalog_surface(self) -> None:
        total_videos = int(self._latest_stats.get("total_videos", 0))
        active_run_id = self.controller.active_run_id()
        active_discovery = (
            active_run_id is not None
            or self._manual_discovery_running
            or self._interest_discovery_active > 0
            or self._catalog_has_manual_interest
        )
        has_videos = total_videos > 0 or bool(self._catalog_rows)

        self.catalog_controls_shell.setVisible(has_videos)
        self.catalog_grid_host.setVisible(has_videos)
        self.catalog_empty_stack.setVisible(not has_videos)
        if not has_videos:
            self.catalog_filters_panel.hide()
            self.catalog_filters_toggle.setText("Mas filtros")

        if not has_videos:
            self.catalog_empty_stack.setCurrentIndex(1 if active_discovery else 0)
            return

        self.render_catalog_cards()

    def _current_catalog_filters(self) -> dict[str, Any]:
        return {
            "lang": self.catalog_lang.currentData() or None,
            "source_id": self.catalog_source.currentData(),
            "channel": self.catalog_channel.currentData() or None,
            "query": self.catalog_query.text() or None,
            "only_dubbed": bool(self.catalog_visibility.currentData()),
            "only_favorites": self.catalog_favorites_only.isChecked(),
            "dub_kind": str(self.catalog_dub_kind.currentData() or ""),
            "sort_by": str(self.catalog_sort.currentData() or "recent"),
            "year": combo_year_value(self.catalog_year),
            "year_after": combo_year_value(self.catalog_after_year),
            "year_before": combo_year_value(self.catalog_before_year),
            "max_duration_seconds": combo_duration_value(self.catalog_max_duration),
        }

    def refresh_catalog(self, *_args: object) -> None:
        if self._current_page_key != "catalog":
            self._catalog_dirty = True
            return

        filters = self._current_catalog_filters()
        same_filter_refresh = (
            bool(self._catalog_rows)
            and filters == self._catalog_filter_state
            and hasattr(self, "catalog_view")
        )
        if same_filter_refresh:
            self._catalog_restore_scroll_anchor = self._capture_catalog_scroll_anchor()
        else:
            self._catalog_restore_scroll_anchor = None
        if same_filter_refresh and self._catalog_loading_page and self._catalog_loading_append:
            self._catalog_refresh_deferred_after_append = True
            return
        self._catalog_filter_state = filters
        self._catalog_query_generation += 1
        generation = self._catalog_query_generation
        self._catalog_restore_scroll_generation = generation if self._catalog_restore_scroll_anchor else None
        self._catalog_loading_page = False
        self._catalog_loading_append = False
        if not same_filter_refresh:
            self._catalog_refresh_deferred_after_append = False
        self._catalog_next_cursor = None
        if not same_filter_refresh:
            self._catalog_count_pending = False
            self._catalog_count_exact = False
            self._catalog_total_count = 0
            self._catalog_rows = []
        self._catalog_loading_page = True
        if hasattr(self, "catalog_model") and not same_filter_refresh:
            self.catalog_model.set_items([])
            self._sync_catalog_card_compat_widgets()
            self.update_catalog_results_count()
        page_size = self._catalog_refresh_page_size(same_filter_refresh)
        self.start_catalog_page_worker(generation, filters, cursor=None, append=False, page_size=page_size)

    def _catalog_refresh_page_size(self, same_filter_refresh: bool) -> int:
        if not same_filter_refresh:
            return CATALOG_PAGE_SIZE
        loaded_count = len(self._catalog_rows)
        if hasattr(self, "catalog_model"):
            loaded_count = max(loaded_count, self.catalog_model.rowCount())
        return max(CATALOG_PAGE_SIZE, loaded_count)

    def _capture_catalog_scroll_anchor(self) -> CatalogScrollAnchor | None:
        if not hasattr(self, "catalog_view") or not hasattr(self, "catalog_model"):
            return None
        bar = self.catalog_view.verticalScrollBar()
        scroll_value = int(bar.value())
        if scroll_value <= 0:
            return None
        bottom_distance = max(0, int(bar.maximum()) - scroll_value)
        viewport = self.catalog_view.viewport()
        anchor_index = QModelIndex()
        for y in (8, 32, 64, max(8, viewport.height() // 3)):
            anchor_index = self.catalog_view.indexAt(QPoint(8, y))
            if anchor_index.isValid():
                break
        if not anchor_index.isValid():
            return (None, 0, scroll_value, None, bottom_distance)
        item = anchor_index.data(CATALOG_ITEM_ROLE)
        video_id = str(item.get("video_id") or "") if isinstance(item, dict) else ""
        offset = self.catalog_view.visualRect(anchor_index).top()
        return (video_id or None, int(offset), scroll_value, int(anchor_index.row()), bottom_distance)

    def _restore_catalog_scroll_anchor_if_needed(self, generation: int) -> None:
        if self._catalog_restore_scroll_generation != generation or self._catalog_restore_scroll_anchor is None:
            return
        anchor = self._catalog_restore_scroll_anchor
        self._catalog_restore_scroll_generation = None
        self._catalog_restore_scroll_anchor = None
        self._restore_catalog_scroll_anchor(anchor)

    def _apply_catalog_scroll_anchor(self, anchor: CatalogScrollAnchor | None) -> None:
        if anchor is None:
            return
        if self._closing or not hasattr(self, "catalog_view") or not hasattr(self, "catalog_model"):
            return
        video_id, offset, fallback_value, old_row, bottom_distance = anchor
        bar = self.catalog_view.verticalScrollBar()
        if bottom_distance <= max(240, self.catalog_view.height()):
            target_value = max(0, min(bar.maximum(), bar.maximum() - bottom_distance))
            self._set_catalog_near_bottom_suppressed_once()
            bar.setValue(target_value)
            self.schedule_visible_catalog_thumbnails()
            return
        restored = False
        if video_id:
            for row, item in enumerate(self.catalog_model.items):
                if str(item.get("video_id") or "") != video_id:
                    continue
                if old_row == row:
                    bar.setValue(max(0, min(bar.maximum(), fallback_value)))
                else:
                    index = self.catalog_model.index(row, 0)
                    self.catalog_view.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtTop)
                    bar.setValue(max(0, min(bar.maximum(), bar.value() - offset)))
                restored = True
                break
        if not restored:
            bar.setValue(max(0, min(bar.maximum(), fallback_value)))
        self.schedule_visible_catalog_thumbnails()

    def _restore_catalog_scroll_anchor(self, anchor: CatalogScrollAnchor | None) -> None:
        if anchor is None:
            return
        QTimer.singleShot(0, lambda: self._apply_catalog_scroll_anchor(anchor))

    def _stop_catalog_scroll_range_restore(self, token: int | None = None) -> None:
        if token is not None and token != self._catalog_scroll_restore_token:
            return
        handler = self._catalog_scroll_range_restore_handler
        if handler is None or not hasattr(self, "catalog_view"):
            self._catalog_scroll_range_restore_handler = None
            return
        try:
            self.catalog_view.verticalScrollBar().rangeChanged.disconnect(handler)
        except (RuntimeError, TypeError):
            pass
        self._catalog_scroll_range_restore_handler = None

    def _start_catalog_scroll_range_restore(self, anchor: CatalogScrollAnchor | None) -> int:
        self._catalog_scroll_restore_token += 1
        token = self._catalog_scroll_restore_token
        self._stop_catalog_scroll_range_restore()
        if anchor is None or not hasattr(self, "catalog_view"):
            return token
        remaining_updates = 12
        bar = self.catalog_view.verticalScrollBar()

        def restore_on_range_change(_minimum: int, _maximum: int) -> None:
            nonlocal remaining_updates
            if token != self._catalog_scroll_restore_token:
                return
            remaining_updates -= 1
            self._apply_catalog_scroll_anchor(anchor)
            if remaining_updates <= 0:
                self._stop_catalog_scroll_range_restore(token)

        self._catalog_scroll_range_restore_handler = restore_on_range_change
        bar.rangeChanged.connect(restore_on_range_change)
        QTimer.singleShot(250, lambda: self._stop_catalog_scroll_range_restore(token))
        return token

    def _append_catalog_items_preserving_scroll(
        self,
        rows: list[dict[str, Any]],
        anchor: CatalogScrollAnchor | None,
    ) -> None:
        self._start_catalog_scroll_range_restore(anchor)
        previous_layout_mode = self.catalog_view.layoutMode()
        try:
            self.catalog_view.setLayoutMode(QListView.LayoutMode.SinglePass)
            self.catalog_model.append_items(rows)
            self.catalog_view.doItemsLayout()
        finally:
            self.catalog_view.setLayoutMode(previous_layout_mode)
        self._apply_catalog_scroll_anchor(anchor)
        QTimer.singleShot(0, lambda: self._apply_catalog_scroll_anchor(anchor))

    def _set_catalog_near_bottom_suppressed_once(self) -> None:
        self._suppress_next_catalog_near_bottom = True
        QTimer.singleShot(0, self._clear_catalog_near_bottom_suppression)

    def _clear_catalog_near_bottom_suppression(self) -> None:
        self._suppress_next_catalog_near_bottom = False

    def start_catalog_page_worker(
        self,
        generation: int,
        filters: dict[str, Any],
        *,
        cursor: str | None,
        append: bool,
        page_size: int | None = None,
    ) -> None:
        requested_page_size = max(1, int(page_size or CATALOG_PAGE_SIZE))

        def worker() -> None:
            payload: dict[str, Any]
            try:
                payload = self.controller.list_catalog_page(
                    lang=filters.get("lang"),
                    source_id=filters.get("source_id"),
                    channel=filters.get("channel"),
                    query=filters.get("query"),
                    only_dubbed=bool(filters.get("only_dubbed")),
                    only_favorites=bool(filters.get("only_favorites")),
                    dub_kind=str(filters.get("dub_kind") or ""),
                    sort_by=str(filters.get("sort_by") or "recent"),
                    year=filters.get("year"),
                    year_after=filters.get("year_after"),
                    year_before=filters.get("year_before"),
                    max_duration_seconds=filters.get("max_duration_seconds"),
                    page_size=requested_page_size,
                    cursor=cursor,
                )
            except Exception as exc:
                payload = {"items": [], "next_cursor": None, "error": humanize_exception(exc)}
            self.catalogPageReady.emit(generation, payload, append)

        self._catalog_page_threads = [thread for thread in self._catalog_page_threads if thread.is_alive()]
        thread = threading.Thread(
            target=worker,
            daemon=True,
            name=f"catalog-page-{generation}-{'append' if append else 'initial'}",
        )
        self._catalog_page_threads.append(thread)
        thread.start()

    def handle_catalog_page_ready(self, generation: int, page: dict[str, Any], append: bool) -> None:
        self._catalog_page_threads = [thread for thread in self._catalog_page_threads if thread.is_alive()]
        if generation != self._catalog_query_generation or self._closing:
            return
        self._catalog_loading_page = False
        if append:
            self._catalog_loading_append = False
        error = page.get("error")
        if error:
            self.statusBar().showMessage(str(error), 6000)
            if not append:
                self.update_catalog_surface()
            self._run_deferred_catalog_refresh_after_append()
            return

        rows = list(page.get("items") or [])
        self._catalog_next_cursor = page.get("next_cursor")
        if append:
            append_anchor = self._catalog_append_scroll_anchor
            self._catalog_append_scroll_anchor = None
            if rows:
                self._catalog_rows.extend(rows)
                self._append_catalog_items_preserving_scroll(rows, append_anchor)
                self._sync_catalog_card_compat_widgets()
                self.schedule_visible_catalog_thumbnails()
            if self._catalog_count_exact:
                self._catalog_count_pending = False
            else:
                self._catalog_count_pending = bool(self._catalog_next_cursor)
                self._catalog_total_count = len(self._catalog_rows)
                self._catalog_count_exact = not self._catalog_count_pending
            self.update_catalog_results_count()
            self._run_deferred_catalog_refresh_after_append()
            return

        self._catalog_count_pending = bool(self._catalog_next_cursor)
        self._catalog_count_exact = not self._catalog_count_pending
        self._catalog_total_count = len(rows)
        signature = (
            self._catalog_total_count,
            self._catalog_next_cursor,
            (
                tuple(
                    (
                        item["video_id"],
                        str(item.get("last_seen_at") or ""),
                        str(item.get("published_at") or ""),
                        str(item.get("source_labels") or ""),
                        str(item.get("audio_language_count") or ""),
                        str(item.get("is_favorite") or ""),
                        str(item.get("dub_kind") or ""),
                    )
                    for item in rows
                )
            ),
        )
        signature_changed = signature != self._last_catalog_signature
        was_dirty = self._catalog_dirty
        self._catalog_rows = rows
        self._last_catalog_signature = signature
        self._catalog_dirty = False
        if was_dirty or signature_changed or not self.catalog_grid_host.isVisible() or not self.catalog_controls_shell.isVisible():
            self.update_catalog_surface()
        else:
            self.render_catalog_cards()
        self._restore_catalog_scroll_anchor_if_needed(generation)
        if self._catalog_count_pending and self.should_count_catalog_exactly(dict(self._catalog_filter_state)):
            self.start_catalog_count_worker(generation, dict(self._catalog_filter_state))

    def _run_deferred_catalog_refresh_after_append(self) -> None:
        if not self._catalog_refresh_deferred_after_append or self._closing:
            return
        self._catalog_refresh_deferred_after_append = False
        QTimer.singleShot(0, self.refresh_catalog)

    def should_count_catalog_exactly(self, filters: dict[str, Any]) -> bool:
        total_videos = int(self._latest_stats.get("total_videos") or 0)
        if total_videos <= CATALOG_BACKGROUND_COUNT_MAX_VIDEOS:
            return True
        return bool(
            filters.get("query")
            or filters.get("source_id")
            or filters.get("channel")
            or filters.get("only_favorites")
            or filters.get("year")
            or filters.get("year_after")
            or filters.get("year_before")
            or filters.get("max_duration_seconds")
        )

    def start_catalog_count_worker(self, generation: int, filters: dict[str, Any]) -> None:
        def worker() -> None:
            try:
                count = self.controller.count_catalog(
                    lang=filters["lang"],
                    source_id=filters["source_id"],
                    channel=filters["channel"],
                    query=filters["query"],
                    only_dubbed=filters["only_dubbed"],
                    only_favorites=filters["only_favorites"],
                    dub_kind=filters["dub_kind"],
                    year=filters["year"],
                    year_after=filters["year_after"],
                    year_before=filters["year_before"],
                    max_duration_seconds=filters["max_duration_seconds"],
                )
            except Exception:
                return
            self.catalogCountReady.emit(generation, count)

        self._catalog_count_threads = [thread for thread in self._catalog_count_threads if thread.is_alive()]
        thread = threading.Thread(target=worker, daemon=True, name=f"catalog-count-{generation}")
        self._catalog_count_threads.append(thread)
        thread.start()

    def handle_catalog_count_ready(self, generation: int, count: int) -> None:
        if generation != self._catalog_query_generation:
            return
        self._catalog_total_count = count
        self._catalog_count_pending = False
        self._catalog_count_exact = True
        self.update_catalog_results_count()

    def load_next_catalog_page(self) -> None:
        if self._suppress_next_catalog_near_bottom:
            self._suppress_next_catalog_near_bottom = False
            return
        if self._catalog_loading_page or not self._catalog_next_cursor:
            return
        if self._current_page_key != "catalog":
            return
        self._catalog_append_scroll_anchor = self._capture_catalog_scroll_anchor()
        self._catalog_loading_page = True
        self._catalog_loading_append = True
        generation = self._catalog_query_generation
        filters = dict(self._catalog_filter_state)
        cursor = self._catalog_next_cursor
        self.start_catalog_page_worker(generation, filters, cursor=cursor, append=True, page_size=CATALOG_PAGE_SIZE)

    def start_metadata_backfill_if_needed(self) -> None:
        if self._metadata_backfill_loading or self._closing:
            return
        self._metadata_backfill_loading = True

        def worker() -> None:
            payload: dict[str, Any]
            try:
                run_id = None
                if self.controller.count_videos_missing_metadata() > 0:
                    run_id = self.controller.start_metadata_backfill(
                        limit=int(getattr(self.services.settings, "startup_metadata_backfill_limit", 80))
                    )
                payload = {"run_id": run_id}
            except Exception as exc:
                payload = {"error": humanize_exception(exc)}
            self.metadataBackfillReady.emit(payload)

        self._metadata_backfill_threads = [
            thread for thread in self._metadata_backfill_threads if thread.is_alive()
        ]
        thread = threading.Thread(target=worker, daemon=True, name="metadata-backfill-check")
        self._metadata_backfill_threads.append(thread)
        thread.start()

    def handle_metadata_backfill_ready(self, payload: dict[str, Any]) -> None:
        self._metadata_backfill_threads = [
            thread for thread in self._metadata_backfill_threads if thread.is_alive()
        ]
        self._metadata_backfill_loading = False
        if self._closing:
            return
        error = payload.get("error")
        if error:
            self.statusBar().showMessage(str(error), 6000)
            return
        run_id = payload.get("run_id")
        if run_id is None:
            return
        self.statusBar().showMessage("Actualizando datos de videos ya encontrados", 4000)
        self.request_summary_refresh()

    def render_catalog_cards_if_visible(self) -> None:
        if self._current_page_key != "catalog":
            self._catalog_dirty = True
            return
        self.render_catalog_cards()

    def render_catalog_cards(self) -> None:
        if not hasattr(self, "catalog_model"):
            return

        self._catalog_render_token += 1
        self.update_catalog_results_count()
        self.configure_catalog_view()
        self.catalog_model.set_items(self._catalog_rows)
        self._sync_catalog_card_compat_widgets()
        if not self._catalog_rows:
            self.catalog_view.setVisible(False)
            self.catalog_grid_host.setStyleSheet(
                """
                QWidget#catalogGridHost {
                    background: #111820;
                    border: 1px solid #161f29;
                    border-radius: 10px;
                }
                """
            )
            if not hasattr(self, "catalog_empty_results_label"):
                self.catalog_empty_results_label = QLabel("No hay videos que coincidan con el filtro actual.", self.catalog_grid_host)
                self.catalog_empty_results_label.setStyleSheet("color: #9198a8; font-size: 16px; padding: 28px 8px;")
            self.catalog_empty_results_label.show()
            self.catalog_empty_results_label.setGeometry(20, 20, max(320, self.catalog_grid_host.width() - 40), 80)
            return

        if hasattr(self, "catalog_empty_results_label"):
            self.catalog_empty_results_label.hide()
        self.catalog_grid_host.setStyleSheet("QWidget#catalogGridHost { background: transparent; border: none; }")
        self.catalog_view.setVisible(True)
        self.schedule_visible_catalog_thumbnails()

    def _continue_catalog_card_batch(self) -> None:
        return

    def _sync_catalog_card_compat_widgets(self) -> None:
        for card in self._catalog_card_widgets:
            card.setParent(None)
            card.deleteLater()
        self._catalog_card_widgets = []
        if os.environ.get("DUBINDEX_COMPAT_CARDS") != "1":
            return
        if len(self._catalog_rows) > 300:
            return
        card_width = self.current_catalog_card_width()
        size_mode = self.catalog_card_size.currentText()
        for item in self._catalog_rows:
            card = CatalogCard(item, card_width, size_mode, self.open_catalog_video, self.toggle_catalog_favorite)
            card.setParent(self.catalog_grid_host)
            card.setGeometry(-10000, -10000, 1, 1)
            card.show()
            self._catalog_card_widgets.append(card)

    def schedule_visible_catalog_thumbnails(self) -> None:
        if hasattr(self, "catalog_thumbnail_timer") and not self._closing:
            self.catalog_thumbnail_timer.start()

    def handle_catalog_visible_rows_changed(self) -> None:
        self.schedule_visible_catalog_thumbnails()
        self.pause_background_worker_briefly()

    def pause_background_worker_briefly(self) -> None:
        now = time.monotonic()
        if now - self._last_worker_pause_sent < 0.35:
            return
        self._last_worker_pause_sent = now

        def worker() -> None:
            try:
                self.controller.pause_background(seconds=0.5)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True, name="worker-pause-scroll").start()

    def request_visible_catalog_thumbnails(self) -> None:
        if not hasattr(self, "catalog_view") or not self.catalog_view.isVisible():
            return
        model = self.catalog_model
        if model.rowCount() == 0:
            return
        viewport = self.catalog_view.viewport()
        top = max(0, viewport.rect().top() - viewport.height())
        bottom = viewport.rect().bottom() + viewport.height()
        first = self.catalog_view.indexAt(QPoint(8, max(8, top)))
        last = self.catalog_view.indexAt(QPoint(max(8, viewport.width() - 8), max(8, bottom)))
        first_row = first.row() if first.isValid() else 0
        last_row = last.row() if last.isValid() else min(model.rowCount() - 1, first_row + CATALOG_THUMBNAIL_PREFETCH_ROWS)
        last_row = min(model.rowCount() - 1, max(last_row, first_row + CATALOG_THUMBNAIL_PREFETCH_ROWS))
        target_size = QSize(
            max(96, int(self.catalog_delegate.card_width * THUMBNAIL_RENDER_SCALE)),
            max(54, int(self.catalog_delegate.thumbnail_height() * THUMBNAIL_RENDER_SCALE)),
        )
        generation = self._catalog_query_generation
        visible_urls: set[str] = set()
        allowed_keys: set[tuple[str, int, int]] = set()
        rows_to_request: list[tuple[str, list[str]]] = []
        for row in range(first_row, last_row + 1):
            item = model.item_at(row)
            if not item:
                continue
            stored_url = str(item.get("thumbnail_url") or "")
            candidates = youtube_thumbnail_candidates(str(item.get("video_id") or ""), stored_url)
            if not candidates:
                continue
            primary_url = stored_url or candidates[0]
            if not stored_url:
                model.set_thumbnail_url(row, primary_url)
            visible_urls.add(primary_url)
            for url in candidates:
                allowed_keys.add((url, max(1, target_size.width()), max(1, target_size.height())))
            rows_to_request.append((primary_url, candidates))
        self._catalog_visible_thumbnail_urls = visible_urls
        if hasattr(self.thumbnail_service, "prune_pending"):
            self.thumbnail_service.prune_pending(allowed_keys)
        for primary_url, candidates in rows_to_request:
            self.thumbnail_service.request_with_fallbacks(
                candidates,
                target_size,
                lambda pixmap, url=primary_url, generation=generation: self.apply_catalog_thumbnail(
                    url, pixmap, generation
                ),
            )

    def apply_catalog_thumbnail(self, url: str, pixmap: QPixmap, generation: int) -> None:
        if generation != self._catalog_query_generation or pixmap.isNull():
            return
        if self._catalog_visible_thumbnail_urls and url not in self._catalog_visible_thumbnail_urls:
            return
        self._catalog_pending_thumbnail_pixmaps[url] = pixmap
        if hasattr(self, "catalog_thumbnail_apply_timer") and not self.catalog_thumbnail_apply_timer.isActive():
            self.catalog_thumbnail_apply_timer.start()

    def flush_catalog_thumbnail_updates(self) -> None:
        if not self._catalog_pending_thumbnail_pixmaps or self._closing:
            return
        pixmaps = dict(self._catalog_pending_thumbnail_pixmaps)
        self._catalog_pending_thumbnail_pixmaps.clear()
        if self._catalog_visible_thumbnail_urls:
            pixmaps = {
                url: pixmap
                for url, pixmap in pixmaps.items()
                if url in self._catalog_visible_thumbnail_urls
            }
        self.catalog_model.set_thumbnails_batch(pixmaps)

    def update_catalog_results_count(self) -> None:
        if self._catalog_count_pending and self._catalog_next_cursor:
            visible_count = max(len(self._catalog_rows), self._catalog_total_count)
            self.catalog_results_count.setText(f"{visible_count}+ encontrados")
            return
        self.catalog_results_count.setText(f"{self._catalog_total_count} encontrados")

    def open_catalog_video(self, item: dict[str, Any]) -> None:
        QDesktopServices.openUrl(QUrl(f"https://www.youtube.com/watch?v={item['video_id']}"))

    def toggle_catalog_favorite(self, item: dict[str, Any], is_favorite: bool) -> None:
        video_id = str(item["video_id"])
        previous_value = bool(item.get("is_favorite"))
        self._favorite_action_versions[video_id] = self._favorite_action_versions.get(video_id, 0) + 1
        version = self._favorite_action_versions[video_id]
        self._set_catalog_favorite_local(video_id, is_favorite)

        def action() -> None:
            self.controller.set_video_favorite(video_id, is_favorite)

        def on_success(_result: Any) -> None:
            if self._favorite_action_versions.get(video_id) != version:
                return
            if self.catalog_favorites_only.isChecked():
                self.refresh_catalog()

        def on_error(exc: Exception) -> None:
            if self._favorite_action_versions.get(video_id) == version:
                self._set_catalog_favorite_local(video_id, previous_value)
            self.show_error("No se pudo actualizar el favorito", exc)

        self._run_ui_action_async(
            "catalog-favorite",
            action,
            on_success=on_success,
            on_error=on_error,
            busy_widgets=[],
        )
        return

    def _set_catalog_favorite_local(self, video_id: str, is_favorite: bool) -> None:
        for row in self._catalog_rows:
            if str(row.get("video_id")) == video_id:
                row["is_favorite"] = 1 if is_favorite else 0
        if hasattr(self, "catalog_model"):
            self.catalog_model.set_favorite(video_id, is_favorite)

    def _tick_refresh(self) -> None:
        self._drain_worker_events()
        active_run_id = self.controller.active_run_id()
        if active_run_id is not None:
            if self._last_active_run_id is None:
                self._last_active_run_id = active_run_id
                self.request_summary_refresh()
            else:
                self.request_active_run_snapshot(active_run_id)
            return

        if self._last_active_run_id is not None:
            self._last_active_run_id = None
            self.request_summary_refresh()
            if self._current_page_key == "catalog":
                self.refresh_catalog()
            else:
                self._catalog_dirty = True

    def _drain_worker_events(self) -> None:
        worker_client = getattr(self.services, "worker_client", None)
        if worker_client is None or not hasattr(worker_client, "drain_events"):
            return
        try:
            events = worker_client.drain_events(limit=100)
        except Exception:
            return
        if not events or self._closing:
            return
        catalog_changed = False
        summary_dirty = False
        for event in events:
            event_name = str(event.get("event") or "")
            if event_name == "catalog_changed":
                catalog_changed = True
                summary_dirty = True
            elif event_name == "run_started":
                self._active_run_progress = dict(event)
                summary_dirty = True
            elif event_name == "run_progress":
                self.apply_run_progress_event(event)
                summary_dirty = True
            elif event_name == "run_finished":
                self._active_run_progress = None
                summary_dirty = True
            elif event_name == "discovery_progress":
                self._active_discovery_progress = dict(event)
                self.apply_discovery_progress(event)
                summary_dirty = True
            elif event_name == "discovery_finished":
                self._active_discovery_progress = None
                summary_dirty = True
            elif event_name == "summary_dirty":
                summary_dirty = True
        if summary_dirty:
            self.request_summary_refresh()
        if catalog_changed:
            if self._current_page_key == "catalog":
                self.refresh_catalog()
            else:
                self._catalog_dirty = True

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_sources_layout()
        if hasattr(self, "catalog_relayout_timer"):
            if self._current_page_key == "catalog":
                self.catalog_relayout_timer.start()
            else:
                self._catalog_dirty = True

    def closeEvent(self, event: Any) -> None:  # type: ignore[override]
        self._closing = True
        self._catalog_scroll_restore_token += 1
        self._stop_catalog_scroll_range_restore()
        self._catalog_render_token += 1
        self._catalog_batch_state = None
        for timer_name in (
            "catalog_relayout_timer",
            "catalog_page_refresh_timer",
            "catalog_batch_timer",
            "catalog_thumbnail_timer",
            "catalog_thumbnail_apply_timer",
            "startup_backfill_timer",
            "timer",
        ):
            timer = getattr(self, timer_name, None)
            if timer is not None:
                timer.stop()
        if self.services.discovery_loop is not None:
            self.services.discovery_loop.stop()
        if self.services.worker_client is not None and hasattr(self.services.worker_client, "stop"):
            self.services.worker_client.stop(wait=False)
        if self._ui_jank_probe is not None:
            self._ui_jank_probe.stop()
        if hasattr(self, "thumbnail_service"):
            self.thumbnail_service.shutdown()
        self._catalog_filter_threads = [thread for thread in self._catalog_filter_threads if thread.is_alive()]
        self._catalog_page_threads = [thread for thread in self._catalog_page_threads if thread.is_alive()]
        self._summary_refresh_threads = [
            thread for thread in self._summary_refresh_threads if thread.is_alive()
        ]
        self._catalog_count_threads = [thread for thread in self._catalog_count_threads if thread.is_alive()]
        self._active_run_snapshot_threads = [
            thread for thread in self._active_run_snapshot_threads if thread.is_alive()
        ]
        self._manual_discovery_threads = [thread for thread in self._manual_discovery_threads if thread.is_alive()]
        self._interest_discovery_threads = [
            thread for thread in self._interest_discovery_threads if thread.is_alive()
        ]
        self._metadata_backfill_threads = [
            thread for thread in self._metadata_backfill_threads if thread.is_alive()
        ]
        self._update_threads = [thread for thread in self._update_threads if thread.is_alive()]
        self._ui_action_threads = [thread for thread in self._ui_action_threads if thread.is_alive()]
        super().closeEvent(event)

    def show_error(self, title: str, error: Exception) -> None:
        QMessageBox.critical(self, title, humanize_exception(error))

    def show_info(self, message: str) -> None:
        QMessageBox.information(self, "Aviso", message)


def launch_app(controller: AppController, services: DesktopServices) -> int:
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(APP_STYLE)
    window = MainWindow(controller, services)
    window.show()
    return app.exec()

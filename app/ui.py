from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
import os
import threading
from typing import Any, Callable

from PySide6.QtCore import QAbstractListModel, QModelIndex, QPoint, QRect, QSize, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontMetrics, QMouseEvent, QPainter, QPixmap, QResizeEvent
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
QLineEdit[compactCatalog="true"], QComboBox[compactCatalog="true"] {
    padding: 6px 12px;
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
    padding-right: 28px;
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


def make_year_combo(empty_text: str) -> QComboBox:
    combo = QComboBox()
    combo.setEditable(False)
    combo.addItem(empty_text, None)
    current_year = datetime.now().year
    for year in range(current_year, YOUTUBE_FIRST_YEAR - 1, -1):
        combo.addItem(str(year), year)
    style_combo_popup(combo)
    combo.setMaxVisibleItems(14)
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
        self.beginResetModel()
        self.items = list(items)
        self.endResetModel()

    def append_items(self, items: list[dict[str, Any]]) -> None:
        if not items:
            return
        start = len(self.items)
        self.beginInsertRows(QModelIndex(), start, start + len(items) - 1)
        self.items.extend(items)
        self.endInsertRows()

    def set_thumbnail(self, url: str, pixmap: QPixmap) -> None:
        self._pixmaps[url] = pixmap
        changed_rows = [
            row
            for row, item in enumerate(self.items)
            if str(item.get("thumbnail_url") or "") == url
        ]
        for row in changed_rows:
            index = self.index(row, 0)
            self.dataChanged.emit(index, index, [CATALOG_PIXMAP_ROLE])

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

    def configure(self, card_width: int, size_mode: str) -> None:
        self.card_width = max(200, int(card_width))
        self.size_mode = size_mode
        thumb_height = self.thumbnail_height()
        body_height = 162 if size_mode != "Compacto" else 138
        self.card_height = thumb_height + body_height

    def thumbnail_height(self) -> int:
        minimum = 128 if self.size_mode == "Compacto" else 164
        return max(minimum, round(self.card_width * 9 / 16))

    def sizeHint(self, option: Any, index: QModelIndex) -> QSize:  # type: ignore[override]
        return QSize(self.card_width, self.card_height)

    def star_rect(self, item_rect: QRect) -> QRect:
        return QRect(item_rect.right() - 44, item_rect.top() + 10, 34, 34)

    @staticmethod
    def _font(pixel_size: int, *, bold: bool = False) -> QFont:
        font = QFont("Segoe UI")
        font.setPixelSize(pixel_size)
        font.setBold(bold)
        return font

    @staticmethod
    def _elided_lines(text: str, font_metrics: QFontMetrics, width: int, max_lines: int) -> list[str]:
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
        metrics = QFontMetrics(font)
        line_height = metrics.lineSpacing()
        lines = self._elided_lines(text, metrics, rect.width(), max_lines)
        for offset, line in enumerate(lines):
            line_rect = QRect(rect.left(), rect.top() + offset * line_height, rect.width(), line_height)
            painter.drawText(
                line_rect,
                Qt.TextFlag.TextSingleLine | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                line,
            )
        return max(1, len(lines)) * line_height

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
            scaled = pixmap.scaled(
                thumb_rect.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = thumb_rect.left() + (thumb_rect.width() - scaled.width()) // 2
            y = thumb_rect.top() + (thumb_rect.height() - scaled.height()) // 2
            painter.setClipRect(thumb_rect)
            painter.drawPixmap(x, y, scaled)
            painter.setClipping(False)
        else:
            painter.setPen(QColor("#758091"))
            painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, "Cargando thumbnail")

        duration = format_duration(item.get("duration_seconds"))
        if duration:
            font = self._font(14, bold=True)
            painter.setFont(font)
            fm = QFontMetrics(font)
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
        content_top = thumb_rect.bottom() + (15 if self.size_mode != "Compacto" else 12)
        title_font = self._font(18 if self.size_mode != "Compacto" else 16, bold=True)
        title_metrics = QFontMetrics(title_font)
        max_title_lines = 3 if self.size_mode != "Compacto" else 2
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

        channel_font = self._font(15 if self.size_mode != "Compacto" else 13)
        painter.setFont(channel_font)
        painter.setPen(QColor("#a2abb9"))
        channel_metrics = QFontMetrics(channel_font)
        channel_top = content_top + used_title_height + 8
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

        meta_font = self._font(14 if self.size_mode != "Compacto" else 12)
        painter.setFont(meta_font)
        painter.setPen(QColor("#a0a8b5"))
        meta_metrics = QFontMetrics(meta_font)
        meta_top = min(
            channel_rect.bottom() + 9,
            card_rect.bottom() - meta_metrics.lineSpacing() - 16,
        )
        meta_rect = QRect(left, meta_top, right - left - 28, meta_metrics.lineSpacing())
        meta_text = format_published_date(item.get("published_at")) or "Fecha desconocida"
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
        self.setUniformItemSizes(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSpacing(16)
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
        self.setGridSize(QSize(card_width + self.spacing(), card_height + self.spacing()))
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

    def _handle_scroll(self, value: int) -> None:
        bar = self.verticalScrollBar()
        if bar.maximum() - value < max(240, self.height()):
            self.nearBottom.emit()
        self.visibleRowsChanged.emit()


class ThumbnailService:
    def __init__(self, owner: QWidget, cache_dir: Any, *, max_memory_bytes: int = 128 * 1024 * 1024) -> None:
        self.owner = owner
        self.max_memory_bytes = max_memory_bytes
        self._memory_bytes = 0
        self._cache: OrderedDict[tuple[str, int, int], QPixmap] = OrderedDict()
        self._inflight: dict[tuple[str, int, int], list[Callable[[QPixmap], None]]] = {}
        self.manager = QNetworkAccessManager(owner)
        self.disk_cache = QNetworkDiskCache(owner)
        self.disk_cache.setCacheDirectory(str(cache_dir))
        self.disk_cache.setMaximumCacheSize(2 * 1024 * 1024 * 1024)
        self.manager.setCache(self.disk_cache)

    def request(self, url: str, target_size: QSize, callback: Callable[[QPixmap], None]) -> None:
        if not url:
            return
        key = (url, max(1, target_size.width()), max(1, target_size.height()))
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            QTimer.singleShot(0, lambda pixmap=cached: callback(pixmap))
            return
        if key in self._inflight:
            self._inflight[key].append(callback)
            return
        self._inflight[key] = [callback]
        reply = self.manager.get(QNetworkRequest(QUrl(url)))
        reply.finished.connect(lambda reply=reply, key=key: self._finish(reply, key))

    def _finish(self, reply: QNetworkReply, key: tuple[str, int, int]) -> None:
        callbacks = self._inflight.pop(key, [])
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                return
            pixmap = QPixmap()
            if not pixmap.loadFromData(reply.readAll().data()):
                return
            target = QSize(key[1], key[2])
            scaled = pixmap.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._remember(key, scaled)
            for callback in callbacks:
                callback(scaled)
        finally:
            reply.deleteLater()

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
    manualDiscoveryReady = Signal(dict)
    interestDiscoveryReady = Signal(dict)

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
        self._catalog_loading_page = False
        self._catalog_query_generation = 0
        self._current_page_key: str | None = None
        self._catalog_dirty = True
        self._catalog_filters_dirty = True
        self._catalog_filters_generation = 0
        self._catalog_filters_loading = False
        self._catalog_filter_threads: list[threading.Thread] = []
        self._manual_discovery_threads: list[threading.Thread] = []
        self._interest_discovery_threads: list[threading.Thread] = []
        self._manual_discovery_running = False
        self._interest_discovery_active = 0
        self._catalog_has_manual_interest = False
        self._catalog_render_token = 0
        self._catalog_row_stretch_index: int | None = None
        self._catalog_layout_signature: tuple[Any, ...] | None = None
        self._catalog_batch_state: tuple[int, int, int, int, str] | None = None
        self._thumbnail_scaled_pixmaps: dict[tuple[str, int, int], QPixmap] = {}
        self.topbar_quick_input: QLineEdit | None = None
        self._sources_layout_mode: str | None = None
        self._closing = False

        self.setWindowTitle(services.settings.app_title or " ")
        self.catalogCountReady.connect(self.handle_catalog_count_ready)
        self.catalogFiltersReady.connect(self.handle_catalog_filters_ready)
        self.manualDiscoveryReady.connect(self.handle_manual_discovery_ready)
        self.interestDiscoveryReady.connect(self.handle_interest_discovery_ready)
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

        shell_layout.addStretch(1)

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
        self.metric_last_run = MetricCard("Última búsqueda", icon_text="⏱", icon_bg="#14293e")
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

        self.catalog_lang = QComboBox()
        self.catalog_lang.setProperty("compactCatalog", "true")
        self.catalog_lang.addItem("Todos los idiomas", "")
        self.catalog_lang.addItem("Español", SPANISH_LANGUAGE_FILTER)
        self.catalog_lang.setCurrentIndex(1)
        self.catalog_lang.setMinimumWidth(200)
        self.catalog_lang.setMinimumHeight(36)
        self.catalog_lang.setMaximumHeight(36)

        self.catalog_channel = QComboBox()
        self.catalog_channel.addItem("Todos los canales", "")
        self.catalog_channel.setMinimumWidth(220)

        self.catalog_source = QComboBox()
        self.catalog_source.addItem("Todos los intereses", None)
        self.catalog_source.setMinimumWidth(220)

        self.catalog_visibility = QComboBox()
        self.catalog_visibility.addItem("Solo doblados", True)
        self.catalog_visibility.addItem("Todos los videos revisados", False)
        self.catalog_visibility.setMinimumWidth(220)

        self.catalog_dub_kind = QComboBox()
        self.catalog_dub_kind.addItem("Todos los dubs", "")
        self.catalog_dub_kind.addItem("IA", "automatic")
        self.catalog_dub_kind.addItem("No IA", "manual")
        self.catalog_dub_kind.setMinimumWidth(180)

        self.catalog_sort = QComboBox()
        self.catalog_sort.setProperty("compactCatalog", "true")
        self.catalog_sort.addItem("Más recientes", "recent")
        self.catalog_sort.addItem("Más antiguos", "oldest")
        self.catalog_sort.addItem("Más vistos", "views")
        self.catalog_sort.addItem("Random", "random")
        self.catalog_sort.setMinimumWidth(170)
        self.catalog_sort.setMinimumHeight(36)
        self.catalog_sort.setMaximumHeight(36)

        self.catalog_year = make_year_combo("Cualquier año")
        self.catalog_year.setMinimumWidth(180)

        self.catalog_after_year = make_year_combo("Sin fecha mínima")
        self.catalog_after_year.setMinimumWidth(180)

        self.catalog_before_year = make_year_combo("Sin fecha máxima")
        self.catalog_before_year.setMinimumWidth(180)
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
        self.catalog_manual_discovery_button = QPushButton("Explorar 50")
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
        filters_layout.addWidget(inline_field("Canal", self.catalog_channel), 0, 0)
        filters_layout.addWidget(inline_field("Búsqueda", self.catalog_source), 0, 1)
        filters_layout.addWidget(inline_field("Mostrar", self.catalog_visibility), 0, 2)
        filters_layout.addWidget(inline_field("Año de subida", self.catalog_year), 0, 3)
        filters_layout.addWidget(inline_field("Subidos desde", self.catalog_after_year), 1, 0)
        filters_layout.addWidget(inline_field("Subidos hasta", self.catalog_before_year), 1, 1)
        filters_layout.addWidget(inline_field("Tipo de dub", self.catalog_dub_kind), 1, 2)
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
        self.catalog_view.visibleRowsChanged.connect(self.request_visible_catalog_thumbnails)
        catalog_grid_layout.addWidget(self.catalog_view)
        layout.addWidget(self.catalog_grid_host, 1)

        for combo in (
            self.catalog_lang,
            self.catalog_source,
            self.catalog_channel,
            self.catalog_visibility,
            self.catalog_dub_kind,
            self.catalog_sort,
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
        self.statusBar().showMessage("Explorando 50 videos recomendados", 4000)

        def worker() -> None:
            payload: dict[str, Any]
            try:
                payload = {"summary": self.controller.run_manual_feed_expansion(candidate_limit=50)}
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
        self.catalog_manual_discovery_button.setText("Explorar 50")
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
        self.refresh_catalog_filters()
        self.refresh_catalog()
        self.refresh_dashboard()

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
        self.refresh_catalog_filters()
        self.refresh_catalog()
        self.refresh_dashboard()

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
            return
        self.source_toggle_button.setText(
            "Pausar" if single_source["enabled"] else "Reactivar"
        )

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
        if latest_run:
            self.metric_last_run.set_value(
                relative_time(latest_run.get("finished_at") or latest_run.get("started_at"))
            )
        else:
            self.metric_last_run.set_value("—")

    def submit_quick_source(self, field: QLineEdit) -> None:
        raw_value = field.text().strip()
        if not raw_value:
            self.show_info("Pega un canal o escribe una búsqueda.")
            return

        try:
            seed_payload = self.controller.submit_interest(raw_value)
            for f in (self.catalog_empty_input, self.topbar_quick_input, self.dashboard_quick_input):
                if f is not None:
                    f.clear()
            self._catalog_has_manual_interest = True
            self.statusBar().showMessage("Interes guardado. Buscando 150 candidatos iniciales.", 4000)
            self.refresh_sources()
            self.refresh_runs()
            self.refresh_dashboard()
            self.switch_page("catalog")
            self.refresh_catalog()
            if hasattr(self, "catalog_empty_stack"):
                self.catalog_empty_stack.setCurrentIndex(1)
            self.start_interest_initial_discovery(int(seed_payload["seed_id"]))
        except Exception as exc:
            self.show_error("No se pudo guardar el interes", exc)

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

            if source:
                source_id = int(source["id"])
                self.controller.update_source(source_id, **payload)
                saved_message = f"Búsqueda #{source_id} actualizada"
            else:
                source_id = self.controller.create_source(**payload)
                saved_message = f"Búsqueda #{source_id} guardada"
            self.controller.set_last_max_candidates(int(self.source_max_candidates.value()))
            self.reset_source_form()
            self.refresh_sources()
            self.refresh_dashboard()
            if bool(payload["enabled"]):
                try:
                    self.controller.run_source(source_id)
                except Exception as exc:
                    self.refresh_runs()
                    self.refresh_dashboard()
                    self.refresh_catalog()
                    self.statusBar().showMessage(saved_message, 4000)
                    self.show_error("Se guardó, pero no pudo empezar la revisión automática", exc)
                    return
                self.statusBar().showMessage(f"{saved_message}. Revisando videos.", 4000)
                self.refresh_runs()
                self.refresh_dashboard()
                self.refresh_catalog()
            else:
                self.statusBar().showMessage(saved_message, 4000)
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

        try:
            self.controller.delete_sources(
                [int(source["id"]) for source in selected],
                delete_videos=delete_videos,
            )
            if delete_videos:
                self.statusBar().showMessage("Busquedas y videos guardados borrados", 4000)
            else:
                self.statusBar().showMessage("Busquedas borradas. Videos conservados.", 4000)
            self.reset_source_form()
            self.refresh_sources()
            self.refresh_dashboard()
            self.refresh_catalog()
        except Exception as exc:
            self.show_error("No se pudieron borrar las busquedas", exc)

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
            self.controller.toggle_source(source["id"])
            self.refresh_sources()
            self.refresh_dashboard()
            state = "pausada" if source["enabled"] else "reactivada"
            self.statusBar().showMessage(f"Búsqueda {state}: {source['label']}", 4000)
        except Exception as exc:
            self.show_error("No se pudo cambiar el estado de la búsqueda", exc)

    def increase_full_source_limits(self, *_args: object) -> None:
        try:
            changed = self.controller.increase_full_source_limits(500)
            self.refresh_sources()
            self.refresh_dashboard()
            if changed:
                self.statusBar().showMessage(
                    f"Límite aumentado en 500 para {changed} fuente{'s' if changed != 1 else ''}",
                    4000,
                )
            else:
                self.statusBar().showMessage("No hay fuentes llenas", 4000)
        except Exception as exc:
            self.show_error("No se pudo aumentar el límite", exc)

    def run_selected_source(self, *_args: object) -> None:
        source = self.selected_source()
        if not source:
            self.show_info("Selecciona una búsqueda primero.")
            return
        try:
            self.controller.run_source(source["id"])
            self.statusBar().showMessage(f"Búsqueda iniciada para “{source['label']}”", 4000)
            self.refresh_runs()
            self.refresh_dashboard()
            self.refresh_catalog()
        except Exception as exc:
            self.show_error("No se pudo iniciar la búsqueda", exc)

    def handle_run_all(self, *_args: object) -> None:
        try:
            self.controller.run_all()
            self.statusBar().showMessage("Búsqueda iniciada para todas tus búsquedas activas", 4000)
            self.refresh_runs()
            self.refresh_dashboard()
            self.refresh_catalog()
        except Exception as exc:
            self.show_error("No se pudo iniciar la búsqueda general", exc)

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
        active_run = self.controller.active_run_snapshot()
        source_lookup = {int(source["id"]): source["label"] for source in self._source_rows}
        if active_run:
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

        self.topbar_progress.hide()
        latest_run = self._latest_stats.get("latest_run")
        if latest_run:
            when = relative_time(latest_run.get("finished_at") or latest_run.get("started_at"))
            self.topbar_status_label.setText(f"Última búsqueda: {when}")
        else:
            self.topbar_status_label.setText("Aún no has buscado videos")

    def refresh_all(self, *_args: object) -> None:
        self.refresh_sources()
        self.refresh_dashboard()
        self.refresh_runs()
        self._catalog_dirty = True
        if self._current_page_key == "catalog":
            self.refresh_catalog()

    def refresh_dashboard(self, *_args: object) -> None:
        stats = self.controller.dashboard_stats()
        self._latest_stats = stats
        self.update_topbar_status()
        self._populate_runs_table(self.latest_runs_table, self.controller.list_runs(limit=5), "latest")
        self._update_dashboard_stats(stats)

    def refresh_sources(self, *_args: object) -> None:
        selected_source_ids = {int(source["id"]) for source in self.selected_sources()}
        self._source_rows = self.controller.list_sources()
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
        self._run_rows = self.controller.list_runs(limit=100)
        self._populate_runs_table(self.runs_table, self._run_rows, "runs")
        self._populate_runs_table(self.sources_recent_runs_table, self._run_rows[:3], "recent")
        self._populate_runs_table(self.sources_full_history_table, self._run_rows, "full")

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
        self._apply_catalog_filters(filters, source_rows)

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
        active_run = self.controller.active_run_snapshot()
        active_discovery = (
            bool(active_run)
            or self._manual_discovery_running
            or self._interest_discovery_active > 0
            or self._catalog_has_manual_interest
        )
        has_videos = total_videos > 0

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
        }

    def refresh_catalog(self, *_args: object) -> None:
        if self._current_page_key != "catalog":
            self._catalog_dirty = True
            return

        filters = self._current_catalog_filters()
        self._catalog_filter_state = filters
        self._catalog_query_generation += 1
        generation = self._catalog_query_generation
        self._catalog_loading_page = False
        self._catalog_next_cursor = None
        self._catalog_count_pending = False
        self._catalog_total_count = 0
        self._catalog_rows = []
        if hasattr(self, "catalog_model"):
            self.catalog_model.set_items([])
            self._sync_catalog_card_compat_widgets()
            self.update_catalog_results_count()
        page = self.controller.list_catalog_page(
            lang=filters["lang"],
            source_id=filters["source_id"],
            channel=filters["channel"],
            query=filters["query"],
            only_dubbed=filters["only_dubbed"],
            only_favorites=filters["only_favorites"],
            dub_kind=filters["dub_kind"],
            sort_by=filters["sort_by"],
            year=filters["year"],
            year_after=filters["year_after"],
            year_before=filters["year_before"],
            page_size=CATALOG_PAGE_SIZE,
            cursor=None,
        )
        rows = list(page["items"])
        self._catalog_next_cursor = page.get("next_cursor")
        self._catalog_count_pending = bool(self._catalog_next_cursor)
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
        if self._catalog_count_pending:
            self.start_catalog_count_worker(generation, filters)

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
                )
            except Exception:
                return
            self.catalogCountReady.emit(generation, count)

        threading.Thread(target=worker, daemon=True, name=f"catalog-count-{generation}").start()

    def handle_catalog_count_ready(self, generation: int, count: int) -> None:
        if generation != self._catalog_query_generation:
            return
        self._catalog_total_count = count
        self._catalog_count_pending = False
        self.update_catalog_results_count()

    def load_next_catalog_page(self) -> None:
        if self._catalog_loading_page or not self._catalog_next_cursor:
            return
        if self._current_page_key != "catalog":
            return
        self._catalog_loading_page = True
        generation = self._catalog_query_generation
        filters = dict(self._catalog_filter_state)
        cursor = self._catalog_next_cursor
        page = self.controller.list_catalog_page(
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
            page_size=CATALOG_PAGE_SIZE,
            cursor=cursor,
        )
        if generation != self._catalog_query_generation:
            self._catalog_loading_page = False
            return
        rows = list(page["items"])
        self._catalog_next_cursor = page.get("next_cursor")
        if rows:
            self._catalog_rows.extend(rows)
            self.catalog_model.append_items(rows)
            self._sync_catalog_card_compat_widgets()
            QTimer.singleShot(0, self.request_visible_catalog_thumbnails)
        self._catalog_loading_page = False

    def start_metadata_backfill_if_needed(self) -> None:
        if self.controller.count_videos_missing_metadata() <= 0:
            return
        run_id = self.controller.start_metadata_backfill(
            limit=int(getattr(self.services.settings, "startup_metadata_backfill_limit", 80))
        )
        if run_id is None:
            return
        self.statusBar().showMessage("Actualizando datos de videos ya encontrados", 4000)
        self.refresh_runs()
        self.refresh_dashboard()

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
        QTimer.singleShot(0, self.request_visible_catalog_thumbnails)

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

    def request_visible_catalog_thumbnails(self) -> None:
        if not hasattr(self, "catalog_view") or not self.catalog_view.isVisible():
            return
        model = self.catalog_model
        if model.rowCount() == 0:
            return
        viewport = self.catalog_view.viewport()
        top = max(0, viewport.rect().top() - viewport.height() * 2)
        bottom = viewport.rect().bottom() + viewport.height() * 2
        first = self.catalog_view.indexAt(QPoint(8, max(8, top)))
        last = self.catalog_view.indexAt(QPoint(max(8, viewport.width() - 8), max(8, bottom)))
        first_row = first.row() if first.isValid() else 0
        last_row = last.row() if last.isValid() else min(model.rowCount() - 1, first_row + 80)
        last_row = min(model.rowCount() - 1, max(last_row, first_row + 80))
        target_size = QSize(self.catalog_delegate.card_width, self.catalog_delegate.thumbnail_height())
        generation = self._catalog_query_generation
        for row in range(first_row, last_row + 1):
            item = model.item_at(row)
            if not item:
                continue
            url = str(item.get("thumbnail_url") or "")
            if not url:
                continue
            self.thumbnail_service.request(
                url,
                target_size,
                lambda pixmap, url=url, generation=generation: self.apply_catalog_thumbnail(url, pixmap, generation),
            )

    def apply_catalog_thumbnail(self, url: str, pixmap: QPixmap, generation: int) -> None:
        if generation != self._catalog_query_generation or pixmap.isNull():
            return
        self.catalog_model.set_thumbnail(url, pixmap)

    def update_catalog_results_count(self) -> None:
        if self._catalog_count_pending and self._catalog_next_cursor:
            visible_count = max(len(self._catalog_rows), self._catalog_total_count)
            self.catalog_results_count.setText(f"{visible_count}+ encontrados")
            return
        self.catalog_results_count.setText(f"{self._catalog_total_count} encontrados")

    def open_catalog_video(self, item: dict[str, Any]) -> None:
        QDesktopServices.openUrl(QUrl(f"https://www.youtube.com/watch?v={item['video_id']}"))

    def toggle_catalog_favorite(self, item: dict[str, Any], is_favorite: bool) -> None:
        self.controller.set_video_favorite(str(item["video_id"]), is_favorite)
        for row in self._catalog_rows:
            if row.get("video_id") == item.get("video_id"):
                row["is_favorite"] = 1 if is_favorite else 0
        if hasattr(self, "catalog_model"):
            self.catalog_model.set_favorite(str(item["video_id"]), is_favorite)
        if self.catalog_favorites_only.isChecked():
            self.refresh_catalog()

    def _tick_refresh(self) -> None:
        active_run_id = self.controller.active_run_id()
        if active_run_id is not None:
            if self._last_active_run_id is None:
                self._last_active_run_id = active_run_id
                self.refresh_runs()
                self.refresh_dashboard()
            else:
                self.update_topbar_status()
            return

        if self._last_active_run_id is not None:
            self._last_active_run_id = None
            self.refresh_sources()
            self.refresh_runs()
            self.refresh_dashboard()
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
        self._catalog_render_token += 1
        self._catalog_batch_state = None
        for timer_name in (
            "catalog_relayout_timer",
            "catalog_page_refresh_timer",
            "catalog_batch_timer",
            "startup_backfill_timer",
            "timer",
        ):
            timer = getattr(self, timer_name, None)
            if timer is not None:
                timer.stop()
        if self.services.discovery_loop is not None:
            self.services.discovery_loop.stop()
        for thread in list(self._catalog_filter_threads):
            if thread.is_alive():
                thread.join(timeout=2.0)
        self._catalog_filter_threads = [thread for thread in self._catalog_filter_threads if thread.is_alive()]
        for thread in list(self._manual_discovery_threads):
            if thread.is_alive():
                thread.join(timeout=2.0)
        self._manual_discovery_threads = [thread for thread in self._manual_discovery_threads if thread.is_alive()]
        for thread in list(self._interest_discovery_threads):
            if thread.is_alive():
                thread.join(timeout=2.0)
        self._interest_discovery_threads = [
            thread for thread in self._interest_discovery_threads if thread.is_alive()
        ]
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

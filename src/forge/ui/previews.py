"""Rendered views of a document: Markdown, CSV table and JSON tree."""

from __future__ import annotations

import importlib.util
import json
import logging
import os
from pathlib import Path

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QStackedWidget,
    QTableView,
    QTextBrowser,
    QWidget,
)

from forge.core.csvtext import detect_delimiter, read_rows
from forge.i18n.translator import tr
from forge.themes.theme import Theme
from forge.ui.markdown_render import basic_css, basic_html
from forge.widgets.json_tree import JsonTree

log = logging.getLogger(__name__)
CODE_FONT = "JetBrains Mono"

# Larger documents are not rendered (the text view stays fast).
MAX_PREVIEW_CHARS = 20_000_000
PREVIEW_LANGUAGES = ("markdown", "csv", "json")


class Preview(QStackedWidget):
    """A rendered view plus a message page for errors."""

    # CSV: set by the document page from the editor (chosen or detected).
    delimiter: str | None = None

    def __init__(self, view: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("documentPreview")
        self.view = view
        self.message = QLabel(self)
        self.message.setObjectName("previewMessage")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)
        self.addWidget(view)
        self.addWidget(self.message)

    def show_message(self, text: str) -> None:
        self.message.setText(text)
        self.setCurrentWidget(self.message)

    def show_view(self) -> None:
        self.setCurrentWidget(self.view)

    def show_document(self, text: str, path: Path | None) -> None:
        raise NotImplementedError

    def apply_theme(self, theme: Theme) -> None:
        """Most previews follow the application palette and stylesheet."""

    def scroll_to_ratio(self, ratio: float) -> None:
        """Keep the preview roughly in step with the editor (split view)."""


class MarkdownPreview(Preview):
    """Basic Markdown preview with Qt's rich text engine (always available)."""

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        self.browser = QTextBrowser()
        self.browser.setObjectName("markdownPreview")
        self.browser.setOpenExternalLinks(True)
        document = self.browser.document()
        if document is not None:
            document.setDocumentMargin(24)
        super().__init__(self.browser, parent)
        self.apply_theme(theme)

    def apply_theme(self, theme: Theme) -> None:
        document = self.browser.document()
        if document is not None:
            document.setDefaultStyleSheet(basic_css(theme, CODE_FONT))

    def show_document(self, text: str, path: Path | None) -> None:
        bar = self.browser.verticalScrollBar()
        position = bar.value() if bar is not None else 0
        if path is not None:
            self.browser.setSearchPaths([str(path.parent)])
        self.browser.setHtml(
            basic_html(text, tr("Install the web extra to draw Mermaid diagrams."))
        )
        if bar is not None:
            bar.setValue(position)
        self.show_view()

    def scroll_to_ratio(self, ratio: float) -> None:
        bar = self.browser.verticalScrollBar()
        if bar is not None:
            bar.setValue(int(bar.maximum() * ratio))


class CsvModel(QAbstractTableModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._header: list[str] = []
        self._rows: list[list[str]] = []

    def set_rows(self, rows: list[list[str]]) -> None:
        self.beginResetModel()
        self._header = rows[0] if rows else []
        self._rows = rows[1:] if rows else []
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        if parent.isValid():
            return 0
        widest = max((len(row) for row in self._rows[:1000]), default=0)
        return max(len(self._header), widest)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return None
        row = self._rows[index.row()]
        return row[index.column()] if index.column() < len(row) else ""

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self._header[section] if section < len(self._header) else str(section + 1)
        return str(section + 2)  # file line number of the row (line 1 is the header)


class CsvPreview(Preview):
    def __init__(self, parent: QWidget | None = None) -> None:
        self.table = QTableView()
        self.table.setObjectName("csvTable")
        self.model = CsvModel(self.table)
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        super().__init__(self.table, parent)

    def show_document(self, text: str, path: Path | None) -> None:
        default = "\t" if path is not None and path.suffix.lower() in (".tsv", ".tab") else ","
        delimiter = self.delimiter or detect_delimiter(text[:20_000], default)
        self.model.set_rows(read_rows(text, delimiter))
        self.table.resizeColumnsToContents()
        self.show_view()


class JsonPreview(Preview):
    def __init__(self, parent: QWidget | None = None) -> None:
        self.tree = JsonTree()
        super().__init__(self.tree, parent)

    def show_document(self, text: str, path: Path | None) -> None:
        if not text.strip():
            self.show_message(tr("The document is empty."))
            return
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            self.show_message(
                tr("Invalid JSON at line {line}: {error}", line=exc.lineno, error=exc.msg)
            )
            return
        self.tree.show_data(data)
        self.show_view()


def rich_markdown_available() -> bool:
    """True when the optional Qt WebEngine is installed (``uv sync --extra web``).

    Set FORGE_BASIC_MARKDOWN=1 to use the basic preview anyway."""
    if os.environ.get("FORGE_BASIC_MARKDOWN"):
        return False
    return importlib.util.find_spec("PyQt6.QtWebEngineWidgets") is not None


def create_preview(language_id: str, theme: Theme) -> Preview | None:
    if language_id == "markdown":
        if rich_markdown_available():
            try:
                from forge.ui.web_preview import WebMarkdownPreview

                return WebMarkdownPreview(theme)
            except Exception:
                log.exception("Rich Markdown preview failed; using the basic preview")
        return MarkdownPreview(theme)
    if language_id == "csv":
        return CsvPreview()
    if language_id == "json":
        return JsonPreview()
    return None

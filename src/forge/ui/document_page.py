"""A tab page: the editor, optionally next to (or replaced by) a rendered view."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from forge.themes.theme import Theme
from forge.ui.document_tab import DocumentTab
from forge.ui.document_toolbar import (
    PREVIEW,
    SPLIT,
    TEXT,
    VIEW_MODES,
    DocumentToolbar,
    ToolItem,
)
from forge.ui.previews import MAX_PREVIEW_CHARS, PREVIEW_LANGUAGES, Preview, create_preview

__all__ = ["PREVIEW", "SPLIT", "TEXT", "VIEW_MODES", "DocumentPage"]

REFRESH_DELAY_MS = 350
ToolProvider = Callable[[DocumentTab], list[ToolItem]]


class DocumentPage(QWidget):
    def __init__(
        self,
        editor: DocumentTab,
        theme: Theme,
        tools: ToolProvider | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("documentPage")
        self.editor = editor
        self._theme = theme
        self.mode = TEXT
        self.preview: Preview | None = None
        self._preview_language = ""
        self._tools = tools
        self.toolbar = DocumentToolbar(theme, self)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(editor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.splitter, 1)
        self.refresh_toolbar()

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(REFRESH_DELAY_MS)
        self._timer.timeout.connect(self.refresh)
        editor.textChanged.connect(self._schedule)
        vertical = editor.verticalScrollBar()
        if vertical is not None:
            vertical.valueChanged.connect(self._sync_scroll)

    @property
    def supports_preview(self) -> bool:
        return self.editor.language.id in PREVIEW_LANGUAGES

    def set_mode(self, mode: str) -> None:
        if mode not in VIEW_MODES:
            mode = TEXT
        if mode != TEXT and not self.supports_preview:
            mode = TEXT
        self.mode = mode
        self.toolbar.set_mode(mode)
        if mode == TEXT:
            if self.preview is not None:
                self.preview.hide()
            self.editor.show()
            return
        self._ensure_preview()
        assert self.preview is not None
        self.preview.show()
        self.editor.setVisible(mode == SPLIT)
        if mode == SPLIT:
            half = max(1, self.width() // 2)
            self.splitter.setSizes([half, half])
        self.refresh()

    def refresh_toolbar(self) -> None:
        """Show the tools and view buttons that fit the document's language."""
        self.toolbar.set_tools(self._tools(self.editor) if self._tools else [])
        self.toolbar.set_modes_visible(self.supports_preview)
        self.toolbar.set_mode(self.mode if self.supports_preview else TEXT)

    def language_changed(self) -> None:
        """Drop a preview that no longer fits the document's language."""
        self.refresh_toolbar()
        if self.preview is not None and self.editor.language.id != self._preview_language:
            self.preview.deleteLater()
            self.preview = None
        if self.mode != TEXT:
            self.set_mode(self.mode)

    def _ensure_preview(self) -> None:
        if self.preview is not None:
            return
        self.preview = create_preview(self.editor.language.id, self._theme)
        self._preview_language = self.editor.language.id
        if self.preview is not None:
            self.splitter.addWidget(self.preview)

    def apply_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.toolbar.apply_theme(theme)
        if self.preview is not None:
            self.preview.apply_theme(theme)
            if self.mode != TEXT:
                self.refresh()

    def _schedule(self) -> None:
        if self.mode != TEXT:
            self._timer.start()

    def refresh(self) -> None:
        if self.preview is None or self.mode == TEXT:
            return
        if self.editor.length() > MAX_PREVIEW_CHARS:
            from forge.i18n.translator import tr

            self.preview.show_message(tr("This document is too large to preview."))
            return
        if self.editor.language.id == "csv":
            self.preview.delimiter = self.editor.csv_delimiter
        self.preview.show_document(str(self.editor.text()), self.editor.doc.path)

    def _sync_scroll(self, value: int) -> None:
        if self.mode != SPLIT or self.preview is None:
            return
        bar = self.editor.verticalScrollBar()
        maximum = bar.maximum() if bar is not None else 0
        self.preview.scroll_to_ratio(value / maximum if maximum else 0.0)

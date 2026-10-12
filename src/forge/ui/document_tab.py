"""An editor tab: a ForgeEditor bound to a Document."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PyQt6.QtWidgets import QToolButton, QWidget

from forge.core.document import Document
from forge.core.settings import EditorSettings
from forge.editor.forge_editor import ForgeEditor
from forge.i18n.translator import tr
from forge.themes.theme import Theme


def _local_files(event: QDropEvent | QDragEnterEvent | QDragMoveEvent) -> list[Path]:
    mime = event.mimeData()
    if mime is None or not mime.hasUrls():
        return []
    return [Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile()]


def document_title(document: Document) -> str:
    """Name shown in tabs and dialogs; untitled documents are translated ("nieuw 1")."""
    if document.path is not None:
        return document.path.name
    return tr("new {number}", number=document.untitled_index)


class DocumentTab(ForgeEditor):
    """Editor widget that knows which document it shows.

    Dropping files on the editor opens them instead of inserting their paths.
    """

    files_dropped = pyqtSignal(list)

    def __init__(
        self,
        document: Document,
        settings: EditorSettings,
        theme: Theme,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(settings, theme, parent)
        self.doc = document  # not `document`: that name is a QsciScintilla method
        # Scintilla can only clear its modified flag. Text restored from a
        # session backup differs from the file on disk, so it is marked here.
        self._forced_dirty = False
        self.close_button: QToolButton | None = None

    @property
    def title(self) -> str:
        return document_title(self.doc)

    @property
    def is_dirty(self) -> bool:
        return self._forced_dirty or bool(self.isModified())

    def setModified(self, m: bool) -> None:
        was_dirty = self.is_dirty
        self._forced_dirty = m
        super().setModified(m)
        if self.is_dirty != was_dirty:
            self.modificationChanged.emit(self.is_dirty)

    def dragEnterEvent(self, event: QDragEnterEvent | None) -> None:
        if event is None:
            return
        if _local_files(event):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent | None) -> None:
        if event is None:
            return
        if _local_files(event):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent | None) -> None:
        if event is None:
            return
        files = _local_files(event)
        if files:
            event.acceptProposedAction()
            self.files_dropped.emit(files)
            return
        super().dropEvent(event)

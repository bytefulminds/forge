"""An editor tab: a ForgeEditor bound to a Document."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PyQt6.QtWidgets import QToolButton, QWidget

from forge.core.document import Document
from forge.core.settings import EditorSettings
from forge.editor.diagnostics import check
from forge.editor.forge_editor import ForgeEditor
from forge.editor.lexers import Language
from forge.i18n.translator import tr
from forge.themes.theme import Theme
from forge.ui.notice_bar import Notice


def _local_files(event: QDropEvent | QDragEnterEvent | QDragMoveEvent) -> list[Path]:
    mime = event.mimeData()
    if mime is None or not mime.hasUrls():
        return []
    return [Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile()]


CHECK_DELAY_MS = 500


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
    diagnostic_changed = pyqtSignal()

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
        # The DocumentPage holding this editor (set by the main window).
        self.page: QWidget | None = None
        # True while a large file is streamed in; the tab is read-only then.
        self.loading = False
        # Message shown in the notice bar while this tab is active.
        self.notice: Notice | None = None
        # Live syntax check, a moment after typing stops.
        self._check_timer = QTimer(self)
        self._check_timer.setSingleShot(True)
        self._check_timer.setInterval(CHECK_DELAY_MS)
        self._check_timer.timeout.connect(self.run_check)
        self.textChanged.connect(self._check_timer.start)

    def schedule_check(self) -> None:
        self._check_timer.start()

    def run_check(self) -> None:
        """Check the syntax now and underline the first error, if any."""
        found = None
        if self._settings.check_syntax and not self.large_file and not self.loading:
            found = check(
                self.language.id, self.doc.path, str(self.text()), self.csv_delimiter_for_check
            )
        if found != self.diagnostic:
            self.set_diagnostic(found)
            self.diagnostic_changed.emit()
        elif found is not None:
            self.set_diagnostic(found)  # positions may have moved

    @property
    def csv_delimiter_for_check(self) -> str | None:
        return self.csv_delimiter if self.language.id == "csv" else None

    def set_csv_delimiter(self, delimiter: str | None) -> None:
        super().set_csv_delimiter(delimiter)
        if hasattr(self, "_check_timer"):
            self.schedule_check()
        page = getattr(self, "page", None)
        if page is not None and hasattr(page, "refresh"):
            page.refresh()

    def set_language(self, language: Language) -> None:
        super().set_language(language)
        if hasattr(self, "_check_timer"):
            self.schedule_check()
        page = getattr(self, "page", None)
        if page is not None and hasattr(page, "language_changed"):
            page.language_changed()

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

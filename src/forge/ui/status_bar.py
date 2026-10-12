"""Status bar: cursor position on the left, language, line endings and encoding on the right."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QMenu, QStatusBar, QToolButton, QWidget

from forge.editor.lexers import PLAIN_TEXT
from forge.i18n.translator import tr
from forge.ui.document_tab import DocumentTab


def _separator() -> QFrame:
    line = QFrame()
    line.setObjectName("statusSeparator")
    line.setFixedSize(1, 12)
    return line


class ForgeStatusBar(QStatusBar):
    def __init__(self, language_menu: QMenu, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizeGripEnabled(False)
        self.position = QLabel()

        # Clickable: opens the same menu as Language in the menu bar.
        self.language = QToolButton()
        self.language.setObjectName("statusSegment")
        self.language.setMenu(language_menu)
        self.language.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.language.setCursor(Qt.CursorShape.PointingHandCursor)
        self.language.setToolTip(tr("Change the language of this document"))

        # Read-only until switching encodings and line endings arrives (phase b).
        self.eol = QLabel()
        self.eol.setToolTip(tr("Line endings"))
        self.encoding = QLabel()
        self.encoding.setToolTip(tr("Encoding"))

        self.addWidget(self.position)
        self.addPermanentWidget(self.language)
        self.addPermanentWidget(_separator())
        self.addPermanentWidget(self.eol)
        self.addPermanentWidget(_separator())
        self.addPermanentWidget(self.encoding)

    def show_tab(self, tab: DocumentTab | None) -> None:
        if tab is None:
            self.position.clear()
            self.language.setText("")
            self.eol.clear()
            self.encoding.clear()
            return
        self.update_position(tab)
        language = tab.language
        self.language.setText(tr("Normal text") if language is PLAIN_TEXT else language.name)
        self.eol.setText(tab.doc.eol.label)
        self.encoding.setText(tab.doc.encoding.label)

    def update_position(self, tab: DocumentTab) -> None:
        line, col = tab.getCursorPosition()
        text = tr("Ln {line}, Col {col}", line=line + 1, col=col + 1)
        selected = len(tab.selectedText())
        if selected:
            text += tr(", {count} selected", count=selected)
        self.position.setText(text)

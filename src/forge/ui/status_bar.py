"""Status bar: cursor position, language, line endings and encoding."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QStatusBar, QWidget

from forge.editor.lexers import PLAIN_TEXT
from forge.i18n.translator import tr
from forge.ui.document_tab import DocumentTab


class ForgeStatusBar(QStatusBar):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizeGripEnabled(False)
        self.position = QLabel()
        self.language = QLabel()
        self.eol = QLabel()
        self.encoding = QLabel()
        self.addWidget(self.position)
        for label in (self.language, self.eol, self.encoding):
            self.addPermanentWidget(label)

    def show_tab(self, tab: DocumentTab | None) -> None:
        if tab is None:
            for label in (self.position, self.language, self.eol, self.encoding):
                label.clear()
            return
        self.update_position(tab)
        language = tab.language
        self.language.setText(tr("Normal text") if language is PLAIN_TEXT else language.name)
        self.eol.setText(tab.doc.eol.label)
        self.encoding.setText(tab.doc.encoding.label)

    def update_position(self, tab: DocumentTab) -> None:
        line, col = tab.getCursorPosition()
        selected = len(tab.selectedText())
        self.position.setText(
            tr("Ln {line}, Col {col}, Sel {sel}", line=line + 1, col=col + 1, sel=selected)
        )

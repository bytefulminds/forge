"""Status bar: cursor position on the left, language, line endings and encoding on the right."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QMenu, QStatusBar, QToolButton, QWidget

from forge.core.csvtext import split_line, unquote
from forge.editor.lexers import PLAIN_TEXT
from forge.i18n.translator import tr
from forge.ui.document_tab import DocumentTab


def _separator() -> QFrame:
    line = QFrame()
    line.setObjectName("statusSeparator")
    line.setFixedSize(1, 12)
    return line


def _segment(menu: QMenu, tooltip: str) -> QToolButton:
    button = QToolButton()
    button.setObjectName("statusSegment")
    button.setMenu(menu)
    button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setToolTip(tooltip)
    return button


def delimiter_name(delimiter: str) -> str:
    return {
        ",": tr("Comma"),
        ";": tr("Semicolon"),
        "\t": tr("Tab"),
        "|": tr("Pipe"),
    }.get(delimiter, delimiter)


class ForgeStatusBar(QStatusBar):
    def __init__(
        self,
        language_menu: QMenu,
        eol_menu: QMenu,
        encoding_menu: QMenu,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setSizeGripEnabled(False)
        # Clicking the position opens Go to Line, as in Notepad++.
        self.position = QToolButton()
        self.position.setObjectName("statusSegment")
        self.position.setCursor(Qt.CursorShape.PointingHandCursor)
        self.position.setToolTip(tr("Go to line"))

        # Clickable segments open the same menus as the menu bar.
        self.language = _segment(language_menu, tr("Change the language of this document"))
        self.eol = _segment(eol_menu, tr("Line endings"))
        self.encoding = _segment(encoding_menu, tr("Encoding"))

        # CSV only: the column at the cursor and the delimiter (click to change).
        self.column = QToolButton()
        self.column.setObjectName("statusSegment")
        self.column.setToolTip(tr("Column at the cursor"))
        self.column.hide()
        self.delimiter = QToolButton()
        self.delimiter.setObjectName("statusSegment")
        self.delimiter.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delimiter.setToolTip(tr("Delimiter used to read this file"))
        self._delimiter_separator = _separator()

        # Shown only when the document has a syntax error; click to jump to it.
        self.problem = QToolButton()
        self.problem.setObjectName("statusProblem")
        self.problem.setCursor(Qt.CursorShape.PointingHandCursor)
        self.problem.hide()

        self.addWidget(self.position)
        self.addWidget(self.column)
        self.addWidget(self.problem)
        self.addPermanentWidget(self.delimiter)
        self.addPermanentWidget(self._delimiter_separator)
        self.addPermanentWidget(self.language)
        self.addPermanentWidget(_separator())
        self.addPermanentWidget(self.eol)
        self.addPermanentWidget(_separator())
        self.addPermanentWidget(self.encoding)

    def show_tab(self, tab: DocumentTab | None) -> None:
        self.show_problem(tab)
        is_csv = tab is not None and tab.language.id == "csv"
        self.delimiter.setVisible(is_csv)
        self._delimiter_separator.setVisible(is_csv)
        if tab is not None and is_csv:
            self.delimiter.setText(delimiter_name(tab.csv_delimiter))
        if tab is None:
            self.column.hide()
            self.position.setText("")
            self.language.setText("")
            self.eol.setText("")
            self.encoding.setText("")
            return
        self.update_position(tab)
        language = tab.language
        self.language.setText(tr("Normal text") if language is PLAIN_TEXT else language.name)
        self.eol.setText(tab.doc.eol.label)
        self.encoding.setText(tab.doc.encoding.label)

    def show_problem(self, tab: DocumentTab | None) -> None:
        diagnostic = tab.diagnostic if tab is not None else None
        if diagnostic is None:
            self.problem.hide()
            return
        self.problem.setText(tr("Error on line {line}", line=diagnostic.line))
        self.problem.setToolTip(diagnostic.message)
        self.problem.show()

    def update_position(self, tab: DocumentTab) -> None:
        line, col = tab.getCursorPosition()
        text = tr("Ln {line}, Col {col}", line=line + 1, col=col + 1)
        selected = len(tab.selectedText())
        if selected:
            text += tr(", {count} selected", count=selected)
        self.position.setText(text)
        self._update_column(tab, line, col)

    def _update_column(self, tab: DocumentTab, line: int, index: int) -> None:
        if tab.language.id != "csv":
            self.column.hide()
            return
        delimiter = tab.csv_delimiter
        self.delimiter.setText(delimiter_name(delimiter))
        before = str(tab.text(line))[:index]
        number = len(split_line(before, delimiter))
        header = split_line(str(tab.text(0)).rstrip("\r\n"), delimiter)
        name = unquote(header[number - 1]).strip() if number <= len(header) else ""
        if name and line > 0 and tab.csv_header:
            text = tr("Column {number}: {name}", number=number, name=name)
        else:
            text = tr("Column {number}", number=number)
        self.column.setText(text)
        self.column.show()
